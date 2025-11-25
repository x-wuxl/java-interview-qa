---
layout: default
title: "索引失效的问题如何排查？"
parent: 数据库MySQL
nav_order: 298
description: "系统讲解MySQL索引失效的排查方法和工具，包括EXPLAIN分析、慢查询日志、执行计划解读等实战技巧。"
date: 2025-11-02
---
## 一、排查工具和方法

MySQL索引失效排查主要使用以下工具：

1. **EXPLAIN**：查看执行计划
2. **EXPLAIN ANALYZE**：查看实际执行情况（MySQL 8.0.18+）
3. **慢查询日志**：记录慢SQL
4. **SHOW WARNINGS**：查看优化器警告
5. **SHOW PROFILE**：详细性能分析
6. **优化器追踪**：optimizer_trace

## 二、EXPLAIN 详解

### 1. 基本用法

```sql
EXPLAIN SELECT * FROM orders 
WHERE user_id=12345 AND status='paid';
```

### 2. 关键字段解读

#### id（查询序列号）

```sql
-- id相同：执行顺序从上到下
-- id不同：id越大越先执行

EXPLAIN 
SELECT * FROM orders o
WHERE user_id IN (
    SELECT user_id FROM users WHERE city='Beijing'
);

-- 输出：
-- id=1: SELECT * FROM orders
-- id=2: SELECT user_id FROM users  ← 先执行（子查询）
```

#### select_type（查询类型）

```
SIMPLE: 简单查询（无子查询、UNION）
PRIMARY: 最外层查询
SUBQUERY: 子查询
DERIVED: 派生表（FROM子句中的子查询）
UNION: UNION的第二个及后续查询
```

#### type（访问类型）⭐

**性能从好到差**：

```
system > const > eq_ref > ref > range > index > ALL

✅ 好的类型：
- const: 主键或唯一索引等值查询
  WHERE id=1

- eq_ref: 主键或唯一索引连接
  JOIN ON t1.id = t2.user_id (user_id是唯一索引)

- ref: 非唯一索引等值查询
  WHERE user_id=12345

- range: 索引范围扫描
  WHERE id BETWEEN 1 AND 100

❌ 差的类型：
- index: 索引全扫描（扫描整个索引树）
  SELECT id FROM table  -- 只查主键，但无WHERE

- ALL: 全表扫描
  WHERE status='paid'  -- 无索引
```

#### possible_keys（可能使用的索引）

```sql
EXPLAIN SELECT * FROM orders 
WHERE user_id=? AND create_time>=?;

-- possible_keys: idx_user, idx_time, idx_user_time
-- 显示优化器考虑的所有索引
```

#### key（实际使用的索引）⭐

```sql
-- key: NULL  → ❌ 未使用索引
-- key: idx_user_time  → ✅ 使用了索引
```

#### key_len（索引使用长度）⭐

**计算方法**：

```
字段类型占用字节数 + NULL标志位(1) + 变长字段长度(2)

示例：
- INT NOT NULL: 4字节
- INT NULL: 4 + 1 = 5字节
- VARCHAR(50) NOT NULL: 50*3(utf8mb4) + 2 = 152字节
- VARCHAR(50) NULL: 50*3 + 2 + 1 = 153字节
- DATETIME NOT NULL: 5字节
- DATETIME NULL: 5 + 1 = 6字节
```

**实战分析**：

```sql
-- 索引：INDEX(user_id, status, create_time)
-- user_id: BIGINT (8字节)
-- status: TINYINT (1字节)
-- create_time: DATETIME (5字节)

-- 查询1
EXPLAIN SELECT * FROM orders WHERE user_id=?;
-- key_len: 8  → 只用了user_id

-- 查询2
EXPLAIN SELECT * FROM orders WHERE user_id=? AND status=?;
-- key_len: 9  → 用了user_id + status

-- 查询3
EXPLAIN SELECT * FROM orders WHERE user_id=? AND status=? AND create_time>=?;
-- key_len: 14  → 用了全部三列（8+1+5）
```

#### rows（预估扫描行数）⭐

```sql
EXPLAIN SELECT * FROM orders WHERE status='paid';

-- rows: 500000  → 预计扫描50万行
-- 如果实际表只有10万行，说明统计信息不准确
```

**注意**：rows是预估值，不是实际值，需结合EXPLAIN ANALYZE验证。

#### filtered（过滤百分比）

```sql
EXPLAIN SELECT * FROM orders 
WHERE user_id=12345 AND total_amount > 100;

-- rows: 1000
-- filtered: 20.00
-- 实际返回：1000 * 20% = 200行
```

#### Extra（额外信息）⭐

