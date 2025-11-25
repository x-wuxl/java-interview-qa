---
layout: default
title: "慢SQL的问题如何排查？"
parent: 数据库MySQL
nav_order: 345
description: "从发现到定位再到解决，详解慢SQL问题的完整排查流程和实战技巧"
date: 2025-11-02
---
# 慢SQL的问题如何排查？

## 核心概念

慢SQL排查是从**发现异常→收集证据→定位根因→验证优化**的系统化故障诊断过程，需要结合监控工具、执行计划分析、系统资源检查等多维度手段。

---

## 一、发现慢SQL（问题识别）

### 方法1：开启慢查询日志
```sql
-- 查看慢查询配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 开启慢查询日志
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 2;  -- 超过2秒记录
SET GLOBAL log_queries_not_using_indexes = ON;  -- 记录未使用索引的查询
```

**慢查询日志位置**（默认）：
```bash
/var/lib/mysql/hostname-slow.log
```

---

### 方法2：实时监控正在执行的查询
```sql
-- 查看当前所有连接和执行状态
SHOW FULL PROCESSLIST;
```

**关键字段**：
- `Time`：SQL已执行时长（秒）
- `State`：当前状态（Sending data、Sorting result等）
- `Info`：正在执行的SQL语句

**发现慢查询后立即操作**：
```sql
-- 杀掉慢查询（慎用）
KILL QUERY 线程ID;
```

---

### 方法3：使用性能监控工具

#### （1）Performance Schema（MySQL 5.7+）
```sql
-- 开启性能监控
UPDATE performance_schema.setup_instruments 
SET ENABLED = 'YES', TIMED = 'YES' 
WHERE NAME LIKE 'statement/%';

-- 查询最慢的10条SQL
SELECT 
    DIGEST_TEXT AS query,
    COUNT_STAR AS exec_count,
    AVG_TIMER_WAIT/1000000000000 AS avg_time_sec,
    MAX_TIMER_WAIT/1000000000000 AS max_time_sec
FROM performance_schema.events_statements_summary_by_digest
ORDER BY AVG_TIMER_WAIT DESC
LIMIT 10;
```

#### （2）第三方工具
- **mysqldumpslow**：分析慢查询日志
  ```bash
  mysqldumpslow -s t -t 10 /var/lib/mysql/slow.log
  ```
- **pt-query-digest**：Percona工具包
  ```bash
  pt-query-digest /var/lib/mysql/slow.log > report.txt
  ```

---

## 二、分析慢SQL（定位根因）

### 步骤1：执行计划分析
```sql
EXPLAIN SELECT * FROM orders 
WHERE user_id = 1001 AND status = 1 
ORDER BY create_time DESC 
LIMIT 10;
```

**重点检查**：
| 指标 | 问题标志 | 常见原因 |
|------|---------|---------|
| **type** | ALL / index | 未使用索引或索引失效 |
| **key** | NULL | 没有合适的索引 |
| **rows** | 数万/数百万 | 扫描行数过多 |
| **Extra** | Using filesort | 排序未走索引 |
| **Extra** | Using temporary | 使用临时表（GROUP BY） |
| **Extra** | Using join buffer | JOIN未使用索引 |

---

### 步骤2：检查索引情况
```sql
-- 查看表的索引
SHOW INDEX FROM orders;

-- 查看索引使用统计
SELECT * FROM sys.schema_unused_indexes WHERE object_schema = 'your_db';

-- 查看索引基数（区分度）
SHOW INDEX FROM orders WHERE Key_name = 'idx_user_id';
```

**常见索引问题**：
1. **缺少索引**：WHERE、JOIN、ORDER BY字段未建索引
2. **索引失效**：函数操作、隐式转换、LIKE '%xxx'
3. **索引选择错误**：MySQL选择了次优索引
4. **索引碎片**：长期增删导致索引膨胀

---

### 步骤3：分析SQL本身问题
```sql
-- 检查是否有以下问题：
```

#### （1）SELECT * 查询不必要字段
```sql
-- ❌ 查询大字段
SELECT * FROM articles WHERE id = 1001;  -- content字段10MB

-- ✅ 按需查询
SELECT id, title, author FROM articles WHERE id = 1001;
```

#### （2）深度分页
```sql
-- ❌ 偏移量过大
SELECT * FROM orders ORDER BY id LIMIT 1000000, 20;
```

#### （3）未优化的JOIN
```sql
-- ❌ 关联字段未加索引
SELECT * FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE u.status = 1;
```

#### （4）隐式类型转换
```sql
-- ❌ user_id是INT，但传入字符串
WHERE user_id = '1001'  -- 索引失效

-- ✅ 类型匹配
WHERE user_id = 1001
```

