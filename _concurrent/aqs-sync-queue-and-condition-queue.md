---
title: "AQS的同步队列和条件队列原理"
date: 2025-11-02
description: "详解AQS中同步队列（Sync Queue）和条件队列（Condition Queue）的实现原理与协作机制"
author: "wuxl"
categories: [并发编程]
tags: [AQS, 同步队列, 条件队列, CLH, Condition]
nav_order: 225
parent: 并发编程
---
## 问题

AQS的同步队列和条件队列原理？

## 答案

### 1. 核心概念

AQS 维护了两种队列来管理线程：
- **同步队列（Sync Queue）**：用于管理竞争锁失败而等待的线程
- **条件队列（Condition Queue）**：用于实现条件等待机制（如 `await()`/`signal()`）

这两个队列协同工作，实现了完整的线程同步和通信机制。

### 2. 同步队列（Sync Queue）

#### 2.1 数据结构

同步队列是一个**双向链表**，基于 **CLH 锁队列**的变体实现。

```java
static final class Node {
    // 节点模式
    static final Node SHARED = new Node();    // 共享模式
    static final Node EXCLUSIVE = null;        // 独占模式

    // 等待状态
    static final int CANCELLED =  1;   // 线程已取消
    static final int SIGNAL    = -1;   // 后继节点需要被唤醒
    static final int CONDITION = -2;   // 节点在条件队列中
    static final int PROPAGATE = -3;   // 共享模式下，释放操作需要传播

    volatile int waitStatus;           // 等待状态
    volatile Node prev;                // 前驱节点
    volatile Node next;                // 后继节点
    volatile Thread thread;            // 当前线程
    Node nextWaiter;                   // 条件队列的下一个节点
}

// AQS 中的队列头尾指针
private transient volatile Node head;
private transient volatile Node tail;
```

#### 2.2 入队过程

当线程获取锁失败时，会被包装成 Node 节点加入同步队列的尾部：

```java
// 添加节点到队列尾部（简化版）
private Node addWaiter(Node mode) {
    Node node = new Node(Thread.currentThread(), mode);

    // 快速尝试在尾部添加
    Node pred = tail;
    if (pred != null) {
        node.prev = pred;
        if (compareAndSetTail(pred, node)) {  // CAS 设置尾节点
            pred.next = node;
            return node;
        }
    }

    // 快速失败则进入完整的入队逻辑
    enq(node);
    return node;
}

// 完整的入队逻辑（自旋 + CAS）
private Node enq(final Node node) {
    for (;;) {  // 自旋直到成功
        Node t = tail;
        if (t == null) {  // 队列为空，初始化
            if (compareAndSetHead(new Node()))
                tail = head;
        } else {
            node.prev = t;
            if (compareAndSetTail(t, node)) {  // CAS 设置尾节点
                t.next = node;
                return t;
            }
        }
    }
}
```

#### 2.3 出队过程

只有队列头节点的后继节点才有资格被唤醒获取锁：

```java
// 节点在队列中等待获取锁（简化版）
final boolean acquireQueued(final Node node, int arg) {
    boolean failed = true;
    try {
        boolean interrupted = false;
        for (;;) {  // 自旋
            final Node p = node.predecessor();  // 获取前驱节点

            // 只有前驱是 head 时才尝试获取锁
            if (p == head && tryAcquire(arg)) {
                setHead(node);  // 获取成功，设置为新的头节点
                p.next = null;  // 帮助 GC
                failed = false;
                return interrupted;
            }

            // 获取失败，判断是否需要阻塞
            if (shouldParkAfterFailedAcquire(p, node) &&
                parkAndCheckInterrupt())  // 阻塞当前线程
                interrupted = true;
        }
    } finally {
        if (failed)
            cancelAcquire(node);
    }
}
```

**队列特点**：
- 头节点是一个**虚拟节点**（哨兵节点），不代表任何线程
- 队列中的线程按照 FIFO 顺序竞争锁
- 使用 **CAS + 自旋**保证线程安全的入队和出队

### 3. 条件队列（Condition Queue）

#### 3.1 数据结构

条件队列是一个**单向链表**，由 `ConditionObject` 内部类实现：

```java
public class ConditionObject implements Condition {
    // 条件队列的首尾节点
    private transient Node firstWaiter;
    private transient Node lastWaiter;

    // await() 和 signal() 的实现
}
```

每个 `Condition` 对象都有自己独立的条件队列，一个 Lock 可以创建多个 Condition。

#### 3.2 await() 流程

线程调用 `await()` 时：

