---
layout: post
title: "MySQL锁机制全面解析"
date: 2025-11-02
description: "系统梳理MySQL锁机制的分类、实现原理及应用场景"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 锁机制, InnoDB, 并发控制, 数据库优化]
---

## 问题

MySQL锁机制

## 答案

### 一、锁的分类体系

MySQL的锁机制可以从多个维度进行分类:

```
MySQL锁机制
├── 按粒度分类
│   ├── 表级锁(Table Lock)
│   ├── 页级锁(Page Lock) - BDB引擎
│   └── 行级锁(Row Lock)
├── 按兼容性分类
│   ├── 共享锁(S Lock)
│   └── 排他锁(X Lock)
├── 按锁定方式分类
│   ├── 悲观锁
│   └── 乐观锁
├── 按算法分类(InnoDB)
│   ├── 记录锁(Record Lock)
│   ├── 间隙锁(Gap Lock)
│   ├── 临键锁(Next-Key Lock)
│   └── 插入意向锁(Insert Intention Lock)
└── 按用途分类
    ├── 意向锁(Intention Lock)
    ├── 自增锁(AUTO-INC Lock)
    └── 空间索引谓词锁(Predicate Lock)
```

### 二、不同存储引擎的锁特性

#### 1. MyISAM:表级锁

```sql
-- MyISAM只支持表级锁
CREATE TABLE test_myisam (
    id INT PRIMARY KEY,
    name VARCHAR(50)
) ENGINE=MyISAM;

-- 读锁(共享表锁)
LOCK TABLES test_myisam READ;
SELECT * FROM test_myisam;
UNLOCK TABLES;

-- 写锁(排他表锁)
LOCK TABLES test_myisam WRITE;
UPDATE test_myisam SET name = 'test';
UNLOCK TABLES;
```

**特点**:
- 开销小,加锁快
- 无死锁问题
- 并发度低,适合读多写少场景
- 不支持事务

#### 2. InnoDB:行级锁+表级锁

```sql
-- InnoDB支持行级锁和表级锁
CREATE TABLE test_innodb (
    id INT PRIMARY KEY,
    name VARCHAR(50),
    age INT,
    INDEX idx_age (age)
) ENGINE=InnoDB;

-- 行级锁(自动)
BEGIN;
UPDATE test_innodb SET name = 'Alice' WHERE id = 1;  -- 只锁id=1的行
COMMIT;

-- 表级锁(意向锁,自动)
BEGIN;
SELECT * FROM test_innodb WHERE id = 1 FOR UPDATE;  -- 表:IX锁, 行:X锁
COMMIT;
```

**特点**:
- 开销大,加锁慢
- 支持事务,MVCC
- 可能死锁
- 并发度高,适合高并发OLTP场景

### 三、InnoDB行级锁详解

#### 1. 记录锁(Record Lock)

锁定单个索引记录。

```sql
-- 主键等值查询:记录锁
SELECT * FROM users WHERE id = 10 FOR UPDATE;
-- 锁定:PRIMARY KEY的id=10记录

-- 唯一索引等值查询:记录锁
SELECT * FROM users WHERE email = 'test@example.com' FOR UPDATE;
-- 锁定:UNIQUE KEY的email='test@example.com'记录
```

#### 2. 间隙锁(Gap Lock)

锁定索引记录之间的间隙,防止其他事务插入数据。

```sql
-- 表数据:id = 1, 5, 10
BEGIN;
SELECT * FROM users WHERE id = 3 FOR UPDATE;  -- id=3不存在

-- 锁定:间隙(1, 5),阻止插入id=2,3,4的记录

-- 其他事务尝试插入
INSERT INTO users (id, name) VALUES (3, 'Alice');  -- 等待间隙锁释放
```

**作用**:防止幻读

#### 3. 临键锁(Next-Key Lock)

记录锁 + 间隙锁,锁定一个范围及记录本身。

```sql
-- 表数据:id = 1, 5, 10, 15
BEGIN;
SELECT * FROM users WHERE id >= 5 AND id < 10 FOR UPDATE;

-- 锁定范围:(1, 5], (5, 10), [10, 10]
-- 包括:
-- - id=5的记录锁
-- - 间隙(1, 5)
-- - 间隙(5, 10)
-- - id=10的记录锁
```

