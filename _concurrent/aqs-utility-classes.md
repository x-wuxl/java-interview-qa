---
title: "AQS操作类有哪些？"
date: 2025-11-02
description: "全面介绍基于AQS实现的常用并发工具类及其应用场景"
author: "wuxl"
categories: [并发编程]
tags: [AQS, ReentrantLock, Semaphore, CountDownLatch, CyclicBarrier, 并发工具]
nav_order: 229
parent: 并发编程
---
## 问题

AQS操作类有哪些？

## 答案

### 1. 核心概念

AQS（AbstractQueuedSynchronizer）是 JUC 包中众多并发工具类的基础框架。基于 AQS 实现的同步器包括：

- **ReentrantLock**（可重入锁）
- **ReentrantReadWriteLock**（读写锁）
- **Semaphore**（信号量）
- **CountDownLatch**（倒计数器）
- **CyclicBarrier**（循环栅栏，间接基于 AQS）
- **ThreadPoolExecutor.Worker**（线程池的工作线程）

### 2. 主要AQS操作类详解

#### 2.1 ReentrantLock（可重入锁）

**核心特性**：
- 独占模式
- 支持公平/非公平锁
- 支持可中断、超时、尝试获取
- 支持多个条件变量

**使用场景**：
- 替代 synchronized，提供更灵活的锁机制
- 需要高级特性（超时、中断、公平锁）的场景

**示例**：
```java
ReentrantLock lock = new ReentrantLock();

lock.lock();
try {
    // 临界区代码
} finally {
    lock.unlock();
}

// 可中断获取
try {
    lock.lockInterruptibly();
    // 业务代码
} finally {
    lock.unlock();
}

// 超时获取
if (lock.tryLock(3, TimeUnit.SECONDS)) {
    try {
        // 业务代码
    } finally {
        lock.unlock();
    }
}
```

#### 2.2 ReentrantReadWriteLock（读写锁）

**核心特性**：
- 同时支持独占模式（写锁）和共享模式（读锁）
- 读锁可被多个线程同时持有
- 写锁是独占的
- 支持锁降级（写锁 → 读锁）

**使用场景**：
- 读多写少的场景
- 需要细粒度控制的数据结构（如缓存）

**示例**：
```java
ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();
Lock readLock = rwLock.readLock();
Lock writeLock = rwLock.writeLock();

// 读操作
readLock.lock();
try {
    // 读取数据（多个线程可同时读）
} finally {
    readLock.unlock();
}

// 写操作
writeLock.lock();
try {
    // 修改数据（独占）
} finally {
    writeLock.unlock();
}
```

**state 的巧妙设计**：
```java
// 高 16 位表示读锁持有次数，低 16 位表示写锁持有次数
static final int SHARED_SHIFT   = 16;
static final int SHARED_UNIT    = (1 << SHARED_SHIFT);
static final int MAX_COUNT      = (1 << SHARED_SHIFT) - 1;
static final int EXCLUSIVE_MASK = (1 << SHARED_SHIFT) - 1;

// 读锁持有次数
static int sharedCount(int c)    { return c >>> SHARED_SHIFT; }

// 写锁持有次数
static int exclusiveCount(int c) { return c & EXCLUSIVE_MASK; }
```

#### 2.3 Semaphore（信号量）

**核心特性**：
- 共享模式
- 控制同时访问某个资源的线程数量
- state 表示可用许可数

**使用场景**：
- 限流（控制并发数）
- 资源池管理（如数据库连接池）
- 停车场管理（车位数量限制）

**示例**：
```java
// 创建一个有 3 个许可的信号量
Semaphore semaphore = new Semaphore(3);

// 获取许可
semaphore.acquire();
try {
    // 访问资源（最多 3 个线程同时访问）
} finally {
    semaphore.release();  // 释放许可
}

// 尝试获取
if (semaphore.tryAcquire()) {
    try {
        // 业务代码
    } finally {
        semaphore.release();
    }
}

// 一次获取多个许可
semaphore.acquire(2);
try {
    // 业务代码
} finally {
    semaphore.release(2);
}
```

