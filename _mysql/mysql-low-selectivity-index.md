---
title: "区分度不高的字段建索引一定没用吗？"
date: 2025-11-02
categories: [MySQL, 索引优化]
tags: [MySQL, 索引设计, 选择性, 低区分度, 性能优化]
description: "深入分析区分度不高的字段（如性别、状态）建索引是否有用，包括适用场景、优化策略和实际案例。"
nav_order: 291
parent: 数据库MySQL
---
## 一、答案概要

**不一定没用**。区分度不高的字段建索引是否有效，取决于以下因素：

1. **数据分布**：实际过滤的数据量
2. **查询模式**：是否与其他条件组合
3. **表规模**：表的总行数
4. **业务场景**：查询频率和性能要求

## 二、核心概念

### 1. 什么是区分度（选择性）

```sql
选择性 = COUNT(DISTINCT column) / COUNT(*)
```

**区分度分类**：
- **高区分度**（0.8-1.0）：用户ID、订单号、邮箱
- **中区分度**（0.1-0.8）：城市、年龄、职业
- **低区分度**（0-0.1）：性别、状态、布尔值

### 2. 低区分度字段示例

```sql
-- 表：1000万行数据

-- gender：只有 'M'/'F' 两个值
SELECT COUNT(DISTINCT gender) FROM users;  -- 结果：2
-- 选择性：2 / 10,000,000 = 0.0000002

-- status：有 5 个状态值
SELECT COUNT(DISTINCT status) FROM orders;  -- 结果：5
-- 选择性：5 / 10,000,000 = 0.0000005

-- is_deleted：软删除标记 0/1
SELECT COUNT(DISTINCT is_deleted) FROM posts;  -- 结果：2
-- 选择性：2 / 10,000,000 = 0.0000002
```

## 三、适用场景分析

### 场景1：数据分布极度不均衡

#### 典型案例

```sql
-- 订单表：1000万行
-- 状态分布：
-- cancelled: 9,900,000 行 (99%)
-- active:       100,000 行 (1%)

CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    status VARCHAR(20),
    INDEX idx_status(status)
);

-- 查询：查找活跃订单
SELECT * FROM orders WHERE status='active';
```

#### 分析

```
不建索引：
  - 扫描行数：10,000,000
  - 返回行数：100,000
  - 扫描率：100%

建立索引：
  - 扫描行数：100,000（通过索引直接定位）
  - 返回行数：100,000
  - 扫描率：1%
  - 性能提升：100倍
```

#### 关键点

```
✅ 有效场景：
  - 数据分布严重倾斜
  - 查询条件集中在少数值
  - 过滤效果达到 90%+

❌ 无效场景：
  - 查询条件平均分布
  - 过滤后仍有大量数据（如50%）
```

### 场景2：作为联合索引的一部分

#### 典型案例

```sql
-- 订单表
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    status TINYINT,  -- 只有5个值，区分度低
    create_time DATETIME,
    -- 联合索引
    INDEX idx_user_status_time(user_id, status, create_time)
);

-- 高频查询
SELECT * FROM orders 
WHERE user_id=? AND status=? 
ORDER BY create_time DESC;
```

#### 分析

```
为什么有效？
1. 虽然 status 区分度低，但在联合索引中起到进一步过滤作用
2. user_id 先过滤到用户级别（假设1000行）
3. status 再过滤到特定状态（假设200行）
4. create_time 用于排序

单独 status 索引：无效（区分度太低）
联合索引中的 status：有效（组合后区分度提升）
```

#### 组合后的选择性

```sql
-- 单独字段选择性
SELECT COUNT(DISTINCT status) / COUNT(*) FROM orders;
-- 结果：0.0000005（几乎无用）

-- 组合字段选择性
SELECT COUNT(DISTINCT user_id, status) / COUNT(*) FROM orders;
-- 结果：0.05（明显提升）

-- 三列组合选择性
SELECT COUNT(DISTINCT user_id, status, DATE(create_time)) / COUNT(*) 
FROM orders;
-- 结果：0.8（高区分度）
```

### 场景3：覆盖索引优化

#### 典型案例

```sql
-- 用户表
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    name VARCHAR(50),
    gender ENUM('M', 'F'),
    city VARCHAR(50),
    INDEX idx_city_gender_name(city, gender, name)
);

-- 查询：只需要索引中的列
SELECT name FROM users 
WHERE city='Beijing' AND gender='F';
```

#### 分析

