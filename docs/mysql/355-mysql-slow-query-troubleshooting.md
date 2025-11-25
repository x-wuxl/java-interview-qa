---
layout: default
title: "MySQL慢查询的排除与优化"
parent: 数据库MySQL
nav_order: 355
description: "从故障应急角度详解MySQL慢查询的快速排查与处理流程，包含完整的诊断checklist和应急方案"
date: 2025-11-02
---
# MySQL慢查询的排除与优化

## 核心概念

慢查询排除是在**生产环境突发慢查询问题**时，通过系统化的排查手段，快速**定位根因、实施应急方案、恢复业务、彻底解决**的完整流程。核心是**快速止血 + 根因分析 + 长效优化**。

---

## 一、应急处理流程（生产环境）

### 黄金30分钟处理流程

```
┌──────────────────────────┐
│ 0-5分钟：快速评估         │
│ - 影响范围？              │
│ - 是否需要紧急回滚？       │
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│ 5-15分钟：止血措施        │
│ - 杀掉慢查询              │
│ - 限流/降级               │
│ - 临时索引                │
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│ 15-30分钟：根因定位       │
│ - EXPLAIN分析             │
│ - 日志分析                │
│ - 代码审查                │
└────────────┬─────────────┘
             │
┌────────────▼─────────────┐
│ 30分钟后：长效方案        │
│ - 优化索引                │
│ - 改写SQL                 │
│ - 架构调整                │
└──────────────────────────┘
```

---

## 二、快速诊断Checklist

### Step 1：确认是否真的慢（5分钟）

#### 1.1 查看当前正在执行的查询
```sql
-- 查看所有连接
SHOW FULL PROCESSLIST;
```

**关键字段**：
- `Time`：执行时长（秒）
- `State`：当前状态
- `Info`：正在执行的SQL

**判断标准**：
```
Time > 10秒 且 State != 'Sleep'  → 慢查询
Command = 'Query' 且 Info包含复杂SQL → 重点关注
```

---

#### 1.2 查看慢查询统计
```sql
-- 查看慢查询总数
SHOW GLOBAL STATUS LIKE 'Slow_queries';

-- 查看最近1小时增量
-- （记录当前值，1小时后再查看）
```

---

### Step 2：识别问题类型（10分钟）

#### 2.1 SQL问题
```sql
-- 查看具体的慢SQL
SELECT * FROM mysql.slow_log 
ORDER BY start_time DESC 
LIMIT 10;

-- 或查看慢查询日志文件
tail -f /var/log/mysql/slow.log
```

**常见特征**：
- 单条SQL执行时间长
- 特定SQL反复出现
- 新上线功能相关

---

#### 2.2 锁等待问题
```sql
-- 查看锁等待
SELECT * FROM information_schema.INNODB_LOCKS;

-- 查看锁等待事务
SELECT * FROM information_schema.INNODB_LOCK_WAITS;

-- 查看事务状态
SELECT * FROM information_schema.INNODB_TRX 
WHERE trx_state = 'LOCK WAIT';
```

**常见特征**：
- State显示`Locked`
- 多个查询等待同一资源
- 某个长事务未提交

---

#### 2.3 系统资源问题
```bash
# CPU使用率
top
# 重点看 %CPU 和 load average

# 磁盘IO
iostat -x 1
# 重点看 %util（接近100%表示IO饱和）

# 内存使用
free -h

# MySQL连接数
mysql> SHOW STATUS LIKE 'Threads_connected';
mysql> SHOW VARIABLES LIKE 'max_connections';
```

**常见特征**：
- CPU持续100%
- IO等待时间长（%iowait高）
- 内存不足，频繁swap
- 连接数打满

---

### Step 3：执行计划分析（5分钟）

```sql
-- 对慢SQL执行EXPLAIN
EXPLAIN SELECT * FROM orders WHERE user_id = 1001;
```

**快速判断问题**：

