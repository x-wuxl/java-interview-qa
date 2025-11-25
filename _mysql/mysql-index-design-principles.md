---
title: "设计索引的时候有哪些原则？"
date: 2025-11-02
categories: [MySQL, 索引优化]
tags: [MySQL, 索引设计, 最佳实践, 性能优化, 数据库设计]
description: "全面总结MySQL索引设计的核心原则和最佳实践，包括字段选择、索引顺序、覆盖索引、冗余索引避免等关键要点。"
nav_order: 290
parent: 数据库MySQL
---
## 一、核心原则概览

MySQL索引设计遵循以下核心原则：

1. **选择性原则**：优先索引高区分度字段
2. **最左前缀原则**：合理设计联合索引顺序
3. **覆盖索引原则**：减少回表操作
4. **适度原则**：避免过度索引
5. **业务优先原则**：根据实际查询模式设计

## 二、详细原则解析

### 原则1：为高频查询条件建索引

#### 核心要点
```
✅ 应该建索引：
  - WHERE 子句中的过滤字段
  - JOIN ON 的关联字段
  - ORDER BY / GROUP BY 的排序字段
  - SELECT DISTINCT 的字段

❌ 不需要建索引：
  - 很少在查询中使用的字段
  - 总是 SELECT * 但从不过滤的字段
```

#### 实战示例

```sql
-- 分析业务查询模式
-- 高频查询1（80%）：按用户ID查订单
SELECT * FROM orders WHERE user_id=? ORDER BY create_time DESC;

-- 高频查询2（15%）：按状态和时间查订单
SELECT * FROM orders WHERE status=? AND create_time >= ?;

-- 低频查询（5%）：按商品名称查
SELECT * FROM orders WHERE product_name LIKE ?;

-- 索引设计：
INDEX(user_id, create_time)  -- 覆盖查询1
INDEX(status, create_time)   -- 覆盖查询2
-- 不为 product_name 建索引（频率低，LIKE查询效果差）
```

### 原则2：选择高区分度（选择性）字段

#### 区分度计算

```sql
-- 计算字段选择性
SELECT 
    COUNT(DISTINCT column) / COUNT(*) AS selectivity
FROM table_name;

-- 选择性范围：0-1
-- 接近1：区分度高（如：用户ID、订单号）
-- 接近0：区分度低（如：性别、状态）
```

#### 实战判断

```sql
-- 表有100万行数据

-- 字段1：user_id
SELECT COUNT(DISTINCT user_id) FROM orders;  -- 结果：500,000
-- 选择性：500,000 / 1,000,000 = 0.5 ✅ 适合建索引

-- 字段2：gender
SELECT COUNT(DISTINCT gender) FROM users;  -- 结果：2
-- 选择性：2 / 1,000,000 = 0.000002 ❌ 不适合单独建索引

-- 字段3：status
SELECT COUNT(DISTINCT status) FROM orders;  -- 结果：5
-- 选择性：5 / 1,000,000 = 0.000005 ⚠️ 看查询条件决定
```

#### 低区分度字段的处理

```sql
-- 策略1：作为联合索引的后续列
INDEX(user_id, status)  -- status区分度低，但组合后有用

-- 策略2：利用索引跳跃扫描（MySQL 8.0+）
INDEX(status, create_time)  -- status值少，可跳跃扫描

-- 策略3：使用复合条件
WHERE status='active' AND create_time >= '2025-01-01'
-- status快速定位少量数据，再用时间精确过滤
```

### 原则3：合理设计联合索引顺序

#### 排序规则

**规则1：高频等值查询列优先**
```sql
-- 查询：WHERE a=? AND b=? AND c>?
-- a、b是等值，c是范围
-- 索引：INDEX(a, b, c) 或 INDEX(b, a, c)
```

**规则2：区分度高的列优先**
```sql
-- a区分度：0.8（高）
-- b区分度：0.1（低）
-- 索引：INDEX(a, b) ✅ 优于 INDEX(b, a)
```

**规则3：范围查询列放后面**
```sql
-- 查询：WHERE a=? AND b>? AND c=?
-- 索引：INDEX(a, b, c)
-- 注意：b是范围查询，c无法使用索引
-- 优化：如果c过滤效果好，考虑 INDEX(a, c, b)
```

#### 典型场景

```sql
-- 场景：电商订单查询
-- 字段：user_id（区分度0.5）、status（区分度0.00001）、create_time

-- 查询模式1（70%）：用户查自己的订单
WHERE user_id=? ORDER BY create_time DESC
→ INDEX(user_id, create_time)

-- 查询模式2（20%）：管理员按状态查订单
WHERE status=? AND create_time >= ?
→ INDEX(status, create_time)

-- 查询模式3（10%）：用户查特定状态订单
WHERE user_id=? AND status=? ORDER BY create_time DESC
→ INDEX(user_id, status, create_time)  -- 或复用索引1
```

### 原则4：充分利用最左前缀原则

#### 减少冗余索引

