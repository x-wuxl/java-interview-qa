---
title: "什么是 ElasticSearch 的深度分页问题？如何解决？"
date: 2025-11-02
categories: [中间件, ElasticSearch]
tags: [ElasticSearch, 分页, 性能优化, 面试]
description: "深入理解 ElasticSearch 深度分页问题的原因及 Scroll API、Search After 等解决方案"
nav_order: 575
parent: ElasticSearch
---
## 核心概念

**深度分页问题**指的是当分页查询的页码很大时（如第 10000 页），ElasticSearch 需要在每个分片上获取并排序大量数据，导致**内存消耗大、性能急剧下降**的问题。

## 问题原因

### 1. From + Size 的工作机制

```java
// 查询第 100 页，每页 10 条
GET /products/_search
{
  "from": 1000,   // (100 - 1) * 10
  "size": 10,
  "query": { ... }
}
```

#### 执行流程
```
假设索引有 3 个分片：

Step 1: Coordinating Node 将查询分发到 3 个分片
Step 2: 每个分片返回 (from + size) = 1010 条数据
        - Shard 0 → 1010 条
        - Shard 1 → 1010 条
        - Shard 2 → 1010 条
        
Step 3: Coordinating Node 汇总 3030 条数据
Step 4: 在内存中排序 3030 条数据
Step 5: 取出第 1001-1010 条，返回 10 条

丢弃：3020 条（浪费资源）
```

### 2. 深度分页的性能问题

#### **内存消耗**
```
分页参数：from=10000, size=10
分片数：5
每个分片需要返回：10010 条
总数据量：5 * 10010 = 50050 条

Coordinating Node 需要在内存中处理 50050 条数据！
```

#### **CPU 消耗**
- 大量数据的排序操作
- 序列化和网络传输开销

#### **ES 默认限制**
```yaml
# 默认限制：from + size <= 10000
index.max_result_window: 10000

# 超过限制会报错
Result window is too large, from + size must be less than or equal to: [10000]
```

## 解决方案

### 方案一：Scroll API（快照 + 游标）

#### 1. 适用场景
- **全量数据导出**（如 ES 数据迁移）
- **非实时数据遍历**（数据不会频繁变化）
- **不关心排序**（按照索引顺序返回）

#### 2. 工作原理
- 创建快照（Snapshot），固定数据视图
- 使用游标（Scroll ID）分批获取数据
- 数据一致性高，但不反映最新写入

#### 3. 使用示例

```java
// Step 1: 初始化 Scroll
SearchRequest searchRequest = new SearchRequest("products");
searchRequest.scroll(TimeValue.timeValueMinutes(1L)); // 快照有效期 1 分钟

SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
sourceBuilder.query(QueryBuilders.matchAllQuery());
sourceBuilder.size(1000); // 每批 1000 条
searchRequest.source(sourceBuilder);

SearchResponse response = client.search(searchRequest, RequestOptions.DEFAULT);
String scrollId = response.getScrollId();

// Step 2: 循环获取数据
while (true) {
    SearchHit[] hits = response.getHits().getHits();
    if (hits.length == 0) {
        break; // 数据获取完毕
    }
    
    // 处理数据
    for (SearchHit hit : hits) {
        // 处理文档
    }
    
    // 获取下一批数据
    SearchScrollRequest scrollRequest = new SearchScrollRequest(scrollId);
    scrollRequest.scroll(TimeValue.timeValueMinutes(1L));
    response = client.scroll(scrollRequest, RequestOptions.DEFAULT);
}

// Step 3: 清理 Scroll 上下文
ClearScrollRequest clearRequest = new ClearScrollRequest();
clearRequest.addScrollId(scrollId);
client.clearScroll(clearRequest, RequestOptions.DEFAULT);
```

#### 4. 优缺点

**优点**：
- 不受 `max_result_window` 限制
- 性能稳定，适合大数据量导出

**缺点**：
- 占用服务器资源（维护快照上下文）
- 不适合实时查询（数据是快照时刻的）
- 不适合跳页查询（只能顺序遍历）

---

### 方案二：Search After（推荐）

#### 1. 适用场景
- **深度分页查询**（类似"加载更多"）
- **实时数据**（反映最新写入）
- **需要排序**

#### 2. 工作原理
- 每次查询返回最后一条数据的排序值（sort values）
- 下次查询以该值为起点，继续获取

#### 3. 使用示例

