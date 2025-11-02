---
layout: post
title: "联合索引是越多越好吗？"
date: 2025-11-02
categories: [MySQL, 索引优化]
tags: [MySQL, 联合索引, 索引设计, 性能优化, 写入性能]
description: "深入分析联合索引的数量权衡，包括过多联合索引的代价、合理数量建议和优化策略。"
---

## 一、直接答案

**不是，联合索引不是越多越好**。过多的联合索引会带来：

1. **写入性能下降**：每次INSERT/UPDATE/DELETE都要维护所有索引
2. **存储空间浪费**：每个索引都占用磁盘空间
3. **内存压力增大**：Buffer Pool需要缓存更多索引页
4. **优化器困惑**：索引太多可能导致选择失误
5. **维护成本增加**：索引越多，管理和优化越复杂

## 二、联合索引的代价

### 1. 写入性能影响

#### 代价分析

```sql
-- 假设表有3个联合索引
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    status TINYINT,
    create_time DATETIME,
    total_amount DECIMAL(10,2),
    INDEX idx_user_status(user_id, status),
    INDEX idx_user_time(user_id, create_time),
    INDEX idx_status_time(status, create_time)
);
```

**单次INSERT操作的成本**：

```
1. 写入主键索引（聚簇索引）
2. 写入 idx_user_status
3. 写入 idx_user_time
4. 写入 idx_status_time
5. 可能触发索引页分裂
6. 写入 undo log
7. 写入 redo log

总成本 = 4次B+树写入 + 日志开销
```

#### 性能测试

```sql
-- 测试表：无额外索引
CREATE TABLE test1 (
    id INT PRIMARY KEY AUTO_INCREMENT,
    a INT, b INT, c INT, d INT, data VARCHAR(100)
);

-- 测试表：有5个联合索引
CREATE TABLE test2 (
    id INT PRIMARY KEY AUTO_INCREMENT,
    a INT, b INT, c INT, d INT, data VARCHAR(100),
    INDEX idx_ab(a, b),
    INDEX idx_ac(a, c),
    INDEX idx_ad(a, d),
    INDEX idx_bc(b, c),
    INDEX idx_cd(c, d)
);

-- 插入测试（10万行）
-- test1: 1.2秒
-- test2: 5.8秒（慢约5倍）

-- UPDATE测试（更新1万行）
-- test1: 0.3秒
-- test2: 2.1秒（慢约7倍）
```

### 2. 存储空间占用

#### 空间计算

```sql
-- 表数据：1000万行，每行约200字节
-- 表大小：10,000,000 × 200字节 ≈ 2GB

-- 单个联合索引大小（平均）
-- 索引 idx_user_status_time (BIGINT + TINYINT + DATETIME + 主键)
-- 每行索引记录：8 + 1 + 8 + 8 = 25字节
-- 索引大小：10,000,000 × 25字节 ≈ 250MB

-- 如果有8个联合索引：
-- 总索引大小：250MB × 8 ≈ 2GB
-- 总占用：表(2GB) + 索引(2GB) = 4GB
```

#### 实际案例

```sql
-- 查看表和索引大小
SELECT 
    table_name,
    ROUND(data_length/1024/1024, 2) AS data_mb,
    ROUND(index_length/1024/1024, 2) AS index_mb,
    ROUND((data_length + index_length)/1024/1024, 2) AS total_mb,
    ROUND(index_length/data_length*100, 2) AS index_ratio
FROM information_schema.TABLES
WHERE table_schema='your_db' AND table_name='orders';

-- 典型结果：
-- data_mb: 2000
-- index_mb: 1800  ← 索引占了90%的空间
-- index_ratio: 90%
```

### 3. 内存压力

#### Buffer Pool 竞争

```
InnoDB Buffer Pool 分配：
- 数据页缓存：60-70%
- 索引页缓存：20-30%
- 其他（自适应哈希等）：10%

索引越多 → 索引页越多 → Buffer Pool 命中率下降
```

#### 案例分析

```sql
-- 配置：innodb_buffer_pool_size = 8GB
-- 表数据：5GB
-- 索引总量：10GB（索引过多）

-- 结果：
-- 1. Buffer Pool 无法完全缓存索引
-- 2. 频繁换页，导致磁盘IO增加
-- 3. 查询性能下降

-- 监控命令：
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';
-- Innodb_buffer_pool_read_requests: 10000000（内存读）
-- Innodb_buffer_pool_reads: 1000000（磁盘读）
-- 命中率：90%（理想应 > 99%）
```