```sql
-- ❌ 冗余设计
INDEX(a)
INDEX(a, b)
INDEX(a, b, c)

-- ✅ 优化设计
INDEX(a, b, c)  -- 一个索引覆盖 (a), (a,b), (a,b,c) 三种查询
-- 必要时再加 INDEX(b) 或 INDEX(c)（看查询频率）
```

#### 合理补充索引

```sql
-- 已有：INDEX(a, b, c)

-- 如果有高频查询：WHERE b=? AND c=?
-- 需要补充：INDEX(b, c)

-- 如果有高频查询：WHERE c=?
-- 需要补充：INDEX(c)
```

### 原则5：利用覆盖索引

#### 什么是覆盖索引

```sql
-- 索引：INDEX(user_id, status, create_time)

-- 覆盖索引查询（无需回表）
SELECT user_id, status, create_time 
FROM orders 
WHERE user_id=?;
-- Extra: Using index

-- 非覆盖查询（需要回表）
SELECT user_id, status, create_time, total_amount
FROM orders 
WHERE user_id=?;
-- Extra: Using index condition
```

#### 设计技巧

```sql
-- 技巧1：把SELECT常用列包含在索引中
-- 高频查询：SELECT id, name, age FROM users WHERE city=?
INDEX(city, name, age)  -- 覆盖索引

-- 技巧2：延迟关联（大表分页）
-- 不好：
SELECT * FROM large_table 
WHERE condition 
ORDER BY create_time 
LIMIT 10000, 10;  -- 需要扫描10010行并回表

-- 好：使用覆盖索引 + 延迟关联
SELECT t.* FROM large_table t
INNER JOIN (
    SELECT id FROM large_table
    WHERE condition
    ORDER BY create_time
    LIMIT 10000, 10
) tmp ON t.id = tmp.id;  -- 子查询走覆盖索引
```

### 原则6：避免过度索引

#### 索引的代价

```
写入成本：
  - 每个索引在INSERT/UPDATE/DELETE时都需要维护
  - N个索引 → 写入放大N倍

存储成本：
  - 每个索引占用磁盘空间
  - 索引越多，空间越大

内存成本：
  - 索引需要缓存在Buffer Pool中
  - 过多索引导致缓存命中率下降
```

#### 合理数量

```
经验值：
  - 单表索引数量：5-8个为宜
  - 最多不超过15个
  - 联合索引列数：2-4列为宜
  - 最多不超过5列
```

#### 识别冗余索引

```sql
-- 冗余场景1：完全包含
INDEX(a, b, c)
INDEX(a, b)      -- ❌ 冗余，删除

-- 冗余场景2：索引前缀相同
INDEX(a, b, c)
INDEX(a, b, d)   -- ⚠️ 可能冗余，看查询模式

-- 冗余场景3：主键包含
PRIMARY KEY(id)
INDEX(id)        -- ❌ 冗余，删除

-- 查询冗余索引（MySQL 8.0+）
SELECT * FROM sys.schema_redundant_indexes;
```

### 原则7：字符串索引优化

#### 前缀索引

```sql
-- 长字符串使用前缀索引
-- 原始：INDEX(email)  -- email平均50字符
-- 优化：INDEX(email(10))  -- 只索引前10个字符

-- 确定合适的前缀长度
SELECT 
    COUNT(DISTINCT LEFT(email, 5)) / COUNT(*) AS sel_5,
    COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) AS sel_10,
    COUNT(DISTINCT LEFT(email, 15)) / COUNT(*) AS sel_15,
    COUNT(DISTINCT email) / COUNT(*) AS sel_full
FROM users;

-- 选择选择性接近完整列的最短长度
```

#### 哈希索引模拟

```sql
-- 对于很长的字符串或TEXT类型
ALTER TABLE articles ADD COLUMN title_hash INT UNSIGNED;
CREATE INDEX idx_title_hash ON articles(title_hash);

-- 应用层计算哈希
INSERT INTO articles (title, title_hash) 
VALUES ('...', CRC32('...'));

-- 查询时使用哈希
SELECT * FROM articles 
WHERE title_hash=CRC32('keyword') AND title='keyword';
-- 注意：必须同时检查原始值（防止哈希碰撞）
```

### 原则8：特殊字段处理

#### NULL值处理

```sql
-- NULL值可以使用索引，但有限制
INDEX(column)
SELECT * FROM table WHERE column IS NULL;  -- ✅ 走索引

-- 但对于联合索引
INDEX(a, b)
SELECT * FROM table WHERE a IS NULL AND b=?;  -- ⚠️ 可能不走索引

-- 建议：重要字段设置 NOT NULL + DEFAULT
```

#### 枚举类型

```sql
-- 使用ENUM或TINYINT存储固定状态
CREATE TABLE orders (
    status ENUM('pending','paid','shipped','completed','cancelled'),
    INDEX idx_status(status)
);

-- 优点：
-- 1. 存储空间小（1-2字节）
-- 2. 索引空间小
-- 3. 比较速度快
```

## 三、索引设计流程

### Step 1：分析查询模式

