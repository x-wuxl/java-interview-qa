---
layout: post
title: "分库分表的策略有哪些？"
date: 2025-11-02
description: "全面解析分库分表的各种策略：范围分片、哈希分片、一致性哈希、地理位置分片等，掌握不同场景下的最佳实践"
author: "wuxl"
categories: [分布式]
tags: [分库分表, 分片策略, 路由算法, 数据分片]
---

## 问题

分库分表的策略有哪些？

## 答案

### 1. 核心概念

分库分表策略本质上是**数据路由算法**，用于决定一条数据应该存储在哪个库、哪张表中。选择合适的分片策略直接影响系统的查询性能、扩展性和数据均衡性。

### 2. 主要分片策略

#### 2.1 范围分片（Range Sharding）

**原理**：按某个字段的值范围划分，如按ID、时间等

**优点**：
- 范围查询效率高
- 扩容时只需新增分片
- 数据分布直观，便于运维

**缺点**：
- 容易出现数据热点
- 分布可能不均匀

**实现示例**：

```java
// 按订单ID范围分表
public class RangeShardingStrategy {

    public String route(Long orderId) {
        if (orderId < 10_000_000) {
            return "order_0";
        } else if (orderId < 20_000_000) {
            return "order_1";
        } else if (orderId < 30_000_000) {
            return "order_2";
        } else {
            return "order_3";
        }
    }
}

// 按时间范围分表（常用于日志、订单等场景）
public class TimeRangeShardingStrategy {

    public String route(Date createTime) {
        String yearMonth = new SimpleDateFormat("yyyyMM").format(createTime);
        return "order_" + yearMonth;  // order_202501, order_202502...
    }
}
```

**适用场景**：
- 订单表按月份归档
- 日志表按日期分表
- 有明确范围查询需求的业务

#### 2.2 哈希取模分片（Hash Modulo）

**原理**：对分片键进行哈希运算后取模

**优点**：
- 数据分布均匀
- 实现简单
- 避免热点问题

**缺点**：
- 扩容困难（需要数据迁移）
- 范围查询需要访问所有分片

**实现示例**：

```java
// 按用户ID哈希分库分表
public class HashModuloStrategy {

    private static final int DB_COUNT = 4;    // 4个数据库
    private static final int TABLE_COUNT = 8; // 每个库8张表

    // 分库路由
    public String routeDatabase(Long userId) {
        int dbIndex = Math.abs(userId.hashCode() % DB_COUNT);
        return "db_" + dbIndex;  // db_0, db_1, db_2, db_3
    }

    // 分表路由
    public String routeTable(Long userId) {
        int tableIndex = Math.abs(userId.hashCode() % TABLE_COUNT);
        return "user_" + tableIndex;  // user_0 ~ user_7
    }

    // 完整路由
    public ShardingTarget route(Long userId) {
        return new ShardingTarget(
            routeDatabase(userId),
            routeTable(userId)
        );
    }
}
```

**适用场景**：
- 数据分布要求均匀
- 主要是点查询（根据ID查询）
- 分片数量相对固定

#### 2.3 一致性哈希（Consistent Hashing）

**原理**：使用哈希环，节点和数据都映射到环上，数据存储到顺时针最近的节点

**优点**：
- 扩容时只影响相邻节点
- 数据迁移量小

**缺点**：
- 实现复杂
- 可能出现数据倾斜（通过虚拟节点解决）

**实现示例**：

```java
public class ConsistentHashStrategy {

    private final TreeMap<Long, String> ring = new TreeMap<>();
    private final int virtualNodes = 150;  // 虚拟节点数

    // 添加物理节点
    public void addNode(String node) {
        for (int i = 0; i < virtualNodes; i++) {
            String virtualNode = node + "#" + i;
            long hash = hash(virtualNode);
            ring.put(hash, node);
        }
    }

    // 路由到目标节点
    public String route(Long userId) {
        long hash = hash(String.valueOf(userId));
        // 找到顺时针方向最近的节点
        Map.Entry<Long, String> entry = ring.ceilingEntry(hash);
        if (entry == null) {
            entry = ring.firstEntry();  // 环形结构
        }
        return entry.getValue();
    }

    private long hash(String key) {
        return MurmurHash.hash64(key);  // 使用MurmurHash
    }
}
```

