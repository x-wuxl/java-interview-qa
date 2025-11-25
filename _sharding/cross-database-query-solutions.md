---
title: "分库分表后如何解决跨库查询？"
date: 2025-11-02
description: "深入探讨分库分表后跨库查询的挑战与解决方案：应用层聚合、全局表、冗余字段、数据同步、CQRS等实战策略"
author: "wuxl"
categories: [分布式]
tags: [分库分表, 跨库查询, 数据聚合, 全局表, CQRS]
nav_order: 517
parent: 分库分表
---
## 问题

分库分表后如何解决跨库查询？

## 答案

### 1. 核心挑战

分库分表后，原本在单库中通过 `JOIN`、`GROUP BY`、`ORDER BY` 等操作轻松完成的查询，现在需要跨多个数据库执行，面临以下问题：

- **无法使用数据库的JOIN**：数据分散在不同的库表中
- **分页查询困难**：全局排序需要查询所有分片
- **聚合统计复杂**：COUNT、SUM等需要汇总多个分片的结果
- **性能下降**：需要访问多个数据源，增加网络开销

### 2. 主要解决方案

#### 2.1 应用层聚合（最常用）

**原理**：在应用层查询所有相关分片，然后在内存中合并结果

**实现示例**：

```java
// 场景：查询用户的所有订单并按时间排序
public class CrossShardQueryService {

    @Autowired
    private List<DataSource> shardDataSources;

    // 跨库分页查询
    public List<Order> queryOrders(Long userId, int page, int size) {
        List<Order> allOrders = new ArrayList<>();

        // 1. 并行查询所有分片
        List<CompletableFuture<List<Order>>> futures = shardDataSources.stream()
            .map(ds -> CompletableFuture.supplyAsync(() ->
                queryFromShard(ds, userId, page * size)  // 每个分片多取一些数据
            ))
            .collect(Collectors.toList());

        // 2. 等待所有查询完成
        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();

        // 3. 合并结果
        futures.forEach(f -> allOrders.addAll(f.join()));

        // 4. 内存排序
        allOrders.sort(Comparator.comparing(Order::getCreateTime).reversed());

        // 5. 内存分页
        return allOrders.stream()
            .skip(page * size)
            .limit(size)
            .collect(Collectors.toList());
    }

    // 跨库聚合查询
    public OrderStatistics queryStatistics(String date) {
        List<OrderStatistics> shardStats = shardDataSources.parallelStream()
            .map(ds -> queryStatsFromShard(ds, date))
            .collect(Collectors.toList());

        // 聚合统计结果
        return OrderStatistics.builder()
            .totalAmount(shardStats.stream()
                .map(OrderStatistics::getTotalAmount)
                .reduce(BigDecimal.ZERO, BigDecimal::add))
            .totalCount(shardStats.stream()
                .mapToLong(OrderStatistics::getTotalCount)
                .sum())
            .build();
    }
}
```

**优点**：实现简单，灵活性高
**缺点**：需要查询所有分片，数据量大时性能差
**适用场景**：数据量不大、分片数量有限的场景

#### 2.2 全局表（字典表冗余）

**原理**：在每个分库中都保存一份完整的字典表数据

**实现示例**：

```sql
-- 每个分片数据库都保存完整的字典表
-- db_0, db_1, db_2, db_3 都有这些表：
CREATE TABLE dict_product_category (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    parent_id INT
);

CREATE TABLE dict_region (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    level TINYINT
);

-- 订单表只在各自分片中
CREATE TABLE order_0 (
    order_id BIGINT,
    user_id BIGINT,
    category_id INT,  -- 可以直接JOIN dict_product_category
    region_id INT     -- 可以直接JOIN dict_region
);
```

**优点**：避免跨库JOIN，查询性能好
**缺点**：数据冗余，更新时需要同步所有分片
**适用场景**：变更频率低的字典表、配置表

#### 2.3 数据冗余（宽表设计）

**原理**：在分片表中冗余常用的关联字段

**实现示例**：

```java
// 原始设计（需要跨库JOIN）
@Table("order")
public class Order {
    private Long orderId;
    private Long userId;
    private Long productId;  // 需要JOIN product表获取产品名称
}

// 冗余设计（避免跨库JOIN）
@Table("order")
public class Order {
    private Long orderId;
    private Long userId;
    private Long productId;
    private String productName;      // 冗余字段
    private BigDecimal productPrice; // 冗余字段
    private String categoryName;     // 冗余字段
}

// 创建订单时同步冗余数据
public void createOrder(OrderDTO dto) {
    Product product = productService.getById(dto.getProductId());

    Order order = Order.builder()
        .orderId(generateId())
        .userId(dto.getUserId())
        .productId(product.getId())
        .productName(product.getName())        // 冗余
        .productPrice(product.getPrice())      // 冗余
        .categoryName(product.getCategoryName()) // 冗余
        .build();

    orderRepository.save(order);
}
```

**优点**：查询性能好，无需跨库
**缺点**：数据冗余，存在一致性问题
**适用场景**：读多写少、允许短暂数据不一致的场景

#### 2.4 数据同步到查询库（CQRS）

**原理**：通过binlog、消息队列等将数据同步到专门的查询库（如ES、ClickHouse）

**实现示例**：

