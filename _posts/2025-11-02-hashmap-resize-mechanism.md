---
layout: post
title: "HashMap扩容机制详解"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [HashMap, 扩容机制, 源码分析, 性能优化]
description: "全面剖析HashMap的扩容机制，包括触发条件、扩容过程、元素迁移策略和性能优化"
---

## 核心概念

HashMap 的**扩容机制（resize）** 是指当元素数量超过阈值时，自动将底层数组容量扩大为原来的 **2 倍**，并将所有元素重新分配到新数组的过程。这是保证 HashMap 性能的关键机制。

## 扩容触发条件

### 1. 元素数量超过阈值

**核心公式**：
```java
threshold = capacity × loadFactor

// 触发条件
if (++size > threshold) {
    resize();
}
```

**默认值**：
```java
static final int DEFAULT_INITIAL_CAPACITY = 16;     // 默认容量
static final float DEFAULT_LOAD_FACTOR = 0.75f;    // 默认负载因子

// 默认阈值 = 16 × 0.75 = 12
// 插入第 13 个元素时触发扩容
```

### 2. 初始化时的延迟扩容

```java
public HashMap() {
    this.loadFactor = DEFAULT_LOAD_FACTOR;
    // 注意：此时 table 为 null，没有分配数组空间
}

public V put(K key, V value) {
    return putVal(hash(key), key, value, false, true);
}

final V putVal(int hash, K key, V value, ...) {
    Node<K,V>[] tab;
    
    // 首次 put 时，table 为 null，触发初始化扩容
    if ((tab = table) == null || tab.length == 0)
        tab = resize();  // ← 初始化扩容
    
    // ...
}
```

### 3. 树化前的容量检查

```java
final void treeifyBin(Node<K,V>[] tab, int hash) {
    int n;
    
    // 如果容量 < 64，优先扩容而不是树化
    if (tab == null || (n = tab.length) < MIN_TREEIFY_CAPACITY)
        resize();  // ← 树化前扩容
    else {
        // 容量够了才树化
        // ...
    }
}
```

## 扩容完整流程

### 源码解析（JDK 1.8）

```java
final Node<K,V>[] resize() {
    Node<K,V>[] oldTab = table;
    int oldCap = (oldTab == null) ? 0 : oldTab.length;
    int oldThr = threshold;
    int newCap, newThr = 0;
    
    // ========== 第一阶段：计算新容量和新阈值 ==========
    
    if (oldCap > 0) {
        // 情况1：已有容量，执行扩容
        if (oldCap >= MAXIMUM_CAPACITY) {
            // 已达最大容量（2^30），不再扩容
            threshold = Integer.MAX_VALUE;
            return oldTab;
        }
        else if ((newCap = oldCap << 1) < MAXIMUM_CAPACITY &&
                 oldCap >= DEFAULT_INITIAL_CAPACITY) {
            // 容量翻倍，阈值翻倍
            newThr = oldThr << 1;  // double threshold
        }
    }
    else if (oldThr > 0) {
        // 情况2：通过构造函数指定了初始容量
        newCap = oldThr;
    }
    else {
        // 情况3：首次初始化，使用默认值
        newCap = DEFAULT_INITIAL_CAPACITY;  // 16
        newThr = (int)(DEFAULT_LOAD_FACTOR * DEFAULT_INITIAL_CAPACITY);  // 12
    }
    
    // 计算新阈值（针对某些特殊情况）
    if (newThr == 0) {
        float ft = (float)newCap * loadFactor;
        newThr = (newCap < MAXIMUM_CAPACITY && ft < (float)MAXIMUM_CAPACITY ?
                  (int)ft : Integer.MAX_VALUE);
    }
    
    threshold = newThr;
    
    // ========== 第二阶段：创建新数组 ==========
    
    @SuppressWarnings({"rawtypes","unchecked"})
    Node<K,V>[] newTab = (Node<K,V>[])new Node[newCap];
    table = newTab;
    
    // ========== 第三阶段：数据迁移 ==========
    
    if (oldTab != null) {
        // 遍历旧数组的每个桶
        for (int j = 0; j < oldCap; ++j) {
            Node<K,V> e;
            if ((e = oldTab[j]) != null) {
                oldTab[j] = null;  // 释放旧引用，帮助 GC
                
                if (e.next == null) {
                    // 情况1：桶中只有一个节点
                    newTab[e.hash & (newCap - 1)] = e;
                }
                else if (e instanceof TreeNode) {
                    // 情况2：红黑树节点
                    ((TreeNode<K,V>)e).split(this, newTab, j, oldCap);
                }
                else {
                    // 情况3：链表节点（核心优化）
                    Node<K,V> loHead = null, loTail = null;  // 低位链表
                    Node<K,V> hiHead = null, hiTail = null;  // 高位链表
                    Node<K,V> next;
                    
                    do {
                        next = e.next;
                        // 通过 hash & oldCap 判断位置
                        if ((e.hash & oldCap) == 0) {
                            // 位置不变，放入低位链表
                            if (loTail == null)
                                loHead = e;
                            else
                                loTail.next = e;
                            loTail = e;
                        }
                        else {
                            // 位置改变，放入高位链表
                            if (hiTail == null)
                                hiHead = e;
                            else
                                hiTail.next = e;
                            hiTail = e;
                        }
                    } while ((e = next) != null);
                    
                    // 将低位链表放到原位置
                    if (loTail != null) {
                        loTail.next = null;
                        newTab[j] = loHead;
                    }
                    // 将高位链表放到新位置（原位置 + oldCap）
                    if (hiTail != null) {
                        hiTail.next = null;
                        newTab[j + oldCap] = hiHead;
                    }
                }
            }
        }
    }
    
    return newTab;
}
```