### 4. 优化器选择困难

#### 问题描述

```sql
-- 表有10个联合索引
CREATE TABLE orders (
    id BIGINT,
    user_id BIGINT,
    merchant_id BIGINT,
    status TINYINT,
    create_time DATETIME,
    update_time DATETIME,
    INDEX idx_user_status(user_id, status),
    INDEX idx_user_time(user_id, create_time),
    INDEX idx_user_update(user_id, update_time),
    INDEX idx_merchant_status(merchant_id, status),
    INDEX idx_merchant_time(merchant_id, create_time),
    INDEX idx_status_time(status, create_time),
    INDEX idx_status_update(status, update_time),
    INDEX idx_time_status(create_time, status),
    INDEX idx_update_status(update_time, status),
    INDEX idx_user_merchant(user_id, merchant_id)
);

-- 查询
SELECT * FROM orders 
WHERE user_id=? AND status=? AND create_time >= ?;
```

**优化器困境**：

```
可选索引：
1. idx_user_status（用user_id和status，时间范围过滤）
2. idx_user_time（用user_id和create_time，status过滤）
3. idx_status_time（用status和create_time，user_id过滤）

优化器需要：
- 评估每个索引的成本
- 评估是否使用索引合并
- 统计信息可能不准确
- 可能做出错误选择

结果：
- 优化器耗时增加
- 可能选择次优索引
- 执行计划不稳定
```

#### 错误选择案例

```sql
-- 期望走 idx_user_time（user_id区分度高）
-- 实际走 idx_status_time（统计信息误导）

EXPLAIN SELECT * FROM orders 
WHERE user_id=12345 AND status=1 AND create_time >= '2025-01-01';

-- 结果：
key: idx_status_time  -- 错误选择
rows: 500000  -- 扫描了50万行

-- 强制使用正确索引：
EXPLAIN SELECT * FROM orders FORCE INDEX(idx_user_time)
WHERE user_id=12345 AND status=1 AND create_time >= '2025-01-01';

-- 结果：
key: idx_user_time  -- 正确选择
rows: 100  -- 只扫描100行
```

## 三、合理数量建议

### 1. 经验数值

```
单表联合索引建议：
- 小表（<1万行）：0-2个
- 中表（1万-100万行）：2-5个
- 大表（>100万行）：3-8个
- 超大表（>1亿行）：根据查询模式，不超过10个

总索引数（包括单列索引）：
- 建议：5-10个
- 警戒线：15个
- 危险线：20个以上
```

### 2. 判断标准

#### 标准1：覆盖核心查询

```sql
-- 分析慢查询日志
SELECT 
    sql_text,
    count_star,
    avg_timer_wait / 1000000000000 AS avg_seconds
FROM sys.x$statements_with_runtimes_in_95th_percentile
ORDER BY avg_timer_wait DESC
LIMIT 10;

-- 为Top 10慢查询设计索引
-- 不要为所有可能的查询都建索引
```

#### 标准2：查询频率权衡

```sql
-- 查询频率分析
-- 高频查询（QPS > 100）：必须有优化索引
-- 中频查询（QPS 10-100）：建议有索引
-- 低频查询（QPS < 10）：可以容忍慢查询，不建索引
```

#### 标准3：写入比例

```
读写比例判断：
- 读多写少（10:1以上）：可以多建索引（6-10个）
- 读写均衡（3:1左右）：适度建索引（4-6个）
- 写多读少（1:1以下）：少建索引（2-4个）
```

## 四、优化策略

### 策略1：索引合并

#### 原理

```sql
-- 不好：为所有组合建索引
INDEX(a, b)
INDEX(a, c)
INDEX(b, c)
INDEX(a, b, c)

-- 好：建少量高效索引
INDEX(a, b, c)  -- 覆盖大部分查询
INDEX(b)        -- 单独查b时使用
INDEX(c)        -- 单独查c时使用
```

#### 合并规则

