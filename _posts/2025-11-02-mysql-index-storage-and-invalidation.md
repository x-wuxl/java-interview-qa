---
layout: post
title: "MySQL索引存储与失效场景详解"
date: 2025-11-02
description: "深入解析MySQL索引的存储结构(B+树)、聚簇索引与非聚簇索引的区别,以及索引失效的常见场景与解决方案"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 索引, B+树, 聚簇索引, 索引失效, 性能优化]
---

## 问题

MySQL索引存储？索引的失效场景

## 答案

## 一、MySQL索引存储

### 1. 索引存储结构：B+树

#### 为什么选择B+树？

**与其他数据结构对比**：

| 数据结构 | 查询复杂度 | 缺点 | 是否适合 |
|---------|-----------|------|---------|
| 数组 | O(n) | 查询慢 | ❌ |
| 哈希表 | O(1) | 不支持范围查询 | ❌ |
| 二叉搜索树 | O(log n) | 树高过高，IO次数多 | ❌ |
| 红黑树 | O(log n) | 树高过高，IO次数多 | ❌ |
| B树 | O(log n) | 非叶子节点存数据，范围查询慢 | ⚠️ |
| **B+树** | O(log n) | **叶子节点存数据，支持范围查询，IO少** | ✅ |

#### B+树的关键特性

**结构特点**：
1. **非叶子节点只存索引键**，不存数据
2. **所有数据都在叶子节点**
3. **叶子节点通过指针连接**，形成有序链表

**优势**：
- **IO次数少**：树高通常3-4层，最多3-4次IO就能定位数据
- **范围查询高效**：叶子节点是有序链表，顺序扫描即可
- **查询稳定**：所有查询都到达叶子节点，复杂度稳定

**示例**：假设索引键是INT（4字节），数据页16KB

```
非叶子节点可存储的键数量 ≈ 16KB / 4B = 4000个
3层B+树可以存储：4000 × 4000 × 16 ≈ 2.56亿条记录
```

### 2. 聚簇索引（Clustered Index）

#### 定义

**聚簇索引**：索引的叶子节点存储的是**完整的行数据**。

**InnoDB的主键索引就是聚簇索引。**

#### 结构示意

```
           [10, 20, 30]          -- 非叶子节点（只存主键值）
          /      |      \
    [1,5,9]  [11,15,19]  [21,25,29]  -- 非叶子节点
     /  |  \
[完整行1] [完整行5] [完整行9]  -- 叶子节点（存储完整数据）
    ↔        ↔        ↔         -- 双向链表
```

#### 特点

**优点**：
- **查询快**：主键查询一次索引树遍历即可获得完整数据
- **范围查询高效**：叶子节点是有序链表，顺序扫描即可

**缺点**：
- **插入慢**：需要维护数据的物理顺序，可能导致页分裂
- **占用空间大**：叶子节点存储完整数据

**InnoDB的规则**：
- 如果定义了主键，主键索引就是聚簇索引
- 如果没有主键，选择第一个非空唯一索引作为聚簇索引
- 如果都没有，InnoDB会创建隐藏的`row_id`作为聚簇索引

### 3. 非聚簇索引（Secondary Index / 二级索引）

#### 定义

**非聚簇索引**：索引的叶子节点存储的是**主键值**，而不是完整数据。

**InnoDB的所有非主键索引都是非聚簇索引。**

#### 结构示意

```
-- 假设在name列上建立索引
           ['Jack', 'Tom', 'Zoe']    -- 非叶子节点
          /         |         \
    ['Alice', 'Bob']  ['Jack', 'Lucy']  ['Tom', 'Zoe']
         |               |                  |
      [主键1]          [主键5]            [主键10]  -- 叶子节点（存主键值）
```

#### 回表查询

**流程**：
1. 在非聚簇索引树中查找，得到主键值
2. 拿着主键值到聚簇索引树中查找完整数据

```sql
-- 假设name有索引
SELECT * FROM users WHERE name = 'Tom';

-- 执行过程：
-- 1. 在name索引树中查找'Tom'，得到主键id=10
-- 2. 在主键索引树中查找id=10，得到完整行数据
```

**性能影响**：回表需要额外的IO，如果回表次数多，性能显著下降。

### 4. 覆盖索引（Covering Index）

#### 定义

**覆盖索引**：查询的所有列都在索引中，无需回表。

```sql
-- 创建联合索引
CREATE INDEX idx_name_age ON users(name, age);

-- 覆盖索引（只查询索引列）
SELECT name, age FROM users WHERE name = 'Tom';
-- Extra: Using index（说明使用了覆盖索引）

-- 非覆盖索引（查询了索引外的列）
SELECT * FROM users WHERE name = 'Tom';
-- 需要回表获取其他列
```

**优势**：
- **避免回表**，减少IO
- **性能大幅提升**（可能快10倍以上）

### 5. MyISAM的索引存储

