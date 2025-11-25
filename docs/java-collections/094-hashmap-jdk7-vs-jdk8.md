---
layout: default
title: "HashMap在JDK1.7和1.8中的区别"
parent: 集合框架
nav_order: 94
description: "详细对比HashMap在JDK 1.7和JDK 1.8中的实现差异，包括数据结构、插入方式、扩容机制等"
date: 2025-11-02
---
## 核心概念

HashMap 在 JDK 1.7 和 1.8 之间有**重大改进**，主要体现在数据结构优化、性能提升和并发安全性改善等方面。这些改进使得 HashMap 在处理大量数据和哈希冲突时表现更好。

## 主要区别对比

### 1. 数据结构

| 对比项 | JDK 1.7 | JDK 1.8 |
|--------|---------|---------|
| 底层结构 | **数组 + 链表** | **数组 + 链表 + 红黑树** |
| 冲突处理 | 链表（无优化） | 链表 → 红黑树（优化） |
| 最坏时间复杂度 | O(n) | O(log n) |

```java
// JDK 1.7：只有链表
static class Entry<K,V> implements Map.Entry<K,V> {
    final K key;
    V value;
    Entry<K,V> next;  // 单向链表
    int hash;
}

// JDK 1.8：链表 + 红黑树
static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;
    final K key;
    V value;
    Node<K,V> next;
}

static final class TreeNode<K,V> extends LinkedHashMap.Entry<K,V> {
    TreeNode<K,V> parent;
    TreeNode<K,V> left;
    TreeNode<K,V> right;
    boolean red;
    // ...
}
```

### 2. 插入方式

**JDK 1.7：头插法（存在并发死循环风险）**

```java
void addEntry(int hash, K key, V value, int bucketIndex) {
    Entry<K,V> e = table[bucketIndex];
    // 新节点指向旧的头节点（头插法）
    table[bucketIndex] = new Entry<>(hash, key, value, e);
    if (size++ >= threshold)
        resize(2 * table.length);
}
```

**JDK 1.8：尾插法（避免死循环）**

```java
final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    // ...
    for (int binCount = 0; ; ++binCount) {
        if ((e = p.next) == null) {
            p.next = newNode(hash, key, value, null);  // 尾插法
            if (binCount >= TREEIFY_THRESHOLD - 1)
                treeifyBin(tab, hash);  // 可能树化
            break;
        }
        // ...
    }
}
```

**为什么改为尾插法？**
- 头插法在并发扩容时可能形成环形链表，导致 CPU 100%
- 尾插法保持原有顺序，避免了这个问题

### 3. 扩容机制

**JDK 1.7：重新计算所有元素的位置**

```java
void transfer(Entry[] newTable) {
    Entry[] src = table;
    for (int j = 0; j < src.length; j++) {
        Entry<K,V> e = src[j];
        if (e != null) {
            src[j] = null;
            do {
                Entry<K,V> next = e.next;
                int i = indexFor(e.hash, newTable.length);  // 重新计算
                e.next = newTable[i];  // 头插法
                newTable[i] = e;
                e = next;
            } while (e != null);
        }
    }
}
```

**JDK 1.8：优化的位置计算**

```java
final Node<K,V>[] resize() {
    // ...
    for (int j = 0; j < oldCap; ++j) {
        Node<K,V> e;
        if ((e = oldTab[j]) != null) {
            // ...
            if (e.next == null)
                newTab[e.hash & (newCap - 1)] = e;
            else {
                Node<K,V> loHead = null, loTail = null;  // 低位链表
                Node<K,V> hiHead = null, hiTail = null;  // 高位链表
                do {
                    if ((e.hash & oldCap) == 0) {
                        // 位置不变，放入低位链表
                        if (loTail == null)
                            loHead = e;
                        else
                            loTail.next = e;
                        loTail = e;
                    } else {
                        // 位置 = 原位置 + oldCap，放入高位链表
                        if (hiTail == null)
                            hiHead = e;
                        else
                            hiTail.next = e;
                        hiTail = e;
                    }
                } while ((e = e.next) != null);
                
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
```

**优化点**：
- 通过 `(e.hash & oldCap) == 0` 判断元素位置
- 只有两种可能：原位置 或 原位置+oldCap
- 避免了重新计算 hash，提升性能

