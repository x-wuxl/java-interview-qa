---
title: "什么是AQS的独占模式和共享模式？"
date: 2025-11-02
description: "深入理解AQS的独占模式（Exclusive）和共享模式（Shared）的原理、区别与应用场景"
author: "wuxl"
categories: [并发编程]
tags: [AQS, 独占模式, 共享模式, ReentrantLock, Semaphore]
nav_order: 228
parent: 并发编程
---
## 问题

什么是AQS的独占模式和共享模式？

## 答案

### 1. 核心概念

AQS 定义了两种资源共享方式，用于支持不同类型的同步器：

- **独占模式（Exclusive）**：同一时刻只有一个线程能持有资源，如 **ReentrantLock**
- **共享模式（Shared）**：同一时刻允许多个线程同时持有资源，如 **Semaphore**、**CountDownLatch**、**ReentrantReadWriteLock** 的读锁

这两种模式通过 AQS 提供的不同方法实现，核心区别在于 `state` 变量的语义和节点的唤醒策略。

### 2. 独占模式（Exclusive）

#### 2.1 基本原理

在独占模式下，只有一个线程能成功获取资源（锁），其他线程必须等待。

**核心方法**：
```java
// 子类需要实现的方法
protected boolean tryAcquire(int arg);      // 尝试独占式获取资源
protected boolean tryRelease(int arg);      // 尝试独占式释放资源
protected boolean isHeldExclusively();      // 判断是否独占资源

// AQS 提供的模板方法
public final void acquire(int arg);         // 获取资源（阻塞）
public final boolean release(int arg);      // 释放资源
public final void acquireInterruptibly(int arg);  // 可中断获取
public final boolean tryAcquireNanos(int arg, long nanosTimeout);  // 超时获取
```

#### 2.2 实现示例：ReentrantLock

```java
public class ReentrantLock implements Lock {
    private final Sync sync;

    abstract static class Sync extends AbstractQueuedSynchronizer {
        // 尝试获取锁（独占模式）
        protected final boolean tryAcquire(int acquires) {
            final Thread current = Thread.currentThread();
            int c = getState();

            if (c == 0) {  // 锁未被占用
                if (compareAndSetState(0, acquires)) {  // CAS 获取锁
                    setExclusiveOwnerThread(current);  // 设置独占线程
                    return true;
                }
            } else if (current == getExclusiveOwnerThread()) {  // 可重入
                int nextc = c + acquires;
                setState(nextc);
                return true;
            }

            return false;  // 获取失败
        }

        // 尝试释放锁（独占模式）
        protected final boolean tryRelease(int releases) {
            int c = getState() - releases;

            if (Thread.currentThread() != getExclusiveOwnerThread())
                throw new IllegalMonitorStateException();

            boolean free = false;
            if (c == 0) {  // 完全释放锁
                free = true;
                setExclusiveOwnerThread(null);
            }

            setState(c);
            return free;
        }

        // 判断是否独占
        protected final boolean isHeldExclusively() {
            return getExclusiveOwnerThread() == Thread.currentThread();
        }
    }
}
```

#### 2.3 独占模式的流程

**获取资源**：
```java
public final void acquire(int arg) {
    if (!tryAcquire(arg) &&  // 1. 尝试获取资源
        acquireQueued(addWaiter(Node.EXCLUSIVE), arg))  // 2. 失败则加入队列（独占节点）
        selfInterrupt();
}
```

**释放资源**：
```java
public final boolean release(int arg) {
    if (tryRelease(arg)) {  // 1. 尝试释放资源
        Node h = head;
        if (h != null && h.waitStatus != 0)
            unparkSuccessor(h);  // 2. 唤醒下一个等待的线程
        return true;
    }
    return false;
}
```

**特点**：
- 只唤醒**一个**后继节点
- `state` 通常表示锁的持有次数（0 表示未锁定，>0 表示重入次数）
- 队列中的节点类型为 `Node.EXCLUSIVE`（实际为 `null`）

### 3. 共享模式（Shared）

#### 3.1 基本原理

在共享模式下，多个线程可以同时持有资源，直到资源耗尽。

