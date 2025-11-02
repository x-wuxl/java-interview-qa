---
layout: post
title: "ThreadLocalMap的数据结构"
date: 2025-11-02
description: "深入剖析ThreadLocalMap的底层数据结构、Entry设计及与HashMap的区别"
author: "wuxl"
categories: [并发编程]
tags: [ThreadLocalMap, 数据结构, 弱引用, 线性探测]
---

## 问题

ThreadLocalMap的数据结构是怎样的？

## 答案

### 核心结构

**ThreadLocalMap是ThreadLocal的内部类**,采用**数组 + 开放地址法（线性探测）**的哈希表结构,而非链表法。

```java
static class ThreadLocalMap {
    // Entry数组，存储键值对
    private Entry[] table;

    // 实际存储的Entry数量
    private int size = 0;

    // 扩容阈值（capacity * 2/3）
    private int threshold;

    // 初始容量（必须是2的幂次）
    private static final int INITIAL_CAPACITY = 16;

    // Entry继承WeakReference，key为ThreadLocal的弱引用
    static class Entry extends WeakReference<ThreadLocal<?>> {
        Object value;  // value为强引用

        Entry(ThreadLocal<?> k, Object v) {
            super(k);  // key作为弱引用
            value = v;
        }
    }
}
```

### 与HashMap的核心区别

| 维度 | ThreadLocalMap | HashMap |
|------|---------------|---------|
| **底层结构** | Entry数组（开放地址法） | Node数组 + 链表/红黑树 |
| **冲突解决** | 线性探测法（向后查找空位） | 链表法 + 红黑树优化 |
| **key类型** | WeakReference<ThreadLocal<?>> | 强引用 |
| **初始容量** | 16 | 16 |
| **扩容阈值** | capacity * 2/3 | capacity * 0.75 |
| **扩容倍数** | 2倍 | 2倍 |
| **线程安全** | 非线程安全（单线程使用） | 非线程安全 |

### Entry结构设计

**为什么Entry继承WeakReference？**

```java
static class Entry extends WeakReference<ThreadLocal<?>> {
    Object value;

    Entry(ThreadLocal<?> k, Object v) {
        super(k);  // 将ThreadLocal对象作为弱引用
        value = v; // value是强引用
    }
}
```

**引用关系示意图**：

```
Thread对象（强引用）
  ↓
ThreadLocalMap（强引用）
  ↓
Entry[] table（强引用）
  ↓
Entry extends WeakReference<ThreadLocal>
  ↓ 弱引用
ThreadLocal对象 ← 外部强引用（如果置为null，则只剩弱引用）
  ↓ 强引用
value对象
```

**设计目的**：
1. 外部ThreadLocal对象置为null后，下次GC时ThreadLocal对象可以被回收
2. Entry的key变为null，ThreadLocalMap在set/get/remove时会清理这些过期Entry
3. 如果key是强引用，即使外部ThreadLocal置为null，Entry仍持有强引用，导致内存泄漏

### 哈希算法

**魔数0x61c88647（斐波那契散列）**：

```java
private final int threadLocalHashCode = nextHashCode();

private static AtomicInteger nextHashCode = new AtomicInteger();

// 魔数：黄金分割比的整数形式
private static final int HASH_INCREMENT = 0x61c88647;

private static int nextHashCode() {
    return nextHashCode.getAndAdd(HASH_INCREMENT);
}
```

**计算索引位置**：

```java
int i = key.threadLocalHashCode & (len - 1);
```

**魔数的作用**：
- 0x61c88647 ≈ 2^32 * (√5 - 1) / 2（黄金分割比）
- 能够在2的幂次容量下实现**均匀分布**，减少哈希冲突
- 即使连续创建多个ThreadLocal，也能避免聚集

**示例**：容量为16时的分布

```java
// 连续创建5个ThreadLocal的索引分布
ThreadLocal1: 0x61c88647 & 15 = 7
ThreadLocal2: 0xc3910c8e & 15 = 14
ThreadLocal3: 0x2559f0d5 & 15 = 5
ThreadLocal4: 0x8722d51c & 15 = 12
ThreadLocal5: 0xe8ebb963 & 15 = 3

// 分布均匀，冲突少
```

### 数组结构示意图

```
table数组（初始容量16）:
┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│  0  │  1  │  2  │  3  │  4  │  5  │  6  │  7  │
├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│null │null │Entry│null │null │Entry│null │Entry│
│     │     │ ↓   │     │     │ ↓   │     │ ↓   │
│     │     │k:TL1│     │     │k:TL2│     │k:TL3│
│     │     │v:obj│     │     │v:obj│     │v:obj│
└─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘

┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
│  8  │  9  │ 10  │ 11  │ 12  │ 13  │ 14  │ 15  │
├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│null │null │null │null │Entry│null │Entry│null │
│     │     │     │     │ ↓   │     │ ↓   │     │
│     │     │     │     │k:TL4│     │k:TL5│     │
│     │     │     │     │v:obj│     │v:obj│     │
└─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
```

### 线性探测法（开放地址法）

**冲突解决流程**：