```java
// 1. 监听binlog将数据同步到ES
@Component
public class OrderBinlogListener {

    @Autowired
    private ElasticsearchClient esClient;

    @BinlogListener(table = "order_*")
    public void onOrderChange(BinlogEvent event) {
        Order order = event.getData();

        // 同步到ES
        OrderDocument doc = OrderDocument.builder()
            .orderId(order.getOrderId())
            .userId(order.getUserId())
            .productName(order.getProductName())
            .amount(order.getAmount())
            .createTime(order.getCreateTime())
            .build();

        esClient.index("order", doc);
    }
}

// 2. 从ES查询
@Service
public class OrderSearchService {

    @Autowired
    private ElasticsearchClient esClient;

    // 复杂查询都走ES
    public List<Order> search(OrderQuery query) {
        BoolQuery boolQuery = BoolQuery.of(b -> b
            .must(m -> m.range(r -> r
                .field("createTime")
                .gte(query.getStartTime())
                .lte(query.getEndTime())))
            .must(m -> m.term(t -> t
                .field("userId")
                .value(query.getUserId())))
        );

        return esClient.search(boolQuery, Order.class);
    }
}
```

**优点**：支持复杂查询，性能好
**缺点**：架构复杂，存在数据延迟
**适用场景**：复杂查询多、对实时性要求不高的场景

#### 2.5 ER分片（关联数据在同一分片）

**原理**：将有关联关系的数据路由到同一个分片

**实现示例**：

```java
// 用户和订单按相同的分片键（userId）分片
public class ERShardingStrategy {

    // 用户表分片
    public String routeUser(Long userId) {
        int shardIndex = Math.abs(userId.hashCode() % 4);
        return "db_" + shardIndex;
    }

    // 订单表使用相同的分片策略
    public String routeOrder(Long userId) {
        // 使用userId而不是orderId作为分片键
        int shardIndex = Math.abs(userId.hashCode() % 4);
        return "db_" + shardIndex;
    }
}

// 这样同一用户的订单和用户信息在同一个库，可以直接JOIN
@Service
public class UserOrderService {

    public UserOrderVO getUserWithOrders(Long userId) {
        // 路由到同一个库
        String db = shardingStrategy.routeUser(userId);

        // 可以在同一个库内JOIN
        return jdbcTemplate.queryForObject(
            "SELECT u.*, o.* FROM user u " +
            "LEFT JOIN order o ON u.user_id = o.user_id " +
            "WHERE u.user_id = ?",
            new Object[]{userId},
            UserOrderVO.class
        );
    }
}
```

**优点**：避免跨库JOIN，保持关联查询能力
**缺点**：分片键选择受限，可能导致数据倾斜
**适用场景**：有明确父子关系的业务（如用户-订单、商户-商品）

### 3. 不同场景的解决方案选择

| 查询类型 | 推荐方案 | 说明 |
|---------|---------|------|
| **按分片键精确查询** | 直接路由 | 最高效，避免跨库 |
| **关联字典表** | 全局表 | 字典表在每个分片都有副本 |
| **关联主表** | ER分片 | 关联数据在同一分片 |
| **复杂查询/全文搜索** | 同步到ES | 利用ES的强大查询能力 |
| **统计分析** | 同步到ClickHouse | OLAP场景，数据仓库 |
| **少量数据聚合** | 应用层聚合 | 简单直接 |
| **实时性要求高** | 数据冗余 | 避免关联查询 |

### 4. 最佳实践

#### 4.1 查询优化原则

```java
// ✅ 好的实践：尽量带上分片键
public List<Order> queryOrders(Long userId) {
    // 可以精确路由到某个分片
    return orderRepository.findByUserId(userId);
}

// ❌ 避免：不带分片键的全局查询
public List<Order> queryOrdersByProductId(Long productId) {
    // 需要查询所有分片，性能差
    return orderRepository.findByProductId(productId);
}

// ✅ 解决方案：冗余userId或使用ES
@Table("order")
public class Order {
    private Long orderId;
    private Long userId;      // 分片键
    private Long productId;
    private Long sellerId;    // 冗余卖家ID，便于按卖家查询
}
```

#### 4.2 分页查询优化

```java
public class CrossShardPagingOptimization {

    // ❌ 错误做法：从每个分片取全部数据
    public List<Order> badPaging(int page, int size) {
        List<Order> allOrders = new ArrayList<>();
        for (DataSource ds : shardDataSources) {
            // 每个分片都取全部数据，内存占用大
            allOrders.addAll(queryAll(ds));
        }
        return allOrders.stream()
            .skip(page * size)
            .limit(size)
            .collect(Collectors.toList());
    }

    // ✅ 正确做法：从每个分片取 (page + 1) * size 条数据
    public List<Order> goodPaging(int page, int size) {
        int fetchSize = (page + 1) * size;  // 关键优化
        List<Order> allOrders = new ArrayList<>();

        for (DataSource ds : shardDataSources) {
            // 每个分片只取需要的数据量
            allOrders.addAll(queryTopN(ds, fetchSize));
        }

        return allOrders.stream()
            .sorted(Comparator.comparing(Order::getCreateTime).reversed())
            .skip(page * size)
            .limit(size)
            .collect(Collectors.toList());
    }
}
```

### 5. 核心要点总结

1. **尽量避免跨库查询**，在设计阶段就要考虑分片键的选择
2. **字典表使用全局表**，在每个分片都保存一份完整数据
3. **关联查询优先考虑ER分片**，将关联数据放在同一分片
4. **复杂查询使用CQRS**，同步到ES或ClickHouse等专用查询引擎
5. **数据冗余是常用手段**，用空间换时间，但要注意一致性问题
6. **应用层聚合适合小数据量**，大数据量需要从架构上解决
7. **分页查询要优化**，不要从每个分片取全部数据，只取需要的topN
