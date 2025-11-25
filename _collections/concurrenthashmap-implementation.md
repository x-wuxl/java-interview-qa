---
title: "ConcurrentHashMap是如何实现的？"
date: 2025-11-02
description: "详解ConcurrentHashMap的实现原理，包括JDK1.8的数组+链表/红黑树结构、CAS+synchronized锁机制，以及分段锁到Node级别锁的演进"
author: "wuxl"
categories: [集合框架, 并发编程]
tags: [ConcurrentHashMap, 并发集合, 线程安全, CAS, synchronized]
nav_order: 98
parent: 集合框架
---
## 问题

ConcurrentHashMap是如何实现的？

## 答案

### 一、核心概念

ConcurrentHashMap 是 Java 并发包中提供的**线程安全的哈希表**实现，它在保证线程安全的同时，提供了比 Hashtable 和 Collections.synchronizedMap 更高的并发性能。

### 二、JDK 1.8 实现原理（主流版本）

#### 1. 数据结构

```java
// 核心字段
transient volatile Node<K,V>[] table;  // 哈希表数组
private transient volatile int sizeCtl; // 控制标识符，负数表示正在初始化或扩容

static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;
    final K key;
    volatile V val;      // volatile保证可见性
    volatile Node<K,V> next;
}
```

采用**数组 + 链表 + 红黑树**结构：
- 数组：存储 Node 节点
- 链表：hash 冲突时，长度小于 8 使用链表
- 红黑树：链表长度达到 8 且数组长度 ≥ 64 时转换为红黑树

#### 2. 锁机制：CAS + synchronized

```java
final V putVal(K key, V value, boolean onlyIfAbsent) {
    // ...
    for (Node<K,V>[] tab = table;;) {
        if ((f = tabAt(tab, i = (n - 1) & hash)) == null) {
            // 位置为空，使用CAS无锁插入
            if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value)))
                break;
        } else {
            // 位置有元素，使用synchronized锁住该位置（Node节点）
            synchronized (f) {
                // 链表或红黑树插入逻辑
                // ...
            }
        }
    }
}
```

**关键点**：
- **CAS 无锁操作**：当桶位为空时，使用 CAS 直接插入，避免加锁
- **synchronized 锁粒度**：锁的是数组中的**单个 Node 节点**（首节点），而不是整个数组
- **锁分离**：不同桶位的操作互不影响，支持高并发

#### 3. get 操作无锁

```java
public V get(Object key) {
    Node<K,V>[] tab; Node<K,V> e;
    int h = spread(key.hashCode());
    if ((tab = table) != null && (e = tabAt(tab, (tab.length - 1) & h)) != null) {
        // 通过volatile读取，无需加锁
        // ...
    }
    return null;
}
```

**原因**：
- `Node.val` 和 `Node.next` 都是 volatile 修饰，保证可见性
- 读操作不会修改数据，可安全并发读取

#### 4. 扩容机制

```java
private final void transfer(Node<K,V>[] tab, Node<K,V>[] nextTab) {
    // 支持多线程协作扩容
    // 每个线程负责一段数组的迁移
}
```

**特点**：
- **多线程协作扩容**：多个线程可以同时参与扩容，提高效率
- **ForwardingNode 标记**：已迁移的桶位用 ForwardingNode 占位，指向新数组

### 三、JDK 1.7 对比（面试补充）

JDK 1.7 采用**分段锁（Segment）**：
```java
// JDK 1.7 结构
Segment<K,V>[] segments;  // 默认16个Segment

static class Segment<K,V> extends ReentrantLock { // 继承锁
    transient HashEntry<K,V>[] table;
}
```

**缺点**：
- 最大并发度受限于 Segment 数量（默认16）
- 锁粒度较粗，多个桶位共享一把锁

### 四、性能优化与线程安全保证

1. **volatile + CAS**：保证可见性和原子性，减少锁竞争
2. **锁粒度细化**：从 Segment 级别降低到 Node 级别
3. **读操作无锁**：利用 volatile 特性，提升并发读性能
4. **红黑树优化**：避免极端情况下链表过长导致性能下降

### 五、答题总结

ConcurrentHashMap（JDK 1.8）通过以下方式实现高效并发：

1. **数据结构**：数组 + 链表 / 红黑树，与 HashMap 类似
2. **锁机制**：CAS（空桶位）+ synchronized（有冲突时锁 Node）
3. **锁粒度**：细化到数组单个元素级别，支持更高并发
4. **读操作**：利用 volatile 实现无锁读取
5. **扩容**：支持多线程协作扩容

相比 JDK 1.7 的分段锁，1.8 版本提升了并发度，降低了锁竞争，性能更优。