**实际案例：限流**：
```java
public class RateLimiter {
    private final Semaphore semaphore;

    public RateLimiter(int maxConcurrent) {
        this.semaphore = new Semaphore(maxConcurrent);
    }

    public void execute(Runnable task) throws InterruptedException {
        semaphore.acquire();
        try {
            task.run();
        } finally {
            semaphore.release();
        }
    }
}

// 使用
RateLimiter limiter = new RateLimiter(10);  // 最多 10 个并发
limiter.execute(() -> {
    // 业务逻辑
});
```

#### 2.4 CountDownLatch（倒计数器）

**核心特性**：
- 共享模式
- 一次性使用（不可重置）
- state 表示剩余计数
- 线程等待计数归零

**使用场景**：
- 主线程等待多个子线程完成
- 并行任务的协调
- 批量任务的同步

**示例**：
```java
// 创建一个计数为 3 的 CountDownLatch
CountDownLatch latch = new CountDownLatch(3);

// 3 个工作线程
for (int i = 0; i < 3; i++) {
    new Thread(() -> {
        try {
            // 执行任务
            System.out.println(Thread.currentThread().getName() + " 完成任务");
        } finally {
            latch.countDown();  // 计数 -1
        }
    }, "Worker-" + i).start();
}

// 主线程等待所有工作线程完成
latch.await();
System.out.println("所有任务完成");
```

**实际案例：并行初始化**：
```java
public class ParallelInitializer {
    public void initialize() throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(3);

        // 初始化数据库连接
        new Thread(() -> {
            initDatabase();
            latch.countDown();
        }).start();

        // 初始化缓存
        new Thread(() -> {
            initCache();
            latch.countDown();
        }).start();

        // 初始化消息队列
        new Thread(() -> {
            initMQ();
            latch.countDown();
        }).start();

        // 等待所有初始化完成
        latch.await();
        System.out.println("系统初始化完成");
    }
}
```

#### 2.5 CyclicBarrier（循环栅栏）

**核心特性**：
- 基于 ReentrantLock + Condition（间接基于 AQS）
- 可重复使用
- 线程到达栅栏后等待其他线程
- 所有线程到齐后一起继续执行

**使用场景**：
- 多线程计算任务的阶段同步
- 游戏中的多人就绪
- 分布式任务的屏障点

**示例**：
```java
// 创建一个等待 3 个线程的栅栏
CyclicBarrier barrier = new CyclicBarrier(3, () -> {
    System.out.println("所有线程到达栅栏，开始执行任务");
});

for (int i = 0; i < 3; i++) {
    new Thread(() -> {
        try {
            System.out.println(Thread.currentThread().getName() + " 到达栅栏");
            barrier.await();  // 等待其他线程
            System.out.println(Thread.currentThread().getName() + " 继续执行");
        } catch (Exception e) {
            e.printStackTrace();
        }
    }, "Thread-" + i).start();
}

// 输出：
// Thread-0 到达栅栏
// Thread-1 到达栅栏
// Thread-2 到达栅栏
// 所有线程到达栅栏，开始执行任务
// Thread-0 继续执行
// Thread-1 继续执行
// Thread-2 继续执行
```

**实际案例：多线程计算**：
```java
public class ParallelComputer {
    public void compute() {
        int workerCount = 4;
        CyclicBarrier barrier = new CyclicBarrier(workerCount, () -> {
            System.out.println("阶段 1 完成，开始阶段 2");
        });

        for (int i = 0; i < workerCount; i++) {
            new Thread(() -> {
                try {
                    // 阶段 1：数据加载
                    loadData();
                    barrier.await();  // 等待所有线程完成阶段 1

                    // 阶段 2：数据处理
                    processData();
                    barrier.await();  // 等待所有线程完成阶段 2

                    // 阶段 3：结果输出
                    outputResult();
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }).start();
        }
    }
}
```

#### 2.6 ThreadPoolExecutor.Worker

