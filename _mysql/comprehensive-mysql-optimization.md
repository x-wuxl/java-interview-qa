---
title: "MySQL优化（综合）"
date: 2025-11-02
categories: [MySQL, 性能优化]
tags: [MySQL, 性能优化, 索引优化, SQL优化, 架构优化, 配置优化]
description: "MySQL性能优化全景图：从SQL、索引、表设计、配置到架构，系统化的优化方法论和最佳实践"
nav_order: 356
parent: 数据库MySQL
---
# MySQL优化（综合）

## 核心概念

MySQL优化是一个**系统工程**，涵盖SQL优化、索引优化、表结构设计、配置调优、架构优化五大层面。需要遵循**"先定位、后优化、重监控"**的科学方法论，根据业务特点和数据量选择合适的优化策略。

---

## 一、优化全景图

### 优化层次（从上到下）

```
┌─────────────────────────────────────┐
│  1. SQL层优化（立竿见影）            │
│     - SQL改写、索引优化               │
├─────────────────────────────────────┤
│  2. 表设计优化（治本）               │
│     - 字段类型、范式、冗余            │
├─────────────────────────────────────┤
│  3. 配置优化（提升资源利用率）        │
│     - 内存、连接数、缓存              │
├─────────────────────────────────────┤
│  4. 架构优化（突破单机瓶颈）         │
│     - 读写分离、分库分表、缓存        │
├─────────────────────────────────────┤
│  5. 硬件优化（成本投入）             │
│     - CPU、内存、SSD                 │
└─────────────────────────────────────┘
```

---

## 二、SQL层优化（80%的性能问题）

### 1. 索引优化（核心）

#### （1）添加缺失索引
```sql
-- ❌ 未使用索引
SELECT * FROM orders WHERE user_id = 1001;
-- EXPLAIN: type=ALL, key=NULL

-- ✅ 添加索引
CREATE INDEX idx_user ON orders(user_id);
-- EXPLAIN: type=ref, key=idx_user
```

---

#### （2）联合索引设计
```sql
-- 遵循：等值查询 > 范围查询 > 排序 > 覆盖查询
CREATE INDEX idx_user_status_time ON orders(
    user_id,      -- 等值查询
    status,       -- 等值查询
    create_time   -- 排序/范围查询
);

-- 最优查询
SELECT * FROM orders 
WHERE user_id = 1001 AND status = 1 
ORDER BY create_time DESC 
LIMIT 10;
```

---

#### （3）覆盖索引（避免回表）
```sql
-- ✅ 查询字段都在索引中
SELECT id, user_id, status FROM orders 
WHERE user_id = 1001;

-- 创建覆盖索引
CREATE INDEX idx_user_status_id ON orders(user_id, status, id);
-- EXPLAIN: Extra=Using index（无回表）
```

---

### 2. 避免索引失效

| 场景 | 错误写法 | 正确写法 |
|------|---------|---------|
| **函数操作** | `WHERE YEAR(create_time)=2025` | `WHERE create_time >= '2025-01-01'` |
| **隐式转换** | `WHERE user_id = '1001'`（INT字段） | `WHERE user_id = 1001` |
| **前缀模糊** | `WHERE name LIKE '%张%'` | `WHERE name LIKE '张%'` 或全文索引 |
| **OR条件** | `WHERE a=1 OR b=2`（b无索引） | 改为UNION或为b加索引 |
| **不等于** | `WHERE status != 1` | `WHERE status IN (0,2,3)` |
| **IS NOT NULL** | `WHERE name IS NOT NULL` | 避免NULL或使用默认值 |

---

### 3. SQL改写优化

#### （1）分页优化
```sql
-- ❌ 深度分页
SELECT * FROM orders ORDER BY id LIMIT 1000000, 20;

-- ✅ 主键定位
SELECT * FROM orders WHERE id > 1000000 ORDER BY id LIMIT 20;

-- ✅ 延迟关联
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders ORDER BY id LIMIT 1000000, 20
) t ON o.id = t.id;
```

