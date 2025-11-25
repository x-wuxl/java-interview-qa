---
layout: default
title: "LongAdder和AtomicLong的区别？"
parent: 并发编程
nav_order: 251
description: "深入解析LongAdder与AtomicLong的性能差异、实现原理及使用场景"
author: "wuxl"
date: 2025-11-02
---
## 问题

LongAdder和AtomicLong的区别？

## 答案

### 核心概念

两者都是JUC包提供的线程安全的计数器，但设计思路不同：

- **AtomicLong**：基于CAS（Compare-And-Swap）直接操作单一变量
- **LongAdder**：采用**分段累加**思想，内部维护多个Cell，降低CAS竞争

### 性能对比

| 维度 | AtomicLong | LongAdder |
|------|-----------|-----------|
| **低并发场景** | ✅ 性能更好（无额外开销） | ❌ 有Cell数组开销 |
| **高并发场景** | ❌ CAS频繁失败，性能下降 | ✅ 分散热点，性能优异 |
| **内存占用** | 小（8字节） | 大（Cell数组+填充） |
| **适用场景** | 低并发、需要精确实时值 | 高并发计数、统计指标 |

**性能差异原因**：
- AtomicLong在高并发时，多个线程同时CAS操作同一个value，导致大量自旋重试
- LongAdder将value分散到多个Cell中，每个线程操作不同Cell，减少竞争

### 实现原理

**AtomicLong核心实现**：
```java
public class AtomicLong {
    private volatile long value;  // 所有线程竞争这一个变量

    public final long incrementAndGet() {
        return unsafe.getAndAddLong(this, valueOffset, 1L) + 1L;
    }

    // CAS自旋
    public final long getAndAddLong(Object o, long offset, long delta) {
        long v;
        do {
            v = getLongVolatile(o, offset);
        } while (!compareAndSwapLong(o, offset, v, v + delta));  // 失败则重试
        return v;
    }
}
```

**LongAdder核心实现**：
```java
public class LongAdder extends Striped64 {
    // Striped64维护：
    // - transient volatile Cell[] cells;  // Cell数组，分散热点
    // - transient volatile long base;     // 无竞争时使用

    public void add(long x) {
        Cell[] as; long b, v; int m; Cell a;
        // 1. 优先CAS更新base（无竞争时）
        if ((as = cells) != null || !casBase(b = base, b + x)) {
            // 2. base更新失败，说明有竞争，使用Cell数组
            int h = threadLocalRandomProbe();  // 线程hash值
            if (as != null && (m = as.length - 1) >= 0 &&
                (a = as[h & m]) != null) {
                // 3. 定位到线程对应的Cell，CAS更新
                if (!a.cas(v = a.value, v + x))
                    longAccumulate(x, null, true);  // 失败则扩容或rehash
            } else {
                longAccumulate(x, null, true);  // 初始化Cell数组
            }
        }
    }

    public long sum() {
        Cell[] as = cells; Cell a;
        long sum = base;
        if (as != null) {
            for (int i = 0; i < as.length; ++i) {
                if ((a = as[i]) != null)
                    sum += a.value;  // 累加所有Cell的值
            }
        }
        return sum;
    }
}

// Cell使用@Contended注解防止伪共享
@sun.misc.Contended
static final class Cell {
    volatile long value;
}
```

### 关键设计优化

**1. 分段累加策略**：
- 无竞争：直接更新base（避免Cell数组开销）
- 有竞争：根据线程哈希值分配到不同Cell，降低冲突概率

**2. 伪共享优化**：
- Cell使用`@Contended`注解，自动填充缓存行（64字节），避免多个Cell在同一缓存行导致的缓存失效

**3. 动态扩容**：
- Cell数组大小为2的幂次，最大为CPU核心数
- CAS失败次数过多时触发扩容或rehash

### 使用场景

**AtomicLong适用**：
- 并发度较低（< 10线程）
- 需要精确的实时值（如ID生成器）
- 对内存敏感

**LongAdder适用**：
- 高并发场景（> 50线程）
- 只需要最终结果，不要求实时精确（如访问统计、点赞数）
- 写多读少

### 代码示例

```java
// 性能对比测试
public class PerformanceTest {
    public static void main(String[] args) throws InterruptedException {
        int threadCount = 100;
        int iterations = 100_000;

        // AtomicLong测试
        AtomicLong atomicLong = new AtomicLong();
        long atomicStart = System.currentTimeMillis();
        testCounter(threadCount, iterations, () -> atomicLong.incrementAndGet());
        long atomicTime = System.currentTimeMillis() - atomicStart;

        // LongAdder测试
        LongAdder longAdder = new LongAdder();
        long adderStart = System.currentTimeMillis();
        testCounter(threadCount, iterations, () -> longAdder.increment());
        long adderTime = System.currentTimeMillis() - adderStart;

        System.out.println("AtomicLong耗时: " + atomicTime + "ms");
        System.out.println("LongAdder耗时: " + adderTime + "ms");
        System.out.println("性能提升: " + (atomicTime * 100.0 / adderTime - 100) + "%");
    }

    static void testCounter(int threadCount, int iterations, Runnable task)
            throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(threadCount);
        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                for (int j = 0; j < iterations; j++) {
                    task.run();
                }
                latch.countDown();
            }).start();
        }
        latch.await();
    }
}

// 实际应用示例：访问统计
public class AccessCounter {
    private final LongAdder totalAccess = new LongAdder();
    private final LongAdder todayAccess = new LongAdder();

    public void recordAccess() {
        totalAccess.increment();
        todayAccess.increment();
    }

    public long getTotalAccess() {
        return totalAccess.sum();  // sum()会遍历所有Cell累加
    }

    public void resetToday() {
        todayAccess.reset();  // 重置base和所有Cell
    }
}
```

### 注意事项

1. **LongAdder的sum()不是原子操作**：
   - sum()过程中，其他线程仍可能在修改值
   - 适合统计场景，不适合需要强一致性的场景

2. **内存占用**：
   - LongAdder的Cell数组最大为CPU核心数，64核机器约占用4KB
   - 一般应用可忽略此开销

3. **选择建议**：
   - 需要精确实时值 → AtomicLong
   - 高并发纯计数 → LongAdder
   - 需要compareAndSet等CAS操作 → AtomicLong

### 面试答题要点

1. **核心差异**：AtomicLong单点CAS，LongAdder分段累加降低竞争
2. **性能原因**：高并发时LongAdder通过分散热点避免CAS频繁失败
3. **内部结构**：LongAdder维护base + Cell数组，使用@Contended防止伪共享
4. **适用场景**：LongAdder适合高并发统计（如Metrics），AtomicLong适合低并发精确计数
5. **JDK8引入LongAdder就是为了优化AtomicLong在高并发下的性能瓶颈**
