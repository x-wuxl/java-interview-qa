---
layout: post
title: "HashMap的容量为什么是2的幂次方？"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [HashMap, 位运算, 性能优化]
description: "深入解析HashMap容量设计为2的幂次方的原因，包括位运算优化、hash分布均匀性等"
---

## 核心概念

HashMap 的容量（capacity）始终保持为 **2 的幂次方**（如 16, 32, 64, 128...），这是一个精心设计的特性，主要目的是通过**位运算优化性能**和**保证 hash 分布的均匀性**。

## 源码体现

```java
public class HashMap<K,V> extends AbstractMap<K,V> {
    // 默认初始容量：16 = 2^4
    static final int DEFAULT_INITIAL_CAPACITY = 1 << 4;
    
    // 最大容量：2^30
    static final int MAXIMUM_CAPACITY = 1 << 30;
    
    public HashMap(int initialCapacity) {
        this.threshold = tableSizeFor(initialCapacity);
    }
    
    // 确保容量是2的幂次方
    static final int tableSizeFor(int cap) {
        int n = cap - 1;
        n |= n >>> 1;
        n |= n >>> 2;
        n |= n >>> 4;
        n |= n >>> 8;
        n |= n >>> 16;
        return (n < 0) ? 1 : (n >= MAXIMUM_CAPACITY) ? MAXIMUM_CAPACITY : n + 1;
    }
}
```

**示例**：
```java
new HashMap<>(10);   // 实际容量会是 16
new HashMap<>(17);   // 实际容量会是 32
new HashMap<>(100);  // 实际容量会是 128
```

## 三大核心原因

### 1. 高效的取模运算

**传统取模方式**（性能较差）：
```java
// 计算元素在数组中的位置
int index = hash % capacity;  // 取模运算，性能较低
```

**HashMap 的位运算方式**（性能优异）：
```java
// 当 capacity 是 2 的幂次方时
int index = hash & (capacity - 1);  // 等价于取模，但更快
```

**数学原理**：
```
假设 capacity = 16 (二进制: 0001 0000)
capacity - 1 = 15 (二进制: 0000 1111)

任意 hash 值 & 15，结果必然在 [0, 15] 范围内
等价于 hash % 16，但位运算速度远快于除法运算
```

**性能对比**：
```java
// 性能测试示例
public class PerformanceTest {
    public static void main(String[] args) {
        int hash = 123456;
        int capacity = 16;
        
        // 方式1：取模运算
        long start1 = System.nanoTime();
        for (int i = 0; i < 10000000; i++) {
            int index = hash % capacity;
        }
        long end1 = System.nanoTime();
        System.out.println("取模耗时: " + (end1 - start1) + "ns");
        
        // 方式2：位运算
        long start2 = System.nanoTime();
        for (int i = 0; i < 10000000; i++) {
            int index = hash & (capacity - 1);
        }
        long end2 = System.nanoTime();
        System.out.println("位运算耗时: " + (end2 - start2) + "ns");
        
        // 位运算性能约是取模运算的 2-3 倍
    }
}
```

### 2. 保证 Hash 分布均匀

**为什么 2 的幂次方能保证均匀性？**

```java
// 假设 capacity = 16，则 capacity - 1 = 15
// 15 的二进制: 0000 1111（低4位全是1）

// 不同 hash 值的分布
hash1: 1101 0101 & 0000 1111 = 0000 0101 = 5
hash2: 1001 1010 & 0000 1111 = 0000 1010 = 10
hash3: 1111 0011 & 0000 1111 = 0000 0011 = 3
```

**关键点**：`capacity - 1` 的二进制低位全是 1，能够充分利用 hash 值的低位信息。

**反例（非 2 的幂次方）**：
```java
// 假设 capacity = 10，则 capacity - 1 = 9
// 9 的二进制: 0000 1001（低位不全是1）

hash1: 1101 0101 & 0000 1001 = 0000 0001 = 1
hash2: 1001 1010 & 0000 1001 = 0000 1000 = 8
hash3: 1111 0011 & 0000 1001 = 0000 0001 = 1  ← 冲突
hash4: 1011 0110 & 0000 1001 = 0000 0000 = 0
hash5: 1100 1110 & 0000 1001 = 0000 1000 = 8  ← 冲突

// 某些位置（如2,3,4,5,6,7,9）可能永远不会被用到
// 导致哈希冲突增加，分布不均匀
```

### 3. 扩容时的位置计算优化

**JDK 1.8 的扩容优化**：

