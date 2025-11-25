---
layout: default
title: "HashMap什么时候扩容？"
parent: 集合框架
nav_order: 90
description: "详解HashMap扩容的触发时机、扩容过程及性能优化建议"
date: 2025-11-02
---
## 核心概念

HashMap 的**扩容（resize）** 是指当元素数量超过一定阈值时，自动将底层数组容量扩大为原来的 **2 倍**，并重新分配所有元素位置的过程。这是保证 HashMap 性能的重要机制。

## 扩容触发时机

### 1. 元素数量超过阈值

**主要触发条件**：
```java
if (++size > threshold)
    resize();
```

**阈值计算**：
```java
threshold = capacity × loadFactor
```

**示例**：
```java
// 默认情况
HashMap<String, Object> map = new HashMap<>();
// capacity = 16（默认初始容量）
// loadFactor = 0.75（默认负载因子）
// threshold = 16 × 0.75 = 12

// 插入第 13 个元素时触发扩容
for (int i = 0; i < 13; i++) {
    map.put("key" + i, i);
    if (i == 12) {
        // 此时触发扩容：capacity 从 16 变为 32
    }
}
```

### 2. 初始化时

**首次 put 操作**：
```java
final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    Node<K,V>[] tab; Node<K,V> p; int n, i;
    
    // 首次插入时，table 为 null，触发初始化扩容
    if ((tab = table) == null || (n = tab.length) == 0)
        n = (tab = resize()).length;  // ← 初始化扩容
    
    // ...
}
```

**场景说明**：
```java
// 创建 HashMap 时并不会立即分配数组空间
HashMap<String, Object> map = new HashMap<>();  // table = null

// 第一次 put 时才会初始化数组
map.put("key1", "value1");  // 触发 resize()，创建容量为 16 的数组
```

### 3. 树化前的容量检查

**链表转红黑树前的判断**：
```java
final void treeifyBin(Node<K,V>[] tab, int hash) {
    int n, index; Node<K,V> e;
    
    // 如果数组容量小于 64，优先扩容而不是树化
    if (tab == null || (n = tab.length) < MIN_TREEIFY_CAPACITY)
        resize();  // ← 扩容而不是树化
    else if ((e = tab[index = (n - 1) & hash]) != null) {
        // 容量 >= 64 时才树化
        // ...
    }
}
```

**触发条件**：
```java
static final int TREEIFY_THRESHOLD = 8;       // 链表转树阈值
static final int MIN_TREEIFY_CAPACITY = 64;   // 最小树化容量

// 场景：链表长度达到 8，但数组容量 < 64
HashMap<String, Object> map = new HashMap<>(8);
// capacity = 8, threshold = 6

// 构造 hash 冲突，让所有元素都在同一个桶
for (int i = 0; i < 8; i++) {
    map.put(new HashCollisionKey(i), "value" + i);
}
// 链表长度达到 8，但 capacity = 8 < 64
// 触发扩容到 16，而不是树化
```

## 扩容过程详解

### 完整源码流程

```java
final Node<K,V>[] resize() {
    Node<K,V>[] oldTab = table;
    int oldCap = (oldTab == null) ? 0 : oldTab.length;
    int oldThr = threshold;
    int newCap, newThr = 0;
    
    // 1. 计算新容量和新阈值
    if (oldCap > 0) {
        if (oldCap >= MAXIMUM_CAPACITY) {
            // 已达最大容量，不再扩容
            threshold = Integer.MAX_VALUE;
            return oldTab;
        }
        else if ((newCap = oldCap << 1) < MAXIMUM_CAPACITY &&
                 oldCap >= DEFAULT_INITIAL_CAPACITY)
            // 容量和阈值都翻倍
            newThr = oldThr << 1;
    }
    else if (oldThr > 0)
        newCap = oldThr;
    else {
        // 初始化：使用默认值
        newCap = DEFAULT_INITIAL_CAPACITY;  // 16
        newThr = (int)(DEFAULT_LOAD_FACTOR * DEFAULT_INITIAL_CAPACITY);  // 12
    }
    
    if (newThr == 0) {
        float ft = (float)newCap * loadFactor;
        newThr = (newCap < MAXIMUM_CAPACITY && ft < (float)MAXIMUM_CAPACITY ?
                  (int)ft : Integer.MAX_VALUE);
    }
    
    threshold = newThr;
    
    // 2. 创建新数组
    @SuppressWarnings({"rawtypes","unchecked"})
    Node<K,V>[] newTab = (Node<K,V>[])new Node[newCap];
    table = newTab;
    
    // 3. 数据迁移
    if (oldTab != null) {
        for (int j = 0; j < oldCap; ++j) {
            Node<K,V> e;
            if ((e = oldTab[j]) != null) {
                oldTab[j] = null;  // 释放旧引用
                
                if (e.next == null)
                    // 单个节点，直接放到新位置
                    newTab[e.hash & (newCap - 1)] = e;
                else if (e instanceof TreeNode)
                    // 红黑树节点，特殊处理
                    ((TreeNode<K,V>)e).split(this, newTab, j, oldCap);
                else {
                    // 链表节点，优化分配
                    Node<K,V> loHead = null, loTail = null;  // 低位链表
                    Node<K,V> hiHead = null, hiTail = null;  // 高位链表
                    Node<K,V> next;
                    
                    do {
                        next = e.next;
                        if ((e.hash & oldCap) == 0) {
                            // 位置不变，放入低位链表
                            if (loTail == null)
                                loHead = e;
                            else
                                loTail.next = e;
                            loTail = e;
                        }
                        else {
                            // 位置变化，放入高位链表
                            if (hiTail == null)
                                hiHead = e;
                            else
                                hiTail.next = e;
                            hiTail = e;
                        }
                    } while ((e = next) != null);
                    
                    if (loTail != null) {
                        loTail.next = null;
                        newTab[j] = loHead;  // 原位置
                    }
                    if (hiTail != null) {
                        hiTail.next = null;
                        newTab[j + oldCap] = hiHead;  // 原位置 + oldCap
                    }
                }
            }
        }
    }
    return newTab;
}
```

