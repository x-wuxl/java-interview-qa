---
layout: post
title: "什么是索引合并，原理是什么？"
date: 2025-11-02
categories: [MySQL, 索引优化]
tags: [MySQL, 索引合并, Index Merge, 优化器, 性能优化]
description: "深入解析MySQL索引合并（Index Merge）机制，包括工作原理、三种合并算法、触发条件和性能优化建议。"
---

## 一、核心概念

**索引合并（Index Merge）** 是MySQL优化器的一种索引优化策略：在单个查询中同时使用多个索引，然后合并这些索引的结果集。

**典型场景**：
```sql
-- 有两个单独索引：INDEX(a), INDEX(b)
SELECT * FROM table WHERE a=1 OR b=2;
SELECT * FROM table WHERE a=1 AND b=2;
```

**特点**：
- MySQL 5.0+ 引入
- 弥补了没有联合索引时的性能损失
- 不如直接使用联合索引高效

## 二、三种合并算法

### 1. Intersection（交集合并）

#### 适用场景
用于 **AND** 条件连接的多个索引。

```sql
SELECT * FROM users WHERE age=25 AND city='Beijing';
-- 有 INDEX(age) 和 INDEX(city)
```

#### 执行过程

```
步骤1：从 INDEX(age) 获取 age=25 的行
  → rowid 集合: {1, 3, 5, 7, 9, 11}

步骤2：从 INDEX(city) 获取 city='Beijing' 的行
  → rowid 集合: {2, 3, 6, 7, 10, 11}

步骤3：求交集
  → 交集: {3, 7, 11}

步骤4：根据 rowid 回表获取完整数据
  → 只需回表3次
```

#### EXPLAIN 输出

```sql
EXPLAIN SELECT * FROM users WHERE age=25 AND city='Beijing';

type: index_merge
key: idx_age,idx_city
key_len: 4,4
Extra: Using intersect(idx_age,idx_city); Using where
```

#### 优势
- 利用两个索引同时过滤，减少回表次数
- 比单独使用一个索引效果更好

### 2. Union（并集合并）

#### 适用场景
用于 **OR** 条件连接的多个索引。

```sql
SELECT * FROM users WHERE age=25 OR city='Beijing';
-- 有 INDEX(age) 和 INDEX(city)
```

#### 执行过程

```
步骤1：从 INDEX(age) 获取 age=25 的行
  → rowid 集合: {1, 3, 5, 7, 9}

步骤2：从 INDEX(city) 获取 city='Beijing' 的行
  → rowid 集合: {2, 3, 6, 7, 10}

步骤3：求并集（去重）
  → 并集: {1, 2, 3, 5, 6, 7, 9, 10}

步骤4：根据 rowid 排序（可选，优化回表效率）

步骤5：根据 rowid 回表获取完整数据
```

#### EXPLAIN 输出

```sql
EXPLAIN SELECT * FROM users WHERE age=25 OR city='Beijing';

type: index_merge
key: idx_age,idx_city
Extra: Using union(idx_age,idx_city); Using where
```

#### 特点
- 避免全表扫描（否则OR条件很难优化）
- 需要去重操作
- 回表次数 = 两个索引匹配行数之和（去重后）

### 3. Sort-Union（排序并集）

#### 适用场景
用于 **范围查询** 的 OR 条件。

```sql
SELECT * FROM users 
WHERE (age BETWEEN 20 AND 30) OR (salary BETWEEN 5000 AND 8000);
```

#### 与 Union 的区别

```
Union：
  - 等值查询的 OR
  - rowid 已经有序
  - 直接合并去重

Sort-Union：
  - 范围查询的 OR
  - rowid 可能无序
  - 需要先排序再合并
```

#### EXPLAIN 输出

```sql
type: index_merge
key: idx_age,idx_salary
Extra: Using sort_union(idx_age,idx_salary); Using where
```

#### 性能影响
- 额外的排序开销
- 比 Union 慢，但比全表扫描快

## 三、触发条件

### 1. 必要条件

```
✅ 需要满足：
  - 有多个可用的单列索引
  - 查询条件使用 AND 或 OR 连接
  - 优化器估算索引合并成本低于其他方案
  - 不存在更优的联合索引

❌ 不会触发：
  - 已有合适的联合索引（优先使用）
  - 单个索引效果足够好
  - 全表扫描成本更低（小表）
```

### 2. 配置参数

```sql
-- 查看是否启用索引合并
SHOW VARIABLES LIKE 'optimizer_switch';

-- 相关选项：
-- index_merge=on
-- index_merge_intersection=on
-- index_merge_union=on
-- index_merge_sort_union=on

-- 禁用索引合并（通常不建议）
SET optimizer_switch='index_merge=off';
```

### 3. 典型触发场景

#### 场景1：AND 条件，无联合索引

```sql
-- 索引：INDEX(status), INDEX(create_time)
SELECT * FROM orders 
WHERE status='paid' AND create_time > '2025-01-01';

-- 可能触发 Intersection
```

#### 场景2：OR 条件

```sql
-- 索引：INDEX(email), INDEX(phone)
SELECT * FROM users 
WHERE email='test@example.com' OR phone='13800138000';

-- 可能触发 Union（OR条件几乎必然触发）
```

#### 场景3：复杂组合

```sql
-- 索引：INDEX(a), INDEX(b), INDEX(c)
SELECT * FROM table 
WHERE (a=1 AND b=2) OR c=3;

-- 可能的执行计划：
-- 1. Intersection(a,b) 得到集合1
-- 2. INDEX(c) 得到集合2
-- 3. Union(集合1, 集合2)
```

## 四、性能分析

### 1. 成本构成

