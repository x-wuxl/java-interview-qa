---
layout: default
title: "执行计划中，key有值，还是很慢怎么办？"
parent: 数据库MySQL
nav_order: 346
description: "深入分析key有值但查询仍然很慢的深层原因，包括索引选择错误、扫描行数过多、回表开销等问题及解决方案"
date: 2025-11-02
---
# 执行计划中，key有值，还是很慢怎么办？

## 核心概念

执行计划中`key`字段有值说明查询使用了索引，但不代表索引使用效率高。慢查询可能源于**索引选择错误、扫描行数过多、回表开销大、索引失效**等深层原因，需要结合`type`、`rows`、`Extra`等字段综合分析。

---

## 一、使用了索引仍然慢的常见原因

### 原因1：索引选择错误（MySQL优化器选错了）

**场景**：表有多个索引，MySQL选择了次优索引。

#### 案例演示
```sql
-- 表结构
CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    status TINYINT,
    create_time DATETIME,
    INDEX idx_user(user_id),
    INDEX idx_status(status),
    INDEX idx_time(create_time)
);

-- 查询SQL
SELECT * FROM orders 
WHERE user_id = 1001 AND status = 1 
ORDER BY create_time DESC 
LIMIT 10;
```

**EXPLAIN结果**：
```
type: ref
key: idx_status          ← 选择了idx_status
rows: 200000             ← 扫描20万行
Extra: Using where; Using filesort
```

**问题分析**：
- MySQL选择了`idx_status`，但`status`区分度低（只有0/1/2三种值）
- 实际应该选择`idx_user`（user_id区分度高）

---

#### 解决方案

**方案1：使用FORCE INDEX强制指定索引**
```sql
SELECT * FROM orders FORCE INDEX(idx_user)
WHERE user_id = 1001 AND status = 1 
ORDER BY create_time DESC 
LIMIT 10;
```

**方案2：创建更合适的联合索引**
```sql
-- 联合索引：高区分度字段在前，排序字段在后
CREATE INDEX idx_user_time ON orders(user_id, create_time);
```

**方案3：更新索引统计信息**
```sql
-- MySQL可能基于过时的统计信息做出错误判断
ANALYZE TABLE orders;
```

---

### 原因2：扫描行数过多（rows值很大）

**场景**：虽然用了索引，但索引过滤效果差。

#### 案例演示
```sql
EXPLAIN SELECT * FROM orders 
WHERE status = 1;  -- status只有0/1/2三种值
```

**EXPLAIN结果**：
```
type: ref
key: idx_status
rows: 3000000    ← 扫描300万行
Extra: Using where
```

**问题分析**：
- 索引存在但区分度低（Cardinality低）
- 需要扫描大量数据，索引效率不如全表扫描

---

#### 解决方案

**方案1：添加更有区分度的字段到联合索引**
```sql
-- 如果经常配合user_id查询
CREATE INDEX idx_status_user ON orders(status, user_id);
```

**方案2：使用覆盖索引避免回表**
```sql
-- 查询字段都在索引中
SELECT id, user_id, status FROM orders WHERE status = 1;
-- 索引：(status, user_id, id)
```

**方案3：改变查询策略**
```sql
-- 如果status=1的数据占比超过20%，考虑反向查询
-- ❌ 慢查询
WHERE status = 1

-- ✅ 如果status=0的数据很少
WHERE status != 1  -- 需改为IN(0,2)才能用索引
```

---

### 原因3：回表开销大（Using where）

**场景**：使用二级索引后需要大量回表查询。

#### 原理说明
```
二级索引查询流程：
1. 扫描二级索引找到主键ID列表
2. 根据主键ID回表查询完整行数据
3. 应用WHERE条件过滤
```

#### 案例演示
```sql
EXPLAIN SELECT * FROM orders 
WHERE user_id = 1001;
```

**EXPLAIN结果**：
```
type: ref
key: idx_user_id
rows: 50000      ← 需要回表5万次
Extra: Using where
```

**问题分析**：
- 用户1001有5万订单
- 每次回表都是随机IO，开销巨大

---

#### 解决方案

**方案1：使用覆盖索引**
```sql
-- 只查询索引中的字段
SELECT id, user_id FROM orders WHERE user_id = 1001;

-- 或创建覆盖索引
CREATE INDEX idx_user_cover ON orders(user_id, status, create_time);
```

**方案2：延迟关联（先走索引查主键，再关联）**
```sql
-- ❌ 直接回表5万次
SELECT * FROM orders WHERE user_id = 1001 ORDER BY id LIMIT 10;

-- ✅ 先用索引找到10个主键ID，只回表10次
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders WHERE user_id = 1001 ORDER BY id LIMIT 10
) t ON o.id = t.id;
```

---

### 原因4：索引失效（部分条件未用索引）

**场景**：联合索引未完全利用，或索引列被函数处理。

#### 案例1：联合索引未遵循最左前缀
```sql
-- 索引：idx_abc(a, b, c)
EXPLAIN SELECT * FROM t WHERE b = 2 AND c = 3;
```

**EXPLAIN结果**：
```
type: index  ← 索引全扫描，不是最优的ref
key: idx_abc
rows: 1000000
Extra: Using where; Using index
```

**解决方案**：
```sql
-- 调整WHERE条件顺序（无效，MySQL不关心顺序）
-- 正确做法：调整索引顺序或添加新索引
CREATE INDEX idx_bc ON t(b, c);
```

---