### 扩容步骤总结

```
步骤1: 计算新容量
oldCap = 16  →  newCap = 32 (翻倍)
oldThr = 12  →  newThr = 24 (翻倍)

步骤2: 创建新数组
new Node[32]

步骤3: 数据迁移
┌─────────────┐
│ 旧数组[16]   │
├─────────────┤
│ index 0     │ ─────┐
│ index 1     │      │
│ ...         │      │  重新分配
│ index 5     │      │
│  A→B→C      │ ─────┤
│ ...         │      │
└─────────────┘      │
                     ↓
┌─────────────┐
│ 新数组[32]   │
├─────────────┤
│ index 5     │ ← A (位置不变)
│ ...         │
│ index 21    │ ← B, C (5 + 16)
│ ...         │
└─────────────┘
```

## 扩容性能分析

### 1. 时间复杂度

**扩容操作**：O(n)
- 需要遍历所有元素
- 重新计算位置（JDK 1.8 优化为位运算判断）

**频繁扩容的影响**：
```java
// 错误示例：频繁扩容
Map<Integer, String> map = new HashMap<>();  // 默认容量 16
for (int i = 0; i < 10000; i++) {
    map.put(i, "value" + i);
}
// 触发扩容：16→32→64→128→256→512→1024→2048→4096→8192→16384
// 共 10 次扩容，每次都需要 O(n) 时间

// 正确示例：预估容量
int expectedSize = 10000;
int capacity = (int) (expectedSize / 0.75 + 1);
Map<Integer, String> map2 = new HashMap<>(capacity);
for (int i = 0; i < 10000; i++) {
    map2.put(i, "value" + i);
}
// 只触发 1 次扩容（或不扩容）
```

### 2. 内存开销

**扩容过程中的内存峰值**：
```
扩容前: capacity = 1024，占用内存 M
扩容中: 旧数组(1024) + 新数组(2048)，占用内存 ≈ 3M
扩容后: capacity = 2048，占用内存 2M
```

**建议**：
```java
// 如果内存敏感，可以提高负载因子，减少扩容
Map<String, Object> map = new HashMap<>(1024, 0.9f);
// threshold = 1024 × 0.9 = 921，更晚触发扩容
```

## 实战建议

### 1. 预估容量，避免扩容

```java
public class HashMapSizeCalculator {
    public static int calculateInitialCapacity(int expectedSize) {
        // 公式：(expectedSize / loadFactor) + 1
        return (int) (expectedSize / 0.75f) + 1;
    }
    
    public static void main(String[] args) {
        // 已知要存储 1000 个元素
        int capacity = calculateInitialCapacity(1000);
        Map<Integer, String> map = new HashMap<>(capacity);
        
        // 插入 1000 个元素不会触发扩容
        for (int i = 0; i < 1000; i++) {
            map.put(i, "value" + i);
        }
    }
}
```

### 2. 监控扩容次数

```java
public class ResizeMonitor {
    public static void main(String[] args) throws Exception {
        Map<Integer, String> map = new HashMap<>();
        
        for (int i = 0; i < 20; i++) {
            map.put(i, "value" + i);
            int capacity = getCapacity(map);
            System.out.println("元素数: " + map.size() + ", 容量: " + capacity);
        }
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
元素数: 1, 容量: 16    ← 初始化
元素数: 2, 容量: 16
...
元素数: 12, 容量: 16
元素数: 13, 容量: 32   ← 第1次扩容（超过 threshold=12）
...
元素数: 20, 容量: 32
```

### 3. 特殊场景优化

```java
// 场景1：数据量巨大，内存紧张
Map<String, Object> map1 = new HashMap<>(1024, 0.95f);
// 更高的负载因子，减少内存占用

// 场景2：频繁查询，性能优先
Map<String, Object> map2 = new HashMap<>(2048, 0.5f);
// 更低的负载因子，减少哈希冲突

// 场景3：数据量已知（最佳实践）
int knownSize = 5000;
Map<String, Object> map3 = new HashMap<>((int)(knownSize / 0.75 + 1));
// 一次性分配足够空间
```

## 面试答题总结

**答题要点**：
1. **主要触发时机**：元素数量超过阈值（capacity × loadFactor）
2. **初始化时机**：首次 put 操作时分配数组空间
3. **树化前检查**：链表长度≥8 但容量<64 时，优先扩容
4. **扩容过程**：容量翻倍，重新分配所有元素，时间复杂度 O(n)

**加分项**：
- 说明 JDK 1.8 扩容时的位运算优化（高低位链表）
- 给出容量计算公式：`(expectedSize / 0.75) + 1`
- 提到扩容的性能开销和优化建议
- 解释为什么容量 < 64 时优先扩容而不是树化

**一句话总结**：当 `size > capacity × 0.75` 时触发扩容，容量翻倍，建议预估容量以避免频繁扩容。

