---
layout: post
title: "FOR UPDATE语句InnoDB加了哪些锁"
date: 2025-11-02
description: "深入剖析SELECT FOR UPDATE在不同场景下InnoDB的加锁行为及锁类型"
author: "wuxl"
categories: [数据库]
tags: [MySQL, InnoDB, FOR UPDATE, 锁机制, 加锁分析]
---

## 问题

FOR UPDATE语句,InnoDB加了哪些锁?

## 答案

### 核心结论

`SELECT ... FOR UPDATE`会根据**查询条件、索引类型、隔离级别、数据是否存在**等因素,加不同类型的锁。主要包括:表级意向排他锁(IX)、行级排他锁(X)、间隙锁(Gap Lock)、临键锁(Next-Key Lock)。

### 一、基础加锁规则

#### 1. 必然加的锁:表级IX锁

```sql
-- 任何FOR UPDATE都会先加表级意向排他锁
BEGIN;
SELECT * FROM users WHERE id = 1 FOR UPDATE;

-- 加锁顺序:
-- 1. 表级:意向排他锁(IX Lock)
-- 2. 行级:根据具体情况加锁
```

**作用**:协调行锁与表锁的兼容性,防止其他事务加表级X锁。

### 二、不同场景下的加锁分析

#### 场景1:主键等值查询(记录存在)

```sql
-- 表结构
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(50)
) ENGINE=InnoDB;
INSERT INTO users VALUES (1, 'Alice'), (5, 'Bob'), (10, 'Charlie');

-- 查询存在的记录
BEGIN;
SELECT * FROM users WHERE id = 5 FOR UPDATE;

-- 加锁情况:
-- 表级:IX锁
-- 行级:id=5的记录锁(Record Lock, X模式)
```

**分析**:
- 主键唯一定位到一条记录
- 只锁定该记录,不锁间隙
- 锁模式:`X,REC_NOT_GAP`(排他记录锁,不含间隙)

**验证**:
```sql
-- 查看锁信息
SELECT LOCK_TYPE, LOCK_MODE, LOCK_DATA
FROM performance_schema.data_locks
WHERE OBJECT_NAME = 'users';

-- 输出:
-- LOCK_TYPE: TABLE,  LOCK_MODE: IX
-- LOCK_TYPE: RECORD, LOCK_MODE: X,REC_NOT_GAP,  LOCK_DATA: 5
```

#### 场景2:主键等值查询(记录不存在)

```sql
-- 查询不存在的记录
BEGIN;
SELECT * FROM users WHERE id = 7 FOR UPDATE;  -- id=7不存在

-- 加锁情况:
-- 表级:IX锁
-- 行级:间隙锁(Gap Lock),锁定间隙(5, 10)
```

**分析**:
- 防止其他事务插入id=7的记录
- 锁模式:`X,GAP`(排他间隙锁)
- 阻止INSERT id=6,7,8,9

**验证**:
```sql
-- 事务A持有间隙锁
BEGIN;
SELECT * FROM users WHERE id = 7 FOR UPDATE;

-- 事务B尝试插入(被阻塞)
INSERT INTO users VALUES (7, 'Test');  -- 等待间隙锁释放
INSERT INTO users VALUES (8, 'Test');  -- 等待间隙锁释放

-- 事务C更新其他记录(成功)
UPDATE users SET name = 'Updated' WHERE id = 1;  -- 不在间隙内,成功
```

#### 场景3:唯一索引等值查询

```sql
-- 表结构
CREATE TABLE users (
    id INT PRIMARY KEY,
    email VARCHAR(100) UNIQUE,
    name VARCHAR(50)
) ENGINE=InnoDB;
INSERT INTO users VALUES (1, 'a@test.com', 'Alice');
INSERT INTO users VALUES (5, 'b@test.com', 'Bob');
INSERT INTO users VALUES (10, 'c@test.com', 'Charlie');

-- 唯一索引查询(记录存在)
BEGIN;
SELECT * FROM users WHERE email = 'b@test.com' FOR UPDATE;

-- 加锁情况:
-- 表级:IX锁
-- 行级:
--   1. 唯一索引email='b@test.com'的记录锁
--   2. 主键id=5的记录锁(回表)
```

**分析**:
- 二级唯一索引 + 主键索引都加记录锁
- 不需要间隙锁(唯一索引保证唯一性)

#### 场景4:非唯一索引等值查询