**核心特性**：
- 基于 AQS 实现的独占锁
- 用于线程池中的工作线程管理
- 实现了简单的不可重入锁

**实现简化**：
```java
private final class Worker extends AbstractQueuedSynchronizer implements Runnable {
    final Thread thread;
    Runnable firstTask;

    Worker(Runnable firstTask) {
        setState(-1);  // 初始状态为 -1，禁止中断
        this.firstTask = firstTask;
        this.thread = getThreadFactory().newThread(this);
    }

    // 简单的独占锁实现
    protected boolean tryAcquire(int unused) {
        if (compareAndSetState(0, 1)) {
            setExclusiveOwnerThread(Thread.currentThread());
            return true;
        }
        return false;
    }

    protected boolean tryRelease(int unused) {
        setExclusiveOwnerThread(null);
        setState(0);
        return true;
    }

    public void run() {
        runWorker(this);
    }
}
```

### 3. AQS操作类对比

| 类名 | 模式 | 可重复使用 | 主要用途 | state 含义 |
|------|------|----------|---------|-----------|
| **ReentrantLock** | 独占 | ✅ | 互斥锁 | 锁的持有次数 |
| **ReentrantReadWriteLock** | 独占+共享 | ✅ | 读写锁 | 高16位：读锁次数<br>低16位：写锁次数 |
| **Semaphore** | 共享 | ✅ | 限流、资源池 | 可用许可数 |
| **CountDownLatch** | 共享 | ❌ | 一次性同步 | 剩余计数 |
| **CyclicBarrier** | - | ✅ | 阶段同步 | 基于 ReentrantLock |
| **Worker** | 独占 | ✅ | 线程池管理 | 锁状态 |

### 4. 选择指南

**需要互斥锁**：
- 简单场景：`synchronized`
- 需要高级特性：`ReentrantLock`

**读多写少**：
- `ReentrantReadWriteLock`

**限流/资源池**：
- `Semaphore`

**等待多任务完成**：
- 一次性：`CountDownLatch`
- 可重复：`CyclicBarrier`

### 5. 实际应用案例

#### 5.1 数据库连接池

```java
public class ConnectionPool {
    private final Semaphore semaphore;
    private final List<Connection> connections;

    public ConnectionPool(int poolSize) {
        this.semaphore = new Semaphore(poolSize);
        this.connections = new ArrayList<>(poolSize);
        // 初始化连接
    }

    public Connection getConnection() throws InterruptedException {
        semaphore.acquire();
        return connections.remove(0);
    }

    public void releaseConnection(Connection conn) {
        connections.add(conn);
        semaphore.release();
    }
}
```

#### 5.2 缓存系统

```java
public class Cache<K, V> {
    private final Map<K, V> cache = new HashMap<>();
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

    public V get(K key) {
        lock.readLock().lock();
        try {
            return cache.get(key);
        } finally {
            lock.readLock().unlock();
        }
    }

    public void put(K key, V value) {
        lock.writeLock().lock();
        try {
            cache.put(key, value);
        } finally {
            lock.writeLock().unlock();
        }
    }
}
```

### 6. 总结

基于 AQS 的操作类包括：

1. **ReentrantLock**：可重入锁，独占模式，功能强大
2. **ReentrantReadWriteLock**：读写锁，支持读共享写独占
3. **Semaphore**：信号量，限流和资源池管理
4. **CountDownLatch**：倒计数器，一次性同步工具
5. **CyclicBarrier**：循环栅栏，可重复的阶段同步
6. **ThreadPoolExecutor.Worker**：线程池工作线程管理

**面试要点**：
- 列举常见的 AQS 操作类及其用途
- 说明独占模式（ReentrantLock）和共享模式（Semaphore）的区别
- 理解 CountDownLatch 和 CyclicBarrier 的差异（一次性 vs 可重复）
- 能够根据场景选择合适的并发工具

**记忆口诀**：
- Lock 独占保互斥，ReadWrite 读写分
- Semaphore 限流量，Latch 倒数一次完
- Barrier 循环可复用，Worker 线程池来管