## 扩容机制的核心优化

### 1. 位运算快速定位新位置

**JDK 1.7 的方式（重新计算）**：
```java
// 旧方式：每个元素都要重新计算 hash
int newIndex = hash % newCapacity;
```

**JDK 1.8 的优化（位运算判断）**：
```java
// 新方式：通过位运算快速判断
if ((e.hash & oldCap) == 0) {
    newIndex = oldIndex;          // 位置不变
} else {
    newIndex = oldIndex + oldCap; // 位置变化
}
```

**原理说明**：
```
假设 oldCap = 16 (0001 0000), newCap = 32 (0010 0000)

元素的旧位置: hash & (oldCap - 1) = hash & 0000 1111
元素的新位置: hash & (newCap - 1) = hash & 0001 1111

关键判断: hash & oldCap（即 hash 的第 5 位）
- 如果第 5 位 = 0: 新位置 = 旧位置
- 如果第 5 位 = 1: 新位置 = 旧位置 + 16

示例1: hash = 0000 0101 (5)
旧位置: 5 & 15 = 5
判断: 5 & 16 = 0 (第 5 位是 0)
新位置: 5 & 31 = 5 (不变)

示例2: hash = 0001 0101 (21)
旧位置: 21 & 15 = 5
判断: 21 & 16 = 16 (第 5 位是 1)
新位置: 21 & 31 = 21 = 5 + 16 (改变)
```

**性能优势**：
- 不需要重新计算 hash
- 只需一次位运算判断
- 时间复杂度从 O(n × hash计算) 降低到 O(n)

### 2. 高低位链表分离

**图示说明**：
```
扩容前 (oldCap = 16):
table[5] → A(5) → B(21) → C(37) → D(5)

扩容后 (newCap = 32):
判断每个节点的 hash & 16:
- A(5):  5 & 16 = 0   → 低位链表
- B(21): 21 & 16 = 16 → 高位链表
- C(37): 37 & 16 = 32 → 高位链表
- D(5):  5 & 16 = 0   → 低位链表

分离结果:
低位链表: A → D
高位链表: B → C

新数组:
table[5]  = A → D       (原位置)
table[21] = B → C       (原位置 + 16)
```

**代码实现**：
```java
// 构建低位链表和高位链表
Node<K,V> loHead = null, loTail = null;  // 低位链表（位置不变）
Node<K,V> hiHead = null, hiTail = null;  // 高位链表（位置改变）

do {
    next = e.next;
    if ((e.hash & oldCap) == 0) {
        // 低位链表（尾插法）
        if (loTail == null)
            loHead = e;
        else
            loTail.next = e;
        loTail = e;
    }
    else {
        // 高位链表（尾插法）
        if (hiTail == null)
            hiHead = e;
        else
            hiTail.next = e;
        hiTail = e;
    }
} while ((e = next) != null);

// 放置到新数组
newTab[j] = loHead;           // 原位置
newTab[j + oldCap] = hiHead;  // 新位置
```

