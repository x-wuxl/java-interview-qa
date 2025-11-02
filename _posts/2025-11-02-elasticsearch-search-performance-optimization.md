---
layout: post
title: "如何优化 ElasticSearch 搜索性能？"
date: 2025-11-02
categories: [中间件, ElasticSearch]
tags: [ElasticSearch, 性能优化, 索引优化, 面试]
description: "全面解析 ElasticSearch 搜索性能优化的最佳实践和调优技巧"
---

## 核心概念

ElasticSearch 的性能优化需要从**索引设计**、**查询优化**、**硬件配置**、**集群架构**四个维度综合考虑，针对不同的业务场景采用不同的优化策略。

## 一、索引设计优化

### 1. 合理规划分片数量

#### **分片过多的问题**
- 每个分片都是一个 Lucene 索引，消耗资源
- 查询需要在所有分片上执行，分片过多影响性能

#### **分片过少的问题**
- 无法充分利用集群并行能力
- 单个分片过大，查询和恢复速度慢

#### **最佳实践**
```json
{
  "settings": {
    "number_of_shards": 3,        // 根据数据量和节点数计算
    "number_of_replicas": 1
  }
}
```

**分片数量计算公式**：
- 单个分片建议大小：**20GB - 50GB**
- 分片数 = 总数据量 / 单分片大小
- 分片数 ≤ 数据节点数 × 3

```
例如：
数据量：300GB
节点数：5 个
单分片大小：30GB
分片数 = 300GB / 30GB = 10（推荐）
```

### 2. 字段类型优化

#### **使用正确的字段类型**
```json
{
  "mappings": {
    "properties": {
      "id": {
        "type": "keyword"           // 精确匹配，不分词
      },
      "title": {
        "type": "text",              // 全文检索，分词
        "analyzer": "ik_max_word",
        "fields": {
          "keyword": {               // 支持聚合和排序
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "price": {
        "type": "double"             // 数值类型
      },
      "created_at": {
        "type": "date",              // 日期类型
        "format": "yyyy-MM-dd HH:mm:ss"
      },
      "status": {
        "type": "keyword",           // 枚举值，使用 keyword
        "doc_values": true           // 支持聚合和排序
      },
      "description": {
        "type": "text",
        "index": false               // 不需要搜索的字段，禁用索引
      }
    }
  }
}
```

#### **禁用不需要的功能**
```json
{
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "norms": false,              // 不需要评分，禁用 norms（节省存储）
        "index_options": "freqs"     // 只存储词频，不存储位置（节省存储）
      },
      "internal_id": {
        "type": "keyword",
        "index": false,              // 不搜索，只存储
        "doc_values": false          // 不聚合、不排序
      }
    }
  }
}
```

### 3. 合理使用 doc_values

- **doc_values**：列式存储，用于排序、聚合、脚本访问
- **默认开启**，keyword、numeric、date 类型自动启用
- **不需要聚合/排序的字段**，可以禁用节省磁盘

```json
{
  "mappings": {
    "properties": {
      "user_id": {
        "type": "keyword",
        "doc_values": false      // 只用于搜索，不用于聚合
      }
    }
  }
}
```

### 4. 使用索引模板

```json
PUT _index_template/logs_template
{
  "index_patterns": ["logs-*"],
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "refresh_interval": "30s",    // 降低刷新频率
      "translog.durability": "async"
    },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "message": { "type": "text" }
      }
    }
  }
}
```

---

## 二、查询优化

### 1. 使用 Filter Context 替代 Query Context

#### **区别**
- **Query Context**：计算相关性评分，不缓存
- **Filter Context**：不计算评分，结果可缓存

#### **优化示例**
```java
// 低效查询（全部使用 Query Context）
BoolQueryBuilder query = QueryBuilders.boolQuery()
    .must(QueryBuilders.matchQuery("title", "ElasticSearch"))
    .must(QueryBuilders.termQuery("status", "published"))
    .must(QueryBuilders.rangeQuery("price").gte(100).lte(500));

// 高效查询（精确匹配使用 Filter Context）
BoolQueryBuilder query = QueryBuilders.boolQuery()
    .must(QueryBuilders.matchQuery("title", "ElasticSearch"))  // 需要评分
    .filter(QueryBuilders.termQuery("status", "published"))    // 不评分，可缓存
    .filter(QueryBuilders.rangeQuery("price").gte(100).lte(500)); // 不评分，可缓存
```

### 2. 避免深度分页

使用 **Search After** 替代 `from + size`：

