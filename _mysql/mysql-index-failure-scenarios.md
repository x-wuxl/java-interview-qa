---
title: "MySQL索引失效情况"
date: 2025-11-02
categories: [MySQL, 索引优化]
tags: [MySQL, 索引失效, 性能优化, 最佳实践]
description: "完整总结MySQL索引失效的各种场景，包括查询写法、索引设计、数据分布等方面的常见问题及优化方案。"
nav_order: 295
parent: 数据库MySQL
---
## 一、索引失效场景总览

MySQL索引失效主要分为以下几类：

1. **查询写法导致失效**（最常见）
2. **索引设计不当**
3. **优化器选择问题**
4. **数据分布问题**
5. **系统配置问题**

## 二、查询写法导致失效

### 1. 索引列使用函数

#### 场景A：日期函数

```sql
-- 索引：INDEX(create_time)

-- ❌ 失效：对索引列使用函数
SELECT * FROM orders 
WHERE DATE(create_time) = '2025-11-02';

-- ❌ 失效：提取年份
SELECT * FROM orders 
WHERE YEAR(create_time) = 2025;

-- ❌ 失效：月份查询
SELECT * FROM orders 
WHERE MONTH(create_time) = 11;
```

**失效原因**：函数破坏了索引的有序性，无法使用B+树快速定位。

**优化方案**：

```sql
-- ✅ 方案1：改写为范围查询
SELECT * FROM orders 
WHERE create_time >= '2025-11-02 00:00:00' 
  AND create_time < '2025-11-03 00:00:00';

-- ✅ 方案2：年份查询
SELECT * FROM orders 
WHERE create_time >= '2025-01-01 00:00:00' 
  AND create_time < '2026-01-01 00:00:00';

-- ✅ 方案3：函数索引（MySQL 8.0.13+）
CREATE INDEX idx_create_date ON orders((DATE(create_time)));
SELECT * FROM orders WHERE DATE(create_time) = '2025-11-02';

-- ✅ 方案4：添加冗余字段
ALTER TABLE orders ADD COLUMN create_date DATE;
UPDATE orders SET create_date = DATE(create_time);
CREATE INDEX idx_create_date ON orders(create_date);
```

#### 场景B：字符串函数

```sql
-- 索引：INDEX(name)

-- ❌ 失效：大小写转换
SELECT * FROM users WHERE UPPER(name) = 'ZHANG';
SELECT * FROM users WHERE LOWER(email) = 'user@example.com';

-- ❌ 失效：字符串截取
SELECT * FROM users WHERE SUBSTRING(phone, 1, 3) = '138';

-- ❌ 失效：拼接
SELECT * FROM users WHERE CONCAT(first_name, last_name) = 'Zhang San';
```

**优化方案**：

```sql
-- ✅ 使用不区分大小写的排序规则
-- 字段定义时使用 COLLATE utf8mb4_general_ci
CREATE TABLE users (
    name VARCHAR(50) COLLATE utf8mb4_general_ci
);
SELECT * FROM users WHERE name = 'zhang';  -- 自动不区分大小写

-- ✅ 前缀匹配
SELECT * FROM users WHERE phone LIKE '138%';

-- ✅ 添加冗余字段
ALTER TABLE users ADD COLUMN full_name VARCHAR(100);
UPDATE users SET full_name = CONCAT(first_name, ' ', last_name);
CREATE INDEX idx_full_name ON users(full_name);
```

### 2. 索引列进行计算

```sql
-- 索引：INDEX(age), INDEX(price)

-- ❌ 失效：对索引列计算
SELECT * FROM users WHERE age + 1 = 30;
SELECT * FROM products WHERE price * 0.9 > 100;
SELECT * FROM orders WHERE amount - discount > 500;
```

**优化方案**：

```sql
-- ✅ 移动计算到等号右边
SELECT * FROM users WHERE age = 30 - 1;  -- age = 29
SELECT * FROM products WHERE price > 100 / 0.9;  -- price > 111.11
SELECT * FROM orders WHERE amount > 500 + discount;

-- ✅ 添加计算字段
ALTER TABLE products ADD COLUMN final_price DECIMAL(10,2);
UPDATE products SET final_price = price * 0.9;
CREATE INDEX idx_final_price ON products(final_price);
```