```java
private void set(ThreadLocal<?> key, Object value) {
    Entry[] tab = table;
    int len = tab.length;
    int i = key.threadLocalHashCode & (len - 1);  // 计算初始位置

    // 线性探测：从初始位置向后查找
    for (Entry e = tab[i];
         e != null;
         e = tab[i = nextIndex(i, len)]) {  // 循环递增索引

        ThreadLocal<?> k = e.get();

        if (k == key) {
            e.value = value;  // 找到相同key，更新value
            return;
        }

        if (k == null) {
            replaceStaleEntry(key, value, i);  // key已被GC，替换过期Entry
            return;
        }
    }

    tab[i] = new Entry(key, value);  // 找到空位，插入新Entry
    int sz = ++size;

    if (!cleanSomeSlots(i, sz) && sz >= threshold)
        rehash();  // 超过阈值，扩容
}

// 计算下一个索引（循环）
private static int nextIndex(int i, int len) {
    return ((i + 1 < len) ? i + 1 : 0);
}
```

**冲突场景示例**：

```
初始状态:
table[5] = Entry(TL1, "value1")

新增ThreadLocal2，hash计算结果也是5（冲突）:
1. 检查table[5]，已被占用，k != key
2. i = nextIndex(5, 16) = 6，检查table[6]
3. table[6]为null，插入Entry(TL2, "value2")

最终结果:
table[5] = Entry(TL1, "value1")
table[6] = Entry(TL2, "value2")  ← 线性探测找到的位置
```

### 为什么使用开放地址法而非链表法？

**原因**：
1. **ThreadLocal数量少**：一般一个线程只有几个ThreadLocal，冲突概率低
2. **缓存友好**：数组连续存储，CPU缓存命中率高
3. **避免链表开销**：无需额外的Node对象，减少内存占用
4. **配合魔数**：0x61c88647保证均匀分布，冲突更少

**HashMap使用链表法的原因**：
- HashMap的key数量可能很多，冲突概率高
- 链表法扩展性更好，单个槽位可以存储多个元素
- 红黑树优化后，单链表长度过长时性能仍可控

### get()方法的实现

```java
private Entry getEntry(ThreadLocal<?> key) {
    int i = key.threadLocalHashCode & (table.length - 1);
    Entry e = table[i];

    if (e != null && e.get() == key) {
        return e;  // 直接命中
    } else {
        return getEntryAfterMiss(key, i, e);  // 未命中，线性探测
    }
}

private Entry getEntryAfterMiss(ThreadLocal<?> key, int i, Entry e) {
    Entry[] tab = table;
    int len = tab.length;

    while (e != null) {
        ThreadLocal<?> k = e.get();
        if (k == key)
            return e;  // 找到
        if (k == null)
            expungeStaleEntry(i);  // 清理过期Entry
        else
            i = nextIndex(i, len);  // 继续向后查找
        e = tab[i];
    }
    return null;  // 未找到
}
```

### remove()方法的实现

```java
private void remove(ThreadLocal<?> key) {
    Entry[] tab = table;
    int len = tab.length;
    int i = key.threadLocalHashCode & (len - 1);

    for (Entry e = tab[i]; e != null; e = tab[i = nextIndex(i, len)]) {
        if (e.get() == key) {
            e.clear();  // 清除弱引用（key置为null）
            expungeStaleEntry(i);  // 清理当前Entry及后续过期Entry
            return;
        }
    }
}
```

### 内存布局

**单个Entry的内存占用**（64位JVM，开启压缩指针）：

```
Entry对象:
- 对象头: 12字节（markword 8字节 + klass 4字节）
- WeakReference.referent: 4字节（指向ThreadLocal）
- value: 4字节（指向实际对象）
- 对齐填充: 4字节
总计: 24字节
```

**table数组**（初始容量16）：
- 数组对象头：16字节
- 16个引用：16 * 4 = 64字节
- 总计：80字节

**完整ThreadLocalMap**（假设存储3个Entry）：
- ThreadLocalMap对象：约40字节
- table数组：80字节
- 3个Entry：3 * 24 = 72字节
- **总计：约192字节**

### 关键设计特点总结

| 特点 | 说明 |
|------|------|
| **弱引用key** | 允许ThreadLocal对象被GC回收 |
| **线性探测** | 简单高效，适合元素少的场景 |
| **魔数哈希** | 0x61c88647实现均匀分布 |
| **惰性清理** | 在set/get/remove时清理过期Entry |
| **低负载因子** | 2/3阈值，保证较低冲突率 |
| **无锁设计** | 单线程使用，无需同步 |

### 面试答题要点

1. **核心结构**：Entry数组 + 线性探测法，Entry的key为WeakReference<ThreadLocal>
2. **与HashMap区别**：使用开放地址法而非链表法，适合元素少的场景
3. **哈希算法**：使用魔数0x61c88647（斐波那契散列）实现均匀分布
4. **弱引用设计**：允许ThreadLocal对象被GC，配合惰性清理避免内存泄漏
5. **冲突解决**：线性探测向后查找空位，找到null或相同key时停止
