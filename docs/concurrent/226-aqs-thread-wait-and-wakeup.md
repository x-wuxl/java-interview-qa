---
layout: default
title: "AQS是如何实现线程的等待和唤醒的？"
parent: 并发编程
nav_order: 226
description: "深入解析AQS如何通过LockSupport和park/unpark机制实现高效的线程阻塞与唤醒"
author: "wuxl"
date: 2025-11-02
---
## 问题

AQS是如何实现线程的等待和唤醒的？

## 答案

### 1. 核心机制

AQS 通过 **LockSupport** 类的 `park()` 和 `unpark()` 方法实现线程的阻塞和唤醒。这是一种比 `Object.wait()`/`notify()` 更底层、更灵活的线程同步机制。

**关键特点**：
- 不需要持有锁或监视器
- 可以先 `unpark()` 再 `park()`（有许可证机制）
- 直接操作线程，而不是对象
- 基于 Unsafe 类的本地方法实现

### 2. LockSupport 原理

#### 2.1 核心方法

```java
public class LockSupport {
    // 阻塞当前线程，直到获得许可证
    public static void park(Object blocker) {
        Thread t = Thread.currentThread();
        setBlocker(t, blocker);  // 设置阻塞对象，便于诊断
        UNSAFE.park(false, 0L);   // 调用 native 方法
        setBlocker(t, null);
    }

    // 无限期阻塞当前线程
    public static void park() {
        UNSAFE.park(false, 0L);
    }

    // 阻塞当前线程，最多等待指定的纳秒数
    public static void parkNanos(long nanos) {
        if (nanos > 0)
            UNSAFE.park(false, nanos);
    }

    // 唤醒指定线程
    public static void unpark(Thread thread) {
        if (thread != null)
            UNSAFE.unpark(thread);
    }
}
```

#### 2.2 许可证机制

每个线程都有一个**许可证（permit）**，可以理解为一个二元信号量（0 或 1）：

- **park()**：如果许可证可用，则消耗许可证并立即返回；否则阻塞线程
- **unpark(thread)**：为指定线程提供许可证。如果线程正在阻塞，则唤醒；如果线程未阻塞，下次 `park()` 将立即返回

**重要特性**：
```java
// 场景 1：先 park，后 unpark
Thread t = new Thread(() -> {
    LockSupport.park();  // 阻塞
    System.out.println("唤醒");
});
t.start();
Thread.sleep(1000);
LockSupport.unpark(t);  // 唤醒线程

// 场景 2：先 unpark，后 park（不会阻塞）
Thread t = new Thread(() -> {
    try {
        Thread.sleep(1000);
        LockSupport.park();  // 不会阻塞，因为已有许可证
        System.out.println("立即返回");
    } catch (InterruptedException e) {}
});
t.start();
LockSupport.unpark(t);  // 提前发放许可证
```

### 3. AQS 中的应用

#### 3.1 获取锁失败时的阻塞

当线程竞争锁失败后，会在同步队列中阻塞等待：

```java
// 获取锁失败后的处理逻辑（简化版）
final boolean acquireQueued(final Node node, int arg) {
    boolean failed = true;
    try {
        boolean interrupted = false;
        for (;;) {  // 自旋
            final Node p = node.predecessor();

            // 如果前驱是 head，尝试获取锁
            if (p == head && tryAcquire(arg)) {
                setHead(node);
                p.next = null;
                failed = false;
                return interrupted;
            }

            // 判断是否需要阻塞
            if (shouldParkAfterFailedAcquire(p, node) &&
                parkAndCheckInterrupt())  // 阻塞当前线程
                interrupted = true;
        }
    } finally {
        if (failed)
            cancelAcquire(node);
    }
}

// 判断获取锁失败后是否应该阻塞
private static boolean shouldParkAfterFailedAcquire(Node pred, Node node) {
    int ws = pred.waitStatus;

    if (ws == Node.SIGNAL)
        // 前驱节点状态为 SIGNAL，表示会唤醒当前节点，可以安全阻塞
        return true;

    if (ws > 0) {
        // 前驱节点已取消，跳过这些节点
        do {
            node.prev = pred = pred.prev;
        } while (pred.waitStatus > 0);
        pred.next = node;
    } else {
        // 将前驱节点状态设置为 SIGNAL
        compareAndSetWaitStatus(pred, ws, Node.SIGNAL);
    }

    return false;
}

// 阻塞当前线程并检查中断状态
private final boolean parkAndCheckInterrupt() {
    LockSupport.park(this);  // 核心：阻塞当前线程
    return Thread.interrupted();  // 返回并清除中断状态
}
```

**流程说明**：
1. 线程获取锁失败，加入同步队列
2. 自旋检查前驱节点，如果前驱是 head，尝试获取锁
3. 如果前驱不是 head 或获取失败，检查是否应该阻塞
4. 调用 `LockSupport.park(this)` 阻塞当前线程

#### 3.2 释放锁时的唤醒

当持有锁的线程释放锁时，会唤醒同步队列中的后继节点：