### 3. 隐式类型转换

#### 场景A：字符串字段 vs 数字

```sql
-- 字段定义：phone VARCHAR(20), INDEX(phone)

-- ❌ 失效：字符串字段用数字查询
SELECT * FROM users WHERE phone = 13800138000;
-- MySQL转换为：WHERE CAST(phone AS UNSIGNED) = 13800138000

-- ✅ 优化：使用字符串
SELECT * FROM users WHERE phone = '13800138000';
```

**规则**：
- **字符串字段** vs **数字值** → 索引失效（字段被转换）
- **数字字段** vs **字符串值** → 索引有效（值被转换）

```sql
-- 字段定义：user_id INT, INDEX(user_id)

-- ✅ 有效：数字字段用字符串查询
SELECT * FROM orders WHERE user_id = '12345';
-- MySQL转换为：WHERE user_id = CAST('12345' AS INT)
-- 值被转换，字段未变，索引有效
```

#### 场景B：字符集不同

```sql
-- orders表：utf8
-- users表：utf8mb4

-- ⚠️ 可能失效
SELECT * FROM orders o
JOIN users u ON o.user_name = u.name;
-- 字符集转换可能导致索引失效

-- ✅ 优化：统一字符集
ALTER TABLE orders CONVERT TO CHARACTER SET utf8mb4;
```

### 4. 前导通配符

```sql
-- 索引：INDEX(name), INDEX(email)

-- ❌ 失效：前导通配符
SELECT * FROM users WHERE name LIKE '%张三%';
SELECT * FROM users WHERE email LIKE '%@gmail.com';
SELECT * FROM users WHERE name LIKE '%三';

-- ✅ 有效：后缀通配符
SELECT * FROM users WHERE name LIKE '张三%';
SELECT * FROM users WHERE email LIKE 'user@%';
```

**原因**：前导通配符无法利用索引的前缀有序性。

**优化方案**：

```sql
-- 方案1：全文索引（中文需要分词插件）
CREATE FULLTEXT INDEX idx_name_ft ON users(name);
SELECT * FROM users WHERE MATCH(name) AGAINST('张三' IN BOOLEAN MODE);

-- 方案2：搜索引擎（推荐）
-- 使用Elasticsearch、Solr等

-- 方案3：反向索引（特殊场景）
-- 如果是邮箱域名查询 '%@gmail.com'
ALTER TABLE users ADD COLUMN email_reverse VARCHAR(100);
UPDATE users SET email_reverse = REVERSE(email);
CREATE INDEX idx_email_reverse ON users(email_reverse);
SELECT * FROM users WHERE email_reverse LIKE REVERSE('@gmail.com') || '%';
```

### 5. 负向查询

```sql
-- 索引：INDEX(status)

-- ⚠️ 可能失效
SELECT * FROM orders WHERE status != 'cancelled';
SELECT * FROM orders WHERE status NOT IN ('cancelled', 'refunded');
SELECT * FROM orders WHERE id NOT BETWEEN 1000 AND 2000;
SELECT * FROM users WHERE name IS NOT NULL;  -- 特殊情况
```

**是否失效取决于数据分布**：

```sql
-- 场景1：排除少量数据（1%）
-- status='cancelled' 只有1%
SELECT * FROM orders WHERE status != 'cancelled';
-- ✅ 索引有效：返回99%数据，但优化器判断走索引更快

-- 场景2：排除大量数据（50%）
-- status='cancelled' 有50%
SELECT * FROM orders WHERE status != 'cancelled';
-- ❌ 可能全表扫描：返回50%数据，回表成本高
```

**优化方案**：

```sql
-- 方案1：改写为正向查询（如果值域小）
-- 假设status只有5个值：pending, paid, shipped, completed, cancelled
SELECT * FROM orders 
WHERE status IN ('pending', 'paid', 'shipped', 'completed');

-- 方案2：接受全表扫描（如果过滤后数据量大）
-- 或者优化其他条件
```

### 6. OR条件

