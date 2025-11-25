---
title: "Redis的Hash是如何实现的？"
date: 2025-11-02
description: "深入解析Redis Hash的底层实现，包括ListPack/ZipList和HashTable的双重编码、渐进式rehash机制及应用场景"
author: "wuxl"
categories: [中间件]
tags: [Redis, Hash, HashTable, ListPack, ZipList]
nav_order: 407
parent: Redis
---
## 问题

Redis的Hash是如何实现的？

## 答案

### 1. 核心概念

Redis的Hash是一个**键值对集合**，类似Java的HashMap。底层采用**双重编码机制**：数据量小时使用紧凑的ListPack/ZipList，数据量大时转换为HashTable。

---

### 2. 双重编码机制

#### 2.1 编码切换条件

**配置参数**：
```bash
# Redis 7.0+ 使用ListPack
hash-max-listpack-entries 512   # 元素数量阈值
hash-max-listpack-value 64      # 单个值大小阈值（字节）

# Redis 7.0之前使用ZipList
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
```

**编码选择**：
```java
if (元素数量 <= 512 && 所有value大小 <= 64字节) {
    使用 ListPack（或ZipList）
} else {
    使用 HashTable
}
```

**查看编码**：
```bash
redis> HSET user:1001 name "Alice" age "25"
redis> OBJECT ENCODING user:1001
"listpack"

redis> HSET user:1001 bio "这是一个超过64字节的长文本........................"
redis> OBJECT ENCODING user:1001
"hashtable"  # 自动转换
```

---

### 3. ListPack/ZipList实现（紧凑编码）

#### 3.1 ZipList结构（Redis 7.0前）

```
<zlbytes><zltail><zllen><entry><entry>...<entry><zlend>

zlbytes: 4字节，总字节数
zltail:  4字节，尾元素偏移量
zllen:   2字节，元素数量
entry:   键值对交替存储
zlend:   1字节，结束标记0xFF
```

**Hash存储方式**：键值对交替排列
```
ZipList: [key1, value1, key2, value2, ...]
```

**示例**：
```bash
HSET user:1001 name "Alice" age "25"
# ZipList: ["name", "Alice", "age", "25"]
```

---

#### 3.2 ListPack结构（Redis 7.0+）

**改进点**：解决ZipList的**级联更新问题**

**ZipList的问题**：
```java
// ZipList每个entry记录前一个entry的长度
entry = <prevlen><encoding><data>

// 问题场景：
插入大元素 → 后续所有entry的prevlen都要更新 → 级联更新
```

**ListPack的优化**：
```java
// ListPack每个entry只记录自身信息
entry = <encoding><data><len>

// len字段：从尾部向前遍历时使用
// 避免了级联更新问题
```

---

#### 3.3 优缺点

**优点**：
- **内存紧凑**：连续内存，无额外指针开销
- **缓存友好**：利用CPU缓存行，提升访问速度

**缺点**：
- **查找慢**：O(N)遍历查找键
- **更新慢**：需要移动后续元素

**适用场景**：小对象存储（如用户信息、配置项）

---

### 4. HashTable实现（哈希表编码）

#### 4.1 核心结构

```c
// 哈希表结构
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
    // ...其他字段
} dict;
```

---

#### 4.2 哈希算法

**MurmurHash2算法**：
```c
// 计算哈希值
hash = MurmurHash2(key, keylen, seed);

// 计算桶索引
index = hash & sizemask;  // 等价于 hash % size
```

**冲突解决**：链地址法（拉链法）
```
table[3] -> entry1 -> entry2 -> entry3
```

---

### 5. 渐进式Rehash机制

#### 5.1 触发条件

**扩容**（load factor > 1）：
```c
if (ht[0].used / ht[0].size >= 1 && 非BGSAVE/BGREWRITEAOF) {
    扩容至原来的2倍
}
```

**缩容**（load factor < 0.1）：
```c
if (ht[0].used / ht[0].size < 0.1) {
    缩容至第一个大于等于used的2^n
}
```

---

#### 5.2 渐进式Rehash流程

**为什么需要渐进式？**
- 大哈希表一次性rehash会阻塞Redis（可能数百万键）
- 分批迁移，避免长时间阻塞

