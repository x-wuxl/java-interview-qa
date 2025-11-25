---
title: "MySQL索引建立与性能影响"
date: 2025-11-02
description: "详解MySQL如何建立索引、索引过多的缺点及其对读写性能的影响"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 索引设计, 性能优化, 数据库调优, 索引管理]
nav_order: 293
parent: 数据库MySQL
---
## 问题

MySQL如何建立索引？索引建太多的缺点？影响读还是写效率

## 答案

## 一、MySQL如何建立索引

### 1. 创建索引的语法

#### 1.1 创建表时定义索引

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,        -- 主键索引
    username VARCHAR(50) NOT NULL UNIQUE,        -- 唯一索引
    email VARCHAR(100) NOT NULL,
    age INT,
    city VARCHAR(50),
    create_time DATETIME,

    INDEX idx_age (age),                         -- 普通索引
    INDEX idx_city_age (city, age),              -- 联合索引
    UNIQUE KEY uk_email (email),                 -- 唯一索引
    FULLTEXT INDEX ft_username (username)        -- 全文索引（MyISAM/InnoDB 5.6+）
) ENGINE=InnoDB;
```

#### 1.2 在已有表上创建索引

**方式1：CREATE INDEX**
```sql
-- 创建普通索引
CREATE INDEX idx_age ON users(age);

-- 创建唯一索引
CREATE UNIQUE INDEX uk_email ON users(email);

-- 创建联合索引
CREATE INDEX idx_city_age_time ON users(city, age, create_time);

-- 创建全文索引
CREATE FULLTEXT INDEX ft_username ON users(username);
```

**方式2：ALTER TABLE**
```sql
-- 添加普通索引
ALTER TABLE users ADD INDEX idx_age (age);

-- 添加唯一索引
ALTER TABLE users ADD UNIQUE KEY uk_email (email);

-- 添加主键（如果没有主键）
ALTER TABLE users ADD PRIMARY KEY (id);

-- 添加联合索引
ALTER TABLE users ADD INDEX idx_city_age (city, age);
```

#### 1.3 删除索引

```sql
-- 删除索引（方式1）
DROP INDEX idx_age ON users;

-- 删除索引（方式2）
ALTER TABLE users DROP INDEX idx_age;

-- 删除主键
ALTER TABLE users DROP PRIMARY KEY;
```

### 2. 索引类型

#### 2.1 按数据结构分类

| 索引类型 | 存储引擎 | 特点 | 适用场景 |
|---------|---------|------|---------|
| **B+树索引** | InnoDB, MyISAM | 有序、支持范围查询 | 绝大多数场景（默认） |
| **哈希索引** | Memory | 等值查询快，不支持范围 | 缓存表、精确匹配 |
| **全文索引** | InnoDB(5.6+), MyISAM | 全文搜索 | 文章内容搜索 |
| **空间索引** | MyISAM | 地理空间数据 | GIS应用 |

#### 2.2 按功能分类

**主键索引（PRIMARY KEY）**
```sql
-- 特点：唯一且非空，InnoDB中是聚簇索引
ALTER TABLE users ADD PRIMARY KEY (id);
```

**唯一索引（UNIQUE）**
```sql
-- 特点：列值唯一，允许NULL
CREATE UNIQUE INDEX uk_email ON users(email);
```

**普通索引（INDEX）**
```sql
-- 特点：最常用，无唯一性约束
CREATE INDEX idx_age ON users(age);
```

**联合索引（Composite Index）**
```sql
-- 特点：多列组合，遵循最左前缀原则
CREATE INDEX idx_city_age_time ON users(city, age, create_time);
```

**全文索引（FULLTEXT）**
```sql
-- 特点：用于全文搜索
CREATE FULLTEXT INDEX ft_content ON articles(content);

-- 查询语法
SELECT * FROM articles WHERE MATCH(content) AGAINST('MySQL索引');
```

### 3. 索引设计原则

#### 3.1 选择合适的列建立索引

**应该建立索引的列**：
- **WHERE、ORDER BY、GROUP BY子句中的列**
- **JOIN的关联列**
- **区分度高的列**（选择性高，不同值多）
- **频繁查询的列**

**不应该建立索引的列**：
- **区分度低的列**（如性别：只有男/女）
- **频繁更新的列**
- **大字段**（TEXT、BLOB等，可以考虑前缀索引）
- **查询很少使用的列**

**示例**：
```sql
-- 好的索引设计
CREATE INDEX idx_user_status_time ON orders(user_id, status, create_time);
-- user_id区分度高，status区分度中等，create_time用于排序