```sql
-- 索引：INDEX(user_id), INDEX(merchant_id)

-- ⚠️ 可能失效或使用索引合并
SELECT * FROM orders 
WHERE user_id=12345 OR merchant_id=67890;

-- 可能的执行计划：
-- 1. 全表扫描（最差）
-- 2. 索引合并（Index Merge Union）（次优）
-- 3. 无法同时完整使用两个索引
```

**优化方案**：

```sql
-- 方案1：改写为UNION（推荐）
SELECT * FROM orders WHERE user_id=12345
UNION
SELECT * FROM orders WHERE merchant_id=67890;
-- 明确使用两个索引，性能可控

-- 方案2：同一字段用IN
SELECT * FROM orders WHERE user_id IN (12345, 67890);

-- 方案3：联合索引（特殊场景）
-- 如果总是这样查询，创建
CREATE INDEX idx_user_merchant ON orders(user_id, merchant_id);
-- 但这个索引对OR条件帮助有限
```

## 三、索引设计导致失效

### 1. 违反最左前缀原则

```sql
-- 索引：INDEX(a, b, c)

-- ❌ 完全失效：跳过最左列
SELECT * FROM table WHERE b=2;
SELECT * FROM table WHERE c=3;
SELECT * FROM table WHERE b=2 AND c=3;

-- ⚠️ 部分失效：跳过中间列
SELECT * FROM table WHERE a=1 AND c=3;
-- 只用到a，c失效

-- ✅ 完整使用
SELECT * FROM table WHERE a=1 AND b=2 AND c=3;
```

**优化方案**：

```sql
-- 方案1：调整查询条件（使用最左列）
SELECT * FROM table WHERE a IS NOT NULL AND b=2 AND c=3;

-- 方案2：创建合适的索引
-- 如果经常 WHERE b=? AND c=?
CREATE INDEX idx_bc ON table(b, c);

-- 方案3：利用索引跳跃扫描（MySQL 8.0.13+）
-- 如果a的值很少（如2-3个），优化器可能自动优化
```

### 2. 范围查询阻断后续列

```sql
-- 索引：INDEX(a, b, c)

-- ⚠️ c列无法使用
SELECT * FROM table WHERE a=1 AND b>10 AND c=5;
-- 使用：a（等值）、b（范围）
-- 失效：c（范围后失效）

EXPLAIN查看：
key_len: 8  -- 只用了a和b
```

**原因**：b是范围查询，在b>10的范围内，c列无序。

**优化方案**：

```sql
-- 方案1：调整索引列顺序（如果c过滤效果更好）
CREATE INDEX idx_ac_b ON table(a, c, b);
-- a=1 AND c=5 精确过滤，b>10最后处理

-- 方案2：使用联合索引 + 索引下推
-- 虽然c不能用于定位，但可以通过ICP在索引层面过滤
-- Extra: Using index condition

-- 方案3：拆分为多个精确条件
-- 如果b的范围很小
WHERE a=1 AND b IN (11, 12, 13, 14, 15) AND c=5
```

### 3. 索引列顺序不合理

```sql
-- 场景：经常查询 WHERE status=? AND user_id=?
-- status区分度低（5个值）
-- user_id区分度高（100万个值）

-- ❌ 不合理
CREATE INDEX idx_status_user ON orders(status, user_id);
-- status过滤到20%数据，然后user_id进一步过滤

-- ✅ 更合理
CREATE INDEX idx_user_status ON orders(user_id, status);
-- user_id直接定位到该用户数据，status进一步过滤

-- 但要考虑：是否有单独查status的需求
-- 如果有，可能需要保留 idx_status_user
```

### 4. 索引区分度太低

```sql
-- 索引：INDEX(gender)  -- 只有M/F两个值

SELECT * FROM users WHERE gender='M';
-- 返回50%的数据（500万行）

EXPLAIN：
type: ALL  -- 优化器选择全表扫描
key: NULL

-- 原因：
-- 回表成本：500万次随机IO
-- 全表扫描：顺序IO，可能更快
```

**优化方案**：

