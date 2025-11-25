---
layout: default
title: "说说 dict 结构"
parent: Redis
nav_order: 404
description: "深入解析Redis的字典（dict）数据结构，了解其哈希表实现、渐进式rehash机制及性能优化策略"
author: "wuxl"
date: 2025-11-08
---
## 问题

说说 dict 结构

## 答案

### 1. 核心概念

**dict**（字典）是 Redis 中最核心的数据结构之一，基于**哈希表**实现，提供 O(1) 的键值对存储和查找能力。dict 不仅用于实现 Redis 的 Hash 类型，还用于存储整个 Redis 数据库的所有键值对、过期键字典、集合类型等。

### 2. 设计原理与内存布局

#### 三层结构

Redis 的 dict 由三个核心结构组成：

```c
// 1. 哈希表节点
typedef struct dictEntry {
    void *key;              // 键
    union {
        void *val;          // 值（指针）
        uint64_t u64;       // 值（无符号整数）
        int64_t s64;        // 值（有符号整数）
        double d;           // 值（浮点数）
    } v;
    struct dictEntry *next; // 链表指针（解决哈希冲突）
} dictEntry;

// 2. 哈希表
typedef struct dictht {
    dictEntry **table;      // 哈希表数组（指针数组）
    unsigned long size;     // 哈希表大小（总是 2^n）
    unsigned long sizemask; // 哈希表大小掩码（size - 1）
    unsigned long used;     // 已使用节点数量
} dictht;

// 3. 字典
typedef struct dict {
    dictType *type;         // 类型特定函数（哈希、比较、析构等）
    void *privdata;         // 私有数据
    dictht ht[2];           // 两个哈希表（用于渐进式 rehash）
    long rehashidx;         // rehash 进度（-1 表示未进行）
    int16_t pauserehash;    // rehash 暂停标志
} dict;
```

#### 内存布局示意图

```
dict
+------------------+
| type             |
| privdata         |
| ht[0] (主表)     |-----> dictht
| ht[1] (备用表)   |       +----------+
| rehashidx = -1   |       | table    |-----> [dictEntry*, dictEntry*, ...]
+------------------+       | size     |                |
                           | sizemask |                v
                           | used     |           dictEntry (链表)
                           +----------+           +------+------+------+
                                                  | key  | val  | next |---> ...
                                                  +------+------+------+
```

### 3. 哈希算法与冲突解决

#### 哈希计算

```c
// 1. 计算哈希值
hash = dict->type->hashFunction(key);

// 2. 计算索引（使用位运算，等价于 hash % size）
index = hash & dict->ht[0].sizemask;
```

**为什么 size 必须是 2^n？**
- 使用位运算 `hash & (size - 1)` 替代取模运算，性能更高
- 例如：size = 8，sizemask = 7（0111），`hash & 7` 等价于 `hash % 8`

#### 冲突解决：链地址法

当多个键映射到同一个索引时，使用**单向链表**连接：

```
table[3] --> [key1, val1] --> [key2, val2] --> [key3, val3] --> NULL
```

**插入策略**：新节点插入到链表头部（O(1)）

### 4. 渐进式 rehash 机制

#### 为什么需要 rehash？

当哈希表的**负载因子**（load factor = used / size）过高或过低时，需要扩容或缩容：

- **扩容条件**：
  - 负载因子 ≥ 1 且未进行 BGSAVE/BGREWRITEAOF
  - 负载因子 ≥ 5（强制扩容）
- **缩容条件**：
  - 负载因子 < 0.1

#### 渐进式 rehash 流程

为了避免一次性 rehash 导致的长时间阻塞，Redis 采用**渐进式 rehash**：

```c
// 1. 为 ht[1] 分配空间
//    扩容：ht[1].size = ht[0].used * 2 的第一个 2^n
//    缩容：ht[1].size = ht[0].used 的第一个 2^n
ht[1].size = nextPower(ht[0].used * 2);

// 2. 设置 rehashidx = 0，开始渐进式 rehash
dict->rehashidx = 0;

// 3. 在每次增删改查操作时，顺带迁移一个桶
while (ht[0].table[rehashidx] == NULL) rehashidx++;
// 迁移 ht[0].table[rehashidx] 的所有节点到 ht[1]
rehashidx++;

// 4. 迁移完成后，释放 ht[0]，将 ht[1] 设为 ht[0]
ht[0] = ht[1];
ht[1] = empty;
rehashidx = -1;
```

#### rehash 期间的操作

