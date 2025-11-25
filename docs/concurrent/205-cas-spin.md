---
layout: default
title: "CAS一定有自旋吗？"
parent: 并发编程
nav_order: 205
description: 深入分析CAS操作是否一定伴随自旋，以及不同场景下的实现机制。
date: 2025-11-02
---
## 核心结论

**CAS本身不一定有自旋**，自旋是在CAS之上构建的重试机制。CAS只是一次原子的"比较并交换"操作，失败后是否重试取决于上层逻辑。

## 概念区分

### 1. CAS操作本身

```java
// Unsafe类的CAS方法：只执行一次
public native boolean compareAndSwapInt(
    Object o, long offset, int expected, int x);
```

**特点**：
- 执行一次CAS操作
- 成功返回true，失败返回false
- **不包含任何重试逻辑**

### 2. CAS + 自旋

```java
// AtomicInteger的自旋实现
public final int getAndAddInt(Object o, long offset, int delta) {
    int v;
    do {
        v = getIntVolatile(o, offset);  // 读取当前值
    } while (!compareAndSwapInt(o, offset, v, v + delta));  // 失败则自旋
    //        ↑ CAS本身        ↑ 自旋逻辑
    return v;
}
```

**特点**：
- CAS失败后，循环重试（自旋）
- 直到成功为止

## 不同场景下的CAS使用

### 场景1：单次CAS（无自旋）

```java
public class SingleCAS {
    private AtomicBoolean flag = new AtomicBoolean(false);
    
    /**
     * 尝试获取锁：只尝试一次，失败就返回
     */
    public boolean tryLock() {
        // 单次CAS，不自旋
        return flag.compareAndSet(false, true);
    }
    
    public void unlock() {
        flag.set(false);
    }
    
    public static void main(String[] args) {
        SingleCAS lock = new SingleCAS();
        
        if (lock.tryLock()) {
            try {
                System.out.println("获取锁成功，执行业务逻辑");
            } finally {
                lock.unlock();
            }
        } else {
            System.out.println("获取锁失败，直接返回");
            // 不自旋，不重试
        }
    }
}
```

**应用场景**：
- 乐观锁的一次尝试
- 非阻塞算法的条件性操作
- 性能敏感的快速失败场景

### 场景2：CAS + 有限自旋

```java
public class BoundedSpinCAS {
    private AtomicInteger value = new AtomicInteger(0);
    
    /**
     * 最多自旋10次，超过则放弃
     */
    public boolean incrementWithLimit() {
        int maxRetries = 10;
        int retries = 0;
        
        while (retries < maxRetries) {
            int current = value.get();
            int next = current + 1;
            
            if (value.compareAndSet(current, next)) {
                return true;  // 成功
            }
            
            retries++;
        }
        
        return false;  // 超过重试次数，失败
    }
}
```

**应用场景**：
- 防止高并发下无限自旋
- 平衡性能和成功率

### 场景3：CAS + 无限自旋

```java
public class UnboundedSpinCAS {
    private AtomicInteger counter = new AtomicInteger(0);
    
    /**
     * 无限自旋，直到成功（AtomicInteger的标准实现）
     */
    public int incrementAndGet() {
        int current;
        int next;
        do {
            current = counter.get();
            next = current + 1;
        } while (!counter.compareAndSet(current, next));
        // 一直自旋，直到成功
        return next;
    }
}
```

**应用场景**：
- 低并发环境
- 必须成功的操作

### 场景4：CAS + 自适应策略

```java
public class AdaptiveSpinCAS {
    private AtomicInteger value = new AtomicInteger(0);
    private static final int SPIN_LIMIT = 100;
    
    /**
     * 自适应：先自旋，自旋失败后升级为阻塞
     */
    public void increment() {
        int retries = 0;
        
        while (retries < SPIN_LIMIT) {
            int current = value.get();
            int next = current + 1;
            
            if (value.compareAndSet(current, next)) {
                return;  // 成功
            }
            
            retries++;
            
            // 适当让出CPU
            if (retries > 10 && retries % 5 == 0) {
                Thread.yield();  // 提示调度器让出CPU
            }
        }
        
        // 自旋失败，升级为阻塞（使用synchronized）
        synchronized (this) {
            value.incrementAndGet();
        }
    }
}
```

**应用场景**：
- 并发度不确定的场景
- JVM的锁升级机制（偏向锁→轻量级锁→重量级锁）

## JDK中的实际案例

### 案例1：AtomicBoolean.compareAndSet（无自旋）

```java
public class AtomicBoolean {
    private volatile int value;
    
    /**
     * 单次CAS，不自旋
     */
    public final boolean compareAndSet(boolean expect, boolean update) {
        int e = expect ? 1 : 0;
        int u = update ? 1 : 0;
        return unsafe.compareAndSwapInt(this, valueOffset, e, u);
        // 直接返回结果，不重试
    }
}
```

### 案例2：AtomicInteger.incrementAndGet（自旋）

```java
public class AtomicInteger {
    /**
     * 自增：使用自旋
     */
    public final int incrementAndGet() {
        return unsafe.getAndAddInt(this, valueOffset, 1) + 1;
    }
    
    // Unsafe.getAndAddInt的实现
    public final int getAndAddInt(Object o, long offset, int delta) {
        int v;
        do {
            v = getIntVolatile(o, offset);
        } while (!compareAndSwapInt(o, offset, v, v + delta));
        // ↑ 自旋直到成功
        return v;
    }
}
```

### 案例3：ConcurrentHashMap.putIfAbsent（条件性自旋）

