---
layout: post
title: "ArrayList扩容机制详解：初始容量与1.5倍扩容"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [ArrayList, 扩容机制, 源码分析, JDK]
description: "详细解析ArrayList扩容机制：添加第一个元素时容量扩为10，每次按1.5倍扩容的原理和实现"
---

## 核心概念

ArrayList 的扩容机制是一个精心设计的过程：
- **首次扩容**：无参构造的 ArrayList，添加第一个元素时，容量从 0 扩展到 **10**
- **后续扩容**：每次扩容为原容量的 **1.5 倍**（`oldCapacity + oldCapacity >> 1`）
- **目的**：在内存占用和性能之间取得平衡

## 扩容机制完整流程

### 1. 初始化阶段

```java
public class ArrayList<E> extends AbstractList<E> {
    // 默认初始容量
    private static final int DEFAULT_CAPACITY = 10;
    
    // 共享的空数组实例（用于无参构造）
    private static final Object[] DEFAULTCAPACITY_EMPTY_ELEMENTDATA = {};
    
    // 存储元素的数组
    transient Object[] elementData;
    
    // 实际元素个数
    private int size;
    
    // 无参构造函数
    public ArrayList() {
        // 初始化为空数组，延迟到第一次 add 时再分配
        this.elementData = DEFAULTCAPACITY_EMPTY_ELEMENTDATA;
    }
    
    // 指定容量的构造函数
    public ArrayList(int initialCapacity) {
        if (initialCapacity > 0) {
            this.elementData = new Object[initialCapacity];
        } else if (initialCapacity == 0) {
            this.elementData = EMPTY_ELEMENTDATA;
        } else {
            throw new IllegalArgumentException("Illegal Capacity: " + initialCapacity);
        }
    }
}
```

**初始状态**：
```java
List<String> list = new ArrayList<>();
// 此时：elementData = {}，capacity = 0，size = 0
// 注意：这里使用空数组，而不是直接创建长度为10的数组（延迟初始化优化）
```

### 2. 第一次添加元素：扩容到10

```java
// 添加元素的入口
public boolean add(E e) {
    ensureCapacityInternal(size + 1);  // size + 1 = 0 + 1 = 1
    elementData[size++] = e;
    return true;
}

// 确保内部容量足够
private void ensureCapacityInternal(int minCapacity) {
    ensureExplicitCapacity(calculateCapacity(elementData, minCapacity));
}

// 计算所需容量
private static int calculateCapacity(Object[] elementData, int minCapacity) {
    // 如果是默认的空数组（无参构造）
    if (elementData == DEFAULTCAPACITY_EMPTY_ELEMENTDATA) {
        // 返回 DEFAULT_CAPACITY(10) 和 minCapacity(1) 中的较大值
        return Math.max(DEFAULT_CAPACITY, minCapacity);  // 返回 10
    }
    return minCapacity;
}

// 确保容量并执行扩容
private void ensureExplicitCapacity(int minCapacity) {
    modCount++;  // 修改次数+1（用于快速失败）
    
    // 如果需要的容量 > 当前数组长度，触发扩容
    if (minCapacity - elementData.length > 0)  // 10 - 0 > 0，触发扩容
        grow(minCapacity);
}

// 执行扩容
private void grow(int minCapacity) {
    int oldCapacity = elementData.length;  // 0
    int newCapacity = oldCapacity + (oldCapacity >> 1);  // 0 + 0 = 0
    
    // 如果新容量还不够，使用 minCapacity
    if (newCapacity - minCapacity < 0)  // 0 - 10 < 0
        newCapacity = minCapacity;  // newCapacity = 10
    
    // 检查是否超过最大容量
    if (newCapacity - MAX_ARRAY_SIZE > 0)
        newCapacity = hugeCapacity(minCapacity);
    
    // 创建新数组并复制元素
    elementData = Arrays.copyOf(elementData, newCapacity);
    // 此时：elementData = new Object[10]
}
```

**第一次添加后的状态**：
```java
list.add("first");
// 结果：elementData = ["first", null, null, ..., null]
//      capacity = 10，size = 1
```

### 3. 后续扩容：1.5倍机制