| 指标 | 正常 | 异常 | 处理 |
|------|------|------|------|
| **type** | ref/range | ALL/index | 加索引 |
| **key** | 有值 | NULL | 加索引 |
| **rows** | <1000 | >100000 | 优化条件 |
| **Extra** | Using index | Using filesort | 优化排序 |
| **Extra** | - | Using temporary | 优化GROUP BY |

---

## 三、应急止血方案

### 方案1：立即杀掉慢查询（最快）

```sql
-- 1. 找到慢查询的线程ID
SHOW PROCESSLIST;

-- 2. 杀掉慢查询
KILL QUERY 线程ID;  -- 只杀查询，保留连接
-- 或
KILL 线程ID;        -- 杀掉整个连接
```

**适用场景**：
- 单条SQL异常慢
- 影响其他业务
- 需要立即恢复

**注意事项**：
- ⚠️ 可能导致事务回滚
- ⚠️ 需要确认业务影响

---

### 方案2：临时限流/降级（5-10分钟）

#### 应用层限流
```java
@Service
public class OrderService {
    
    // Guava限流器
    private final RateLimiter rateLimiter = RateLimiter.create(100);  // 100 QPS
    
    public List<Order> queryOrders(Long userId) {
        // 限流
        if (!rateLimiter.tryAcquire(1, TimeUnit.SECONDS)) {
            throw new BusinessException("系统繁忙，请稍后重试");
        }
        
        return orderRepository.findByUserId(userId);
    }
}
```

---

#### 服务降级
```java
@Service
public class OrderService {
    
    @Autowired
    private RedisTemplate redis;
    
    @Autowired
    private OrderRepository orderRepo;
    
    public List<Order> queryOrders(Long userId) {
        // 降级开关（Redis）
        if (redis.get("order:degrade") != null) {
            // 返回缓存或默认数据
            return getCachedOrders(userId);
        }
        
        return orderRepo.findByUserId(userId);
    }
}
```

---

### 方案3：临时添加索引（15-30分钟）

```sql
-- 紧急添加索引（在线DDL，不锁表）
ALTER TABLE orders 
ADD INDEX idx_user_id_temp (user_id) 
ALGORITHM=INPLACE, LOCK=NONE;

-- MySQL 5.6+支持在线DDL
-- ALGORITHM=INPLACE：原地修改，不创建临时表
-- LOCK=NONE：不锁表，允许并发读写
```

**注意事项**：
- ✅ 在线DDL不影响业务
- ⚠️ 大表添加索引仍需时间（监控进度）
- ⚠️ 临时索引后续需评估是否保留

---

### 方案4：修改慢查询阈值（临时缓解）

```sql
-- 临时提高慢查询阈值（治标不治本）
SET GLOBAL long_query_time = 10;  -- 改为10秒

-- 或关闭慢查询日志（极端情况）
SET GLOBAL slow_query_log = OFF;
```

**适用场景**：
- 慢查询日志过多，影响性能
- 临时缓解，后续需彻底优化

---

## 四、根因排查详解

### 原因1：新上线代码引入慢SQL

#### 排查方法
```bash
# 1. 查看最近部署时间
git log --since="1 day ago"

# 2. 对比慢查询日志时间和部署时间

# 3. 审查新SQL
grep -r "SELECT.*FROM orders" src/
```

#### 应急方案
```bash
# 立即回滚到上一版本
kubectl rollout undo deployment/order-service
```

---

### 原因2：数据量激增

#### 排查方法
```sql
-- 查看表数据量
SELECT 
    table_name,
    table_rows,
    data_length / 1024 / 1024 AS data_mb
FROM information_schema.TABLES
WHERE table_schema = 'your_db'
ORDER BY table_rows DESC;

-- 对比历史数据
-- （需要提前记录）
```

#### 解决方案
```sql
-- 1. 清理历史数据
DELETE FROM orders WHERE create_time < '2020-01-01';

-- 2. 分区表（针对时间范围查询）
ALTER TABLE orders PARTITION BY RANGE (YEAR(create_time)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026)
);

-- 3. 归档历史数据
-- 迁移到历史库
```

---

### 原因3：索引失效

