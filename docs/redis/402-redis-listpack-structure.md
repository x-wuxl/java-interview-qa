---
layout: default
title: "说说 listpack 结构"
parent: Redis
nav_order: 402
description: "深入解析Redis 7.0中引入的listpack数据结构，了解其设计原理、内存布局及相比ziplist的优化"
author: "wuxl"
date: 2025-11-08
---
## 问题

说说 listpack 结构

## 答案

### 1. 核心概念

**listpack**（紧凑列表）是 Redis 7.0 引入的一种新的内存紧凑型数据结构，用于替代 ziplist（压缩列表）。它主要用于存储小规模的列表、哈希、有序集合等数据类型的底层实现，目标是在保持内存高效的同时，解决 ziplist 的连锁更新问题。

### 2. 设计原理与内存布局

#### 整体结构

listpack 的内存布局如下：

```
+----------+----------+-------+-------+-----+-------+---------+
| total    | num      | entry | entry | ... | entry | listpack|
| bytes    | elements | 1     | 2     |     | N     | end     |
+----------+----------+-------+-------+-----+-------+---------+
| 4 bytes  | 2 bytes  |       |       |     |       | 1 byte  |
+----------+----------+-------+-------+-----+-------+---------+
```

- **total bytes**（4字节）：整个 listpack 占用的总字节数
- **num elements**（2字节）：listpack 中元素的个数
- **entry**：每个元素的编码数据
- **listpack end**（1字节）：结束标记，固定为 `0xFF`

#### 单个 entry 的结构

每个 entry 由三部分组成：

```
+----------+----------+----------+
| encoding | data     | backlen  |
+----------+----------+----------+
```

- **encoding**：编码类型和长度信息（变长，1-5字节）
- **data**：实际存储的数据
- **backlen**：当前 entry 的总长度（变长编码），用于从后向前遍历

#### 关键设计点

1. **独立的 backlen**：每个 entry 的 backlen 只记录自己的长度，不依赖前一个元素
2. **变长编码**：根据数据大小动态调整编码方式，节省空间
3. **支持的数据类型**：
   - 小整数（7位、13位、16位、24位、32位、64位）
   - 字符串（长度可变）

### 3. 相比 ziplist 的优化

#### ziplist 的连锁更新问题

ziplist 中每个 entry 的 `prevlen` 字段记录前一个元素的长度：
- 如果前一个元素长度 < 254 字节，`prevlen` 占 1 字节
- 如果前一个元素长度 ≥ 254 字节，`prevlen` 占 5 字节

当插入或删除元素导致某个 entry 长度从 253 变为 254 时，后续所有 entry 的 `prevlen` 都可能需要扩展，引发连锁更新，最坏情况下时间复杂度为 O(N²)。

#### listpack 的解决方案

listpack 通过以下设计避免连锁更新：

1. **backlen 只记录自己的长度**：不依赖前一个元素，修改某个 entry 不会影响其他 entry
2. **从后向前遍历**：通过 backlen 可以快速定位前一个元素
3. **编码方式优化**：使用更灵活的变长编码，减少空间浪费

### 4. 使用场景

listpack 在 Redis 7.0+ 中替代了 ziplist，应用于以下场景：

- **List 类型**：当列表元素较少且元素较小时
- **Hash 类型**：当哈希表字段数量较少时
- **Sorted Set 类型**：当有序集合元素较少时
- **Stream 类型**：消息队列的底层存储

配置参数示例（以 Hash 为例）：

```
hash-max-listpack-entries 512
hash-max-listpack-value 64
```

### 5. 性能特点

| 操作 | 时间复杂度 | 说明 |
|------|-----------|------|
| 头部插入 | O(N) | 需要移动后续元素 |
| 尾部插入 | O(1) | 直接追加 |
| 查找 | O(N) | 需要遍历 |
| 删除 | O(N) | 需要移动后续元素 |

**优势**：
- 内存紧凑，适合小数据量场景
- 避免了 ziplist 的连锁更新问题
- CPU 缓存友好（连续内存）

**劣势**：
- 不适合大数据量（插入/删除需要移动数据）
- 查找效率低于哈希表

### 6. 示例代码（概念性）

```c
// listpack entry 编码示例
typedef struct {
    unsigned char *data;  // 指向 listpack 数据
    uint32_t total_bytes; // 总字节数
    uint16_t num_elements; // 元素个数
} listpack;

// 获取 entry 的 backlen（从后向前遍历）
unsigned int lpDecodeBacklen(unsigned char *p) {
    uint64_t val = 0;
    uint64_t shift = 0;
    do {
        val |= (uint64_t)(p[0] & 127) << shift;
        if (!(p[0] & 128)) break;
        shift += 7;
        p--;
        if (shift > 63) return 0; // 错误
    } while(1);
    return val;
}
```

### 7. 面试总结

**回答要点**：
1. listpack 是 Redis 7.0 引入的紧凑型数据结构，替代 ziplist
2. 核心优化：通过独立的 backlen 避免连锁更新问题
3. 内存布局：总长度 + 元素数 + entry列表 + 结束标记
4. 适用场景：小规模数据的 List、Hash、Sorted Set 底层实现
5. 性能权衡：内存紧凑但插入/删除需要移动数据，适合读多写少场景

**进阶问题**：
- 为什么 Redis 要用 listpack 替代 ziplist？（连锁更新问题）
- listpack 如何实现从后向前遍历？（backlen 字段）
- 什么情况下 listpack 会转换为其他数据结构？（超过配置阈值时转为 hashtable 或 skiplist）