```java
// 当添加第11个元素时触发扩容
list.add("11th element");

// 扩容过程
private void grow(int minCapacity) {
    int oldCapacity = elementData.length;  // 10
    
    // 核心：右移1位相当于除以2，即增长50%
    int newCapacity = oldCapacity + (oldCapacity >> 1);
    // newCapacity = 10 + (10 >> 1) = 10 + 5 = 15
    
    if (newCapacity - minCapacity < 0)
        newCapacity = minCapacity;
    
    if (newCapacity - MAX_ARRAY_SIZE > 0)
        newCapacity = hugeCapacity(minCapacity);
    
    // 创建长度为15的新数组并复制元素
    elementData = Arrays.copyOf(elementData, newCapacity);
}
```

**扩容序列**：
```
初始：0
第1次添加：0 → 10
第11次添加：10 → 15
第16次添加：15 → 22 (15 + 7)
第23次添加：22 → 33 (22 + 11)
第34次添加：33 → 49 (33 + 16)
第50次添加：49 → 73 (49 + 24)
...
```

## 源码关键点深入分析

### 1. 为什么第一次扩容到10？

```java
// JDK 设计者认为10是一个合理的默认值
private static final int DEFAULT_CAPACITY = 10;

// 原因：
// 1. 大多数场景下存储的元素数量在10左右
// 2. 10不会占用太多内存（只有40-80字节）
// 3. 避免频繁扩容导致的性能开销
```

### 2. 为什么是1.5倍而不是2倍？

```java
// 1.5倍扩容的优势

// 计算方式：oldCapacity + (oldCapacity >> 1)
// 右移1位等价于除以2，效率高

// 对比2倍扩容：
// - 2倍扩容：10 → 20 → 40 → 80 → 160 → 320
//   总内存浪费：10 + 20 + 40 + 80 + 160 = 310
// - 1.5倍扩容：10 → 15 → 22 → 33 → 49 → 73
//   总内存浪费：10 + 15 + 22 + 33 + 49 = 129

// 优势1：节省内存
// 1.5倍扩容的内存利用率更高，减少空间浪费

// 优势2：有利于内存回收
// 数学性质：1.5^n 的增长速度，使得新数组可能重用之前释放的空间
// 例如：10 → 15 → 22，释放的10+15=25空间可以容纳22
```

```java
// 内存复用示例（理论上）
第1次扩容：分配 10 字节，释放 0 字节
第2次扩容：分配 15 字节，释放 10 字节
第3次扩容：分配 22 字节，释放 15 字节（可能复用前两次释放的 10+15=25字节）
第4次扩容：分配 33 字节，释放 22 字节（可能复用前三次释放的 10+15+22=47字节）
```

### 3. Arrays.copyOf 的实现

```java
public static <T> T[] copyOf(T[] original, int newLength) {
    return (T[]) copyOf(original, newLength, original.getClass());
}

public static <T,U> T[] copyOf(U[] original, int newLength, Class<? extends T[]> newType) {
    T[] copy = ((Object)newType == (Object)Object[].class)
        ? (T[]) new Object[newLength]
        : (T[]) Array.newInstance(newType.getComponentType(), newLength);
    
    // 底层调用 System.arraycopy（native 方法）
    System.arraycopy(original, 0, copy, 0,
                     Math.min(original.length, newLength));
    return copy;
}

// System.arraycopy 是 JVM 内部实现的高效内存复制
// 时间复杂度：O(n)
```

### 4. 批量添加时的特殊处理

```java
public boolean addAll(Collection<? extends E> c) {
    Object[] a = c.toArray();
    int numNew = a.length;
    // 确保容量足够容纳所有新元素
    ensureCapacityInternal(size + numNew);
    System.arraycopy(a, 0, elementData, size, numNew);
    size += numNew;
    return numNew != 0;
}

// 示例：如果当前容量10，要添加100个元素
List<Integer> list = new ArrayList<>();  // capacity = 0
list.add(1);  // capacity = 10, size = 1

List<Integer> bigList = new ArrayList<>();
for (int i = 0; i < 100; i++) {
    bigList.add(i);
}

list.addAll(bigList);  
// minCapacity = 1 + 100 = 101
// oldCapacity = 10
// newCapacity = 10 + 5 = 15 (不够)
// 最终 newCapacity = 101（直接扩容到需要的大小）
```