#### 排查方法
```sql
-- 查看索引统计信息是否过期
SHOW INDEX FROM orders;
-- 重点看：Cardinality（基数）

-- 更新索引统计
ANALYZE TABLE orders;

-- 再次EXPLAIN
EXPLAIN SELECT * FROM orders WHERE user_id = 1001;
```

#### 常见失效场景
```sql
-- 1. 函数操作
WHERE DATE(create_time) = '2025-11-02'

-- 2. 隐式转换
WHERE user_id = '1001'  -- user_id是INT

-- 3. OR条件
WHERE user_id = 1001 OR status = 1  -- status无索引

-- 4. NOT IN / != 
WHERE status != 1
```

---

### 原因4：锁等待/死锁

#### 排查方法
```sql
-- 查看当前锁等待
SELECT 
    r.trx_id AS waiting_trx_id,
    r.trx_mysql_thread_id AS waiting_thread,
    r.trx_query AS waiting_query,
    b.trx_id AS blocking_trx_id,
    b.trx_mysql_thread_id AS blocking_thread,
    b.trx_query AS blocking_query
FROM information_schema.INNODB_LOCK_WAITS w
INNER JOIN information_schema.INNODB_TRX r ON w.requesting_trx_id = r.trx_id
INNER JOIN information_schema.INNODB_TRX b ON w.blocking_trx_id = b.trx_id;

-- 查看死锁日志
SHOW ENGINE INNODB STATUS\G
-- 查看LATEST DETECTED DEADLOCK部分
```

#### 解决方案
```sql
-- 1. 杀掉阻塞线程
KILL 阻塞线程ID;

-- 2. 优化事务
-- - 缩短事务时间
-- - 统一锁顺序
-- - 降低隔离级别（慎重）
```

---

### 原因5：参数配置不当

#### 排查方法
```sql
-- 查看关键配置
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
SHOW VARIABLES LIKE 'max_connections';
SHOW VARIABLES LIKE 'sort_buffer_size';

-- 查看缓冲池命中率
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';
-- 命中率 = (1 - reads / read_requests) * 100%
```

#### 优化建议
```ini
[mysqld]
# 缓冲池（物理内存的60-80%）
innodb_buffer_pool_size = 8G

# 连接数
max_connections = 1000

# 日志缓冲
innodb_log_buffer_size = 16M

# 日志刷盘（性能优先）
innodb_flush_log_at_trx_commit = 2
sync_binlog = 0
```

---

## 五、长效优化方案

### 1. 索引优化（优先）

```sql
-- 基于慢查询日志，分析高频查询
pt-query-digest /var/log/mysql/slow.log

-- 创建联合索引
CREATE INDEX idx_combined ON orders(
    user_id,      -- WHERE条件
    status,       -- WHERE条件
    create_time   -- ORDER BY
);
```

---

### 2. SQL改写

```sql
-- ❌ 原始SQL
SELECT * FROM orders 
WHERE DATE(create_time) = '2025-11-02'
ORDER BY amount DESC
LIMIT 1000000, 20;

-- ✅ 优化后
SELECT id, user_id, amount, create_time FROM orders 
WHERE create_time >= '2025-11-02 00:00:00' 
  AND create_time < '2025-11-03 00:00:00'
  AND id > 1000000
ORDER BY id DESC
LIMIT 20;
```

---

### 3. 读写分离

```yaml
# MyBatis配置
spring:
  datasource:
    master:
      url: jdbc:mysql://master:3306/db
      username: root
      password: xxx
    slave:
      url: jdbc:mysql://slave:3306/db
      username: readonly
      password: xxx

# 读写路由
@Transactional
public void createOrder(Order order) {
    masterDB.insert(order);  // 写主库
}

public Order getOrder(Long id) {
    return slaveDB.select(id);  // 读从库
}
```

---

### 4. 引入缓存

