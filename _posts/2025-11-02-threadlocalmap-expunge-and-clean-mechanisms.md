---
layout: post
title: "探测式清理和启发式清理"
date: 2025-11-02
description: "深入剖析ThreadLocalMap的两种清理机制：expungeStaleEntry探测式清理与cleanSomeSlots启发式清理"
author: "wuxl"
categories: [并发编程]
tags: [ThreadLocalMap, 内存管理, GC, 清理机制]
---

## 问题

ThreadLocalMap的探测式清理和启发式清理是什么？

## 答案

### 核心概念

ThreadLocalMap提供了两种清理过期Entry（key为null）的机制：

- **探测式清理（Expunge Stale Entry）**：从指定位置开始，**连续向后清理**，直到遇到null
- **启发式清理（Heuristic Clean）**：从指定位置开始，**跳跃式采样清理**，控制扫描次数

### 探测式清理（expungeStaleEntry）

**触发时机**：
- get()未命中时
- set()遇到过期Entry时
- remove()删除Entry时
- rehash()扩容前全量清理

**核心源码**：

```java
// slotToExpunge: 开始清理的索引位置
private int expungeStaleEntry(int staleSlot) {
    Entry[] tab = table;
    int len = tab.length;

    // 1. 清理当前位置的Entry
    tab[staleSlot].value = null;  // help GC
    tab[staleSlot] = null;
    size--;

    Entry e;
    int i;

    // 2. 从下一个位置开始，连续向后扫描
    for (i = nextIndex(staleSlot, len);
         (e = tab[i]) != null;  // 遇到null停止
         i = nextIndex(i, len)) {

        ThreadLocal<?> k = e.get();

        if (k == null) {
            // 2.1 发现过期Entry，清理
            e.value = null;
            tab[i] = null;
            size--;
        } else {
            // 2.2 有效Entry，重新hash（优化分布）
            int h = k.threadLocalHashCode & (len - 1);
            if (h != i) {
                // 当前位置不是理想位置，需要重新hash
                tab[i] = null;

                // 从理想位置开始，线性探测找空位
                while (tab[h] != null)
                    h = nextIndex(h, len);
                tab[h] = e;
            }
        }
    }

    return i;  // 返回遇到null的位置
}
```

**工作流程图**：

```
初始状态（staleSlot=3）:
┌───┬───┬───┬─────┬─────┬─────┬───┬───┬───┬───┐
│ 0 │ 1 │ 2 │ tl1 │ tl2 │ tl3 │ 6 │ 7 │ 8 │ 9 │
│   │   │   │(null)│(valid)│(null)│   │   │   │   │
└───┴───┴───┴─────┴─────┴─────┴───┴───┴───┴───┘
                ↑ 开始清理

清理过程:
1. 清理table[3]（tl1的key为null）
2. 检查table[4]（tl2有效，检查是否需要rehash）
3. 清理table[5]（tl3的key为null）
4. 检查table[6]（null，停止）

清理后:
┌───┬───┬───┬───┬─────┬───┬───┬───┬───┬───┐
│ 0 │ 1 │ 2 │   │ tl2 │   │   │   │   │   │
└───┴───┴───┴───┴─────┴───┴───┴───┴───┴───┘
```

**关键特性**：

1. **连续扫描**：一直向后扫描，直到遇到null才停止
2. **rehash优化**：清理过程中会调整有效Entry的位置，优化分布
3. **彻底清理**：保证从起点到null之间的所有过期Entry都被清理

### 启发式清理（cleanSomeSlots）

**触发时机**：
- set()插入新Entry后
- replaceStaleEntry()替换过期Entry后

**核心源码**：

```java
// i: 开始扫描的位置（已知无过期Entry）
// n: 控制扫描次数的参数（通常是size）
private boolean cleanSomeSlots(int i, int n) {
    boolean removed = false;
    Entry[] tab = table;
    int len = tab.length;

    do {
        i = nextIndex(i, len);  // 跳到下一个位置
        Entry e = tab[i];

        if (e != null && e.get() == null) {
            // 发现过期Entry
            n = len;  // 重置扫描次数为容量
            removed = true;
            i = expungeStaleEntry(i);  // 调用探测式清理
        }
    } while ((n >>>= 1) != 0);  // 扫描次数减半，直到为0

    return removed;  // 返回是否清理过Entry
}
```