```sql
-- 方案1：联合索引（提升区分度）
CREATE INDEX idx_gender_age_city ON users(gender, age, city);
SELECT * FROM users WHERE gender='M' AND age>20 AND city='Beijing';

-- 方案2：覆盖索引（避免回表）
CREATE INDEX idx_gender_id_name ON users(gender, id, name);
SELECT id, name FROM users WHERE gender='M';

-- 方案3：接受全表扫描
-- 如果确实需要50%的数据，全表扫描是合理的
```

## 四、优化器选择问题

### 1. 统计信息过时

```sql
-- 问题：表数据大量变化后，统计信息未更新

-- 实际：status='active' 只有1000行
-- 统计：优化器认为有100万行

EXPLAIN SELECT * FROM orders WHERE status='active';
type: ALL  -- 优化器错误地选择全表扫描
rows: 1000000  -- 预估错误
```

**解决方案**：

```sql
-- 方案1：手动更新统计信息
ANALYZE TABLE orders;

-- 方案2：配置自动更新（MySQL 8.0+）
SET GLOBAL innodb_stats_auto_recalc = ON;

-- 方案3：查看统计信息
SHOW INDEX FROM orders;
-- 检查Cardinality列是否异常

-- 方案4：强制使用索引（临时）
SELECT * FROM orders FORCE INDEX(idx_status) 
WHERE status='active';
```

### 2. 索引选择错误

```sql
-- 有两个索引：
-- INDEX(status) - 过滤到50万行
-- INDEX(create_time) - 过滤到1000行

SELECT * FROM orders 
WHERE status='paid' AND create_time >= '2025-11-01';

-- 优化器错误选择 idx_status
EXPLAIN:
key: idx_status
rows: 500000

-- 应该选择 idx_create_time
```

**解决方案**：

```sql
-- 方案1：强制使用正确索引
SELECT * FROM orders FORCE INDEX(idx_create_time)
WHERE status='paid' AND create_time >= '2025-11-01';

-- 方案2：创建联合索引（根本解决）
CREATE INDEX idx_time_status ON orders(create_time, status);
-- 或
CREATE INDEX idx_status_time ON orders(status, create_time);

-- 方案3：使用optimizer hint（MySQL 8.0+）
SELECT /*+ INDEX(orders idx_create_time) */ *
FROM orders 
WHERE status='paid' AND create_time >= '2025-11-01';

-- 方案4：更新统计信息后重试
ANALYZE TABLE orders;
```

### 3. 回表成本过高

```sql
-- 索引存在但优化器不用

-- 索引：INDEX(status)
SELECT * FROM orders WHERE status='paid';

-- status='paid' 占90%的数据（900万行）

EXPLAIN:
type: ALL  -- 全表扫描
key: NULL
rows: 10000000

-- 原因：回表900万次成本太高
```

**这不是索引失效，而是优化器正确选择**。

**优化方案**：

```sql
-- 方案1：添加过滤条件
SELECT * FROM orders 
WHERE status='paid' AND create_time >= '2025-11-01';

-- 方案2：覆盖索引（无需回表）
CREATE INDEX idx_status_cols ON orders(status, id, total_amount, user_id);
SELECT id, total_amount, user_id FROM orders WHERE status='paid';

-- 方案3：接受全表扫描
-- 如果确实需要90%的数据，全表扫描是最优的
```

## 五、系统配置问题

### 1. 优化器开关

```sql
-- 查看优化器配置
SHOW VARIABLES LIKE 'optimizer_switch';

-- 相关开关：
-- index_merge=on  -- 索引合并
-- index_merge_union=on
-- index_merge_sort_union=on
-- index_merge_intersection=on
-- index_condition_pushdown=on  -- 索引下推
-- skip_scan=on  -- 索引跳跃扫描（MySQL 8.0.13+）

-- 如果关闭了某些优化，可能导致"失效"
```

### 2. 表统计信息配置

```sql
-- 持久化统计信息（推荐）
CREATE TABLE orders (
    ...
) ENGINE=InnoDB 
  STATS_PERSISTENT=1
  STATS_AUTO_RECALC=1;

-- STATS_PERSISTENT=1: 统计信息持久化
-- STATS_AUTO_RECALC=1: 自动重新计算
```

## 六、特殊场景

### 1. 小表不走索引

