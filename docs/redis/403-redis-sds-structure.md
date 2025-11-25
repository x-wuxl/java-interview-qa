---
layout: default
title: "说说 SDS 结构"
parent: Redis
nav_order: 403
description: "深入解析Redis的Simple Dynamic String（SDS）数据结构，了解其设计原理、内存布局及相比C字符串的优势"
author: "wuxl"
date: 2025-11-08
---
## 问题

说说 SDS 结构

## 答案

### 1. 核心概念

**SDS**（Simple Dynamic String，简单动态字符串）是 Redis 自己实现的字符串类型，用于替代 C 语言的传统字符串（以 `\0` 结尾的字符数组）。SDS 是 Redis 中最基础的数据结构，不仅用于存储字符串类型的值，还用于存储 AOF 缓冲区、客户端输入缓冲区等场景。

### 2. 设计原理与内存布局

#### SDS 的结构定义

Redis 根据字符串长度的不同，定义了 5 种 SDS 类型（Redis 3.2+）：

```c
// sdshdr5：长度 < 32 字节（很少使用，仅用于优化小字符串）
struct __attribute__ ((__packed__)) sdshdr5 {
    unsigned char flags; // 低3位存储类型，高5位存储长度
    char buf[];          // 字符数组
};

// sdshdr8：长度 < 256 字节
struct __attribute__ ((__packed__)) sdshdr8 {
    uint8_t len;        // 已使用长度
    uint8_t alloc;      // 已分配长度（不包括头和结尾的 \0）
    unsigned char flags; // 类型标识（低3位）
    char buf[];         // 字符数组
};

// sdshdr16：长度 < 65536 字节
struct __attribute__ ((__packed__)) sdshdr16 {
    uint16_t len;
    uint16_t alloc;
    unsigned char flags;
    char buf[];
};

// sdshdr32：长度 < 4GB
struct __attribute__ ((__packed__)) sdshdr32 {
    uint32_t len;
    uint32_t alloc;
    unsigned char flags;
    char buf[];
};

// sdshdr64：长度 < 2^64
struct __attribute__ ((__packed__)) sdshdr64 {
    uint64_t len;
    uint64_t alloc;
    unsigned char flags;
    char buf[];
};
```

#### 内存布局示例（以 sdshdr8 为例）

```
+-----+-------+-------+----------+-----+
| len | alloc | flags | buf      | \0  |
+-----+-------+-------+----------+-----+
| 1B  | 1B    | 1B    | N bytes  | 1B  |
+-----+-------+-------+----------+-----+
```

- **len**：当前字符串的实际长度（不包括 `\0`）
- **alloc**：已分配的空间大小（不包括头和 `\0`）
- **flags**：低 3 位标识 SDS 类型（SDS_TYPE_8/16/32/64）
- **buf**：实际存储字符串内容的字节数组
- **\0**：兼容 C 字符串的结尾符

#### 关键设计点

1. **`__attribute__ ((__packed__))`**：取消结构体内存对齐，节省空间
2. **柔性数组 `buf[]`**：不占用结构体空间，紧跟在结构体后面
3. **类型自适应**：根据字符串长度自动选择合适的 SDS 类型

### 3. 相比 C 字符串的优势

| 特性 | C 字符串 | SDS |
|------|---------|-----|
| **获取长度** | O(N)，需要遍历到 `\0` | O(1)，直接读取 `len` 字段 |
| **缓冲区溢出** | 容易发生（如 `strcat` 不检查边界） | 自动扩容，避免溢出 |
| **二进制安全** | 不支持（遇到 `\0` 会截断） | 支持（通过 `len` 判断长度） |
| **内存重分配** | 每次修改都需要重新分配 | 空间预分配 + 惰性释放 |
| **兼容性** | 标准 C 函数 | 兼容 C 字符串（保留 `\0`） |

#### 详细说明

**1. O(1) 获取长度**

```c
// C 字符串获取长度
size_t len = strlen(str); // O(N)

// SDS 获取长度
size_t len = sdslen(s);   // O(1)，直接返回 s->len
```

**2. 避免缓冲区溢出**

