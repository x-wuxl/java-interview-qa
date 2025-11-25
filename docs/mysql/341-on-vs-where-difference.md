---
layout: default
title: "ON和WHERE的区别详解"
parent: 数据库MySQL
nav_order: 341
description: "深入解析SQL中ON和WHERE子句的执行时机、作用范围及其对查询结果的影响"
author: "wuxl"
date: 2025-11-02
---
## 问题

on和where有什么区别？

## 答案

### 核心概念

`ON`和`WHERE`都是SQL中的过滤条件，但它们的**作用阶段**和**影响范围**完全不同：

- **ON**：用于JOIN操作，在**生成临时表**时过滤
- **WHERE**：在**临时表生成后**过滤最终结果集

理解这一区别，尤其在使用**LEFT/RIGHT JOIN**时至关重要。

### 执行顺序差异

#### SQL执行顺序回顾

```
FROM → ON → JOIN → WHERE → GROUP BY → HAVING → SELECT → ORDER BY
```

**关键点**：
- **ON**：在第2步执行（JOIN过程中）
- **WHERE**：在第4步执行（JOIN完成后）

### INNER JOIN场景：差异不明显

#### 示例1：条件放在ON中

```sql
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id AND o.status = 'paid';
```

**执行过程**：
1. 扫描users表
2. 对每个user，在orders中查找满足`u.id = o.user_id AND o.status = 'paid'`的记录
3. 返回匹配的结果

#### 示例2：条件放在WHERE中

```sql
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';
```

**执行过程**：
1. 扫描users表
2. 对每个user，在orders中查找满足`u.id = o.user_id`的记录
3. 过滤结果集，只保留`o.status = 'paid'`的记录

**结论**：对于INNER JOIN，两种写法**结果相同**，优化器通常会生成相同的执行计划。

**推荐**：将非关联条件放在WHERE中，可读性更好。

```sql
-- 推荐写法
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id  -- ON只放关联条件
WHERE o.status = 'paid'                  -- WHERE放过滤条件
  AND u.age > 18;
```

### LEFT JOIN场景：差异显著

#### 测试数据

```sql
-- users表
+----+-------+
| id | name  |
+----+-------+
| 1  | Alice |
| 2  | Bob   |
| 3  | Carol |
+----+-------+

-- orders表
+----+---------+--------+
| id | user_id | status |
+----+---------+--------+
| 1  | 1       | paid   |
| 2  | 1       | pending|
| 3  | 2       | paid   |
+----+---------+--------+
```

#### 示例1：条件放在ON中

```sql
SELECT u.*, o.*
FROM users u
LEFT JOIN orders o ON u.id = o.user_id AND o.status = 'paid';
```

**执行逻辑**：
1. 遍历users表（驱动表）
2. 对每个user，在orders中查找满足`u.id = o.user_id AND o.status = 'paid'`的记录
3. **即使没有匹配**（或status不是paid），**也保留左表记录**，右表字段填NULL

**结果**：
```
+----+-------+------+---------+--------+
| id | name  | id   | user_id | status |
+----+-------+------+---------+--------+
| 1  | Alice | 1    | 1       | paid   |  -- 匹配到paid订单
| 1  | Alice | NULL | NULL    | NULL   |  -- pending订单不满足ON条件,但Alice仍保留
| 2  | Bob   | 3    | 2       | paid   |  -- 匹配到paid订单
| 3  | Carol | NULL | NULL    | NULL   |  -- 没有订单,保留
+----+-------+------+---------+--------+
```

**注意**：Alice有2条记录（1条匹配paid，1条因为pending不匹配而填NULL）

**实际结果（MySQL优化后）**：
```
+----+-------+------+---------+--------+
| id | name  | id   | user_id | status |
+----+-------+------+---------+--------+
| 1  | Alice | 1    | 1       | paid   |
| 2  | Bob   | 3    | 2       | paid   |
| 3  | Carol | NULL | NULL    | NULL   |
+----+-------+------+---------+--------+
```
（Alice只有1条paid记录，因为ON同时过滤了关联和状态）

