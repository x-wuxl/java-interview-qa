---
layout: default
title: "Lock是否公平，能否实现非公平，如何实现？"
parent: 并发编程
nav_order: 233
description: "深入解析Lock的公平性机制及公平锁和非公平锁的实现原理"
author: "wuxl"
date: 2025-11-02
---
## 问题

Lock是否公平，能否实现非公平，如何实现？

## 答案

### 1. 核心概念

**Lock 的公平性**：
- Lock 接口本身不规定是否公平
- 具体实现类（如 ReentrantLock）可以选择公平或非公平模式
- **默认是非公平锁**（性能更好）

**答案**：
- Lock 既可以是公平的，也可以是非公平的
- ReentrantLock 支持通过构造函数参数选择公平或非公平模式
- 默认情况下是非公平锁

### 2. ReentrantLock 的公平性选择

#### 2.1 构造函数

```java
// 默认非公平锁
ReentrantLock lock = new ReentrantLock();

// 显式指定非公平锁
ReentrantLock unfairLock = new ReentrantLock(false);

// 显式指定公平锁
ReentrantLock fairLock = new ReentrantLock(true);
```

#### 2.2 实现类结构

```java
public class ReentrantLock implements Lock {
    private final Sync sync;

    // 默认构造函数：非公平锁
    public ReentrantLock() {
        sync = new NonfairSync();
    }

    // 可指定公平性的构造函数
    public ReentrantLock(boolean fair) {
        sync = fair ? new FairSync() : new NonfairSync();
    }

    // 内部同步器基类
    abstract static class Sync extends AbstractQueuedSynchronizer {
        // 公共逻辑
    }

    // 非公平锁实现
    static final class NonfairSync extends Sync {
        // 非公平获取锁的逻辑
    }

    // 公平锁实现
    static final class FairSync extends Sync {
        // 公平获取锁的逻辑
    }
}
```

### 3. 非公平锁的实现原理

#### 3.1 核心代码

```java
static final class NonfairSync extends Sync {
    // 加锁
    final void lock() {
        // 1. 直接尝试 CAS 获取锁（插队机会 1）
        if (compareAndSetState(0, 1))
            setExclusiveOwnerThread(Thread.currentThread());
        else
            acquire(1);  // CAS 失败，进入正常流程
    }

    // 尝试获取锁
    protected final boolean tryAcquire(int acquires) {
        return nonfairTryAcquire(acquires);
    }
}

// 非公平获取锁的具体实现
final boolean nonfairTryAcquire(int acquires) {
    final Thread current = Thread.currentThread();
    int c = getState();

    if (c == 0) {  // 锁未被占用
        // 2. 不检查队列，直接 CAS 获取锁（插队机会 2）
        if (compareAndSetState(0, acquires)) {
            setExclusiveOwnerThread(current);
            return true;
        }
    } else if (current == getExclusiveOwnerThread()) {
        // 可重入逻辑
        int nextc = c + acquires;
        if (nextc < 0)  // 溢出检查
            throw new Error("Maximum lock count exceeded");
        setState(nextc);
        return true;
    }

    return false;
}
```

#### 3.2 非公平锁的特点

**两次"插队"机会**：

1. **第一次插队**：`lock()` 方法中直接 CAS 获取锁
   ```java
   if (compareAndSetState(0, 1))  // 直接尝试，不管队列
       setExclusiveOwnerThread(Thread.currentThread());
   ```

2. **第二次插队**：`tryAcquire()` 中再次尝试 CAS 获取锁
   ```java
   if (c == 0 && compareAndSetState(0, acquires))  // 仍然不检查队列
       return true;
   ```

**优势**：
- 减少线程切换，提高吞吐量
- 新线程可能立即获得锁，无需等待

**劣势**：
- 可能导致队列中的线程长时间等待（饥饿）
- 不保证获取锁的顺序

### 4. 公平锁的实现原理

#### 4.1 核心代码

```java
static final class FairSync extends Sync {
    // 加锁
    final void lock() {
        acquire(1);  // 直接进入正常流程，不尝试插队
    }

    // 尝试获取锁
    protected final boolean tryAcquire(int acquires) {
        final Thread current = Thread.currentThread();
        int c = getState();

        if (c == 0) {  // 锁未被占用
            // 关键：检查队列中是否有前驱节点
            if (!hasQueuedPredecessors() &&  // 必须队列为空或自己是队首
                compareAndSetState(0, acquires)) {
                setExclusiveOwnerThread(current);
                return true;
            }
        } else if (current == getExclusiveOwnerThread()) {
            // 可重入逻辑
            int nextc = c + acquires;
            if (nextc < 0)
                throw new Error("Maximum lock count exceeded");
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

#### 4.2 公平锁的特点

**严格按 FIFO 顺序**：
- 调用 `lock()` 时不尝试插队，直接进入 `acquire(1)`
- 在 `tryAcquire()` 中通过 `hasQueuedPredecessors()` 检查队列
- 只有队列为空或当前线程是队首，才能获取锁

**优势**：
- 保证获取锁的顺序，公平性
- 避免线程饥饿

**劣势**：
- 频繁的线程切换，降低吞吐量
- 性能比非公平锁差 10-100 倍

### 5. 关键方法：hasQueuedPredecessors()

#### 5.1 方法实现

```java
public final boolean hasQueuedPredecessors() {
    Node t = tail;
    Node h = head;
    Node s;

    // 条件 1：h != t（队列不为空）
    // 条件 2：(s = h.next) == null || s.thread != Thread.currentThread()
    //        （头节点的下一个节点为空 或 下一个节点的线程不是当前线程）
    return h != t &&
           ((s = h.next) == null || s.thread != Thread.currentThread());
}
```

#### 5.2 逻辑分析

**返回 `false`（可以获取锁）的情况**：
1. 队列为空（`h == t`）
2. 队列不为空，但当前线程是头节点的下一个节点（`s.thread == Thread.currentThread()`）

**返回 `true`（不能获取锁）的情况**：
1. 队列不为空，且当前线程不是队首（有其他线程在等待）

**特殊情况**：`s == null`
- 在并发环境下，`head.next` 可能尚未设置完成
- 此时保守地返回 `true`，让当前线程进入队列

### 6. 对比总结

| 特性 | 非公平锁 | 公平锁 |
|------|---------|--------|
| **检查队列** | ❌ 不检查 | ✅ 检查（`hasQueuedPredecessors()`） |
| **插队机会** | ✅ 两次（`lock()` 和 `tryAcquire()`） | ❌ 无 |
| **获取顺序** | 不保证 | 严格 FIFO |
| **性能** | 高（减少上下文切换） | 低（频繁切换） |
| **线程饥饿** | 可能 | 不会 |
| **默认** | ✅ ReentrantLock 默认 | ❌ 需显式指定 |

### 7. 性能测试

```java
public class LockPerformanceTest {
    private static final int THREAD_COUNT = 10;
    private static final int ITERATIONS = 100000;