-- 不好的索引设计
CREATE INDEX idx_gender ON users(gender);
-- gender只有2-3个值，区分度太低
```

#### 3.2 前缀索引

**适用场景**：字符串列很长时，只索引前N个字符

```sql
-- 分析前缀选择性
SELECT
    COUNT(DISTINCT LEFT(email, 5)) / COUNT(*) AS prefix_5,
    COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) AS prefix_10,
    COUNT(DISTINCT LEFT(email, 15)) / COUNT(*) AS prefix_15,
    COUNT(DISTINCT email) / COUNT(*) AS full_column
FROM users;

-- 创建前缀索引（前10个字符）
CREATE INDEX idx_email_prefix ON users(email(10));
```

**优点**：
- 节省索引空间
- 提升索引构建和维护速度

**缺点**：
- 无法用于ORDER BY和GROUP BY
- 无法用于覆盖索引

#### 3.3 联合索引设计

**列顺序原则**：
1. **选择性高的列在前**
2. **常用于等值查询的列在前**
3. **范围查询的列在后**

```sql
-- 假设查询：WHERE user_id = ? AND status = ? AND create_time > ?
-- user_id选择性最高（每个用户唯一）
-- status选择性中等（几个状态值）
-- create_time是范围查询

-- 推荐索引设计
CREATE INDEX idx_user_status_time ON orders(user_id, status, create_time);
```

#### 3.4 覆盖索引优化

**目标**：让索引包含查询所需的所有列，避免回表

```sql
-- 频繁查询
SELECT user_id, status, amount FROM orders WHERE user_id = ? AND status = ?;

-- 优化：创建覆盖索引
CREATE INDEX idx_user_status_amount ON orders(user_id, status, amount);
-- 查询无需回表，性能大幅提升
```

### 4. 索引的维护

#### 4.1 查看索引

```sql
-- 查看表的所有索引
SHOW INDEX FROM users;

-- 查看索引统计信息
SHOW INDEX FROM users\G

-- 关键字段：
-- Cardinality: 索引基数（不同值的数量，越大越好）
-- Index_type: 索引类型（BTREE、HASH等）
```

#### 4.2 分析索引使用情况

```sql
-- 查看未使用的索引（MySQL 8.0+）
SELECT * FROM sys.schema_unused_indexes WHERE object_schema = 'your_db';

-- 查看索引统计信息
SELECT * FROM mysql.innodb_index_stats WHERE database_name = 'your_db';
```

#### 4.3 重建索引

**场景**：索引碎片化、统计信息过期

```sql
-- 重建索引（方式1）
ALTER TABLE users DROP INDEX idx_age, ADD INDEX idx_age (age);

-- 重建索引（方式2）
OPTIMIZE TABLE users;  -- 会重建表和所有索引

-- 更新统计信息
ANALYZE TABLE users;   -- 只更新统计信息，不重建索引
```

## 二、索引建太多的缺点

### 1. 影响写性能（主要）

#### 1.1 INSERT操作变慢

**原因**：插入数据时，需要同时更新所有索引

```sql
-- 假设有5个索引
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    status INT,
    amount DECIMAL,
    create_time DATETIME,

    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_amount (amount),
    INDEX idx_time (create_time),
    INDEX idx_user_status (user_id, status)
);

-- 插入一条数据
INSERT INTO orders VALUES (...);

-- 实际操作：
-- 1. 插入数据到主键索引（聚簇索引）
-- 2. 更新idx_user索引
-- 3. 更新idx_status索引
-- 4. 更新idx_amount索引
-- 5. 更新idx_time索引
-- 6. 更新idx_user_status索引
-- 总共6次索引维护操作！
```

**性能影响**：
- 每个索引都需要维护B+树结构
- 可能导致**页分裂**（当数据页满时，需要分裂成两个页）
- **写入IO增加**：更多的磁盘写入

**测试对比**：
```sql
-- 无索引的表
INSERT INTO table_no_index VALUES (...);  -- 假设耗时1ms

-- 有5个索引的表
INSERT INTO table_with_indexes VALUES (...);  -- 可能耗时5-10ms
```

#### 1.2 UPDATE操作变慢

**原因**：更新涉及索引列时，需要维护索引

```sql
-- 更新索引列
UPDATE orders SET status = 2, amount = 200 WHERE id = 1;