```
为什么包含 gender？
1. 虽然 gender 区分度低，但可以实现覆盖索引
2. 避免回表操作
3. gender 在索引中只占 1 字节，空间开销小

执行计划：
type: ref
key: idx_city_gender_name
Extra: Using where; Using index  ← 覆盖索引
```

### 场景4：小表场景

#### 典型案例

```sql
-- 配置表：只有100行数据
CREATE TABLE config (
    id INT PRIMARY KEY,
    category VARCHAR(20),  -- 只有3个类别
    config_key VARCHAR(50),
    config_value TEXT,
    INDEX idx_category(category)
);
```

#### 分析

```
小表是否需要索引？

数据量 < 1000行：
  - 全表扫描非常快（几毫秒）
  - 索引维护开销 > 查询优化收益
  - 结论：通常不需要索引

数据量 1000-10000行：
  - 看查询频率和并发量
  - 高并发场景建议建索引

数据量 > 10000行：
  - 建议建索引（即使区分度低）
```

### 场景5：与其他高区分度字段组合查询

#### 典型案例

```sql
-- 文章表
CREATE TABLE articles (
    id BIGINT PRIMARY KEY,
    author_id BIGINT,
    is_published TINYINT,  -- 0/1，区分度很低
    publish_time DATETIME,
    INDEX idx_author_pub_time(author_id, is_published, publish_time)
);

-- 查询：查看某作者的已发布文章
SELECT * FROM articles 
WHERE author_id=? AND is_published=1 
ORDER BY publish_time DESC;
```

#### 分析

```
执行过程：
1. author_id 定位到作者的所有文章（假设100篇）
2. is_published 过滤未发布的（假设剩50篇）
3. publish_time 排序

虽然 is_published 区分度低，但：
- 在已过滤的小范围内（100篇）进一步过滤
- 过滤效果显著（从100篇到50篇）
- 有效利用索引排序
```

## 四、优化器的选择逻辑

### 1. 成本估算

```sql
-- MySQL 优化器评估使用索引的成本

全表扫描成本 = 表的数据页数 × IO成本

索引扫描成本 = 
    + 索引扫描页数 × IO成本
    + 回表次数 × IO成本
    + CPU处理成本

-- 当：索引扫描成本 < 全表扫描成本 时，使用索引
```

### 2. 区分度阈值

```
经验值：
- 选择性 > 0.1：通常会使用索引
- 选择性 0.01-0.1：根据数据量和分布决定
- 选择性 < 0.01：通常不使用索引（除非数据分布极度倾斜）

但这不是绝对的，MySQL 会动态评估。
```

### 3. 实际测试

```sql
-- 测试表：1000万行
CREATE TABLE test (
    id INT PRIMARY KEY AUTO_INCREMENT,
    status TINYINT,  -- 1,2,3,4,5 五个值，均匀分布
    data VARCHAR(100),
    INDEX idx_status(status)
);

-- 测试1：查询20%的数据
EXPLAIN SELECT * FROM test WHERE status IN (1, 2);
-- 结果：type: ALL（全表扫描）
-- 原因：过滤后还有400万行，回表成本太高

-- 测试2：查询1%的数据
EXPLAIN SELECT * FROM test WHERE status=1 AND id > 9900000;
-- 结果：type: range
-- 原因：只需查10万行，索引有效

-- 测试3：覆盖索引
EXPLAIN SELECT COUNT(*) FROM test WHERE status=1;
-- 结果：type: index, Extra: Using index
-- 原因：覆盖索引，无需回表，索引有效
```

## 五、具体优化策略

### 策略1：利用数据分布倾斜

```sql
-- 场景：软删除标记
-- 分布：is_deleted=0 (99%), is_deleted=1 (1%)

CREATE TABLE posts (
    id BIGINT,
    content TEXT,
    is_deleted TINYINT DEFAULT 0,
    INDEX idx_not_deleted(is_deleted, publish_time)
);

-- 查询未删除的（主要查询）
SELECT * FROM posts 
WHERE is_deleted=0 AND publish_time >= ?;
-- ✅ 索引有效

-- 查询已删除的（次要查询）
SELECT * FROM posts WHERE is_deleted=1;
-- ✅ 索引仍有效（只有1%的数据）
```

### 策略2：创建联合索引

```sql
-- 不好：单独的低区分度索引
INDEX(status)

-- 好：联合索引
INDEX(status, create_time, user_id)

-- 查询：
WHERE status=? AND create_time >= ?
-- 充分利用联合索引
```

### 策略3：使用部分索引（MySQL 8.0.13+）

