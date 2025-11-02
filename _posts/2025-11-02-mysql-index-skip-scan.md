---
layout: post
title: "什么是索引跳跃扫描？"
date: 2025-11-02
categories: [MySQL, 索引优化]
tags: [MySQL, 索引跳跃扫描, Index Skip Scan, 索引优化, MySQL 8.0]
description: "深入解析MySQL 8.0引入的索引跳跃扫描（Index Skip Scan）特性，包括工作原理、触发条件和实际应用场景。"
---

## 一、核心概念

**索引跳跃扫描（Index Skip Scan）** 是MySQL 8.0.13版本引入的优化技术，允许在某些特定条件下**跳过联合索引的最左列**，直接使用后续列进行查询。

**打破常规**：
```sql
-- 索引：INDEX(gender, age, city)
-- 传统：必须先用gender（最左前缀原则）
-- 跳跃扫描：可以跳过gender，直接用age
SELECT * FROM users WHERE age=25;
```

**关键点**：
- MySQL 8.0.13+ 特性
- 仅在特定条件下生效
- 本质是一种启发式优化

## 二、工作原理

### 1. 传统方式 vs 跳跃扫描

#### 场景设定
```sql
-- 表结构
CREATE TABLE users (
    id INT,
    gender ENUM('M', 'F'),  -- 只有2个值
    age INT,
    city VARCHAR(50),
    INDEX idx_gac(gender, age, city)
);

-- 查询
SELECT * FROM users WHERE age=25 AND city='Beijing';
```

#### 传统执行方式（MySQL 5.7及以下）

```
问题：跳过了最左列gender，索引无法使用
结果：全表扫描
type: ALL
```

#### 跳跃扫描方式（MySQL 8.0.13+）

```
优化器改写查询：

原查询：
  WHERE age=25 AND city='Beijing'

改写为：
  WHERE gender='M' AND age=25 AND city='Beijing'
  UNION ALL
  WHERE gender='F' AND age=25 AND city='Beijing'

执行：
  - 第1次：扫描 (M, 25, Beijing) 的索引范围
  - 第2次：扫描 (F, 25, Beijing) 的索引范围
  - 合并结果
```

### 2. B+树遍历过程

#### 索引结构示意

```
B+树叶子节点（简化）：
(F, 20, Beijing) → (F, 20, Shanghai) → (F, 25, Beijing) → (F, 25, Shanghai)
(F, 30, Beijing) → (F, 30, Shanghai)
(M, 20, Beijing) → (M, 20, Shanghai) → (M, 25, Beijing) → (M, 25, Shanghai)
(M, 30, Beijing) → (M, 30, Shanghai)
```

#### 跳跃扫描步骤

```
步骤1：确定最左列的所有可能值
  → gender: {F, M}

步骤2：为每个值构造子查询
  → 子查询1: gender=F AND age=25 AND city=Beijing
  → 子查询2: gender=M AND age=25 AND city=Beijing

步骤3：依次扫描
  → 扫描 (F, 25, Beijing) 范围
  → "跳跃" 到 (M, 25, Beijing) 范围

步骤4：合并结果
```

### 3. 成本估算

```
跳跃扫描成本 = 
  + 获取最左列不同值的成本
  + N次索引范围扫描成本（N=最左列不同值数量）
  + 回表成本

全表扫描成本 = 
  + 扫描所有数据页的成本
  + CPU过滤成本

当：跳跃扫描成本 < 全表扫描成本 时触发
```

## 三、触发条件

### 1. 必要条件

```
✅ 必须满足：
  - MySQL 8.0.13 或更高版本
  - 查询跳过了联合索引的最左列
  - 最左列的不同值数量很少（通常 ≤ 几十个）
  - 后续列的过滤条件明确
  - 优化器开关启用（默认启用）

❌ 不会触发：
  - 最左列不同值太多（如用户ID，几百万个）
  - 全表扫描成本更低（小表）
  - 后续列也是范围查询
  - optimizer_switch 中 skip_scan=off
```

### 2. 典型触发场景

#### 场景1：枚举类型最左列

```sql
-- 索引：INDEX(status, create_time, user_id)
-- status: 'pending', 'active', 'cancelled' (3个值)

SELECT * FROM orders 
WHERE create_time >= '2025-11-01' AND user_id=12345;

-- 可能触发跳跃扫描
-- 优化器改写为3个子查询（每个status一个）
```

#### 场景2：布尔类型最左列

