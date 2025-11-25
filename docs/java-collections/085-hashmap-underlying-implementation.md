---
layout: default
title: "HashMap的底层实现原理"
parent: 集合框架
nav_order: 85
description: "深入解析HashMap的底层数据结构和实现原理，包括数组+链表+红黑树的设计思想"
date: 2025-11-02
---
## 核心概念

HashMap 是基于**哈希表**实现的 Map 接口实现类，用于存储键值对（key-value）映射关系。它的核心是通过 hash 算法将 key 映射到数组的某个位置（bucket），实现 O(1) 的平均查找时间复杂度。

## 底层数据结构

### JDK 1.8 的实现

HashMap 采用 **数组 + 链表 + 红黑树** 的组合结构：

```java
// 核心数据结构
transient Node<K,V>[] table;  // 哈希桶数组

// 节点定义
static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;    // 哈希值
    final K key;       // 键
    V value;           // 值
    Node<K,V> next;    // 链表的下一个节点
}

// 红黑树节点
static final class TreeNode<K,V> extends LinkedHashMap.Entry<K,V> {
    TreeNode<K,V> parent;
    TreeNode<K,V> left;
    TreeNode<K,V> right;
    TreeNode<K,V> prev;
    boolean red;
}
```

### 工作原理

1. **存储过程（put）**：
   ```java
   public V put(K key, V value) {
       return putVal(hash(key), key, value, false, true);
   }
   ```
   - 计算 key 的 hash 值
   - 通过 `(n - 1) & hash` 确定在数组中的索引位置
   - 如果该位置为空，直接插入
   - 如果该位置已有元素：
     - 如果是链表结构，遍历链表插入或更新
     - 如果是红黑树结构，按树的方式插入或更新
   - 链表长度超过 8 且数组长度 ≥ 64 时，转为红黑树

2. **查询过程（get）**：
   ```java
   public V get(Object key) {
       Node<K,V> e;
       return (e = getNode(hash(key), key)) == null ? null : e.value;
   }
   ```
   - 计算 hash 值定位到桶
   - 比较第一个节点，匹配则返回
   - 如果是树节点，按树查找
   - 如果是链表，遍历查找

## 关键特性

### 1. 时间复杂度
- **最优情况**：O(1) - 无哈希冲突
- **最坏情况**：O(log n) - 红黑树结构（JDK 1.8）
- **JDK 1.7 最坏情况**：O(n) - 全部冲突在链表上

### 2. 容量与负载因子
```java
static final int DEFAULT_INITIAL_CAPACITY = 16;  // 默认初始容量
static final float DEFAULT_LOAD_FACTOR = 0.75f;  // 默认负载因子
```

### 3. 线程安全性
- **非线程安全**，多线程环境需使用 `ConcurrentHashMap` 或 `Collections.synchronizedMap()`

## 性能优化考量

1. **合理设置初始容量**：避免频繁扩容
   ```java
   // 如果知道大概数据量，可以预设容量
   Map<String, Object> map = new HashMap<>(128);
   ```

2. **选择合适的 Key**：
   - 重写 `equals()` 和 `hashCode()` 方法
   - 保证 hashCode 分布均匀，减少碰撞

3. **避免过多冲突**：
   - 链表过长影响性能
   - JDK 1.8 引入红黑树优化了这个问题

## 面试答题总结

**答题要点**：
1. 底层是数组 + 链表 + 红黑树（JDK 1.8）
2. 通过 hash 算法定位元素位置
3. 哈希冲突时用链表存储，链表过长转红黑树
4. 扩容机制：当元素数量超过容量 × 负载因子时扩容为原来的 2 倍
5. 时间复杂度：查询 O(1) ~ O(log n)

**加分项**：
- 提到 JDK 1.7 与 1.8 的区别（头插法 vs 尾插法）
- 说明为什么容量是 2 的幂次方
- 解释负载因子 0.75 的权衡

