---
layout: post
title: "Redis 大 key 问题"
date: 2025-11-08
description: "深入解析Redis大key问题的危害、发现方法、解决方案及最佳实践"
author: "wuxl"
categories: [中间件]
tags: [Redis, 性能优化, 大key, 最佳实践]
---

## 问题

Redis 大 key 问题是什么？如何发现和解决？

## 答案

### 1. 什么是大 key

**大 key** 指占用内存空间较大或包含元素数量过多的 key，通常包括：

- **String 类型**：value 超过 10KB
- **List/Set/Hash/ZSet**：元素数量超过 5000 个
- **集合类型**：单个元素过大或整体占用内存超过 10MB

### 2. 大 key 的危害

#### 2.1 性能问题
- **阻塞主线程**：大 key 的读写操作耗时长，Redis 单线程模型会导致其他请求排队等待
- **网络拥塞**：大 key 数据传输占用大量带宽，影响其他请求
- **慢查询**：操作大 key 容易触发慢查询，影响整体响应时间

#### 2.2 内存问题
- **内存分布不均**：大 key 占用过多内存，导致内存碎片增加
- **过期删除阻塞**：大 key 过期时，DEL 操作会阻塞主线程
- **持久化影响**：RDB/AOF 持久化时，大 key 会增加 fork 子进程的内存开销

#### 2.3 集群问题
- **数据倾斜**：在 Redis Cluster 中，大 key 导致某个节点内存占用过高
- **主从同步延迟**：大 key 的同步会增加主从复制的延迟
- **故障恢复慢**：节点宕机后，大 key 的迁移和恢复耗时长

### 3. 如何发现大 key

#### 3.1 使用 redis-cli 工具

```bash
# --bigkeys 参数扫描大 key（采样统计）
redis-cli --bigkeys

# 指定数据库
redis-cli -n 0 --bigkeys

# 输出到文件
redis-cli --bigkeys > bigkeys.txt
```

**优点**：简单快速，官方工具
**缺点**：只能找到每种类型最大的 key，无法自定义阈值

#### 3.2 使用 MEMORY USAGE 命令（Redis 4.0+）

```bash
# 查看某个 key 占用的内存字节数
MEMORY USAGE mykey

# 采样精度（SAMPLES 参数，默认 5）
MEMORY USAGE mykey SAMPLES 10
```

#### 3.3 使用 SCAN + DEBUG OBJECT

```bash
# 扫描所有 key
SCAN 0 MATCH * COUNT 100

# 查看 key 的序列化长度
DEBUG OBJECT mykey
```

#### 3.4 使用 RDB 分析工具

```bash
# 使用 redis-rdb-tools 分析 RDB 文件
pip install rdbtools
rdb --command memory dump.rdb --bytes 10240 --largest 10
```

#### 3.5 监控告警
- **Redis 慢查询日志**：`SLOWLOG GET` 查看慢查询
- **监控系统**：Prometheus + Grafana 监控内存使用、命令耗时
- **自定义脚本**：定期扫描并告警

### 4. 解决方案

#### 4.1 拆分大 key

**String 类型拆分**：

```java
// 原始大 key
jedis.set("user:1:info", largeJsonString); // 假设 100KB

// 拆分为多个小 key
jedis.set("user:1:info:base", baseInfo);      // 10KB
jedis.set("user:1:info:detail", detailInfo);  // 20KB
jedis.set("user:1:info:extra", extraInfo);    // 70KB
```

**Hash 类型拆分**：

```java
// 原始大 Hash（10000 个 field）
jedis.hset("user:1:orders", "order1", "data1");
// ... 10000 个订单

// 拆分为多个小 Hash（按时间或 ID 分片）
jedis.hset("user:1:orders:2024", "order1", "data1");
jedis.hset("user:1:orders:2023", "order2", "data2");

// 或按 hash 分片
int shardId = orderId.hashCode() % 10;
jedis.hset("user:1:orders:" + shardId, orderId, data);
```

**List 类型拆分**：

