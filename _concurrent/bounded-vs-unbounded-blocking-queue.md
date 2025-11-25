---
title: "阻塞队列的有界与无界是什么意思？"
date: 2025-11-19
categories: [Java并发]
tags: [BlockingQueue, Java, 面试题]
description: "深入解析Java阻塞队列中有界与无界的区别，分析ArrayBlockingQueue与LinkedBlockingQueue的实现原理及生产环境中的OOM风险。"
nav_order: 264
parent: 并发编程
---
### 1. 核心概念简述

在 Java 的 `BlockingQueue` 体系中，**有界（Bounded）**与**无界（Unbounded）**主要指的是队列**存储容量（Capacity）**的限制策略：

*   **有界队列**：在创建时必须指定一个固定的最大容量。当队列元素数量达到该容量时，生产者线程如果继续尝试插入元素，将会被**阻塞**（put操作）或失败（add/offer操作），直到队列中有空位。
*   **无界队列**：通常指容量设置为 `Integer.MAX_VALUE` 的队列。虽然理论上也是“有界”的（受限于内存），但在实际应用中，其容量远超一般任务处理量，因此被称为“无界”。在这种情况下，生产者几乎永远不会因为队列满而被阻塞。

### 2. 原理与源码关键点

这一区别最典型的代表是 `ArrayBlockingQueue` 和 `LinkedBlockingQueue`。

#### ArrayBlockingQueue（典型的有界队列）
基于数组实现，创建时**必须**传入 `capacity` 参数。

```java
// ArrayBlockingQueue 构造函数
public ArrayBlockingQueue(int capacity, boolean fair) {
    if (capacity <= 0)
        throw new IllegalArgumentException();
    this.items = new Object[capacity]; // 必须指定大小
    // ...
}
```

#### LinkedBlockingQueue（可选的有界/无界队列）
基于链表实现。如果构造时不传大小，默认容量为 `Integer.MAX_VALUE`，此时表现为“无界”；如果传入大小，则表现为“有界”。

```java
// LinkedBlockingQueue 构造函数
public LinkedBlockingQueue() {
    this(Integer.MAX_VALUE); // 默认无界
}

public LinkedBlockingQueue(int capacity) {
    if (capacity <= 0) throw new IllegalArgumentException();
    this.capacity = capacity;
    last = head = new Node<E>(null);
}
```

### 3. 生产环境考量：OOM 与 稳定性

在面试中，这一点是区分“背书”与“实战经验”的关键：

1.  **内存溢出（OOM）风险**：
    *   使用**无界队列**（如默认的 `LinkedBlockingQueue` 或 `Executors.newFixedThreadPool` 创建的队列）时，如果消费者的处理速度跟不上生产者的生产速度，队列中的任务会无限堆积，最终导致 Heap 内存耗尽，抛出 `OutOfMemoryError`。
    *   **阿里巴巴 Java 开发手册**明确禁止使用 `Executors` 去创建线程池，正是因为其默认使用了无界队列。

2.  **背压（Backpressure）机制**：
    *   **有界队列**提供了一种天然的保护机制。当系统过载时，队列满了会阻塞生产者或拒绝新任务（配合线程池的拒绝策略），从而保护系统不被压垮，这是一种“快速失败”或“自我保护”的策略。

3.  **吞吐量**：
    *   `ArrayBlockingQueue` 在入队和出队时使用同一把锁，而 `LinkedBlockingQueue` 使用了两把锁（`putLock` 和 `takeLock`），实现了入队和出队的分离。因此，在并发度极高的场景下，`LinkedBlockingQueue`（即使设置为有界）的吞吐量通常优于 `ArrayBlockingQueue`。

### 4. 总结与示例

**回答总结：**
“有界与无界的核心区别在于**容量限制**。有界队列限制了最大任务数，能防止内存溢出，提供系统自我保护；无界队列容量近似无限，容易在生产快于消费时导致 OOM。在生产环境中，为了系统稳定性，**强烈建议优先使用有界队列**，并根据业务量合理设置大小。”

**代码示例：**

```java
// 推荐：使用有界队列，容量为 100
BlockingQueue<Runnable> boundedQueue = new ArrayBlockingQueue<>(100);

// 慎用：默认无界队列，容量为 Integer.MAX_VALUE
BlockingQueue<Runnable> unboundedQueue = new LinkedBlockingQueue<>();

// 线程池中的应用
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    10, 20, 60L, TimeUnit.SECONDS,
    new ArrayBlockingQueue<>(1000), // 使用有界队列防止 OOM
    new ThreadPoolExecutor.AbortPolicy()
);
```