**适用场景**：
- 需要频繁扩容的场景
- 分布式缓存（Redis集群）
- 节点动态变化的系统

#### 2.4 地理位置分片（Geo Sharding）

**原理**：按地理位置（地区、城市）划分

**实现示例**：

```java
public class GeoShardingStrategy {

    private static final Map<String, String> REGION_DB_MAP = Map.of(
        "华北", "db_north",
        "华东", "db_east",
        "华南", "db_south",
        "西南", "db_southwest"
    );

    public String route(String region) {
        return REGION_DB_MAP.getOrDefault(region, "db_default");
    }
}
```

**适用场景**：
- 跨国/跨地区业务
- 就近访问，减少延迟
- 数据主权要求（如GDPR）

#### 2.5 复合分片策略

**原理**：组合多种策略，先分库再分表

**实现示例**：

```java
public class CompositeShardingStrategy {

    private static final int DB_COUNT = 4;
    private static final int TABLE_COUNT = 16;

    public ShardingTarget route(Long userId) {
        // 先按用户ID哈希分库
        int dbIndex = Math.abs(userId.hashCode() % DB_COUNT);

        // 再按用户ID取模分表
        int tableIndex = (int) (userId % TABLE_COUNT);

        return new ShardingTarget(
            "db_" + dbIndex,
            "user_" + tableIndex
        );
    }
}
```

### 3. 分片策略对比

| 策略 | 数据均匀性 | 扩容难度 | 范围查询 | 实现复杂度 | 典型应用 |
|------|-----------|---------|---------|-----------|---------|
| **范围分片** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 订单归档、日志 |
| **哈希取模** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | 用户表、订单表 |
| **一致性哈希** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | 缓存、动态扩容场景 |
| **地理分片** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 国际化业务 |

### 4. 分片键的选择原则

```java
// 好的分片键特征：
// 1. 高基数（Cardinality）：取值范围广，分布均匀
// 2. 查询常用：大部分查询都包含分片键
// 3. 不可变性：分片键值不应频繁更新

// 示例：订单表的分片键选择
public class OrderShardingKeyChoice {

    // ❌ 不好的选择：订单状态（基数低，只有几个值）
    String shardingKey1 = order.getStatus();

    // ❌ 不好的选择：创建时间（范围查询多，但会造成热点）
    Date shardingKey2 = order.getCreateTime();

    // ✅ 推荐选择：订单ID（高基数、均匀分布、不可变）
    Long shardingKey3 = order.getOrderId();

    // ✅ 也可选择：用户ID（如果按用户查询订单是主要场景）
    Long shardingKey4 = order.getUserId();
}
```

### 5. 实际应用建议

#### 5.1 订单表分片策略

```java
// 推荐：用户ID哈希 + 订单ID范围
public class OrderShardingStrategy {

    public ShardingTarget route(Long userId, Long orderId) {
        // 按用户ID哈希分库（保证同一用户的订单在同一个库）
        int dbIndex = Math.abs(userId.hashCode() % 4);

        // 按订单ID取模分表
        int tableIndex = (int) (orderId % 16);

        return new ShardingTarget("db_" + dbIndex, "order_" + tableIndex);
    }
}
```

#### 5.2 用户表分片策略

```java
// 推荐：用户ID哈希取模
public class UserShardingStrategy {

    public ShardingTarget route(Long userId) {
        int dbIndex = Math.abs(userId.hashCode() % 4);
        int tableIndex = (int) (userId % 8);

        return new ShardingTarget("db_" + dbIndex, "user_" + tableIndex);
    }
}
```

### 6. 核心要点总结

1. **哈希取模是最常用的策略**，数据分布均匀，但扩容困难
2. **范围分片适合时间序列数据**，如日志、订单归档
3. **一致性哈希适合动态扩容场景**，如缓存系统
4. **分片键的选择至关重要**：高基数、查询常用、不可变
5. **实际应用中常采用复合策略**：分库和分表使用不同的策略
6. **预留扩展空间**：初期可以分多一些表（如256张），按需启用