-- 实际操作：
-- 1. 定位数据（通过主键索引）
-- 2. 更新主键索引中的数据
-- 3. 删除idx_status旧值，插入新值
-- 4. 删除idx_amount旧值，插入新值
-- 5. 删除idx_user_status旧值（如果status变了），插入新值
```

**特别注意**：
- 如果更新的列**有索引**，性能影响大
- 如果更新的列**无索引**，只更新主键索引，影响小

#### 1.3 DELETE操作变慢

**原因**：删除数据时，需要同时删除所有索引中的记录

```sql
DELETE FROM orders WHERE id = 1;

-- 实际操作：
-- 1. 通过主键定位数据
-- 2. 从主键索引删除
-- 3. 从所有二级索引删除对应记录
```

### 2. 影响读性能（次要）

#### 2.1 优化器选择索引耗时增加

**原因**：索引越多，优化器需要评估的执行计划越多

```sql
-- 如果有10个索引，优化器需要评估：
-- - 使用索引1的成本
-- - 使用索引2的成本
-- - ...
-- - 使用索引10的成本
-- - 全表扫描的成本
-- 然后选择成本最低的方案
```

**影响**：
- **编译时间增加**（通常很小，毫秒级）
- 可能**选错索引**（索引多导致统计信息复杂）

#### 2.2 索引空间占用大

**空间消耗**：
- 每个索引都会占用磁盘空间
- 索引越多，占用空间越大

**示例**：
```sql
-- 查看索引空间占用
SELECT
    table_name,
    ROUND(data_length / 1024 / 1024, 2) AS data_mb,
    ROUND(index_length / 1024 / 1024, 2) AS index_mb,
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb
FROM information_schema.TABLES
WHERE table_schema = 'your_db'
ORDER BY (data_length + index_length) DESC;
```

**影响**：
- **内存占用**：InnoDB会尽量缓存索引到Buffer Pool，索引多会挤占数据缓存
- **备份/恢复时间**：索引多导致备份文件大，恢复慢

### 3. 维护成本高

#### 3.1 统计信息维护

**问题**：
- 索引多，统计信息收集时间长
- 统计信息不准确的概率增加

```sql
-- 分析表（收集统计信息）
ANALYZE TABLE orders;
-- 索引多时，ANALYZE耗时更长
```

#### 3.2 索引碎片化

**原因**：
- 频繁的INSERT/DELETE导致索引碎片
- 索引多，碎片化问题更严重

**影响**：
- 索引查找效率下降
- 需要定期OPTIMIZE TABLE

### 4. 总结：影响读还是写？

| 操作类型 | 影响程度 | 原因 |
|---------|---------|------|
| **INSERT** | 🔴 严重影响 | 需要维护所有索引，写入IO增加 |
| **UPDATE** | 🔴 严重影响（更新索引列时） | 需要删除旧索引值，插入新值 |
| **UPDATE** | 🟢 影响小（更新非索引列时） | 只更新主键索引 |
| **DELETE** | 🔴 严重影响 | 需要从所有索引删除记录 |
| **SELECT** | 🟡 轻微影响 | 优化器选择耗时略增，可能选错索引 |

**核心结论**：**索引主要影响写性能，对读性能影响很小。**

## 三、索引设计最佳实践

### 1. 不要过度索引

**原则**：
- **不要为每个列都建索引**
- **关注20%的核心查询，优化这些查询的索引**
- **定期审查索引使用情况，删除无用索引**

**示例**：
```sql
-- 不好：为所有列建索引
CREATE INDEX idx_col1 ON table(col1);
CREATE INDEX idx_col2 ON table(col2);
CREATE INDEX idx_col3 ON table(col3);
-- ...
CREATE INDEX idx_col20 ON table(col20);

-- 好：只为高频查询建索引
CREATE INDEX idx_frequently_used ON table(col1, col2);
```

### 2. 合理使用联合索引

**原则**：一个联合索引可以替代多个单列索引

```sql
-- 不好：建立多个单列索引
CREATE INDEX idx_a ON table(a);
CREATE INDEX idx_b ON table(b);
CREATE INDEX idx_c ON table(c);

-- 好：建立联合索引
CREATE INDEX idx_abc ON table(a, b, c);

