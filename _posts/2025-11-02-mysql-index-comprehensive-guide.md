---
layout: post
title: "MySQL索引，最左匹配，索引覆盖，索引下推，索引失效情况，查询优化"
date: 2025-11-02
categories: [MySQL, 索引优化]
tags: [MySQL, 索引, 最左匹配, 索引覆盖, 索引下推, 查询优化]
description: "MySQL索引核心知识点综合指南，涵盖最左匹配原则、索引覆盖、索引下推、索引失效场景和查询优化技巧。"
---

## 一、最左匹配原则

### 1. 核心概念

**最左匹配原则**：联合索引必须从最左列开始连续使用，不能跳过中间列。

```sql
-- 索引：INDEX(a, b, c)

✅ 可以使用：
WHERE a=1
WHERE a=1 AND b=2
WHERE a=1 AND b=2 AND c=3

❌ 无法完整使用：
WHERE b=2  -- 完全不走索引
WHERE c=3  -- 完全不走索引
WHERE a=1 AND c=3  -- 只用到a，c无法使用
```

### 2. 原理

联合索引在B+树中按照 **a → b → c** 的顺序排列：

```
索引数据排列：
(1, 1, 1)
(1, 1, 2)
(1, 2, 1)  ← a相同时，按b排序
(2, 1, 1)
(2, 2, 1)  ← b只在a相同时有序
```

- **a列**：全局有序，可以快速定位
- **b列**：只在a相同时有序
- **c列**：只在a、b都相同时有序

### 3. 范围查询的影响

```sql
-- 索引：INDEX(a, b, c)

WHERE a=1 AND b>10 AND c=5

-- 使用情况：
-- a: ✅ 使用（等值）
-- b: ✅ 使用（范围）
-- c: ❌ 不使用（范围后失效）
```

**原因**：b是范围查询，在b>10的范围内，c列无序。

### 4. 优化建议

```sql
-- 原则1：等值查询列放前面
INDEX(a, b, c)  -- a、b等值，c范围

-- 原则2：高区分度列放前面
INDEX(user_id, status, create_time)  -- user_id区分度高

-- 原则3：根据查询频率调整
-- 如果WHERE a=? AND c=? 很频繁
-- 考虑创建 INDEX(a, c, b)
```

## 二、索引覆盖

### 1. 核心概念

**索引覆盖**（Covering Index）：查询的所有字段都在索引中，无需回表查询。

```sql
-- 索引：INDEX(user_id, status, create_time)

-- ✅ 覆盖索引（无回表）
SELECT user_id, status, create_time
FROM orders
WHERE user_id=12345;

-- Extra: Using index  ← 关键标识

-- ❌ 非覆盖索引（需要回表）
SELECT user_id, status, create_time, total_amount
FROM orders
WHERE user_id=12345;

-- Extra: Using index condition  ← 需要回表获取total_amount
```

### 2. 性能优势

```
回表成本 = 返回行数 × 单次回表IO成本

示例：
- 返回1000行
- 覆盖索引：只需索引扫描，0次回表
- 非覆盖索引：需要回表1000次

性能差异：
- 数据在内存：提升20%-50%
- 数据在磁盘：提升5-10倍
```

### 3. 应用场景

#### 场景1：分页查询优化（延迟关联）

```sql
-- 不好：需要回表100020次
SELECT * FROM orders 
WHERE status='paid'
ORDER BY create_time DESC 
LIMIT 100000, 20;

-- 好：利用覆盖索引 + 延迟关联
SELECT o.*
FROM orders o
INNER JOIN (
    SELECT id 
    FROM orders
    WHERE status='paid'
    ORDER BY create_time DESC
    LIMIT 100000, 20
) t ON o.id = t.id;

-- 子查询走覆盖索引，只回表20次
```

#### 场景2：统计查询

```sql
-- 索引：INDEX(user_id, status, create_time)

-- 覆盖索引优化
SELECT 
    user_id,
    COUNT(*) AS total,
    SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) AS paid_count
FROM orders
WHERE create_time >= '2025-01-01'
GROUP BY user_id;

-- 全部字段都在索引中，无需回表
```

#### 场景3：EXISTS优化

```sql
-- 不好：SELECT *
SELECT * FROM users u
WHERE EXISTS (
    SELECT * FROM orders o WHERE o.user_id=u.id
);

-- 好：SELECT 1 或主键（覆盖索引）
SELECT * FROM users u
WHERE EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id=u.id
);
```