```sql
-- 索引：INDEX(is_deleted, update_time)
-- is_deleted: 0/1 (2个值)

SELECT * FROM products WHERE update_time > '2025-11-01';

-- 改写为：
-- WHERE is_deleted=0 AND update_time > '2025-11-01'
-- UNION ALL
-- WHERE is_deleted=1 AND update_time > '2025-11-01'
```

#### 场景3：小范围分类字段

```sql
-- 索引：INDEX(category_id, price, name)
-- category_id: 1-20 (20个类别)

SELECT * FROM products 
WHERE price BETWEEN 100 AND 200 AND name LIKE 'Phone%';

-- 可能触发跳跃扫描（20次范围扫描）
```

### 3. 不触发的场景

#### 场景1：最左列值太多

```sql
-- 索引：INDEX(user_id, order_time)
-- user_id: 100万个不同用户

SELECT * FROM orders WHERE order_time > '2025-11-01';

-- 不会触发：需要扫描100万次，成本太高
-- 结果：全表扫描或使用其他索引
```

#### 场景2：小表

```sql
-- 表只有1000行数据
SELECT * FROM small_table WHERE age=25;

-- 不会触发：全表扫描更快
```

## 四、EXPLAIN 输出

### 1. 识别跳跃扫描

```sql
EXPLAIN SELECT * FROM users WHERE age=25;

-- 输出：
type: range
key: idx_gac
Extra: Using where; Using index for skip scan
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
       这是关键标识
```

### 2. 详细分析

```sql
EXPLAIN FORMAT=TREE 
SELECT * FROM users WHERE age=25 AND city='Beijing';

-- 输出（简化）：
-> Filter: (age=25 AND city='Beijing')
    -> Index skip scan on idx_gac
        -> Skip scan values: gender in ('M', 'F')
        -> Index range scan: (gender=?, age=25, city='Beijing')
```

### 3. 性能对比

```sql
-- 测试准备
CREATE TABLE test (
    gender ENUM('M', 'F'),
    age INT,
    city VARCHAR(50),
    data VARCHAR(100),
    INDEX idx_gac(gender, age, city)
);

-- 插入100万行数据

-- 测试1：MySQL 5.7（或禁用skip scan）
SET optimizer_switch='skip_scan=off';
SELECT * FROM test WHERE age=25;
-- type: ALL, 执行时间: 0.5秒

-- 测试2：MySQL 8.0.13+（启用skip scan）
SET optimizer_switch='skip_scan=on';
SELECT * FROM test WHERE age=25;
-- type: range, Extra: Using index for skip scan
-- 执行时间: 0.05秒（快10倍）
```

## 五、性能考量

### 1. 优势与劣势

#### 优势
```
✅ 避免全表扫描
✅ 充分利用现有联合索引
✅ 无需创建额外索引
✅ 对低区分度最左列效果显著
```

#### 劣势
```
❌ 性能不如直接满足最左前缀的索引
❌ 最左列值越多，性能越差
❌ 多次索引扫描有额外开销
❌ 仅MySQL 8.0.13+支持
```

### 2. 性能对比

| 方案 | 索引使用 | 扫描次数 | 性能 | 适用场景 |
|------|---------|---------|------|---------|
| **直接索引** | `INDEX(age)` | 1次 | 最优 | 最左列不重要 |
| **联合索引** | `INDEX(gender,age)` 且 `WHERE gender=x AND age=y` | 1次 | 最优 | 需要gender过滤 |
| **跳跃扫描** | `INDEX(gender,age)` 且 `WHERE age=y` | N次（N=gender值数量） | 较好 | gender值少 |
| **全表扫描** | 无索引 | 全表 | 最差 | 无可用索引 |

### 3. 成本阈值

```
假设：
- 最左列有 N 个不同值
- 表有 M 行数据
- 每次索引扫描成本为 C

跳跃扫描成本 ≈ N × C
全表扫描成本 ≈ M × (磁盘IO成本)

通常当 N < 20-50 时，跳跃扫描有优势
```

## 六、优化建议

### 1. 设计索引时考虑列顺序

```sql
-- 不好：高区分度列放前面
INDEX(user_id, gender, age)
-- user_id区分度高，但如果经常只查gender和age，索引利用率低

-- 好：低区分度常用列放前面（如果支持跳跃扫描）
INDEX(gender, age, user_id)
-- gender值少，跳跃扫描可跳过
-- 同时支持 gender+age 的高频查询
```

### 2. 何时依赖跳跃扫描

```
✅ 适合依赖：
  - MySQL 8.0.13+ 环境
  - 最左列是状态/类型等枚举字段（值少）
  - 后续列查询频繁
  - 不想维护太多索引

❌ 不适合依赖：
  - 需要兼容旧版本MySQL
  - 最左列值很多（几百上千个）
  - 对性能要求极高的核心查询
  - 不确定优化器行为
```