---

#### （2）避免SELECT *
```sql
-- ❌ 查询不必要的字段
SELECT * FROM orders WHERE id = 1001;

-- ✅ 按需查询
SELECT id, user_id, amount, create_time FROM orders WHERE id = 1001;
```

---

#### （3）优化IN查询
```sql
-- ❌ IN列表过大
SELECT * FROM orders WHERE user_id IN (1,2,3,...,10000);

-- ✅ 拆分为多个小批次
-- 或使用临时表关联
CREATE TEMPORARY TABLE temp_user_ids (user_id INT);
INSERT INTO temp_user_ids VALUES (1),(2),(3),...;
SELECT o.* FROM orders o INNER JOIN temp_user_ids t ON o.user_id = t.user_id;
```

---

#### （4）优化子查询
```sql
-- ❌ 非相关子查询可能执行多次
SELECT * FROM orders WHERE user_id IN (
    SELECT id FROM users WHERE status = 1
);

-- ✅ 改为JOIN
SELECT o.* FROM orders o
INNER JOIN users u ON o.user_id = u.id
WHERE u.status = 1;
```

---

### 4. 减少锁竞争

```sql
-- ❌ 长事务
BEGIN;
SELECT * FROM orders WHERE id = 1001 FOR UPDATE;
-- ... 业务逻辑（耗时）
UPDATE orders SET status = 1 WHERE id = 1001;
COMMIT;

-- ✅ 缩短事务
-- 1. 业务逻辑放事务外
-- 2. 只锁必要的行
UPDATE orders SET status = 1 WHERE id = 1001;
```

---

## 三、表设计优化

### 1. 字段类型选择

#### （1）数值类型
```sql
-- ❌ 使用过大类型
user_id BIGINT      -- 最大支持2^63，实际只有100万用户

-- ✅ 使用合适类型
user_id INT         -- 最大21亿，节省4字节
age TINYINT         -- 0-255，节省3字节
is_deleted TINYINT(1)  -- 布尔值
```

---

#### （2）字符串类型
```sql
-- ❌ 使用过长VARCHAR
name VARCHAR(255)   -- 实际最多20个字符

-- ✅ 精确定义长度
name VARCHAR(50)    -- 节省索引空间

-- ✅ 固定长度用CHAR
country_code CHAR(2)  -- 'CN', 'US'
mobile CHAR(11)       -- 手机号固定11位
```

---

#### （3）时间类型
```sql
-- ❌ 使用VARCHAR存储时间
create_time VARCHAR(20)  -- '2025-11-02 10:00:00'

-- ✅ 使用DATETIME/TIMESTAMP
create_time DATETIME      -- 范围：1000-9999年
update_time TIMESTAMP     -- 自动更新，范围：1970-2038年

-- ✅ 时间戳场景用INT
create_timestamp INT UNSIGNED  -- 节省空间，适合大数据
```

---

### 2. 范式与反范式

#### （1）适度冗余
```sql
-- ❌ 过度范式化（需要JOIN）
SELECT o.id, u.name FROM orders o
JOIN users u ON o.user_id = u.id;

-- ✅ 冗余常用字段
CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    user_name VARCHAR(50),  -- 冗余用户名
    INDEX idx_user(user_id)
);

-- 查询无需JOIN
SELECT id, user_name FROM orders WHERE user_id = 1001;
```

---

#### （2）垂直拆分（大字段分离）
```sql
-- ❌ 大字段和小字段混在一起
CREATE TABLE articles (
    id INT PRIMARY KEY,
    title VARCHAR(255),
    content LONGTEXT,      -- 大字段
    author VARCHAR(50),
    create_time DATETIME
);

-- ✅ 拆分为两张表
CREATE TABLE articles (
    id INT PRIMARY KEY,
    title VARCHAR(255),
    author VARCHAR(50),
    create_time DATETIME
);

CREATE TABLE article_contents (
    article_id INT PRIMARY KEY,
    content LONGTEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
```

---

