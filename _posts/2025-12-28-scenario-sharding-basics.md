---
layout: post
title: "分库分表前需要了解哪些核心知识点？"
date: 2025-12-28
categories: [大厂项目场景实战, 分库分表实战]
tags: [分库分表, MySQL, ShardingSphere, 分片策略, 分布式ID]
description: "全面讲解分库分表的核心概念、分片策略、Sharding Key选择、分布式事务等关键知识点。"
---

# 分库分表前需要了解哪些核心知识点？

## 面试场景

面试官："你们的数据量多大？有没有做过分库分表？"

分库分表是大厂必问的高频话题，但不能只说"数据量大就分"，需要展现**系统的知识体系**。

---

## 为什么需要分库分表？

### 单库瓶颈

| 问题 | 表现 | 原因 |
|------|------|------|
| 存储瓶颈 | 磁盘空间不足 | 单表数据量过大 |
| 性能瓶颈 | 查询变慢 | B+树层级增加 |
| 连接瓶颈 | 连接数不足 | 单库连接数有限 |
| 并发瓶颈 | TPS上不去 | 锁竞争严重 |

### 一般阈值（经验值）

- 单表超过 **1000万~2000万** 考虑分表
- 单库超过 **500GB~1TB** 考虑分库
- 单库QPS超过 **10000** 考虑分库

---

## 分库分表的两种维度

### 垂直拆分

按**业务功能**拆分：

```
单体数据库
    │
    ├── 用户库（user_db）
    │      └── user, user_address...
    │
    ├── 订单库（order_db）
    │      └── orders, order_items...
    │
    └── 商品库（product_db）
           └── product, product_sku...
```

**优点**：业务解耦，便于维护
**缺点**：无法解决单表数据量过大问题

### 水平拆分

按**数据行**拆分：

```
orders表 ──水平拆分──> orders_0, orders_1, orders_2, orders_3
```

**分库**：解决连接数、存储容量瓶颈
**分表**：解决单表数据量、锁竞争问题

---

## 核心概念：Sharding Key

**Sharding Key**（分片键）是决定数据路由到哪个库/表的关键字段。

### 选择原则

| 原则 | 说明 | 示例 |
|------|------|------|
| 高频查询字段 | WHERE条件常用 | 订单表用user_id |
| 分布均匀 | 避免数据倾斜 | 避免用status |
| 不可变更 | 变更需要迁移 | 避免用updateable字段 |

### 常见选择

| 业务 | Sharding Key | 原因 |
|------|--------------|------|
| 订单 | user_id | 用户查询自己的订单 |
| 外卖 | city_id | 按城市维度隔离 |
| 日志 | 时间 | 按时间范围查询 |

---

## 分片策略

### 1. Hash取模

```
shard_index = hash(sharding_key) % shard_count
```

**优点**：分布均匀
**缺点**：扩容困难，需要数据迁移

### 2. 范围分片

```
if order_id < 10000000:    分片0
elif order_id < 20000000:  分片1
else:                      分片2
```

**优点**：扩容方便
**缺点**：可能数据倾斜，热点问题

### 3. 一致性Hash

```
                    ┌───节点A───┐
            ┌───────┤           ├───────┐
            │       │   Hash环  │       │
            │       └───────────┘       │
         节点D                        节点B
                    │
                  节点C

数据根据hash值落在环上的某个节点
```

**优点**：扩容只需迁移部分数据
**应用**：Redis Cluster、Cassandra

### 4. 时间分片

```sql
orders_2024_01
orders_2024_02
orders_2024_03
```

**适用**：日志、历史数据，有明显时间特征

---

## 分布式ID方案

分库分表后，自增ID无法保证全局唯一。

### 方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| UUID | 简单 | 无序，索引性能差 |
| 雪花算法 | 有序，性能高 | 依赖时钟，可能回拨 |
| 数据库号段 | 简单可靠 | 依赖DB |
| Leaf/Tinyid | 高可用 | 需要部署服务 |