**优势**：
- 保持原链表的相对顺序（JDK 1.7 的头插法会逆序）
- 一次遍历完成分离，效率高
- 避免了 JDK 1.7 的并发死循环问题

### 3. 红黑树的扩容处理

```java
final void split(HashMap<K,V> map, Node<K,V>[] tab, int index, int bit) {
    TreeNode<K,V> b = this;
    // 同样分为低位树和高位树
    TreeNode<K,V> loHead = null, loTail = null;
    TreeNode<K,V> hiHead = null, hiTail = null;
    int lc = 0, hc = 0;  // 统计节点数
    
    for (TreeNode<K,V> e = b, next; e != null; e = next) {
        next = (TreeNode<K,V>)e.next;
        e.next = null;
        
        if ((e.hash & bit) == 0) {
            // 低位树
            if ((e.prev = loTail) == null)
                loHead = e;
            else
                loTail.next = e;
            loTail = e;
            ++lc;
        }
        else {
            // 高位树
            if ((e.prev = hiTail) == null)
                hiHead = e;
            else
                hiTail.next = e;
            hiTail = e;
            ++hc;
        }
    }
    
    if (loHead != null) {
        // 如果低位树节点数 <= 6，退化为链表
        if (lc <= UNTREEIFY_THRESHOLD)
            tab[index] = loHead.untreeify(map);
        else {
            tab[index] = loHead;
            if (hiHead != null)
                loHead.treeify(tab);  // 重新树化
        }
    }
    if (hiHead != null) {
        // 如果高位树节点数 <= 6，退化为链表
        if (hc <= UNTREEIFY_THRESHOLD)
            tab[index + bit] = hiHead.untreeify(map);
        else {
            tab[index + bit] = hiHead;
            if (loHead != null)
                hiHead.treeify(tab);  // 重新树化
        }
    }
}
```

## 扩容性能分析

### 1. 时间复杂度

**扩容操作总时间复杂度：O(n)**
- 遍历所有元素：O(n)
- 位运算判断位置：O(1)
- 链表分离：O(链表长度)
- 红黑树处理：O(k log k)，k 为树节点数

### 2. 空间复杂度

**扩容过程的内存峰值**：
```
扩容前: oldCap × 空间
扩容中: oldCap × 空间 + newCap × 空间 = 3 × oldCap × 空间
扩容后: newCap × 空间 = 2 × oldCap × 空间

峰值出现在数据迁移过程中
```

### 3. 扩容次数计算

```java
public class ResizeCountTest {
    public static void main(String[] args) {
        // 默认容量 16，负载因子 0.75
        Map<Integer, String> map = new HashMap<>();
        
        int[] resizePoints = {13, 25, 49, 97, 193, 385, 769, 1537};
        
        for (int i = 0; i < 10000; i++) {
            map.put(i, "value" + i);
        }
        
        // 扩容次数 = log₂(10000/12) ≈ 10 次
        // 16 → 32 → 64 → 128 → 256 → 512 → 1024 → 2048 → 4096 → 8192 → 16384
    }
}
```

**公式**：
```
扩容次数 ≈ log₂(n / (初始容量 × 负载因子))

示例：插入 10000 个元素，初始容量 16
扩容次数 = log₂(10000 / 12) ≈ 9.7 ≈ 10 次
```

## 性能优化实践

### 1. 预估容量，减少扩容

```java
// ❌ 错误：频繁扩容
Map<Integer, String> map1 = new HashMap<>();
for (int i = 0; i < 10000; i++) {
    map1.put(i, "value" + i);
}
// 触发约 10 次扩容

// ✅ 正确：预估容量
int expectedSize = 10000;
int capacity = (int) (expectedSize / 0.75 + 1);
Map<Integer, String> map2 = new HashMap<>(capacity);
for (int i = 0; i < 10000; i++) {
    map2.put(i, "value" + i);
}
// 只触发 1 次或 0 次扩容
```

### 2. 容量计算工具方法

