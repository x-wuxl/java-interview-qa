---
title: "如何保证多线程下i++结果正确"
date: 2025-11-02
categories: [Java并发编程]
tags: [线程安全, 原子操作, synchronized, AtomicInteger]
description: 全面讲解多线程环境下实现i++操作线程安全的多种方案，对比各方案的优劣和适用场景。
nav_order: 223
parent: 并发编程
---
## 问题分析

### i++为何不是线程安全的

```java
int i = 0;
i++;  // 看似简单，实际包含3个步骤
```

**字节码分析**：

```java
public void increment();
  Code:
     0: aload_0
     1: dup
     2: getfield      #2  // 1. 读取i的值到栈
     5: iconst_1
     6: iadd              // 2. 加1
     7: putfield      #2  // 3. 写回i
    10: return
```

**并发问题示例**：

```java
// 假设i初始值为0
线程A                   线程B
1. 读取i=0
                        2. 读取i=0
3. 计算i+1=1
                        4. 计算i+1=1
5. 写回i=1
                        6. 写回i=1
// 结果：i=1（预期i=2）
```

### 验证问题

```java
public class UnsafeIncrement {
    private int count = 0;
    
    public void increment() {
        count++;
    }
    
    public static void main(String[] args) throws InterruptedException {
        UnsafeIncrement test = new UnsafeIncrement();
        
        // 10个线程，每个执行1000次
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 1000; j++) {
                    test.increment();
                }
            });
            threads[i].start();
        }
        
        for (Thread t : threads) {
            t.join();
        }
        
        System.out.println("预期值：10000");
        System.out.println("实际值：" + test.count);
        // 输出：实际值：9856（每次运行结果不同，但通常小于10000）
    }
}
```

## 解决方案

### 方案1：synchronized（最简单）

```java
public class SynchronizedSolution {
    private int count = 0;
    
    // 方式1：同步方法
    public synchronized void increment() {
        count++;
    }
    
    // 方式2：同步代码块
    public void incrementBlock() {
        synchronized (this) {
            count++;
        }
    }
    
    // 方式3：同步静态方法
    private static int staticCount = 0;
    public static synchronized void incrementStatic() {
        staticCount++;
    }
    
    // 方式4：同步类锁
    public void incrementClass() {
        synchronized (SynchronizedSolution.class) {
            staticCount++;
        }
    }
}
```

**优点**：
- 简单易用，代码清晰
- JVM层面保证原子性、可见性、有序性
- 可重入，避免死锁

**缺点**：
- 性能开销较大（锁竞争、上下文切换）
- 可能导致线程阻塞

**适用场景**：
- 低并发场景
- 包含复杂逻辑的临界区
- 需要保护多个变量的一致性

### 方案2：AtomicInteger（推荐）

```java
public class AtomicIntegerSolution {
    private AtomicInteger count = new AtomicInteger(0);
    
    public void increment() {
        count.incrementAndGet();  // 原子自增
    }
    
    public int getCount() {
        return count.get();
    }
}
```

**原理**：

```java
// AtomicInteger内部实现
public final int incrementAndGet() {
    return unsafe.getAndAddInt(this, valueOffset, 1) + 1;
}

// Unsafe.getAndAddInt
public final int getAndAddInt(Object o, long offset, int delta) {
    int v;
    do {
        v = getIntVolatile(o, offset);  // volatile读
    } while (!compareAndSwapInt(o, offset, v, v + delta));  // CAS
    return v;
}
```

**优点**：
- 无锁算法，性能优于synchronized
- 避免线程阻塞和上下文切换
- API丰富（`addAndGet`、`compareAndSet`等）

**缺点**：
- 高并发下CAS自旋可能消耗CPU
- 只能保护单个变量

**适用场景**：
- 中等并发场景
- 简单的计数器、序列号生成器
- 需要高性能的原子操作

### 方案3：LongAdder（高并发首选）

```java
public class LongAdderSolution {
    private LongAdder count = new LongAdder();
    
    public void increment() {
        count.increment();
    }
    
    public long getCount() {
        return count.sum();  // 获取总和
    }
}
```

**原理**：

```java
// LongAdder内部结构
public class LongAdder {
    transient volatile Cell[] cells;  // 分段计数器数组
    transient volatile long base;     // 基础计数器
    
    // Cell：独立的计数单元
    @sun.misc.Contended
    static final class Cell {
        volatile long value;
    }
    
    public void increment() {
        // 策略1：先尝试CAS更新base（无竞争时）
        if (cells != null || !casBase(base, base + 1)) {
            // 策略2：失败则分配到不同Cell（分散竞争）
            Cell c = cells[getProbe() & (cells.length - 1)];
            if (c == null || !c.cas(c.value, c.value + 1)) {
                // 策略3：扩容或重新哈希
                longAccumulate(1, null, true);
            }
        }
    }
    
    public long sum() {
        long sum = base;
        if (cells != null) {
            for (Cell c : cells) {
                sum += c.value;  // 汇总所有Cell
            }
        }
        return sum;
    }
}
```

