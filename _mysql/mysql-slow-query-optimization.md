---
title: "MySQL慢查询优化"
date: 2025-11-02
categories: [MySQL, 性能优化]
tags: [MySQL, 慢查询, 性能优化, 实战案例, 优化方案]
description: "从实战角度详解MySQL慢查询优化的完整流程、常见场景及解决方案，包含多个真实案例分析"
nav_order: 354
parent: 数据库MySQL
---
# MySQL慢查询优化

## 核心概念

慢查询优化是通过**定位慢SQL → 分析执行计划 → 制定优化方案 → 验证效果**的闭环流程，系统性提升数据库查询性能。优化核心是**索引优化、SQL改写、表设计调整**三大手段。

---

## 一、慢查询优化流程

### 完整优化流程图

```
┌──────────────┐
│ 1. 开启慢查询 │
│    日志监控   │
└───────┬──────┘
        │
┌───────▼──────┐
│ 2. 分析慢SQL  │
│   - 日志分析  │
│   - EXPLAIN   │
└───────┬──────┘
        │
┌───────▼──────┐
│ 3. 制定方案  │
│   - 加索引    │
│   - 改SQL     │
│   - 调表结构  │
└───────┬──────┘
        │
┌───────▼──────┐
│ 4. 测试验证  │
│   - 开发环境  │
│   - 压力测试  │
└───────┬──────┘
        │
┌───────▼──────┐
│ 5. 上线观察  │
│   - 灰度发布  │
│   - 监控指标  │
└───────┬──────┘
        │
┌───────▼──────┐
│ 6. 持续监控  │
└──────────────┘
```

---

## 二、常见慢查询场景及优化

### 场景1：未建索引导致全表扫描

#### 问题SQL
```sql
SELECT * FROM orders 
WHERE user_id = 1001 
ORDER BY create_time DESC 
LIMIT 10;
```

#### EXPLAIN分析
```
type: ALL
key: NULL
rows: 5000000
Extra: Using where; Using filesort
执行时间：8.5秒
```

**问题诊断**：
- ❌ 全表扫描500万行
- ❌ 未使用索引
- ❌ 需要额外排序

---

#### 优化方案
```sql
-- 创建联合索引
CREATE INDEX idx_user_time ON orders(user_id, create_time);

-- 优化后EXPLAIN
type: ref
key: idx_user_time
rows: 120
Extra: Using index condition
执行时间：0.02秒
```

**优化效果**：425倍提升！

---

### 场景2：索引失效（函数操作）

#### 问题SQL
```sql
SELECT * FROM orders 
WHERE DATE(create_time) = '2025-11-02';
```

#### EXPLAIN分析
```
type: ALL
key: NULL
rows: 5000000
Extra: Using where
执行时间：6.8秒
```

**问题诊断**：
- ❌ `DATE()`函数导致索引失效
- ❌ 即使create_time有索引也无法使用

---

#### 优化方案
```sql
-- ✅ 改写为范围查询
SELECT * FROM orders 
WHERE create_time >= '2025-11-02 00:00:00' 
  AND create_time < '2025-11-03 00:00:00';

-- 优化后EXPLAIN
type: range
key: idx_create_time
rows: 15000
Extra: Using index condition
执行时间：0.08秒
```

**优化效果**：85倍提升！

---

### 场景3：深度分页

#### 问题SQL
```sql
SELECT * FROM orders 
ORDER BY id 
LIMIT 1000000, 20;
```

#### EXPLAIN分析
```
type: index
key: PRIMARY
rows: 1000020
Extra: Using index
执行时间：12秒
```

**问题诊断**：
- ❌ 需要扫描100万行
- ❌ 每行都要回表
- ❌ 前100万行全部丢弃

---

#### 优化方案1：主键定位（推荐）
```sql
-- 记录上一页最大ID
SELECT * FROM orders 
WHERE id > 1000000 
ORDER BY id 
LIMIT 20;

-- 优化后EXPLAIN
type: range
key: PRIMARY
rows: 20
执行时间：0.001秒
```

**优化效果**：12000倍提升！

---

#### 优化方案2：延迟关联
```sql
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders ORDER BY id LIMIT 1000000, 20
) t ON o.id = t.id;

-- 执行时间：2.5秒
```

**优化效果**：4.8倍提升

---

### 场景4：JOIN未使用索引

#### 问题SQL
```sql
SELECT o.*, u.name FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE o.status = 1;
```

#### EXPLAIN分析
```
-- orders表
type: ALL
key: NULL
rows: 5000000

-- users表
type: eq_ref
key: PRIMARY
rows: 1

执行时间：15秒
```

**问题诊断**：
- ❌ orders表全表扫描
- ❌ status字段未建索引

---

#### 优化方案
```sql
-- 1. 为status字段建索引
CREATE INDEX idx_status ON orders(status);

-- 2. 确保关联字段有索引（user_id和id）
CREATE INDEX idx_user_id ON orders(user_id);  -- 如果没有的话

-- 优化后EXPLAIN
-- orders表
type: ref
key: idx_status
rows: 80000

-- users表
type: eq_ref
key: PRIMARY
rows: 1

执行时间：0.5秒
```