```sql
-- 表只有100行数据
CREATE TABLE config (
    id INT PRIMARY KEY,
    key VARCHAR(50),
    value TEXT,
    INDEX idx_key(key)
);

SELECT * FROM config WHERE key='timeout';

EXPLAIN:
type: ALL  -- 全表扫描
rows: 100

-- 原因：表太小，全表扫描更快（顺序IO）
-- 这是正常的优化器行为，不是失效
```

### 2. 覆盖索引但仍慢

```sql
-- 索引：INDEX(status, create_time)
SELECT status, create_time FROM orders;
-- 无WHERE条件

EXPLAIN:
type: index  -- 索引全扫描
Extra: Using index

-- 虽然是覆盖索引，但扫描整个索引树仍然慢
-- 优化：添加WHERE条件限制范围
```

### 3. IS NULL 的特殊性

```sql
-- 索引列允许NULL

-- MySQL 5.x及以前：IS NULL 可能不走索引
SELECT * FROM users WHERE email IS NULL;

-- MySQL 8.0+：IS NULL 走索引
EXPLAIN:
type: ref
key: idx_email

-- 建议：重要字段设置 NOT NULL + DEFAULT
```

## 七、索引失效检查清单

### 日常开发检查

```
查询写法：
□ 索引列是否使用函数（DATE、UPPER等）
□ 索引列是否进行计算（age+1、price*0.9）
□ 字符串字段是否用数字查询（类型转换）
□ 是否使用前导通配符（LIKE '%xxx'）
□ 是否使用负向查询（!=、NOT IN）
□ 是否使用OR连接不同字段

索引设计：
□ 是否违反最左前缀原则
□ 范围查询是否阻断后续列
□ 索引列顺序是否合理
□ 索引区分度是否足够（>0.1）

数据情况：
□ 统计信息是否准确（ANALYZE TABLE）
□ 过滤后数据量是否过大（>30%）
□ 表数据量是否太小（<1000行）
```

### EXPLAIN检查

```
□ type: ALL/index → 可能失效
□ key: NULL → 未使用索引
□ possible_keys: 有候选但key=NULL → 优化器放弃
□ rows: 是否异常大
□ key_len: 联合索引使用了几列
□ Extra: Using filesort/temporary → 需要优化
```

## 八、优化建议总结

### 查询层面

1. **避免函数**：不在索引列使用函数
2. **避免计算**：不在索引列进行计算
3. **类型匹配**：确保查询条件类型与字段一致
4. **避免通配符**：不使用前导通配符
5. **改写OR**：OR改UNION，或使用IN

### 索引层面

1. **遵守最左前缀**：从最左列开始使用
2. **合理顺序**：等值→范围，高区分度优先
3. **覆盖索引**：把常查列加入索引
4. **联合索引**：优于多个单列索引
5. **定期维护**：ANALYZE TABLE更新统计

### 系统层面

1. **配置优化**：确保optimizer_switch正确
2. **统计信息**：开启自动更新
3. **监控索引**：删除未使用索引
4. **版本升级**：新版本有更多优化特性

## 九、面试总结

**MySQL索引失效的主要场景**：

**查询写法（最常见）**：
1. 索引列使用函数：`DATE()`、`UPPER()`等
2. 索引列进行计算：`age+1`、`price*0.9`
3. 隐式类型转换：字符串字段用数字查询
4. 前导通配符：`LIKE '%xxx'`
5. 负向查询：`!=`、`NOT IN`（取决于数据分布）
6. OR条件：连接不同字段

**索引设计**：
7. 违反最左前缀原则
8. 范围查询阻断后续列
9. 索引列顺序不合理
10. 索引区分度太低

**优化器选择**：
11. 统计信息过时
12. 索引选择错误
13. 回表成本过高（优化器正确放弃）

**排查方法**：
- EXPLAIN查看执行计划
- 检查type、key、key_len、rows
- ANALYZE TABLE更新统计
- 对比不同索引的效果

**优化原则**：
- 查询写法规范化
- 索引设计合理化
- 定期维护和监控
- 使用工具辅助分析

掌握这些索引失效场景和优化方法，能够有效解决绝大多数索引相关的性能问题。