### 3. 分区表

```sql
-- 按时间分区（适合日志、订单等历史数据）
CREATE TABLE orders (
    id BIGINT,
    user_id INT,
    create_time DATETIME,
    INDEX idx_user(user_id)
) PARTITION BY RANGE (YEAR(create_time)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- 查询时自动剪枝
SELECT * FROM orders WHERE create_time >= '2025-01-01';
-- 只扫描p2025和p_future分区
```

---

## 四、配置优化

### 1. InnoDB配置

```ini
[mysqld]
# ========== 内存配置 ==========
# 缓冲池大小（物理内存的60-80%）
innodb_buffer_pool_size = 8G

# 缓冲池实例数（提升并发）
innodb_buffer_pool_instances = 8

# 日志缓冲区
innodb_log_buffer_size = 16M

# ========== 日志配置 ==========
# 重做日志文件大小
innodb_log_file_size = 1G

# 日志刷盘策略（1=最安全，2=性能优先）
innodb_flush_log_at_trx_commit = 2

# Binlog刷盘策略
sync_binlog = 0

# ========== 并发配置 ==========
# 最大连接数
max_connections = 1000

# 线程缓存
thread_cache_size = 128

# ========== IO配置 ==========
# IO线程数
innodb_read_io_threads = 8
innodb_write_io_threads = 8

# 异步IO
innodb_use_native_aio = ON
```

---

### 2. 查询缓存（MySQL 5.7，8.0已移除）

```ini
# MySQL 5.7及以前
query_cache_type = ON
query_cache_size = 256M
query_cache_limit = 2M
```

**注意**：MySQL 8.0已移除查询缓存，推荐使用Redis等外部缓存。

---

### 3. 慢查询日志

```ini
[mysqld]
# 开启慢查询日志
slow_query_log = ON
slow_query_log_file = /var/log/mysql/slow.log

# 慢查询阈值（2秒）
long_query_time = 2

# 记录未使用索引的查询
log_queries_not_using_indexes = ON
```

---

## 五、架构优化

### 1. 读写分离

```
        ┌──────────┐
        │  应用层  │
        └────┬─────┘
             │
      ┌──────┴──────┐
      │  写（主库） │  读（从库）
      │             │
  ┌───▼───┐    ┌───▼───┐  ┌────────┐
  │ Master│───>│ Slave1│  │ Slave2 │
  └───────┘    └───────┘  └────────┘
       │            │          │
       └────────────┴──────────┘
            主从同步
```

**实现**：
```java
@Service
public class OrderService {
    
    @Autowired
    private DataSource masterDB;  // 主库
    
    @Autowired
    private DataSource slaveDB;   // 从库
    
    @Transactional
    public void createOrder(Order order) {
        masterDB.insert(order);  // 写主库
    }
    
    public Order getOrder(Long id) {
        return slaveDB.select(id);  // 读从库
    }
}
```

---

### 2. 分库分表

#### 垂直拆分（按业务）
```
原始库：shop_db
├── users（用户表）
├── products（商品表）
├── orders（订单表）
└── payments（支付表）

拆分后：
├── user_db（用户库）
│   └── users
├── product_db（商品库）
│   └── products
└── order_db（订单库）
    ├── orders
    └── payments
```

---

#### 水平拆分（按数据）
```
订单表（单表1亿数据）

拆分为1024张表：
orders_0000, orders_0001, ..., orders_1023

路由规则：
table_index = user_id % 1024
```

**ShardingSphere示例**：
```yaml
shardingsphere:
  sharding:
    tables:
      orders:
        actual-data-nodes: ds0.orders_$->{0..1023}
        table-strategy:
          standard:
            sharding-column: user_id
            sharding-algorithm-name: orders_inline
    sharding-algorithms:
      orders_inline:
        type: INLINE
        props:
          algorithm-expression: orders_$->{user_id % 1024}
```

---

### 3. 缓存架构

