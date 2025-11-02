---
layout: post
title: "什么是可重入锁，怎么实现可重入锁？"
date: 2025-11-02
description: "深入理解可重入锁的概念、作用及其在synchronized和ReentrantLock中的实现原理"
author: "wuxl"
categories: [并发编程]
tags: [可重入锁, ReentrantLock, synchronized, 线程安全]
---

## 问题

什么是可重入锁，怎么实现可重入锁？

## 答案

### 1. 核心概念

**可重入锁（Reentrant Lock）**：也叫递归锁，指的是同一个线程在持有锁的情况下，可以再次获取该锁，而不会造成死锁。

**通俗理解**：
- 一个线程获得锁后，可以多次进入被该锁保护的代码块
- 每次进入锁的计数器加 1，每次退出锁的计数器减 1
- 当计数器为 0 时，锁才真正释放

### 2. 为什么需要可重入锁

#### 2.1 避免死锁

如果锁不可重入，同一个线程多次获取锁会导致死锁：

```java
// 假设锁不可重入
synchronized (this) {
    System.out.println("第一次获取锁");
    synchronized (this) {  // 死锁！同一个线程无法再次获取锁
        System.out.println("第二次获取锁");
    }
}
```

#### 2.2 支持递归调用

```java
public synchronized void methodA() {
    System.out.println("methodA");
    methodB();  // 调用另一个同步方法
}

public synchronized void methodB() {
    System.out.println("methodB");
    // 如果锁不可重入，这里会死锁
}
```

#### 2.3 简化代码结构

可重入锁让方法调用链中的每个方法都可以独立使用 synchronized，无需担心死锁。

### 3. Java 中的可重入锁

Java 中的以下锁都是可重入的：
- **synchronized**
- **ReentrantLock**
- **ReentrantReadWriteLock**

### 4. synchronized 的可重入实现

#### 4.1 实现原理

synchronized 通过**对象头的 Mark Word** 和**锁计数器**实现可重入：

```java
// 对象头结构（Mark Word，64 位 JVM）
| 锁状态   | 存储内容                    | 锁标志位 |
|---------|----------------------------|---------|
| 偏向锁  | 线程 ID + Epoch + 对象分代年龄 | 01      |
| 轻量级锁 | 指向栈中锁记录的指针           | 00      |
| 重量级锁 | 指向 Monitor 对象的指针        | 10      |
```

**重入逻辑**：
1. 线程首次获取锁：在对象头记录线程 ID，计数器设为 1
2. 线程再次获取锁：检查线程 ID 匹配，计数器 +1
3. 线程释放锁：计数器 -1，当计数器为 0 时真正释放锁

#### 4.2 代码示例

```java
public class SynchronizedReentrant {
    public synchronized void outer() {
        System.out.println("外层方法");
        inner();  // 调用内层方法
    }

    public synchronized void inner() {
        System.out.println("内层方法");
    }

    public static void main(String[] args) {
        SynchronizedReentrant obj = new SynchronizedReentrant();
        obj.outer();  // 正常执行，不会死锁
    }
}

// 输出：
// 外层方法
// 内层方法
```

**执行流程**：
1. 线程调用 `outer()`，获取 `obj` 的锁，计数器 = 1
2. 线程调用 `inner()`，检测到已持有锁，计数器 = 2
3. `inner()` 执行完，计数器 = 1
4. `outer()` 执行完，计数器 = 0，释放锁

### 5. ReentrantLock 的可重入实现

#### 5.1 实现原理

ReentrantLock 基于 **AQS** 的 **state 变量**和**线程持有者**实现可重入：

```java
public class ReentrantLock implements Lock {
    private final Sync sync;

    abstract static class Sync extends AbstractQueuedSynchronizer {
        // 记录锁的持有线程
        private transient Thread exclusiveOwnerThread;

        // 尝试获取锁（非公平）
        final boolean nonfairTryAcquire(int acquires) {
            final Thread current = Thread.currentThread();
            int c = getState();  // 获取 AQS 的 state

            if (c == 0) {  // 锁未被占用
                if (compareAndSetState(0, acquires)) {  // CAS 获取锁
                    setExclusiveOwnerThread(current);  // 记录持有线程
                    return true;
                }
            } else if (current == getExclusiveOwnerThread()) {  // 可重入逻辑
                int nextc = c + acquires;  // 计数器 +1
                if (nextc < 0)  // 溢出检查
                    throw new Error("Maximum lock count exceeded");
                setState(nextc);  // 更新 state
                return true;
            }

            return false;
        }

        // 尝试释放锁
        protected final boolean tryRelease(int releases) {
            int c = getState() - releases;  // 计数器 -1

            if (Thread.currentThread() != getExclusiveOwnerThread())
                throw new IllegalMonitorStateException();

            boolean free = false;
            if (c == 0) {  // 计数器为 0，真正释放锁
                free = true;
                setExclusiveOwnerThread(null);  // 清除持有线程
            }

            setState(c);  // 更新 state
            return free;
        }
    }
}
```

