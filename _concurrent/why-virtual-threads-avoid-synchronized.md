---
title: "为什么虚拟线程不能用synchronized？"
date: 2025-11-02
description: "深入分析虚拟线程与synchronized的pinning问题、底层原因及替代方案"
author: "wuxl"
categories: [并发编程]
tags: [虚拟线程, synchronized, Pinning, ReentrantLock, JDK21]
nav_order: 271
parent: 并发编程
---
## 问题

为什么虚拟线程不能用synchronized？

## 答案

### 核心问题

虚拟线程**不是不能用**synchronized，而是**不应该用**。原因是synchronized会导致**pinning**（固定）问题：当虚拟线程在synchronized块中执行阻塞操作时，**无法卸载（unmount）**，会一直占用平台线程（carrier thread），直接**抵消虚拟线程的并发优势**。

### Pinning问题详解

#### 1. 正常卸载流程

```java
// 正常情况：虚拟线程遇阻塞自动卸载
Thread.startVirtualThread(() -> {
    System.out.println("Step 1 on " + Thread.currentThread());
    
    Thread.sleep(1000);  // 阻塞操作
    // ↑ 此时虚拟线程自动unmount，释放平台线程
    // 平台线程可执行其他虚拟线程
    
    System.out.println("Step 2 on " + Thread.currentThread());
    // ↑ 恢复后可能在不同的平台线程上执行
});
```

**输出示例**：
```
Step 1 on VirtualThread[#21]/CarrierThread[#1]
Step 2 on VirtualThread[#21]/CarrierThread[#3]  ← 平台线程可能变化
```

#### 2. Pinning问题案例

```java
Object lock = new Object();

// ❌ 错误：synchronized导致pinning
Thread.startVirtualThread(() -> {
    synchronized (lock) {
        System.out.println("Enter synchronized on " + Thread.currentThread());
        
        Thread.sleep(5000);  // 阻塞5秒
        // ⚠️ 虚拟线程无法卸载，平台线程被占用5秒！
        
        System.out.println("Exit synchronized on " + Thread.currentThread());
    }
});
```

**输出示例**：
```
Enter synchronized on VirtualThread[#21]/CarrierThread[#1]
（等待5秒，CarrierThread[#1]一直被占用）
Exit synchronized on VirtualThread[#21]/CarrierThread[#1]  ← 始终是同一个平台线程
```

**问题影响**：
```java
// 场景：100万个虚拟线程，每个都在synchronized中阻塞1秒
Object lock = new Object();
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    for (int i = 0; i < 1_000_000; i++) {
        executor.submit(() -> {
            synchronized (lock) {
                Thread.sleep(1000);  // pinning!
                // 平台线程被占用，其他999,999个虚拟线程无法执行
            }
        });
    }
}
// 结果：退化为平台线程模型，只有CPU核心数个任务并发执行
```

### 底层原因分析

#### 1. synchronized的JVM实现

```java
// 字节码层面
monitorenter   // 进入监视器
  // 临界区代码
monitorexit    // 退出监视器
```

**关键点**：
- synchronized的monitor（监视器）实现在**JVM C++层**
- 进入synchronized时，会**关联当前平台线程**（owner字段指向carrier thread）
- JVM无法在不释放monitor的情况下切换线程

**源码简化**：
```cpp
// HotSpot VM源码（简化）
class ObjectMonitor {
    Thread* _owner;  // 指向持有锁的平台线程
    
    void enter() {
        _owner = Thread::current();  // 记录carrier thread
        // 虚拟线程信息丢失，无法unmount
    }
}
```

#### 2. 为什么无法unmount

```
传统平台线程模型：
Thread-1 → Monitor → 持有锁 → 执行完成 → 释放锁

虚拟线程模型（正常情况）：
VThread-1 mount→ CarrierThread-1 → 遇到阻塞 → unmount → 让出CarrierThread
                                                    ↓
VThread-2 mount→ CarrierThread-1 → 继续执行

虚拟线程+synchronized（pinning）：
VThread-1 mount→ CarrierThread-1 → synchronized (lock)
                                    ↓
                                  Monitor记录CarrierThread-1为owner
                                    ↓
                                  遇到阻塞（如sleep）
                                    ↓
                                  ❌ 无法unmount！
                                  Monitor的owner必须是当前线程才能操作
                                  切换到其他CarrierThread会导致owner不匹配
                                    ↓
                                  CarrierThread-1被pinning，一直等待到锁释放
```

#### 3. JFR监控pinning事件