```sql
-- 表结构
CREATE TABLE users (
    id INT PRIMARY KEY,
    age INT,
    name VARCHAR(50),
    INDEX idx_age (age)
) ENGINE=InnoDB;
INSERT INTO users VALUES (1, 20, 'Alice');
INSERT INTO users VALUES (5, 20, 'Bob');
INSERT INTO users VALUES (10, 30, 'Charlie');

-- 非唯一索引查询
BEGIN;
SELECT * FROM users WHERE age = 20 FOR UPDATE;

-- 加锁情况(RR隔离级别):
-- 表级:IX锁
-- 行级:
--   1. idx_age索引:age=20的所有记录锁 + Next-Key Lock
--   2. 主键索引:id=1和id=5的记录锁(回表)
--   3. 间隙锁:锁定age=20前后的间隙
```

**详细分析**:
```sql
-- 具体锁定范围
-- 假设age值分布:10, 20, 20, 30
-- 锁定:
-- 1. (10, 20] 的Next-Key Lock
-- 2. age=20两条记录的记录锁
-- 3. (20, 30) 的间隙锁
```

**验证**:
```sql
-- 事务A
BEGIN;
SELECT * FROM users WHERE age = 20 FOR UPDATE;

-- 事务B的各种操作
INSERT INTO users VALUES (2, 20, 'Test');   -- 阻塞(间隙锁)
INSERT INTO users VALUES (3, 25, 'Test');   -- 阻塞(间隙锁)
UPDATE users SET name = 'X' WHERE id = 1;   -- 阻塞(记录锁)
UPDATE users SET name = 'Y' WHERE id = 10;  -- 成功(不在锁定范围)
```

#### 场景5:范围查询

```sql
-- 范围查询
BEGIN;
SELECT * FROM users WHERE id > 5 AND id <= 10 FOR UPDATE;

-- 加锁情况(RR隔离级别):
-- 表级:IX锁
-- 行级:Next-Key Lock,锁定范围(5, 10]及相邻间隙
```

**详细锁定**:
```sql
-- 假设id值:1, 5, 10, 15
-- 锁定:
-- 1. (5, 10] 的Next-Key Lock
-- 2. (10, 15) 的间隙锁(防止插入id=11,12等)
```

**不同隔离级别对比**:
```sql
-- RC隔离级别:只锁匹配的记录
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
BEGIN;
SELECT * FROM users WHERE id > 5 AND id <= 10 FOR UPDATE;
-- 锁定:只锁id=10的记录锁,不锁间隙

-- RR隔离级别:锁记录+间隙
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
BEGIN;
SELECT * FROM users WHERE id > 5 AND id <= 10 FOR UPDATE;
-- 锁定:Next-Key Lock (5, 10] + 间隙(10, 15)
```

#### 场景6:无索引查询(全表扫描)

```sql
-- 无索引列查询
BEGIN;
SELECT * FROM users WHERE name = 'Alice' FOR UPDATE;  -- name无索引

-- 加锁情况:
-- 表级:IX锁
-- 行级:全表所有记录的Next-Key Lock(等同于锁表)
```

**严重后果**:
```sql
-- 事务A
BEGIN;
SELECT * FROM users WHERE name = 'Alice' FOR UPDATE;

-- 事务B的所有操作都被阻塞
UPDATE users SET name = 'X' WHERE id = 100;  -- 阻塞
INSERT INTO users VALUES (200, 'Test');      -- 阻塞
DELETE FROM users WHERE id = 300;            -- 阻塞

-- 整张表被锁定!
```

**解决方案**:
```sql
-- 添加索引
ALTER TABLE users ADD INDEX idx_name (name);

-- 再次执行,只锁匹配行
SELECT * FROM users WHERE name = 'Alice' FOR UPDATE;
```

#### 场景7:覆盖索引查询

```sql
-- 表结构
CREATE TABLE users (
    id INT PRIMARY KEY,
    age INT,
    name VARCHAR(50),
    INDEX idx_age (age)
) ENGINE=InnoDB;

-- 覆盖索引查询(不需要回表)
BEGIN;
SELECT id, age FROM users WHERE age = 20 FOR UPDATE;

-- 加锁情况:
-- 表级:IX锁
-- 行级:只锁二级索引idx_age的记录,不需要锁主键索引
```

**优势**:减少锁的范围,提高并发性能。

### 三、隔离级别影响

#### RC级别 vs RR级别

