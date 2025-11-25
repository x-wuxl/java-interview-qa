---
layout: default
title: "HashMap的hash方法原理"
parent: 集合框架
nav_order: 92
description: "深入剖析HashMap的hash方法实现，解析扰动函数的设计原理和优化思想"
date: 2025-11-02
---
## 核心概念

HashMap 的 **hash 方法**是将任意对象的 hashCode 转换为数组索引的关键步骤。它通过**扰动函数（perturbation function）** 优化 hash 值的分布，减少哈希冲突，提升 HashMap 的性能。

## 源码实现（JDK 1.8）

```java
static final int hash(Object key) {
    int h;
    // 如果 key 为 null，hash 值为 0
    // 否则：高 16 位异或低 16 位
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}

// 使用 hash 值计算数组索引
public V put(K key, V value) {
    return putVal(hash(key), key, value, false, true);
}

final V putVal(int hash, K key, V value, ...) {
    // ...
    // 通过 (n-1) & hash 计算索引位置
    if ((p = tab[i = (n - 1) & hash]) == null)
        tab[i] = newNode(hash, key, value, null);
    // ...
}
```

## 完整流程

### 1. 获取 hashCode

```java
Object key = "hello";
int hashCode = key.hashCode();  // 调用 String 的 hashCode()
```

### 2. 扰动处理（高低位异或）

```java
int h = hashCode;
int hash = h ^ (h >>> 16);  // 高 16 位异或低 16 位
```

**图示**：
```
原始 hashCode (32位):
高16位                  低16位
1010 1100 0011 1001 | 0110 1010 1100 0101

右移16位 (h >>> 16):
0000 0000 0000 0000 | 1010 1100 0011 1001

异或运算 (^):
1010 1100 0011 1001   (原高16位)
0000 0000 0000 0000   (原高16位移到低位)
─────────────────────────────────────
1010 1100 0011 1001 | 1100 0110 1111 1100
                    ↑
                扰动后的低16位（混合了高低位信息）
```

### 3. 计算数组索引

```java
int index = (capacity - 1) & hash;
```

**示例**：
```java
// 假设 capacity = 16
int capacity = 16;
int mask = capacity - 1;  // 15 = 0000 1111

// hash 值（扰动后）
int hash = 0b1010_1100_0011_1001_1100_0110_1111_1100;

// 计算索引（只取低 4 位）
int index = mask & hash;  // 0000 1111 & xxxx xxxx = 0000 1100 = 12
```

## 为什么要扰动？

### 问题：直接使用 hashCode 的缺陷

**场景 1：高位信息丢失**

```java
// 容量为 16 时，只使用低 4 位
int capacity = 16;
int mask = 15;  // 0000 1111

// 两个不同的 hashCode，但低 4 位相同
int hash1 = 0b0000_0000_0000_0000_0000_0000_0000_0101;  // 5
int hash2 = 0b1111_1111_1111_1111_0000_0000_0000_0101;  // 高位不同

int index1 = hash1 & mask;  // 5
int index2 = hash2 & mask;  // 5  ← 冲突！
```

**问题**：只使用低位，导致高位信息完全浪费，冲突率高。

### 解决：高低位异或混合

```java
// 扰动后，高位信息也参与低位计算
int h1 = 0b0000_0000_0000_0000_0000_0000_0000_0101;
int hash1 = h1 ^ (h1 >>> 16);
// = 0b0000_0000_0000_0000_0000_0000_0000_0101 
// ^ 0b0000_0000_0000_0000_0000_0000_0000_0000
// = 0b0000_0000_0000_0000_0000_0000_0000_0101

int h2 = 0b1111_1111_1111_1111_0000_0000_0000_0101;
int hash2 = h2 ^ (h2 >>> 16);
// = 0b1111_1111_1111_1111_0000_0000_0000_0101 
// ^ 0b0000_0000_0000_0000_1111_1111_1111_1111
// = 0b1111_1111_1111_1111_1111_1111_1111_1010

int index1 = hash1 & 15;  // 5
int index2 = hash2 & 15;  // 10  ← 不冲突！
```

**效果**：高 16 位的信息融入低 16 位，减少冲突。

## JDK 1.7 vs JDK 1.8

### JDK 1.7：4 次扰动

```java
final int hash(Object k) {
    int h = hashSeed;
    if (0 != h && k instanceof String) {
        return sun.misc.Hashing.stringHash32((String) k);
    }
    
    h ^= k.hashCode();
    
    // 4 次扰动
    h ^= (h >>> 20) ^ (h >>> 12);
    return h ^ (h >>> 7) ^ (h >>> 4);
}
```

**特点**：
- 多次扰动，分布更均匀
- 但计算开销较大

### JDK 1.8：1 次扰动

```java
static final int hash(Object key) {
    int h;
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}
```

**优化原因**：
1. **红黑树优化**：JDK 1.8 引入红黑树，即使冲突也能保持 O(log n)
2. **性能提升**：简化计算，减少 CPU 开销
3. **效果足够**：一次异或已经能很好地混合高低位信息

## 为什么是右移 16 位？

### 1. 正好是 32 位的一半