### 4. 设计技巧

```sql
-- 技巧1：把常查列加到索引末尾
-- 查询：SELECT id, name, age FROM users WHERE city='Beijing'
CREATE INDEX idx_city_name_age ON users(city, name, age);

-- 技巧2：利用主键自动包含
-- InnoDB的二级索引自动包含主键
INDEX(user_id, status)
-- 实际包含：(user_id, status, id)
-- 查询id时无需回表
```

## 三、索引下推（ICP）

### 1. 核心概念

**索引下推**（Index Condition Pushdown，ICP）：MySQL 5.6+引入，将WHERE条件的一部分下推到存储引擎层面，在索引遍历时就进行过滤。

```sql
-- 索引：INDEX(user_id, age, city)

SELECT * FROM users 
WHERE user_id=12345 AND age>20 AND city='Beijing';
```

**无ICP时**：

```
1. 使用索引定位 user_id=12345 AND age>20 的记录
2. 回表获取完整行
3. 在Server层过滤 city='Beijing'

回表1000次 → 返回100行（city过滤后）
```

**有ICP时**：

```
1. 使用索引定位 user_id=12345 AND age>20
2. 在索引层面过滤 city='Beijing'（索引下推）
3. 只对符合所有条件的记录回表

回表100次 → 返回100行

减少回表次数：从1000次减少到100次
```

### 2. EXPLAIN识别

```sql
EXPLAIN SELECT * FROM users 
WHERE user_id=12345 AND age>20 AND city='Beijing';

-- Extra: Using index condition  ← ICP启用
```

### 3. 触发条件

```
✅ 会使用ICP：
- 使用了索引但需要回表
- WHERE条件中有索引列但未全部使用
- InnoDB和MyISAM引擎

❌ 不使用ICP：
- 覆盖索引（无需回表）
- 全表扫描
- 查询条件不涉及索引列
```

### 4. 开关控制

```sql
-- 查看状态
SHOW VARIABLES LIKE 'optimizer_switch';
-- index_condition_pushdown=on

-- 关闭ICP（不建议）
SET optimizer_switch='index_condition_pushdown=off';
```

### 5. 性能影响

```sql
-- 测试表：1000万行
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    age INT,
    city VARCHAR(50),
    data TEXT,  -- 大字段
    INDEX idx_user_age_city(user_id, age, city)
);

-- 查询：返回100行，但需要从10000行中过滤
SELECT * FROM users 
WHERE user_id=12345 AND age>20 AND city='Beijing';

-- 无ICP：回表10000次
-- 执行时间：2.5秒

-- 有ICP：回表100次
-- 执行时间：0.3秒

-- 性能提升：8倍
```

## 四、索引失效情况

### 1. 索引列使用函数

```sql
-- ❌ 失效
WHERE DATE(create_time) = '2025-11-02'
WHERE YEAR(create_time) = 2025
WHERE UPPER(name) = 'ZHANG'

-- ✅ 优化
WHERE create_time >= '2025-11-02 00:00:00' 
  AND create_time < '2025-11-03 00:00:00'

WHERE create_time >= '2025-01-01' 
  AND create_time < '2026-01-01'

-- MySQL 8.0+ 可以创建函数索引
CREATE INDEX idx_year ON orders((YEAR(create_time)));
```

### 2. 索引列进行计算

```sql
-- ❌ 失效
WHERE age + 1 = 30
WHERE price * 0.9 > 100

-- ✅ 优化
WHERE age = 29
WHERE price > 100 / 0.9
```

### 3. 隐式类型转换

```sql
-- 字段：phone VARCHAR(20)

-- ❌ 失效（字符串→数字转换）
WHERE phone = 13800138000

-- ✅ 优化
WHERE phone = '13800138000'

-- 规则：
-- 字符串字段 vs 数字值 → 索引失效
-- 数字字段 vs 字符串值 → 索引有效（条件转换）
```

### 4. 前导通配符

```sql
-- ❌ 失效
WHERE name LIKE '%张三%'
WHERE email LIKE '%@gmail.com'

-- ✅ 可以使用
WHERE name LIKE '张三%'
WHERE email LIKE 'user@%'

-- 优化方案：
-- 1. 使用全文索引（FULLTEXT）
-- 2. 使用Elasticsearch等搜索引擎
-- 3. 反向字符串+前缀索引（特殊场景）
```

### 5. 负向查询

