---
title: "MySQL只操作同一条记录也会发生死锁吗"
date: 2025-11-02
description: "揭示MySQL在单行操作场景下仍可能发生死锁的几种情况及其底层原因"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 死锁, 并发控制, 锁机制, InnoDB]
nav_order: 330
parent: 数据库MySQL
---
## 问题

MySQL只操作同一条记录,也会发生死锁吗?

## 答案

### 核心结论

**会发生死锁!** 即使多个事务只操作同一条记录,在特定场景下仍然可能形成死锁。主要有以下几种情况:

### 场景1:共享锁升级排他锁

这是最经典的单行死锁场景。

#### 死锁过程

```sql
-- 表结构
CREATE TABLE account (
    id INT PRIMARY KEY,
    balance DECIMAL(10,2)
);
INSERT INTO account VALUES (1, 1000);

-- 事务A
BEGIN;
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- 获取S锁
-- ... 业务逻辑 ...
UPDATE account SET balance = balance - 100 WHERE id = 1;  -- 等待升级为X锁

-- 事务B(同时执行)
BEGIN;
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- 获取S锁
-- ... 业务逻辑 ...
UPDATE account SET balance = balance - 200 WHERE id = 1;  -- 等待升级为X锁

-- 结果:死锁!
-- 事务A持有S锁,等待事务B释放S锁以获取X锁
-- 事务B持有S锁,等待事务A释放S锁以获取X锁
```

#### 死锁原因

```java
/**
 * 锁升级死锁示意
 */
// 时刻1: 两个事务都持有S锁(S锁兼容)
Transaction A: [S Lock on row 1]
Transaction B: [S Lock on row 1]  ✓ 兼容

// 时刻2: 两个事务都想升级为X锁
Transaction A: [S Lock] → 想要 [X Lock]  ← 等待B释放S锁
Transaction B: [S Lock] → 想要 [X Lock]  ← 等待A释放S锁

// 形成循环等待 → 死锁
```

#### 解决方案

```sql
-- 方案1:直接使用FOR UPDATE(避免锁升级)
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;  -- 直接获取X锁
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;

-- 方案2:先锁定再查询
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;
-- 后续UPDATE不会死锁
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;
```

### 场景2:唯一索引冲突导致的死锁

当多个事务尝试插入相同的唯一键值时,也可能发生死锁。

#### 死锁过程

```sql
-- 表结构
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE
);

-- 事务A
BEGIN;
INSERT INTO users (username) VALUES ('alice');  -- 成功,加X锁
-- 未提交...

-- 事务B
BEGIN;
INSERT INTO users (username) VALUES ('alice');  -- 等待事务A的X锁

-- 事务A
ROLLBACK;  -- 释放锁

-- 此时如果有第三个事务C也在等待,可能形成复杂的死锁循环
```

#### 更复杂的场景

```sql
-- 事务A
BEGIN;
INSERT INTO users (username) VALUES ('alice');  -- 获取X锁

-- 事务B
BEGIN;
INSERT INTO users (username) VALUES ('alice');  -- 等待A的X锁,获取S锁(next-key lock)

-- 事务A
ROLLBACK;  -- 释放X锁

-- 事务B
-- 原本等待的插入继续...

-- 事务C(同时)
BEGIN;
INSERT INTO users (username) VALUES ('alice');  -- 也在等待

-- 当事务A回滚后,事务B和C可能形成死锁
```

### 场景3:间隙锁与插入意向锁的死锁

```sql
-- 表结构和数据
CREATE TABLE test (
    id INT PRIMARY KEY
);
INSERT INTO test VALUES (1), (5), (10);

-- 事务A
BEGIN;
SELECT * FROM test WHERE id = 3 FOR UPDATE;  -- id=3不存在,加间隙锁(1,5)

-- 事务B
BEGIN;
SELECT * FROM test WHERE id = 4 FOR UPDATE;  -- id=4不存在,加间隙锁(1,5)

-- 事务A
INSERT INTO test VALUES (3);  -- 等待插入意向锁,被事务B的间隙锁阻塞

-- 事务B
INSERT INTO test VALUES (4);  -- 等待插入意向锁,被事务A的间隙锁阻塞

-- 死锁!
```

### 场景4:外键约束导致的死锁