**RR隔离级别默认使用Next-Key Lock**

#### 4. 插入意向锁(Insert Intention Lock)

一种特殊的间隙锁,用于INSERT操作。

```sql
-- 事务A:持有间隙锁
BEGIN;
SELECT * FROM users WHERE id > 5 AND id < 10 FOR UPDATE;  -- 间隙锁(5, 10)

-- 事务B:插入意向锁
BEGIN;
INSERT INTO users (id, name) VALUES (7, 'Bob');  -- 申请插入意向锁
-- 插入意向锁与间隙锁冲突,等待
```

### 四、加锁规则(InnoDB RR级别)

#### 规则1:主键等值查询

```sql
-- 记录存在:记录锁
SELECT * FROM users WHERE id = 10 FOR UPDATE;
-- 锁定:id=10的记录锁

-- 记录不存在:间隙锁
SELECT * FROM users WHERE id = 15 FOR UPDATE;  -- id=15不存在
-- 锁定:间隙(10, 20)
```

#### 规则2:非唯一索引等值查询

```sql
-- 锁定:匹配记录的记录锁 + 间隙锁
SELECT * FROM users WHERE age = 20 FOR UPDATE;
-- 假设age=20有3条记录
-- 锁定:
-- 1. 3条记录的记录锁
-- 2. age=20范围的间隙锁
-- 3. age=20下一个值之前的间隙锁
```

#### 规则3:范围查询

```sql
-- Next-Key Lock
SELECT * FROM users WHERE id > 10 AND id <= 20 FOR UPDATE;
-- 锁定:(10, 20]的Next-Key Lock
```

#### 规则4:无索引查询

```sql
-- 全表扫描:锁表
SELECT * FROM users WHERE name = 'Alice' FOR UPDATE;  -- name无索引
-- 锁定:所有记录的Next-Key Lock(等同于锁表)
```

### 五、锁的兼容性矩阵

#### 1. 行级锁兼容性

|        | X锁    | S锁    | IX锁   | IS锁   |
|--------|--------|--------|--------|--------|
| X锁    | ✗ 冲突 | ✗ 冲突 | ✗ 冲突 | ✗ 冲突 |
| S锁    | ✗ 冲突 | ✓ 兼容 | ✗ 冲突 | ✓ 兼容 |
| IX锁   | ✗ 冲突 | ✗ 冲突 | ✓ 兼容 | ✓ 兼容 |
| IS锁   | ✗ 冲突 | ✓ 兼容 | ✓ 兼容 | ✓ 兼容 |

#### 2. 间隙锁特殊兼容性

```sql
-- 间隙锁之间兼容(除了插入意向锁)
-- 事务A
BEGIN;
SELECT * FROM users WHERE id > 5 AND id < 10 FOR UPDATE;  -- 间隙锁(5, 10)

-- 事务B(可以并发)
BEGIN;
SELECT * FROM users WHERE id > 5 AND id < 10 FOR UPDATE;  -- 间隙锁(5, 10)
-- 两个间隙锁兼容!

-- 事务C(会阻塞)
INSERT INTO users (id, name) VALUES (7, 'test');  -- 插入意向锁,等待
```

### 六、锁的查看与监控

#### 1. 查看当前锁信息

```sql
-- 查看锁等待
SELECT
    r.trx_id AS waiting_trx_id,
    r.trx_mysql_thread_id AS waiting_thread,
    r.trx_query AS waiting_query,
    b.trx_id AS blocking_trx_id,
    b.trx_mysql_thread_id AS blocking_thread,
    b.trx_query AS blocking_query
FROM information_schema.innodb_lock_waits w
INNER JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
INNER JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id;

-- MySQL 8.0+
SELECT * FROM sys.innodb_lock_waits;
```

#### 2. 查看详细锁信息

```sql
-- 查看所有锁
SELECT
    ENGINE_TRANSACTION_ID,
    OBJECT_NAME,
    INDEX_NAME,
    LOCK_TYPE,
    LOCK_MODE,
    LOCK_STATUS,
    LOCK_DATA
FROM performance_schema.data_locks;
```

