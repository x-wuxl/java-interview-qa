---
layout: post
title: "Redis底层结构"
date: 2025-11-02
description: "深入解析Redis的底层数据结构，包括SDS、链表、跳表、哈希表、整数集合、压缩列表、快速列表、紧凑列表等核心实现"
author: "wuxl"
categories: [中间件]
tags: [Redis, 数据结构, 源码分析, 底层原理]
---

## 问题

Redis底层结构

## 答案

### 1. 核心概念

Redis的高性能和灵活性源于其**精心设计的底层数据结构**。上层的五大数据类型（String、List、Hash、Set、ZSet）都是基于这些底层结构实现的。理解底层结构是优化Redis使用的关键。

---

### 2. 底层数据结构全景

#### 2.1 结构分类

**基础结构**：
- **SDS（Simple Dynamic String）**：动态字符串
- **LinkedList**：双向链表（已废弃）
- **Dict（HashTable）**：哈希表
- **SkipList**：跳表
- **IntSet**：整数集合

**紧凑结构**：
- **ZipList**：压缩列表（Redis 7.0前）
- **ListPack**：紧凑列表（Redis 7.0+）

**组合结构**：
- **QuickList**：快速列表（链表+压缩列表）

**数据类型与底层结构对应关系**：
```
String  -> SDS
List    -> QuickList (LinkedList + ZipList/ListPack)
Hash    -> Dict 或 ListPack/ZipList
Set     -> Dict 或 IntSet
ZSet    -> SkipList + Dict 或 ListPack/ZipList
```

---

### 3. 核心底层结构详解

#### 3.1 SDS（简单动态字符串）

**结构定义**：
```c
struct sdshdr {
    uint32_t len;      // 已使用长度
    uint32_t alloc;    // 已分配长度
    unsigned char flags; // 类型标识
    char buf[];        // 字节数组
};
```

**核心特性**：
- **O(1)获取长度**：直接读取len字段
- **防止缓冲区溢出**：自动扩容检查
- **减少内存重分配**：空间预分配和惰性释放
- **二进制安全**：通过len记录长度，支持任意数据
- **兼容C字符串**：buf末尾保留'\0'

**空间预分配策略**：
```c
if (新长度 < 1MB) {
    分配空间 = 新长度 * 2;
} else {
    分配空间 = 新长度 + 1MB;
}
```

**应用**：String类型的底层实现

---

#### 3.2 Dict（哈希表）

**结构定义**：
```c
// 哈希表
typedef struct dictht {
    dictEntry **table;      // 哈希表数组
    unsigned long size;     // 桶数量
    unsigned long sizemask; // 掩码（size - 1）
    unsigned long used;     // 已有节点数量
} dictht;

// 哈希节点
typedef struct dictEntry {
    void *key;
    void *val;
    struct dictEntry *next; // 链地址法解决冲突
} dictEntry;

// 字典（包含2个哈希表用于渐进式rehash）
typedef struct dict {
    dictht ht[2];           // 两个哈希表
    long rehashidx;         // rehash进度（-1表示未进行）
    // ...
} dict;
```

**核心特性**：
- **MurmurHash2算法**：计算哈希值
- **链地址法**：解决哈希冲突
- **渐进式rehash**：分批迁移数据，避免阻塞

**渐进式Rehash流程**：
```java
1. 为ht[1]分配空间（通常是ht[0]的2倍）
2. rehashidx设置为0
3. 每次增删改查时，迁移ht[0].table[rehashidx]到ht[1]
4. rehashidx++
5. 全部迁移完成后，ht[0]指向ht[1]，ht[1]重置
```

**应用**：Hash、Set类型的底层实现之一

---

#### 3.3 SkipList（跳表）

**结构定义**：
```c
// 跳表节点
typedef struct zskiplistNode {
    sds ele;                // 元素值
    double score;           // 分数
    struct zskiplistNode *backward; // 后退指针
    struct zskiplistLevel {
        struct zskiplistNode *forward; // 前进指针
        unsigned long span;     // 跨度
    } level[];              // 层级数组
} zskiplistNode;

// 跳表
typedef struct zskiplist {
    struct zskiplistNode *header;  // 头节点
    struct zskiplistNode *tail;    // 尾节点
    unsigned long length;          // 节点数量
    int level;                     // 最大层数
} zskiplist;
```

**核心特性**：
- **多层索引**：通过"跳跃"加速查找
- **随机层数**：每个节点随机1-32层，概率P=0.25
- **平均O(log N)**：查找、插入、删除
- **支持范围查询**：有序链表特性

**层数生成**：
```c
int zslRandomLevel(void) {
    int level = 1;
    while ((random() & 0xFFFF) < (0.25 * 0xFFFF))
        level += 1;
    return (level < 32) ? level : 32;
}
```