```java
// 原始大 List
jedis.lpush("user:1:messages", msg); // 10000 条消息

// 拆分为多个小 List（按时间或序号）
jedis.lpush("user:1:messages:page:0", msg);  // 0-999
jedis.lpush("user:1:messages:page:1", msg);  // 1000-1999
```

#### 4.2 压缩数据

```java
// 使用压缩算法减少存储空间
public String compress(String data) {
    byte[] compressed = Gzip.compress(data.getBytes());
    return Base64.getEncoder().encodeToString(compressed);
}

// 存储压缩后的数据
String compressed = compress(largeData);
jedis.set("user:1:info", compressed);
```

#### 4.3 设置合理的过期时间

```java
// 避免大 key 长期占用内存
jedis.setex("user:1:cache", 3600, data); // 1 小时过期
```

#### 4.4 异步删除（Redis 4.0+）

```java
// 使用 UNLINK 代替 DEL，异步删除大 key
jedis.unlink("big_key");

// 配置 lazy-free 机制
// lazyfree-lazy-eviction yes
// lazyfree-lazy-expire yes
// lazyfree-lazy-server-del yes
```

#### 4.5 渐进式删除

**Hash/Set/ZSet 渐进式删除**：

```java
public void deleteBigHash(Jedis jedis, String key) {
    // 每次删除 100 个 field
    int batchSize = 100;
    ScanParams params = new ScanParams().count(batchSize);
    String cursor = "0";

    do {
        ScanResult<Map.Entry<String, String>> result =
            jedis.hscan(key, cursor, params);

        List<String> fields = result.getResult().stream()
            .map(Map.Entry::getKey)
            .collect(Collectors.toList());

        if (!fields.isEmpty()) {
            jedis.hdel(key, fields.toArray(new String[0]));
        }

        cursor = result.getCursor();
    } while (!"0".equals(cursor));

    // 最后删除 key
    jedis.del(key);
}
```

**List 渐进式删除**：

```java
public void deleteBigList(Jedis jedis, String key) {
    int batchSize = 100;
    long len;

    while ((len = jedis.llen(key)) > 0) {
        if (len > batchSize) {
            // 保留前面的元素，删除后面的
            jedis.ltrim(key, 0, len - batchSize - 1);
        } else {
            // 剩余元素较少，直接删除
            jedis.del(key);
            break;
        }
    }
}
```

### 5. 最佳实践

#### 5.1 设计阶段预防
- **控制 value 大小**：String 类型建议不超过 10KB
- **控制集合元素数量**：List/Set/Hash/ZSet 建议不超过 5000 个
- **合理设计数据结构**：避免将大量数据存储在单个 key 中

#### 5.2 监控和告警
- **定期扫描**：使用 `--bigkeys` 或自定义脚本定期扫描
- **慢查询监控**：关注 `SLOWLOG`，及时发现性能问题
- **内存监控**：监控 Redis 内存使用情况，设置告警阈值

#### 5.3 运维规范
- **使用 UNLINK**：删除大 key 时使用 `UNLINK` 代替 `DEL`
- **启用 lazy-free**：配置 Redis 的 lazy-free 机制
- **避免 KEYS 命令**：生产环境禁用 `KEYS *`，使用 `SCAN` 代替

#### 5.4 业务优化
- **缓存预热**：分批加载大 key，避免一次性加载
- **读写分离**：大 key 的读操作可以走从库
- **降级策略**：大 key 访问失败时，提供降级方案

### 6. 总结

| 维度 | 关键点 |
|------|--------|
| **危害** | 阻塞主线程、内存倾斜、主从同步延迟 |
| **发现** | `--bigkeys`、`MEMORY USAGE`、RDB 分析工具 |
| **解决** | 拆分 key、压缩数据、异步删除、渐进式删除 |
| **预防** | 控制大小、合理设计、监控告警、运维规范 |

**面试要点**：
1. 能说出大 key 的定义和危害（性能、内存、集群）
2. 掌握至少 2 种发现大 key 的方法
3. 能给出拆分、压缩、异步删除等解决方案
4. 了解 Redis 4.0+ 的 UNLINK 和 lazy-free 机制