**好的Extra**：

```
✅ Using index: 覆盖索引，无需回表
✅ Using index condition: 索引下推
✅ Using where: WHERE过滤（正常）
```

**需要注意的Extra**：

```
⚠️ Using filesort: 需要额外排序（无法使用索引排序）
⚠️ Using temporary: 使用临时表（GROUP BY/DISTINCT/UNION）
⚠️ Using where; Using join buffer: 连接无法使用索引
❌ Using index; Using where; Using filesort: 虽有索引但排序失效
```

### 3. 完整示例分析

```sql
EXPLAIN SELECT 
    o.id, o.total_amount, u.name
FROM orders o
INNER JOIN users u ON o.user_id = u.id
WHERE o.status='paid' 
  AND o.create_time >= '2025-11-01'
ORDER BY o.create_time DESC
LIMIT 10;
```

**理想执行计划**：

```
id | select_type | table | type  | key              | key_len | rows  | Extra
---|-------------|-------|-------|------------------|---------|-------|------------------
1  | SIMPLE      | o     | range | idx_status_time  | 6       | 1000  | Using where
1  | SIMPLE      | u     | eq_ref| PRIMARY          | 8       | 1     | NULL
```

**分析**：
- orders表：使用 idx_status_time 索引，range类型，扫描1000行
- users表：主键连接，eq_ref类型（最优），每次连接只查1行
- 无Using filesort：说明排序使用了索引

**问题执行计划**：

```
id | select_type | table | type | key   | rows    | Extra
---|-------------|-------|------|-------|---------|-------------------------
1  | SIMPLE      | o     | ALL  | NULL  | 500000  | Using where; Using filesort
1  | SIMPLE      | u     | ref  | idx_u | 1       | NULL
```

**问题**：
- orders表：全表扫描（type=ALL）
- 需要额外排序（Using filesort）
- 扫描50万行（rows=500000）

## 三、EXPLAIN ANALYZE（MySQL 8.0.18+）

### 1. 基本用法

```sql
EXPLAIN ANALYZE
SELECT * FROM orders 
WHERE user_id=12345 AND status='paid';
```

### 2. 输出示例

```
-> Filter: ((orders.user_id = 12345) and (orders.status = 'paid'))
    (cost=150.25 rows=100) 
    (actual time=0.123..5.456 rows=87 loops=1)
    -> Index range scan on orders using idx_user
        (cost=50.25 rows=500)
        (actual time=0.089..4.123 rows=500 loops=1)
```

### 3. 关键信息

```
cost=150.25: 预估成本
rows=100: 预估行数
actual time=0.123..5.456: 实际执行时间（首行..末行）
rows=87: 实际返回行数
loops=1: 循环次数（JOIN时可能>1）
```

### 4. 对比分析

```sql
-- 预估 vs 实际对比

预估扫描100行 vs 实际返回87行 → 基本准确
预估扫描500行 vs 实际扫描500行 → 索引使用正确

-- 如果差异很大：
预估扫描100行 vs 实际扫描100万行 → 统计信息不准确
```

## 四、慢查询日志分析

### 1. 开启慢查询日志

```sql
-- 查看配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 开启
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;  -- 超过1秒记录
SET GLOBAL log_queries_not_using_indexes = ON;  -- 记录未使用索引的查询
```

### 2. 日志内容

```
# Time: 2025-11-02T10:15:30.123456Z
# User@Host: root[root] @ localhost []
# Query_time: 2.345678  Lock_time: 0.000123  Rows_sent: 100  Rows_examined: 500000
SET timestamp=1698926130;
SELECT * FROM orders WHERE status='paid' ORDER BY create_time DESC LIMIT 100;
```

**关键指标**：
- `Query_time`: 总执行时间
- `Lock_time`: 锁等待时间
- `Rows_sent`: 返回行数
- `Rows_examined`: 扫描行数

**问题识别**：
```
Rows_examined >> Rows_sent  → 索引使用不当或缺失
Lock_time 很高 → 锁竞争问题
Query_time 很高但Lock_time很低 → 查询本身慢
```

### 3. 分析工具

#### pt-query-digest（推荐）

```bash
# 安装
wget https://www.percona.com/downloads/percona-toolkit/...

# 分析
pt-query-digest /var/log/mysql/slow.log > report.txt

# 输出Top慢查询
# - 总执行时间
# - 执行次数
# - 平均时间
# - 查询指纹（参数化）
```

## 五、优化器追踪

### 1. 开启optimizer_trace

