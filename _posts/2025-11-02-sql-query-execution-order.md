---
layout: post
title: "SQL查询语句的执行顺序"
date: 2025-11-02
description: "深入理解SQL查询语句各子句的逻辑执行顺序及其对查询优化的影响"
author: "wuxl"
categories: [数据库]
tags: [MySQL, SQL执行, 查询优化, SQL语法]
---

## 问题

一个查询语句的执行顺序是怎么样的?

## 答案

### 核心概念

SQL查询语句的**书写顺序**和**执行顺序**是不同的。理解执行顺序有助于编写高效的SQL语句和理解查询优化的原理。

### SQL标准执行顺序

```sql
SELECT DISTINCT column, AGG_FUNC(column)
FROM table1
JOIN table2 ON table1.id = table2.id
WHERE condition
GROUP BY column
HAVING group_condition
ORDER BY column
LIMIT offset, count;
```

**逻辑执行顺序**（从1到8）：

```
(1) FROM        -- 确定数据来源
(2) ON          -- 多表连接的关联条件
(3) JOIN        -- 执行表连接操作
(4) WHERE       -- 过滤行数据
(5) GROUP BY    -- 分组
(6) HAVING      -- 过滤分组后的数据
(7) SELECT      -- 选择列
(8) DISTINCT    -- 去重
(9) ORDER BY    -- 排序
(10) LIMIT      -- 限制返回行数
```

### 详细执行过程

#### 1. FROM阶段

**作用**：确定数据来源表，计算笛卡尔积（如果有多表）

```sql
FROM table1, table2
-- 生成table1和table2的笛卡尔积
```

**性能提示**：尽量减少FROM子句中的表数量，大表应通过索引优化。

#### 2. ON阶段

**作用**：对FROM阶段生成的结果集应用ON条件过滤

```sql
FROM table1 JOIN table2 ON table1.id = table2.id
-- 只保留满足ON条件的行
```

#### 3. JOIN阶段

**作用**：执行JOIN操作（LEFT JOIN会在此阶段添加外部行）

- **INNER JOIN**：仅保留匹配的行
- **LEFT JOIN**：保留左表所有行，右表不匹配则填NULL
- **RIGHT JOIN**：保留右表所有行，左表不匹配则填NULL

#### 4. WHERE阶段

**作用**：对JOIN后的结果集进行行级过滤

```sql
WHERE status = 1 AND age > 18
```

**重要特性**：
- WHERE子句**无法使用列别名**（因为SELECT还未执行）
- WHERE在GROUP BY之前执行，所以不能使用聚合函数

```sql
-- 错误示例
SELECT name AS user_name FROM user WHERE user_name = 'Tom';  -- 错误！
SELECT COUNT(*) FROM user WHERE COUNT(*) > 10;                -- 错误！
```

#### 5. GROUP BY阶段

**作用**：按指定列分组，将数据聚合成组

```sql
GROUP BY department_id
-- 将数据按部门ID分组
```

**执行后**：生成的结果集每组只有一行数据。

#### 6. HAVING阶段

**作用**：对分组后的结果进行过滤（可以使用聚合函数）

```sql
HAVING COUNT(*) > 10
-- 过滤掉成员数量小于等于10的分组
```

**WHERE vs HAVING**：
- **WHERE**：过滤行，在分组前执行，不能用聚合函数
- **HAVING**：过滤组，在分组后执行，可以用聚合函数

```sql
-- 正确示例
SELECT department_id, COUNT(*) as cnt
FROM employee
WHERE salary > 5000           -- 先过滤薪资>5000的员工
GROUP BY department_id        -- 再按部门分组
HAVING COUNT(*) > 10;         -- 最后过滤人数>10的部门
```

#### 7. SELECT阶段

**作用**：选择要返回的列，计算表达式，生成列别名

```sql
SELECT id, name, age * 2 AS double_age
```

**重要**：此阶段才会生成别名，所以WHERE和GROUP BY不能使用SELECT中的别名。

#### 8. DISTINCT阶段

**作用**：对SELECT结果集去重

```sql
SELECT DISTINCT department_id FROM employee;
```

**性能提示**：DISTINCT操作成本较高，能用GROUP BY替代时尽量替代。

#### 9. ORDER BY阶段

**作用**：对结果集排序

```sql
ORDER BY age DESC, create_time ASC
```

**特性**：ORDER BY可以使用SELECT中的别名（因为SELECT已执行）

```sql
SELECT name AS user_name FROM user ORDER BY user_name;  -- 正确
```

#### 10. LIMIT阶段

**作用**：限制返回的行数

```sql
LIMIT 10 OFFSET 20  -- 跳过20行，返回10行
-- 或简写为
LIMIT 20, 10
```

### 完整示例

```sql
SELECT
    d.name AS dept_name,
    COUNT(*) AS emp_count,
    AVG(e.salary) AS avg_salary
FROM
    employee e
INNER JOIN
    department d ON e.dept_id = d.id
WHERE
    e.status = 1                    -- (4) 过滤在职员工
    AND e.salary > 5000             -- (4) 过滤薪资>5000
GROUP BY
    d.id, d.name                    -- (5) 按部门分组
HAVING
    COUNT(*) > 10                   -- (6) 过滤人数>10的部门
ORDER BY
    avg_salary DESC                 -- (9) 按平均薪资降序
LIMIT 10;                           -- (10) 只返回前10个部门
```

**执行顺序解析**：
1. FROM employee e → 获取员工表
2. JOIN department d ON ... → 关联部门表
3. WHERE status=1 AND salary>5000 → 过滤数据
4. GROUP BY d.id, d.name → 按部门分组
5. HAVING COUNT(*)>10 → 过滤小部门
6. SELECT dept_name, COUNT(*), AVG(salary) → 选择列
7. ORDER BY avg_salary DESC → 排序
8. LIMIT 10 → 取前10条

### 对查询优化的启示

1. **WHERE优先于HAVING**：能在WHERE过滤的数据不要放到HAVING，减少分组计算量
2. **减少JOIN前的数据量**：在JOIN前通过WHERE过滤，减少笛卡尔积规模
3. **索引优化**：WHERE、JOIN、ORDER BY涉及的列应考虑建立索引
4. **避免SELECT ***：只查询需要的列，减少数据传输和内存占用
5. **LIMIT提前终止**：ORDER BY配合LIMIT时，MySQL可能使用优先队列优化，不需要排序全部数据

### 面试总结

**简洁版回答**：
SQL执行顺序为：**FROM → JOIN → WHERE → GROUP BY → HAVING → SELECT → DISTINCT → ORDER BY → LIMIT**

**关键点**：
- WHERE在GROUP BY之前，不能用聚合函数
- HAVING在GROUP BY之后，可以用聚合函数
- SELECT在WHERE之后，所以WHERE不能用列别名
- ORDER BY在SELECT之后，可以用列别名

理解执行顺序有助于写出更高效的SQL和避免语法错误。
