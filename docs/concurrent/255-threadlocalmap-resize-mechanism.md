---
layout: default
title: "ThreadLocalMap的扩容机制"
parent: 并发编程
nav_order: 255
description: "详解ThreadLocalMap的扩容时机、rehash过程及与HashMap扩容的差异"
author: "wuxl"
date: 2025-11-02
---
## 问题

ThreadLocalMap的扩容机制是怎样的？

## 答案

### 核心参数

```java
static class ThreadLocalMap {
    // 初始容量（必须是2的幂次）
    private static final int INITIAL_CAPACITY = 16;

    // Entry数组
    private Entry[] table;

    // 实际存储的Entry数量
    private int size = 0;

    // 扩容阈值（len * 2 / 3）
    private int threshold;

    // 设置扩容阈值
    private void setThreshold(int len) {
        threshold = len * 2 / 3;
    }
}
```

### 扩容触发条件

**触发时机**：

```java
private void set(ThreadLocal<?> key, Object value) {
    // ... 查找逻辑

    tab[i] = new Entry(key, value);
    int sz = ++size;

    // 触发条件：清理失败 && size >= threshold
    if (!cleanSomeSlots(i, sz) && sz >= threshold)
        rehash();
}
```

**两个条件（同时满足）**：
1. **cleanSomeSlots()返回false**：启发式清理未发现过期Entry
2. **size >= threshold**：元素数量达到阈值（capacity * 2/3）

### 完整扩容流程

```java
private void rehash() {
    // 第1步：清理所有过期Entry
    expungeStaleEntries();

    // 第2步：清理后仍超过3/4阈值，则扩容
    // threshold - threshold / 4 = 3/4 * threshold = 1/2 * capacity
    if (size >= threshold - threshold / 4)
        resize();
}

// 清理所有过期Entry
private void expungeStaleEntries() {
    Entry[] tab = table;
    int len = tab.length;
    for (int j = 0; j < len; j++) {
        Entry e = tab[j];
        if (e != null && e.get() == null)
            expungeStaleEntry(j);  // 探测式清理
    }
}

// 扩容为原来的2倍
private void resize() {
    Entry[] oldTab = table;
    int oldLen = oldTab.length;
    int newLen = oldLen * 2;  // 扩容2倍
    Entry[] newTab = new Entry[newLen];

    int count = 0;

    // 遍历旧数组，重新hash到新数组
    for (int j = 0; j < oldLen; ++j) {
        Entry e = oldTab[j];
        if (e != null) {
            ThreadLocal<?> k = e.get();
            if (k == null) {
                e.value = null;  // help GC
            } else {
                // 重新计算索引位置
                int h = k.threadLocalHashCode & (newLen - 1);
                // 线性探测找空位
                while (newTab[h] != null)
                    h = nextIndex(h, newLen);
                newTab[h] = e;
                count++;
            }
        }
    }

    setThreshold(newLen);  // 设置新阈值
    size = count;
    table = newTab;
}
```

### 扩容流程图

```
set()方法插入元素后
  ↓
size++ 后检查条件
  ↓
cleanSomeSlots(i, sz)  // 启发式清理
  ↓
清理成功？
  ├─ 是 → 不扩容，返回
  └─ 否 → 检查 size >= threshold？
           ├─ 否 → 不扩容，返回
           └─ 是 → 调用rehash()
                    ↓
              expungeStaleEntries()  // 全量清理过期Entry
                    ↓
              清理后 size >= threshold * 3/4？
                    ├─ 否 → 不扩容，返回
                    └─ 是 → resize()
                             ↓
                        容量扩大2倍
                        重新hash所有Entry
                        设置新阈值
```

### 扩容示例

**初始状态**（容量16，阈值10）：

```
table (len=16, threshold=10):
┌───┬───┬───┬─────┬─────┬─────┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
│ 0 │ 1 │ 2 │ tl1 │ tl2 │ tl3 │ 6 │ 7 │ 8 │ 9 │10 │11 │12 │13 │14 │15 │
└───┴───┴───┴─────┴─────┴─────┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
size = 3
```

**插入7个元素后**（size=10，达到阈值）：

```
插入第10个元素后:
size = 10 >= threshold(10)
  ↓
调用cleanSomeSlots()，未发现过期Entry
  ↓
调用rehash()
  ↓
expungeStaleEntries()全量清理，假设清理掉2个
  ↓
size = 8 < threshold * 3/4 (7.5)
  ↓
不扩容
```

**继续插入后**（size=11，超过3/4阈值）：

```
size = 11 >= threshold * 3/4 (7.5)
  ↓
调用resize()
  ↓
扩容后（容量32，阈值21）:
┌───┬───┬───┬─────┬───┬───┬───┬─────┬───┬───┬───┬─────┬───┬───┬───┬───┬...
│ 0 │ 1 │ 2 │ tl1 │ 4 │ 5 │ 6 │ tl2 │ 8 │ 9 │10 │ tl3 │12 │13 │14 │15 │...
└───┴───┴───┴─────┴───┴───┴───┴─────┴───┴───┴───┴─────┴───┴───┴───┴───┴...
元素分布更均匀，冲突减少
```

### rehash过程详解

**重新计算索引**：

