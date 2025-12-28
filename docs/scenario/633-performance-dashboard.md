---
layout: default
title: "数据看板从15s优化到54ms，如何做到？"
parent: 大厂项目场景实战
nav_order: 633
description: "讲解报表查询优化，包括预计算、缓存、异步加载等策略"
date: 2025-12-28
---

# 数据看板从15s优化到54ms，如何做到？

## 业务场景

电销系统的数据看板，展示各维度的销售数据：
- 今日通话量、成单量、成单金额
- 按团队、按人员的业绩排名
- 趋势图（最近7天/30天）

**问题**：页面加载需要15秒，用户体验极差。

---

## 性能分析

### 原始架构

```
前端请求 → 后端服务 → 实时查询MySQL → 返回结果
                           │
                     多个复杂聚合查询
                     每个查询2-5秒
```

### 慢查询分析

```sql
-- 今日成单统计（3秒）
SELECT team_id, COUNT(*), SUM(amount)
FROM orders
WHERE create_time >= CURDATE()
GROUP BY team_id;

-- 人员排名（5秒）
SELECT user_id, SUM(amount) as total
FROM orders
WHERE create_time >= CURDATE()
GROUP BY user_id
ORDER BY total DESC
LIMIT 10;

-- 趋势数据（7秒）
SELECT DATE(create_time), SUM(amount)
FROM orders
WHERE create_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DATE(create_time);
```

---

## 优化策略

### 策略一：预计算 + 缓存

将复杂聚合提前计算好，存入汇总表或缓存。

```java
// 定时任务：每5分钟预计算
@Scheduled(cron = "0 */5 * * * ?")
public void preComputeDashboard() {
    // 计算各维度数据
    DashboardData data = new DashboardData();
    data.setTodayCalls(orderMapper.countTodayCalls());
    data.setTodayOrders(orderMapper.countTodayOrders());
    data.setTeamRanking(orderMapper.getTeamRanking());
    data.setUserRanking(orderMapper.getUserRanking());
    data.setTrend(orderMapper.getTrendData());
    
    // 存入Redis
    redisTemplate.opsForValue().set("dashboard:data", 
        JSON.toJSONString(data), 6, TimeUnit.MINUTES);
}

// 查询接口：直接读缓存
public DashboardData getDashboard() {
    String json = redisTemplate.opsForValue().get("dashboard:data");
    return JSON.parseObject(json, DashboardData.class);
}
```

**效果**：查询时间从15秒降到54ms（只是Redis读取）。

### 策略二：增量更新

不必每次全量计算，可以增量更新。

```java
// 订单创建时增量更新
@TransactionalEventListener
public void onOrderCreated(OrderCreatedEvent event) {
    Order order = event.getOrder();
    
    // 更新今日统计
    String key = "dashboard:today:" + LocalDate.now();
    redisTemplate.opsForHash().increment(key, "orderCount", 1);
    redisTemplate.opsForHash().increment(key, "totalAmount", order.getAmount());
    
    // 更新团队统计
    String teamKey = "dashboard:team:" + order.getTeamId();
    redisTemplate.opsForHash().increment(teamKey, "amount", order.getAmount());
}
```

### 策略三：分层加载

首屏快速展示关键指标，详细数据异步加载。

```javascript
// 前端分层加载
async function loadDashboard() {
    // 第一层：核心指标（优先加载）
    const summary = await api.getSummary();
    renderSummary(summary);
    
    // 第二层：排行榜（次优先）
    const ranking = await api.getRanking();
    renderRanking(ranking);
    
    // 第三层：趋势图（可延迟）
    const trend = await api.getTrend();
    renderTrend(trend);
}
```

### 策略四：物化视图

对于复杂查询，可以使用物化视图。

```sql
-- 创建汇总表（每日定时刷新）
CREATE TABLE daily_order_summary (
    stat_date DATE PRIMARY KEY,
    order_count INT,
    total_amount DECIMAL(15,2),
    call_count INT,
    update_time DATETIME
);

-- 定时刷新
INSERT INTO daily_order_summary (stat_date, order_count, total_amount, call_count)
SELECT DATE(create_time), COUNT(*), SUM(amount), SUM(call_count)
FROM orders
WHERE DATE(create_time) = CURDATE()
ON DUPLICATE KEY UPDATE
    order_count = VALUES(order_count),
    total_amount = VALUES(total_amount);
```

### 策略五：ES聚合查询

对于维度多、查询灵活的场景，使用ES。

```java
public DashboardData getDashboardFromES() {
    SearchRequest request = new SearchRequest("orders");
    
    SearchSourceBuilder source = new SearchSourceBuilder();
    source.size(0);  // 不需要文档，只要聚合结果
    
    // 按团队聚合
    source.aggregation(AggregationBuilders.terms("by_team")
        .field("team_id")
        .subAggregation(AggregationBuilders.sum("amount").field("amount")));
    
    // 按日期聚合
    source.aggregation(AggregationBuilders.dateHistogram("by_date")
        .field("create_time")
        .calendarInterval(DateHistogramInterval.DAY));
    
    request.source(source);
    return parseResponse(client.search(request));
}
```

---

## 最终架构

```
前端请求
    │
    ├── 核心指标 → Redis（预计算结果）→ 54ms
    │
    ├── 排行榜 → Redis（增量更新）→ 30ms
    │
    └── 趋势图 → ES聚合查询 → 200ms
    
定时任务
    │
    ├── 每5分钟 → 预计算核心指标
    │
    └── 每天凌晨 → 同步数据到ES
```

---

## 优化效果

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 首屏加载 | 15秒 | 54ms | 278倍 |
| 排行榜 | 5秒 | 30ms | 167倍 |
| 趋势图 | 7秒 | 200ms | 35倍 |

---

## 面试答题框架

```
原始问题：实时聚合查询，15秒加载

优化思路：
1. 预计算：定时任务提前算好，存Redis
2. 增量更新：订单创建时实时更新统计
3. 分层加载：首屏优先，详情异步
4. ES聚合：灵活查询走ES

技术选型：
- 核心指标：Redis预计算
- 排行榜：Redis ZSet
- 趋势图：ES或物化视图

效果：15秒 → 54ms
```

---

## 总结

| 策略 | 适用场景 | 效果 |
|------|----------|------|
| 预计算缓存 | 数据变化不频繁 | 极快 |
| 增量更新 | 实时性要求高 | 快+实时 |
| 物化视图 | 固定维度报表 | 快 |
| ES聚合 | 灵活多维分析 | 快+灵活 |