```bash
# 启动JFR监控
jcmd <pid> JFR.start settings=profile

# 触发pinning
java -XX:+UnlockDiagnosticVMOptions \
     -XX:+ShowHiddenFrames \
     YourApp

# 导出JFR文件
jcmd <pid> JFR.dump filename=pinning.jfr
```

**JFR事件**：
```java
jdk.VirtualThreadPinned {
    startTime = 2025-11-02 10:30:15
    duration = 5000 ms        // pinning持续时间
    carrierThread = "CarrierThread-1"
    stackTrace = [
        java.lang.Object.wait()
        YourClass.synchronized块()
    ]
}
```

### 替代方案

#### 1. 使用ReentrantLock

```java
import java.util.concurrent.locks.ReentrantLock;

ReentrantLock lock = new ReentrantLock();

// ✅ 正确：ReentrantLock支持虚拟线程unmount
Thread.startVirtualThread(() -> {
    lock.lock();
    try {
        System.out.println("Acquired lock");
        
        Thread.sleep(1000);  // 正常卸载！
        // 虚拟线程unmount，平台线程可执行其他任务
        
        System.out.println("After sleep");
    } finally {
        lock.unlock();
    }
});
```

**原理**：ReentrantLock基于AQS（AbstractQueuedSynchronizer），使用**LockSupport.park()**实现阻塞，该方法已被JDK改造，支持虚拟线程unmount。

#### 2. 性能对比测试

```java
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.Executors;

public class SynchronizedVsLockBenchmark {
    
    // 测试1：synchronized + 虚拟线程
    public static void testSynchronized() {
        Object lock = new Object();
        Instant start = Instant.now();
        
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 10000; i++) {
                executor.submit(() -> {
                    synchronized (lock) {
                        Thread.sleep(Duration.ofMillis(10));
                    }
                });
            }
        }
        
        Duration elapsed = Duration.between(start, Instant.now());
        System.out.println("Synchronized: " + elapsed.toMillis() + "ms");
        // 输出：~100,000ms（串行执行，pinning）
    }
    
    // 测试2：ReentrantLock + 虚拟线程
    public static void testReentrantLock() {
        ReentrantLock lock = new ReentrantLock();
        Instant start = Instant.now();
        
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 10000; i++) {
                executor.submit(() -> {
                    lock.lock();
                    try {
                        Thread.sleep(Duration.ofMillis(10));
                    } finally {
                        lock.unlock();
                    }
                });
            }
        }
        
        Duration elapsed = Duration.between(start, Instant.now());
        System.out.println("ReentrantLock: " + elapsed.toMillis() + "ms");
        // 输出：~100,000ms（仍然串行，因为同一把锁）
    }
    
    // 测试3：无锁竞争场景
    public static void testNoContention() {
        Instant start = Instant.now();
        
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 10000; i++) {
                executor.submit(() -> {
                    // 每个任务独立的锁，无竞争
                    Object localLock = new Object();
                    synchronized (localLock) {
                        Thread.sleep(Duration.ofMillis(10));
                    }
                });
            }
        }
        
        Duration elapsed = Duration.between(start, Instant.now());
        System.out.println("No contention (synchronized): " + elapsed.toMillis() + "ms");
        // 输出：~20ms（pinning但无竞争，多个carrier thread并发）
    }
    
    // 测试4：ReentrantLock无竞争
    public static void testReentrantLockNoContention() {
        Instant start = Instant.now();
        
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            for (int i = 0; i < 10000; i++) {
                executor.submit(() -> {
                    ReentrantLock localLock = new ReentrantLock();
                    localLock.lock();
                    try {
                        Thread.sleep(Duration.ofMillis(10));
                    } finally {
                        localLock.unlock();
                    }
                });
            }
        }
        
        Duration elapsed = Duration.between(start, Instant.now());
        System.out.println("No contention (ReentrantLock): " + elapsed.toMillis() + "ms");
        // 输出：~10ms（正常unmount，充分利用虚拟线程）
    }
}
```

**测试结果分析**：

| 场景 | 锁类型 | 耗时 | 原因 |
|------|--------|------|------|
| 有锁竞争 | synchronized | ~100s | pinning + 串行 |
| 有锁竞争 | ReentrantLock | ~100s | 串行执行（正常） |
| 无锁竞争 | synchronized | ~20ms | pinning但能并发 |
| 无锁竞争 | ReentrantLock | ~10ms | 正常unmount，最优 |

#### 3. 其他替代方案

```java
// 1. StampedLock（读写锁）
StampedLock lock = new StampedLock();
long stamp = lock.writeLock();
try {
    // 临界区
    Thread.sleep(1000);  // 支持unmount
} finally {
    lock.unlockWrite(stamp);
}

// 2. ReadWriteLock
ReadWriteLock rwLock = new ReentrantReadWriteLock();
rwLock.readLock().lock();
try {
    // 读操作
} finally {
    rwLock.readLock().unlock();
}

// 3. 无锁并发（推荐）
AtomicInteger counter = new AtomicInteger();
counter.incrementAndGet();  // CAS操作，无需加锁
```