```sql
-- RC隔离级别:不加间隙锁
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
BEGIN;
SELECT * FROM users WHERE age = 20 FOR UPDATE;
-- 只锁定:age=20的记录锁,不锁间隙

-- RR隔离级别:加间隙锁防止幻读
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
BEGIN;
SELECT * FROM users WHERE age = 20 FOR UPDATE;
-- 锁定:age=20的记录锁 + 间隙锁
```

### 四、加锁流程总结

```
FOR UPDATE加锁流程:
1. 表级加锁
   └─> 意向排他锁(IX Lock)

2. 定位索引
   ├─> 主键索引 → 直接定位
   ├─> 唯一索引 → 定位后回表
   ├─> 普通索引 → 扫描索引树 + 回表
   └─> 无索引   → 全表扫描

3. 行级加锁(根据场景)
   ├─> 记录存在   → 记录锁(X,REC_NOT_GAP)
   ├─> 记录不存在 → 间隙锁(X,GAP)
   ├─> 范围查询   → Next-Key Lock
   └─> 全表扫描   → 所有记录的Next-Key Lock
```

### 五、实际应用建议

#### 1. 优化索引避免锁表

```sql
-- 错误:导致锁表
SELECT * FROM orders WHERE user_id = 100 FOR UPDATE;  -- user_id无索引

-- 正确:添加索引
ALTER TABLE orders ADD INDEX idx_user_id (user_id);
SELECT * FROM orders WHERE user_id = 100 FOR UPDATE;  -- 只锁相关行
```

#### 2. 使用RC隔离级别提高并发

```sql
-- 高并发场景:减少间隙锁
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
SELECT * FROM products WHERE category = 'electronics' FOR UPDATE;
-- 只锁匹配行,不锁间隙
```

#### 3. 分布式锁实现

```java
/**
 * 使用FOR UPDATE实现分布式锁
 */
@Transactional(rollbackFor = Exception.class)
public void processWithLock(String resourceId) {
    // 1. 尝试获取锁
    DistributedLock lock = lockMapper.selectByResourceIdForUpdate(resourceId);

    if (lock == null) {
        // 锁不存在,创建锁
        lockMapper.insert(new DistributedLock(resourceId));
    }

    // 2. 执行业务逻辑(持有锁期间,其他事务等待)
    doBusinessLogic();

    // 3. 提交事务自动释放锁
}
```

```sql
-- Mapper SQL
<select id="selectByResourceIdForUpdate" resultType="DistributedLock">
    SELECT * FROM distributed_lock
    WHERE resource_id = #{resourceId}
    FOR UPDATE
</select>
```

### 六、锁查看与调试

```sql
-- 查看当前会话的锁
SELECT
    ENGINE_TRANSACTION_ID,
    OBJECT_NAME,
    INDEX_NAME,
    LOCK_TYPE,
    LOCK_MODE,
    LOCK_DATA
FROM performance_schema.data_locks
WHERE ENGINE_TRANSACTION_ID = (
    SELECT trx_id FROM information_schema.innodb_trx
    WHERE trx_mysql_thread_id = CONNECTION_ID()
);

-- 输出示例:
-- OBJECT_NAME: users
-- INDEX_NAME: PRIMARY
-- LOCK_TYPE: RECORD
-- LOCK_MODE: X,REC_NOT_GAP
-- LOCK_DATA: 5
```

### 答题总结

**FOR UPDATE加锁规则**:

1. **必然加锁**:表级IX锁(意向排他锁)

2. **行级加锁**(根据查询条件):
   - **主键等值(存在)**: 记录锁
   - **主键等值(不存在)**: 间隙锁
   - **唯一索引**: 二级索引记录锁 + 主键记录锁
   - **非唯一索引**: 记录锁 + 间隙锁(RR级别)
   - **范围查询**: Next-Key Lock
   - **无索引**: 全表Next-Key Lock(锁表)

3. **隔离级别影响**:
   - RC:只锁记录,不锁间隙
   - RR:锁记录+间隙,防幻读

**面试要点**:
- 能说清楚不同场景下的加锁类型
- 理解索引对加锁范围的影响
- 知道无索引会导致锁表
- 了解RC和RR的锁行为差异
- 能够通过`performance_schema.data_locks`查看锁信息

**关键总结**:FOR UPDATE的加锁行为取决于**索引、查询条件、隔离级别**三个因素,理解这些规则是优化数据库并发性能的关键。