```sql
-- 父表
CREATE TABLE parent (
    id INT PRIMARY KEY
);
INSERT INTO parent VALUES (1);

-- 子表
CREATE TABLE child (
    id INT PRIMARY KEY,
    parent_id INT,
    FOREIGN KEY (parent_id) REFERENCES parent(id)
);

-- 事务A
BEGIN;
UPDATE child SET parent_id = 1 WHERE id = 100;  -- 自动对parent.id=1加S锁

-- 事务B
BEGIN;
UPDATE child SET parent_id = 1 WHERE id = 200;  -- 自动对parent.id=1加S锁

-- 事务A
DELETE FROM parent WHERE id = 1;  -- 需要X锁,等待事务B释放S锁

-- 事务B
DELETE FROM parent WHERE id = 1;  -- 需要X锁,等待事务A释放S锁

-- 死锁!
```

### 检测和分析死锁

```sql
-- 查看最近一次死锁信息
SHOW ENGINE INNODB STATUS;

-- 输出包含死锁日志
/*
------------------------
LATEST DETECTED DEADLOCK
------------------------
2025-11-02 10:30:00 0x7f8c8c0d9700
*** (1) TRANSACTION:
TRANSACTION 1234, ACTIVE 10 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 10, OS thread handle 140241234, query id 500 localhost root updating
UPDATE account SET balance = balance - 100 WHERE id = 1
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 2 page no 3 n bits 72 index PRIMARY of table `test`.`account` trx id 1234 lock_mode X locks rec but not gap waiting

*** (2) TRANSACTION:
TRANSACTION 1235, ACTIVE 8 sec starting index read
mysql tables in use 1, locked 1
2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 11, OS thread handle 140241235, query id 501 localhost root updating
UPDATE account SET balance = balance - 200 WHERE id = 1
*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 2 page no 3 n bits 72 index PRIMARY of table `test`.`account` trx id 1235 lock mode S locks rec but not gap
*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 2 page no 3 n bits 72 index PRIMARY of table `test`.`account` trx id 1235 lock_mode X locks rec but not gap waiting

*** WE ROLL BACK TRANSACTION (2)
*/
```

### 死锁的四个必要条件

即使是单行操作,只要满足这四个条件,就会发生死锁:

1. **互斥条件**:S锁与X锁互斥
2. **持有并等待**:持有S锁的同时等待X锁
3. **不可剥夺**:锁只能由事务主动释放
4. **循环等待**:事务A等待事务B,事务B等待事务A

### 避免单行死锁的最佳实践

#### 1. 避免锁升级

```sql
-- 错误:先读后写,可能死锁
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;
UPDATE account SET balance = balance - 100 WHERE id = 1;

-- 正确:直接加排他锁
SELECT * FROM account WHERE id = 1 FOR UPDATE;
UPDATE account SET balance = balance - 100 WHERE id = 1;
```

#### 2. 缩短事务时间

```sql
-- 错误:事务中包含耗时操作
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;
-- 调用外部API(耗时3秒)...
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;

-- 正确:先完成外部操作,最后执行事务
-- 调用外部API...
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;
```

#### 3. 统一加锁顺序

```sql
-- 即使操作同一行,也要保证加锁顺序一致
-- 错误:不同事务加锁顺序不同
-- 事务A: SELECT FOR SHARE → UPDATE
-- 事务B: SELECT FOR SHARE → UPDATE

-- 正确:统一直接加排他锁
-- 事务A: SELECT FOR UPDATE → UPDATE
-- 事务B: SELECT FOR UPDATE → UPDATE(排队执行)
```

#### 4. 使用乐观锁替代

```sql
-- 悲观锁:可能死锁
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;

-- 乐观锁:避免死锁
BEGIN;
SELECT balance, version FROM account WHERE id = 1;  -- 不加锁
UPDATE account
SET balance = balance - 100, version = version + 1
WHERE id = 1 AND version = ?;  -- 版本号校验
COMMIT;
```

### 答题总结

MySQL操作同一条记录仍然可能发生死锁,主要场景包括:
1. **S锁升级X锁**:多个事务先读后写,互相等待对方释放S锁
2. **唯一索引冲突**:并发插入相同唯一键
3. **间隙锁冲突**:查询不存在的记录后尝试插入
4. **外键约束**:子表操作触发父表锁冲突

**核心要点**:死锁的本质是循环等待,与操作几行数据无关。即使单行操作,只要形成"A等B,B等A"的循环,就会死锁。

**面试强调**:避免单行死锁的关键是"直接加排他锁,避免锁升级",以及"缩短事务时间,统一加锁顺序"。在高并发场景下,优先考虑乐观锁方案。