### 雪花算法结构

```
| 1bit | 41bit时间戳 | 10bit机器ID | 12bit序列号 |
  符号    可用69年      1024台机器    4096/ms
```

**Java实现**：
```java
public class SnowflakeIdGenerator {
    private long datacenterId;
    private long workerId;
    private long sequence = 0L;
    private long lastTimestamp = -1L;
    
    public synchronized long nextId() {
        long timestamp = System.currentTimeMillis();
        if (timestamp < lastTimestamp) {
            throw new RuntimeException("时钟回拨");
        }
        if (timestamp == lastTimestamp) {
            sequence = (sequence + 1) & 4095;
            if (sequence == 0) {
                timestamp = waitNextMillis(timestamp);
            }
        } else {
            sequence = 0L;
        }
        lastTimestamp = timestamp;
        return ((timestamp - 1609459200000L) << 22) | (datacenterId << 17) 
               | (workerId << 12) | sequence;
    }
}
```

---

## 跨分片查询问题

### 问题场景

```sql
-- Sharding Key是user_id
-- 这个查询需要扫描所有分片！
SELECT * FROM orders WHERE create_time > '2024-01-01';
```

### 解决方案

**1. 冗余字段**
在订单表冗余 create_time 相关的分片信息

**2. 基因法**
将分片信息编码到ID中：
```
订单ID后4位 = user_id % 10000
```

**3. ES辅助查询**
复杂查询走ES，再根据ID回源

**4. 聚合表**
针对报表需求建立汇总表

---

## 分库分表中间件

### ShardingSphere

```yaml
# application.yml
spring:
  shardingsphere:
    datasource:
      names: ds0, ds1
      ds0:
        url: jdbc:mysql://localhost:3306/db0
      ds1:
        url: jdbc:mysql://localhost:3306/db1
    rules:
      sharding:
        tables:
          orders:
            actual-data-nodes: ds$->{0..1}.orders_$->{0..3}
            table-strategy:
              standard:
                sharding-column: user_id
                sharding-algorithm-name: orders-inline
        sharding-algorithms:
          orders-inline:
            type: INLINE
            props:
              algorithm-expression: orders_$->{user_id % 4}
```

### 其他方案

| 方案 | 类型 | 特点 |
|------|------|------|
| ShardingSphere-JDBC | 客户端 | 无需代理，性能好 |
| ShardingSphere-Proxy | 代理 | 对应用透明 |
| MyCat | 代理 | 成熟稳定 |
| Vitess | 代理 | 云原生，YouTube使用 |

---

## 分布式事务

分库分表后，跨库事务是个大问题。

### 解决方案

| 方案 | 一致性 | 性能 | 适用场景 |
|------|--------|------|----------|
| 2PC/XA | 强一致 | 差 | 金融核心 |
| TCC | 最终一致 | 中 | 复杂业务 |
| SAGA | 最终一致 | 好 | 长事务 |
| 本地消息表 | 最终一致 | 好 | 一般业务 |

详见分布式事务相关章节。

---

## 面试答题框架

```
什么时候分：
- 单表1000万+、单库500GB+、QPS 10000+

怎么分：
- 垂直拆分：按业务
- 水平拆分：按数据行

分片策略：
- Hash取模（均匀）
- 范围分片（扩容）
- 一致性Hash（弹性）

核心问题及解决：
- 分布式ID：雪花算法
- 跨分片查询：ES辅助
- 分布式事务：Seata/本地消息表
```

---

## 总结

| 知识点 | 核心内容 |
|--------|----------|
| Sharding Key | 选择高频、均匀、不变的字段 |
| 分片策略 | Hash取模、范围、一致性Hash |
| 分布式ID | 雪花算法、号段模式 |
| 跨分片查询 | ES辅助、冗余、聚合表 |
| 分布式事务 | 柔性事务优先 |
