---
title: "MySQL驱动表概念及选择策略"
date: 2025-11-02
description: "详细解析MySQL多表JOIN时驱动表的概念、选择策略及其对查询性能的影响"
author: "wuxl"
categories: [数据库]
tags: [MySQL, JOIN优化, 查询优化, 执行计划, 驱动表]
nav_order: 396
parent: 数据库MySQL
---
## 问题

MySQL的驱动表是什么？MySQL怎么选的？

## 答案

### 核心概念

**驱动表（Driving Table）**：在多表JOIN操作中，**第一个被访问的表**，也称为外层表或主表。MySQL会遍历驱动表的每一行，然后根据JOIN条件在被驱动表中查找匹配的行。

**被驱动表（Driven Table）**：根据驱动表的每一行记录，通过JOIN条件去匹配数据的表，也称为内层表。

### JOIN执行过程示意

#### 嵌套循环连接（Nested-Loop Join）

```sql
SELECT * FROM table1 t1
INNER JOIN table2 t2 ON t1.id = t2.t1_id;
```

**执行逻辑**（假设table1是驱动表）：

```java
// 伪代码
for (row1 in table1) {  // 外层循环：遍历驱动表
    for (row2 in table2) {  // 内层循环：遍历被驱动表
        if (row1.id == row2.t1_id) {  // 匹配JOIN条件
            output(row1, row2);
        }
    }
}
```

**优化后**（被驱动表有索引）：

```java
for (row1 in table1) {  // 遍历驱动表
    row2 = table2.index_search(row1.id);  // 通过索引快速查找
    if (row2 != null) {
        output(row1, row2);
    }
}
```

**性能关键**：
- 驱动表决定外层循环次数
- 被驱动表的索引决定内层查找效率

### MySQL如何选择驱动表

#### 选择策略

MySQL优化器根据**成本模型**选择驱动表，主要考虑：

1. **表的大小**（记录数）
2. **WHERE条件的过滤效果**
3. **索引情况**
4. **JOIN类型**

#### 1. INNER JOIN的驱动表选择

**原则**：优先选择**小表**或**过滤后结果集小的表**作为驱动表

**示例1：根据表大小选择**

```sql
-- users: 100万行
-- orders: 10万行
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id;
```

**优化器选择**：orders作为驱动表
- 外层循环10万次（orders）
- 内层通过u.id索引查找，10万次索引查找

**如果选错**（users作为驱动表）：
- 外层循环100万次
- 内层需要100万次索引查找
- 性能差10倍

**示例2：根据WHERE过滤选择**

```sql
-- users: 100万行
-- orders: 10万行
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE u.age > 60;  -- 过滤后只有1000行
```

**优化器选择**：users作为驱动表
- WHERE条件将users过滤到1000行
- 外层循环1000次，内层1000次索引查找
- 总成本远低于以orders为驱动表（10万次循环）

#### 2. LEFT JOIN的驱动表选择

**原则**：**左表**必须作为驱动表（语义要求）

```sql
-- LEFT JOIN: 左表是驱动表
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id;
-- 驱动表：users
-- 被驱动表：orders
```

**原因**：LEFT JOIN要求返回左表的所有记录，即使右表没有匹配行也要返回（右表字段为NULL）。

**性能优化**：
```sql
-- 如果WHERE条件过滤了右表,LEFT JOIN可能被优化为INNER JOIN
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'completed';  -- 过滤了右表NULL的情况

-- 优化器可能改写为INNER JOIN,重新选择驱动表
```

#### 3. RIGHT JOIN的驱动表选择

**原则**：**右表**必须作为驱动表

```sql
SELECT * FROM users u
RIGHT JOIN orders o ON u.id = o.user_id;
-- 驱动表：orders
-- 被驱动表：users
```

**建议**：实际开发中很少用RIGHT JOIN，通常改写为LEFT JOIN：
```sql
-- 等价改写
SELECT * FROM orders o
LEFT JOIN users u ON u.id = o.user_id;
```

#### 4. 多表JOIN的驱动表选择

对于3个或更多表的JOIN：

```sql
SELECT * FROM t1
JOIN t2 ON t1.id = t2.t1_id
JOIN t3 ON t2.id = t3.t2_id
WHERE t1.status = 1;
```

**优化器选择过程**：
1. 计算每个表经过WHERE过滤后的大小
2. 选择最小的表作为驱动表
3. 依次选择下一个被驱动表，形成JOIN顺序

**可能的执行顺序**：
- t1 → t2 → t3（如果t1过滤后最小）
- t2 → t1 → t3（如果t2最小且有合适索引）

### 查看实际驱动表

#### 方法1：使用EXPLAIN

```sql
EXPLAIN SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id;
```

输出示例：
```
+----+-------+-------+------+---------+------+
| id | table | type  | key  | rows    | ...  |
+----+-------+-------+------+---------+------+
|  1 | o     | ALL   | NULL | 100000  | ...  |
|  1 | u     | eq_ref| PRIMARY | 1    | ...  |
+----+-------+-------+------+---------+------+
```

