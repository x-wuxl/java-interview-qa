---
layout: default
title: "公平锁和非公平锁的区别"
parent: 并发编程
nav_order: 232
description: "深入理解公平锁和非公平锁的概念、实现原理、性能差异及应用场景"
author: "wuxl"
date: 2025-11-02
---
## 问题

公平锁和非公平锁的区别？

## 答案

### 1. 核心概念

**公平锁（Fair Lock）**：
- 多个线程按照**申请锁的顺序**获取锁，先到先得（FIFO）
- 等待时间最长的线程优先获得锁

**非公平锁（Unfair Lock）**：
- 线程获取锁时**不考虑等待队列**，直接尝试获取锁
- 可能出现"插队"现象，后来的线程可能先获得锁

**通俗理解**：
- **公平锁**：像排队买票，先来的先买
- **非公平锁**：不排队，谁抢到谁买（新来的人可能先买到）

### 2. 实现对比

#### 2.1 ReentrantLock 的两种模式

ReentrantLock 支持公平和非公平两种模式：

```java
// 非公平锁（默认）
ReentrantLock unfairLock = new ReentrantLock();
// 或
ReentrantLock unfairLock = new ReentrantLock(false);

// 公平锁
ReentrantLock fairLock = new ReentrantLock(true);
```

#### 2.2 非公平锁的实现

```java
// ReentrantLock 的非公平锁实现
static final class NonfairSync extends Sync {
    final void lock() {
        // 1. 直接尝试 CAS 获取锁（插队）
        if (compareAndSetState(0, 1))
            setExclusiveOwnerThread(Thread.currentThread());
        else
            acquire(1);  // CAS 失败，进入正常流程
    }

    protected final boolean tryAcquire(int acquires) {
        return nonfairTryAcquire(acquires);
    }
}

final boolean nonfairTryAcquire(int acquires) {
    final Thread current = Thread.currentThread();
    int c = getState();

    if (c == 0) {  // 锁未被占用
        // 2. 不检查队列，直接 CAS 获取锁（插队）
        if (compareAndSetState(0, acquires)) {
            setExclusiveOwnerThread(current);
            return true;
        }
    } else if (current == getExclusiveOwnerThread()) {
        // 可重入逻辑
        int nextc = c + acquires;
        setState(nextc);
        return true;
    }

    return false;
}
```

**关键点**：
- **不检查等待队列**，直接尝试 CAS 获取锁
- 新来的线程可能"插队"成功，跳过等待队列中的线程

#### 2.3 公平锁的实现

```java
// ReentrantLock 的公平锁实现
static final class FairSync extends Sync {
    final void lock() {
        acquire(1);  // 直接进入正常流程，不尝试插队
    }

    protected final boolean tryAcquire(int acquires) {
        final Thread current = Thread.currentThread();
        int c = getState();

        if (c == 0) {  // 锁未被占用
            // 关键：检查队列中是否有等待的线程
            if (!hasQueuedPredecessors() &&  // 队列中没有前驱节点
                compareAndSetState(0, acquires)) {
                setExclusiveOwnerThread(current);
                return true;
            }
        } else if (current == getExclusiveOwnerThread()) {
            // 可重入逻辑
            int nextc = c + acquires;
            setState(nextc);
            return true;
        }

        return false;
    }
}

// 检查队列中是否有前驱节点
public final boolean hasQueuedPredecessors() {
    Node t = tail;
    Node h = head;
    Node s;

    // 队列不为空 && (头节点的下一个节点为空 || 下一个节点的线程不是当前线程)
    return h != t &&
           ((s = h.next) == null || s.thread != Thread.currentThread());
}
```

**关键点**：
- **检查等待队列**：通过 `hasQueuedPredecessors()` 判断是否有线程在排队
- 只有队列为空或当前线程是队首，才能获取锁
- 严格按照 FIFO 顺序分配锁

### 3. 执行流程对比

#### 3.1 非公平锁流程

```
线程 A 持有锁
          |
线程 B、C、D 在队列中等待
          |
线程 A 释放锁
          |
线程 E 新到达 ──┐
                ├──> 线程 E 直接尝试 CAS 获取锁（插队）
                │
                ├──> 成功：线程 E 获得锁（跳过 B、C、D）
                │
                └──> 失败：线程 E 加入队列尾部，线程 B 获得锁
```

**示例代码**：
```java
public class UnfairLockExample {
    private static ReentrantLock lock = new ReentrantLock(false);  // 非公平锁

    public static void main(String[] args) {
        Runnable task = () -> {
            for (int i = 0; i < 2; i++) {
                lock.lock();
                try {
                    System.out.println(Thread.currentThread().getName() + " 获得锁");
                } finally {
                    lock.unlock();
                }
            }
        };

        Thread t1 = new Thread(task, "线程1");
        Thread t2 = new Thread(task, "线程2");
        Thread t3 = new Thread(task, "线程3");

        t1.start();
        t2.start();
        t3.start();
    }
}

// 可能的输出（非公平，顺序不确定）：
// 线程1 获得锁
// 线程1 获得锁  ← 线程1 释放后立即重新获得（插队）
// 线程2 获得锁
// 线程3 获得锁
// 线程2 获得锁
// 线程3 获得锁
```

#### 3.2 公平锁流程

```
线程 A 持有锁
          |
线程 B、C、D 在队列中等待（按顺序）
          |
线程 A 释放锁
          |
线程 E 新到达 ──┐
                ├──> 线程 E 检查队列
                │
                ├──> 发现有 B、C、D 在等待
                │
                └──> 线程 E 加入队列尾部，线程 B 获得锁（FIFO）
```

