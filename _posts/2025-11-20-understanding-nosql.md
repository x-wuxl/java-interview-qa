---
layout: post
title: 谈谈你对 NoSQL 的理解。
categories: [Database]
tags: [NoSQL, Redis, MongoDB, Architecture]
description: 宏观阐述 NoSQL（Not Only SQL）的定义、四大分类（KV, 文档, 列式, 图）及其与关系型数据库的互补关系。
keywords: NoSQL, Redis, MongoDB, CAP Theorem, 数据库选型
---

## 1. 核心概念

NoSQL（Not Only SQL）泛指非关系型的数据库。它的出现不是为了取代 SQL，而是为了解决关系型数据库在 **高并发、海量数据、高扩展性** 场景下的瓶颈。

## 2. NoSQL 的四大分类

| 分类 | 代表产品 | 特点 | 适用场景 |
| :--- | :--- | :--- | :--- |
| **键值存储 (Key-Value)** | **Redis**, Memcached | 读写极快，结构简单(Map) | 缓存、Session、计数器、排行榜 |
| **文档数据库 (Document)** | **MongoDB**, ES | Schema-free，格式灵活(JSON) | 日志、CMS、用户画像、非结构化数据 |
| **列式存储 (Column)** | **HBase**, Cassandra | 大数据量，列独立存储 | 离线分析、超大宽表、历史归档 |
| **图数据库 (Graph)** | **Neo4j** | 存储节点与关系 | 社交网络、推荐系统、知识图谱 |

## 3. NoSQL vs RDBMS (关系型数据库)

### 3.1 优势 (CAP 中的 AP)
1.  **高扩展性**：天生支持分布式集群，Scale Out（横向扩展）容易。
2.  **高性能**：通常基于内存或特定的存储结构（LSM Tree），读写性能远超 MySQL。
3.  **灵活模型**：无需预定义 Schema，适合敏捷开发。

### 3.2 劣势
1.  **弱一致性**：通常只保证最终一致性（BASE 理论），不支持强 ACID 事务。
2.  **查询功能弱**：不如 SQL 语言通用和强大，复杂关联查询（Join）困难。

## 4. 总结

**面试回答示例：**
"NoSQL 是对关系型数据库的补充。
我们通常使用 **Redis** 做高频热点数据的缓存，抗并发；
使用 **MongoDB** 存储日志或非结构化的运营配置数据；
使用 **HBase** 存储海量的历史订单数据供离线分析。
NoSQL 牺牲了强一致性和复杂的 SQL 能力，换取了极致的读写性能和水平扩展能力。在架构中，通常是 MySQL 存核心数据，NoSQL 存辅助数据，两者混合使用。"