#### 示例2：条件放在WHERE中

```sql
SELECT u.*, o.*
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';
```

**执行逻辑**：
1. 遍历users表
2. 对每个user，在orders中查找满足`u.id = o.user_id`的记录（匹配所有订单）
3. 生成临时结果集（包含所有users和匹配的orders，未匹配的orders字段为NULL）
4. **WHERE过滤**：只保留`o.status = 'paid'`的记录

**临时结果集（JOIN后）**：
```
+----+-------+------+---------+---------+
| id | name  | id   | user_id | status  |
+----+-------+------+---------+---------+
| 1  | Alice | 1    | 1       | paid    |
| 1  | Alice | 2    | 1       | pending |
| 2  | Bob   | 3    | 2       | paid    |
| 3  | Carol | NULL | NULL    | NULL    |  -- Carol没有订单
+----+-------+------+---------+---------+
```

**WHERE过滤后最终结果**：
```
+----+-------+----+---------+--------+
| id | name  | id | user_id | status |
+----+-------+----+---------+--------+
| 1  | Alice | 1  | 1       | paid   |
| 2  | Bob   | 3  | 2       | paid   |
+----+-------+----+---------+--------+
```

**关键差异**：
- Carol被过滤掉了！（因为`o.status = 'paid'`，但Carol的o.status是NULL）
- **LEFT JOIN的语义被破坏**：原本应该保留所有左表记录

#### 对比总结

| 写法 | Carol是否保留 | Alice记录数 | 语义 |
|------|--------------|------------|------|
| `LEFT JOIN ... ON ... AND o.status='paid'` | **保留**（o.*为NULL） | 1条 | 保留所有用户，只关联paid订单 |
| `LEFT JOIN ... WHERE o.status='paid'` | **过滤掉** | 1条 | **等价于INNER JOIN** |

### 关键规律

#### 规律1：LEFT JOIN + WHERE右表条件 = INNER JOIN

```sql
-- 这两个查询等价
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';

SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';
```

**原因**：WHERE过滤掉了右表为NULL的记录（即左表未匹配的记录），失去了LEFT JOIN的意义。

#### 规律2：WHERE左表条件不影响LEFT JOIN语义

```sql
-- 仍然是LEFT JOIN
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.age > 18;  -- 过滤左表，不影响JOIN语义
```

**结果**：先过滤users（age>18），然后LEFT JOIN orders，保留所有年龄>18的用户。

#### 规律3：ON中的非关联条件影响匹配结果

```sql
-- ON中添加额外条件
LEFT JOIN orders o ON u.id = o.user_id AND o.amount > 100
```

**效果**：只关联`amount > 100`的订单，其他订单视为不匹配，右表字段填NULL。

### 实际应用场景

#### 场景1：查询所有用户及其已支付订单

**需求**：返回所有用户，如果有已支付订单则显示，没有则显示NULL

```sql
-- 正确写法
SELECT u.name, o.order_no
FROM users u
LEFT JOIN orders o ON u.id = o.user_id AND o.status = 'paid';
```

**错误写法**：
```sql
-- 错误！会过滤掉没有已支付订单的用户
SELECT u.name, o.order_no
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';
```

#### 场景2：查询有已支付订单的用户

**需求**：只返回至少有1个已支付订单的用户

```sql
-- 正确写法（方案1）
SELECT u.name, o.order_no
FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';

-- 正确写法（方案2）
SELECT u.name, o.order_no
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';  -- 此时WHERE的过滤效果正是我们需要的
```

#### 场景3：查询所有用户及其订单数量（包括0订单的用户）

```sql
-- 正确写法
SELECT u.name, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name;
```

**结果**：
```
+-------+-------------+
| name  | order_count |
+-------+-------------+
| Alice | 2           |
| Bob   | 1           |
| Carol | 0           |  -- COUNT(o.id)不计NULL,所以是0
+-------+-------------+
```