**核心方法**：
```java
// 子类需要实现的方法
protected int tryAcquireShared(int arg);      // 尝试共享式获取资源（返回剩余资源数）
protected boolean tryReleaseShared(int arg);  // 尝试共享式释放资源

// AQS 提供的模板方法
public final void acquireShared(int arg);     // 获取共享资源（阻塞）
public final boolean releaseShared(int arg);  // 释放共享资源
public final void acquireSharedInterruptibly(int arg);  // 可中断获取
public final boolean tryAcquireSharedNanos(int arg, long nanosTimeout);  // 超时获取
```

#### 3.2 实现示例：Semaphore

```java
public class Semaphore implements java.io.Serializable {
    private final Sync sync;

    abstract static class Sync extends AbstractQueuedSynchronizer {
        Sync(int permits) {
            setState(permits);  // state 表示可用许可数
        }

        // 尝试获取许可（共享模式）
        protected int tryAcquireShared(int acquires) {
            for (;;) {
                int available = getState();  // 当前可用许可数
                int remaining = available - acquires;

                if (remaining < 0 ||  // 许可不足
                    compareAndSetState(available, remaining))  // CAS 减少许可
                    return remaining;  // 返回剩余许可数
            }
        }

        // 尝试释放许可（共享模式）
        protected boolean tryReleaseShared(int releases) {
            for (;;) {
                int current = getState();
                int next = current + releases;

                if (compareAndSetState(current, next))  // CAS 增加许可
                    return true;
            }
        }
    }

    // 获取许可
    public void acquire() throws InterruptedException {
        sync.acquireSharedInterruptibly(1);
    }

    // 释放许可
    public void release() {
        sync.releaseShared(1);
    }
}
```

#### 3.3 共享模式的流程

**获取资源**：
```java
public final void acquireShared(int arg) {
    if (tryAcquireShared(arg) < 0)  // 1. 尝试获取资源，返回剩余资源数
        doAcquireShared(arg);  // 2. 失败则加入队列（共享节点）
}

private void doAcquireShared(int arg) {
    final Node node = addWaiter(Node.SHARED);  // 创建共享节点
    boolean failed = true;
    try {
        boolean interrupted = false;
        for (;;) {
            final Node p = node.predecessor();
            if (p == head) {
                int r = tryAcquireShared(arg);  // 尝试获取
                if (r >= 0) {  // 获取成功
                    setHeadAndPropagate(node, r);  // 设置头节点并传播唤醒
                    p.next = null;
                    if (interrupted)
                        selfInterrupt();
                    failed = false;
                    return;
                }
            }
            if (shouldParkAfterFailedAcquire(p, node) &&
                parkAndCheckInterrupt())
                interrupted = true;
        }
    } finally {
        if (failed)
            cancelAcquire(node);
    }
}
```

**释放资源**：
```java
public final boolean releaseShared(int arg) {
    if (tryReleaseShared(arg)) {  // 1. 尝试释放资源
        doReleaseShared();  // 2. 唤醒后继的共享节点
        return true;
    }
    return false;
}

private void doReleaseShared() {
    for (;;) {
        Node h = head;
        if (h != null && h != tail) {
            int ws = h.waitStatus;
            if (ws == Node.SIGNAL) {
                if (!compareAndSetWaitStatus(h, Node.SIGNAL, 0))
                    continue;
                unparkSuccessor(h);  // 唤醒后继节点
            } else if (ws == 0 &&
                       !compareAndSetWaitStatus(h, 0, Node.PROPAGATE))
                continue;
        }
        if (h == head)  // 头节点未变化则退出
            break;
    }
}
```

**特点**：
- 唤醒操作会**传播**，可能唤醒多个后继节点
- `state` 表示可用资源数（如 Semaphore 的许可数）
- 队列中的节点类型为 `Node.SHARED`

#### 3.4 传播机制

共享模式的核心是**唤醒传播**：

```java
private void setHeadAndPropagate(Node node, int propagate) {
    Node h = head;
    setHead(node);  // 设置为新的头节点

    // 如果还有剩余资源，继续唤醒后继节点
    if (propagate > 0 || h == null || h.waitStatus < 0 ||
        (h = head) == null || h.waitStatus < 0) {
        Node s = node.next;
        if (s == null || s.isShared())  // 后继是共享节点
            doReleaseShared();  // 继续传播唤醒
    }
}
```