### 4. Hash 计算

**JDK 1.7：多次扰动**

```java
final int hash(Object k) {
    int h = hashSeed;
    if (0 != h && k instanceof String) {
        return sun.misc.Hashing.stringHash32((String) k);
    }
    h ^= k.hashCode();
    // 四次扰动
    h ^= (h >>> 20) ^ (h >>> 12);
    return h ^ (h >>> 7) ^ (h >>> 4);
}
```

**JDK 1.8：简化的扰动**

```java
static final int hash(Object key) {
    int h;
    // 高16位异或低16位
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}
```

**优化原因**：
- 红黑树的引入已经优化了冲突场景
- 简化 hash 计算可以提升性能
- 高低位异或保证了 hash 分布的均匀性

### 5. 树化与退化

**JDK 1.8 新增机制**：

```java
static final int TREEIFY_THRESHOLD = 8;     // 树化阈值
static final int UNTREEIFY_THRESHOLD = 6;   // 退化阈值
static final int MIN_TREEIFY_CAPACITY = 64; // 最小树化容量

final void treeifyBin(Node<K,V>[] tab, int hash) {
    int n, index; Node<K,V> e;
    if (tab == null || (n = tab.length) < MIN_TREEIFY_CAPACITY)
        resize();  // 容量不足，先扩容
    else if ((e = tab[index = (n - 1) & hash]) != null) {
        // 转换为红黑树
    }
}
```

**触发条件**：
1. 链表长度 ≥ 8
2. 数组容量 ≥ 64

### 6. 性能对比

| 场景 | JDK 1.7 | JDK 1.8 | 提升 |
|------|---------|---------|------|
| 哈希分布均匀 | O(1) | O(1) | 持平 |
| 大量哈希冲突 | O(n) | O(log n) | **显著提升** |
| 扩容操作 | 较慢 | 更快 | 位运算优化 |
| 并发扩容 | 可能死循环 | 数据丢失但不死循环 | 安全性提升 |

## 完整对比表

| 对比项 | JDK 1.7 | JDK 1.8 |
|--------|---------|---------|
| 数据结构 | 数组+链表 | 数组+链表+红黑树 |
| 插入方式 | 头插法 | 尾插法 |
| Hash计算 | 4次扰动 | 1次扰动（高低位异或） |
| 扩容rehash | 全部重新计算 | 位运算判断位置 |
| 树化机制 | 无 | 链表长度≥8且容量≥64 |
| 最坏查询 | O(n) | O(log n) |
| 并发问题 | 可能死循环 | 数据不一致但不死循环 |

## 示例对比

```java
public class HashMapTest {
    public static void main(String[] args) {
        Map<Integer, String> map = new HashMap<>();
        
        // 构造大量哈希冲突的场景
        for (int i = 0; i < 10000; i++) {
            // 假设这些 key 的 hash 都映射到同一个桶
            map.put(new HashCollisionKey(i), "value" + i);
        }
        
        long start = System.nanoTime();
        map.get(new HashCollisionKey(9999));
        long end = System.nanoTime();
        
        System.out.println("查询耗时: " + (end - start) + "ns");
        // JDK 1.7: 链表遍历，耗时较长
        // JDK 1.8: 红黑树查找，耗时更短
    }
    
    static class HashCollisionKey {
        int value;
        HashCollisionKey(int value) { this.value = value; }
        
        @Override
        public int hashCode() {
            return 1;  // 故意让所有 key 的 hash 都相同
        }
        
        @Override
        public boolean equals(Object obj) {
            if (obj instanceof HashCollisionKey) {
                return this.value == ((HashCollisionKey) obj).value;
            }
            return false;
        }
    }
}
```

## 面试答题总结

**答题要点**：
1. **数据结构**：1.7 是数组+链表，1.8 增加了红黑树
2. **插入方式**：1.7 头插法，1.8 尾插法（避免并发死循环）
3. **性能优化**：1.8 在哈希冲突时从 O(n) 优化到 O(log n)
4. **扩容优化**：1.8 通过位运算快速定位新位置

**加分项**：
- 说明 1.7 并发死循环的原理
- 解释为什么链表长度是 8 时树化
- 对比 hash 函数的演进
- 提到扩容时的高低位链表优化