**扫描次数计算**：

```
初始n = size（元素数量）
第1轮: n = size, 扫描1个位置
第2轮: n = size/2, 扫描1个位置
第3轮: n = size/4, 扫描1个位置
...
第k轮: n = size/2^k = 0, 停止

总扫描次数 ≈ log2(size)
```

**示例**：

```
初始状态（size=16，i=5）:
┌───┬───┬───┬───┬───┬─────┬───┬─────┬───┬───┬───┬───┬───┬───┬───┬───┐
│ 0 │ 1 │ 2 │ 3 │ 4 │  5  │ 6 │  7  │ 8 │ 9 │10 │11 │12 │13 │14 │15 │
│   │   │   │tl1│   │(start)│   │(null)│   │   │   │   │   │   │   │   │
└───┴───┴───┴───┴───┴─────┴───┴─────┴───┴───┴───┴───┴───┴───┴───┴───┘

扫描过程（n初始=16）:
1. i=6, n=16, tab[6]有效 → n=8
2. i=7, n=8,  tab[7]的key为null → 发现过期Entry!
   - 调用expungeStaleEntry(7)
   - n重置为len(16)
   - removed = true
3. i=继续从expungeStaleEntry返回的位置, n=16
4. i=..., n=8
5. i=..., n=4
6. i=..., n=2
7. i=..., n=1
8. n=0, 停止

总扫描次数: log2(16) ≈ 4-5次（如果发现过期Entry会重置）
```

**关键特性**：

1. **对数级扫描**：扫描次数为O(log n)，避免全量扫描
2. **跳跃式采样**：不是连续扫描，而是跳跃检查
3. **动态调整**：发现过期Entry后，重置扫描次数为容量，提高清理覆盖率
4. **快速失败**：大部分情况下快速返回，性能好

### 两种清理机制对比

| 维度 | 探测式清理 | 启发式清理 |
|------|----------|----------|
| **扫描方式** | 连续向后，直到null | 跳跃式采样 |
| **扫描次数** | 不确定（取决于null位置） | O(log n) |
| **清理彻底性** | ✅ 彻底（起点到null之间全部清理） | ❌ 部分清理 |
| **性能** | 慢（可能扫描整个数组） | 快（对数级） |
| **触发时机** | get/set遇到过期Entry | set插入后 |
| **是否rehash** | ✅ 重新调整Entry位置 | ❌ 不调整 |

### 配合使用场景

**场景1：set()方法**

```java
private void set(ThreadLocal<?> key, Object value) {
    Entry[] tab = table;
    int len = tab.length;
    int i = key.threadLocalHashCode & (len - 1);

    for (Entry e = tab[i]; e != null; e = tab[i = nextIndex(i, len)]) {
        ThreadLocal<?> k = e.get();

        if (k == key) {
            e.value = value;
            return;
        }

        if (k == null) {
            // 情况1：遇到过期Entry，调用探测式清理
            replaceStaleEntry(key, value, i);
            return;
        }
    }

    // 插入新Entry
    tab[i] = new Entry(key, value);
    int sz = ++size;

    // 情况2：插入后，调用启发式清理
    if (!cleanSomeSlots(i, sz) && sz >= threshold)
        rehash();
}
```

**场景2：get()方法**

```java
private Entry getEntry(ThreadLocal<?> key) {
    int i = key.threadLocalHashCode & (table.length - 1);
    Entry e = table[i];

    if (e != null && e.get() == key)
        return e;
    else
        return getEntryAfterMiss(key, i, e);
}

private Entry getEntryAfterMiss(ThreadLocal<?> key, int i, Entry e) {
    Entry[] tab = table;
    int len = tab.length;

    while (e != null) {
        ThreadLocal<?> k = e.get();
        if (k == key)
            return e;
        if (k == null)
            expungeStaleEntry(i);  // 调用探测式清理
        else
            i = nextIndex(i, len);
        e = tab[i];
    }
    return null;
}
```