```
            ┌──────────┐
            │  应用层  │
            └────┬─────┘
                 │
          ┌──────┴──────┐
          │ Redis缓存    │
          └──────┬───────┘
                 │ 缓存未命中
          ┌──────▼──────┐
          │   MySQL     │
          └─────────────┘
```

**多级缓存**：
```java
@Service
public class OrderService {
    
    @Autowired
    private RedisTemplate redis;
    
    @Autowired
    private OrderRepository orderRepo;
    
    public Order getOrder(Long id) {
        // 1. 查本地缓存（Caffeine）
        Order order = localCache.get(id);
        if (order != null) return order;
        
        // 2. 查Redis
        order = redis.get("order:" + id);
        if (order != null) {
            localCache.put(id, order);
            return order;
        }
        
        // 3. 查数据库
        order = orderRepo.findById(id);
        if (order != null) {
            redis.set("order:" + id, order, 3600);
            localCache.put(id, order);
        }
        
        return order;
    }
}
```

---

## 六、监控与诊断

### 1. 性能监控指标

```sql
-- 查看当前连接数
SHOW STATUS LIKE 'Threads_connected';

-- 查看QPS（每秒查询数）
SHOW GLOBAL STATUS LIKE 'Questions';

-- 查看TPS（每秒事务数）
SHOW GLOBAL STATUS LIKE 'Com_commit';
SHOW GLOBAL STATUS LIKE 'Com_rollback';

-- 查看缓冲池命中率
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';
-- 命中率 = (1 - Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests) * 100%

-- 查看慢查询数量
SHOW GLOBAL STATUS LIKE 'Slow_queries';
```

---

### 2. 使用监控工具

- **Prometheus + Grafana**：开源监控方案
- **Percona Monitoring and Management (PMM)**：专业MySQL监控
- **阿里云RDS/腾讯云CDB**：云厂商自带监控
- **MySQL Enterprise Monitor**：官方商业监控

---

## 七、优化流程

```
1. 发现问题
   ├─ 慢查询日志
   ├─ 监控告警
   └─ 用户反馈

2. 分析定位
   ├─ EXPLAIN分析
   ├─ SHOW PROCESSLIST
   └─ Performance Schema

3. 制定方案
   ├─ 索引优化（优先）
   ├─ SQL改写
   ├─ 表结构调整
   └─ 架构优化

4. 执行优化
   ├─ 开发环境测试
   ├─ 灰度发布
   └─ 全量上线

5. 效果验证
   ├─ EXPLAIN对比
   ├─ 压测验证
   └─ 监控观察

6. 持续监控
   └─ 定期Review慢查询
```

---

## 八、面试答题要点

1. **分层优化**：SQL → 表设计 → 配置 → 架构，优先级递减
2. **80/20原则**：80%性能问题在SQL和索引层
3. **核心手段**：索引优化、SQL改写、读写分离、分库分表
4. **监控先行**：没有监控就没有优化依据
5. **业务结合**：技术方案要结合实际业务场景

---

## 九、优化案例总结

### 案例1：电商订单查询优化
**问题**：订单列表查询慢（5秒）  
**方案**：创建联合索引`idx_user_time(user_id, create_time)`  
**效果**：5秒 → 0.05秒（100倍提升）

---

### 案例2：商品搜索优化
**问题**：`LIKE '%关键词%'`全表扫描  
**方案**：引入Elasticsearch全文搜索  
**效果**：5秒 → 0.01秒（500倍提升）

---

### 案例3：高并发秒杀优化
**问题**：数据库并发连接打满  
**方案**：Redis缓存 + 消息队列削峰  
**效果**：QPS从5000提升到50000

---

## 总结

MySQL优化是一个系统工程，需要从SQL、索引、表设计、配置、架构五个层面综合考虑。**优先从SQL和索引层优化（低成本高收益）**，单机瓶颈后考虑读写分离、分库分表等架构方案。核心是**先监控定位问题，再针对性优化，最后持续监控效果**。面试中能系统讲解优化方法论，并结合实际案例说明优化效果，体现全栈的数据库优化能力。