```java
// 旧容量16，新容量32
ThreadLocal tl1:
  hashCode = 0x61c88647
  旧索引 = 0x61c88647 & 15 = 7
  新索引 = 0x61c88647 & 31 = 7  // 可能不变

ThreadLocal tl2:
  hashCode = 0xc3910c8e
  旧索引 = 0xc3910c8e & 15 = 14
  新索引 = 0xc3910c8e & 31 = 14 或 14+16 = 30  // 可能变化
```

**元素迁移规律**：
- 容量从2^n扩容到2^(n+1)
- 元素要么保持原索引，要么移动到 `原索引 + 旧容量` 位置
- 这与HashMap扩容规律一致

### 与HashMap扩容对比

| 维度 | ThreadLocalMap | HashMap |
|------|---------------|---------|
| **初始容量** | 16 | 16 |
| **扩容倍数** | 2倍 | 2倍 |
| **负载因子** | 2/3 ≈ 0.67 | 0.75 |
| **扩容前清理** | ✅ expungeStaleEntries() | ❌ 无 |
| **二次检查** | ✅ 清理后再判断 | ❌ 直接扩容 |
| **rehash方式** | 线性探测找空位 | 计算高位bit |
| **适用场景** | 元素少，需清理 | 元素多，性能优先 |

### 为什么负载因子是2/3？

**对比分析**：

| 负载因子 | 优点 | 缺点 |
|---------|------|------|
| **2/3（ThreadLocalMap）** | 冲突率低，查找快 | 空间利用率66% |
| **0.75（HashMap）** | 空间利用率75% | 冲突率稍高 |
| **1.0** | 空间利用率100% | 冲突严重，性能差 |

**ThreadLocalMap选择2/3的原因**：
1. **线性探测对冲突敏感**：冲突率高会导致聚集，查找效率下降
2. **元素数量少**：ThreadLocal数量少，空间浪费可接受
3. **优先性能**：牺牲空间换取更低的冲突率和更快的查找速度

### 清理机制的作用

**为什么扩容前要清理？**

```java
private void rehash() {
    expungeStaleEntries();  // 先清理

    // 清理后可能不需要扩容了
    if (size >= threshold - threshold / 4)
        resize();
}
```

**场景示例**：

```
扩容前（容量16，阈值10）:
- 实际有效Entry: 8个
- 过期Entry（key=null）: 4个
- size = 12 >= threshold(10)，触发rehash()

清理过期Entry后:
- 有效Entry: 8个
- size = 8 < threshold * 3/4 (7.5)
- 不需要扩容！节省了内存和rehash开销
```

**优势**：
- 避免不必要的扩容
- 减少内存占用
- 提高清理效率（全量遍历）

### 扩容性能分析

**时间复杂度**：

| 操作 | 时间复杂度 |
|------|----------|
| expungeStaleEntries() | O(capacity) |
| resize() | O(capacity + size) |
| 总计 | O(capacity) |

**示例计算**（容量16→32，有效元素10个）：
- 清理：遍历16个槽位
- rehash：遍历16个槽位 + 重新插入10个元素
- 总操作数：约40次

**与HashMap对比**：
- HashMap扩容：O(capacity)，无清理步骤
- ThreadLocalMap扩容：O(capacity)，但包含清理，实际操作更多

### 实际扩容触发测试

```java
public class ResizeTest {
    public static void main(String[] args) throws Exception {
        List<ThreadLocal<String>> list = new ArrayList<>();

        for (int i = 0; i < 20; i++) {
            ThreadLocal<String> tl = new ThreadLocal<>();
            tl.set("value" + i);
            list.add(tl);

            // 反射查看容量
            Thread t = Thread.currentThread();
            Field field = Thread.class.getDeclaredField("threadLocals");
            field.setAccessible(true);
            Object threadLocalMap = field.get(t);

            Field tableField = threadLocalMap.getClass().getDeclaredField("table");
            tableField.setAccessible(true);
            Object[] table = (Object[]) tableField.get(threadLocalMap);

            System.out.println("第" + (i+1) + "个ThreadLocal，容量: " + table.length);
        }
    }
}

// 输出：
// 第1-10个ThreadLocal，容量: 16
// 第11个ThreadLocal，容量: 16（未扩容，因为清理机制）
// 第12个ThreadLocal，容量: 32（扩容）
```

### 扩容优化建议

**1. 预估容量，减少扩容**

```java
// 如果预计有很多ThreadLocal，可以初始化时扩容
// （ThreadLocalMap没有提供公共API，只能间接实现）
for (int i = 0; i < 20; i++) {
    ThreadLocal<String> tl = new ThreadLocal<>();
    tl.set("dummy");  // 触发扩容
    tl.remove();
}
// 此时容量已扩大到32或64
```

**2. 及时清理，避免扩容**

```java
ThreadLocal<User> userContext = new ThreadLocal<>();

try {
    userContext.set(user);
    // 业务逻辑
} finally {
    userContext.remove();  // 及时清理，降低size
}
```

### 面试答题要点

1. **扩容时机**：size >= threshold（2/3 capacity）且启发式清理失败
2. **两阶段检查**：先全量清理过期Entry，清理后仍超过3/4阈值才真正扩容
3. **扩容倍数**：2倍扩容，与HashMap一致
4. **负载因子**：2/3（低于HashMap的0.75），优先性能而非空间利用率
5. **清理优化**：扩容前清理可能避免不必要的扩容，节省内存和性能开销
