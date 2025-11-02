---
layout: post
title: "Hashtable、HashMap、ConcurrentHashMap的区别"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [HashMap, Hashtable, ConcurrentHashMap, 线程安全, 并发]
description: "详解 Hashtable、HashMap 和 ConcurrentHashMap 三者在线程安全、性能、实现机制上的核心区别，以及在不同场景下的选型建议"
---

## 核心概念

这三个都是 Java 中常用的 Map 实现，主要区别在于**线程安全性**和**性能特征**：

- **HashMap**：线程不安全，性能最高，适用于单线程或外部同步场景
- **Hashtable**：线程安全（方法级同步），性能较低，已基本被淘汰
- **ConcurrentHashMap**：线程安全（分段锁/CAS），高并发性能优异，是并发场景首选

---

## 核心区别对比

### 1. 线程安全性

**Hashtable**：
- 所有方法使用 `synchronized` 修饰
- 粒度粗，整个表锁定，并发度为 1
- 读写操作都会阻塞其他线程

```java
public synchronized V get(Object key) { ... }
public synchronized V put(K key, V value) { ... }
```

**HashMap**：
- 完全不同步，多线程下可能导致数据不一致甚至死循环（JDK 1.7）

**ConcurrentHashMap**：
- **JDK 1.7**：分段锁（Segment 数组），默认 16 个段，并发度 16
- **JDK 1.8+**：CAS + synchronized（锁桶头节点），并发度等于桶数量
- 读操作几乎无锁（`volatile` 保证可见性），写操作只锁单个桶

```java
// JDK 1.8 put 操作核心逻辑
final V putVal(K key, V value, boolean onlyIfAbsent) {
    Node<K,V>[] tab; Node<K,V> f; int n, i, fh;
    // 1. 如果桶为空，CAS 设置
    if ((f = tabAt(tab, i = (n - 1) & hash)) == null) {
        if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value, null)))
            break; // 成功则退出
    }
    // 2. 如果有冲突，synchronized 锁住桶头节点
    else {
        synchronized (f) {
            // 链表或红黑树插入逻辑
        }
    }
}
```

---

### 2. Null 键值支持

| 实现类 | null key | null value |
|--------|----------|------------|
| HashMap | 允许 1 个 | 允许多个 |
| Hashtable | **不允许** | **不允许** |
| ConcurrentHashMap | **不允许** | **不允许** |

**原因**：
- HashMap 单线程场景，`get(key)` 返回 `null` 可明确区分"键不存在"和"值为 null"（通过 `containsKey`）
- 并发容器中，`get(key)` 返回 `null` 无法区分这两种情况（存在竞态条件），故禁止 null

---

### 3. 底层结构

**Hashtable**：
- 数组 + 链表（无红黑树优化）
- 初始容量 11，扩容为 `2n + 1`

**HashMap**：
- 数组 + 链表 + 红黑树（JDK 1.8+）
- 链表长度 ≥ 8 且数组长度 ≥ 64 时转红黑树
- 初始容量 16，扩容为 `2n`（保证容量为 2 的幂）

**ConcurrentHashMap**：
- JDK 1.7：Segment 数组 + HashEntry 数组
- JDK 1.8：与 HashMap 相似（数组 + 链表 + 红黑树），但节点使用 `volatile`

---

### 4. 性能对比

| 场景 | HashMap | Hashtable | ConcurrentHashMap |
|------|---------|-----------|-------------------|
| 单线程读写 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| 多线程读 | ❌ 不安全 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 多线程写 | ❌ 不安全 | ⭐ | ⭐⭐⭐⭐⭐ |
| 高并发场景 | ❌ | ⭐ | ⭐⭐⭐⭐⭐ |

---

## 使用场景与选型

### HashMap
```java
// 单线程或外部同步
Map<String, User> userMap = new HashMap<>();

// 需要线程安全可包装（性能差，不推荐）
Map<String, User> syncMap = Collections.synchronizedMap(new HashMap<>());
```

### ConcurrentHashMap
```java
// 高并发场景首选
Map<String, User> cache = new ConcurrentHashMap<>();

// 原子操作
cache.putIfAbsent("key", new User());
cache.computeIfAbsent("key", k -> new User());
```

### Hashtable
```java
// ❌ 已过时，不推荐使用
// 如需线程安全，优先选择 ConcurrentHashMap
```

---

## 并发场景的注意事项

### 1. HashMap 在多线程下的问题

**JDK 1.7 死循环问题**：
- 扩容时采用头插法，多线程可能形成环形链表
- `get()` 操作陷入死循环，CPU 100%

**JDK 1.8 改进**：
- 改为尾插法，但仍可能丢失数据或覆盖

### 2. ConcurrentHashMap 的弱一致性

```java
ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
map.put("a", 1);
map.put("b", 2);

// 迭代过程中的修改可能可见也可能不可见
for (String key : map.keySet()) {
    map.put("c", 3); // 可能在迭代中体现，也可能不体现
}
```

### 3. 复合操作需额外同步

```java
// ❌ 非原子操作
if (!map.containsKey(key)) {
    map.put(key, value); // 存在竞态条件
}

// ✅ 使用原子方法
map.putIfAbsent(key, value);
map.computeIfAbsent(key, k -> computeValue(k));
```

---

## 面试总结

| 维度 | HashMap | Hashtable | ConcurrentHashMap |
|------|---------|-----------|-------------------|
| 线程安全 | ❌ | ✅（方法锁） | ✅（分段锁/CAS） |
| null 支持 | ✅ | ❌ | ❌ |
| 性能 | 最高 | 低 | 高 |
| 推荐场景 | 单线程 | **不推荐** | 并发场景 |
| JDK 版本 | 1.2+ | 1.0（遗留类） | 1.5+（1.8 重写） |

**记忆口诀**：
- **HashMap**：快但不安全
- **Hashtable**：安全但慢（已淘汰）
- **ConcurrentHashMap**：又快又安全（并发首选）