**优化效果**：30倍提升！

---

### 场景5：回表开销大

#### 问题SQL
```sql
SELECT * FROM orders 
WHERE user_id = 1001;
```

#### EXPLAIN分析
```
type: ref
key: idx_user_id
rows: 50000
Extra: Using where
执行时间：2.8秒
```

**问题诊断**：
- ✅ 使用了索引
- ❌ 需要回表5万次
- ❌ 随机IO开销大

---

#### 优化方案1：覆盖索引
```sql
-- 只查询必要字段
SELECT id, user_id, amount, create_time FROM orders 
WHERE user_id = 1001;

-- 创建覆盖索引
CREATE INDEX idx_user_cover ON orders(user_id, amount, create_time, id);

-- 优化后EXPLAIN
type: ref
key: idx_user_cover
rows: 50000
Extra: Using index  ← 无需回表
执行时间：0.3秒
```

**优化效果**：9倍提升！

---

#### 优化方案2：延迟关联
```sql
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders WHERE user_id = 1001 LIMIT 20
) t ON o.id = t.id;

-- 只回表20次
执行时间：0.05秒
```

**优化效果**：56倍提升！

---

### 场景6：LIKE模糊查询

#### 问题SQL
```sql
SELECT * FROM products 
WHERE name LIKE '%iPhone%';
```

#### EXPLAIN分析
```
type: ALL
key: NULL
rows: 1000000
Extra: Using where
执行时间：8.2秒
```

**问题诊断**：
- ❌ 前缀通配符导致索引失效
- ❌ 全表扫描

---

#### 优化方案1：全文索引
```sql
-- 创建全文索引
CREATE FULLTEXT INDEX ft_name ON products(name) WITH PARSER ngram;

-- 使用全文搜索
SELECT * FROM products 
WHERE MATCH(name) AGAINST('iPhone' IN NATURAL LANGUAGE MODE);

-- 执行时间：0.15秒
```

**优化效果**：55倍提升！

---

#### 优化方案2：Elasticsearch
```java
// 引入Elasticsearch
@Service
public class ProductSearchService {
    
    @Autowired
    private ElasticsearchClient esClient;
    
    public List<Product> search(String keyword) {
        SearchRequest request = SearchRequest.of(s -> s
            .index("products")
            .query(q -> q.match(m -> m
                .field("name")
                .query(keyword)
            ))
        );
        
        return esClient.search(request, Product.class)
            .hits().hits().stream()
            .map(Hit::source)
            .collect(Collectors.toList());
    }
}

// 执行时间：0.01秒
```

**优化效果**：820倍提升！

---

### 场景7：ORDER BY未用索引

#### 问题SQL
```sql
SELECT * FROM orders 
WHERE user_id = 1001 
ORDER BY amount DESC 
LIMIT 10;
```

#### EXPLAIN分析
```
type: ref
key: idx_user_id
rows: 50000
Extra: Using where; Using filesort
执行时间：1.5秒
```

**问题诊断**：
- ✅ WHERE使用了索引
- ❌ ORDER BY未使用索引
- ❌ 需要额外排序5万行

---

#### 优化方案
```sql
-- 创建联合索引（WHERE + ORDER BY）
CREATE INDEX idx_user_amount ON orders(user_id, amount);

-- 优化后EXPLAIN
type: ref
key: idx_user_amount
rows: 50000
Extra: Using index condition
执行时间：0.05秒
```

**优化效果**：30倍提升！

---

### 场景8：GROUP BY产生临时表

#### 问题SQL
```sql
SELECT user_id, COUNT(*) as cnt 
FROM orders 
GROUP BY user_id 
ORDER BY cnt DESC 
LIMIT 10;
```

#### EXPLAIN分析
```
type: ALL
key: NULL
rows: 5000000
Extra: Using temporary; Using filesort
执行时间：25秒
```

**问题诊断**：
- ❌ 全表扫描
- ❌ 使用临时表
- ❌ 需要排序

---

#### 优化方案
```sql
-- 1. 为GROUP BY字段建索引
CREATE INDEX idx_user_id ON orders(user_id);

-- 2. 如果可能，业务层缓存热门用户
-- 或定期统计，存入汇总表

-- 优化后EXPLAIN
type: index
key: idx_user_id
rows: 5000000
Extra: Using index; Using temporary; Using filesort
执行时间：8秒
```

**优化效果**：3倍提升

---

#### 更优方案：汇总表
```sql
-- 创建汇总表
CREATE TABLE user_order_summary (
    user_id INT PRIMARY KEY,
    order_count INT,
    update_time DATETIME,
    INDEX idx_count(order_count)
);

-- 定期更新（每小时）
INSERT INTO user_order_summary (user_id, order_count, update_time)
SELECT user_id, COUNT(*), NOW() FROM orders 
GROUP BY user_id
ON DUPLICATE KEY UPDATE 
    order_count = VALUES(order_count),
    update_time = VALUES(update_time);

-- 查询汇总表
SELECT user_id, order_count FROM user_order_summary 
ORDER BY order_count DESC 
LIMIT 10;

-- 执行时间：0.001秒
```