```java
final Node<K,V>[] resize() {
    // ... 
    int oldCap = oldTab.length;
    int newCap = oldCap << 1;  // 容量翻倍（仍是2的幂次方）
    
    // 关键优化：判断元素在新数组中的位置
    for (int j = 0; j < oldCap; ++j) {
        Node<K,V> e;
        if ((e = oldTab[j]) != null) {
            // ...
            if ((e.hash & oldCap) == 0) {
                // 位置不变，仍在 index = j
                newTab[j] = e;
            } else {
                // 位置变化，新位置 = j + oldCap
                newTab[j + oldCap] = e;
            }
        }
    }
}
```

**原理说明**：
```
oldCap = 16 (0001 0000)
newCap = 32 (0010 0000)

元素原位置: hash & (16-1) = hash & 0000 1111
元素新位置: hash & (32-1) = hash & 0001 1111

关键判断: hash & 16 (oldCap)
- 如果为 0：说明 hash 的第5位是0，新位置不变
- 如果为 1：说明 hash 的第5位是1，新位置 = 原位置 + 16
```

**示例**：
```
假设 oldCap = 16，扩容为 newCap = 32

hash1 = 0000 0101 (5)
hash1 & 15 = 5          (旧位置)
hash1 & 16 = 0          (第5位是0)
hash1 & 31 = 5          (新位置不变)

hash2 = 0001 0101 (21)
hash2 & 15 = 5          (旧位置)
hash2 & 16 = 16         (第5位是1)
hash2 & 31 = 21 = 5+16  (新位置 = 旧位置 + oldCap)
```

**性能优势**：
- 不需要重新计算 hash
- 只需一次位运算判断
- 扩容效率显著提升

## tableSizeFor 方法详解

```java
static final int tableSizeFor(int cap) {
    int n = cap - 1;  // 防止 cap 本身就是2的幂次方时，结果翻倍
    n |= n >>> 1;     // 将最高位的1后面的1位变为1
    n |= n >>> 2;     // 将最高位的1后面的2位变为1
    n |= n >>> 4;     // 将最高位的1后面的4位变为1
    n |= n >>> 8;     // 将最高位的1后面的8位变为1
    n |= n >>> 16;    // 将最高位的1后面的16位变为1
    return (n < 0) ? 1 : (n >= MAXIMUM_CAPACITY) ? MAXIMUM_CAPACITY : n + 1;
}
```

**执行过程示例**：
```
输入: cap = 10 (二进制: 0000 1010)

n = 10 - 1 = 9     →  0000 1001
n |= n >>> 1       →  0000 1001 | 0000 0100 = 0000 1101
n |= n >>> 2       →  0000 1101 | 0000 0011 = 0000 1111
n |= n >>> 4       →  0000 1111 | 0000 0000 = 0000 1111
n |= n >>> 8       →  0000 1111 | 0000 0000 = 0000 1111
n |= n >>> 16      →  0000 1111 | 0000 0000 = 0000 1111

return n + 1 = 15 + 1 = 16 (2的幂次方)
```

## 实际应用建议

```java
public class HashMapExample {
    public static void main(String[] args) {
        // 1. 如果知道数据量，应该提前指定容量
        // 避免多次扩容，提升性能
        
        // 错误示例：频繁扩容
        Map<String, Object> map1 = new HashMap<>();  // 默认16
        for (int i = 0; i < 1000; i++) {
            map1.put("key" + i, i);  // 会触发多次扩容
        }
        
        // 正确示例：预估容量
        // 公式：容量 = 预期元素数量 / 0.75 + 1
        int expectedSize = 1000;
        int capacity = (int) (expectedSize / 0.75f + 1);
        Map<String, Object> map2 = new HashMap<>(capacity);
        for (int i = 0; i < 1000; i++) {
            map2.put("key" + i, i);  // 不会触发扩容
        }
        
        // 2. 即使指定了非2的幂次方，也会自动转换
        Map<String, Object> map3 = new HashMap<>(10);
        // 实际容量是 16，不是 10
    }
}
```

## 面试答题总结

**答题要点**：
1. **性能优化**：`hash & (capacity-1)` 等价于 `hash % capacity`，但位运算更快
2. **均匀分布**：capacity-1 的二进制低位全是1，能充分利用 hash 值
3. **扩容优化**：通过 `hash & oldCap` 快速定位新位置，无需重新计算 hash
4. **自动调整**：即使指定非 2 的幂次方，`tableSizeFor` 也会向上取整

**加分项**：
- 画图说明位运算过程
- 对比取模和位运算的性能差异
- 说明扩容时的高低位链表划分
- 提到 `tableSizeFor` 方法的巧妙实现

**一句话总结**：2的幂次方设计是性能和分布均匀性的完美平衡。