```java
// 低效（深度分页）
SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
    .from(10000)
    .size(10);

// 高效（Search After）
SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
    .size(10)
    .sort("_id", SortOrder.ASC)
    .searchAfter(new Object[]{lastId});  // 从上次位置继续
```

### 3. 合理使用分词器

#### **减少分词粒度**
```json
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "ik_smart"       // 粗粒度分词（性能好）
        // "analyzer": "ik_max_word"  // 细粒度分词（准确度高，性能差）
      }
    }
  }
}
```

### 4. 使用 _source 过滤

#### **只返回需要的字段**
```java
// 返回所有字段（低效）
SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
    .query(QueryBuilders.matchAllQuery());

// 只返回指定字段（高效）
SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
    .query(QueryBuilders.matchAllQuery())
    .fetchSource(new String[]{"id", "title", "price"}, null);
```

### 5. 使用 prefix、wildcard 查询时加限制

```java
// 低效（前缀匹配，扫描大量数据）
QueryBuilders.wildcardQuery("name", "*手机*");

// 优化：限制搜索范围 + 使用 ngram 分词
// 1. 建索引时使用 ngram
{
  "settings": {
    "analysis": {
      "analyzer": {
        "ngram_analyzer": {
          "tokenizer": "ngram_tokenizer"
        }
      },
      "tokenizer": {
        "ngram_tokenizer": {
          "type": "ngram",
          "min_gram": 2,
          "max_gram": 3
        }
      }
    }
  }
}

// 2. 查询时使用 match
QueryBuilders.matchQuery("name", "手机");  // 比 wildcard 快
```

### 6. 合理使用聚合

#### **聚合优化**
```java
// 聚合 + 分页（使用 Composite Aggregation）
CompositeAggregationBuilder aggregation = AggregationBuilders
    .composite("agg", Arrays.asList(
        new TermsValuesSourceBuilder("brand").field("brand.keyword")
    ))
    .size(100);

// 避免全局聚合（使用 Filter Aggregation）
AggregationBuilders.filter("filtered_agg", 
    QueryBuilders.termQuery("status", "published"))
    .subAggregation(AggregationBuilders.terms("brands").field("brand.keyword"));
```

---

## 三、写入性能优化

### 1. 调整 refresh_interval

```json
{
  "settings": {
    "refresh_interval": "30s"    // 默认 1s，降低刷新频率提升写入性能
    // "refresh_interval": "-1"  // 批量导入时禁用，完成后手动刷新
  }
}
```

### 2. 批量写入（Bulk API）

```java
BulkRequest bulkRequest = new BulkRequest();
for (Product product : products) {
    bulkRequest.add(new IndexRequest("products")
        .id(product.getId().toString())
        .source(convertToJson(product), XContentType.JSON));
    
    // 每 1000 条提交一次
    if (bulkRequest.numberOfActions() >= 1000) {
        client.bulk(bulkRequest, RequestOptions.DEFAULT);
        bulkRequest = new BulkRequest();
    }
}
// 提交剩余数据
if (bulkRequest.numberOfActions() > 0) {
    client.bulk(bulkRequest, RequestOptions.DEFAULT);
}
```

### 3. 调整 translog 持久化策略

```json
{
  "settings": {
    "translog.durability": "async",         // 异步刷盘（提升性能，但可能丢失数据）
    "translog.sync_interval": "5s",         // 每 5 秒刷盘一次
    "translog.flush_threshold_size": "1gb"  // Translog 达到 1GB 时触发 flush
  }
}
```

### 4. 增加副本前批量导入

```bash
# 1. 导入前禁用副本
PUT /products/_settings
{
  "number_of_replicas": 0
}

# 2. 批量导入数据
# ...

# 3. 导入完成后恢复副本
PUT /products/_settings
{
  "number_of_replicas": 1
}
```

---

## 四、硬件与集群优化

### 1. 内存配置

```yaml
# JVM Heap 配置
-Xms16g
-Xmx16g  # 不超过 32GB（指针压缩阈值）

# 内存分配建议
总内存：64GB
- JVM Heap：16GB（25%）
- OS Cache：48GB（75%，用于文件缓存）
```

### 2. 使用 SSD 磁盘
- 随机读写性能远超 HDD
- 适合 ES 的 Segment 读取场景

### 3. 节点分离

```
Master Node：负责集群管理（轻量级）
Data Node：负责数据存储和查询（高配置）
Coordinating Node：负责请求分发和结果聚合（中等配置）
Ingest Node：负责数据预处理（可选）
```

### 4. 冷热架构