```
索引合并总成本 = 
  + 索引1扫描成本
  + 索引2扫描成本
  + 集合运算成本（交集/并集/排序）
  + 回表成本
```

### 2. 与其他方案对比

#### 对比表

| 方案 | 索引扫描 | 回表次数 | 额外开销 | 性能 |
|------|---------|---------|---------|------|
| **单索引** | 1次 | 多（需二次过滤） | 无 | 中等 |
| **索引合并 (AND)** | 2次 | 少（精确过滤） | 交集运算 | 较好 |
| **索引合并 (OR)** | 2次 | 多（并集） | 并集+去重 | 一般 |
| **联合索引** | 1次 | 最少 | 无 | **最优** |

#### 实际测试

```sql
-- 准备数据：100万行
CREATE TABLE test (
    a INT,
    b INT,
    data VARCHAR(100),
    INDEX idx_a(a),
    INDEX idx_b(b)
) ENGINE=InnoDB;

-- 测试1：单索引
SELECT * FROM test WHERE a=100;
-- 执行时间：0.05秒，扫描1000行

-- 测试2：索引合并 (Intersection)
SELECT * FROM test WHERE a=100 AND b=200;
-- 执行时间：0.08秒，扫描1000+1000行，回表10行

-- 测试3：联合索引
ALTER TABLE test ADD INDEX idx_ab(a, b);
SELECT * FROM test WHERE a=100 AND b=200;
-- 执行时间：0.02秒，扫描10行
```

**结论**：联合索引性能提升约 **4倍**。

### 3. 适用数据量

```
小表（< 1万行）：
  → 索引合并优势不明显，全表扫描可能更快

中表（1万-100万行）：
  → 索引合并有明显效果

大表（> 100万行）：
  → 索引合并效果显著，但联合索引更优
```

## 五、优化建议

### 1. 创建联合索引（首选）

```sql
-- 不推荐：依赖索引合并
INDEX(a), INDEX(b)
WHERE a=x AND b=y

-- 推荐：创建联合索引
INDEX(a, b)
WHERE a=x AND b=y
```

**原因**：
- 避免多次索引扫描
- 避免集合运算开销
- 可能实现索引覆盖

### 2. OR 条件优化

OR 条件难以优化，考虑以下方案：

#### 方案A：UNION 改写

```sql
-- 原查询（索引合并）
SELECT * FROM users WHERE age=25 OR city='Beijing';

-- 改写为 UNION（可能更快）
SELECT * FROM users WHERE age=25
UNION
SELECT * FROM users WHERE city='Beijing';
```

#### 方案B：IN 替代 OR

```sql
-- 如果是同一字段
WHERE status='active' OR status='pending'

-- 改写为
WHERE status IN ('active', 'pending')
```

### 3. 监控索引使用

```sql
-- 查看索引合并是否频繁出现
EXPLAIN SELECT ...;

-- 如果经常出现 index_merge，考虑：
-- 1. 创建对应的联合索引
-- 2. 优化查询条件
-- 3. 检查统计信息是否准确
```

### 4. 特殊场景保留

某些场景索引合并是合理的：

```sql
-- 场景：偶尔出现的临时查询
-- 不值得为此创建专门的联合索引
SELECT * FROM users WHERE email='x' OR phone='y';

-- 保留 INDEX(email) 和 INDEX(phone)
-- 让索引合并处理这种低频查询
```

## 六、常见问题

### Q1：为什么有联合索引还用索引合并？

**回答**：优化器判断索引合并成本更低，可能的原因：
- 联合索引统计信息不准确
- 联合索引列顺序不合适
- 数据分布特殊

**解决**：`ANALYZE TABLE` 或 `FORCE INDEX`

### Q2：如何强制使用/禁用索引合并？

```sql
-- 禁用索引合并
SELECT /*+ NO_INDEX_MERGE(table) */ * FROM table WHERE ...;

-- 或修改会话级别
SET optimizer_switch='index_merge=off';
```

### Q3：索引合并的性能瓶颈在哪？

**主要开销**：
1. 多次索引扫描（2次或更多）
2. 集合运算（交集/并集）
3. 排序（Sort-Union）
4. 回表操作

## 七、实战案例

### 案例：电商订单查询

```sql
-- 需求：查询已支付或已发货的订单
SELECT * FROM orders 
WHERE status='paid' OR status='shipped';

-- 方案1：索引合并（现状）
INDEX(status)  -- 单列索引
-- Extra: Using union(idx_status,idx_status)
-- 执行时间：0.5秒

-- 方案2：IN 改写
WHERE status IN ('paid', 'shipped')
-- 执行时间：0.3秒

-- 方案3：位图索引（如果状态少）
-- 添加状态位字段 status_flags
INDEX(status_flags)
WHERE status_flags & 0b0011 > 0
-- 执行时间：0.1秒
```

## 八、面试总结

**索引合并（Index Merge）** 是MySQL在单个查询中同时使用多个索引的优化策略。

**三种类型**：
1. **Intersection**：AND条件，求交集，减少回表
2. **Union**：OR条件，求并集，避免全表扫描
3. **Sort-Union**：范围OR条件，需要排序

**工作原理**：
- 分别从多个索引获取 rowid 集合
- 进行集合运算（交集/并集）
- 根据 rowid 回表获取完整数据

**性能考量**：
- 比全表扫描快，比联合索引慢
- 额外开销：多次索引扫描 + 集合运算
- 通常是妥协方案，不是最优方案

**优化建议**：
- 高频查询创建联合索引（最优）
- OR条件考虑UNION改写
- 使用EXPLAIN监控索引使用
- 定期ANALYZE更新统计信息

在面试中能详细说明索引合并的三种类型和工作原理，体现了对MySQL优化器的深入理解。

