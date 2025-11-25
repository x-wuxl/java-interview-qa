---
title: "Redis的String是如何实现的？"
date: 2025-11-02
description: "深入解析Redis String的底层实现SDS（简单动态字符串），包括结构设计、优化策略及与C字符串的对比"
author: "wuxl"
categories: [中间件]
tags: [Redis, SDS, 数据结构, 源码分析]
nav_order: 405
parent: Redis
---
## 问题

Redis的String是如何实现的？

## 答案

### 1. 核心概念

Redis的String并非直接使用C语言的字符串，而是自己实现了**SDS（Simple Dynamic String，简单动态字符串）**结构，这是Redis的基础数据结构之一。

---

### 2. SDS结构设计

#### 2.1 源码结构（Redis 6.0+）

```c
struct sdshdr {
    uint32_t len;      // 已使用长度
    uint32_t alloc;    // 已分配长度（不包含头和结束符）
    unsigned char flags; // 类型标识（sdshdr5/8/16/32/64）
    char buf[];        // 字节数组，存储实际内容
};
```

**示例**：存储字符串"Redis"
```
len = 5
alloc = 10
flags = SDS_TYPE_8
buf = "Redis\0"  // 末尾仍保留'\0'，兼容C字符串函数
```

#### 2.2 多类型优化（内存对齐）

Redis根据字符串长度使用不同的SDS类型：

| 类型 | 最大长度 | 头部大小 | 使用场景 |
|------|---------|---------|---------|
| sdshdr5 | 32字节 | 1字节 | 短字符串（已废弃） |
| sdshdr8 | 255字节 | 3字节 | 较短字符串 |
| sdshdr16 | 65535字节 | 5字节 | 中等字符串 |
| sdshdr32 | 4GB | 9字节 | 长字符串 |
| sdshdr64 | 无限制 | 17字节 | 超长字符串 |

---

### 3. SDS相比C字符串的优势

#### 3.1 O(1)复杂度获取长度

**C字符串**：需要遍历到`\0`，O(N)
```c
strlen(s); // 需要遍历整个字符串
```

**SDS**：直接读取len字段，O(1)
```c
sdslen(s); // 直接返回 s->len
```

**应用场景**：Redis的`STRLEN`命令、统计操作都能高效执行。

---

#### 3.2 防止缓冲区溢出

**C字符串**：`strcat`等函数不检查空间，容易溢出
```c
char s1[10] = "Hello";
strcat(s1, " World"); // 可能溢出
```

**SDS**：自动扩容
```c
sds s = sdsnew("Hello");
s = sdscat(s, " World"); // 自动检查并扩容
```

---

#### 3.3 减少内存重分配次数

**空间预分配策略**：
```c
// 扩容策略
if (新长度 < 1MB) {
    分配空间 = 新长度 * 2
} else {
    分配空间 = 新长度 + 1MB
}
```

**惰性释放策略**：
- 缩短字符串时不立即释放内存，保留空闲空间供下次使用
- 通过`alloc - len`计算剩余空间

**示例**：
```java
// 假设初始字符串"Redis"
SET key "Redis"        // len=5, alloc=10（预分配）
APPEND key "Labs"      // len=10, alloc=10（无需重新分配）
APPEND key "Database"  // len=18, alloc=36（扩容）
```

---

#### 3.4 二进制安全

**C字符串**：以`\0`作为结束标志，无法存储二进制数据
```c
char s[] = "Hello\0World"; // 只能读取到"Hello"
```

**SDS**：通过len字段记录长度，支持任意二进制数据
```c
sds s = sdsnewlen("Hello\0World", 11); // 可正确存储
```

**应用场景**：Redis可以存储图片、音频等二进制文件。

---

#### 3.5 兼容C字符串函数

SDS的`buf`数组末尾仍保留`\0`，可以直接使用C标准库函数：
```c
printf("%s", s->buf); // 可以直接使用
```

---

### 4. SDS的内存分配策略

#### 4.1 扩容流程

```java
// 伪代码
if (需要的空间 <= alloc - len) {
    // 空闲空间足够，直接使用
    len += 新增长度;
} else {
    // 空间不足，需要扩容
    新alloc = (len + 新增长度) * 2; // 或 +1MB
    重新分配内存;
    复制数据;
}
```

#### 4.2 缩容策略

Redis不会自动缩容，需手动调用：
```c
sdsclear(s);    // 清空内容但不释放空间
sdsRemoveFreeSpace(s); // 释放所有空闲空间
```

---

### 5. 源码关键点

#### 5.1 获取SDS头指针

```c
// buf指针向前偏移获取头结构
#define SDS_HDR(T,s) ((struct sdshdr##T *)((s)-(sizeof(struct sdshdr##T))))

// 使用示例
sds s = sdsnew("Redis");
struct sdshdr8 *sh = SDS_HDR(8, s); // 获取头部
printf("len=%d, alloc=%d\n", sh->len, sh->alloc);
```

#### 5.2 关键API

```c
sds sdsnew(const char *init);              // 创建SDS
sds sdscat(sds s, const char *t);          // 拼接字符串
void sdsclear(sds s);                      // 清空（保留空间）
void sdsfree(sds s);                       // 释放SDS
size_t sdslen(const sds s);                // 获取长度
size_t sdsavail(const sds s);              // 获取可用空间
```

---

### 6. 性能优化与应用场景

#### 6.1 高频写场景
- 利用预分配空间，减少内存分配次数
- 适合日志追加、计数器更新等场景

#### 6.2 大字符串存储
- 单个String最大512MB，适合存储JSON、HTML等
- 注意：大Key会阻塞Redis，建议拆分存储

#### 6.3 二进制数据
- 存储图片缩略图、序列化对象等
- 使用`SETRANGE`、`GETRANGE`操作部分数据

```java
// 存储二进制数据
byte[] imageData = loadImage();
redisTemplate.opsForValue().set("image:1001", imageData);
```

---

### 7. 面试答题总结

**标准回答模板**：

> Redis的String基于**SDS（简单动态字符串）**实现，核心优势：
> 1. **O(1)获取长度**：通过len字段直接返回，无需遍历
> 2. **防止缓冲区溢出**：自动检查空间并扩容
> 3. **减少内存重分配**：空间预分配（小于1MB翻倍，大于1MB每次+1MB）和惰性释放
> 4. **二进制安全**：通过len记录长度而非`\0`，可存储任意数据
> 5. **兼容C函数**：buf末尾保留`\0`，可使用标准库函数
>
> SDS根据长度使用不同类型（sdshdr8/16/32/64），优化内存占用。

**常见追问**：
- **SDS的扩容策略？** → 小于1MB翻倍，大于1MB每次+1MB
- **为什么不直接用C字符串？** → C字符串获取长度慢、不安全、不支持二进制
- **SDS如何节省内存？** → 多类型头部（sdshdr8只需3字节）、惰性释放