**应用**：ZSet类型的底层实现之一

---

#### 3.4 IntSet（整数集合）

**结构定义**：
```c
typedef struct intset {
    uint32_t encoding;  // 编码类型（int16/int32/int64）
    uint32_t length;    // 元素数量
    int8_t contents[];  // 实际存储数组
} intset;
```

**核心特性**：
- **紧凑存储**：连续内存，无指针开销
- **有序排列**：支持二分查找，O(log N)
- **自动升级**：添加大整数时升级编码
- **只升级不降级**：删除大整数后不回退编码

**编码类型**：
```c
INTSET_ENC_INT16: 2字节，范围-32768~32767
INTSET_ENC_INT32: 4字节，范围-2^31~2^31-1
INTSET_ENC_INT64: 8字节，范围-2^63~2^63-1
```

**应用**：Set类型（全整数且数量≤512）的底层实现

---

#### 3.5 ZipList（压缩列表）

**结构设计**：
```
<zlbytes><zltail><zllen><entry>...<entry><zlend>

zlbytes: 4字节，总字节数
zltail:  4字节，尾元素偏移量
zllen:   2字节，元素数量
entry:   实际存储的元素
zlend:   1字节，结束标记0xFF
```

**Entry结构**：
```
<prevlen><encoding><data>

prevlen: 前一个entry的长度（1或5字节）
encoding: 编码类型（字符串或整数）
data: 实际数据
```

**核心特性**：
- **内存紧凑**：连续内存，无额外指针
- **缓存友好**：利用CPU缓存行
- **级联更新问题**：插入大元素导致后续所有prevlen更新

**级联更新场景**：
```java
// ZipList: [250字节] [250字节] [250字节]
// prevlen都是1字节（因为前一个entry < 254字节）

// 插入一个260字节的元素
[260字节] [250字节] [250字节] [250字节]
//         ↓ prevlen需从1字节扩展到5字节
//                    ↓ 后续所有entry都要更新
```

**应用**：List、Hash、ZSet（小对象）的底层实现（Redis 7.0前）

---

#### 3.6 ListPack（紧凑列表）

**改进点**：解决ZipList的级联更新问题

**Entry结构**：
```
<encoding><data><len>

encoding: 编码类型
data: 实际数据
len: entry总长度（用于反向遍历）
```

**核心特性**：
- **避免级联更新**：不记录前一个entry的长度
- **支持反向遍历**：通过len字段
- **内存紧凑**：连续存储

**对比ZipList**：
```
ZipList:  <prevlen><encoding><data>  // prevlen可能级联更新
ListPack: <encoding><data><len>      // 无级联更新风险
```

**应用**：List、Hash、ZSet（小对象）的底层实现（Redis 7.0+）

---

#### 3.7 QuickList（快速列表）

**结构设计**：
```c
// QuickList主结构
typedef struct quicklist {
    quicklistNode *head;
    quicklistNode *tail;
    unsigned long count;   // 所有ZipList中的元素总数
    unsigned long len;     // QuickList节点数量
    int fill;              // 单个ZipList的大小限制
    unsigned int compress; // 压缩深度
} quicklist;

// QuickList节点
typedef struct quicklistNode {
    struct quicklistNode *prev;
    struct quicklistNode *next;
    unsigned char *zl;      // 指向ZipList/ListPack
    unsigned int sz;        // ZipList的字节大小
    unsigned int count;     // ZipList中的元素数量
    unsigned int encoding;  // 编码格式（RAW或LZF压缩）
} quicklistNode;
```

**设计理念**：
```
QuickList = LinkedList + ZipList/ListPack

优势：
- 结合LinkedList的灵活性（快速头尾操作）
- 结合ZipList的内存紧凑性
- 避免LinkedList的指针开销
- 避免ZipList的大规模移动
```

**示例**：
```
quicklist
  |
  +-> [node1: ZipList1] <-> [node2: ZipList2] <-> [node3: ZipList3]
          [1,2,3]               [4,5,6]               [7,8,9]
```

**压缩策略**：
```bash
list-compress-depth 1  # 首尾各1个节点不压缩

# 示例：5个节点
[不压缩] <-> [压缩] <-> [压缩] <-> [压缩] <-> [不压缩]
   ↑                                         ↑
  头部（热数据）                          尾部（热数据）
```

**应用**：List类型的底层实现（Redis 3.2+）

---

### 4. 数据类型编码选择

#### 4.1 String

**编码**：
- **int**：存储整数且在long范围内
- **embstr**：≤44字节的字符串（Redis 6.0+）
- **raw**：>44字节的字符串

