---
layout: post
title: "HashMap为什么线程不安全？"
date: 2025-11-02
categories: [Java, 集合框架, 并发编程]
tags: [HashMap, 线程安全, 并发问题]
description: "详解HashMap在多线程环境下的安全问题，包括数据丢失、死循环等典型场景"
---

## 核心概念

HashMap 是**非线程安全**的集合类，在多线程并发操作时会出现数据不一致、数据丢失甚至死循环等问题。这是因为 HashMap 的内部操作没有任何同步机制。

## 线程不安全的表现

### 1. 数据覆盖丢失

**场景**：多个线程同时执行 put 操作

```java
public V put(K key, V value) {
    return putVal(hash(key), key, value, false, true);
}

final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    // ...
    if ((p = tab[i = (n - 1) & hash]) == null)  // ① 判断位置为空
        tab[i] = newNode(hash, key, value, null);  // ② 插入新节点
    // ...
}
```

**问题分析**：
- 线程 A 在 ① 处判断位置为空，准备插入
- 线程 B 也在 ① 处判断位置为空，准备插入
- 线程 A 执行 ② 插入数据
- 线程 B 执行 ② 插入数据，**覆盖了线程 A 的数据**

**结果**：线程 A 的数据丢失

### 2. size 计数不准确

```java
final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    // ...
    if (++size > threshold)  // 非原子操作
        resize();
    // ...
}
```

**问题分析**：
- `++size` 不是原子操作，包含读取、加1、写入三个步骤
- 多线程并发时，可能多次插入但 size 只增加一次

**示例**：
```java
// 初始 size = 5
线程A: 读取 size = 5
线程B: 读取 size = 5
线程A: 计算 5 + 1 = 6，写入 size = 6
线程B: 计算 5 + 1 = 6，写入 size = 6
// 实际插入了2个元素，但 size 只增加了1
```

### 3. JDK 1.7 死循环问题（已修复）

**场景**：并发扩容时的链表环化

```java
// JDK 1.7 的扩容转移方法（头插法）
void transfer(Entry[] newTable) {
    Entry[] src = table;
    for (int j = 0; j < src.length; j++) {
        Entry<K,V> e = src[j];
        if (e != null) {
            src[j] = null;
            do {
                Entry<K,V> next = e.next;  // ①
                int i = indexFor(e.hash, newTable.length);
                e.next = newTable[i];      // ② 头插法
                newTable[i] = e;           // ③
                e = next;                  // ④
            } while (e != null);
        }
    }
}
```

**死循环场景**：
1. 假设线程1和线程2同时扩容
2. 原链表：A → B → null
3. 线程1执行到 ① 后挂起（此时 e=A, next=B）
4. 线程2完成扩容，因为头插法，变成：B → A → null
5. 线程1恢复执行：
   - A.next = B（A 指向 B）
   - B.next = A（B 指向 A）
   - 形成环：A ⇄ B

**结果**：CPU 100%，get 操作陷入死循环

> **注意**：JDK 1.8 改用尾插法后避免了这个问题，但**仍然不是线程安全的**

### 4. JDK 1.8 的并发问题

虽然 JDK 1.8 解决了死循环问题，但仍存在：
- **数据覆盖**：同位置并发插入
- **扩容数据丢失**：一个线程扩容，另一个线程 put
- **Fast-fail**：迭代时其他线程修改，抛出 `ConcurrentModificationException`

```java
public class HashMapConcurrentTest {
    public static void main(String[] args) throws InterruptedException {
        Map<String, String> map = new HashMap<>();
        
        // 模拟并发 put
        for (int i = 0; i < 10; i++) {
            new Thread(() -> {
                for (int j = 0; j < 1000; j++) {
                    map.put(Thread.currentThread().getName() + j, "value" + j);
                }
            }).start();
        }
        
        Thread.sleep(3000);
        System.out.println("期望: 10000, 实际: " + map.size());  // 可能小于 10000
    }
}
```

## 线程安全替代方案

### 1. ConcurrentHashMap（推荐）
```java
Map<String, String> map = new ConcurrentHashMap<>();
```
- JDK 1.7：分段锁（Segment）
- JDK 1.8：CAS + synchronized，性能更优

### 2. Collections.synchronizedMap
```java
Map<String, String> map = Collections.synchronizedMap(new HashMap<>());
```
- 通过 synchronized 对每个方法加锁
- 性能较差，锁粒度大

### 3. Hashtable（不推荐）
```java
Map<String, String> map = new Hashtable<>();
```
- 所有方法都加 synchronized
- 性能差，已过时

## 面试答题总结

**答题要点**：
1. **数据覆盖**：多线程同时 put 到同一位置，后写覆盖先写
2. **size 不准确**：++size 非原子操作，导致计数错误
3. **JDK 1.7 死循环**：扩容时头插法 + 并发导致链表成环
4. **JDK 1.8**：虽然改为尾插法避免死循环，但仍有数据丢失问题

**加分项**：
- 画图说明死循环的形成过程
- 对比 ConcurrentHashMap 的线程安全实现
- 提到 modCount 和 fast-fail 机制
- 说明为什么 JDK 1.8 用尾插法

**实际建议**：多线程环境必须使用 `ConcurrentHashMap`