```sql
-- ⚠️ 可能失效
WHERE status != 'cancelled'
WHERE status NOT IN ('cancelled', 'refunded')
WHERE id NOT BETWEEN 1000 AND 2000

-- 优化：
-- 1. 改写为正向查询（如果值域小）
WHERE status IN ('pending', 'paid', 'shipped', 'completed')

-- 2. 如果负向过滤效果好（如只排除1%），索引仍可能有效
```

### 6. OR条件

```sql
-- ❌ 可能失效
WHERE user_id=? OR merchant_id=?

-- ✅ 优化1：改写为UNION
SELECT * FROM orders WHERE user_id=?
UNION
SELECT * FROM orders WHERE merchant_id=?;

-- ✅ 优化2：如果是同一字段
WHERE user_id IN (?, ?)

-- ⚠️ 索引合并：
-- 如果有 INDEX(user_id) 和 INDEX(merchant_id)
-- 可能触发索引合并（Index Merge Union）
```

### 7. 违反最左前缀

```sql
-- 索引：INDEX(a, b, c)

-- ❌ 完全失效
WHERE b=? AND c=?

-- ⚠️ 部分失效
WHERE a=? AND c=?  -- 只用到a

-- ✅ 完整使用
WHERE a=? AND b=? AND c=?
```

### 8. 区分度太低

```sql
-- 索引：INDEX(gender)  -- 只有M/F

-- 查询返回50%的数据
SELECT * FROM users WHERE gender='M';

-- 优化器可能选择全表扫描：
-- 原因：回表成本太高（500万次）
-- 全表扫描的顺序IO更快
```

## 五、查询优化技巧

### 1. SELECT优化

```sql
-- ❌ 不要SELECT *
SELECT * FROM orders WHERE user_id=?;

-- ✅ 只查需要的列
SELECT id, total_amount, create_time 
FROM orders WHERE user_id=?;

-- 好处：
-- 1. 减少网络传输
-- 2. 可能实现覆盖索引
-- 3. 减少内存占用
```

### 2. JOIN优化

```sql
-- 原则：小表驱动大表

-- ❌ 大表驱动小表
SELECT o.* FROM orders o  -- 1000万行
JOIN users u ON o.user_id=u.id  -- 10万行
WHERE u.city='Beijing';  -- 1000行

-- ✅ 小表驱动大表
SELECT o.* FROM users u  -- 10万行
JOIN orders o ON u.id=o.user_id  -- 1000万行
WHERE u.city='Beijing';  -- 1000行

-- 确保JOIN字段有索引：
-- orders.user_id 需要索引
```

### 3. IN vs EXISTS

```sql
-- IN适合：子查询返回结果少
SELECT * FROM orders
WHERE user_id IN (
    SELECT id FROM users WHERE city='Beijing'  -- 1000行
);

-- EXISTS适合：子查询返回结果多
SELECT * FROM users u
WHERE EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id=u.id
);

-- 规则：
-- 外表小用IN，外表大用EXISTS
```

### 4. COUNT优化

```sql
-- ❌ 慢
SELECT COUNT(*) FROM orders WHERE status='paid';

-- ✅ 快1：覆盖索引
CREATE INDEX idx_status ON orders(status);
SELECT COUNT(*) FROM orders WHERE status='paid';
-- 索引扫描，无需回表

-- ✅ 快2：近似值（业务允许的话）
SELECT table_rows FROM information_schema.tables
WHERE table_name='orders';

-- ✅ 快3：异步统计
-- 后台定时统计，写入缓存表
```

### 5. LIMIT优化（深度分页）

```sql
-- ❌ 深度分页很慢
SELECT * FROM orders 
ORDER BY create_time DESC 
LIMIT 100000, 20;

-- ✅ 延迟关联
SELECT o.* FROM orders o
JOIN (
    SELECT id FROM orders
    ORDER BY create_time DESC
    LIMIT 100000, 20
) t ON o.id=t.id;

-- ✅ 游标分页（记录上次位置）
SELECT * FROM orders 
WHERE create_time < '上次最后一条时间'
ORDER BY create_time DESC 
LIMIT 20;
```

### 6. GROUP BY优化

```sql
-- ❌ 产生临时表
SELECT user_id, COUNT(*)
FROM orders
WHERE create_time >= '2025-01-01'
GROUP BY user_id;

-- ✅ 索引优化
CREATE INDEX idx_time_user ON orders(create_time, user_id);

-- ✅ 覆盖索引
CREATE INDEX idx_time_user_status ON orders(create_time, user_id, status);
SELECT user_id, COUNT(*), SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END)
FROM orders
WHERE create_time >= '2025-01-01'
GROUP BY user_id;
```