#### 案例2：函数操作导致索引失效
```sql
EXPLAIN SELECT * FROM orders 
WHERE DATE(create_time) = '2025-11-02';
```

**EXPLAIN结果**：
```
type: index
key: idx_create_time
rows: 5000000   ← 全索引扫描
Extra: Using where; Using index
```

**解决方案**：
```sql
-- 改写为范围查询
WHERE create_time >= '2025-11-02 00:00:00' 
  AND create_time < '2025-11-03 00:00:00';
```

---

### 原因5：深度分页问题（LIMIT偏移量大）

**场景**：虽然用了索引，但需要扫描+跳过大量数据。

#### 案例演示
```sql
EXPLAIN SELECT * FROM orders 
ORDER BY id 
LIMIT 1000000, 20;
```

**EXPLAIN结果**：
```
type: index
key: PRIMARY
rows: 1000020   ← 需要扫描100万+20行
Extra: Using index
```

**问题分析**：
- 虽然走了主键索引，但需要扫描100万行然后丢弃
- 每行都要回表查询完整数据

---

#### 解决方案

**方案1：主键定位法**
```sql
-- 记录上一页最大ID
SELECT * FROM orders WHERE id > 1000000 ORDER BY id LIMIT 20;
```

**方案2：延迟关联**
```sql
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders ORDER BY id LIMIT 1000000, 20
) t ON o.id = t.id;
```

**方案3：业务层优化**
```java
// 禁止跳页，只允许"下一页"
// 或限制最大页码（如最多查看前100页）
```

---

## 二、诊断流程

### 步骤1：完整分析EXPLAIN
```sql
EXPLAIN SELECT ...;
```

**重点检查**：
| 字段 | 检查点 | 优化目标 |
|------|--------|---------|
| **type** | 是否为index/ALL | 争取达到ref/range |
| **key** | 是否选择了最优索引 | 必要时FORCE INDEX |
| **rows** | 扫描行数是否过多 | 减少到几百行以内 |
| **Extra** | 是否有filesort/temporary | 优化索引避免额外操作 |
| **filtered** | 过滤比例是否过低 | 提高索引区分度 |

---

### 步骤2：查看索引统计信息
```sql
-- 查看索引基数（区分度）
SHOW INDEX FROM orders;
```

**关键指标**：
- `Cardinality`：索引不重复值的数量
- 理想情况：Cardinality ≈ 表总行数（唯一索引）
- 区分度低：Cardinality << 表总行数

---

### 步骤3：使用OPTIMIZER_TRACE分析
```sql
-- 开启优化器跟踪（MySQL 5.6+）
SET optimizer_trace="enabled=on";

SELECT * FROM orders WHERE user_id = 1001 AND status = 1;

-- 查看优化器决策过程
SELECT * FROM information_schema.OPTIMIZER_TRACE\G

SET optimizer_trace="enabled=off";
```

**可以看到**：
- 候选索引列表
- 各索引的成本估算
- 最终选择原因

---

## 三、实战案例

### 案例：电商订单查询优化

**原始SQL**：
```sql
SELECT * FROM orders 
WHERE user_id = 1001 AND status IN (1,2,3)
ORDER BY create_time DESC 
LIMIT 20;
```

**初次EXPLAIN**：
```
type: ref
key: idx_status
rows: 800000
Extra: Using where; Using filesort
执行时间：2.8秒
```

---

**问题分析**：
1. ❌ MySQL选择了`idx_status`（区分度低）
2. ❌ 扫描80万行
3. ❌ Using filesort（排序未用索引）

---

**优化步骤**：

#### 1️⃣ 强制使用正确索引
```sql
SELECT * FROM orders FORCE INDEX(idx_user_id)
WHERE user_id = 1001 AND status IN (1,2,3)
ORDER BY create_time DESC 
LIMIT 20;

-- 执行时间：0.8秒（仍不理想）
```

---

#### 2️⃣ 创建联合索引
```sql
CREATE INDEX idx_user_time ON orders(user_id, create_time);

-- 执行时间：0.05秒 ✅
```

**优化后EXPLAIN**：
```
type: range
key: idx_user_time
rows: 50
Extra: Using index condition; Using where
```

---

## 四、总结对比

| 问题场景 | 症状 | 解决方案 |
|---------|------|---------|
| **索引选择错误** | key值不是最优索引 | FORCE INDEX / ANALYZE TABLE |
| **扫描行数多** | rows值很大 | 优化索引设计 / 覆盖索引 |
| **回表开销大** | Using where | 覆盖索引 / 延迟关联 |
| **索引失效** | type=index | 避免函数操作 / 调整索引 |
| **深度分页** | LIMIT偏移量大 | 主键定位 / 延迟关联 |

---

## 面试答题要点

1. **key有值≠索引高效**：需结合type、rows、Extra综合判断
2. **重点看rows扫描行数**：超过1万行通常有优化空间
3. **检查索引选择**：用OPTIMIZER_TRACE分析MySQL为何做出该选择
4. **覆盖索引是优化利器**：避免回表能显著提升性能
5. **必要时强制索引**：FORCE INDEX解决优化器选择错误

---

## 总结

执行计划中key有值但仍然慢，核心是**索引存在但未高效使用**。排查时重点关注索引选择是否正确、扫描行数是否过多、是否存在回表开销。通过联合索引、覆盖索引、FORCE INDEX等手段优化。面试中能快速定位"用了索引但不高效"的深层原因，体现对MySQL索引机制的深刻理解。