```sql
-- 开启追踪
SET optimizer_trace="enabled=on";

-- 执行查询
SELECT * FROM orders WHERE user_id=12345 AND status='paid';

-- 查看追踪信息
SELECT * FROM information_schema.optimizer_trace\G

-- 关闭追踪
SET optimizer_trace="enabled=off";
```

### 2. 追踪信息解读

```json
{
  "steps": [
    {
      "join_preparation": {
        "select_id": 1,
        "steps": [
          {
            "expanded_query": "SELECT * FROM orders WHERE user_id=12345 AND status='paid'"
          }
        ]
      }
    },
    {
      "join_optimization": {
        "select_id": 1,
        "steps": [
          {
            "condition_processing": {
              "condition": "WHERE",
              "original_condition": "(user_id=12345 AND status='paid')",
              "steps": [...]
            }
          },
          {
            "analyzing_range_alternatives": {
              "range_scan_alternatives": [
                {
                  "index": "idx_user",
                  "ranges": ["12345 <= user_id <= 12345"],
                  "rows": 1000,
                  "cost": 1200.5
                },
                {
                  "index": "idx_status",
                  "ranges": ["paid <= status <= paid"],
                  "rows": 50000,
                  "cost": 60000.2
                }
              ],
              "chosen_range_access_summary": {
                "range_access_plan": {
                  "chosen": true,
                  "index": "idx_user",
                  "cost": 1200.5
                }
              }
            }
          }
        ]
      }
    }
  ]
}
```

**关键信息**：
- `analyzing_range_alternatives`: 候选索引分析
- `cost`: 每个索引的成本估算
- `chosen`: 最终选择的索引

## 六、排查流程实战

### 场景1：查询突然变慢

#### Step 1：确认是否使用索引

```sql
EXPLAIN SELECT * FROM orders 
WHERE user_id=12345 AND create_time >= '2025-11-01';

-- 检查：
-- type: ALL？ → 未使用索引
-- key: NULL？ → 未使用索引
-- rows: 很大？ → 扫描行数过多
```

#### Step 2：查看可用索引

```sql
SHOW INDEX FROM orders;

-- 检查：
-- 1. 是否有合适的索引
-- 2. Cardinality 是否正常（NULL或很小→统计信息过时）
```

#### Step 3：更新统计信息

```sql
ANALYZE TABLE orders;

-- 再次EXPLAIN
EXPLAIN SELECT * FROM orders 
WHERE user_id=12345 AND create_time >= '2025-11-01';

-- 是否有改善？
```

#### Step 4：检查查询写法

```sql
-- 常见问题：
-- 1. 函数导致失效
WHERE DATE(create_time) = '2025-11-01'  -- ❌
WHERE create_time >= '2025-11-01 00:00:00' 
  AND create_time < '2025-11-02 00:00:00'  -- ✅

-- 2. 类型转换
WHERE phone = 13800138000  -- ❌ phone是VARCHAR
WHERE phone = '13800138000'  -- ✅

-- 3. OR条件
WHERE user_id=? OR merchant_id=?  -- 可能导致索引失效

-- 4. 前导通配符
WHERE name LIKE '%张三%'  -- ❌
WHERE name LIKE '张三%'  -- ✅
```

### 场景2：索引存在但不使用

#### Step 1：查看优化器选择

```sql
EXPLAIN SELECT * FROM orders WHERE status='paid';

-- possible_keys: idx_status
-- key: NULL  ← 有索引但不用

-- 原因：优化器认为全表扫描更快
```

#### Step 2：分析数据分布

```sql
-- 检查数据分布
SELECT 
    status,
    COUNT(*) AS cnt,
    COUNT(*) / (SELECT COUNT(*) FROM orders) * 100 AS pct
FROM orders
GROUP BY status;

-- 结果：
-- paid: 900万 (90%)  ← status='paid' 返回90%的数据
-- 优化器选择全表扫描是正确的（随机回表成本高）
```

#### Step 3：优化方案

```sql
-- 方案1：如果确实需要大量数据，全表扫描可能更优
-- 方案2：增加过滤条件
SELECT * FROM orders 
WHERE status='paid' AND create_time >= '2025-11-01';

-- 方案3：使用覆盖索引
SELECT id, user_id, total_amount 
FROM orders 
WHERE status='paid';
-- 创建 INDEX(status, id, user_id, total_amount)
```

### 场景3：JOIN查询索引失效

#### Step 1：EXPLAIN分析

```sql
EXPLAIN SELECT o.*, u.name
FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.status='paid';

-- 检查：
-- orders表的type和key
-- users表的type（应该是eq_ref）
-- Extra中是否有"Using join buffer"
```

#### Step 2：检查JOIN字段

