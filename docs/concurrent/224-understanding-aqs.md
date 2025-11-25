---
layout: default
title: "如何理解AQS？"
parent: 并发编程
nav_order: 224
description: "深入理解AbstractQueuedSynchronizer（AQS）的核心概念、设计原理与应用场景"
author: "wuxl"
date: 2025-11-02
---
## 问题

如何理解AQS？

## 答案

### 1. 核心概念

**AQS**（AbstractQueuedSynchronizer，抽象队列同步器）是 `java.util.concurrent` 包中的核心基础组件，由 Doug Lea 设计。它为实现依赖于先进先出（FIFO）等待队列的阻塞锁和同步器提供了一个框架。

AQS 是构建锁和同步器的基础，JUC 包中的很多同步工具类都是基于 AQS 实现的，包括：
- **ReentrantLock**（可重入锁）
- **Semaphore**（信号量）
- **CountDownLatch**（倒计数器）
- **ReentrantReadWriteLock**（读写锁）
- **ThreadPoolExecutor** 中的 Worker

### 2. 设计原理

#### 2.1 核心数据结构

AQS 维护了两个关键部分：

```java
// 同步状态，通过 CAS 操作保证原子性
private volatile int state;

// CLH 队列的头节点和尾节点
private transient volatile Node head;
private transient volatile Node tail;
```

**state 变量**：
- 表示同步状态，0 表示未锁定，大于 0 表示锁定
- 通过 `volatile` 保证可见性
- 通过 CAS（Compare-And-Swap）保证原子性修改

**CLH 队列**（Craig, Landin, and Hagersten 队列）：
- 是一个双向链表的变体
- 每个节点（Node）代表一个等待获取锁的线程
- 节点包含：线程引用、等待状态、前驱和后继指针

#### 2.2 工作机制

AQS 定义了两种资源共享方式：

1. **Exclusive（独占模式）**：只有一个线程能执行，如 ReentrantLock
2. **Share（共享模式）**：多个线程可同时执行，如 Semaphore、CountDownLatch

**获取锁的流程**：
```java
// 伪代码示例
public final void acquire(int arg) {
    if (!tryAcquire(arg)) {  // 尝试获取锁
        // 获取失败，将当前线程加入等待队列
        Node node = addWaiter(Node.EXCLUSIVE);
        // 在队列中自旋等待或阻塞
        acquireQueued(node, arg);
    }
}
```

**释放锁的流程**：
```java
// 伪代码示例
public final boolean release(int arg) {
    if (tryRelease(arg)) {  // 尝试释放锁
        Node h = head;
        if (h != null && h.waitStatus != 0)
            unparkSuccessor(h);  // 唤醒后继节点
        return true;
    }
    return false;
}
```

#### 2.3 模板方法模式

AQS 使用了**模板方法设计模式**，定义了同步器的骨架，将具体的实现细节交给子类：

需要子类重写的方法：
- `tryAcquire(int)`：独占式获取同步状态
- `tryRelease(int)`：独占式释放同步状态
- `tryAcquireShared(int)`：共享式获取同步状态
- `tryReleaseShared(int)`：共享式释放同步状态
- `isHeldExclusively()`：判断当前线程是否独占资源

### 3. 核心特性

#### 3.1 状态管理

```java
// 获取同步状态
protected final int getState() {
    return state;
}

// 设置同步状态
protected final void setState(int newState) {
    state = newState;
}

// CAS 更新同步状态
protected final boolean compareAndSetState(int expect, int update) {
    return unsafe.compareAndSwapInt(this, stateOffset, expect, update);
}
```

#### 3.2 线程阻塞与唤醒

AQS 通过 `LockSupport.park()` 和 `LockSupport.unpark()` 实现线程的阻塞和唤醒：
- **park()**：阻塞当前线程
- **unpark(Thread)**：唤醒指定线程

### 4. 应用示例

以 **ReentrantLock** 为例，看 AQS 如何被使用：

```java
public class ReentrantLock implements Lock {
    // 内部使用 Sync 继承 AQS
    private final Sync sync;

    abstract static class Sync extends AbstractQueuedSynchronizer {
        // 实现 tryAcquire 等方法
    }

    // 公平锁实现
    static final class FairSync extends Sync {
        protected final boolean tryAcquire(int acquires) {
            // 检查队列，公平地获取锁
        }
    }

    // 非公平锁实现
    static final class NonfairSync extends Sync {
        protected final boolean tryAcquire(int acquires) {
            // 直接尝试获取锁，不检查队列
        }
    }
}
```

### 5. 性能优化考量

- **CAS + volatile**：避免重量级锁，提高并发性能
- **自旋 + 阻塞**：获取锁时先自旋一定次数，减少上下文切换
- **双向链表**：支持快速的节点插入和删除操作
- **状态标识**：通过节点的 waitStatus 减少不必要的唤醒操作

### 6. 总结

AQS 是并发编程的基石，理解 AQS 需要掌握：

1. **核心思想**：通过 state 变量表示同步状态，通过 FIFO 队列管理竞争线程
2. **设计模式**：模板方法模式，提供框架由子类实现具体逻辑
3. **两种模式**：独占模式（如 ReentrantLock）和共享模式（如 Semaphore）
4. **关键技术**：CAS 操作、LockSupport、CLH 队列变体
5. **应用广泛**：JUC 包中大量同步工具类都是基于 AQS 构建的

在面试中，能够说清楚 AQS 的 state + FIFO 队列的核心机制，以及它如何通过模板方法模式被 ReentrantLock 等类使用，就能体现对并发编程的深刻理解。