```java
// 释放锁（简化版）
public final boolean release(int arg) {
    if (tryRelease(arg)) {  // 尝试释放锁
        Node h = head;
        if (h != null && h.waitStatus != 0)
            unparkSuccessor(h);  // 唤醒后继节点
        return true;
    }
    return false;
}

// 唤醒后继节点
private void unparkSuccessor(Node node) {
    int ws = node.waitStatus;

    // 清除头节点的 SIGNAL 状态
    if (ws < 0)
        compareAndSetWaitStatus(node, ws, 0);

    // 找到需要唤醒的节点（通常是下一个节点）
    Node s = node.next;

    // 如果下一个节点为空或已取消，从尾部向前查找有效节点
    if (s == null || s.waitStatus > 0) {
        s = null;
        for (Node t = tail; t != null && t != node; t = t.prev)
            if (t.waitStatus <= 0)
                s = t;
    }

    // 唤醒线程
    if (s != null)
        LockSupport.unpark(s.thread);  // 核心：唤醒线程
}
```

**流程说明**：
1. 线程释放锁成功
2. 检查头节点的 `waitStatus`，如果不为 0，说明有等待的线程
3. 找到下一个需要唤醒的节点（非取消状态）
4. 调用 `LockSupport.unpark(thread)` 唤醒线程

#### 3.3 条件队列中的等待与唤醒

在条件队列中，`await()` 和 `signal()` 也使用 LockSupport：

```java
// await() 实现（简化版）
public final void await() throws InterruptedException {
    Node node = addConditionWaiter();  // 加入条件队列
    int savedState = fullyRelease(node);  // 完全释放锁

    int interruptMode = 0;
    while (!isOnSyncQueue(node)) {
        LockSupport.park(this);  // 阻塞当前线程
        if ((interruptMode = checkInterruptWhileWaiting(node)) != 0)
            break;
    }

    // 被唤醒后，重新竞争锁
    if (acquireQueued(node, savedState) && interruptMode != THROW_IE)
        interruptMode = REINTERRUPT;

    // ... 后续处理
}

// signal() 实现（简化版）
public final void signal() {
    Node first = firstWaiter;
    if (first != null)
        doSignal(first);
}

private void doSignal(Node first) {
    // 将节点从条件队列转移到同步队列
    Node p = enq(first);
    int ws = p.waitStatus;

    // 唤醒线程
    if (ws > 0 || !compareAndSetWaitStatus(p, ws, Node.SIGNAL))
        LockSupport.unpark(first.thread);  // 唤醒线程
}
```

### 4. 与 wait/notify 的对比

| 特性 | LockSupport.park/unpark | Object.wait/notify |
|------|------------------------|--------------------|
| **是否需要锁** | 不需要 | 必须在 synchronized 块中 |
| **操作对象** | 线程 | 对象监视器 |
| **许可证机制** | 有（可先 unpark 后 park） | 无（必须先 wait 后 notify） |
| **精准唤醒** | 可以指定唤醒哪个线程 | notifyAll 会唤醒所有线程 |
| **中断响应** | 可以响应中断 | 可以响应中断 |
| **性能** | 更高效（基于 Unsafe） | 依赖 JVM 监视器锁 |

### 5. 性能优化考量

#### 5.1 自旋 + 阻塞策略

AQS 采用**先自旋后阻塞**的策略，减少上下文切换：

```java
for (;;) {  // 自旋一定次数
    if (前驱是 head && 获取锁成功) {
        return;
    }
    if (应该阻塞()) {
        LockSupport.park(this);  // 自旋失败后阻塞
    }
}
```

#### 5.2 避免虚假唤醒

LockSupport 可能发生虚假唤醒（spurious wakeup），因此 AQS 使用循环检查条件：

```java
for (;;) {
    LockSupport.park(this);
    if (条件满足) {
        break;
    }
}
```

#### 5.3 中断处理

`park()` 会响应中断，但不会抛出异常，通过 `Thread.interrupted()` 检查并记录中断状态：

```java
private final boolean parkAndCheckInterrupt() {
    LockSupport.park(this);
    return Thread.interrupted();  // 检查并清除中断标志
}
```

### 6. 底层实现

LockSupport 的 `park/unpark` 最终调用 Unsafe 类的本地方法：

```java
// Unsafe 类中的方法
public native void park(boolean isAbsolute, long time);
public native void unpark(Object thread);
```

这些方法在不同操作系统上有不同实现：
- **Linux**：基于 `pthread_mutex` 和 `pthread_cond`
- **Windows**：基于 `WaitForSingleObject` 和 `SetEvent`

### 7. 总结

AQS 通过 **LockSupport.park/unpark** 实现线程的等待和唤醒：

1. **阻塞机制**：调用 `LockSupport.park()` 阻塞当前线程，比 `wait()` 更灵活
2. **唤醒机制**：调用 `LockSupport.unpark(thread)` 唤醒指定线程，实现精准控制
3. **许可证机制**：允许先 `unpark` 后 `park`，避免信号丢失问题
4. **高性能**：基于 Unsafe 的本地方法，不依赖重量级监视器锁
5. **结合自旋**：先自旋后阻塞，减少上下文切换开销

**面试要点**：
- 明确指出使用 LockSupport 而非 wait/notify
- 说明许可证机制的优势（可先 unpark 后 park）
- 理解在同步队列和条件队列中的应用场景
- 对比与 Object.wait/notify 的区别

理解这一机制是掌握 AQS、ReentrantLock、Semaphore 等并发工具实现原理的关键。