```
合并原则：
1. 最左前缀：INDEX(a,b,c) 可以替代 INDEX(a) 和 INDEX(a,b)
2. 高频覆盖：优先保留高频查询的索引
3. 去除冗余：删除完全被包含的索引

示例：
已有 INDEX(user_id, status, create_time)
可删除：
  - INDEX(user_id)
  - INDEX(user_id, status)
保留（如果需要）：
  - INDEX(status, create_time) -- 不同查询模式
```

### 策略2：查询改写

#### 方案A：统一查询模式

```sql
-- 原查询（需要多个索引）
-- 查询1：WHERE user_id=?
-- 查询2：WHERE user_id=? AND status=?
-- 查询3：WHERE user_id=? AND status=? AND create_time>=?

-- 原索引方案（3个索引）
INDEX(user_id)
INDEX(user_id, status)
INDEX(user_id, status, create_time)

-- 优化：统一使用一个索引
INDEX(user_id, status, create_time)

-- 查询1改写（可选）
WHERE user_id=? AND status IS NOT NULL  -- 仍走索引
```

#### 方案B：OR改UNION

```sql
-- 原查询（需要多个索引支持OR）
SELECT * FROM orders 
WHERE user_id=? OR merchant_id=?;
-- 需要：INDEX(user_id), INDEX(merchant_id) + 索引合并

-- 改写为UNION
SELECT * FROM orders WHERE user_id=?
UNION
SELECT * FROM orders WHERE merchant_id=?;
-- 同样的索引，但执行计划更可控
```

### 策略3：分表分库

#### 垂直分表

```sql
-- 原表：字段多，索引多
CREATE TABLE orders (
    id BIGINT,
    user_id BIGINT,
    merchant_id BIGINT,
    status TINYINT,
    create_time DATETIME,
    -- 20个其他字段...
    -- 15个索引...
);

-- 拆分：核心表 + 扩展表
CREATE TABLE orders_core (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    merchant_id BIGINT,
    status TINYINT,
    create_time DATETIME,
    INDEX idx_user_status_time(user_id, status, create_time),
    INDEX idx_merchant_time(merchant_id, create_time)
    -- 只保留高频查询的索引
);

CREATE TABLE orders_ext (
    order_id BIGINT PRIMARY KEY,
    -- 其他20个字段
    -- 2-3个低频查询索引
);
```

#### 水平分表

```sql
-- 按时间分表
orders_2025_01
orders_2025_02
...

-- 好处：
-- 1. 每个分表索引更小
-- 2. 历史表可以减少索引（只读场景）
-- 3. 查询只命中相关分表
```

### 策略4：定期审计

#### 监控脚本

```sql
-- 1. 查找未使用的索引
SELECT 
    t.table_schema,
    t.table_name,
    s.index_name,
    s.cardinality
FROM information_schema.statistics s
JOIN information_schema.tables t 
    ON s.table_name = t.table_name
LEFT JOIN sys.schema_unused_indexes u
    ON u.object_schema = t.table_schema
    AND u.object_name = t.table_name
    AND u.index_name = s.index_name
WHERE t.table_schema = 'your_db'
    AND u.index_name IS NOT NULL;

-- 2. 查找冗余索引
SELECT * FROM sys.schema_redundant_indexes
WHERE table_schema='your_db';

-- 3. 分析索引大小
SELECT 
    table_name,
    index_name,
    ROUND(stat_value * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
FROM mysql.innodb_index_stats
WHERE database_name='your_db' AND stat_name='size'
ORDER BY stat_value DESC;
```

## 五、实战案例

### 案例1：电商订单表优化

#### 优化前

```sql
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    merchant_id BIGINT,
    status TINYINT,
    create_time DATETIME,
    update_time DATETIME,
    total_amount DECIMAL(10,2),
    -- 12个索引（过多）
    INDEX idx_user(user_id),
    INDEX idx_user_status(user_id, status),
    INDEX idx_user_time(user_id, create_time),
    INDEX idx_user_status_time(user_id, status, create_time),
    INDEX idx_merchant(merchant_id),
    INDEX idx_merchant_status(merchant_id, status),
    INDEX idx_merchant_time(merchant_id, create_time),
    INDEX idx_status(status),
    INDEX idx_status_time(status, create_time),
    INDEX idx_time(create_time),
    INDEX idx_update(update_time),
    INDEX idx_amount(total_amount)
);

-- 问题：
-- 1. 写入性能差（13个B+树维护）
-- 2. 占用空间大（索引占表的120%）
-- 3. 优化器经常选错
```