| 操作 | 行为 |
|------|------|
| **查找** | 先查 ht[0]，未找到再查 ht[1] |
| **插入** | 直接插入 ht[1]（避免 ht[0] 继续增长） |
| **删除** | 在 ht[0] 和 ht[1] 中都尝试删除 |
| **更新** | 先查找，再更新 |

#### 定时 rehash

除了在操作时顺带迁移，Redis 还会在**定时任务**中主动推进 rehash：

```c
// serverCron 中每次迁移 100 个桶（限时 1ms）
dictRehashMilliseconds(db->dict, 1);
```

### 5. 性能特点

| 操作 | 平均时间复杂度 | 最坏时间复杂度 |
|------|---------------|---------------|
| 查找 | O(1) | O(N)（链表过长） |
| 插入 | O(1) | O(N)（rehash 时） |
| 删除 | O(1) | O(N)（链表过长） |

**优化策略**：
1. **负载因子控制**：保持在 0.1 ~ 5 之间
2. **渐进式 rehash**：避免长时间阻塞
3. **哈希函数**：使用 SipHash（防止哈希碰撞攻击）

### 6. 使用场景

dict 在 Redis 中的应用：

1. **数据库键空间**：存储所有键值对
   ```c
   redisDb->dict  // 键值对字典
   redisDb->expires  // 过期键字典
   ```

2. **Hash 类型**：当字段数量较多时
   ```bash
   HSET user:1 name "Alice" age 30
   # 底层使用 dict 存储
   ```

3. **Set 类型**：当元素不是整数或数量较多时
   ```bash
   SADD myset "a" "b" "c"
   # 底层使用 dict（值为 NULL）
   ```

4. **Cluster 模式**：槽位映射表

### 7. 示例代码

```c
// 创建字典
dict *d = dictCreate(&hashDictType, NULL);

// 插入键值对
dictAdd(d, sdsnew("name"), sdsnew("Alice"));
dictAdd(d, sdsnew("age"), (void*)30);

// 查找
dictEntry *entry = dictFind(d, "name");
if (entry) {
    printf("name: %s\n", (char*)dictGetVal(entry));
}

// 删除
dictDelete(d, "age");

// 遍历（安全迭代器，允许修改）
dictIterator *iter = dictGetSafeIterator(d);
dictEntry *entry;
while ((entry = dictNext(iter)) != NULL) {
    printf("key: %s\n", (char*)dictGetKey(entry));
}
dictReleaseIterator(iter);

// 释放字典
dictRelease(d);
```

### 8. 线程安全性

dict 本身**不是线程安全**的，Redis 通过以下方式保证安全：

1. **单线程命令执行**：Redis 6.0+ 的多线程仅用于 IO
2. **COW 机制**：RDB 持久化时使用写时复制
3. **主从复制**：通过命令传播保证一致性

### 9. 与 Java HashMap 的对比

| 特性 | Redis dict | Java HashMap |
|------|-----------|--------------|
| **冲突解决** | 链地址法（单向链表） | 链地址法 + 红黑树（链表长度 ≥ 8） |
| **扩容策略** | 渐进式 rehash | 一次性 rehash |
| **负载因子** | 1（扩容）/ 0.1（缩容） | 0.75（扩容） |
| **哈希函数** | SipHash | MurmurHash3 |
| **线程安全** | 单线程模型 | 非线程安全（ConcurrentHashMap 安全） |

### 10. 面试总结

**回答要点**：
1. dict 是 Redis 的核心数据结构，基于哈希表实现，提供 O(1) 查找
2. 三层结构：dict → dictht（两个，用于 rehash）→ dictEntry（链表节点）
3. 冲突解决：链地址法（单向链表）
4. 核心机制：渐进式 rehash，避免一次性迁移导致阻塞
5. 扩容条件：负载因子 ≥ 1（或 ≥ 5 强制）；缩容条件：< 0.1
6. 应用场景：数据库键空间、Hash 类型、Set 类型、过期键字典

**进阶问题**：
- 为什么 dict 要用两个哈希表？（实现渐进式 rehash）
- rehash 期间如何保证数据一致性？（查找查两个表，插入只插 ht[1]）
- 为什么哈希表大小必须是 2^n？（使用位运算替代取模，性能更高）
- Redis 如何防止哈希碰撞攻击？（使用 SipHash 算法）
- dict 的负载因子为什么在 BGSAVE 时提高到 5？（避免 COW 期间频繁扩容导致内存翻倍）