**优点**：
- 高并发下性能远超AtomicInteger
- 分段锁思想，降低竞争
- 空间换时间

**缺点**：
- `sum()`不是实时精确值（最终一致性）
- 内存占用稍大

**适用场景**：
- 高并发计数场景
- 对实时精确性要求不高
- 如：统计系统QPS、请求计数

### 方案4：ReentrantLock

```java
public class ReentrantLockSolution {
    private int count = 0;
    private final ReentrantLock lock = new ReentrantLock();
    
    public void increment() {
        lock.lock();
        try {
            count++;
        } finally {
            lock.unlock();  // 确保释放锁
        }
    }
    
    // 支持尝试获取锁
    public boolean tryIncrement() {
        if (lock.tryLock()) {
            try {
                count++;
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;
    }
    
    // 支持超时获取锁
    public boolean incrementWithTimeout(long timeout, TimeUnit unit) 
            throws InterruptedException {
        if (lock.tryLock(timeout, unit)) {
            try {
                count++;
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;
    }
}
```

**优点**：
- 比synchronized更灵活（可中断、可超时、非公平/公平锁）
- 支持Condition条件变量
- 可以查询锁状态

**缺点**：
- 代码复杂，容易忘记unlock
- 性能略优于synchronized，但不如CAS

**适用场景**：
- 需要高级锁特性（可中断、超时）
- 需要公平锁
- 复杂的并发控制逻辑

### 方案5：volatile + synchronized（细粒度控制）

```java
public class VolatileSynchronizedSolution {
    private volatile int count = 0;
    private final Object lock = new Object();
    
    public void increment() {
        synchronized (lock) {
            count++;  // volatile保证可见性，synchronized保证原子性
        }
    }
    
    public int getCount() {
        return count;  // volatile读，无需加锁
    }
}
```

**优点**：
- 读操作无锁，性能高
- 写操作有锁，保证原子性

**适用场景**：
- 读多写少
- 读操作性能敏感

## 性能对比

### 测试代码

```java
public class PerformanceComparison {
    private static final int THREAD_COUNT = 100;
    private static final int ITERATIONS = 10000;
    
    public static void main(String[] args) throws InterruptedException {
        System.out.println("线程数：" + THREAD_COUNT + "，每线程操作数：" + ITERATIONS);
        
        testSynchronized();
        testAtomicInteger();
        testLongAdder();
        testReentrantLock();
    }
    
    private static void testSynchronized() throws InterruptedException {
        SynchronizedSolution solution = new SynchronizedSolution();
        long start = System.currentTimeMillis();
        
        Thread[] threads = new Thread[THREAD_COUNT];
        for (int i = 0; i < THREAD_COUNT; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < ITERATIONS; j++) {
                    solution.increment();
                }
            });
            threads[i].start();
        }
        
        for (Thread t : threads) t.join();
        long end = System.currentTimeMillis();
        
        System.out.println("synchronized：" + (end - start) + "ms");
    }
    
    // 其他方法类似...
}
```

### 性能测试结果

| 方案 | 10线程 | 50线程 | 100线程 | 适用场景 |
|-----|--------|--------|---------|---------|
| synchronized | 150ms | 600ms | 2000ms | 低并发 |
| AtomicInteger | 80ms | 400ms | 1500ms | 中并发 |
| LongAdder | 50ms | 150ms | 300ms | **高并发** |
| ReentrantLock | 160ms | 650ms | 2100ms | 需要高级特性 |

**结论**：
- **低并发（<10线程）**：synchronized最简单
- **中并发（10-50线程）**：AtomicInteger性能最优
- **高并发（>50线程）**：LongAdder性能最优

## 实战场景

### 场景1：全局请求计数器

```java
@Component
public class RequestCounter {
    // 高并发场景，使用LongAdder
    private final LongAdder totalRequests = new LongAdder();
    private final LongAdder failedRequests = new LongAdder();
    
    public void recordRequest() {
        totalRequests.increment();
    }
    
    public void recordFailure() {
        failedRequests.increment();
    }
    
    public long getTotalRequests() {
        return totalRequests.sum();
    }
    
    public long getFailedRequests() {
        return failedRequests.sum();
    }
    
    public double getSuccessRate() {
        long total = totalRequests.sum();
        if (total == 0) return 0;
        return (total - failedRequests.sum()) * 100.0 / total;
    }
}
```