## 性能优化实践

### 1. 预估容量避免扩容

```java
// 场景1：明确知道数据量
List<User> users = new ArrayList<>(1000);  // 避免多次扩容

// 场景2：根据经验值估算
List<Order> orders = new ArrayList<>(initialSize * 2);

// 场景3：使用 ensureCapacity 手动扩容
List<Integer> list = new ArrayList<>();
list.ensureCapacity(5000);  // 提前扩容到5000
```

### 2. 计算最优初始容量

```java
// 如果预计存储 n 个元素，推荐初始容量：
int optimalCapacity = (int) Math.ceil(n * 1.25);

// 原因：考虑到负载因子，留一些余量
// 例如存储1000个元素：
List<String> list = new ArrayList<>(1250);
```

### 3. 释放多余空间

```java
List<Integer> list = new ArrayList<>(10000);
// 只使用了100个空间
for (int i = 0; i < 100; i++) {
    list.add(i);
}

// 释放未使用的9900个空间
list.trimToSize();  // capacity 变为 100

// trimToSize 源码
public void trimToSize() {
    modCount++;
    if (size < elementData.length) {
        elementData = (size == 0)
          ? EMPTY_ELEMENTDATA
          : Arrays.copyOf(elementData, size);
    }
}
```

## 扩容过程可视化

```
步骤1：创建 ArrayList
┌──────────────────┐
│ elementData = {} │  capacity = 0, size = 0
└──────────────────┘

步骤2：添加第1个元素
┌────────────────────────────────────────┐
│ [e1][  ][  ][  ][  ][  ][  ][  ][  ][  ] │  capacity = 10, size = 1
└────────────────────────────────────────┘

步骤3：添加到第10个元素
┌────────────────────────────────────────┐
│ [e1][e2][e3][e4][e5][e6][e7][e8][e9][e10]│  capacity = 10, size = 10
└────────────────────────────────────────┘

步骤4：添加第11个元素（触发扩容 10 → 15）
┌────────────────────────────────────────────────────────┐
│ [e1][e2][e3][e4][e5][e6][e7][e8][e9][e10][e11][  ][  ][  ][  ] │
└────────────────────────────────────────────────────────┘
capacity = 15, size = 11

步骤5：添加第16个元素（触发扩容 15 → 22）
┌──────────────────────────────────────────────────────────────────────┐
│ [e1][e2]...[e15][e16][  ][  ][  ][  ][  ][  ] │
└──────────────────────────────────────────────────────────────────────┘
capacity = 22, size = 16
```

## 面试答题总结

**标准答案**：

1. **第一次扩容**：
   - 无参构造的 ArrayList 初始化为空数组
   - 添加第一个元素时，容量扩展到 **DEFAULT_CAPACITY = 10**
   
2. **后续扩容**：
   - 扩容公式：`newCapacity = oldCapacity + (oldCapacity >> 1)`
   - 即每次扩容为原容量的 **1.5倍**
   - 扩容序列：10 → 15 → 22 → 33 → 49 → 73 → ...

3. **扩容时机**：
   - 当 `size + 1 > elementData.length` 时触发扩容

4. **扩容成本**：
   - 时间复杂度：O(n)（需要复制所有元素）
   - 空间复杂度：O(n)（需要新数组）
   - 摊销复杂度：O(1)

**加分项**：

1. **为什么是1.5倍**：
   - 相比2倍更节省内存
   - 有利于内存回收和重用
   - 平衡了扩容频率和空间利用率

2. **延迟初始化优化**：
   - 无参构造不立即分配10个空间，而是延迟到第一次 add
   - 节省不使用 ArrayList 的内存开销

3. **批量添加优化**：
   - `addAll()` 会一次性扩容到足够大小，而不是按1.5倍多次扩容

4. **最佳实践**：
   ```java
   // 推荐：预估容量
   List<String> list = new ArrayList<>(expectedSize);
   
   // 或手动扩容
   list.ensureCapacity(expectedSize);
   ```

5. **容量限制**：
   ```java
   private static final int MAX_ARRAY_SIZE = Integer.MAX_VALUE - 8;
   // 理论最大容量约 2^31 - 9 = 2,147,483,639 个元素
   ```