### 特殊情况：synchronized也可用

#### 1. 临界区无阻塞

```java
// ✅ 可接受：临界区不阻塞，pinning时间短
synchronized (lock) {
    counter++;  // 纯内存操作，微秒级
    map.put(key, value);
}
// pinning时间极短，影响可忽略
```

#### 2. 单线程场景

```java
// ✅ 可接受：无并发，不影响其他虚拟线程
Thread.startVirtualThread(() -> {
    synchronized (this) {  // 锁自身，无竞争
        Thread.sleep(1000);
    }
});
```

### 代码迁移示例

**迁移前**：
```java
public class OrderService {
    private final Object lock = new Object();
    
    public void processOrder(Order order) {
        synchronized (lock) {
            // 1. 查询数据库（阻塞IO）
            Order existing = orderRepository.findById(order.getId());
            
            // 2. 调用外部API（阻塞IO）
            PaymentResult result = paymentClient.pay(order);
            
            // 3. 更新数据库
            orderRepository.save(order);
        }
        // ⚠️ 问题：pinning导致虚拟线程无法卸载
    }
}
```

**迁移后**：
```java
public class OrderService {
    private final ReentrantLock lock = new ReentrantLock();
    
    public void processOrder(Order order) {
        lock.lock();
        try {
            // 1. 查询数据库（阻塞时自动unmount）
            Order existing = orderRepository.findById(order.getId());
            
            // 2. 调用外部API（阻塞时自动unmount）
            PaymentResult result = paymentClient.pay(order);
            
            // 3. 更新数据库
            orderRepository.save(order);
        } finally {
            lock.unlock();
        }
        // ✅ 阻塞时虚拟线程正常卸载，平台线程可执行其他任务
    }
}
```

### 诊断工具

#### 1. JVM参数

```bash
# 1. 打印pinning警告
java -Djdk.tracePinnedThreads=full YourApp

# 输出示例：
# VirtualThread[#23] pinned at
#   java.base/java.lang.Object.wait(Native Method)
#   YourClass.lambda$main$0(YourClass.java:15)

# 2. 限制pinning时间（实验性）
java -Djdk.virtualThreadScheduler.maxPoolSize=256 \
     -Djdk.virtualThreadScheduler.parallelism=16 \
     YourApp
```

#### 2. 代码检测

```java
// 自定义检测工具
public class PinningDetector {
    public static void detectPinning(Runnable task) {
        Thread vThread = Thread.ofVirtual().start(() -> {
            long start = System.currentTimeMillis();
            Thread carrierBefore = getCarrierThread();
            
            task.run();
            
            Thread carrierAfter = getCarrierThread();
            long duration = System.currentTimeMillis() - start;
            
            if (carrierBefore == carrierAfter && duration > 100) {
                System.err.println("⚠️ Possible pinning detected: " + duration + "ms");
            }
        });
        vThread.join();
    }
    
    private static Thread getCarrierThread() {
        // 通过反射获取carrier thread（仅用于调试）
        try {
            var field = Thread.class.getDeclaredField("carrierThread");
            field.setAccessible(true);
            return (Thread) field.get(Thread.currentThread());
        } catch (Exception e) {
            return null;
        }
    }
}
```

### 面试答题要点

1. **并非不能用**：虚拟线程可以用synchronized，但会导致pinning（固定到平台线程）
2. **pinning问题**：synchronized块中遇阻塞时，虚拟线程无法unmount，平台线程被占用，降低并发能力
3. **底层原因**：synchronized的monitor实现记录平台线程为owner，切换会导致owner不匹配
4. **替代方案**：使用ReentrantLock等基于AQS的锁，支持虚拟线程正常卸载
5. **可用场景**：临界区无阻塞或阻塞时间极短时，synchronized仍可使用
6. **诊断方法**：使用`-Djdk.tracePinnedThreads=full`参数或JFR监控`jdk.VirtualThreadPinned`事件

**高级回答**：pinning的本质是synchronized的monitor与平台线程强绑定，而虚拟线程的unmount需要解除这种绑定。ReentrantLock基于LockSupport.park()实现，该方法已被JDK改造为虚拟线程友好，会将阻塞信息存储在虚拟线程对象中而非平台线程。因此在虚拟线程中应优先使用ReentrantLock，只在临界区极短且无阻塞时才考虑synchronized。

