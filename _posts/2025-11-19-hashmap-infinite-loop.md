---
layout: post
title: "为什么 HashMap 会产生死循环？"
date: 2025-11-19
categories: [Java, 集合框架]
tags: [HashMap, 并发问题, JDK7, 扩容机制]
description: "深入解析 JDK 7 中 HashMap 在多线程扩容时产生死循环的原因，以及 JDK 8 的改进方案"
---

### 1. 核心原因概述
HashMap 产生死循环（Infinite Loop）的经典场景主要发生在 **JDK 1.7 及以下版本** 的 **多线程并发扩容（Resize）** 阶段。

根本原因在于 JDK 1.7 的 HashMap 在扩容迁移链表时采用了 **头插法（Head Insertion）**，会导致链表元素顺序倒置。当多个线程同时触发扩容时，特定的执行顺序会导致链表形成 **环形数据结构（Circular Linked List）**。一旦形成环，当后续线程尝试 `get()` 操作遍历该链表时，就会陷入死循环，导致 CPU 飙升至 100%。

> **注**：JDK 1.8 改用了 **尾插法（Tail Insertion）**，扩容时保持链表元素相对顺序不变，因此解决了死循环问题，但在多线程环境下仍存在数据覆盖（丢数据）的风险，所以 HashMap 依然不是线程安全的。

---

### 2. 原理深度剖析 (JDK 1.7)

#### 2.1 关键源码逻辑
在 JDK 1.7 中，HashMap 扩容的核心方法是 `transfer`，负责将旧数组的元素迁移到新数组。

```java
// JDK 1.7 HashMap transfer 方法简化逻辑
void transfer(Entry[] newTable, boolean rehash) {
    int newCapacity = newTable.length;
    for (Entry<K,V> e : table) {
        while(null != e) {
            Entry<K,V> next = e.next; // 1. 记录下一个节点
            int i = indexFor(e.hash, newCapacity);
            e.next = newTable[i];     // 2. 头插法：将当前节点的 next 指向新位置的头节点
            newTable[i] = e;          // 3. 将当前节点设置为新位置的头节点
            e = next;                 // 4. 继续处理下一个节点
        }
    }
}
```

#### 2.2 死循环形成步骤演示
假设有两个线程 `Thread A` 和 `Thread B` 同时对 HashMap 进行扩容。
当前链表结构为：`Hash表[i] -> A -> B -> null`。

1.  **Thread A 执行到一半挂起**：
    Thread A 执行了 `Entry<K,V> next = e.next;`，此时：
    - `e` 指向 `A`
    - `next` 指向 `B`
    - **Thread A 挂起**。

2.  **Thread B 完成整个扩容**：
    Thread B 顺利完成了扩容和迁移。由于是 **头插法**，链表顺序会倒置。
    新数组中该位置的链表变为：`Hash表[j] -> B -> A -> null`。
    *注意：此时内存中 A 和 B 对象的引用关系已经变了，B.next 指向了 A。*

3.  **Thread A 恢复执行**：
    - Thread A 此时持有旧的引用：`e = A`, `next = B`。
    - Thread A 将 `A` 插入新表头：`newTable[i] = A`。
    - Thread A 处理下一个节点：`e = B`。

4.  **循环形成（关键点）**：
    - Thread A 处理 `e = B`。
    - 读取 `next = B.next`。由于 Thread B 已经修改了 B 的指向，此时 `B.next` 实际上是 `A`（见步骤 2）。
    - Thread A 将 `B` 头插：`B.next = A`（原本就是 A，没变），`newTable[i] = B`。
    - Thread A 处理下一个节点：`e = A`（因为 B.next 指向 A）。
    - Thread A 再次处理 `A`：`A.next = B`（头插法将 A 指向表头 B）。
    - **结果**：`A.next` 指向 `B`，而 `B.next` 指向 `A`。形成 `A <-> B` 环形链表。

---

### 3. 面试总结与扩展

#### 3.1 为什么 JDK 1.8 修复了这个问题？
JDK 1.8 在扩容时，使用了 **尾插法**。
- 在扩容时，通过高低位运算（`(e.hash & oldCap) == 0`）将链表拆分为两个子链表（Low 和 High）。
- 元素在迁移后，**相对顺序保持不变**。
- 因为顺序不倒置，就不会出现 B 指向 A，A 又指向 B 的情况，从而避免了死循环。

#### 3.2 线程安全建议
虽然 JDK 1.8 解决了死循环，但 HashMap 在多线程下依然不安全：
1.  **数据丢失**：并发 `put` 时，若发生 Hash 碰撞，两个线程判断槽位为空，可能同时赋值，导致其中一个数据被覆盖。
2.  **size 不准确**：`size` 变量是非原子操作。

**解决方案**：
- 必须使用 `ConcurrentHashMap`。
- 或者使用 `Collections.synchronizedMap(new HashMap<>())`（性能较差，全表锁）。