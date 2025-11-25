---
layout: default
title: "ArrayList与LinkedList有什么区别？"
parent: 集合框架
nav_order: 80
description: "深入对比ArrayList和LinkedList的底层实现、性能特点和使用场景"
date: 2025-11-02
---
## 核心概念

ArrayList 和 LinkedList 都是 Java 集合框架中 List 接口的实现类，但它们的底层数据结构完全不同：
- **ArrayList**：基于**动态数组**实现
- **LinkedList**：基于**双向链表**实现

这两种不同的数据结构导致它们在性能和使用场景上有明显差异。

## 底层实现原理

### ArrayList 的实现

```java
public class ArrayList<E> extends AbstractList<E> {
    // 底层是 Object 数组
    transient Object[] elementData;
    
    // 实际元素个数
    private int size;
    
    // 默认初始容量
    private static final int DEFAULT_CAPACITY = 10;
}
```

**特点**：
- 基于数组，元素在内存中连续存储
- 支持快速随机访问（通过索引）
- 插入/删除需要移动后续元素

### LinkedList 的实现

```java
public class LinkedList<E> extends AbstractSequentialList<E> 
    implements List<E>, Deque<E> {
    
    // 双向链表的头节点和尾节点
    transient Node<E> first;
    transient Node<E> last;
    
    // 节点结构
    private static class Node<E> {
        E item;
        Node<E> next;
        Node<E> prev;
    }
}
```

**特点**：
- 基于双向链表，元素在内存中不连续
- 不支持快速随机访问
- 插入/删除只需修改指针

## 核心区别对比

| 对比维度 | ArrayList | LinkedList |
|---------|-----------|------------|
| **底层结构** | 动态数组 | 双向链表 |
| **随机访问** | O(1)，支持快速随机访问 | O(n)，需要遍历 |
| **插入/删除（头部）** | O(n)，需要移动元素 | O(1)，修改指针即可 |
| **插入/删除（尾部）** | O(1)，摊销复杂度 | O(1) |
| **插入/删除（中间）** | O(n)，需要移动元素 | O(n)，需要先定位 |
| **内存占用** | 较小，只存储元素 | 较大，需存储前后指针 |
| **适用场景** | 频繁查询、遍历 | 频繁插入、删除 |

## 性能优化与使用场景

### ArrayList 适用场景

```java
// 1. 频繁随机访问
List<String> list = new ArrayList<>();
for (int i = 0; i < 1000; i++) {
    list.add("item" + i);
}
// 随机访问非常快
String item = list.get(500);  // O(1)

// 2. 遍历操作
for (String s : list) {
    System.out.println(s);
}

// 3. 预知大小时，指定容量避免扩容
List<Integer> numbers = new ArrayList<>(1000);
```

### LinkedList 适用场景

```java
// 1. 频繁在头部/尾部插入删除
LinkedList<String> deque = new LinkedList<>();
deque.addFirst("first");  // O(1)
deque.addLast("last");    // O(1)
deque.removeFirst();      // O(1)

// 2. 实现队列或栈
Queue<Integer> queue = new LinkedList<>();
queue.offer(1);
queue.poll();

Deque<Integer> stack = new LinkedList<>();
stack.push(1);
stack.pop();

// 3. 不确定数据量且需要频繁增删
List<String> list = new LinkedList<>();
list.add(0, "insert at head");  // 比 ArrayList 快
```

## 线程安全性考量

两者都**不是线程安全**的，多线程环境需要：

```java
// 方案1：使用同步包装器
List<String> syncList = Collections.synchronizedList(new ArrayList<>());

// 方案2：使用并发集合
List<String> concurrentList = new CopyOnWriteArrayList<>();

// 方案3：手动同步
synchronized(list) {
    list.add("item");
}
```

## 面试答题总结

**简洁版答案**：
1. **底层结构不同**：ArrayList 基于动态数组，LinkedList 基于双向链表
2. **性能差异**：
   - ArrayList 支持快速随机访问（O(1)），但插入/删除慢（O(n)）
   - LinkedList 头尾插入/删除快（O(1)），但随机访问慢（O(n)）
3. **内存占用**：LinkedList 额外存储前后指针，内存占用更大
4. **使用场景**：
   - ArrayList：查询多、插入删除少
   - LinkedList：插入删除多、查询少，或用作队列/栈

**加分项**：
- ArrayList 扩容机制：默认初始容量10，扩容为1.5倍
- LinkedList 实现了 Deque 接口，可作为双端队列使用
- 实际开发中 **ArrayList 使用更频繁**，因为现代 CPU 缓存对连续内存访问更友好
- 即使频繁插入删除，ArrayList 在数据量不大时也可能比 LinkedList 快（缓存局部性）