-- 可以支持的查询：
-- WHERE a = ?
-- WHERE a = ? AND b = ?
-- WHERE a = ? AND b = ? AND c = ?
```

**注意**：如果有单独查询b或c的需求，可能还需要额外的索引。

### 3. 避免冗余索引

**冗余索引示例**：
```sql
-- 错误：idx_a是idx_ab的冗余
CREATE INDEX idx_a ON table(a);
CREATE INDEX idx_ab ON table(a, b);
-- idx_ab可以替代idx_a，idx_a是冗余的

-- 正确：删除冗余索引
DROP INDEX idx_a ON table;
```

**工具检测**：
```sql
-- 使用pt-duplicate-key-checker工具（Percona Toolkit）
pt-duplicate-key-checker --host=localhost --user=root --password=xxx
```

### 4. 定期审查索引

**步骤**：
1. **查看索引使用情况**
2. **删除未使用的索引**
3. **合并相似索引**

```sql
-- MySQL 8.0+：查看未使用的索引
SELECT * FROM sys.schema_unused_indexes;

-- 查看索引大小
SELECT
    table_name,
    index_name,
    ROUND(stat_value * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
FROM mysql.innodb_index_stats
WHERE stat_name = 'size'
  AND database_name = 'your_db'
ORDER BY stat_value DESC;
```

### 5. 监控索引性能

**关键指标**：
- **慢查询日志**：发现未使用索引的查询
- **EXPLAIN分析**：定期检查核心SQL的执行计划
- **索引命中率**：监控索引使用频率

```sql
-- 开启慢查询日志
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;  -- 记录超过1秒的查询

-- 分析慢查询
pt-query-digest /var/log/mysql/slow.log
```

### 6. 读写分离场景的索引策略

**场景**：读写分离架构

**策略**：
- **主库（写多）**：索引适度，保证写性能
- **从库（读多）**：可以建立更多索引，优化查询性能

```sql
-- 主库：只有核心索引
CREATE INDEX idx_user_status ON orders(user_id, status);

-- 从库：额外的查询优化索引
CREATE INDEX idx_time ON orders(create_time);
CREATE INDEX idx_amount ON orders(amount);
```

## 四、实战案例

### 案例1：订单表索引设计

**需求**：
```sql
-- 高频查询1：按用户查询订单
SELECT * FROM orders WHERE user_id = ?;

-- 高频查询2：按用户和状态查询
SELECT * FROM orders WHERE user_id = ? AND status = ?;

-- 高频查询3：按时间范围查询
SELECT * FROM orders WHERE create_time >= ? AND create_time < ?;
```

**索引设计**：
```sql
-- 方案1：多个单列索引（不推荐）
CREATE INDEX idx_user ON orders(user_id);
CREATE INDEX idx_status ON orders(status);
CREATE INDEX idx_time ON orders(create_time);

-- 方案2：联合索引（推荐）
CREATE INDEX idx_user_status_time ON orders(user_id, status, create_time);
-- 可以支持查询1、2，查询3需要额外索引

-- 方案3：组合设计
CREATE INDEX idx_user_status_time ON orders(user_id, status, create_time);
CREATE INDEX idx_time ON orders(create_time);  -- 只为查询3
```

### 案例2：删除无用索引

**步骤**：
```sql
-- 1. 查看索引使用情况（运行一段时间后）
SELECT * FROM sys.schema_unused_indexes WHERE object_schema = 'your_db';

-- 2. 确认无用索引
-- 假设idx_old_column从未被使用

-- 3. 删除索引
DROP INDEX idx_old_column ON orders;

-- 4. 观察性能变化
-- - INSERT性能提升
-- - 表空间减小
```

## 五、面试总结

**简洁版回答**：

**如何建立索引**：
```sql
-- 创建表时定义
CREATE TABLE t (id INT PRIMARY KEY, name VARCHAR(50), INDEX idx_name(name));

-- 已有表添加
CREATE INDEX idx_name ON t(name);
ALTER TABLE t ADD INDEX idx_name(name);
```

**索引设计原则**：
1. 为WHERE、JOIN、ORDER BY的列建索引
2. 选择区分度高的列
3. 联合索引优于多个单列索引
4. 避免冗余索引

**索引过多的缺点**：
- **主要影响写性能**：INSERT/UPDATE/DELETE需要维护所有索引，写入变慢
- **轻微影响读性能**：优化器选择耗时增加
- **空间占用**：索引占用磁盘和内存
- **维护成本**：碎片化、统计信息维护

**影响读还是写**：**主要影响写，对读影响很小。**

**最佳实践**：
- 不要过度索引，关注核心查询
- 定期审查删除无用索引
- 读写分离场景下，从库可以多建索引
