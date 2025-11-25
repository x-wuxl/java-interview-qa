---
title: "Redis有哪些数据结构？"
date: 2025-11-02
description: "全面解析Redis的五大基础数据类型和底层数据结构，包括String、List、Hash、Set、ZSet及其应用场景"
author: "wuxl"
categories: [中间件]
tags: [Redis, 数据结构, 面试]
nav_order: 400
parent: Redis
---
## 问题

Redis有哪些数据结构？

## 答案

### 1. 核心概念

Redis提供了**丰富的数据类型**，既包括面向用户的五大基础数据类型，也包括底层的高效数据结构实现。理解两者的对应关系是优化Redis使用的关键。

---

### 2. 五大基础数据类型

#### 2.1 String（字符串）
- **特点**：二进制安全，最大512MB
- **应用场景**：缓存、计数器、分布式锁、Session共享
- **常用命令**：`SET`、`GET`、`INCR`、`DECR`

```java
// 计数器示例
redisTemplate.opsForValue().increment("page:views:1001"); // 页面访问计数
```

#### 2.2 List（列表）
- **特点**：有序、可重复、双向链表
- **应用场景**：消息队列、时间线、最新动态
- **常用命令**：`LPUSH`、`RPUSH`、`LPOP`、`RPOP`、`LRANGE`

```java
// 简单消息队列
redisTemplate.opsForList().leftPush("queue:tasks", task); // 生产者
String task = redisTemplate.opsForList().rightPop("queue:tasks"); // 消费者
```

#### 2.3 Hash（哈希表）
- **特点**：键值对集合，类似Java的HashMap
- **应用场景**：对象存储、购物车、用户信息
- **常用命令**：`HSET`、`HGET`、`HMGET`、`HGETALL`

```java
// 存储用户信息
Map<String, String> user = new HashMap<>();
user.put("name", "张三");
user.put("age", "25");
redisTemplate.opsForHash().putAll("user:1001", user);
```

#### 2.4 Set（集合）
- **特点**：无序、不重复、支持交并差运算
- **应用场景**：标签、好友关系、去重
- **常用命令**：`SADD`、`SMEMBERS`、`SINTER`、`SUNION`

```java
// 共同关注
redisTemplate.opsForSet().intersect("user:1001:follows", "user:1002:follows");
```

#### 2.5 ZSet（有序集合）
- **特点**：有序、不重复、通过score排序
- **应用场景**：排行榜、延时队列、范围查询
- **常用命令**：`ZADD`、`ZRANGE`、`ZREVRANGE`、`ZRANGEBYSCORE`

```java
// 排行榜
redisTemplate.opsForZSet().add("rank:score", "player1", 9500.0);
Set<String> top10 = redisTemplate.opsForZSet().reverseRange("rank:score", 0, 9);
```

---

### 3. 底层数据结构实现

Redis的上层数据类型基于以下底层结构实现：

#### 3.1 SDS（Simple Dynamic String）
- **说明**：Redis自定义的字符串结构，相比C字符串增加了长度记录和预分配空间
- **优势**：O(1)获取长度、防止缓冲区溢出、支持二进制数据

#### 3.2 链表（Linked List）
- **说明**：双向链表，Redis 3.2前List的底层实现之一
- **特点**：插入删除O(1)，但内存不连续、指针占用额外空间

#### 3.3 跳表（Skip List）
- **说明**：多层有序链表，ZSet的核心实现
- **优势**：支持范围查询，平均O(log N)复杂度，实现简单

#### 3.4 哈希表（Hash Table）
- **说明**：类似Java的HashMap，采用链地址法解决冲突
- **特点**：支持渐进式rehash，避免阻塞

#### 3.5 整数集合（IntSet）
- **说明**：当Set中全是整数且数量较少时使用
- **优势**：紧凑存储，节省内存

#### 3.6 压缩列表（ZipList）
- **说明**：紧凑的连续内存数组，Redis 7.0前List/Hash/ZSet在数据量小时使用
- **优势**：内存紧凑，但插入删除需移动元素

#### 3.7 快速列表（QuickList）
- **说明**：Redis 3.2+ List的底层实现，结合链表和压缩列表
- **优势**：兼顾内存和性能

#### 3.8 紧凑列表（ListPack）
- **说明**：Redis 7.0+ 替代ZipList的新结构
- **优势**：解决了ZipList的级联更新问题

---

### 4. 数据类型与底层结构对应关系

| 数据类型 | 底层编码（Redis 7.0+） | 触发条件 |
|---------|----------------------|---------|
| **String** | SDS | 所有情况 |
| **List** | QuickList | 所有情况 |
| **Hash** | ListPack / HashTable | 元素少用ListPack，多了转HashTable |
| **Set** | IntSet / HashTable | 全整数且少用IntSet |
| **ZSet** | ListPack / SkipList+HashTable | 元素少用ListPack，多了转SkipList |

**查看编码方式**：
```bash
redis> OBJECT ENCODING mykey
"listpack"
```

---

### 5. 性能优化与场景选择

#### 5.1 类型选择原则
- **简单值**：用String（如计数器）
- **列表数据**：用List（如消息队列）
- **对象属性**：用Hash（如用户信息）
- **去重场景**：用Set（如标签）
- **排序需求**：用ZSet（如排行榜）

#### 5.2 内存优化
- **小对象优化**：控制元素数量和大小，触发紧凑编码（ListPack/IntSet）
  - Hash：`hash-max-listpack-entries 512`（默认）
  - ZSet：`zset-max-listpack-entries 128`（默认）
- **避免大Key**：单个Key的value过大会阻塞Redis
- **过期策略**：合理设置TTL，及时释放内存

---

### 6. 面试答题总结

**标准回答模板**：

> Redis提供五大基础数据类型：
> 1. **String**：最基础类型，用于缓存、计数器、分布式锁
> 2. **List**：有序列表，用于消息队列、时间线
> 3. **Hash**：键值对集合，用于对象存储、购物车
> 4. **Set**：无序不重复集合，用于标签、去重
> 5. **ZSet**：有序集合，用于排行榜、延时队列
>
> 底层基于SDS、跳表、哈希表、压缩列表等高效数据结构实现，会根据数据量自动选择合适的编码方式以优化内存和性能。

**常见追问**：
- **ZSet为什么用跳表而不是红黑树？** → 实现简单，支持范围查询，内存局部性好
- **List的底层实现？** → Redis 3.2+ 用QuickList（链表+压缩列表）
- **如何查看Key的底层编码？** → `OBJECT ENCODING key`