```sql
-- 收集慢查询日志
SELECT 
    query_time,
    sql_text,
    rows_examined,
    rows_sent
FROM mysql.slow_log
WHERE query_time > 1
ORDER BY query_time DESC;

-- 分析查询频率
-- 工具：pt-query-digest (Percona Toolkit)
```

### Step 2：评估字段特征

```sql
-- 检查字段选择性
SELECT 
    'user_id' AS field,
    COUNT(DISTINCT user_id) / COUNT(*) AS selectivity
FROM orders
UNION ALL
SELECT 
    'status',
    COUNT(DISTINCT status) / COUNT(*)
FROM orders;
```

### Step 3：设计索引方案

```sql
-- 根据查询模式设计
-- 模式1：单条件高频查询 → 单列索引
-- 模式2：组合条件高频查询 → 联合索引
-- 模式3：覆盖查询 → 包含SELECT列的索引
```

### Step 4：验证与优化

```sql
-- 创建索引
CREATE INDEX idx_xxx ON table(...);

-- 验证执行计划
EXPLAIN SELECT ...;

-- 对比性能
-- 创建索引前后的查询时间对比

-- 监控索引使用
SELECT * FROM sys.schema_index_statistics
WHERE table_name='your_table';
```

## 四、实战案例

### 案例1：电商订单表

```sql
-- 表结构（简化）
CREATE TABLE orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    status TINYINT NOT NULL,
    total_amount DECIMAL(10,2),
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL
);

-- 查询分析
-- Q1（40%）：用户查自己订单，按时间倒序
SELECT * FROM orders 
WHERE user_id=? 
ORDER BY create_time DESC 
LIMIT 10;

-- Q2（30%）：用户查特定状态订单
SELECT * FROM orders 
WHERE user_id=? AND status=? 
ORDER BY create_time DESC;

-- Q3（20%）：管理员查特定状态订单
SELECT * FROM orders 
WHERE status=? AND create_time >= ?;

-- Q4（10%）：统计用户订单金额
SELECT user_id, SUM(total_amount) 
FROM orders 
WHERE create_time >= ? 
GROUP BY user_id;

-- 索引方案：
INDEX(user_id, create_time)        -- 覆盖Q1
INDEX(user_id, status, create_time) -- 覆盖Q1+Q2
INDEX(status, create_time)         -- 覆盖Q3
INDEX(create_time, user_id, total_amount) -- 覆盖Q4（覆盖索引）

-- 最终优化（减少冗余）：
INDEX(user_id, status, create_time) -- 主索引
INDEX(status, create_time)          -- 管理员查询
INDEX(create_time)                  -- 时间范围查询
```

### 案例2：社交媒体帖子表

```sql
CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    content TEXT,
    is_deleted TINYINT DEFAULT 0,
    publish_time DATETIME,
    like_count INT DEFAULT 0,
    INDEX idx_user_time(user_id, publish_time),
    INDEX idx_time_like(publish_time, like_count),
    INDEX idx_del_time(is_deleted, publish_time)
);

-- 设计考虑：
-- 1. user_id+publish_time：用户时间线查询
-- 2. publish_time+like_count：热门内容查询（覆盖索引）
-- 3. is_deleted+publish_time：支持软删除过滤
```

## 五、常见错误

### 错误1：为所有字段建索引

```sql
-- ❌ 错误做法
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    age INT,
    email VARCHAR(100),
    phone VARCHAR(20),
    city VARCHAR(50),
    INDEX(name),
    INDEX(age),
    INDEX(email),
    INDEX(phone),
    INDEX(city)  -- 索引过多
);
```

### 错误2：忽略联合索引顺序

```sql
-- 查询：WHERE status=? AND user_id=?
-- ❌ INDEX(user_id, status)  -- user_id区分度高但不常单独查
-- ✅ INDEX(status, user_id)  -- status常单独查，放前面
```

### 错误3：过度使用前缀索引

```sql
-- ❌ 前缀太短
INDEX(email(3))  -- 'abc@...'、'abc@...'  前缀重复太多

-- ✅ 合理长度
INDEX(email(15))  -- 保证足够的区分度
```

## 六、面试总结

**MySQL索引设计的核心原则**：

1. **针对性**：为高频查询条件建索引
2. **选择性**：优先高区分度字段
3. **顺序性**：联合索引遵循最左前缀，高频/等值/高区分度列优先
4. **覆盖性**：尽量实现覆盖索引，减少回表
5. **适度性**：避免过度索引，权衡查询与写入性能
6. **前缀性**：长字符串使用前缀索引
7. **非空性**：重要字段设置NOT NULL
8. **监控性**：定期分析索引使用情况，删除无效索引

**设计流程**：
1. 分析查询模式（慢查询日志）
2. 评估字段特征（选择性、数据类型）
3. 设计索引方案（单列/联合/覆盖）
4. 验证与优化（EXPLAIN分析）

**关键权衡**：
- 查询性能 vs 写入性能
- 索引数量 vs 索引效果
- 完整索引 vs 前缀索引
- 单列索引 vs 联合索引

在面试中能系统地阐述这些原则，并结合实际案例说明，体现了扎实的索引设计能力。