```bash
redis> SET num 123
redis> OBJECT ENCODING num
"int"

redis> SET short "hello"
redis> OBJECT ENCODING short
"embstr"

redis> SET long "这是一个很长的字符串........................"
redis> OBJECT ENCODING long
"raw"
```

---

#### 4.2 List

**编码**：
- **QuickList**：所有情况（Redis 3.2+）

**配置**：
```bash
list-max-ziplist-size -2    # 单个ZipList最大8KB
list-compress-depth 0       # 不压缩（默认）
```

---

#### 4.3 Hash

**编码**：
- **ListPack/ZipList**：元素≤512且所有值≤64字节
- **HashTable**：其他情况

**配置**：
```bash
hash-max-listpack-entries 512  # Redis 7.0+
hash-max-listpack-value 64

hash-max-ziplist-entries 512   # Redis 7.0前
hash-max-ziplist-value 64
```

---

#### 4.4 Set

**编码**：
- **IntSet**：全整数且元素≤512
- **HashTable**：其他情况

**配置**：
```bash
set-max-intset-entries 512
```

---

#### 4.5 ZSet

**编码**：
- **ListPack/ZipList**：元素≤128且所有元素≤64字节
- **SkipList + HashTable**：其他情况

**配置**：
```bash
zset-max-listpack-entries 128  # Redis 7.0+
zset-max-listpack-value 64

zset-max-ziplist-entries 128   # Redis 7.0前
zset-max-ziplist-value 64
```

---

### 5. 底层结构演进历史

#### 5.1 List的演进

```
Redis 3.2之前：
  - 小对象：ZipList
  - 大对象：LinkedList

Redis 3.2+：
  - 统一使用QuickList（LinkedList + ZipList）

Redis 7.0+：
  - QuickList内部改用ListPack（替代ZipList）
```

---

#### 5.2 Hash/ZSet的演进

```
Redis 7.0之前：
  - 小对象：ZipList
  - 大对象：HashTable/SkipList

Redis 7.0+：
  - 小对象：ListPack（替代ZipList）
  - 大对象：HashTable/SkipList
```

**ListPack优势**：
- 解决ZipList的级联更新问题
- 更新性能提升
- 内存占用相当

---

### 6. 性能优化建议

#### 6.1 利用紧凑编码

**小对象优化**：
```bash
# 控制在阈值以下，享受紧凑编码
HSET user:1001 name "Alice" age "25"  # 2个字段，用ListPack

# 避免超过阈值
HSET config field1 "value1" ... field600 "value600"  # 超过512，转HashTable
```

---

#### 6.2 避免大Key

**问题**：
- 单个Key过大会阻塞Redis
- 内存不连续，影响性能

**解决**：
```bash
# 不推荐：单个大List
LPUSH biglist item1 item2 ... item1000000

# 推荐：拆分多个小List
LPUSH list:2024-11-01 item1 ...
LPUSH list:2024-11-02 item2 ...
```

---

#### 6.3 选择合适的数据结构

| 场景 | 推荐结构 | 原因 |
|------|---------|------|
| 计数器 | String | 简单高效 |
| 对象存储 | Hash | 可单独操作字段 |
| 去重 | Set | 自动去重 |
| 排行榜 | ZSet | 有序，范围查询快 |
| 消息队列 | List/Stream | 头尾操作快 |
| UV统计 | HyperLogLog | 内存占用极小 |

---

### 7. 面试答题总结

**标准回答模板**：

> Redis的底层数据结构包括：
> 1. **SDS**：动态字符串，O(1)获取长度，二进制安全，空间预分配
> 2. **Dict（哈希表）**：MurmurHash2算法，链地址法解决冲突，渐进式rehash
> 3. **SkipList（跳表）**：多层索引，平均O(log N)，支持范围查询
> 4. **IntSet**：整数集合，有序存储，自动升级
> 5. **ListPack**：紧凑列表，解决ZipList的级联更新问题（Redis 7.0+）
> 6. **QuickList**：快速列表，结合链表和压缩列表，支持LZF压缩
>
> 上层数据类型根据数据量自动选择合适的底层编码，小对象用紧凑编码（ListPack/IntSet），大对象用高效编码（Dict/SkipList）。

**常见追问**：
- **ZipList的级联更新问题？** → 插入大元素导致后续所有entry的prevlen字段都要更新
- **为什么需要渐进式rehash？** → 大表一次性rehash会阻塞，分批迁移保证可用性
- **QuickList为什么比LinkedList好？** → 减少指针开销，提升缓存友好性，支持压缩
- **ListPack如何解决级联更新？** → 不记录前一个entry的长度，而是记录自身长度