```java
// Step 1: 第一次查询（无 search_after）
SearchRequest searchRequest = new SearchRequest("products");
SearchSourceBuilder sourceBuilder = new SearchSourceBuilder();
sourceBuilder.query(QueryBuilders.matchAllQuery());
sourceBuilder.size(10);
sourceBuilder.sort("created_at", SortOrder.DESC); // 必须指定排序字段
sourceBuilder.sort("_id", SortOrder.ASC);         // 添加唯一字段，保证排序稳定
searchRequest.source(sourceBuilder);

SearchResponse response = client.search(searchRequest, RequestOptions.DEFAULT);
SearchHit[] hits = response.getHits().getHits();

// 获取最后一条数据的 sort values
Object[] lastSortValues = hits[hits.length - 1].getSortValues();

// Step 2: 第二次查询（使用 search_after）
sourceBuilder.searchAfter(lastSortValues); // 从上次的位置继续
searchRequest.source(sourceBuilder);
response = client.search(searchRequest, RequestOptions.DEFAULT);

// Step 3: 继续翻页...
```

#### 4. REST API 示例
```json
// 第一次查询
POST /products/_search
{
  "size": 10,
  "sort": [
    { "created_at": "desc" },
    { "_id": "asc" }
  ]
}

// 返回结果（最后一条数据的 sort values）
{
  "hits": {
    "hits": [
      {
        "_id": "100",
        "_source": { ... },
        "sort": [1698825600000, "100"]  // 保存这个值
      }
    ]
  }
}

// 第二次查询（使用 search_after）
POST /products/_search
{
  "size": 10,
  "sort": [
    { "created_at": "desc" },
    { "_id": "asc" }
  ],
  "search_after": [1698825600000, "100"]  // 从上次的位置继续
}
```

#### 5. 优缺点

**优点**：
- 性能稳定，不受分页深度影响
- 实时数据，反映最新写入
- 无需维护快照上下文，资源占用少

**缺点**：
- 不支持跳页（只能上一页/下一页）
- 必须指定排序字段

---

### 方案三：调整 max_result_window（不推荐）

```yaml
# 临时调整最大窗口
PUT /products/_settings
{
  "index.max_result_window": 50000
}
```

#### 缺点
- 治标不治本，只是延缓问题
- 内存和性能问题依然存在
- 增加 OOM 风险

---

### 方案四：业务层优化

#### 1. 禁止深度分页
- 限制最大页码（如最多显示前 100 页）
- 类似 Google 搜索（不会显示第 1000 页）

#### 2. 使用"加载更多"替代分页
- 移动端常见方案
- 结合 Search After 实现

#### 3. 引导用户缩小搜索范围
- 通过筛选条件减少结果集
- 提供时间范围、分类等过滤器

## 方案对比

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **Scroll** | 全量导出、离线分析 | 不受限制、性能稳定 | 快照数据、占用资源、不支持跳页 |
| **Search After** | 深度分页、实时查询 | 实时数据、性能好、资源占用少 | 不支持跳页 |
| **调大窗口** | 临时应急 | 简单 | 治标不治本、风险大 |
| **业务优化** | 所有场景 | 根本解决问题 | 需要改变产品逻辑 |

## 最佳实践

### 1. 常规分页（前 100 页）
- 使用 `from + size`

### 2. 深度分页（页码很大）
- 使用 `search_after`
- 前端改为"加载更多"

### 3. 全量导出
- 使用 `Scroll API`
- 或使用 Logstash、Spark 等工具

### 4. 实时数据流
- 使用 `Point In Time (PIT)` + `search_after`（ES 7.10+）

```java
// 创建 PIT
OpenPointInTimeRequest pitRequest = new OpenPointInTimeRequest("products")
    .keepAlive(TimeValue.timeValueMinutes(5));
OpenPointInTimeResponse pitResponse = client.openPointInTime(pitRequest, RequestOptions.DEFAULT);
String pitId = pitResponse.getPointInTimeId();

// 使用 PIT + search_after
SearchRequest searchRequest = new SearchRequest();
searchRequest.source(new SearchSourceBuilder()
    .query(QueryBuilders.matchAllQuery())
    .size(10)
    .sort("_shard_doc", SortOrder.ASC)
    .pointInTimeBuilder(new PointInTimeBuilder(pitId)));

// ... 循环查询
```

## 总结

ElasticSearch 深度分页问题本质是**分布式排序**导致的性能问题。解决方案选择：

- **Scroll API**：适合离线全量导出，不适合实时查询
- **Search After**：推荐方案，适合深度分页和实时查询
- **业务优化**：从产品层面避免深度分页需求

**面试要点**：
- 说明 `from + size` 在深度分页时的性能问题（N 个分片 × (from + size) 条数据）
- 重点介绍 **Search After** 方案（推荐）
- 提及 Scroll API 的应用场景（数据导出）
- 可补充业务层优化思路（限制页码、加载更多）

