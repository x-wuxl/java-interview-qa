---
layout: default
title: "什么是排他锁和共享锁"
parent: 数据库MySQL
nav_order: 326
description: "详解数据库中的排他锁(X锁)和共享锁(S锁)的概念、兼容性规则及应用场景"
author: "wuxl"
date: 2025-11-02
---
## 问题

什么是排他锁和共享锁?

## 答案

### 核心概念

**共享锁(Shared Lock, S锁)**:允许事务读取一行数据,多个事务可以同时持有同一资源的共享锁。
**排他锁(Exclusive Lock, X锁)**:允许事务更新或删除一行数据,一旦事务持有排他锁,其他事务无法获取该资源的任何锁。

### 锁的兼容性矩阵

|          | 共享锁(S) | 排他锁(X) |
|----------|-----------|-----------|
| 共享锁(S) | ✓ 兼容    | ✗ 冲突    |
| 排他锁(X) | ✗ 冲突    | ✗ 冲突    |

**含义**:
- S锁与S锁兼容:多个事务可以同时读取同一数据
- S锁与X锁冲突:读锁阻止写,写锁阻止读
- X锁与X锁冲突:写操作之间互斥

### SQL语法与加锁方式

#### 1. 共享锁(S锁)

```sql
-- 显式加共享锁
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;

-- MySQL 8.0新语法
SELECT * FROM users WHERE id = 1 FOR SHARE;

-- 普通SELECT不加锁(MVCC实现快照读)
SELECT * FROM users WHERE id = 1;  -- 不加锁
```

**应用场景**:
- 确保读取期间数据不被修改
- 多个事务需要同时读取相同数据
- 检查外键约束时自动加S锁

#### 2. 排他锁(X锁)

```sql
-- 显式加排他锁
SELECT * FROM users WHERE id = 1 FOR UPDATE;

-- DML语句自动加排他锁
UPDATE users SET name = 'Alice' WHERE id = 1;  -- 自动加X锁
DELETE FROM users WHERE id = 1;                -- 自动加X锁
INSERT INTO users VALUES (1, 'Alice');         -- 自动加X锁
```

**应用场景**:
- 数据修改操作(INSERT/UPDATE/DELETE)
- 读取后立即修改(避免并发修改冲突)
- 分布式锁实现(SELECT FOR UPDATE)

### 实际并发场景示例

#### 场景1:共享锁的并发读

```sql
-- 事务A:加共享锁读取
BEGIN;
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- balance = 1000
-- 持有S锁...

-- 事务B:可以同时读取
BEGIN;
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- balance = 1000
-- 成功!两个事务同时持有S锁

-- 事务C:无法修改,等待
UPDATE account SET balance = 500 WHERE id = 1;  -- 等待S锁释放
```

#### 场景2:排他锁的互斥

```sql
-- 事务A:加排他锁
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;  -- 持有X锁

-- 事务B:无法读(LOCK IN SHARE MODE)
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- 等待

-- 事务C:无法写
UPDATE account SET balance = 500 WHERE id = 1;  -- 等待

-- 事务D:可以快照读(不加锁)
SELECT * FROM account WHERE id = 1;  -- 成功(MVCC读取旧版本)
```

#### 场景3:共享锁升级为排他锁(死锁风险)

```sql
-- 事务A
BEGIN;
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- 持有S锁
-- 尝试升级为X锁
UPDATE account SET balance = 500 WHERE id = 1;  -- 等待事务B释放S锁

-- 事务B(同时执行)
BEGIN;
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- 持有S锁
-- 尝试升级为X锁
UPDATE account SET balance = 800 WHERE id = 1;  -- 等待事务A释放S锁

-- 结果:死锁!InnoDB自动检测并回滚一个事务
```

### 实现原理(简化)

```java
/**
 * 锁管理器伪代码
 */
class LockManager {
    Map<RowId, Set<Transaction>> sharedLocks = new HashMap<>();
    Map<RowId, Transaction> exclusiveLocks = new HashMap<>();

    // 申请共享锁
    public boolean acquireSharedLock(RowId row, Transaction txn) {
        // 检查是否有排他锁
        if (exclusiveLocks.containsKey(row)) {
            return false;  // 等待排他锁释放
        }
        // 加入共享锁集合
        sharedLocks.computeIfAbsent(row, k -> new HashSet<>()).add(txn);
        return true;
    }

    // 申请排他锁
    public boolean acquireExclusiveLock(RowId row, Transaction txn) {
        // 检查是否有其他事务持有锁
        if (exclusiveLocks.containsKey(row) ||
            (sharedLocks.containsKey(row) && sharedLocks.get(row).size() > 0)) {
            return false;  // 等待所有锁释放
        }
        exclusiveLocks.put(row, txn);
        return true;
    }
}
```

### 分布式锁实现

```sql
-- 使用SELECT FOR UPDATE实现悲观锁
BEGIN;
-- 尝试获取分布式锁
SELECT * FROM distributed_lock WHERE resource_name = 'order_123' FOR UPDATE;

-- 执行业务逻辑
UPDATE orders SET status = 'processing' WHERE id = 123;

COMMIT;  -- 释放锁
```

### 性能与优化

#### 1. 优先使用MVCC快照读

```sql
-- 不推荐:加共享锁降低并发
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;

-- 推荐:利用MVCC,无锁读取
SELECT * FROM users WHERE id = 1;  -- 读取一致性快照
```

#### 2. 避免长事务持有锁

```sql
-- 错误:长事务持有锁时间过长
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;
-- 执行复杂业务逻辑(耗时10秒)...
COMMIT;

-- 正确:缩短锁持有时间
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;
-- 快速完成数据修改
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;
```

#### 3. 减少锁冲突

```sql
-- 高并发场景:拆分热点行
-- 原表设计:单行记录总库存
UPDATE inventory SET total = total - 1 WHERE product_id = 100;  -- 高并发冲突

-- 优化:分段库存
UPDATE inventory_shards SET amount = amount - 1
WHERE product_id = 100 AND shard_id = (user_id % 10);  -- 减少冲突
```

### 不同隔离级别下的行为

| 隔离级别          | SELECT     | LOCK IN SHARE MODE | FOR UPDATE |
|-------------------|------------|--------------------|------------|
| READ UNCOMMITTED  | 不加锁     | S锁                | X锁        |
| READ COMMITTED    | 不加锁     | S锁(读完即释放)    | X锁        |
| REPEATABLE READ   | 不加锁     | S锁(事务结束释放)  | X锁+Gap锁  |
| SERIALIZABLE      | 自动加S锁  | S锁                | X锁        |

### 答题总结

共享锁和排他锁是实现数据库并发控制的基础机制:
- **S锁允许并发读**,适用于多个事务同时查询同一数据
- **X锁保证独占写**,确保数据修改的原子性和一致性
- **关键规则**:读读不互斥,读写/写写互斥

面试要点:
1. 理解锁的兼容性矩阵
2. 区分显式加锁(LOCK IN SHARE MODE/FOR UPDATE)和自动加锁(DML)
3. 掌握MVCC快照读不加锁的特性
4. 警惕S锁升级X锁可能导致的死锁问题

在实际开发中,应尽量使用MVCC快照读代替共享锁,用乐观锁代替排他锁,以提高系统并发性能。