### replaceStaleEntry详解

**综合运用两种清理机制的典型代码**：

```java
private void replaceStaleEntry(ThreadLocal<?> key, Object value, int staleSlot) {
    Entry[] tab = table;
    int len = tab.length;
    Entry e;

    int slotToExpunge = staleSlot;  // 记录需要清理的起始位置

    // 1. 向前扫描，找到最早的过期Entry
    for (int i = prevIndex(staleSlot, len);
         (e = tab[i]) != null;
         i = prevIndex(i, len))
        if (e.get() == null)
            slotToExpunge = i;

    // 2. 向后扫描，查找key或过期Entry
    for (int i = nextIndex(staleSlot, len);
         (e = tab[i]) != null;
         i = nextIndex(i, len)) {

        ThreadLocal<?> k = e.get();

        if (k == key) {
            // 找到相同key，交换位置并更新value
            e.value = value;
            tab[i] = tab[staleSlot];
            tab[staleSlot] = e;

            // 如果前面没有发现过期Entry，从当前位置开始清理
            if (slotToExpunge == staleSlot)
                slotToExpunge = i;
            // 先探测式清理，再启发式清理
            cleanSomeSlots(expungeStaleEntry(slotToExpunge), len);
            return;
        }

        if (k == null && slotToExpunge == staleSlot)
            slotToExpunge = i;
    }

    // 3. 未找到相同key，直接替换过期Entry
    tab[staleSlot].value = null;
    tab[staleSlot] = new Entry(key, value);

    // 如果发现了其他过期Entry，清理
    if (slotToExpunge != staleSlot)
        cleanSomeSlots(expungeStaleEntry(slotToExpunge), len);
}
```

### 清理效率分析

**时间复杂度**：

| 操作 | 时间复杂度 |
|------|----------|
| expungeStaleEntry | O(n)（最坏遍历整个数组） |
| cleanSomeSlots | O(log n) |
| 全量清理（expungeStaleEntries） | O(n) |

**实际性能**：

```java
// 测试场景：容量1024，100个ThreadLocal
expungeStaleEntry: 扫描约50-200个位置（取决于null位置）
cleanSomeSlots: 扫描约10-20个位置（log2(1024)=10）
```

### 为什么需要两种清理机制？

**设计权衡**：

1. **探测式清理**：
   - 优点：彻底，优化Entry分布
   - 缺点：可能扫描整个数组，性能差

2. **启发式清理**：
   - 优点：快速，对数级扫描
   - 缺点：可能遗漏部分过期Entry

**组合使用**：
- 常规操作：先用启发式清理快速采样
- 发现过期Entry：再用探测式清理彻底清理
- 扩容前：全量探测式清理，确保准确性

### 实际案例

**内存泄漏风险场景**：

```java
// 糟糕的代码
for (int i = 0; i < 1000; i++) {
    ThreadLocal<BigObject> tl = new ThreadLocal<>();  // 局部变量
    tl.set(new BigObject(1024 * 1024));  // 10MB
    // 方法结束，tl出栈，ThreadLocal对象失去强引用
    // Entry的key变为null，但value仍存在
}
// 如果启发式清理未覆盖所有过期Entry，会导致内存泄漏
```

**依赖清理机制的风险**：
- 启发式清理可能遗漏部分过期Entry
- 探测式清理只在特定操作时触发
- **最佳实践：主动调用remove()，不依赖自动清理**

### 面试答题要点

1. **探测式清理**：从指定位置连续向后扫描，直到遇到null，彻底清理且会rehash优化分布
2. **启发式清理**：跳跃式采样，扫描次数O(log n)，快速但可能遗漏
3. **配合使用**：启发式清理快速采样，发现问题后调用探测式清理彻底处理
4. **触发时机**：探测式在遇到过期Entry时触发，启发式在插入后触发
5. **不能完全依赖**：清理机制是惰性的，最佳实践是主动调用remove()
