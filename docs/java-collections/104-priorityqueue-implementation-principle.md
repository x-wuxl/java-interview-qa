---
layout: default
title: "PriorityQueue的底层实现原理"
parent: 集合框架
nav_order: 104
description: "深入分析PriorityQueue的堆数据结构实现、自动排序机制及其核心源码原理"
author: "wuxl"
date: 2025-11-02
---
## 问题

PriorityQueue的底层实现原理？

## 答案

### 1. 核心概念

`PriorityQueue` 是基于**优先级堆**（Priority Heap）的无界优先级队列，元素按照**自然顺序**或**自定义比较器**进行排序，队头始终是最小元素（或自定义规则下的最高优先级元素）。

**关键特点**：
- 底层使用**数组实现的完全二叉堆**（默认是小顶堆）
- 非线程安全
- 不允许 `null` 元素
- 插入和删除的时间复杂度为 `O(log n)`
- 查看队头元素（peek）时间复杂度为 `O(1)`

---

### 2. 底层实现原理

#### 2.1 数据结构

```java
public class PriorityQueue<E> extends AbstractQueue<E> {
    // 存储堆元素的数组
    transient Object[] queue;

    // 队列中的元素个数
    private int size = 0;

    // 比较器（null 表示使用元素的自然顺序）
    private final Comparator<? super E> comparator;

    // 默认初始容量
    private static final int DEFAULT_INITIAL_CAPACITY = 11;
}
```

#### 2.2 堆的性质

PriorityQueue 使用**完全二叉堆**，满足以下性质：

- **父子节点关系**（数组索引）：
  - 父节点索引：`(i - 1) / 2`
  - 左子节点索引：`2 * i + 1`
  - 右子节点索引：`2 * i + 2`

- **堆序性**（以小顶堆为例）：
  - 任意节点的值 ≤ 其子节点的值

#### 2.3 核心操作源码分析

**（1）插入元素 - offer(E e)**

```java
public boolean offer(E e) {
    if (e == null)
        throw new NullPointerException();
    modCount++;
    int i = size;
    if (i >= queue.length)
        grow(i + 1);  // 数组扩容
    size = i + 1;
    if (i == 0)
        queue[0] = e;  // 第一个元素直接放在堆顶
    else
        siftUp(i, e);  // 上浮调整堆
    return true;
}

// 上浮操作：将新元素从叶子节点向上调整
private void siftUp(int k, E x) {
    if (comparator != null)
        siftUpUsingComparator(k, x);
    else
        siftUpComparable(k, x);
}

private void siftUpComparable(int k, E x) {
    Comparable<? super E> key = (Comparable<? super E>) x;
    while (k > 0) {
        int parent = (k - 1) >>> 1;  // 父节点索引
        Object e = queue[parent];
        if (key.compareTo((E) e) >= 0)
            break;  // 满足堆序性，停止上浮
        queue[k] = e;  // 父节点下移
        k = parent;    // 继续向上比较
    }
    queue[k] = key;
}
```

**（2）删除队头 - poll()**

```java
public E poll() {
    if (size == 0)
        return null;
    int s = --size;
    modCount++;
    E result = (E) queue[0];  // 保存队头元素
    E x = (E) queue[s];
    queue[s] = null;
    if (s != 0)
        siftDown(0, x);  // 将最后一个元素放到堆顶后下沉调整
    return result;
}

// 下沉操作：从堆顶向下调整
private void siftDown(int k, E x) {
    if (comparator != null)
        siftDownUsingComparator(k, x);
    else
        siftDownComparable(k, x);
}

private void siftDownComparable(int k, E x) {
    Comparable<? super E> key = (Comparable<? super E>) x;
    int half = size >>> 1;  // 只需遍历到非叶子节点
    while (k < half) {
        int child = (k << 1) + 1;  // 左子节点
        Object c = queue[child];
        int right = child + 1;
        // 找到左右子节点中较小的一个
        if (right < size &&
            ((Comparable<? super E>) c).compareTo((E) queue[right]) > 0)
            c = queue[child = right];
        if (key.compareTo((E) c) <= 0)
            break;  // 满足堆序性
        queue[k] = c;  // 子节点上移
        k = child;     // 继续向下比较
    }
    queue[k] = key;
}
```

**（3）扩容机制**

```java
private void grow(int minCapacity) {
    int oldCapacity = queue.length;
    // 容量翻倍（小容量时 +2，大容量时 +50%）
    int newCapacity = oldCapacity + ((oldCapacity < 64) ?
                                     (oldCapacity + 2) :
                                     (oldCapacity >> 1));
    if (newCapacity - MAX_ARRAY_SIZE > 0)
        newCapacity = hugeCapacity(minCapacity);
    queue = Arrays.copyOf(queue, newCapacity);
}
```

---

### 3. 性能特点与使用场景

#### 3.1 时间复杂度

| 操作 | 时间复杂度 | 说明 |
|-----|----------|------|
| `offer(e)` | O(log n) | 上浮调整堆 |
| `poll()` | O(log n) | 下沉调整堆 |
| `peek()` | O(1) | 直接访问数组首元素 |
| `remove(o)` | O(n) | 需要先查找元素 |
| `contains(o)` | O(n) | 线性查找 |

#### 3.2 线程安全

- **PriorityQueue 非线程安全**，多线程环境需使用：
  ```java
  PriorityBlockingQueue<Integer> queue = new PriorityBlockingQueue<>();
  ```

#### 3.3 典型应用场景

1. **任务调度**：按优先级处理任务
2. **TopK 问题**：维护最大/最小的 K 个元素
3. **Dijkstra 算法**：图的最短路径计算
4. **事件驱动模拟**：按时间顺序处理事件

---

### 4. 使用示例

#### 4.1 自然排序（小顶堆）

```java
PriorityQueue<Integer> minHeap = new PriorityQueue<>();
minHeap.offer(5);
minHeap.offer(2);
minHeap.offer(8);
minHeap.offer(1);

System.out.println(minHeap.poll());  // 输出 1（最小值）
System.out.println(minHeap.poll());  // 输出 2
```

#### 4.2 自定义比较器（大顶堆）

```java
PriorityQueue<Integer> maxHeap = new PriorityQueue<>((a, b) -> b - a);
maxHeap.offer(5);
maxHeap.offer(2);
maxHeap.offer(8);

System.out.println(maxHeap.poll());  // 输出 8（最大值）
```

#### 4.3 自定义对象排序

```java
class Task {
    String name;
    int priority;

    Task(String name, int priority) {
        this.name = name;
        this.priority = priority;
    }
}

PriorityQueue<Task> taskQueue = new PriorityQueue<>(
    Comparator.comparingInt(t -> t.priority)
);

taskQueue.offer(new Task("任务A", 3));
taskQueue.offer(new Task("任务B", 1));
taskQueue.offer(new Task("任务C", 2));

Task urgent = taskQueue.poll();  // 获取优先级最高的任务（priority=1）
```

---

### 答题总结

**PriorityQueue 使用数组实现的完全二叉堆**，通过 `siftUp`（上浮）和 `siftDown`（下沉）操作维护堆的性质。插入和删除的时间复杂度为 `O(log n)`，适合需要动态获取最值的场景。注意它是**非线程安全**的，多线程环境应使用 `PriorityBlockingQueue`。