### 4. 两种模式的对比

| 特性 | 独占模式（Exclusive） | 共享模式（Shared） |
|------|---------------------|------------------|
| **资源持有** | 同一时刻只有一个线程 | 同一时刻可多个线程 |
| **state 语义** | 锁的持有次数（重入次数） | 可用资源数量 |
| **节点类型** | `Node.EXCLUSIVE`（`null`） | `Node.SHARED` |
| **唤醒策略** | 只唤醒一个后继节点 | 唤醒操作会传播，可能唤醒多个节点 |
| **tryAcquire/tryRelease** | 返回 `boolean` | `tryAcquireShared` 返回 `int`（剩余资源数） |
| **典型实现** | ReentrantLock、ReentrantReadWriteLock 的写锁 | Semaphore、CountDownLatch、ReentrantReadWriteLock 的读锁 |

### 5. 混合模式：ReentrantReadWriteLock

`ReentrantReadWriteLock` 同时使用了两种模式：

```java
public class ReentrantReadWriteLock {
    private final ReadLock readerLock;
    private final WriteLock writerLock;

    // 读锁：共享模式
    public static class ReadLock implements Lock {
        protected int tryAcquireShared(int unused) {
            // 允许多个线程同时持有读锁
        }
    }

    // 写锁：独占模式
    public static class WriteLock implements Lock {
        protected boolean tryAcquire(int acquires) {
            // 只允许一个线程持有写锁
        }
    }
}
```

**state 的巧妙设计**：
- 高 16 位：表示读锁的持有次数（共享模式）
- 低 16 位：表示写锁的持有次数（独占模式）

```java
static final int SHARED_SHIFT   = 16;
static final int SHARED_UNIT    = (1 << SHARED_SHIFT);  // 读锁计数单位
static final int MAX_COUNT      = (1 << SHARED_SHIFT) - 1;
static final int EXCLUSIVE_MASK = (1 << SHARED_SHIFT) - 1;  // 写锁掩码

// 读锁持有次数
static int sharedCount(int c)    { return c >>> SHARED_SHIFT; }

// 写锁持有次数
static int exclusiveCount(int c) { return c & EXCLUSIVE_MASK; }
```

### 6. 应用场景

**独占模式**：
- **互斥锁**：ReentrantLock、synchronized 的替代品
- **写锁**：保证数据修改的互斥性

**共享模式**：
- **信号量**：Semaphore 控制并发访问数量
- **倒计数**：CountDownLatch 实现线程协调
- **读锁**：允许多个线程同时读取数据
- **栅栏**：CyclicBarrier 等待多个线程到达某个点

### 7. 性能考量

**独占模式**：
- 唤醒开销小（只唤醒一个线程）
- 适合竞争激烈的场景

**共享模式**：
- 唤醒可能传播，开销较大
- 但允许更高的并发度，适合读多写少的场景

### 8. 总结

AQS 的独占模式和共享模式是两种基本的资源共享方式：

1. **独占模式**：
   - 同一时刻只有一个线程能持有资源
   - 实现方法：`tryAcquire/tryRelease`
   - 典型应用：ReentrantLock、写锁

2. **共享模式**：
   - 同一时刻允许多个线程持有资源
   - 实现方法：`tryAcquireShared/tryReleaseShared`
   - 唤醒会传播，可能唤醒多个线程
   - 典型应用：Semaphore、CountDownLatch、读锁

3. **灵活组合**：
   - 可以在同一个类中混合使用两种模式（如 ReentrantReadWriteLock）
   - 通过 `state` 的不同位表示不同类型的资源

**面试要点**：
- 清楚说明两种模式的核心区别（单线程 vs 多线程）
- 举例说明典型应用（ReentrantLock vs Semaphore）
- 理解共享模式的传播机制
- 了解 ReentrantReadWriteLock 如何同时使用两种模式

掌握这两种模式是理解 JUC 包中各种同步工具实现原理的关键。