**核心要素**：
- **state 变量**：表示锁的持有次数（0 表示未锁定，>0 表示重入次数）
- **exclusiveOwnerThread**：记录当前持有锁的线程
- **重入判断**：检查当前线程是否等于 `exclusiveOwnerThread`

#### 5.2 代码示例

```java
public class ReentrantLockExample {
    private final ReentrantLock lock = new ReentrantLock();

    public void outer() {
        lock.lock();  // 第一次获取锁，state = 1
        try {
            System.out.println("外层方法，state = " + lock.getHoldCount());
            inner();  // 调用内层方法
        } finally {
            lock.unlock();  // 释放锁，state = 0
        }
    }

    public void inner() {
        lock.lock();  // 第二次获取锁（可重入），state = 2
        try {
            System.out.println("内层方法，state = " + lock.getHoldCount());
        } finally {
            lock.unlock();  // 释放锁，state = 1
        }
    }

    public static void main(String[] args) {
        ReentrantLockExample example = new ReentrantLockExample();
        example.outer();
    }
}

// 输出：
// 外层方法，state = 1
// 内层方法，state = 2
```

### 6. 手动实现一个简单的可重入锁

```java
public class SimpleReentrantLock {
    // 记录持有锁的线程
    private Thread owner;
    // 重入计数器
    private int count = 0;

    // 加锁
    public synchronized void lock() {
        Thread current = Thread.currentThread();

        // 如果是当前线程持有锁，计数器 +1（可重入）
        if (owner == current) {
            count++;
            return;
        }

        // 否则等待锁释放
        while (owner != null) {
            try {
                wait();  // 阻塞等待
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }

        // 获取锁
        owner = current;
        count = 1;
    }

    // 解锁
    public synchronized void unlock() {
        if (Thread.currentThread() != owner) {
            throw new IllegalMonitorStateException("当前线程未持有锁");
        }

        count--;  // 计数器 -1

        if (count == 0) {  // 真正释放锁
            owner = null;
            notify();  // 唤醒等待的线程
        }
    }
}
```

**测试代码**：
```java
public class TestSimpleReentrantLock {
    private static SimpleReentrantLock lock = new SimpleReentrantLock();

    public static void outer() {
        lock.lock();
        try {
            System.out.println("外层方法");
            inner();
        } finally {
            lock.unlock();
        }
    }

    public static void inner() {
        lock.lock();  // 可重入
        try {
            System.out.println("内层方法");
        } finally {
            lock.unlock();
        }
    }

    public static void main(String[] args) {
        outer();  // 正常执行，不会死锁
    }
}
```

### 7. 实现要点总结

实现可重入锁需要：

1. **记录持有锁的线程**（`Thread owner` 或对象头的线程 ID）
2. **维护重入计数器**（`int count` 或 AQS 的 `state`）
3. **加锁逻辑**：
   - 如果锁未被持有，获取锁并设置计数器为 1
   - 如果当前线程已持有锁，计数器 +1（可重入）
   - 否则阻塞等待
4. **解锁逻辑**：
   - 计数器 -1
   - 当计数器为 0 时，清除持有线程，真正释放锁

### 8. 对比：可重入 vs 不可重入

| 特性 | 可重入锁 | 不可重入锁 |
|------|---------|-----------|
| **同一线程多次获取** | ✅ 允许 | ❌ 死锁 |
| **递归调用** | ✅ 支持 | ❌ 不支持 |
| **实现复杂度** | 需要计数器和线程记录 | 简单（只需一个标志位） |
| **典型代表** | synchronized, ReentrantLock | 无（Java 标准库中的锁都是可重入的） |

### 9. 性能考量

- **计数器开销**：每次重入需要增减计数器，但开销很小
- **线程检查开销**：需要比较当前线程与持有线程，开销也很小
- **避免死锁收益**：可重入锁极大简化了代码结构，避免了复杂的死锁场景

### 10. 注意事项

#### 10.1 加锁和解锁次数必须匹配

```java
lock.lock();
lock.lock();  // 重入一次
try {
    // 业务代码
} finally {
    lock.unlock();
    lock.unlock();  // 必须解锁两次
}
```

#### 10.2 不要忘记释放锁

```java
lock.lock();
try {
    // 业务代码
} finally {
    lock.unlock();  // 必须在 finally 中释放
}
```

### 11. 总结

**可重入锁的核心**：
1. **定义**：同一个线程可以多次获取同一把锁，不会死锁
2. **作用**：支持递归调用，简化代码结构
3. **实现要素**：
   - 记录持有锁的线程（Thread ID 或 exclusiveOwnerThread）
   - 维护重入计数器（对象头的计数或 AQS 的 state）
4. **Java 中的可重入锁**：synchronized、ReentrantLock、ReentrantReadWriteLock

**面试要点**：
- 明确可重入锁的定义和作用
- 说明 synchronized 和 ReentrantLock 的可重入实现原理
- 强调计数器和线程持有者两个关键要素
- 能够手写一个简单的可重入锁（加分项）

**记忆口诀**：
- 线程记录要保存，计数器来控状态
- 加锁加一减锁减，归零释放唤后来
