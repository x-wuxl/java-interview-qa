---
title: "什么是脏读、幻读、不可重复读？"
date: 2025-11-02
description: "深入理解数据库并发事务中的三种读问题及其产生原因"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 事务, 并发控制, 脏读, 幻读, 不可重复读]
nav_order: 312
parent: 数据库MySQL
---
## 问题

什么是脏读、幻读、不可重复读?

## 答案

### 核心概念

脏读、不可重复读、幻读是数据库并发事务执行过程中可能出现的三种数据不一致问题，通过设置不同的事务隔离级别可以避免这些问题。

### 1. 脏读（Dirty Read）

#### 定义
一个事务读取到了另一个事务**未提交**的数据。

#### 场景示例

```sql
-- 时刻1：事务A查询余额
START TRANSACTION;
SELECT balance FROM account WHERE id = 1; -- 结果：1000

-- 时刻2：事务B修改余额但未提交
START TRANSACTION;
UPDATE account SET balance = 500 WHERE id = 1;
-- 注意：事务B还未COMMIT

-- 时刻3：事务A再次查询（READ UNCOMMITTED级别）
SELECT balance FROM account WHERE id = 1; -- 结果：500（脏读！）

-- 时刻4：事务B回滚
ROLLBACK;

-- 时刻5：事务A的数据成了无效数据
-- 事务A读到了500，但实际数据仍是1000
```

#### 危害
- 读取到的数据可能被回滚，导致业务逻辑基于错误数据
- 严重影响数据一致性

#### 解决方案
使用**READ COMMITTED**或更高隔离级别。

---

### 2. 不可重复读（Non-Repeatable Read）

#### 定义
一个事务内多次读取**同一行数据**，结果不一致（其他事务修改并提交了该数据）。

#### 场景示例

```sql
-- 事务A：统计分析场景
START TRANSACTION;

-- 时刻1：第一次查询
SELECT balance FROM account WHERE id = 1; -- 结果：1000

-- 时刻2：事务B修改并提交
START TRANSACTION;
UPDATE account SET balance = 500 WHERE id = 1;
COMMIT;

-- 时刻3：事务A再次查询同一行（READ COMMITTED级别）
SELECT balance FROM account WHERE id = 1; -- 结果：500（不可重复读！）

-- 同一个事务内，两次读取同一条数据，结果不同
COMMIT;
```

#### 危害
- 影响统计报表的准确性
- 基于前后两次查询的业务逻辑可能出错

#### 解决方案
使用**REPEATABLE READ**或更高隔离级别。

---

### 3. 幻读（Phantom Read）

#### 定义
一个事务内多次执行**相同的查询条件**，返回的**结果集行数**不一致（其他事务插入或删除了符合条件的数据）。

#### 场景示例

```sql
-- 事务A：查询并统计
START TRANSACTION;

-- 时刻1：第一次查询
SELECT * FROM account WHERE balance > 500; -- 结果：5行

-- 时刻2：事务B插入新数据并提交
START TRANSACTION;
INSERT INTO account (id, balance) VALUES (100, 600);
COMMIT;

-- 时刻3：事务A再次查询（REPEATABLE READ级别）
SELECT * FROM account WHERE balance > 500; -- 结果：6行（幻读！）

-- 同一个查询条件，两次返回的行数不同，像出现了"幻影"
COMMIT;
```

#### 特殊性
- **不可重复读关注的是同一条数据的值变化**（UPDATE）
- **幻读关注的是结果集行数的变化**（INSERT/DELETE）

#### 解决方案
- 使用**SERIALIZABLE**隔离级别（完全串行化）
- InnoDB在**REPEATABLE READ**级别下，通过**Next-Key Lock（记录锁+间隙锁）**在很大程度上解决了幻读

---

### 三者对比总结

| 问题类型 | 关注点 | 涉及操作 | 最低解决级别 |
|---------|-------|---------|------------|
| **脏读** | 读到未提交的数据 | 读取未提交事务的修改 | READ COMMITTED |
| **不可重复读** | 同一行数据值变化 | 其他事务UPDATE并提交 | REPEATABLE READ |
| **幻读** | 结果集行数变化 | 其他事务INSERT/DELETE并提交 | SERIALIZABLE（InnoDB的RR基本解决） |

### 记忆技巧

- **脏读**：读到"脏"（未提交）的数据
- **不可重复读**：重复读同一行，值不同，"不可重复"
- **幻读**：记录数量变化，像见到了"幻影"

### 面试要点

1. 三种问题的本质都是**并发事务的可见性问题**
2. InnoDB通过**MVCC**解决了大部分读一致性问题
3. 在RR级别下：
   - **快照读**（普通SELECT）：MVCC避免不可重复读和大部分幻读
   - **当前读**（SELECT FOR UPDATE/LOCK IN SHARE MODE）：Next-Key Lock避免幻读
4. 实际生产中需要在**数据一致性**和**并发性能**之间权衡选择合适的隔离级别
