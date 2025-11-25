---
layout: default
title: "ConcurrentHashMap在JDK1.7和1.8中有什么不同？"
parent: 集合框架
nav_order: 99
description: "对比分析ConcurrentHashMap在JDK1.7和1.8版本的核心差异，包括数据结构、锁机制、并发度等方面的演进优化"
author: "wuxl"
date: 2025-11-02
---
## 问题

ConcurrentHashMap在JDK1.7和1.8中有什么不同？

## 答案

### 一、核心差异对比表

| 对比维度 | JDK 1.7 | JDK 1.8 |
|---------|---------|---------|
| **数据结构** | Segment数组 + HashEntry数组 + 链表 | Node数组 + 链表 + 红黑树 |
| **锁机制** | ReentrantLock 分段锁 | CAS + synchronized |
| **锁粒度** | Segment级别（粗） | Node节点级别（细） |
| **最大并发度** | Segment数量（默认16） | 数组长度（理论上无上限） |
| **扩容方式** | 单线程扩容 | 多线程协作扩容 |
| **查询性能** | O(n) 最坏情况 | O(log n) 红黑树优化 |

### 二、JDK 1.7 实现

#### 1. 数据结构

```java
// 分段锁结构
final Segment<K,V>[] segments;  // Segment数组

static final class Segment<K,V> extends ReentrantLock {
    transient volatile HashEntry<K,V>[] table;  // 每个Segment包含一个HashEntry数组
    transient int count;
}

static final class HashEntry<K,V> {
    final int hash;
    final K key;
    volatile V value;
    volatile HashEntry<K,V> next;
}
```

**特点**：
- 整个 ConcurrentHashMap 分为多个 **Segment**（默认16个）
- 每个 Segment 相当于一个小的 HashMap
- Segment 继承 **ReentrantLock**，本身就是一把锁

#### 2. 锁机制

```java
public V put(K key, V value) {
    Segment<K,V> s;
    // 1. 定位到具体的Segment
    int hash = hash(key);
    int j = (hash >>> segmentShift) & segmentMask;
    s = ensureSegment(j);

    // 2. 在Segment内部加锁
    return s.put(key, hash, value, false);
}

final V put(K key, int hash, V value, boolean onlyIfAbsent) {
    // 尝试获取锁，失败则自旋尝试
    HashEntry<K,V> node = tryLock() ? null : scanAndLockForPut(key, hash, value);
    // 获取锁后进行插入操作
    // ...
}
```

**缺点**：
- 并发度受限于 Segment 数量
- 不同的 key 可能落在同一个 Segment，产生锁竞争

### 三、JDK 1.8 实现

#### 1. 数据结构

```java
// 直接使用Node数组，类似HashMap
transient volatile Node<K,V>[] table;

static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;
    final K key;
    volatile V val;
    volatile Node<K,V> next;
}

// 红黑树节点
static final class TreeNode<K,V> extends Node<K,V> {
    TreeNode<K,V> parent;
    TreeNode<K,V> left;
    TreeNode<K,V> right;
    // ...
}
```

**改进**：
- 取消 Segment 分段设计
- 链表长度 ≥ 8 且数组长度 ≥ 64 时转红黑树

#### 2. 锁机制

```java
final V putVal(K key, V value, boolean onlyIfAbsent) {
    for (Node<K,V>[] tab = table;;) {
        Node<K,V> f; int n, i, fh;
        if (tab == null || (n = tab.length) == 0)
            tab = initTable();  // 初始化
        else if ((f = tabAt(tab, i = (n - 1) & hash)) == null) {
            // CAS插入，不加锁
            if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value)))
                break;
        } else {
            // synchronized锁住数组中的Node节点
            synchronized (f) {
                if (tabAt(tab, i) == f) {
                    // 链表或红黑树插入
                }
            }
        }
    }
}
```

**优势**：
- **CAS 操作**：桶位为空时，无锁插入，性能更高
- **synchronized 优化**：JDK 1.6 后 synchronized 性能大幅提升（锁升级机制）
- **锁粒度更细**：锁的是数组索引位置，而非整个 Segment

### 四、关键改进点分析

#### 1. 并发度提升

```java
// JDK 1.7：最大并发度 = Segment数量（默认16）
// 16个线程同时操作不同Segment才能完全并发

// JDK 1.8：最大并发度 = 数组长度
// 理论上数组有多长，就能支持多少并发操作
```

#### 2. 扩容优化

```java
// JDK 1.7：单线程扩容
// 某个Segment扩容时，其他线程访问该Segment会阻塞

// JDK 1.8：多线程协作扩容
private final void transfer(Node<K,V>[] tab, Node<K,V>[] nextTab) {
    // 多个线程可以同时迁移数据
    // 使用ForwardingNode标记已迁移的桶位
}
```

#### 3. 内存占用

- **JDK 1.7**：即使元素很少，也需要初始化所有 Segment
- **JDK 1.8**：延迟初始化，更节省内存

### 五、性能对比

1. **高并发场景**：JDK 1.8 的细粒度锁性能更优
2. **低冲突场景**：JDK 1.8 的 CAS 操作减少锁开销
3. **查询性能**：JDK 1.8 的红黑树避免极端情况下的 O(n) 查询

### 六、答题总结

JDK 1.7 → JDK 1.8 的主要变化：

1. **取消分段锁**：Segment 数组 + ReentrantLock → Node 数组 + synchronized
2. **锁粒度优化**：Segment 级别 → Node 节点级别
3. **引入红黑树**：链表过长时转红黑树，提升查询性能
4. **引入 CAS**：空桶位插入使用 CAS，减少锁竞争
5. **协作扩容**：支持多线程同时参与扩容，效率更高
6. **并发度提升**：从固定的 Segment 数量提升到数组长度

总体而言，JDK 1.8 版本在**并发性能、扩展性、内存占用**等方面都有显著提升。