```sql
-- 仅为特定值建索引
-- 注意：MySQL暂不直接支持，但可以通过函数索引模拟

-- PostgreSQL 的部分索引示例（参考）
CREATE INDEX idx_active_orders 
ON orders(create_time) 
WHERE status='active';
```

### 策略4：条件下推

```sql
-- 利用索引下推（Index Condition Pushdown）
CREATE INDEX idx_status_time ON orders(status, create_time);

SELECT * FROM orders 
WHERE status='active' 
  AND create_time >= '2025-01-01'
  AND total_amount > 100;  -- 虽然不在索引中，但可以下推

-- Extra: Using index condition
-- total_amount 的过滤在存储引擎层完成，减少回表
```

## 六、性能对比实测

### 测试场景

```sql
-- 表：10,000,000 行
-- status: 'A'/'B'/'C' 三个值，均匀分布（各333万行）

-- 测试1：无索引
SELECT COUNT(*) FROM orders WHERE status='A';
-- 执行时间：2.5秒（全表扫描）

-- 测试2：有索引 + 覆盖查询
CREATE INDEX idx_status ON orders(status);
SELECT COUNT(*) FROM orders WHERE status='A';
-- 执行时间：0.3秒（索引扫描，无回表）

-- 测试3：有索引 + 需要回表
SELECT * FROM orders WHERE status='A';
-- 执行时间：8秒（索引扫描 + 333万次回表）
-- 结论：优化器可能选择全表扫描（2.5秒更快）

-- 测试4：联合索引 + 进一步过滤
CREATE INDEX idx_status_time ON orders(status, create_time);
SELECT * FROM orders 
WHERE status='A' AND create_time >= '2025-11-01';
-- 执行时间：0.05秒（只需回表1000行）
```

## 七、面试陷阱问题

### 陷阱1：绝对化判断

**错误回答**："区分度低的字段建索引没用"

**正确回答**：
- 需要考虑数据分布、查询模式、表规模
- 数据倾斜场景下很有用
- 联合索引中可以发挥作用
- 覆盖索引场景下有效

### 陷阱2：只看选择性数值

**错误回答**："选择性0.0001，所以不建索引"

**正确回答**：
- 数值只是参考，不是绝对标准
- 需要结合实际过滤比例
- 查询 `WHERE status='rare_value'` 可能只返回0.1%的数据
- 此时索引非常有效

### 陷阱3：忽略组合效果

**错误回答**："status区分度低，不用加到联合索引中"

**正确回答**：
- 联合索引中，每增加一列都能提升组合区分度
- status在user_id之后，可以进一步缩小范围
- 空间开销小（status通常1-2字节）

## 八、实战建议

### 1. 评估是否建索引

```
决策流程：
1. 计算选择性
2. 分析数据分布（是否倾斜）
3. 评估查询模式（单独查询 vs 组合查询）
4. 考虑表规模（行数）
5. 实测对比（EXPLAIN + 实际执行时间）
```

### 2. 监控索引使用

```sql
-- 查看索引使用情况
SELECT 
    table_name,
    index_name,
    rows_selected,
    rows_inserted,
    rows_updated,
    rows_deleted
FROM sys.schema_index_statistics
WHERE table_name='orders';

-- 如果 rows_selected=0，考虑删除索引
```

### 3. 定期分析

```sql
-- 更新统计信息
ANALYZE TABLE orders;

-- 检查索引效率
EXPLAIN SELECT * FROM orders WHERE status='xxx';

-- 对比不同索引方案
EXPLAIN FORMAT=JSON SELECT ...;
```

## 九、面试总结

**区分度不高的字段建索引不一定没用**，关键看场景：

**有效场景**：
1. **数据分布倾斜**：查询集中在少数值（如查询1%的活跃订单）
2. **联合索引一部分**：与高区分度字段组合，提升整体效果
3. **覆盖索引**：无需回表，索引扫描成本低
4. **大表 + 高频查询**：即使区分度低，也比全表扫描快

**无效场景**：
1. 数据均匀分布且需要大量回表
2. 小表（<1000行）
3. 查询过滤后仍有大量数据（>30%）

**优化建议**：
- 利用数据倾斜特性
- 创建联合索引而非单列索引
- 尽量实现覆盖索引
- 使用EXPLAIN验证实际效果
- 监控索引使用情况

**关键原则**：不要教条化，要根据实际数据和查询模式灵活决策。

能从多个角度分析这个问题，体现了对MySQL索引机制的深刻理解和实战经验。