**错误写法**：
```sql
-- 错误：WHERE o.id IS NOT NULL会过滤掉Carol
SELECT u.name, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.id IS NOT NULL
GROUP BY u.id, u.name;
```

### 性能对比

#### INNER JOIN：性能无明显差异

```sql
-- 方案A：条件在ON中
EXPLAIN SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id AND o.status = 'paid';

-- 方案B：条件在WHERE中
EXPLAIN SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';
```

**结论**：优化器通常生成相同的执行计划，性能一致。

#### LEFT JOIN：性能可能有差异

```sql
-- 方案A：ON中过滤（推荐）
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id AND o.status = 'paid';

-- 方案B：WHERE中过滤
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';
```

**性能影响**：
- **方案A**：JOIN时直接过滤，减少中间结果集（如果orders.status有索引）
- **方案B**：先生成完整JOIN结果，再过滤，中间结果集更大

**建议**：将过滤条件尽量放在ON中，减少JOIN的数据量。

### 最佳实践

#### 1. INNER JOIN：建议条件分离

```sql
-- 推荐：关联条件在ON，过滤条件在WHERE
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid'
  AND u.age > 18;
```

**优点**：
- 可读性好：一眼看出哪个是关联条件，哪个是过滤条件
- 符合SQL执行逻辑

#### 2. LEFT JOIN：根据需求选择

**需求：保留左表所有记录**
```sql
-- 右表过滤条件放在ON中
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id AND o.status = 'paid';
```

**需求：只要有匹配就行**
```sql
-- 右表过滤条件放在WHERE中（实际等价于INNER JOIN）
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'paid';  -- 不保留未匹配的左表记录
```

**需求：左表先过滤**
```sql
-- 左表条件放在WHERE中
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.age > 18;  -- 先过滤users，再LEFT JOIN
```

#### 3. 复杂条件组合

```sql
-- 标准写法
SELECT u.name, o.order_no
FROM users u
LEFT JOIN orders o
    ON u.id = o.user_id           -- 关联条件
    AND o.status = 'paid'         -- 右表过滤（保留左表）
    AND o.amount > 100            -- 右表过滤（保留左表）
WHERE u.age > 18                  -- 左表过滤
  AND u.status = 'active';        -- 左表过滤
```

### 常见错误

#### 错误1：LEFT JOIN中WHERE过滤右表

```sql
-- 错误：失去LEFT JOIN意义
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.create_time > '2024-01-01';  -- 会过滤掉没有订单的用户
```

**修正**：
```sql
-- 方案1：改为INNER JOIN
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE o.create_time > '2024-01-01';

-- 方案2：保留LEFT JOIN语义
SELECT * FROM users u
LEFT JOIN orders o
    ON u.id = o.user_id
    AND o.create_time > '2024-01-01';  -- 条件移到ON中
```

#### 错误2：ON中使用OR导致笛卡尔积

```sql
-- 危险：可能产生意外结果
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id OR u.name = o.receiver_name;
```

**问题**：OR条件可能导致一个user匹配多个order，结果集膨胀。

### 面试总结

**简洁版回答**：

**ON vs WHERE的核心区别**：

1. **执行时机**：
   - ON：JOIN时执行（临时表生成阶段）
   - WHERE：JOIN后执行（过滤最终结果）

2. **INNER JOIN**：
   - 两者效果相同，优化器会优化
   - 建议：关联条件在ON，过滤条件在WHERE（可读性好）

3. **LEFT JOIN**：
   - ON：右表过滤条件不影响左表记录（未匹配的左表记录保留，右表字段为NULL）
   - WHERE：右表过滤条件会过滤掉未匹配的左表记录（**等价于INNER JOIN**）

**关键原则**：
- LEFT JOIN要保留左表所有记录时，右表过滤条件必须放在ON中
- WHERE中对右表的过滤会破坏LEFT JOIN语义

**记忆口诀**：ON定关联，WHERE筛结果；LEFT JOIN右表滤ON上，WHERE上就变INNER状。