```java
public final void await() throws InterruptedException {
    // 1. 将当前线程包装成 Node，加入条件队列
    Node node = addConditionWaiter();

    // 2. 完全释放当前持有的锁
    int savedState = fullyRelease(node);

    // 3. 阻塞等待，直到被 signal() 或中断
    int interruptMode = 0;
    while (!isOnSyncQueue(node)) {  // 判断是否在同步队列中
        LockSupport.park(this);      // 阻塞当前线程
        if ((interruptMode = checkInterruptWhileWaiting(node)) != 0)
            break;
    }

    // 4. 被唤醒后，重新竞争锁
    if (acquireQueued(node, savedState) && interruptMode != THROW_IE)
        interruptMode = REINTERRUPT;

    // 5. 清理条件队列中的取消节点
    if (node.nextWaiter != null)
        unlinkCancelledWaiters();

    // 6. 处理中断
    if (interruptMode != 0)
        reportInterruptAfterWait(interruptMode);
}
```

#### 3.3 signal() 流程

线程调用 `signal()` 时：

```java
public final void signal() {
    if (!isHeldExclusively())  // 检查是否持有锁
        throw new IllegalMonitorStateException();

    Node first = firstWaiter;
    if (first != null)
        doSignal(first);  // 唤醒条件队列的第一个节点
}

private void doSignal(Node first) {
    do {
        // 1. 从条件队列中移除节点
        if ((firstWaiter = first.nextWaiter) == null)
            lastWaiter = null;
        first.nextWaiter = null;

        // 2. 将节点转移到同步队列
    } while (!transferForSignal(first) &&
             (first = firstWaiter) != null);
}

final boolean transferForSignal(Node node) {
    // 修改节点状态，从 CONDITION 改为 0
    if (!compareAndSetWaitStatus(node, Node.CONDITION, 0))
        return false;

    // 加入同步队列尾部
    Node p = enq(node);
    int ws = p.waitStatus;

    // 设置前驱节点状态为 SIGNAL，唤醒当前节点
    if (ws > 0 || !compareAndSetWaitStatus(p, ws, Node.SIGNAL))
        LockSupport.unpark(node.thread);

    return true;
}
```

### 4. 两个队列的协作

#### 4.1 完整流程示例

```java
Lock lock = new ReentrantLock();
Condition condition = lock.newCondition();

// 线程 A：等待条件
lock.lock();
try {
    while (!conditionSatisfied) {
        condition.await();  // 1. 进入条件队列
                            // 2. 释放锁
                            // 3. 阻塞等待
    }
    // 被唤醒后执行业务逻辑
} finally {
    lock.unlock();
}

// 线程 B：满足条件，通知等待线程
lock.lock();
try {
    conditionSatisfied = true;
    condition.signal();  // 1. 将条件队列节点转移到同步队列
                         // 2. 唤醒线程
} finally {
    lock.unlock();       // 3. 释放锁后，线程 A 才能竞争到锁
}
```

#### 4.2 流程图

```
获取锁失败 ──┐
            ├──> 加入同步队列 ──> 阻塞等待 ──> 被唤醒 ──> 竞争锁
            │
调用 await() ┘
            │
            ├──> 加入条件队列 ──> 阻塞等待 ──┐
                                            │
调用 signal() ────────────────────────────┘
            │
            └──> 转移到同步队列 ──> 唤醒线程 ──> 竞争锁
```

### 5. 两个队列的区别

| 特性 | 同步队列（Sync Queue） | 条件队列（Condition Queue） |
|------|----------------------|---------------------------|
| **数据结构** | 双向链表 | 单向链表 |
| **用途** | 管理竞争锁失败的线程 | 实现条件等待机制 |
| **节点状态** | SIGNAL、CANCELLED、PROPAGATE | CONDITION |
| **入队时机** | 获取锁失败时 | 调用 `await()` 时 |
| **出队时机** | 获取锁成功时 | 调用 `signal()`/`signalAll()` 时 |
| **队列数量** | 每个 AQS 实例一个 | 每个 Condition 一个（可多个） |

### 6. 性能考量

- **同步队列**：使用 **CAS + 自旋**保证高并发下的性能，避免重量级锁
- **条件队列**：不需要 CAS 操作，因为操作条件队列的前提是已持有锁
- **节点复用**：节点从条件队列转移到同步队列时，避免了对象创建开销
- **精准唤醒**：`signal()` 只唤醒一个线程，`signalAll()` 唤醒所有线程，可根据场景选择

### 7. 总结

**同步队列**：
- 管理竞争锁失败的线程，使用双向链表 + CAS 实现线程安全
- 基于 FIFO 顺序唤醒等待线程
- 头节点是虚拟节点，只有头节点的后继才能竞争锁

**条件队列**：
- 实现类似 `wait()`/`notify()` 的条件等待机制
- 调用 `await()` 时加入条件队列并释放锁
- 调用 `signal()` 时将节点从条件队列转移到同步队列

**协作机制**：
- 条件队列节点被唤醒后，会转移到同步队列重新竞争锁
- 这两个队列共同实现了 AQS 的完整同步能力

理解这两个队列的协作原理，是深入掌握 AQS 和 ReentrantLock、ReentrantReadWriteLock 等同步工具的关键。