    public static void main(String[] args) throws InterruptedException {
        testLock(new ReentrantLock(false), "非公平锁");
        testLock(new ReentrantLock(true), "公平锁");
    }

    static void testLock(ReentrantLock lock, String name) throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(THREAD_COUNT);
        long start = System.currentTimeMillis();

        for (int i = 0; i < THREAD_COUNT; i++) {
            new Thread(() -> {
                for (int j = 0; j < ITERATIONS; j++) {
                    lock.lock();
                    try {
                        // 空操作
                    } finally {
                        lock.unlock();
                    }
                }
                latch.countDown();
            }).start();
        }

        latch.await();
        long end = System.currentTimeMillis();
        System.out.println(name + " 耗时：" + (end - start) + " ms");
    }
}

// 可能的输出：
// 非公平锁 耗时：1523 ms
// 公平锁 耗时：15678 ms  （慢 10 倍以上）
```

### 8. 应用场景

#### 8.1 使用非公平锁

**场景**：
- 对吞吐量要求高
- 不关心获取锁的顺序
- 任务执行时间短

**示例**：
```java
public class Counter {
    private final ReentrantLock lock = new ReentrantLock();  // 默认非公平
    private int count = 0;

    public void increment() {
        lock.lock();
        try {
            count++;  // 快速操作
        } finally {
            lock.unlock();
        }
    }
}
```

#### 8.2 使用公平锁

**场景**：
- 需要严格按顺序处理请求
- 防止线程饥饿
- 任务执行时间较长

**示例**：
```java
public class OrderService {
    // 公平锁保证订单按顺序处理
    private final ReentrantLock lock = new ReentrantLock(true);

    public void processOrder(Order order) {
        lock.lock();
        try {
            // 处理订单（耗时操作）
            System.out.println("处理订单：" + order.getId());
        } finally {
            lock.unlock();
        }
    }
}
```

### 9. 其他 Lock 实现的公平性

#### 9.1 ReentrantReadWriteLock

```java
// 非公平读写锁（默认）
ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();

// 公平读写锁
ReentrantReadWriteLock fairRwLock = new ReentrantReadWriteLock(true);
```

#### 9.2 Semaphore

```java
// 非公平信号量（默认）
Semaphore semaphore = new Semaphore(10);

// 公平信号量
Semaphore fairSemaphore = new Semaphore(10, true);
```

### 10. 实现建议

**默认使用非公平锁**：
- 大多数场景下性能更好
- Java 标准库的默认选择

**特殊场景使用公平锁**：
- 需要严格顺序的业务逻辑
- 防止线程饥饿的关键任务
- 对公平性有明确要求

**混合策略**：
- 可以根据业务特点动态选择
- 例如：低负载时用公平锁，高负载时切换到非公平锁

### 11. 总结

**Lock 的公平性**：
1. **可选**：Lock 接口不规定公平性，由具体实现决定
2. **默认非公平**：ReentrantLock 默认是非公平锁
3. **构造函数选择**：通过 `new ReentrantLock(true/false)` 指定

**非公平锁实现**：
- 不检查队列，直接 CAS 获取锁
- 两次"插队"机会（`lock()` 和 `tryAcquire()`）
- 性能高，但可能饥饿

**公平锁实现**：
- 通过 `hasQueuedPredecessors()` 检查队列
- 只有队列为空或自己是队首才能获取锁
- 保证 FIFO，但性能低

**面试要点**：
1. **默认非公平**：ReentrantLock 默认是非公平锁
2. **构造参数**：通过 `new ReentrantLock(fair)` 选择
3. **实现差异**：非公平锁不检查队列，公平锁检查 `hasQueuedPredecessors()`
4. **性能对比**：非公平锁性能显著优于公平锁（10-100 倍）
5. **应用场景**：默认非公平，特殊场景用公平

**记忆口诀**：
- Lock 默认非公平，构造参数可指定
- 非公平插队效率高，公平排队保顺序
- hasQueuedPredecessors 是关键，检查队列保公平