### 7. ORDER BY优化

```sql
-- ❌ 产生filesort
SELECT * FROM orders 
WHERE user_id=? 
ORDER BY create_time DESC;

-- ✅ 索引排序
CREATE INDEX idx_user_time ON orders(user_id, create_time);

-- Extra: Using index  ← 无filesort

-- 注意：排序方向要一致
INDEX(a ASC, b ASC)  -- 或都DESC
WHERE a=? ORDER BY b ASC  -- ✅
WHERE a=? ORDER BY b DESC  -- MySQL 8.0+也支持倒序扫描
```

### 8. 子查询优化

```sql
-- ❌ 依赖子查询（慢）
SELECT * FROM orders o
WHERE o.user_id = (
    SELECT id FROM users WHERE name='张三'
);

-- ✅ JOIN改写
SELECT o.* FROM orders o
JOIN users u ON o.user_id=u.id
WHERE u.name='张三';

-- MySQL 5.6+ 的子查询优化已经很好
-- 但JOIN通常更直观和可控
```

## 六、综合实战案例

### 案例：电商订单查询优化

#### 原始查询（慢）

```sql
SELECT 
    o.id,
    o.order_no,
    o.total_amount,
    o.status,
    o.create_time,
    u.name AS user_name,
    u.phone
FROM orders o
JOIN users u ON o.user_id=u.id
WHERE DATE(o.create_time) >= '2025-11-01'
  AND o.status IN ('paid', 'shipped')
  AND o.total_amount * 0.9 > 100
ORDER BY o.create_time DESC
LIMIT 10000, 20;

-- 执行时间：5.2秒
```

#### 问题分析

```sql
EXPLAIN 分析：
1. DATE(create_time) → 索引失效
2. total_amount * 0.9 → 索引失效
3. LIMIT 10000, 20 → 深度分页
4. 回表次数：10020次

慢查询日志：
Query_time: 5.234
Rows_examined: 5000000
Rows_sent: 20
```

#### 优化后（快）

```sql
-- 1. 创建优化索引
CREATE INDEX idx_status_time_amount 
ON orders(status, create_time, total_amount, id, order_no, user_id);

-- 2. 优化查询
SELECT 
    t.id,
    t.order_no,
    t.total_amount,
    t.status,
    t.create_time,
    u.name AS user_name,
    u.phone
FROM (
    SELECT id, order_no, total_amount, status, create_time, user_id
    FROM orders
    WHERE status IN ('paid', 'shipped')
      AND create_time >= '2025-11-01 00:00:00'  -- 去除DATE函数
      AND total_amount > 111.11  -- 预计算 100/0.9
    ORDER BY create_time DESC
    LIMIT 10000, 20
) t
JOIN users u ON t.user_id=u.id;

-- 执行时间：0.12秒（快43倍）
```

#### 优化点总结

```
1. 去除函数：DATE() → 直接比较
2. 避免计算：total_amount * 0.9 > 100 → total_amount > 111.11
3. 覆盖索引：子查询所需字段都在索引中
4. 延迟关联：只对最终20行进行JOIN
5. 索引排序：避免filesort
```

## 七、面试要点总结

### 最左匹配

- **原理**：联合索引按从左到右顺序排列，后续列只在前面列相同时有序
- **使用**：必须从最左列开始，不能跳过
- **范围**：范围查询会导致后续列失效

### 索引覆盖

- **定义**：查询字段都在索引中，无需回表
- **识别**：Extra: Using index
- **优势**：避免回表，性能提升显著
- **应用**：分页优化（延迟关联）、统计查询

### 索引下推

- **定义**：将WHERE条件下推到存储引擎层过滤
- **版本**：MySQL 5.6+
- **识别**：Extra: Using index condition
- **优势**：减少回表次数

### 索引失效

- **函数**：索引列使用函数
- **计算**：索引列进行计算
- **类型**：隐式类型转换（字符串字段用数字查询）
- **通配符**：LIKE '%xxx'
- **最左**：违反最左前缀原则

### 查询优化

- 避免SELECT *
- 小表驱动大表（JOIN）
- 深度分页用延迟关联
- 覆盖索引优化COUNT/GROUP BY
- 索引排序优化ORDER BY

这些是MySQL索引的核心知识点，掌握这些能够有效优化90%以上的索引相关问题。

