---
layout: post
title: "LinkedHashMap是如何实现的？"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [LinkedHashMap, HashMap, 双向链表, LRU, 有序Map]
description: "深入解析 LinkedHashMap 的实现原理，包括双向链表维护访问顺序、LRU 缓存实现机制以及源码关键设计"
---

## 核心概念

**LinkedHashMap** 是 HashMap 的子类，在 HashMap 的基础上增加了**双向链表**，维护元素的**插入顺序**或**访问顺序**。

```java
public class LinkedHashMap<K,V> extends HashMap<K,V> implements Map<K,V>
```

**核心特性**：
- 继承 HashMap 的所有特性（数组 + 链表 + 红黑树）
- 额外维护一条贯穿所有节点的双向链表
- 支持两种顺序模式：插入顺序（默认）和访问顺序
- 迭代性能与元素数量相关，而非容量（优于 HashMap）

---

## 底层数据结构

### 1. 节点定义

LinkedHashMap 使用 `Entry` 继承自 HashMap 的 `Node`，增加了前后指针：

```java
static class Entry<K,V> extends HashMap.Node<K,V> {
    Entry<K,V> before, after;  // 双向链表指针
    Entry(int hash, K key, V value, Node<K,V> next) {
        super(hash, key, value, next);
    }
}
```

**数据结构示意**：
```
HashMap 的桶数组（用于快速查找）
┌─────┬─────┬─────┬─────┐
│ [0] │ [1] │ [2] │ [3] │
└──┬──┴─────┴──┬──┴─────┘
   │           │
   ↓           ↓
 Entry1      Entry3
   ↓
 Entry2

双向链表（维护顺序）
head → Entry1 ⇄ Entry2 ⇄ Entry3 → tail
```

---

### 2. 关键字段

```java
public class LinkedHashMap<K,V> extends HashMap<K,V> {
    // 双向链表的头节点（最老的元素）
    transient LinkedHashMap.Entry<K,V> head;
    
    // 双向链表的尾节点（最新的元素）
    transient LinkedHashMap.Entry<K,V> tail;
    
    // 顺序模式：false=插入顺序（默认），true=访问顺序
    final boolean accessOrder;
}
```

---

## 核心实现原理

### 1. 插入操作（维护插入顺序）

LinkedHashMap 重写了 HashMap 的节点创建方法：

```java
// 创建新节点
Node<K,V> newNode(int hash, K key, V value, Node<K,V> e) {
    LinkedHashMap.Entry<K,V> p = 
        new LinkedHashMap.Entry<>(hash, key, value, e);
    linkNodeLast(p);  // 链接到双向链表尾部
    return p;
}

// 将节点添加到链表尾部
private void linkNodeLast(LinkedHashMap.Entry<K,V> p) {
    LinkedHashMap.Entry<K,V> last = tail;
    tail = p;
    if (last == null)
        head = p;
    else {
        p.before = last;
        last.after = p;
    }
}
```

---

### 2. 访问顺序模式（LRU 基础）

构造方法指定 `accessOrder = true` 时，每次 `get/put` 会将访问的节点移到链表尾部：

```java
public V get(Object key) {
    Node<K,V> e;
    if ((e = getNode(hash(key), key)) == null)
        return null;
    if (accessOrder)
        afterNodeAccess(e);  // 移到链表尾部
    return e.value;
}

void afterNodeAccess(Node<K,V> e) {
    LinkedHashMap.Entry<K,V> last;
    // 如果节点不是尾节点，移到尾部
    if (accessOrder && (last = tail) != e) {
        LinkedHashMap.Entry<K,V> p = (LinkedHashMap.Entry<K,V>)e;
        LinkedHashMap.Entry<K,V> b = p.before, a = p.after;
        p.after = null;
        // 从原位置移除
        if (b == null)
            head = a;
        else
            b.after = a;
        if (a != null)
            a.before = b;
        else
            last = b;
        // 链接到尾部
        if (last == null)
            head = p;
        else {
            p.before = last;
            last.after = p;
        }
        tail = p;
    }
}
```

---

### 3. 删除最老元素（LRU 淘汰策略）

LinkedHashMap 提供了钩子方法，可在插入后判断是否删除最老元素：

```java
void afterNodeInsertion(boolean evict) {
    LinkedHashMap.Entry<K,V> first;
    // 如果需要删除最老元素（头节点）
    if (evict && (first = head) != null && removeEldestEntry(first)) {
        K key = first.key;
        removeNode(hash(key), key, null, false, true);
    }
}

// 钩子方法，默认返回 false（不删除）
protected boolean removeEldestEntry(Map.Entry<K,V> eldest) {
    return false;
}
```

