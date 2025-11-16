---
layout: post
title: "为什么 HashMap 会产生死循环？"
date: 2025-11-16
categories: ["集合与数据结构"]
tags: ["HashMap", "并发", "数据结构"]
description: "分析 HashMap 在并发扩容时出现死循环的根因与规避策略。"
---

### 核心概念
HashMap 在 JDK7 及之前使用数组 + 链表结构，通过拉链法解决冲突；在并发环境下没有任何同步控制，线程同时触发扩容会导致链表重排异常，进而出现访问死循环。

### 原理或源码关键点
1. **扩容触发点**：`size > threshold` 时执行 `resize`，将旧桶数据按 `hash & newMask` 迁移至新表。
2. **链表反转问题**：JDK7 的 `transfer` 采用头插法搬迁链表节点，在多线程交错写入时会破坏链表顺序；部分节点互相引用，形成环形结构。
3. **非线程安全根因**：`table`、`size`、`next` 等字段未加锁或 volatile，导致可见性与指令交错问题；任何读操作若进入含环链表都会无限遍历。
4. **JDK8 改进**：引入红黑树与尾插式迁移，降低环链概率，但仍然未提供并发保障。

### 性能与线程安全考量
- 在多线程场景使用 `ConcurrentHashMap` 或加外部锁；JDK8 的 `CHM` 采用分段 CAS + synchronized，避免扩容死循环。
- 结合 `computeIfAbsent`、`putIfAbsent` 等原子操作，减少竞态。
- 监控扩容频率：初始容量设置为 `expectedSize / loadFactor`，降低迁移次数。

HashMap 死循环本质是多线程同时 resize 时链表被拆散/反转形成环。正确做法是在并发场景使用线程安全容器或外部同步，并提前规划容量以避免频繁扩容。