```c
// C 字符串：危险操作
char s1[10] = "hello";
strcat(s1, " world"); // 可能溢出！

// SDS：自动扩容
sds s = sdsnew("hello");
s = sdscat(s, " world"); // 自动检查并扩容
```

**3. 二进制安全**

```c
// C 字符串：无法存储二进制数据
char data[] = "hello\0world"; // strlen(data) = 5

// SDS：可以存储任意二进制数据
sds s = sdsnewlen("hello\0world", 11); // len = 11
```

**4. 空间预分配策略**

当 SDS 需要扩容时：
- 如果修改后长度 < 1MB：分配 2 倍所需空间
- 如果修改后长度 ≥ 1MB：额外分配 1MB 空间

```c
// 示例：追加字符串
sds s = sdsnew("hello");     // len=5, alloc=5
s = sdscat(s, " world");     // len=11, alloc=22（预分配）
s = sdscat(s, "!");          // len=12, alloc=22（无需重新分配）
```

**5. 惰性释放**

当 SDS 缩短时，不立即释放多余空间，而是保留以备后用：

```c
sds s = sdsnew("hello world"); // len=11, alloc=11
sdsclear(s);                   // len=0, alloc=11（空间未释放）
```

### 4. 使用场景

SDS 在 Redis 中的应用非常广泛：

1. **String 类型的值**：所有字符串键值对
2. **AOF 缓冲区**：持久化时的写缓冲
3. **客户端输入/输出缓冲区**：网络通信
4. **复杂数据结构的字段**：Hash、List、Set 等的字符串元素

### 5. 性能优化

#### 内存优化

```c
// 根据长度选择合适的 SDS 类型
sds s1 = sdsnew("hi");           // 使用 sdshdr8（3字节头）
sds s2 = sdsnewlen(buf, 10000);  // 使用 sdshdr16（5字节头）
```

#### 减少内存分配次数

```c
// 预分配空间
sds s = sdsempty();
s = sdsMakeRoomFor(s, 1000); // 预分配 1000 字节

// 批量追加，减少重新分配
for (int i = 0; i < 100; i++) {
    s = sdscat(s, "data");
}
```

### 6. 示例代码

```c
// 创建 SDS
sds s = sdsnew("hello");

// 获取长度和可用空间
printf("len: %zu\n", sdslen(s));      // 5
printf("avail: %zu\n", sdsavail(s));  // 0

// 追加字符串（自动扩容）
s = sdscat(s, " world");
printf("len: %zu\n", sdslen(s));      // 11
printf("avail: %zu\n", sdsavail(s));  // 11（预分配）

// 格式化追加
s = sdscatprintf(s, " %d", 2024);

// 范围删除
sdsrange(s, 0, 4); // 保留 "hello"

// 清空（惰性释放）
sdsclear(s);

// 释放内存
sdsfree(s);
```

### 7. 线程安全性

SDS 本身**不是线程安全**的，Redis 通过以下方式保证安全：

1. **单线程模型**：Redis 6.0 之前，所有命令在单线程中执行
2. **IO 多线程**：Redis 6.0+ 的多线程仅用于网络 IO，命令执行仍是单线程
3. **COW（Copy-On-Write）**：RDB 持久化时使用写时复制

### 8. 面试总结

**回答要点**：
1. SDS 是 Redis 自定义的动态字符串，替代 C 字符串
2. 核心优势：O(1) 获取长度、避免缓冲区溢出、二进制安全、减少内存重分配
3. 内存布局：len + alloc + flags + buf + \0
4. 优化策略：空间预分配（< 1MB 翻倍，≥ 1MB 加 1MB）+ 惰性释放
5. 类型自适应：根据长度选择 sdshdr8/16/32/64，节省内存

**进阶问题**：
- 为什么 SDS 要保留 `\0` 结尾符？（兼容 C 字符串函数，如 `printf`）
- SDS 的空间预分配策略为什么是 1MB 分界？（平衡内存浪费和重新分配次数）
- Redis 如何保证 SDS 的线程安全？（单线程命令执行 + IO 多线程）
- SDS 如何支持二进制数据？（通过 `len` 字段而非 `\0` 判断长度）
