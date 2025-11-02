---
layout: post
title: "ArrayList和LinkedList的时间复杂度"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [ArrayList, LinkedList, 时间复杂度, 性能分析]
description: "详细对比ArrayList和LinkedList各种操作的时间复杂度，帮助选择合适的数据结构"
---

## 核心概念

ArrayList 和 LinkedList 因底层数据结构不同（数组 vs 双向链表），导致各种操作的时间复杂度存在显著差异。理解这些差异是选择合适数据结构的关键。

## 时间复杂度对比表

| 操作 | ArrayList | LinkedList | 说明 |
|-----|-----------|------------|------|
| **get(index)** | O(1) | O(n) | 数组支持随机访问，链表需遍历 |
| **add(E e)** | O(1)* | O(1) | 尾部添加，ArrayList 需考虑扩容 |
| **add(0, E e)** | O(n) | O(1) | 头部添加，ArrayList 需移动元素 |
| **add(index, E e)** | O(n) | O(n) | 中间插入，都需要定位+操作 |
| **remove(index)** | O(n) | O(n) | ArrayList 需移动，LinkedList 需定位 |
| **remove(0)** | O(n) | O(1) | 头部删除 |
| **remove(size-1)** | O(1) | O(1) | 尾部删除 |
| **contains(E e)** | O(n) | O(n) | 都需要遍历查找 |
| **iterator.remove()** | O(n) | O(1) | 迭代器删除 |
| **size()** | O(1) | O(1) | 都维护了 size 字段 |
| **clear()** | O(n) | O(n) | 需要清理引用 |

**注**：O(1)* 表示摊销时间复杂度，扩容时为 O(n)

## 详细分析

### 1. 随机访问（get）

```java
// ArrayList：O(1) - 直接通过索引访问
public E get(int index) {
    rangeCheck(index);
    return elementData[index];  // 数组下标访问
}

// LinkedList：O(n) - 需要遍历链表
public E get(int index) {
    checkElementIndex(index);
    return node(index).item;  // 调用 node() 方法遍历
}

Node<E> node(int index) {
    // 优化：从头或尾开始遍历（取较近的一端）
    if (index < (size >> 1)) {
        Node<E> x = first;
        for (int i = 0; i < index; i++)
            x = x.next;
        return x;
    } else {
        Node<E> x = last;
        for (int i = size - 1; i > index; i--)
            x = x.prev;
        return x;
    }
}
```

**性能对比示例**：
```java
List<Integer> arrayList = new ArrayList<>();
List<Integer> linkedList = new LinkedList<>();

// 都添加10000个元素
for (int i = 0; i < 10000; i++) {
    arrayList.add(i);
    linkedList.add(i);
}

// ArrayList：O(1)，瞬间完成
long start = System.nanoTime();
for (int i = 0; i < 10000; i++) {
    arrayList.get(i);
}
long time1 = System.nanoTime() - start;  // ~0.5ms

// LinkedList：O(n²)，需要大量时间
start = System.nanoTime();
for (int i = 0; i < 10000; i++) {
    linkedList.get(i);  // 每次都要遍历
}
long time2 = System.nanoTime() - start;  // ~500ms（慢1000倍）
```

### 2. 头部插入（add 到索引0）

```java
// ArrayList：O(n) - 需要移动所有元素
public void add(int index, E element) {
    rangeCheckForAdd(index);
    ensureCapacityInternal(size + 1);
    // 将 index 及之后的元素向后移动一位
    System.arraycopy(elementData, index, 
                     elementData, index + 1,
                     size - index);
    elementData[index] = element;
    size++;
}

// LinkedList：O(1) - 只需修改指针
public void addFirst(E e) {
    linkFirst(e);
}

private void linkFirst(E e) {
    final Node<E> f = first;
    final Node<E> newNode = new Node<>(null, e, f);
    first = newNode;
    if (f == null)
        last = newNode;
    else
        f.prev = newNode;
    size++;
}
```

**性能对比示例**：
```java
List<Integer> arrayList = new ArrayList<>();
List<Integer> linkedList = new LinkedList<>();

// ArrayList：O(n) - 每次都要移动元素
long start = System.nanoTime();
for (int i = 0; i < 10000; i++) {
    arrayList.add(0, i);  // 头部插入
}
long time1 = System.nanoTime() - start;  // ~200ms

// LinkedList：O(1) - 快速完成
start = System.nanoTime();
for (int i = 0; i < 10000; i++) {
    linkedList.add(0, i);  // 头部插入
}
long time2 = System.nanoTime() - start;  // ~2ms
```

### 3. 尾部插入（add）