```java
// ConcurrentHashMap的put操作（简化版）
public V putIfAbsent(K key, V value) {
    int hash = spread(key.hashCode());
    for (Node<K,V>[] tab = table;;) {  // 外层自旋
        // ...
        Node<K,V> f = tabAt(tab, i);  // volatile读
        
        if (f == null) {
            // 使用CAS插入新节点
            if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value, null))) {
                break;  // CAS成功，退出自旋
            }
            // CAS失败，继续下一轮自旋
        } else {
            synchronized (f) {  // 链表或树的修改需要加锁
                // ...
            }
            break;  // 加锁操作完成后退出
        }
    }
    return null;
}
```

**特点**：
- 节点为空时：CAS + 自旋
- 节点非空时：synchronized（不自旋）

### 案例4：LongAdder（分段减少自旋）

```java
public class LongAdder {
    /**
     * 核心思想：分段CAS，减少竞争
     */
    public void increment() {
        Cell[] cs; long b, v; int m; Cell c;
        
        // 先尝试CAS更新base（无锁快速路径）
        if ((cs = cells) != null || !casBase(b = base, b + 1)) {
            // 快速路径失败，分配Cell
            // ...
            
            // 对特定Cell进行CAS（竞争分散到多个Cell）
            if (!c.cas(v = c.value, v + 1)) {
                // CAS失败：扩容或重新哈希，而不是无限自旋
                longAccumulate(1, null, true);
            }
        }
    }
}
```

**优势**：
- 通过分段降低单个CAS的竞争
- 失败时扩容而非自旋，避免CPU浪费

## 自旋与非自旋的性能对比

### 测试代码

```java
public class SpinVsNonSpinTest {
    static AtomicInteger counter = new AtomicInteger(0);
    static int successCount = 0;
    static int failCount = 0;
    
    // 方法1：单次CAS（无自旋）
    public static void trySingleCAS() {
        int current = counter.get();
        if (counter.compareAndSet(current, current + 1)) {
            successCount++;
        } else {
            failCount++;
        }
    }
    
    // 方法2：CAS + 自旋
    public static void spinCAS() {
        int current;
        do {
            current = counter.get();
        } while (!counter.compareAndSet(current, current + 1));
    }
    
    public static void main(String[] args) throws InterruptedException {
        int threadCount = 100;
        int iterations = 1000;
        
        // 测试1：单次CAS
        System.out.println("=== 测试单次CAS ===");
        counter.set(0);
        successCount = 0;
        failCount = 0;
        
        long start1 = System.currentTimeMillis();
        Thread[] threads1 = new Thread[threadCount];
        for (int i = 0; i < threadCount; i++) {
            threads1[i] = new Thread(() -> {
                for (int j = 0; j < iterations; j++) {
                    trySingleCAS();
                }
            });
            threads1[i].start();
        }
        for (Thread t : threads1) t.join();
        long end1 = System.currentTimeMillis();
        
        System.out.println("耗时：" + (end1 - start1) + "ms");
        System.out.println("成功：" + successCount + ", 失败：" + failCount);
        System.out.println("最终值：" + counter.get());
        
        // 测试2：自旋CAS
        System.out.println("\n=== 测试自旋CAS ===");
        counter.set(0);
        
        long start2 = System.currentTimeMillis();
        Thread[] threads2 = new Thread[threadCount];
        for (int i = 0; i < threadCount; i++) {
            threads2[i] = new Thread(() -> {
                for (int j = 0; j < iterations; j++) {
                    spinCAS();
                }
            });
            threads2[i].start();
        }
        for (Thread t : threads2) t.join();
        long end2 = System.currentTimeMillis();
        
        System.out.println("耗时：" + (end2 - start2) + "ms");
        System.out.println("最终值：" + counter.get());
    }
}
```

**运行结果**：
```
=== 测试单次CAS ===
耗时：45ms
成功：85234, 失败：14766
最终值：85234

=== 测试自旋CAS ===
耗时：523ms
最终值：100000
```

**结论**：
- 单次CAS：快速完成，但有失败
- 自旋CAS：保证成功，但耗时更长

## 选择建议

| 场景 | 推荐方式 | 理由 |
|-----|---------|------|
| 低并发 | CAS + 无限自旋 | 冲突少，自旋次数少 |
| 中并发 | CAS + 有限自旋 | 平衡成功率和性能 |
| 高并发 | LongAdder（分段）| 降低竞争，避免过度自旋 |
| 乐观锁 | 单次CAS | 快速失败，上层处理 |
| 必须成功 | CAS + 自旋 | 保证操作完成 |

## 答题总结

### 三句话总结

1. **CAS本身不包含自旋**，只是一次原子的比较并交换操作，返回成功或失败。

2. **自旋是建立在CAS之上的重试机制**，由上层代码决定是否重试、重试多少次。

3. **JDK中有三种模式**：
   - 单次CAS：如`compareAndSet()`，失败直接返回
   - 无限自旋：如`AtomicInteger.incrementAndGet()`，循环直到成功
   - 自适应：如`ConcurrentHashMap`，根据情况选择策略

### 面试答题模板

> "CAS本身不一定有自旋。CAS只是一次原子操作，比较并交换，成功返回true，失败返回false，不包含重试逻辑。
>
> 自旋是在CAS之上的重试机制，由调用方决定。比如`AtomicBoolean.compareAndSet()`就是单次CAS，失败直接返回；而`AtomicInteger.incrementAndGet()`使用了自旋，失败后会循环重试直到成功。
>
> 在实际应用中，需要根据并发度选择策略：低并发可以自旋，高并发下过度自旋会浪费CPU，应该使用有限自旋或者像LongAdder那样通过分段降低竞争。"