**优化效果**：25000倍提升！

---

## 三、优化工具

### 1. 慢查询日志分析

```bash
# mysqldumpslow（系统自带）
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log
# -s t：按查询时间排序
# -t 10：显示前10条

# pt-query-digest（Percona工具）
pt-query-digest /var/log/mysql/slow.log > report.txt
```

---

### 2. EXPLAIN分析

```sql
-- 基础EXPLAIN
EXPLAIN SELECT * FROM orders WHERE user_id = 1001;

-- 详细分析（MySQL 8.0+）
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 1001;

-- 查看优化器选择过程
SET optimizer_trace="enabled=on";
SELECT * FROM orders WHERE user_id = 1001;
SELECT * FROM information_schema.OPTIMIZER_TRACE\G
SET optimizer_trace="enabled=off";
```

---

### 3. 性能剖析

```sql
-- 开启性能剖析
SET profiling = 1;

-- 执行查询
SELECT * FROM orders WHERE user_id = 1001;

-- 查看性能分析
SHOW PROFILES;
SHOW PROFILE FOR QUERY 1;

-- 关闭
SET profiling = 0;
```

---

## 四、优化最佳实践

### 1. 索引设计原则

```sql
-- ✅ 好的索引设计
CREATE INDEX idx_combined ON orders(
    user_id,      -- 等值查询（选择性高）
    status,       -- 等值查询
    create_time   -- 排序/范围查询
);

-- ❌ 差的索引设计
CREATE INDEX idx_time ON orders(create_time);  -- 只能用于排序
CREATE INDEX idx_status ON orders(status);      -- 区分度太低
```

---

### 2. SQL编写规范

```sql
-- ✅ 好的SQL
SELECT id, user_id, amount FROM orders 
WHERE user_id = 1001 AND status = 1 
ORDER BY create_time DESC 
LIMIT 20;

-- ❌ 差的SQL
SELECT * FROM orders 
WHERE YEAR(create_time) = 2025 
ORDER BY amount 
LIMIT 10000, 20;
```

---

### 3. 监控告警

```yaml
# Prometheus告警规则
groups:
  - name: mysql_alerts
    rules:
      # 慢查询数量告警
      - alert: HighSlowQueries
        expr: rate(mysql_global_status_slow_queries[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "慢查询过多"
          
      # 连接数告警
      - alert: HighConnections
        expr: mysql_global_status_threads_connected / mysql_global_variables_max_connections > 0.8
        for: 5m
        labels:
          severity: critical
```

---

## 五、优化效果对比

| 优化手段 | 适用场景 | 难度 | 效果 | 成本 |
|---------|---------|------|------|------|
| **加索引** | 未建索引 | ⭐ | ⭐⭐⭐⭐⭐ | 低 |
| **SQL改写** | 索引失效 | ⭐⭐ | ⭐⭐⭐⭐ | 低 |
| **覆盖索引** | 回表多 | ⭐⭐ | ⭐⭐⭐ | 低 |
| **分页优化** | 深度分页 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 低 |
| **读写分离** | 读多写少 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 中 |
| **分库分表** | 海量数据 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 高 |

---

## 六、面试答题模板

### 回答结构
```
1. 问题定位（如何发现慢查询）
   - 慢查询日志
   - 监控告警
   
2. 分析诊断（为什么慢）
   - EXPLAIN分析
   - 索引情况
   
3. 优化方案（怎么解决）
   - 加索引
   - 改SQL
   - 架构优化
   
4. 效果验证（优化效果）
   - 性能对比
   - 监控数据
   
5. 经验总结（举一反三）
   - 预防措施
   - 最佳实践
```

---

### 示例回答

**问：如何优化慢查询？**

**答**：
我会按照以下流程优化慢查询：

**1. 定位慢SQL**：通过慢查询日志或监控系统发现问题SQL。

**2. 分析根因**：用EXPLAIN分析执行计划，重点看type、key、rows、Extra。常见问题是：
- type=ALL（全表扫描）
- key=NULL（未使用索引）
- rows过大（扫描行数多）
- Extra=Using filesort（需要排序）

**3. 优化方案**：
- **80%的慢查询**是索引问题，优先创建合适的索引
- **SQL改写**：避免函数操作、隐式转换、前缀通配符
- **深度分页**：用主键定位或延迟关联
- **架构优化**：读写分离、分库分表

**4. 实战案例**：
曾优化过电商订单查询，原SQL执行8秒，通过创建联合索引`idx_user_time(user_id, create_time)`，优化后0.02秒，提升400倍。

**5. 预防措施**：
- 定期Review慢查询日志
- 上线前SQL审核
- 监控告警及时响应

---

## 总结

慢查询优化遵循**"定位→分析→优化→验证"**的闭环流程。80%的慢查询是索引问题，通过EXPLAIN分析执行计划，针对性创建索引或改写SQL，通常能获得数十倍甚至数百倍的性能提升。单机优化到瓶颈后，考虑读写分离、分库分表等架构方案。面试中能系统讲解优化流程，并结合实际案例说明优化效果，体现数据库优化的实战能力。

