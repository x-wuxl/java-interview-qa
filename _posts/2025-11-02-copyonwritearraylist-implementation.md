---
layout: post
title: "CopyOnWriteArrayList是如何实现的？"
date: 2025-11-02
description: "深入解析CopyOnWriteArrayList的写时复制机制，包括ReentrantLock保证写安全、volatile数组保证读可见性，以及适用的读多写少场景"
author: "wuxl"
categories: [集合框架, 并发编程]
tags: [CopyOnWriteArrayList, 写时复制, COW, 并发集合, 线程安全]
---

## 问题

CopyOnWriteArrayList是如何实现的？

## 答案

### 一、核心概念

CopyOnWriteArrayList 是 Java 并发包提供的**线程安全的 ArrayList**，采用**写时复制（Copy-On-Write, COW）**策略：

- **读操作**：无锁，直接读取
- **写操作**：加锁，复制整个数组后修改，再替换原数组

### 二、底层实现

#### 1. 核心字段

```java
public class CopyOnWriteArrayList<E> implements List<E> {
    // 可重入锁，保护所有写操作
    final transient ReentrantLock lock = new ReentrantLock();

    // volatile修饰的数组引用，保证可见性
    private transient volatile Object[] array;

    // 获取数组
    final Object[] getArray() {
        return array;
    }

    // 设置数组
    final void setArray(Object[] a) {
        array = a;
    }
}
```

**关键点**：
- `ReentrantLock`：保证写操作互斥
- `volatile array`：保证数组引用的可见性（写线程修改后，读线程立即可见）

#### 2. 读操作（无锁）

```java
public E get(int index) {
    return get(getArray(), index);
}

private E get(Object[] a, int index) {
    return (E) a[index];
}
```

**特点**：
- 直接读取当前数组，**不加锁**
- 通过 volatile 保证读取到最新的数组引用
- 性能极高，适合读多的场景

#### 3. 写操作（写时复制）

```java
public boolean add(E e) {
    final ReentrantLock lock = this.lock;
    lock.lock();  // 加锁
    try {
        Object[] elements = getArray();
        int len = elements.length;

        // 复制原数组，长度+1
        Object[] newElements = Arrays.copyOf(elements, len + 1);

        // 在新数组上修改
        newElements[len] = e;

        // 替换原数组引用
        setArray(newElements);
        return true;
    } finally {
        lock.unlock();  // 释放锁
    }
}

public E set(int index, E element) {
    final ReentrantLock lock = this.lock;
    lock.lock();
    try {
        Object[] elements = getArray();
        E oldValue = get(elements, index);

        if (oldValue != element) {
            int len = elements.length;
            // 复制整个数组
            Object[] newElements = Arrays.copyOf(elements, len);
            newElements[index] = element;
            setArray(newElements);
        }
        return oldValue;
    } finally {
        lock.unlock();
    }
}
```

**写操作步骤**：
1. 加 ReentrantLock 锁
2. 复制当前数组（`Arrays.copyOf`）
3. 在新数组上进行修改
4. 将新数组赋值给 volatile 修饰的 array 引用
5. 释放锁

#### 4. 迭代器（快照迭代）

```java
public Iterator<E> iterator() {
    return new COWIterator<E>(getArray(), 0);
}

static final class COWIterator<E> implements ListIterator<E> {
    private final Object[] snapshot;  // 迭代器创建时的数组快照
    private int cursor;

    private COWIterator(Object[] elements, int initialCursor) {
        cursor = initialCursor;
        snapshot = elements;  // 持有创建时的数组引用
    }

    public E next() {
        return (E) snapshot[cursor++];
    }
}
```

**特点**：
- 迭代器持有创建时的数组快照
- 遍历过程中不会抛出 `ConcurrentModificationException`
- 无法通过迭代器修改元素（`remove()`、`set()` 不支持）

### 三、线程安全保证

#### 1. 写-写互斥

```java
// 线程A和线程B同时写
// 通过ReentrantLock保证互斥，只有一个能获取锁
lock.lock();  // 同一时刻只有一个写线程
```

#### 2. 读-写分离

```java
// 线程A读，线程B写
// 线程A读取旧数组，线程B在新数组上写，互不影响
// 写完成后，线程A下次读取会看到新数组（volatile保证）
```

#### 3. 可见性保证

```java
// volatile修饰的数组引用
private transient volatile Object[] array;

// 写线程：
setArray(newElements);  // volatile写，刷新到主内存

// 读线程：
getArray();  // volatile读，从主内存读取最新引用
```

### 四、优缺点分析

#### 优点

1. **读操作无锁**：读性能极高，适合读多写少场景
2. **线程安全**：读写分离，无需额外同步
3. **迭代安全**：迭代器不会抛出并发修改异常
4. **实现简单**：相比读写锁等方案更易理解

#### 缺点

1. **内存占用高**：每次写操作都复制整个数组
2. **写性能差**：复制数组开销大，不适合写多场景
3. **数据一致性**：读操作可能读到旧数据（最终一致性）

```java
// 场景示例：
Thread A: list.add("A");  // 复制数组，新数组包含"A"
Thread B: list.get(0);    // 可能读到旧数组（不包含"A"）
```

### 五、适用场景

#### 适合

```java
// 1. 黑名单/白名单（读多写少）
CopyOnWriteArrayList<String> blacklist = new CopyOnWriteArrayList<>();

// 2. 事件监听器列表
CopyOnWriteArrayList<Listener> listeners = new CopyOnWriteArrayList<>();

// 3. 配置信息（偶尔更新，频繁读取）
CopyOnWriteArrayList<Config> configs = new CopyOnWriteArrayList<>();
```

#### 不适合

```java
// 1. 写操作频繁的场景
// 2. 数据量大的场景（复制开销大）
// 3. 实时一致性要求高的场景
```

### 六、对比其他并发集合

| 集合 | 读操作 | 写操作 | 适用场景 |
|-----|--------|--------|----------|
| **CopyOnWriteArrayList** | 无锁 | 加锁+复制数组 | 读多写少 |
| **Collections.synchronizedList** | 加锁 | 加锁 | 读写均衡 |
| **Vector** | 加锁 | 加锁 | 遗留实现 |

### 七、答题总结

CopyOnWriteArrayList 通过以下机制实现线程安全：

1. **核心思想**：写时复制，读写分离
2. **数据结构**：volatile 修饰的 Object 数组
3. **读操作**：无锁，直接读取，性能极高
4. **写操作**：ReentrantLock 加锁，复制数组后修改，再替换引用
5. **迭代器**：持有数组快照，遍历期间不受写操作影响
6. **适用场景**：读多写少、数据量不大、允许短暂数据不一致

**面试要点**：强调"写时复制"机制、volatile 保证可见性、适用于读多写少场景，以及内存和性能的权衡。
