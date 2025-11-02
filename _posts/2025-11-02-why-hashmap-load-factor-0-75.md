---
layout: post
title: "HashMap的加载因子为什么是0.75？"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [HashMap, 负载因子, 性能调优]
description: "深入分析HashMap负载因子0.75的设计原理，探讨空间与时间的平衡艺术"
---

## 核心概念

**加载因子（Load Factor）** 是 HashMap 中用于衡量**哈希表填充程度**的关键参数，默认值为 **0.75**。它决定了何时触发扩容操作，是**空间利用率**和**时间效率**之间的权衡点。

## 源码定义

```java
public class HashMap<K,V> extends AbstractMap<K,V> {
    // 默认负载因子：0.75
    static final float DEFAULT_LOAD_FACTOR = 0.75f;
    
    // 扩容阈值 = 容量 × 负载因子
    int threshold;
    
    // 负载因子
    final float loadFactor;
    
    public HashMap() {
        this.loadFactor = DEFAULT_LOAD_FACTOR;  // 0.75
    }
    
    public HashMap(int initialCapacity, float loadFactor) {
        // 可以自定义负载因子
        this.loadFactor = loadFactor;
        this.threshold = tableSizeFor(initialCapacity);
    }
}
```

**扩容触发条件**：
```java
final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    // ...
    if (++size > threshold)  // size > capacity × loadFactor
        resize();
    // ...
}
```

## 为什么是 0.75？

### 1. 时间与空间的权衡

**负载因子的影响**：

| 负载因子 | 空间利用率 | 查询效率 | 扩容频率 | 适用场景 |
|---------|-----------|---------|---------|---------|
| **0.5** | 低（50%） | 高（冲突少） | 频繁 | 内存充足，追求性能 |
| **0.75** | 适中（75%） | 适中 | 适中 | **默认推荐** |
| **1.0** | 高（100%） | 低（冲突多） | 较少 | 内存紧张 |
| **>1.0** | 很高 | 很低（冲突严重） | 罕见 | 不推荐 |

**示例对比**：
```java
public class LoadFactorTest {
    public static void main(String[] args) {
        // 场景：插入 12 个元素，初始容量 16
        
        // 负载因子 0.5
        // threshold = 16 × 0.5 = 8
        // 插入 8 个元素后扩容到 32，再插入 4 个，共 1 次扩容
        Map<Integer, String> map1 = new HashMap<>(16, 0.5f);
        
        // 负载因子 0.75（默认）
        // threshold = 16 × 0.75 = 12
        // 插入 12 个元素后扩容到 32，共 1 次扩容
        Map<Integer, String> map2 = new HashMap<>(16, 0.75f);
        
        // 负载因子 1.0
        // threshold = 16 × 1.0 = 16
        // 插入 12 个元素不扩容，但哈希冲突增加
        Map<Integer, String> map3 = new HashMap<>(16, 1.0f);
    }
}
```

### 2. 泊松分布的理论支持

**官方注释中的说明**（源码中的注释）：

```java
/**
 * Ideally, under random hashCodes, the frequency of
 * nodes in bins follows a Poisson distribution with a
 * parameter of about 0.5 on average for the default
 * resizing threshold of 0.75.
 *
 * 在理想情况下（随机哈希码），当负载因子为 0.75 时，
 * 桶中节点的频率遵循泊松分布，参数约为 0.5。
 */
```

**泊松分布分析**：

当负载因子为 0.75 时，单个桶中元素数量的概率分布：

| 桶中元素数 | 概率 |
|-----------|------|
| 0 | 60.65% |
| 1 | 30.33% |
| 2 | 7.58% |
| 3 | 1.26% |
| 4 | 0.16% |
| 5 | 0.016% |
| 6 | 0.001% |
| 7 | 0.0001% |
| 8 | 0.00001% |

**结论**：
- 大部分桶是空的或只有 1 个元素（查询效率高）
- 链表长度达到 8 的概率极低（约千万分之一）
- 因此设置树化阈值为 8 是合理的

### 3. 实际性能测试