### 3. 监控和验证

```sql
-- 1. 查看是否启用
SHOW VARIABLES LIKE 'optimizer_switch';
-- 确认: skip_scan=on

-- 2. 验证实际使用
EXPLAIN SELECT * FROM table WHERE ...;
-- 检查: Extra 列是否有 "Using index for skip scan"

-- 3. 性能对比
-- 禁用跳跃扫描测试
SET optimizer_switch='skip_scan=off';
SELECT ...;  -- 记录执行时间

-- 启用跳跃扫描测试
SET optimizer_switch='skip_scan=on';
SELECT ...;  -- 记录执行时间

-- 4. 监控慢查询
-- 如果跳跃扫描导致性能问题，考虑创建专用索引
```

## 七、实战案例

### 案例1：电商订单系统

```sql
-- 场景：订单表有1000万行
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    status ENUM('pending','paid','shipped','completed','cancelled'),
    create_time DATETIME,
    user_id BIGINT,
    INDEX idx_status_time_user(status, create_time, user_id)
);

-- 需求：按时间范围查询某用户订单（不关心状态）
SELECT * FROM orders 
WHERE create_time >= '2025-11-01' AND user_id=12345;

-- MySQL 5.7：全表扫描（0.8秒）
-- MySQL 8.0.13+：跳跃扫描（0.06秒）
--   内部改写为5个子查询（每个status一个）
```

### 案例2：社交媒体帖子

```sql
-- 场景：帖子表
CREATE TABLE posts (
    id BIGINT,
    is_deleted TINYINT,  -- 0/1
    publish_time DATETIME,
    author_id BIGINT,
    INDEX idx_del_time_author(is_deleted, publish_time, author_id)
);

-- 需求：按时间倒序获取某作者帖子（包括已删除）
SELECT * FROM posts 
WHERE publish_time >= '2025-01-01' AND author_id=999
ORDER BY publish_time DESC
LIMIT 20;

-- 跳跃扫描：
--   子查询1: is_deleted=0 AND ...
--   子查询2: is_deleted=1 AND ...
--   合并并排序
```

## 八、常见问题

### Q1：能强制使用跳跃扫描吗？

**回答**：不能直接强制，但可以：
```sql
-- 确保启用优化器开关
SET optimizer_switch='skip_scan=on';

-- 如果优化器仍不使用，可能是：
-- 1. 成本估算认为不划算
-- 2. 最左列值太多
-- 3. 统计信息不准确 → ANALYZE TABLE
```

### Q2：跳跃扫描与索引下推的关系？

**回答**：
- **索引跳跃扫描**：解决跳过最左列的问题
- **索引下推**：将WHERE条件下推到存储引擎层过滤

两者可以同时工作：
```sql
EXPLAIN SELECT * FROM users WHERE age=25 AND city LIKE 'Bei%';
-- Extra: Using index for skip scan; Using index condition
--        ^^^^^^^^^^^^^^^^^^^^      ^^^^^^^^^^^^^^^^^^^^^^^
--        跳跃扫描                   索引下推
```

### Q3：如何禁用跳跃扫描？

```sql
-- 全局禁用（不推荐）
SET GLOBAL optimizer_switch='skip_scan=off';

-- 会话级别禁用
SET SESSION optimizer_switch='skip_scan=off';

-- 查询级别禁用（MySQL 8.0.20+）
SELECT /*+ NO_SKIP_SCAN(table) */ * FROM table WHERE ...;
```

## 九、面试总结

**索引跳跃扫描（Index Skip Scan）** 是MySQL 8.0.13+引入的优化技术，允许跳过联合索引最左列。

**工作原理**：
- 获取最左列的所有不同值
- 为每个值构造子查询
- 依次执行索引范围扫描
- 合并结果

**触发条件**：
- MySQL 8.0.13+
- 最左列不同值数量少（通常<20-50个）
- 后续列有明确过滤条件
- 优化器评估成本划算

**适用场景**：
- 最左列是状态、类型、布尔等低区分度字段
- 经常跳过最左列查询后续列
- 不想创建过多索引

**性能特点**：
- 比全表扫描快
- 比直接满足最左前缀的索引慢
- 扫描次数 = 最左列不同值数量

**优化建议**：
- 索引设计时可考虑将低区分度字段放前面
- 使用EXPLAIN验证是否触发
- 高频核心查询仍建议创建专用索引
- 定期ANALYZE更新统计信息

这是MySQL 8.0的重要优化特性，体现了对最左前缀原则的补充和完善。