```sql
-- 检查字段类型是否一致
SHOW COLUMNS FROM orders LIKE 'user_id';
SHOW COLUMNS FROM users LIKE 'id';

-- 如果类型不一致（如INT vs BIGINT），会有隐式转换
-- 解决：统一字段类型
ALTER TABLE orders MODIFY user_id BIGINT;
```

#### Step 3：检查字符集

```sql
-- 字符集不同也会导致索引失效
SHOW CREATE TABLE orders;
SHOW CREATE TABLE users;

-- 统一字符集
ALTER TABLE orders CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 七、常见索引失效原因总结

### 1. 查询写法问题

```sql
-- ❌ 索引列使用函数
WHERE DATE(create_time) = '2025-11-01'
WHERE YEAR(create_time) = 2025
WHERE UPPER(name) = 'ZHANG'

-- ❌ 索引列进行计算
WHERE age + 1 = 30
WHERE price * 0.9 > 100

-- ❌ 前导通配符
WHERE name LIKE '%张三%'
WHERE email LIKE '%@gmail.com'

-- ❌ 负向查询（部分情况）
WHERE status != 'cancelled'
WHERE status NOT IN ('cancelled', 'refunded')

-- ❌ OR条件连接不同字段
WHERE user_id=? OR merchant_id=?

-- ❌ 隐式类型转换
WHERE varchar_column = 123  -- 字符串字段用数字查询
```

### 2. 索引设计问题

```sql
-- ❌ 区分度太低
INDEX(gender)  -- 只有M/F两个值

-- ❌ 违反最左前缀
INDEX(a, b, c)
WHERE b=? AND c=?  -- 跳过了a

-- ❌ 范围查询阻断后续列
INDEX(a, b, c)
WHERE a=? AND b>? AND c=?  -- c无法使用
```

### 3. 数据分布问题

```sql
-- 过滤后数据量太大（>30%）
-- 优化器选择全表扫描
SELECT * FROM orders WHERE status='paid';  -- 90%的数据
```

### 4. 统计信息问题

```sql
-- 统计信息过时
-- 优化器基于错误信息做决策
-- 解决：ANALYZE TABLE
```

## 八、实用检查清单

### 索引失效排查清单

```
□ 1. EXPLAIN 查看执行计划
  □ type是否为ALL（全表扫描）
  □ key是否为NULL（未使用索引）
  □ rows是否异常大
  □ Extra是否有Using filesort/temporary

□ 2. 检查索引存在性
  □ SHOW INDEX FROM table_name
  □ 相关字段是否有索引

□ 3. 检查统计信息
  □ Cardinality是否为NULL或异常小
  □ 执行ANALYZE TABLE更新

□ 4. 检查查询写法
  □ 是否在索引列使用函数
  □ 是否有隐式类型转换
  □ LIKE是否前导通配符
  □ 是否使用OR连接不同字段

□ 5. 检查索引设计
  □ 是否违反最左前缀
  □ 联合索引顺序是否合理
  □ 索引区分度是否足够

□ 6. 检查数据分布
  □ 过滤后返回数据比例
  □ 是否超过30%（可能选择全表扫描）

□ 7. 使用EXPLAIN ANALYZE验证
  □ 预估行数 vs 实际行数
  □ 实际执行时间

□ 8. 查看慢查询日志
  □ Rows_examined vs Rows_sent比例
  □ Lock_time是否异常高
```

## 九、面试总结

**索引失效排查方法**：

**核心工具**：
1. **EXPLAIN**：查看执行计划，关注type、key、key_len、rows、Extra
2. **EXPLAIN ANALYZE**：查看实际执行情况（MySQL 8.0.18+）
3. **慢查询日志**：定位慢SQL，分析Rows_examined
4. **optimizer_trace**：深入了解优化器决策

**关键检查点**：
- **type字段**：ALL/index表示未有效使用索引
- **key字段**：NULL表示未使用索引
- **key_len**：判断联合索引使用了几列
- **rows**：扫描行数，过大说明索引效果差
- **Extra**：Using filesort/temporary需要优化

**常见失效原因**：
1. 索引列使用函数或计算
2. 隐式类型转换
3. 前导通配符（LIKE '%xxx'）
4. 违反最左前缀原则
5. 统计信息过时
6. 数据分布问题（过滤后数据量大）

**排查流程**：
1. EXPLAIN确认是否使用索引
2. 检查索引存在性和统计信息
3. 检查查询写法（函数、类型、通配符）
4. 分析数据分布和过滤比例
5. 使用EXPLAIN ANALYZE验证
6. 必要时使用optimizer_trace深入分析

能系统地掌握这些排查工具和方法，体现了扎实的MySQL调优能力。