---

## 实现 LRU 缓存

利用 LinkedHashMap 的访问顺序模式实现 LRU 缓存：

```java
public class LRUCache<K, V> extends LinkedHashMap<K, V> {
    private final int capacity;

    public LRUCache(int capacity) {
        // 参数：初始容量、负载因子、访问顺序模式
        super(capacity, 0.75f, true);
        this.capacity = capacity;
    }

    @Override
    protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
        return size() > capacity;  // 超过容量时删除最老元素
    }
}

// 使用示例
LRUCache<String, String> cache = new LRUCache<>(3);
cache.put("1", "a");
cache.put("2", "b");
cache.put("3", "c");
cache.get("1");        // 访问 "1"，移到尾部
cache.put("4", "d");   // 超容量，删除 "2"（最老）

System.out.println(cache.keySet()); // [3, 1, 4]
```

---

## 遍历性能优化

**HashMap 遍历**：
```java
// 需要遍历整个桶数组（包括空桶）
for (Entry<K,V> e : hashMap.entrySet()) {
    // 时间复杂度 O(capacity + size)
}
```

**LinkedHashMap 遍历**：
```java
// 直接沿双向链表遍历
for (Entry<K,V> e : linkedHashMap.entrySet()) {
    // 时间复杂度 O(size)，与容量无关
}
```

**源码实现**：
```java
abstract class LinkedHashIterator {
    LinkedHashMap.Entry<K,V> next = head;  // 从头节点开始
    
    final LinkedHashMap.Entry<K,V> nextNode() {
        LinkedHashMap.Entry<K,V> e = next;
        next = e.after;  // 沿着链表遍历
        return e;
    }
}
```

---

## 性能分析

| 操作 | 时间复杂度 | 说明 |
|------|-----------|------|
| get | O(1) | 继承 HashMap，哈希定位 + 可能移动到尾部 |
| put | O(1) | 哈希定位 + 链表尾部插入 |
| remove | O(1) | 哈希定位 + 双向链表删除 |
| 遍历 | O(n) | 沿链表遍历，n 为元素数量（优于 HashMap） |

**空间复杂度**：
- 每个节点额外占用两个指针（before/after）
- 空间开销约为 HashMap 的 1.5 倍

---

## 使用场景

### 1. 保持插入顺序
```java
// 场景：需要按插入顺序输出的配置项
Map<String, String> config = new LinkedHashMap<>();
config.put("host", "localhost");
config.put("port", "8080");
config.put("timeout", "3000");
// 遍历顺序与插入顺序一致
```

### 2. LRU 缓存
```java
// 场景：最近最少使用缓存
LinkedHashMap<String, Image> imageCache = new LinkedHashMap<>(100, 0.75f, true) {
    @Override
    protected boolean removeEldestEntry(Map.Entry eldest) {
        return size() > 100;
    }
};
```

### 3. 数据库查询结果集
```java
// 场景：保持查询结果的顺序
Map<Long, User> userMap = new LinkedHashMap<>();
for (User user : queryResults) {
    userMap.put(user.getId(), user);
}
```

---

## 线程安全性

LinkedHashMap **不是线程安全**的，多线程环境需外部同步：

```java
// 方案 1：Collections.synchronizedMap（性能差）
Map<K, V> syncMap = Collections.synchronizedMap(new LinkedHashMap<>());

// 方案 2：显式加锁
Map<K, V> map = new LinkedHashMap<>();
synchronized(map) {
    map.put(key, value);
}

// 方案 3：使用 ConcurrentHashMap（无序）
// 注意：ConcurrentHashMap 不保证顺序，无法替代 LinkedHashMap
```

---

## 面试总结

**LinkedHashMap 的关键设计**：
1. **继承 HashMap**：复用哈希表的高效查找（O(1)）
2. **双向链表**：维护元素顺序（插入/访问）
3. **两种模式**：
   - 插入顺序（默认）：按 put 顺序遍历
   - 访问顺序（accessOrder=true）：get/put 后移到尾部
4. **LRU 钩子**：`removeEldestEntry()` 方法支持自动淘汰
5. **遍历优化**：O(size) 而非 O(capacity)

**经典面试追问**：
- Q: 为什么需要双向链表而不是单向？
- A: 删除节点时需要修改前驱节点的 `after` 指针，单向链表无法反向定位

**使用建议**：
- 需要顺序：优先选择 LinkedHashMap
- 需要排序：使用 TreeMap
- 高并发：ConcurrentHashMap（但无序）
- 简单场景：HashMap（性能最佳）