```java
public class HashMapUtils {
    /**
     * 根据预期元素数量计算初始容量
     * @param expectedSize 预期元素数量
     * @return 建议的初始容量
     */
    public static int calculateCapacity(int expectedSize) {
        return calculateCapacity(expectedSize, 0.75f);
    }
    
    public static int calculateCapacity(int expectedSize, float loadFactor) {
        if (expectedSize < 0) {
            throw new IllegalArgumentException("Expected size must be positive");
        }
        // 计算需要的容量
        int capacity = (int) Math.ceil(expectedSize / loadFactor);
        // 向上取 2 的幂次方
        return tableSizeFor(capacity);
    }
    
    private static int tableSizeFor(int cap) {
        int n = cap - 1;
        n |= n >>> 1;
        n |= n >>> 2;
        n |= n >>> 4;
        n |= n >>> 8;
        n |= n >>> 16;
        return (n < 0) ? 1 : (n >= (1 << 30)) ? (1 << 30) : n + 1;
    }
    
    public static void main(String[] args) {
        System.out.println(calculateCapacity(100));   // 128
        System.out.println(calculateCapacity(1000));  // 2048
        System.out.println(calculateCapacity(10000)); // 16384
    }
}
```

### 3. 监控扩容性能

```java
public class ResizePerformanceMonitor {
    public static void main(String[] args) throws Exception {
        int[] sizes = {100, 1000, 10000, 100000};
        
        for (int size : sizes) {
            testResize(size, false);  // 不预设容量
            testResize(size, true);   // 预设容量
            System.out.println("---");
        }
    }
    
    static void testResize(int size, boolean presize) throws Exception {
        Map<Integer, String> map = presize 
            ? new HashMap<>((int)(size / 0.75 + 1))
            : new HashMap<>();
        
        int resizeCount = 0;
        int lastCapacity = 0;
        
        long start = System.nanoTime();
        
        for (int i = 0; i < size; i++) {
            map.put(i, "value" + i);
            
            int currentCapacity = getCapacity(map);
            if (currentCapacity > lastCapacity) {
                resizeCount++;
                lastCapacity = currentCapacity;
            }
        }
        
        long end = System.nanoTime();
        
        System.out.printf("大小: %6d, 预设容量: %5s, 扩容次数: %2d, 耗时: %6d ms%n",
            size, presize, resizeCount, (end - start) / 1_000_000);
    }
    
    static int getCapacity(Map<?, ?> map) throws Exception {
        java.lang.reflect.Field tableField = HashMap.class.getDeclaredField("table");
        tableField.setAccessible(true);
        Object[] table = (Object[]) tableField.get(map);
        return table == null ? 0 : table.length;
    }
}
```

**输出示例**：
```
大小:    100, 预设容量: false, 扩容次数:  4, 耗时:     2 ms
大小:    100, 预设容量:  true, 扩容次数:  0, 耗时:     1 ms
---
大小:   1000, 预设容量: false, 扩容次数:  7, 耗时:     5 ms
大小:   1000, 预设容量:  true, 扩容次数:  0, 耗时:     2 ms
---
大小:  10000, 预设容量: false, 扩容次数: 10, 耗时:    15 ms
大小:  10000, 预设容量:  true, 扩容次数:  0, 耗时:     8 ms
```

## JDK 1.7 vs JDK 1.8 扩容对比

| 对比项 | JDK 1.7 | JDK 1.8 |
|--------|---------|---------|
| 插入方式 | 头插法 | 尾插法 |
| 位置计算 | 重新计算 hash | 位运算判断 |
| 元素顺序 | 扩容后逆序 | 保持原顺序 |
| 并发问题 | 可能死循环 | 不会死循环（但仍不安全） |
| 性能 | 较慢 | 更快 |

## 面试答题总结

**答题要点**：
1. **触发条件**：size > capacity × loadFactor（默认 0.75）
2. **扩容倍数**：容量翻倍（2 倍）
3. **核心流程**：计算新容量 → 创建新数组 → 数据迁移
4. **JDK 1.8 优化**：位运算快速定位、高低位链表分离、尾插法

**加分项**：
- 详细说明位运算优化原理（hash & oldCap）
- 对比 JDK 1.7 和 1.8 的扩容差异
- 提到红黑树扩容时的退化机制
- 给出预估容量的计算公式
- 说明扩容的时间和空间复杂度

**一句话总结**：HashMap 通过容量翻倍、位运算优化和高低位链表分离实现高效扩容，建议预估容量以避免频繁扩容。