**示例代码**：
```java
public class FairLockExample {
    private static ReentrantLock lock = new ReentrantLock(true);  // 公平锁

    public static void main(String[] args) {
        Runnable task = () -> {
            for (int i = 0; i < 2; i++) {
                lock.lock();
                try {
                    System.out.println(Thread.currentThread().getName() + " 获得锁");
                } finally {
                    lock.unlock();
                }
            }
        };

        Thread t1 = new Thread(task, "线程1");
        Thread t2 = new Thread(task, "线程2");
        Thread t3 = new Thread(task, "线程3");

        t1.start();
        t2.start();
        t3.start();
    }
}

// 可能的输出（公平，基本按顺序）：
// 线程1 获得锁
// 线程2 获得锁  ← 公平分配
// 线程3 获得锁
// 线程1 获得锁
// 线程2 获得锁
// 线程3 获得锁
```

### 4. 详细对比

| 特性 | 公平锁 | 非公平锁 |
|------|--------|---------|
| **获取锁顺序** | 严格按 FIFO 顺序 | 不保证顺序，可能插队 |
| **是否检查队列** | ✅ 检查队列是否有前驱节点 | ❌ 不检查队列，直接 CAS |
| **吞吐量** | 低（频繁的上下文切换） | 高（减少上下文切换） |
| **性能** | 较低 | 较高 |
| **线程饥饿** | ✅ 不会饥饿（保证公平） | ❌ 可能饥饿（长时间得不到锁） |
| **实现复杂度** | 较高（需要维护队列顺序） | 较低 |
| **默认模式** | ReentrantLock 非默认 | ReentrantLock 默认 |

### 5. 性能差异

#### 5.1 非公平锁性能更好的原因

**原因 1：减少线程切换**
```
非公平锁：
线程 A 释放锁 → 线程 A 立即重新获得锁（不切换）

公平锁：
线程 A 释放锁 → 唤醒线程 B → 线程 B 获得锁（上下文切换）
```

**原因 2：减少唤醒开销**
- 非公平锁：如果新线程能立即获得锁，无需唤醒队列中的线程
- 公平锁：每次都需要唤醒队列中的下一个线程

**性能测试结果**：
- 非公平锁的吞吐量通常是公平锁的 **10-100 倍**（高竞争场景）
- 但非公平锁可能导致某些线程长时间无法获得锁（饥饿）

### 6. synchronized 是公平还是非公平

**synchronized 是非公平锁**：
- 不保证等待线程的获取顺序
- JVM 的实现不遵循 FIFO 原则
- 优先考虑性能而非公平性

```java
public synchronized void method() {
    // 非公平锁，不保证顺序
}
```

### 7. 应用场景

#### 7.1 使用非公平锁

**场景**：
- 对吞吐量要求高
- 不关心线程获取锁的顺序
- 任务执行时间较短

**示例**：
- 缓存操作
- 统计计数器
- 高频率的读写操作

```java
ReentrantLock lock = new ReentrantLock();  // 默认非公平锁
```

#### 7.2 使用公平锁

**场景**：
- 需要严格按顺序处理请求
- 防止线程饥饿
- 任务执行时间较长

**示例**：
- 订单处理系统（先来先服务）
- 任务调度系统
- 需要保证顺序的业务逻辑

```java
ReentrantLock lock = new ReentrantLock(true);  // 公平锁
```

### 8. 线程饥饿问题

#### 8.1 非公平锁的饥饿风险

```java
public class StarvationExample {
    private static ReentrantLock lock = new ReentrantLock(false);  // 非公平锁

    public static void main(String[] args) {
        // 10 个高频线程
        for (int i = 0; i < 10; i++) {
            new Thread(() -> {
                while (true) {
                    lock.lock();
                    try {
                        // 快速执行
                    } finally {
                        lock.unlock();
                    }
                }
            }, "高频线程" + i).start();
        }

        // 1 个低频线程
        new Thread(() -> {
            lock.lock();
            try {
                System.out.println("低频线程终于获得锁");  // 可能很久才打印
            } finally {
                lock.unlock();
            }
        }, "低频线程").start();
    }
}
```

**问题**：高频线程不断"插队"，低频线程可能长时间无法获得锁。

#### 8.2 公平锁避免饥饿

```java
ReentrantLock lock = new ReentrantLock(true);  // 公平锁
// 低频线程按顺序排队，最终一定能获得锁
```

### 9. 性能优化建议

1. **默认使用非公平锁**：在大多数情况下性能更好
2. **特殊场景用公平锁**：需要严格顺序或防止饥饿时
3. **减少锁持有时间**：无论公平与否，快速释放锁都能提升性能
4. **考虑读写锁**：如果读多写少，使用 `ReentrantReadWriteLock`

### 10. 总结

**公平锁**：
- 严格按 FIFO 顺序分配锁
- 保证公平性，避免饥饿
- 性能较低（频繁的上下文切换）
- 适用于对顺序敏感的场景

**非公平锁**：
- 不保证顺序，允许"插队"
- 吞吐量高，性能好
- 可能导致线程饥饿
- Java 默认选择（synchronized、ReentrantLock 默认）

**面试要点**：
1. **定义区别**：公平锁按顺序，非公平锁可插队
2. **实现差异**：公平锁检查队列（`hasQueuedPredecessors()`），非公平锁直接 CAS
3. **性能对比**：非公平锁性能显著优于公平锁（10-100 倍）
4. **应用场景**：默认用非公平锁，特殊场景用公平锁
5. **synchronized**：属于非公平锁

**记忆口诀**：
- 公平排队讲顺序，非公平插队效率高
- 默认非公平性能好,特殊场景公平保