```json
// 热节点（高性能 SSD）
PUT /logs-hot
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.routing.allocation.require.box_type": "hot"
  }
}

// 冷节点（大容量 HDD）
PUT /logs-cold
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.routing.allocation.require.box_type": "cold"
  }
}
```

---

## 五、监控与调优

### 1. 慢查询日志

```yaml
# elasticsearch.yml
index.search.slowlog.threshold.query.warn: 10s
index.search.slowlog.threshold.query.info: 5s
index.search.slowlog.threshold.fetch.warn: 1s
```

### 2. 使用 Profile API 分析查询

```json
GET /products/_search
{
  "profile": true,
  "query": {
    "match": { "title": "ElasticSearch" }
  }
}
```

返回结果包含每个阶段的耗时，帮助定位性能瓶颈。

### 3. 监控关键指标

```bash
# 集群健康
GET /_cluster/health

# 节点统计
GET /_nodes/stats

# 索引统计
GET /products/_stats

# 关键指标
- JVM Heap 使用率：< 75%
- CPU 使用率：< 70%
- 磁盘使用率：< 85%
- 查询延迟：P99 < 100ms
```

---

## 六、实战优化案例

### 案例 1：电商商品搜索优化

#### **优化前**
```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "手机" } },
        { "term": { "status": "on_sale" } },
        { "range": { "price": { "gte": 1000, "lte": 5000 } } }
      ]
    }
  },
  "from": 0,
  "size": 20
}
```

#### **优化后**
```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "手机" } }  // 只有需要评分的放 must
      ],
      "filter": [  // 精确匹配放 filter
        { "term": { "status": "on_sale" } },
        { "range": { "price": { "gte": 1000, "lte": 5000 } } }
      ]
    }
  },
  "_source": ["id", "name", "price", "thumbnail"],  // 只返回需要的字段
  "from": 0,
  "size": 20
}
```

### 案例 2：日志分析优化

```json
// 优化前：按时间范围查询 + 聚合
GET /logs/_search
{
  "query": {
    "range": {
      "@timestamp": {
        "gte": "2025-11-01",
        "lte": "2025-11-02"
      }
    }
  },
  "aggs": {
    "error_count": {
      "terms": { "field": "level" }
    }
  }
}

// 优化后：使用时间索引 + Filter Context
GET /logs-2025-11-01,logs-2025-11-02/_search
{
  "query": {
    "bool": {
      "filter": [
        { "range": { "@timestamp": { "gte": "2025-11-01", "lte": "2025-11-02" } } }
      ]
    }
  },
  "aggs": {
    "error_count": {
      "terms": { 
        "field": "level",
        "size": 10
      }
    }
  },
  "size": 0  // 只要聚合结果，不要文档
}
```

---

## 优化清单总结

### 索引设计
- ✅ 合理规划分片数量（单分片 20-50GB）
- ✅ 使用正确的字段类型（keyword、text、numeric）
- ✅ 禁用不需要的功能（norms、index、doc_values）
- ✅ 使用索引模板统一配置

### 查询优化
- ✅ 使用 Filter Context（精确匹配、不需要评分）
- ✅ 避免深度分页（使用 Search After）
- ✅ 使用 _source 过滤（只返回需要的字段）
- ✅ 避免 wildcard、prefix 查询（使用 ngram）

### 写入优化
- ✅ 降低 refresh_interval（30s 或更高）
- ✅ 使用 Bulk API 批量写入
- ✅ 调整 translog 持久化策略（async）
- ✅ 批量导入时禁用副本

### 硬件配置
- ✅ JVM Heap 不超过 32GB
- ✅ 使用 SSD 磁盘
- ✅ 节点分离（Master、Data、Coordinating）
- ✅ 冷热架构（热数据 SSD，冷数据 HDD）

### 监控调优
- ✅ 开启慢查询日志
- ✅ 使用 Profile API 分析
- ✅ 监控 JVM、CPU、磁盘指标

---

## 总结

ElasticSearch 性能优化是一个系统工程，需要从索引设计、查询优化、硬件配置、监控调优多个维度综合考虑。关键原则：

1. **合理的索引设计**：字段类型、分片数量、禁用不必要功能
2. **高效的查询方式**：Filter Context、避免深度分页、字段过滤
3. **充分利用缓存**：Filter 缓存、OS Page Cache
4. **硬件资源优化**：SSD、内存分配、节点分离

**面试要点**：
- 说明索引设计的重要性（字段类型、分片数量）
- 重点介绍 **Filter Context** 的性能优势
- 提及硬件优化（SSD、内存分配 50/50）
- 可结合实际项目说明优化效果（如查询耗时从 5s 降到 500ms）