**解读**：
- 输出顺序：第一个出现的表（orders）是驱动表
- `type=ALL`：全表扫描驱动表
- `type=eq_ref`：通过主键索引在被驱动表中查找

#### 方法2：使用EXPLAIN FORMAT=TREE（MySQL 8.0+）

```sql
EXPLAIN FORMAT=TREE
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id\G
```

输出示例：
```
-> Nested loop inner join
    -> Table scan on o  (cost=10000 rows=100000)  -- 驱动表
    -> Single-row index lookup on u using PRIMARY (id=o.user_id)  -- 被驱动表
```

### 强制指定驱动表顺序

#### 方法1：使用STRAIGHT_JOIN

```sql
-- 强制按书写顺序执行JOIN
SELECT * FROM users u
STRAIGHT_JOIN orders o ON u.id = o.user_id;
-- 强制users作为驱动表
```

**注意**：STRAIGHT_JOIN会禁用优化器的JOIN顺序优化，需谨慎使用。

#### 方法2：使用Optimizer Hints（MySQL 8.0+）

```sql
-- 指定JOIN顺序
SELECT /*+ JOIN_ORDER(o, u) */ *
FROM users u
INNER JOIN orders o ON u.id = o.user_id;
-- 强制orders作为驱动表
```

### 驱动表选择对性能的影响

#### 性能对比示例

**场景**：
- users表：100万行
- orders表：10万行
- orders.user_id有索引

**方案A：小表驱动大表（正确）**
```sql
-- orders作为驱动表
成本 = 100000(扫描orders) + 100000(索引查找users) ≈ 200000
```

**方案B：大表驱动小表（错误）**
```sql
-- users作为驱动表
成本 = 1000000(扫描users) + 1000000(索引查找orders) ≈ 2000000
```

**性能差距**：10倍

#### 索引的关键作用

**被驱动表必须有索引**，否则每次内层循环都是全表扫描：

```sql
-- 假设orders.user_id没有索引
成本 = 100000(扫描orders) + 100000 × 100000(全表扫描users)
     = 10000000000（100亿次操作！）
```

### 驱动表选择的最佳实践

#### 1. 确保被驱动表有索引

```sql
-- JOIN条件的列必须有索引
CREATE INDEX idx_user_id ON orders(user_id);

SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id;
-- orders.user_id有索引,可以快速查找
```

#### 2. 优先过滤驱动表

```sql
-- 在驱动表上应用WHERE条件
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE u.age > 60  -- 减少驱动表记录数
  AND u.status = 1;
```

#### 3. 使用覆盖索引优化被驱动表

```sql
-- 创建覆盖索引
CREATE INDEX idx_user_id_status ON orders(user_id, status, amount);

-- 查询可以直接从索引获取数据
SELECT u.name, o.status, o.amount
FROM users u
INNER JOIN orders o ON u.id = o.user_id;
```

#### 4. 监控执行计划

```sql
-- 定期检查EXPLAIN结果
EXPLAIN SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id;

-- 关注：
-- - 驱动表的rows（越小越好）
-- - 被驱动表的type（eq_ref、ref最优）
-- - 是否使用了索引
```

### 常见误区

**误区1**："永远用小表驱动大表"

**正确理解**：应该用**过滤后记录数少的表**作为驱动表。

```sql
-- users: 100万行, WHERE过滤后1000行
-- orders: 10万行, 无过滤
SELECT * FROM users u
INNER JOIN orders o ON u.id = o.user_id
WHERE u.vip_level = 5;  -- 只有1000个VIP用户

-- 正确：users作为驱动表（1000行）
-- 错误：orders作为驱动表（10万行）
```

**误区2**："LEFT JOIN左表一定是驱动表，性能一定差"

**正确理解**：如果WHERE过滤了右表，优化器可能改写为INNER JOIN。

```sql
-- 表面是LEFT JOIN
SELECT * FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.status = 'completed';  -- 过滤了右表NULL

-- 优化器改写为INNER JOIN,可能选择orders为驱动表
```

### 面试总结

**简洁版回答**：

**驱动表**：多表JOIN时第一个被访问的表，决定外层循环次数。

**MySQL选择驱动表的策略**：
1. **INNER JOIN**：选择过滤后记录数最少的表（通常是小表）
2. **LEFT JOIN**：左表必须是驱动表
3. **RIGHT JOIN**：右表必须是驱动表
4. **考虑因素**：表大小、WHERE过滤效果、索引情况

**关键原则**：
- **小表驱动大表**（准确说是：过滤后小的表驱动大表）
- **被驱动表的JOIN列必须有索引**
- 驱动表选择不当，性能可能相差数十倍

**查看方式**：`EXPLAIN`查看table列顺序，第一个是驱动表。