**MyISAM使用的是非聚簇索引**：

- **主键索引和非主键索引结构相同**
- 索引的叶子节点存储的是**数据文件的地址**（指针）
- 数据和索引分别存储在不同文件中（.MYD和.MYI）

```
-- MyISAM索引结构
           [10, 20, 30]
          /      |      \
    [1,5,9]  [11,15,19]  [21,25,29]
     /  |  \
[地址A] [地址B] [地址C]  -- 叶子节点存储数据文件地址
```

## 二、索引失效场景

### 1. 使用函数或表达式

#### 场景：在索引列上使用函数

```sql
-- 索引失效
SELECT * FROM users WHERE YEAR(create_time) = 2024;
SELECT * FROM users WHERE UPPER(name) = 'TOM';
SELECT * FROM users WHERE age + 1 = 26;
```

**原因**：索引存储的是原始值，函数计算后的值无法利用索引。

**解决方案**：
```sql
-- 正确写法1：范围查询
SELECT * FROM users
WHERE create_time >= '2024-01-01'
  AND create_time < '2025-01-01';

-- 正确写法2：函数索引（MySQL 8.0+）
CREATE INDEX idx_year ON users((YEAR(create_time)));
```

### 2. 隐式类型转换

#### 场景：字符串和数字比较

```sql
-- 假设phone是VARCHAR类型
CREATE INDEX idx_phone ON users(phone);

-- 索引失效
SELECT * FROM users WHERE phone = 123456;

-- 原因：MySQL会将字符串转为数字，相当于
SELECT * FROM users WHERE CAST(phone AS SIGNED) = 123456;
```

**规则**：
- 字符串列 = 数字 → 索引失效（字符串会被转换）
- 数字列 = 字符串 → 索引有效（字符串会被转换为数字，列本身不变）

**解决方案**：
```sql
-- 正确写法
SELECT * FROM users WHERE phone = '123456';
```

### 3. 前导模糊查询

#### 场景：LIKE以%开头

```sql
-- 索引失效
SELECT * FROM users WHERE name LIKE '%Tom%';
SELECT * FROM users WHERE name LIKE '%Tom';

-- 索引有效
SELECT * FROM users WHERE name LIKE 'Tom%';
```

**原因**：B+树索引是有序的，只能支持前缀匹配，无法支持后缀或中间匹配。

**解决方案**：
```sql
-- 方案1：改为前缀匹配
WHERE name LIKE 'Tom%'

-- 方案2：使用全文索引（适合文本搜索）
CREATE FULLTEXT INDEX idx_name_fulltext ON users(name);
SELECT * FROM users WHERE MATCH(name) AGAINST('Tom');

-- 方案3：使用Elasticsearch等搜索引擎
```

### 4. 联合索引不遵循最左前缀

#### 场景：跳过联合索引的最左列

```sql
CREATE INDEX idx_abc ON users(a, b, c);

-- 索引失效
SELECT * FROM users WHERE b = 2 AND c = 3;
SELECT * FROM users WHERE c = 3;

-- 索引有效
SELECT * FROM users WHERE a = 1;
SELECT * FROM users WHERE a = 1 AND b = 2;
SELECT * FROM users WHERE a = 1 AND b = 2 AND c = 3;
```

**原因**：联合索引按照(a, b, c)顺序建立B+树，必须从a开始匹配。

**解决方案**：
```sql
-- 方案1：调整索引顺序（根据查询需求）
CREATE INDEX idx_bca ON users(b, c, a);

-- 方案2：创建单独索引
CREATE INDEX idx_b ON users(b);
CREATE INDEX idx_c ON users(c);
```

### 5. 范围查询后的列无法使用索引

#### 场景：范围查询中断索引使用

```sql
CREATE INDEX idx_abc ON users(a, b, c);

-- b是范围查询，c无法使用索引
SELECT * FROM users WHERE a = 1 AND b > 10 AND c = 3;
-- 索引使用：a, b（c用不上）
```

**原因**：范围查询后，索引的有序性被破坏。

**解决方案**：
```sql
-- 调整索引顺序（等值查询在前）
CREATE INDEX idx_acb ON users(a, c, b);
-- WHERE a = 1 AND c = 3 AND b > 10
-- 索引使用：a, c, b（完整）
```

### 6. 使用OR导致索引失效

#### 场景：OR连接的条件中有列没有索引

```sql
CREATE INDEX idx_age ON users(age);

-- 索引失效（name没有索引）
SELECT * FROM users WHERE age = 25 OR name = 'Tom';
```

**原因**：如果name没有索引，MySQL可能选择全表扫描（因为OR的一侧无法使用索引）。

**解决方案**：
```sql
-- 方案1：为name创建索引
CREATE INDEX idx_name ON users(name);
-- MySQL会使用索引合并（Index Merge）

-- 方案2：改写为UNION
SELECT * FROM users WHERE age = 25
UNION
SELECT * FROM users WHERE name = 'Tom';
```

