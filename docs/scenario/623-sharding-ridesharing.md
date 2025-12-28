---
layout: default
title: "复杂业务场景（顺风车）的分库分表如何设计？"
parent: 大厂项目场景实战
nav_order: 623
description: "通过顺风车场景讲解多维度查询的分库分表设计，包括主表+ES索引方案"
date: 2025-12-28
---

# 复杂业务场景（顺风车）的分库分表如何设计？

## 业务场景

顺风车平台订单数据，日均订单500万，历史订单超过20亿条。

**核心挑战**：不同于电商订单只需按用户查询，顺风车需要**多维度查询**：

| 角色 | 查询维度 |
|------|----------|
| 乘客 | 按乘客ID查 |
| 车主 | 按车主ID查 |
| 客服 | 按订单ID查 |
| 城市运营 | 按城市+时间查 |

**问题**：无论选择哪个字段作为Sharding Key，其他维度都需要跨分片查询！

---

## 方案分析

### 方案一：选择乘客ID

```
分片键：passenger_id

乘客查订单 → 精准路由 ✅
车主查订单 → 跨分片扫描 ❌
```

### 方案二：选择车主ID

```
分片键：driver_id

车主查订单 → 精准路由 ✅
乘客查订单 → 跨分片扫描 ❌
```

### 方案三：双写冗余

```
orders_by_passenger（按乘客ID分片）
orders_by_driver（按车主ID分片）

乘客查订单 → 查orders_by_passenger ✅
车主查订单 → 查orders_by_driver ✅
```

**缺点**：数据冗余，一致性维护复杂

---

## 推荐方案：主表 + ES索引

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                     写入流程                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   创建订单 → MySQL分库分表（按乘客ID） → 同步到ES        │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     查询流程                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   乘客查询 → MySQL精准路由                               │
│   车主查询 → ES查询 → 获取订单ID → MySQL回源             │
│   运营查询 → ES聚合                                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 核心设计

**1. MySQL主表（按乘客ID分片）**

```sql
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,        -- 包含分片基因
    passenger_id BIGINT NOT NULL, -- 分片键
    driver_id BIGINT NOT NULL,
    city_id INT NOT NULL,
    order_status TINYINT,
    create_time DATETIME,
    -- 其他字段
    KEY idx_passenger (passenger_id),
    KEY idx_create_time (create_time)
);
```

**2. 订单ID设计（基因法）**

```java
public long generateOrderId(long passengerId) {
    long snowflakeId = snowflake.nextId();
    // 将passengerId的分片信息编入订单ID
    int gene = (int) (passengerId % 1024);
    return (snowflakeId >> 10 << 10) | gene;
}
```

好处：通过订单ID即可路由到正确分片。

**3. ES索引结构**

```json
{
  "mappings": {
    "properties": {
      "order_id": { "type": "long" },
      "passenger_id": { "type": "long" },
      "driver_id": { "type": "long" },
      "city_id": { "type": "integer" },
      "order_status": { "type": "integer" },
      "create_time": { "type": "date" },
      "start_location": { "type": "geo_point" },
      "end_location": { "type": "geo_point" }
    }
  }
}
```

---

## 查询实现

### 乘客查询（走MySQL）

```java
public List<Order> getPassengerOrders(Long passengerId) {
    // 直接路由到对应分片
    return orderMapper.findByPassengerId(passengerId);
}
```

### 车主查询（ES + MySQL回源）

```java
public List<Order> getDriverOrders(Long driverId, int page, int size) {
    // 1. ES查询订单ID
    SearchRequest request = new SearchRequest("orders");
    request.source(new SearchSourceBuilder()
        .query(QueryBuilders.termQuery("driver_id", driverId))
        .sort("create_time", SortOrder.DESC)
        .from(page * size).size(size)
        .fetchSource(new String[]{"order_id", "passenger_id"}, null));
    
    SearchResponse response = esClient.search(request);
    
    // 2. 根据订单ID批量回源MySQL
    List<Long> orderIds = extractOrderIds(response);
    return orderMapper.findByIds(orderIds);
}
```