```java
// ArrayList：O(1) 摊销复杂度
public boolean add(E e) {
    ensureCapacityInternal(size + 1);  // 可能触发扩容O(n)
    elementData[size++] = e;
    return true;
}
// 大多数情况 O(1)，偶尔扩容时 O(n)
// 摊销分析：n 次操作总时间 O(n)，平均 O(1)

// LinkedList：O(1)
public boolean add(E e) {
    linkLast(e);
    return true;
}

void linkLast(E e) {
    final Node<E> l = last;
    final Node<E> newNode = new Node<>(l, e, null);
    last = newNode;
    if (l == null)
        first = newNode;
    else
        l.next = newNode;
    size++;
}
```

### 4. 中间插入/删除

```java
// ArrayList：O(n) - 需要移动元素
list.add(list.size() / 2, element);  // 移动一半元素

// LinkedList：O(n) - 需要先定位到位置
list.add(list.size() / 2, element);  // 先遍历到中间，再插入

// 综合时间：ArrayList 和 LinkedList 都是 O(n)
```

### 5. 迭代器操作

```java
// ArrayList 迭代器删除：O(n)
Iterator<Integer> iter1 = arrayList.iterator();
while (iter1.hasNext()) {
    if (iter1.next() == target) {
        iter1.remove();  // 需要移动后续元素
    }
}

// LinkedList 迭代器删除：O(1)
Iterator<Integer> iter2 = linkedList.iterator();
while (iter2.hasNext()) {
    if (iter2.next() == target) {
        iter2.remove();  // 只需修改指针
    }
}
```

## 实际性能考量

### 1. CPU 缓存友好性

```java
// ArrayList：数组在内存中连续，缓存命中率高
for (int i = 0; i < arrayList.size(); i++) {
    process(arrayList.get(i));  // CPU 可预取数据
}

// LinkedList：节点分散在堆中，缓存命中率低
for (int i = 0; i < linkedList.size(); i++) {
    process(linkedList.get(i));  // 每次访问可能缓存未命中
}

// 结论：即使是 O(n) 的遍历，ArrayList 通常也比 LinkedList 快
```

### 2. 内存占用对比

```java
// ArrayList 内存占用
// - 数组本身：n * 引用大小（4或8字节）
// - 未使用的容量：(capacity - size) * 引用大小

// LinkedList 内存占用
// - 每个节点：对象头(12-16字节) + 元素引用(4-8字节) + prev(4-8字节) + next(4-8字节)
// - 总计：每个元素约 24-40 字节

// 结论：LinkedList 的内存开销明显大于 ArrayList
```

### 3. 场景选择建议

```java
// 场景1：频繁随机访问 → ArrayList
List<String> cache = new ArrayList<>();
String value = cache.get(randomIndex);  // O(1)

// 场景2：频繁头尾插入删除 → LinkedList（或ArrayDeque）
Deque<Task> queue = new LinkedList<>();
queue.addFirst(task);   // O(1)
queue.removeFirst();    // O(1)

// 场景3：大量遍历操作 → ArrayList
for (String item : list) {
    process(item);  // ArrayList 更快（缓存友好）
}

// 场景4：不确定数据量，以查询为主 → ArrayList
List<User> users = new ArrayList<>();  // 默认选择
```

## 面试答题总结

**核心答案**：

| 操作类型 | ArrayList | LinkedList | 推荐选择 |
|---------|-----------|------------|----------|
| 随机访问 | O(1) ✅ | O(n) ❌ | ArrayList |
| 头部插入 | O(n) ❌ | O(1) ✅ | LinkedList |
| 尾部插入 | O(1) ✅ | O(1) ✅ | ArrayList（内存友好） |
| 中间插入 | O(n) | O(n) | ArrayList（缓存友好） |
| 顺序遍历 | O(n) ✅ | O(n) ⚠️ | ArrayList（快2-3倍） |

**关键要点**：
1. **ArrayList**：
   - 优势：随机访问 O(1)，内存连续，缓存友好
   - 劣势：插入删除需要移动元素 O(n)，扩容开销

2. **LinkedList**：
   - 优势：头尾插入删除 O(1)，无需扩容
   - 劣势：随机访问 O(n)，内存占用大，缓存不友好

3. **实际建议**：
   - **90% 的场景选 ArrayList**（即使有插入删除）
   - 只有频繁头部操作时考虑 LinkedList（或 ArrayDeque）
   - 需要队列/栈时优先使用 ArrayDeque

**加分项**：
- 提到 CPU 缓存行（cache line）对性能的影响
- 说明 LinkedList 的 `node()` 方法会从两端遍历优化
- 建议使用 `ArrayDeque` 替代 LinkedList 作为队列/栈
- 解释摊销时间复杂度的概念