```java
@Service
public class OrderService {
    
    @Autowired
    private RedisTemplate redis;
    
    @Autowired
    private OrderRepository orderRepo;
    
    @Cacheable(value = "order", key = "#id", expire = 3600)
    public Order getOrder(Long id) {
        return orderRepo.findById(id);
    }
    
    @CacheEvict(value = "order", key = "#order.id")
    public void updateOrder(Order order) {
        orderRepo.update(order);
    }
}
```

---

## 六、预防措施

### 1. 上线前SQL审核

```java
// SQL审核工具（Sonar插件、阿里巴巴p3c等）

// 审核要点：
// ✅ 所有WHERE字段有索引
// ✅ 无SELECT *
// ✅ 无LIMIT深度分页
// ✅ 无前缀通配符LIKE '%xxx'
// ✅ 无函数操作索引字段
```

---

### 2. 定期Review慢查询

```bash
# 每周分析慢查询日志
pt-query-digest /var/log/mysql/slow.log > weekly_report.txt

# 优化TOP 10慢查询
```

---

### 3. 监控告警

```yaml
# Prometheus告警规则
- alert: SlowQueryHigh
  expr: rate(mysql_global_status_slow_queries[5m]) > 10
  for: 5m
  annotations:
    summary: "慢查询过多（>10/s）"

- alert: ConnectionHigh
  expr: mysql_global_status_threads_connected > 800
  for: 1m
  annotations:
    summary: "连接数过高（>800）"
```

---

## 七、故障复盘模板

### 复盘报告结构

```markdown
# 慢查询故障复盘

## 1. 故障概述
- 发生时间：2025-11-02 10:00
- 影响范围：订单查询接口响应时间从0.1s增加到8s
- 故障时长：30分钟

## 2. 根因分析
- 新上线代码引入慢SQL
- 未建索引导致全表扫描
- EXPLAIN分析：type=ALL, rows=5000000

## 3. 应急处理
- 10:05 回滚到上一版本
- 10:10 业务恢复正常

## 4. 根治方案
- 添加索引：idx_user_time(user_id, create_time)
- SQL改写：避免SELECT *
- 执行时间优化：8s → 0.05s

## 5. 改进措施
- 上线前SQL审核
- 完善监控告警
- 定期Review慢查询

## 6. 经验总结
- 索引是性能关键
- 监控告警要完善
- 应急预案要演练
```

---

## 八、面试答题要点

1. **应急流程**：快速评估 → 止血措施 → 根因定位 → 长效优化
2. **诊断工具**：SHOW PROCESSLIST、EXPLAIN、慢查询日志
3. **止血方案**：杀慢查询、限流降级、临时索引
4. **根因分析**：新代码、数据激增、索引失效、锁等待、配置不当
5. **预防措施**：SQL审核、定期Review、监控告警

---

## 九、快速参考卡

### 常用诊断命令
```sql
-- 查看慢查询
SHOW PROCESSLIST;
SHOW GLOBAL STATUS LIKE 'Slow_queries';

-- 分析SQL
EXPLAIN SELECT ...;

-- 查看锁
SHOW ENGINE INNODB STATUS\G
SELECT * FROM information_schema.INNODB_LOCKS;

-- 查看配置
SHOW VARIABLES LIKE 'innodb%';

-- 查看统计
SHOW STATUS LIKE 'Innodb_buffer_pool%';
```

---

### 紧急操作
```sql
-- 杀慢查询
KILL QUERY 线程ID;

-- 添加索引（在线）
ALTER TABLE t ADD INDEX idx(col) ALGORITHM=INPLACE, LOCK=NONE;

-- 更新统计
ANALYZE TABLE t;

-- 修改配置（临时）
SET GLOBAL long_query_time = 10;
```

---

## 总结

慢查询排除遵循**"快速止血 → 根因分析 → 长效优化 → 预防复发"**四步法。生产环境应急时，优先恢复业务（杀查询、限流、回滚），再定位根因（EXPLAIN、日志、锁等待），最后实施长效方案（加索引、改SQL、架构优化）。完善的监控告警和定期Review是预防慢查询的关键。面试中能系统讲解应急流程和诊断方法，并结合故障复盘展示实战经验，体现生产环境问题处理能力。