### 运营查询（纯ES）

```java
public DashboardData getCityStats(Integer cityId, LocalDate date) {
    SearchRequest request = new SearchRequest("orders");
    request.source(new SearchSourceBuilder()
        .query(QueryBuilders.boolQuery()
            .must(QueryBuilders.termQuery("city_id", cityId))
            .must(QueryBuilders.rangeQuery("create_time")
                .gte(date.atStartOfDay())
                .lt(date.plusDays(1).atStartOfDay())))
        .aggregation(AggregationBuilders.count("total"))
        .aggregation(AggregationBuilders.sum("amount").field("order_amount"))
        .size(0));
    
    return parseResponse(esClient.search(request));
}
```

---

## 数据同步

### Canal + Kafka实时同步

```
MySQL binlog → Canal → Kafka → ES Consumer → ES
```

```java
@KafkaListener(topics = "order-binlog")
public void syncToES(String message) {
    BinlogEvent event = JSON.parseObject(message, BinlogEvent.class);
    
    if ("INSERT".equals(event.getType()) || "UPDATE".equals(event.getType())) {
        Order order = event.getData();
        ESOrder esOrder = convertToESOrder(order);
        esClient.index(new IndexRequest("orders")
            .id(order.getId().toString())
            .source(JSON.toJSONString(esOrder), XContentType.JSON));
    }
}
```

### 延迟处理

ES同步有延迟（通常秒级），对于车主端可以接受：
- 刚完成的订单会有1-2秒延迟出现
- 实时性要求高的场景，可先查缓存

---

## 复杂查询场景

### 附近的顺风车（地理位置）

```java
public List<Order> findNearbyOrders(double lat, double lon, double distance) {
    SearchRequest request = new SearchRequest("orders");
    request.source(new SearchSourceBuilder()
        .query(QueryBuilders.boolQuery()
            .must(QueryBuilders.termQuery("order_status", 1))  // 待接单
            .must(QueryBuilders.geoDistanceQuery("start_location")
                .point(lat, lon)
                .distance(distance, DistanceUnit.KILOMETERS)))
        .sort(SortBuilders.geoDistanceSort("start_location", lat, lon)
            .order(SortOrder.ASC)));
    
    return extractOrders(esClient.search(request));
}
```

### 订单路径匹配

```java
// 车主发布行程后，匹配顺路乘客
public List<Order> matchPassengers(Route driverRoute) {
    // 使用ES的geo_shape查询
    // 匹配起点和终点都在车主路线附近的订单
    // 具体实现较复杂，需要路径规划算法配合
}
```

---

## 方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| 单一分片键 | 简单 | 跨分片查询多 |
| 双写冗余 | 两个维度都快 | 数据翻倍，一致性难 |
| 主表+ES | 灵活，支持复杂查询 | ES运维成本 |

### 推荐选择

- **小规模**：单一分片键 + 广播查询
- **中等规模**：双写冗余
- **大规模/复杂查询**：主表 + ES（推荐）

---

## 面试答题框架

```
场景特点：多维度查询（乘客/车主/城市）

核心挑战：
- 无论选哪个分片键，其他维度都需跨分片

解决方案：
1. MySQL按乘客ID分片（主要写入维度）
2. ES索引支持多维度查询
3. 基因法支持订单ID路由

查询策略：
- 乘客查询 → MySQL精准路由
- 车主/运营查询 → ES → MySQL回源

数据同步：
- Canal监听binlog
- Kafka异步同步到ES
```

---

## 总结

| 设计点 | 方案 |
|--------|------|
| 分片键 | 乘客ID（写入主维度） |
| 订单ID | 雪花ID + 基因法 |
| 车主查询 | ES索引 |
| 运营统计 | ES聚合 |
| 数据同步 | Canal + Kafka |
