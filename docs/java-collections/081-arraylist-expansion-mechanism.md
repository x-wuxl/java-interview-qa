---
layout: default
title: "ArrayList的扩容机制是怎样的？"
parent: 集合框架
nav_order: 81
description: "深入解析ArrayList的扩容机制，包括初始容量、扩容时机和扩容倍数"
date: 2025-11-02
---
## 核心概念

ArrayList 的扩容机制是指当数组容量不足以容纳新增元素时，ArrayList 会自动创建一个更大的数组，并将原数组的元素复制到新数组中。这是一种**空间换时间**的策略，通过动态扩容实现可变长度的数组。

## 扩容机制原理

### 关键参数

```java
public class ArrayList<E> {
    // 默认初始容量
    private static final int DEFAULT_CAPACITY = 10;
    
    // 存储元素的数组
    transient Object[] elementData;
    
    // 实际元素个数
    private int size;
    
    // 最大数组大小
    private static final int MAX_ARRAY_SIZE = Integer.MAX_VALUE - 8;
}
```

### 扩容过程源码分析

#### 1. 添加元素触发扩容

```java
public boolean add(E e) {
    // 确保容量足够
    ensureCapacityInternal(size + 1);
    elementData[size++] = e;
    return true;
}

private void ensureCapacityInternal(int minCapacity) {
    ensureExplicitCapacity(calculateCapacity(elementData, minCapacity));
}

private static int calculateCapacity(Object[] elementData, int minCapacity) {
    // 如果是默认空数组，返回默认容量10
    if (elementData == DEFAULTCAPACITY_EMPTY_ELEMENTDATA) {
        return Math.max(DEFAULT_CAPACITY, minCapacity);
    }
    return minCapacity;
}
```

#### 2. 执行扩容操作

```java
private void ensureExplicitCapacity(int minCapacity) {
    modCount++;
    // 如果需要的容量大于当前数组长度，执行扩容
    if (minCapacity - elementData.length > 0)
        grow(minCapacity);
}

private void grow(int minCapacity) {
    int oldCapacity = elementData.length;
    // 核心：新容量 = 旧容量 + 旧容量 / 2（即1.5倍）
    int newCapacity = oldCapacity + (oldCapacity >> 1);
    
    // 如果1.5倍还不够，直接使用需要的容量
    if (newCapacity - minCapacity < 0)
        newCapacity = minCapacity;
    
    // 如果超过最大容量限制，处理为最大值
    if (newCapacity - MAX_ARRAY_SIZE > 0)
        newCapacity = hugeCapacity(minCapacity);
    
    // 创建新数组并复制元素
    elementData = Arrays.copyOf(elementData, newCapacity);
}
```

## 扩容规则详解

### 1. 初始化阶段

```java
// 情况1：无参构造
List<String> list1 = new ArrayList<>();
// 此时 elementData = {}，容量为0
// 添加第一个元素时，扩容为 DEFAULT_CAPACITY = 10

// 情况2：指定容量
List<String> list2 = new ArrayList<>(20);
// 此时 elementData = new Object[20]，容量为20

// 情况3：使用集合初始化
List<String> list3 = new ArrayList<>(Arrays.asList("a", "b", "c"));
// 容量等于集合大小，这里为3
```

### 2. 扩容倍数：1.5倍

```java
// 旧容量右移1位，相当于除以2
int newCapacity = oldCapacity + (oldCapacity >> 1);

// 示例：
// oldCapacity = 10，newCapacity = 10 + 5 = 15
// oldCapacity = 15，newCapacity = 15 + 7 = 22
// oldCapacity = 22，newCapacity = 22 + 11 = 33
```

**为什么是1.5倍而不是2倍？**
- **内存利用率**：1.5倍比2倍更节省空间
- **性能权衡**：减少扩容次数的同时避免空间浪费
- **内存回收**：扩容后的旧数组可能被后续扩容的新数组复用（1.5倍的数学特性）

### 3. 特殊情况处理

```java
// 情况1：批量添加导致1.5倍不够
List<Integer> list = new ArrayList<>(10);
List<Integer> bigList = new ArrayList<>(Collections.nCopies(100, 1));
list.addAll(bigList);  // 直接扩容到需要的容量，而不是1.5倍

// 情况2：超过最大容量
// MAX_ARRAY_SIZE = Integer.MAX_VALUE - 8
// 超过时会抛出 OutOfMemoryError
```

## 性能优化建议

### 1. 预估容量，避免频繁扩容

```java
// 不推荐：频繁扩容
List<Integer> list1 = new ArrayList<>();
for (int i = 0; i < 10000; i++) {
    list1.add(i);  // 会扩容多次：10 -> 15 -> 22 -> 33 -> 49 -> ...
}

// 推荐：预设容量
List<Integer> list2 = new ArrayList<>(10000);
for (int i = 0; i < 10000; i++) {
    list2.add(i);  // 不需要扩容
}
```

### 2. 容量计算公式

```java
// 如果已知元素数量 n，建议初始容量设置为：
int initialCapacity = (int) (n / 0.75) + 1;

// 例如预计存储1000个元素
List<String> list = new ArrayList<>((int) (1000 / 0.75) + 1);
```

### 3. 使用 trimToSize 释放多余空间

```java
List<Integer> list = new ArrayList<>(1000);
// 只添加了100个元素
for (int i = 0; i < 100; i++) {
    list.add(i);
}
// 释放多余的900个空间
list.trimToSize();
```

## 扩容过程图解

```
初始状态（无参构造）：
elementData = {}，capacity = 0

添加第1个元素：
elementData = [e1, null, null, ..., null]，capacity = 10

添加第11个元素（触发扩容）：
1. oldCapacity = 10
2. newCapacity = 10 + 5 = 15
3. 创建新数组：new Object[15]
4. 复制元素：System.arraycopy()
5. elementData = [e1, e2, ..., e11, null, null, null, null]

添加第16个元素（再次扩容）：
1. oldCapacity = 15
2. newCapacity = 15 + 7 = 22
3. 依此类推...
```

## 面试答题总结

**标准答案**：
1. **初始容量**：无参构造的 ArrayList，添加第一个元素时容量扩为 **10**
2. **扩容倍数**：每次扩容为原容量的 **1.5倍**（oldCapacity + oldCapacity >> 1）
3. **扩容时机**：当 `size + 1 > elementData.length` 时触发扩容
4. **扩容操作**：创建新数组，使用 `Arrays.copyOf()` 复制元素
5. **时间复杂度**：单次扩容 O(n)，但摊销复杂度为 O(1)

**加分项**：
- 说明为什么是1.5倍而不是2倍（内存利用率和性能权衡）
- 提到 `ensureCapacity()` 方法可以手动扩容
- 建议预估容量以避免频繁扩容
- 提到 `MAX_ARRAY_SIZE = Integer.MAX_VALUE - 8` 的限制
- 扩容过程中的 `modCount++` 用于快速失败机制（fail-fast）

**实际应用**：
```java
// 最佳实践：预估容量
List<User> users = new ArrayList<>(expectedSize);

// 避免：使用默认容量存储大量数据
List<User> users = new ArrayList<>(); // 会多次扩容
```