#### 优化后

```sql
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    merchant_id BIGINT,
    status TINYINT,
    create_time DATETIME,
    update_time DATETIME,
    total_amount DECIMAL(10,2),
    -- 5个索引（精简）
    INDEX idx_user_status_time(user_id, status, create_time),
    INDEX idx_merchant_status_time(merchant_id, status, create_time),
    INDEX idx_status_time(status, create_time),
    INDEX idx_time_status(create_time, status),
    INDEX idx_update(update_time)
);

-- 改进：
-- 1. 写入性能提升 70%
-- 2. 空间占用减少 60%
-- 3. 查询性能不降反升（优化器选择更准确）
```

#### 查询覆盖分析

```sql
-- 高频查询1（50%）：用户查自己订单
WHERE user_id=? ORDER BY create_time DESC
→ 使用 idx_user_status_time（最左前缀）

-- 高频查询2（30%）：商家查订单
WHERE merchant_id=? AND status=?
→ 使用 idx_merchant_status_time

-- 高频查询3（15%）：管理员按状态查
WHERE status=? AND create_time>=?
→ 使用 idx_status_time

-- 高频查询4（5%）：按时间范围查
WHERE create_time BETWEEN ? AND ?
→ 使用 idx_time_status

-- 覆盖率：100%
-- 索引数：从12个减少到5个
```

### 案例2：社交媒体帖子表

#### 分析

```sql
-- 业务特点：
-- 1. 写入非常频繁（用户发帖）
-- 2. 读取也很频繁（浏览帖子）
-- 3. 读写比约 5:1

-- 索引策略：
-- 由于写入频繁，索引要精简
INDEX(author_id, publish_time)      -- 用户时间线
INDEX(publish_time, like_count)     -- 热门内容（覆盖索引）
INDEX(topic_id, publish_time)       -- 话题浏览
-- 只保留3个高频索引，写入性能优先
```

## 六、监控和告警

### 1. 关键指标

```sql
-- 监控指标1：索引使用率
SELECT 
    index_name,
    rows_selected,
    rows_inserted,
    rows_updated,
    rows_deleted,
    ROUND(rows_selected / (rows_inserted + rows_updated + rows_deleted + 1), 2) 
        AS read_write_ratio
FROM sys.schema_index_statistics
WHERE table_name='orders'
ORDER BY rows_selected DESC;

-- 监控指标2：写入性能
SHOW STATUS LIKE 'Handler_write';
SHOW STATUS LIKE 'Innodb_rows_inserted';

-- 监控指标3：索引大小占比
-- （如前述查询）
```

### 2. 告警规则

```
告警阈值：
1. 索引总大小 > 表大小：警告
2. 索引总大小 > 表大小 * 1.5：严重
3. 单表索引数 > 15：警告
4. 单表索引数 > 20：严重
5. 写入TPS下降 > 30%：警告（可能索引过多）
6. Buffer Pool命中率 < 95%：警告
```

## 七、面试总结

**联合索引不是越多越好**，需要权衡以下因素：

**过多索引的代价**：
1. **写入性能**：每个索引都需要维护，写入放大N倍
2. **存储空间**：索引可能占表大小的50%-100%
3. **内存压力**：Buffer Pool无法完全缓存，命中率下降
4. **优化器困惑**：索引太多可能导致选择失误
5. **维护成本**：管理和优化复杂度增加

**合理数量**：
- 中小表：3-5个联合索引
- 大表：5-8个联合索引
- 总索引数（包括单列）：不超过15个

**优化策略**：
1. **索引合并**：利用最左前缀，减少冗余
2. **查询改写**：统一查询模式，减少索引需求
3. **定期审计**：删除未使用和冗余索引
4. **读写权衡**：读多写少可以多索引，反之少索引

**判断标准**：
- 覆盖核心高频查询（80%以上）
- 考虑写入性能影响
- 监控索引使用情况
- 实测性能对比

关键是找到**查询性能和写入性能的平衡点**，而不是盲目追求更多索引。

这道题考查对索引成本的全面理解和实战经验，能体现候选人的综合能力。

