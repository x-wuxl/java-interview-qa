---
layout: post
title: "如何实现排行榜，例如高考成绩排序？"
date: 2025-11-16
categories: ["系统设计与高并发实战"]
tags: ["排行榜", "Redis", "系统设计"]
description: "解析高并发排行榜系统的设计要点。"
---

### 核心概念
排行榜需要对海量数据进行实时排序和查询，支持写入分数、获取区间排名、查询个人名次等功能，关注有序性、实时性与可扩展性。

### 原理或源码关键点
1. **数据结构选择**：Redis ZSet（跳表 + 哈希）支持 O(logN) 插入和区间查询，是实时榜单首选；对超大规模可结合 ClickHouse/Elasticsearch 做离线榜单。
2. **写入路径**：分数写入 ZADD，若有并发更新需以分数为 score，或存储复合值（成绩 + 时间戳）保证稳定排序。
3. **读取路径**：ZRANGE/ZREVRANGE 获取 TopN；ZREVRANK 查询个人排名。结合缓存层 + 本地热点副本减轻 Redis 压力。
4. **持久化与回放**：开启 AOF + RDB 或 Canal 订阅 binlog 将成绩同步到 HDFS/OLAP，便于归档与重放。

### 性能与分布式考量
- 分片：按地区或年份分库分表，Redis Cluster 分片维护子榜；需要全局榜时再做聚合（MapReduce 或归并 TopK）。
- 一致性：写入采用流水线批量提交，并配合乐观锁或 Lua 脚本实现事务，防止同一考生分数被覆盖。
- 热点防护：Top 榜查询极多，可将 Top100 缓存于内存并定期从 Redis 拉取增量；同时加速个人名次查询可预估排名范围并用二分定位。

### 示例与总结
```java
// 写入成绩
redisTemplate.opsForZSet().add("gaokao:2025", studentId, totalScore);
// 查询个人排名（倒序）
Long rank = redisTemplate.opsForZSet().reverseRank("gaokao:2025", studentId);
```
高并发排行榜一般采用“Redis ZSet + 分片 + 持久化回放”的架构，并辅以热点缓存、批量写入和一致性策略，才能兼顾实时性、精确性与可靠性。