### 7. 不等于操作符

#### 场景：使用!= 或 <>

```sql
-- 可能导致索引失效
SELECT * FROM users WHERE age != 25;
SELECT * FROM users WHERE age <> 25;
```

**原因**：不等于操作符可能导致优化器认为扫描范围过大，选择全表扫描。

**是否失效取决于**：
- 数据分布（如果!=的范围很小，可能使用索引）
- 表大小
- MySQL版本和优化器配置

**解决方案**：
```sql
-- 改写为范围查询
SELECT * FROM users WHERE age < 25 OR age > 25;

-- 或拆分为两个查询
SELECT * FROM users WHERE age < 25
UNION ALL
SELECT * FROM users WHERE age > 25;
```

### 8. IS NULL / IS NOT NULL

#### 场景：判断NULL值

```sql
-- 可能导致索引失效
SELECT * FROM users WHERE email IS NULL;
SELECT * FROM users WHERE email IS NOT NULL;
```

**规则**（与数据分布有关）：
- **IS NULL**：如果NULL值很少，可能使用索引
- **IS NOT NULL**：如果NULL值很多，可能全表扫描

**解决方案**：
```sql
-- 避免NULL值，使用默认值
ALTER TABLE users MODIFY email VARCHAR(100) NOT NULL DEFAULT '';

-- 或使用特殊值代替NULL
WHERE email != '' AND email IS NOT NULL
```

### 9. 使用NOT IN / NOT EXISTS

#### 场景：NOT IN子查询

```sql
-- 通常导致索引失效
SELECT * FROM users WHERE id NOT IN (SELECT user_id FROM orders);
```

**原因**：NOT IN的执行效率很低，MySQL通常选择全表扫描。

**解决方案**：
```sql
-- 改写为LEFT JOIN
SELECT u.* FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.user_id IS NULL;

-- 或使用NOT EXISTS
SELECT * FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id = u.id
);
```

### 10. 数据量过小

#### 场景：表数据量很少

```sql
-- 表只有100行数据
SELECT * FROM small_table WHERE id = 10;
```

**原因**：当数据量很小时，全表扫描比索引查询更快（索引需要额外的IO）。

**优化器选择**：自动选择全表扫描。

**无需优化**：这是正常的优化器行为。

### 索引失效总结表

| 场景 | 示例 | 是否失效 | 解决方案 |
|------|------|---------|---------|
| 函数计算 | `WHERE YEAR(time)=2024` | ✅ | 改写为范围查询 |
| 隐式转换 | `WHERE varchar_col = 123` | ✅ | 使用正确类型 |
| 前导模糊 | `WHERE name LIKE '%Tom'` | ✅ | 改为`'Tom%'`或全文索引 |
| 跳过最左列 | `WHERE b=2`（索引是a,b,c） | ✅ | 调整索引或查询 |
| 范围中断 | `WHERE a=1 AND b>10 AND c=3` | ⚠️ | c失效，调整列顺序 |
| OR无索引 | `WHERE indexed_col=1 OR no_index_col=2` | ✅ | 为另一列创建索引 |
| 不等于 | `WHERE age != 25` | ⚠️ | 取决于数据分布 |
| IS NOT NULL | `WHERE col IS NOT NULL` | ⚠️ | 避免NULL值 |
| NOT IN | `WHERE id NOT IN (...)` | ✅ | 改写为LEFT JOIN |

### 诊断方法

```sql
-- 使用EXPLAIN查看是否使用索引
EXPLAIN SELECT * FROM users WHERE ...;

-- 关键字段：
-- type: ALL表示全表扫描（索引失效）
-- possible_keys: 可能使用的索引
-- key: 实际使用的索引（NULL表示未使用）
-- rows: 扫描行数（越少越好）
-- Extra: Using index（覆盖索引），Using where（需要过滤）

-- 使用SHOW WARNINGS查看优化后的SQL
EXPLAIN ...;
SHOW WARNINGS;
```

### 面试总结

**简洁版回答**：

**MySQL索引存储**：
- **InnoDB使用B+树**：所有数据在叶子节点，支持范围查询，IO少（3-4层）
- **聚簇索引**：主键索引，叶子节点存完整数据
- **非聚簇索引**：二级索引，叶子节点存主键值，需要回表
- **覆盖索引**：查询列都在索引中，避免回表，性能最优

**索引失效场景**（重点）：
1. **函数计算**：`WHERE YEAR(time)=2024`
2. **隐式转换**：字符串列与数字比较
3. **前导模糊**：`LIKE '%xxx'`
4. **违反最左前缀**：联合索引跳过最左列
5. **范围查询**：中断后续列的索引使用
6. **OR无索引**：OR的一侧无索引
7. **不等于/IS NOT NULL**：可能全表扫描

**优化原则**：避免在索引列上做计算、使用正确类型、遵循最左前缀、用EXPLAIN验证。