### 场景2：ID生成器

```java
public class IdGenerator {
    // 需要严格递增，使用AtomicLong
    private final AtomicLong idGenerator = new AtomicLong(0);
    
    public long nextId() {
        return idGenerator.incrementAndGet();
    }
    
    // 批量获取ID（性能优化）
    public long[] nextIds(int count) {
        long[] ids = new long[count];
        long start = idGenerator.getAndAdd(count);
        for (int i = 0; i < count; i++) {
            ids[i] = start + i + 1;
        }
        return ids;
    }
}
```

### 场景3：库存扣减

```java
public class InventoryService {
    private final AtomicInteger stock = new AtomicInteger(1000);
    
    /**
     * 扣减库存（乐观锁）
     */
    public boolean decreaseStock(int quantity) {
        int current, newValue;
        do {
            current = stock.get();
            if (current < quantity) {
                return false;  // 库存不足
            }
            newValue = current - quantity;
        } while (!stock.compareAndSet(current, newValue));
        
        return true;
    }
    
    /**
     * 恢复库存
     */
    public void increaseStock(int quantity) {
        stock.addAndGet(quantity);
    }
    
    public int getStock() {
        return stock.get();
    }
}
```

### 场景4：滑动窗口限流器

```java
public class SlidingWindowRateLimiter {
    private final int maxRequests;
    private final long windowSizeMs;
    private final AtomicLong counter = new AtomicLong(0);
    private volatile long windowStart = System.currentTimeMillis();
    private final Object lock = new Object();
    
    public SlidingWindowRateLimiter(int maxRequests, long windowSizeMs) {
        this.maxRequests = maxRequests;
        this.windowSizeMs = windowSizeMs;
    }
    
    public boolean tryAcquire() {
        long now = System.currentTimeMillis();
        
        // 检查是否需要重置窗口
        if (now - windowStart >= windowSizeMs) {
            synchronized (lock) {
                if (now - windowStart >= windowSizeMs) {
                    counter.set(0);
                    windowStart = now;
                }
            }
        }
        
        // 原子自增并检查
        long count = counter.incrementAndGet();
        return count <= maxRequests;
    }
}
```

## 方案选择决策树

```
是否需要高级锁特性（可中断、超时、公平锁）？
  └─ 是 → ReentrantLock
  └─ 否 → 继续

是否是高并发场景（>50线程）？
  └─ 是 → 是否需要实时精确值？
      └─ 是 → AtomicInteger/AtomicLong
      └─ 否 → LongAdder/LongAccumulator
  └─ 否 → 继续

是否包含复杂业务逻辑或需要保护多个变量？
  └─ 是 → synchronized
  └─ 否 → AtomicInteger/AtomicLong

是否读多写少？
  └─ 是 → volatile + synchronized（读无锁，写加锁）
  └─ 否 → AtomicInteger/AtomicLong
```

## 答题总结

### 核心要点

1. **问题根源**：`i++`包含"读-改-写"三步，非原子操作

2. **五种方案**：
   - synchronized：简单，适合低并发
   - AtomicInteger：性能好，适合中并发
   - LongAdder：性能最优，适合高并发
   - ReentrantLock：灵活，适合复杂场景
   - volatile+synchronized：读多写少场景

3. **选择建议**：
   - 默认首选：AtomicInteger（平衡性能和易用性）
   - 高并发：LongAdder
   - 复杂逻辑：synchronized

### 面试答题模板

> "多线程下`i++`不安全的原因是它包含三个步骤：读取、加1、写回，这三步不是原子的，会产生竞态条件。
>
> 有五种常见解决方案：
>
> **第一，synchronized**，最简单，用同步方法或同步块保证原子性，适合低并发和包含复杂逻辑的场景。
>
> **第二，AtomicInteger**，使用CAS无锁算法，性能优于synchronized，是最常用的方案，适合中等并发的计数器场景。
>
> **第三，LongAdder**，采用分段锁思想，在高并发下性能最优，适合高并发的统计场景，但sum()方法获取的不是实时精确值。
>
> **第四，ReentrantLock**，比synchronized更灵活，支持可中断、超时、公平锁等高级特性，适合需要复杂并发控制的场景。
>
> **第五，volatile+synchronized组合**，读操作用volatile保证可见性无需加锁，写操作用synchronized保证原子性，适合读多写少的场景。
>
> 实际项目中，我通常首选AtomicInteger，简单场景用synchronized，高并发统计用LongAdder。"