---

### 步骤4：检查系统资源
```sql
-- 查看当前数据库状态
SHOW STATUS LIKE 'Threads%';
SHOW STATUS LIKE 'Innodb_buffer_pool%';

-- 查看锁等待情况
SHOW ENGINE INNODB STATUS;

-- 查看表锁
SHOW OPEN TABLES WHERE In_use > 0;
```

**系统层面检查**：
```bash
# CPU使用率
top

# 磁盘IO
iostat -x 1

# 内存使用
free -h

# MySQL连接数
mysql> SHOW VARIABLES LIKE 'max_connections';
mysql> SHOW STATUS LIKE 'Threads_connected';
```

---

## 三、常见慢SQL场景及排查重点

### 场景1：突然变慢（之前正常）
**排查方向**：
- 数据量激增 → 检查表行数、索引统计信息
- 索引失效 → 执行`ANALYZE TABLE`更新统计信息
- 锁等待 → 检查长事务、死锁
- 系统资源 → CPU、内存、磁盘IO

```sql
-- 更新索引统计信息
ANALYZE TABLE orders;

-- 重建索引
ALTER TABLE orders DROP INDEX idx_user_id, ADD INDEX idx_user_id(user_id);
```

---

### 场景2：一直很慢（历史问题）
**排查方向**：
- 缺少索引 → EXPLAIN查看key是否为NULL
- 索引设计不合理 → 检查联合索引顺序
- SQL写法问题 → 函数操作、深度分页等
- 表结构问题 → 单表数据量过大

---

### 场景3：偶尔慢（间歇性）
**排查方向**：
- 业务高峰期 → 并发量激增
- 慢查询阻塞 → 某个大事务占用资源
- 主从同步延迟 → 从库读取到旧数据
- 缓存失效 → 缓存雪崩导致大量请求打到DB

```sql
-- 查看主从延迟
SHOW SLAVE STATUS\G
-- 重点看：Seconds_Behind_Master
```

---

## 四、排查实战案例

### 案例：订单查询慢SQL
**问题SQL**：
```sql
SELECT * FROM orders 
WHERE user_id = 1001 AND create_time > '2025-01-01'
ORDER BY create_time DESC
LIMIT 10;
```

**排查步骤**：

#### 1️⃣ EXPLAIN分析
```sql
EXPLAIN ...;
```
结果：
```
type: ref
key: idx_user_id
rows: 50000
Extra: Using where; Using filesort
```

**问题识别**：
- 虽然使用了索引`idx_user_id`，但扫描了5万行
- `Using filesort`说明排序未走索引

---

#### 2️⃣ 检查索引
```sql
SHOW INDEX FROM orders;
```
发现只有单列索引`idx_user_id`，缺少联合索引。

---

#### 3️⃣ 优化方案
```sql
-- 创建联合索引（等值查询 + 范围查询 + 排序）
CREATE INDEX idx_user_time ON orders(user_id, create_time);
```

---

#### 4️⃣ 验证效果
```sql
EXPLAIN ...;
```
结果：
```
type: range
key: idx_user_time
rows: 150
Extra: Using index condition
```

**性能提升**：
- 扫描行数：50000 → 150（减少99.7%）
- 执行时间：3.2s → 0.05s

---

## 五、排查工具对比

| 工具 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **慢查询日志** | 定位历史慢SQL | 全量记录 | 影响性能，日志占空间 |
| **SHOW PROCESSLIST** | 实时发现慢SQL | 实时诊断 | 需要人工盯盘 |
| **Performance Schema** | 全面性能分析 | 数据详细 | 配置复杂，有性能开销 |
| **pt-query-digest** | 慢日志分析 | 报告专业 | 需额外安装 |
| **监控平台** | 持续监控告警 | 自动化 | 需搭建平台 |

---

## 面试答题要点

1. **先发现后分析**：通过慢查询日志、SHOW PROCESSLIST定位慢SQL
2. **EXPLAIN是核心**：重点看type、key、rows、Extra
3. **分层排查**：SQL层（索引、写法）→ 系统层（资源、锁）
4. **对比分析**：突然变慢vs一直慢，排查方向不同
5. **验证效果**：优化后用EXPLAIN和实际执行验证

---

## 总结

慢SQL排查遵循**"发现→分析→定位→优化→验证"**五步法，核心工具是慢查询日志+EXPLAIN+SHOW PROCESSLIST。80%的慢SQL是索引问题，需重点检查索引是否存在、是否失效、是否被正确使用。面试中能结合实际案例快速定位问题并给出解决方案，是数据库优化能力的体现。