```java
int hashCode;  // 32 位
// 右移 16 位 = 将高 16 位移到低 16 位
// 异或后，低 16 位混合了高低位信息
```

### 2. 适配常见容量

**HashMap 默认容量是 16，常用容量通常在 2^4 ~ 2^16 之间**：

| 容量 | 二进制 | 使用位数 | 影响范围 |
|------|--------|---------|---------|
| 16 | 0x10 | 低 4 位 | 低 16 位完全覆盖 |
| 256 | 0x100 | 低 8 位 | 低 16 位完全覆盖 |
| 65536 | 0x10000 | 低 16 位 | 刚好利用全部低 16 位 |

**结论**：右移 16 位能够在大多数容量下，让高位信息参与索引计算。

### 3. 性能与效果的平衡

```java
// 方案1：右移 8 位（混合不充分）
hash = h ^ (h >>> 8);   // 高8位混入低位，但高8位利用不充分

// 方案2：右移 16 位（推荐）
hash = h ^ (h >>> 16);  // 高16位混入低16位，平衡最好

// 方案3：右移 24 位（过度混合）
hash = h ^ (h >>> 24);  // 只有高8位参与，信息利用不足
```

## 实战案例

### 案例 1：冲突对比

```java
public class HashCollisionTest {
    public static void main(String[] args) {
        int capacity = 16;
        int mask = capacity - 1;
        
        // 测试一组 hashCode
        int[] hashCodes = {
            0x00000005, 0x00010005, 0x00020005, 0x00030005,
            0x10000005, 0x20000005, 0x30000005, 0x40000005
        };
        
        System.out.println("不扰动的冲突情况：");
        for (int h : hashCodes) {
            int index = h & mask;
            System.out.println("hashCode=" + Integer.toHexString(h) + " → index=" + index);
        }
        // 结果：全部映射到 index=5（严重冲突）
        
        System.out.println("\n扰动后的分布：");
        for (int h : hashCodes) {
            int hash = h ^ (h >>> 16);
            int index = hash & mask;
            System.out.println("hashCode=" + Integer.toHexString(h) + " → hash=" + Integer.toHexString(hash) + " → index=" + index);
        }
        // 结果：分布到不同的 index（冲突减少）
    }
}
```

**输出**：
```
不扰动的冲突情况：
hashCode=5 → index=5
hashCode=10005 → index=5
hashCode=20005 → index=5
...（全部冲突）

扰动后的分布：
hashCode=5 → hash=5 → index=5
hashCode=10005 → hash=10000 → index=0
hashCode=20005 → hash=20000 → index=0
...（冲突显著减少）
```

### 案例 2：null key 的处理

```java
public class NullKeyTest {
    public static void main(String[] args) {
        Map<String, String> map = new HashMap<>();
        
        // HashMap 允许 null key
        map.put(null, "value1");
        System.out.println(map.get(null));  // value1
        
        // null key 的 hash 值固定为 0
        // 总是存储在 table[0] 位置
    }
}
```

**源码体现**：
```java
static final int hash(Object key) {
    int h;
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
    //     ↑ null key 的 hash 值为 0
}
```

## 性能对比

```java
public class HashPerformanceTest {
    public static void main(String[] args) {
        int iterations = 10_000_000;
        int h = 0x12345678;
        
        // 测试1：不扰动
        long start1 = System.nanoTime();
        for (int i = 0; i < iterations; i++) {
            int hash = h;
            int index = hash & 15;
        }
        long end1 = System.nanoTime();
        
        // 测试2：JDK 1.8 扰动
        long start2 = System.nanoTime();
        for (int i = 0; i < iterations; i++) {
            int hash = h ^ (h >>> 16);
            int index = hash & 15;
        }
        long end2 = System.nanoTime();
        
        // 测试3：JDK 1.7 扰动
        long start3 = System.nanoTime();
        for (int i = 0; i < iterations; i++) {
            int hash = h ^ (h >>> 20) ^ (h >>> 12);
            hash = hash ^ (hash >>> 7) ^ (hash >>> 4);
            int index = hash & 15;
        }
        long end3 = System.nanoTime();
        
        System.out.println("不扰动耗时: " + (end1 - start1) / 1_000_000 + "ms");
        System.out.println("JDK 1.8 扰动耗时: " + (end2 - start2) / 1_000_000 + "ms");
        System.out.println("JDK 1.7 扰动耗时: " + (end3 - start3) / 1_000_000 + "ms");
    }
}
```

## 面试答题总结

**答题要点**：
1. **目的**：优化 hash 分布，减少哈希冲突
2. **实现**：`(h = key.hashCode()) ^ (h >>> 16)`，高 16 位异或低 16 位
3. **原因**：容量通常较小，只使用低位，扰动让高位信息也参与计算
4. **演进**：JDK 1.7 是 4 次扰动，JDK 1.8 简化为 1 次（因为有红黑树优化）

**加分项**：
- 画图说明高低位异或过程
- 对比 JDK 1.7 和 1.8 的差异
- 解释为什么是右移 16 位
- 提到 null key 的特殊处理（hash = 0）

**一句话总结**：通过高低位异或，让高位信息参与低位索引计算，在保证性能的同时减少哈希冲突。