#### 3. 查看死锁日志

```sql
SHOW ENGINE INNODB STATUS\G

-- 输出中的LATEST DETECTED DEADLOCK部分
```

### 七、锁优化最佳实践

#### 1. 索引优化

```sql
-- 错误:无索引导致锁表
UPDATE orders SET status = 'paid' WHERE user_id = 100;  -- user_id无索引

-- 正确:添加索引
ALTER TABLE orders ADD INDEX idx_user_id (user_id);
UPDATE orders SET status = 'paid' WHERE user_id = 100;  -- 只锁相关行
```

#### 2. 事务优化

```sql
-- 错误:长事务
BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 调用外部API(耗时5秒)
-- 发送邮件(耗时3秒)
UPDATE orders SET status = 'paid' WHERE id = 1;
COMMIT;

-- 正确:缩短事务
-- 先完成外部操作
callExternalAPI();
sendEmail();

-- 快速提交事务
BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
UPDATE orders SET status = 'paid' WHERE id = 1;
COMMIT;
```

#### 3. 隔离级别优化

```sql
-- 高并发场景:使用RC隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 优势:
-- 1. 减少间隙锁,提高并发
-- 2. 减少死锁概率
-- 3. 牺牲可重复读一致性
```

#### 4. 批量操作优化

```sql
-- 错误:单条循环更新
FOR each id IN ids DO
    UPDATE products SET stock = stock - 1 WHERE id = ?;
END FOR;

-- 正确:批量更新
UPDATE products SET stock = stock - 1 WHERE id IN (1, 2, 3, ...);

-- 或使用CASE WHEN
UPDATE products
SET stock = CASE
    WHEN id = 1 THEN stock - 1
    WHEN id = 2 THEN stock - 2
    ELSE stock
END
WHERE id IN (1, 2);
```

### 八、常见问题与解决

#### 问题1:锁等待超时

```sql
-- 错误信息
ERROR 1205 (HY000): Lock wait timeout exceeded; try restarting transaction

-- 解决方案
-- 1. 调整超时时间
SET innodb_lock_wait_timeout = 100;  -- 默认50秒

-- 2. 优化SQL,缩短事务时间
-- 3. 检查是否有未提交的长事务
SELECT * FROM information_schema.innodb_trx WHERE trx_started < NOW() - INTERVAL 1 MINUTE;
```

#### 问题2:死锁频繁

```sql
-- 解决方案
-- 1. 统一加锁顺序
-- 2. 避免锁升级(直接用FOR UPDATE)
-- 3. 降低隔离级别(RR → RC)
-- 4. 使用乐观锁
```

#### 问题3:性能下降

```sql
-- 排查步骤
-- 1. 查看锁等待
SELECT * FROM sys.innodb_lock_waits;

-- 2. 查看慢查询
SELECT * FROM mysql.slow_log WHERE lock_time > 1;

-- 3. 分析执行计划
EXPLAIN SELECT * FROM orders WHERE user_id = 100 FOR UPDATE;
```

### 答题总结

**MySQL锁机制核心要点**:

1. **锁粒度**: 表锁(MyISAM) vs 行锁(InnoDB)
2. **锁类型**: S锁/X锁, 记录锁/间隙锁/Next-Key锁
3. **加锁规则**:
   - 主键查询 → 记录锁
   - 非唯一索引 → 记录锁+间隙锁
   - 范围查询 → Next-Key Lock
   - 无索引 → 锁表
4. **优化原则**:
   - 使用索引避免锁表
   - 缩短事务时间
   - 统一加锁顺序
   - 合理选择隔离级别

**面试强调**:
- InnoDB的行级锁锁的是索引记录
- RR隔离级别通过Next-Key Lock防止幻读
- 意向锁实现多粒度锁定
- 理解锁的兼容性矩阵
- 能够分析和优化锁等待问题

MySQL锁机制是数据库并发控制的核心,深入理解锁的原理和优化方法,是高级后端工程师的必备技能。