**实现步骤**：
```java
1. 为ht[1]分配空间
2. 将rehashidx设置为0
3. 每次增删改查操作时：
   - 迁移ht[0].table[rehashidx]上的所有键到ht[1]
   - rehashidx++
4. 全部迁移完成后：
   - ht[0]指向ht[1]
   - ht[1]重置为空
   - rehashidx设置为-1
```

**期间的操作策略**：
- **查询**：先查ht[0]，未找到再查ht[1]
- **新增**：直接插入ht[1]
- **删除**：两个表都查找并删除

---

#### 5.3 主动Rehash

除了操作触发，Redis还会在定时任务中主动推进：
```c
// 每100ms执行一次
void databasesCron() {
    // 每次迁移100个桶
    dictRehashMilliseconds(db->dict, 1); // 1ms内尽可能多迁移
}
```

---

### 6. 应用场景与最佳实践

#### 6.1 对象存储

**方案对比**：
```java
// 方案1：String序列化整个对象
SET user:1001 '{"name":"Alice","age":25,"city":"Beijing"}'
// 缺点：修改任意字段都要序列化/反序列化整个对象

// 方案2：Hash存储对象字段
HMSET user:1001 name "Alice" age 25 city "Beijing"
// 优点：可单独修改字段，节省带宽
HSET user:1001 age 26  // 只更新年龄
```

**Java示例**：
```java
// 存储用户对象
Map<String, String> user = new HashMap<>();
user.put("name", "Alice");
user.put("age", "25");
user.put("city", "Beijing");
redisTemplate.opsForHash().putAll("user:1001", user);

// 获取单个字段
String name = (String) redisTemplate.opsForHash().get("user:1001", "name");

// 增量更新
redisTemplate.opsForHash().increment("user:1001", "age", 1);
```

---

#### 6.2 购物车

```java
// 用户ID作为key，商品ID作为field，数量作为value
HSET cart:1001 item:2001 2   // 用户1001的购物车，商品2001，数量2
HSET cart:1001 item:2002 1

// 修改数量
HINCRBY cart:1001 item:2001 1  // 增加1件

// 删除商品
HDEL cart:1001 item:2002

// 获取购物车所有商品
HGETALL cart:1001
```

---

#### 6.3 统计信息

```java
// 网站实时统计
HINCRBY stats:2024-11-02 pv 1        // 页面浏览量+1
HINCRBY stats:2024-11-02 uv 1        // 独立访客+1
HSET stats:2024-11-02 date "2024-11-02"

// 获取当天所有统计
HGETALL stats:2024-11-02
```

---

### 7. 性能优化建议

#### 7.1 控制Hash大小
- **小对象优化**：保持在512个字段以下，享受ListPack的内存优势
- **大对象拆分**：超大Hash（百万字段）考虑拆分为多个小Hash

#### 7.2 避免大Value
- 单个字段值过大会触发HashTable编码，增加内存开销
- 建议：大文本单独存储为String，Hash只存ID引用

#### 7.3 批量操作
```java
// 不推荐：多次网络往返
for (String field : fields) {
    redisTemplate.opsForHash().get(key, field);
}

// 推荐：一次获取多个字段
List<Object> values = redisTemplate.opsForHash().multiGet(key, fields);
```

---

### 8. 面试答题总结

**标准回答模板**：

> Redis的Hash采用**双重编码**机制：
> 1. **小对象**（≤512个字段且每个值≤64字节）：使用**ListPack**（或ZipList），键值对交替存储在连续内存，节省空间
> 2. **大对象**：使用**HashTable**，采用MurmurHash2算法和链地址法解决冲突
> 3. **渐进式rehash**：扩容时分批迁移数据，避免阻塞，期间同时维护两个哈希表
>
> ListPack相比ZipList解决了级联更新问题（Redis 7.0+），提升了更新性能。

**常见追问**：
- **为什么需要渐进式rehash？** → 大表一次性rehash会阻塞Redis，分批迁移保证可用性
- **rehash期间如何查询？** → 先查ht[0]，未找到再查ht[1]；新增直接写ht[1]
- **ZipList的级联更新问题？** → 插入大元素导致后续所有entry的prevlen字段都要更新
- **Hash和String存对象的区别？** → Hash可单独操作字段，String需序列化整个对象