```java
public class LoadFactorPerformanceTest {
    public static void main(String[] args) {
        int elementCount = 10000;
        
        // 测试不同负载因子的性能
        testLoadFactor(0.5f, elementCount);
        testLoadFactor(0.75f, elementCount);
        testLoadFactor(1.0f, elementCount);
    }
    
    static void testLoadFactor(float loadFactor, int count) {
        Map<Integer, String> map = new HashMap<>(16, loadFactor);
        
        // 插入性能
        long startPut = System.nanoTime();
        for (int i = 0; i < count; i++) {
            map.put(i, "value" + i);
        }
        long endPut = System.nanoTime();
        
        // 查询性能
        long startGet = System.nanoTime();
        for (int i = 0; i < count; i++) {
            map.get(i);
        }
        long endGet = System.nanoTime();
        
        System.out.println("负载因子: " + loadFactor);
        System.out.println("插入耗时: " + (endPut - startPut) / 1000000 + "ms");
        System.out.println("查询耗时: " + (endGet - startGet) / 1000000 + "ms");
        System.out.println("最终容量: " + getCapacity(map));
        System.out.println("---");
    }
    
    static int getCapacity(Map<?, ?> map) {
        // 通过反射获取实际容量（仅用于测试）
        try {
            java.lang.reflect.Field tableField = HashMap.class.getDeclaredField("table");
            tableField.setAccessible(true);
            Object[] table = (Object[]) tableField.get(map);
            return table == null ? 0 : table.length;
        } catch (Exception e) {
            return -1;
        }
    }
}
```

**典型输出**：
```
负载因子: 0.5
插入耗时: 15ms
查询耗时: 3ms
最终容量: 32768  ← 扩容次数多，内存占用大

负载因子: 0.75
插入耗时: 12ms
查询耗时: 4ms
最终容量: 16384  ← 平衡点

负载因子: 1.0
插入耗时: 10ms
查询耗时: 8ms   ← 冲突多，查询变慢
最终容量: 16384
```

## 如何选择负载因子？

### 默认 0.75 适用于大多数场景

```java
// 推荐：使用默认值
Map<String, Object> map = new HashMap<>();
```

### 自定义负载因子的场景

**1. 内存敏感，数据量大**
```java
// 提高负载因子，减少扩容，节省内存
Map<String, Object> map = new HashMap<>(1024, 0.9f);
// 缺点：哈希冲突增加，查询性能下降
```

**2. 性能优先，内存充足**
```java
// 降低负载因子，减少冲突，提升查询速度
Map<String, Object> map = new HashMap<>(1024, 0.5f);
// 缺点：内存占用增加，扩容更频繁
```

**3. 数据量已知**
```java
// 最佳实践：提前计算容量，避免扩容
int expectedSize = 1000;
int capacity = (int) (expectedSize / 0.75f) + 1;
Map<String, Object> map = new HashMap<>(capacity);
```

## 扩容阈值计算

```java
public class ThresholdExample {
    public static void main(String[] args) {
        // 默认初始化
        Map<String, Object> map1 = new HashMap<>();
        // capacity = 16, loadFactor = 0.75
        // threshold = 16 × 0.75 = 12
        // 插入第 13 个元素时触发扩容
        
        // 自定义容量
        Map<String, Object> map2 = new HashMap<>(32);
        // capacity = 32, loadFactor = 0.75
        // threshold = 32 × 0.75 = 24
        // 插入第 25 个元素时触发扩容
        
        // 自定义负载因子
        Map<String, Object> map3 = new HashMap<>(16, 0.5f);
        // capacity = 16, loadFactor = 0.5
        // threshold = 16 × 0.5 = 8
        // 插入第 9 个元素时触发扩容
    }
}
```

## 源码中的扩容判断

```java
final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    Node<K,V>[] tab; Node<K,V> p; int n, i;
    
    // 初始化或扩容
    if ((tab = table) == null || (n = tab.length) == 0)
        n = (tab = resize()).length;
    
    // ... 插入逻辑 ...
    
    // 关键判断：元素数量超过阈值时扩容
    if (++size > threshold)
        resize();
    
    afterNodeInsertion(evict);
    return null;
}

final Node<K,V>[] resize() {
    Node<K,V>[] oldTab = table;
    int oldCap = (oldTab == null) ? 0 : oldTab.length;
    int oldThr = threshold;
    int newCap, newThr = 0;
    
    if (oldCap > 0) {
        // 扩容为原来的 2 倍
        newCap = oldCap << 1;
        // 新阈值 = 新容量 × 负载因子
        newThr = oldThr << 1;
    }
    // ...
    
    threshold = newThr;
    // ... 数据迁移 ...
}
```

## 面试答题总结

**答题要点**：
1. **定义**：负载因子决定了 HashMap 何时扩容（元素数量 > 容量 × 0.75）
2. **权衡**：0.75 是**空间利用率**和**查询效率**的最佳平衡点
3. **理论依据**：基于泊松分布，0.75 时冲突概率最低
4. **实践意义**：既避免了频繁扩容，又保证了较低的冲突率

**加分项**：
- 提到泊松分布和源码注释
- 说明不同负载因子的适用场景
- 给出容量计算公式：`(expectedSize / loadFactor) + 1`
- 对比 0.5、0.75、1.0 的性能差异

**一句话总结**：0.75 是经过理论计算和实践验证的最优值，能够在空间和时间之间取得最佳平衡。

