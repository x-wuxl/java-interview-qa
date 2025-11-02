---
layout: post
title: "什么是意向锁"
date: 2025-11-02
description: "深入理解InnoDB意向锁的设计目的、工作原理及其在多粒度锁定中的关键作用"
author: "wuxl"
categories: [数据库]
tags: [MySQL, InnoDB, 意向锁, 多粒度锁, 表级锁]
---

## 问题

什么是意向锁?

## 答案

### 核心概念

**意向锁(Intention Lock)** 是InnoDB实现多粒度锁定的关键机制,是一种表级锁,用于表明事务**打算**在表中的某些行上加共享锁或排他锁。意向锁分为两种:
- **意向共享锁(IS Lock)**:事务打算给表中的某些行加共享锁
- **意向排他锁(IX Lock)**:事务打算给表中的某些行加排他锁

### 设计目的:解决多粒度锁的效率问题

#### 问题场景

假设没有意向锁,当事务A想要对整张表加表级锁时:

```sql
-- 事务A:已经对某行加了行级锁
BEGIN;
SELECT * FROM users WHERE id = 100 FOR UPDATE;  -- 行级排他锁

-- 事务B:想要对整表加表级锁
LOCK TABLES users WRITE;  -- 需要检查表中是否有行级锁
```

**问题**:事务B必须遍历整张表的所有行,检查是否有行级锁存在,这在大表场景下效率极低。

#### 意向锁的解决方案

```sql
-- 事务A:加行级锁时,自动加意向锁到表
BEGIN;
SELECT * FROM users WHERE id = 100 FOR UPDATE;
-- 1. 先在表级加IX锁(瞬间完成)
-- 2. 再在行级加X锁

-- 事务B:只需检查表级锁
LOCK TABLES users WRITE;
-- 检测到表上有IX锁,直接等待(无需遍历所有行)
```

### 意向锁的兼容性矩阵

|       | IS锁  | IX锁  | S锁(表) | X锁(表) |
|-------|-------|-------|---------|---------|
| IS锁  | ✓兼容 | ✓兼容 | ✓兼容   | ✗冲突   |
| IX锁  | ✓兼容 | ✓兼容 | ✗冲突   | ✗冲突   |
| S锁   | ✓兼容 | ✗冲突 | ✓兼容   | ✗冲突   |
| X锁   | ✗冲突 | ✗冲突 | ✗冲突   | ✗冲突   |

**关键点**:
- 意向锁之间永远兼容(IS与IX可以共存)
- 意向锁与行级锁不冲突(允许多个事务同时持有表级意向锁和行级锁)
- 意向锁与表级X锁冲突(保护行级锁不被表级锁覆盖)

### 自动加锁机制

InnoDB在加行级锁时,会自动添加对应的意向锁:

```sql
-- 1. 共享行锁 → 自动加IS锁
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;
-- 表级:IS锁
-- 行级:S锁

-- 2. 排他行锁 → 自动加IX锁
SELECT * FROM users WHERE id = 1 FOR UPDATE;
-- 表级:IX锁
-- 行级:X锁

-- 3. UPDATE/DELETE → 自动加IX锁
UPDATE users SET name = 'Alice' WHERE id = 1;
-- 表级:IX锁
-- 行级:X锁

-- 4. 表级锁(显式)
LOCK TABLES users READ;   -- 表级S锁
LOCK TABLES users WRITE;  -- 表级X锁
```

### 工作流程示例

#### 示例1:行锁与表锁的协调

```sql
-- 事务A:对某些行加锁
BEGIN;
SELECT * FROM users WHERE id IN (1, 2, 3) FOR UPDATE;
-- 步骤:
-- 1. 在表上加IX锁
-- 2. 在id=1,2,3三行上加X锁

-- 事务B:尝试对整表加读锁
LOCK TABLES users READ;
-- 检测到表上有IX锁
-- IX锁与S锁冲突 → 等待事务A释放

-- 事务C:继续对其他行加锁(不冲突)
SELECT * FROM users WHERE id = 10 FOR UPDATE;
-- 表上已有IX锁,IX与IX兼容 → 成功
-- 在id=10的行上加X锁
```

#### 示例2:多个事务并发加行锁

```sql
-- 事务A
BEGIN;
SELECT * FROM users WHERE id = 1 FOR UPDATE;  -- 表:IX锁, 行:X锁

-- 事务B(并发执行)
BEGIN;
SELECT * FROM users WHERE id = 2 FOR UPDATE;  -- 表:IX锁(兼容), 行:X锁

-- 事务C(并发执行)
BEGIN;
SELECT * FROM users WHERE age > 20 LOCK IN SHARE MODE;  -- 表:IS锁(兼容), 行:S锁

-- 结果:三个事务的意向锁都兼容,可以并发执行(只要行锁不冲突)
```

### 为什么意向锁不与行锁冲突

```java
/**
 * 意向锁与行锁的关系(伪代码)
 */
class LockManager {

    // 意向锁是表级别的"标记"
    Map<Table, Set<IntentionLock>> tableLocks = new HashMap<>();

    // 行锁是行级别的实际锁
    Map<RowId, RowLock> rowLocks = new HashMap<>();

    // 加行级排他锁
    public void lockRowExclusive(Table table, RowId row) {
        // 1. 先在表上加IX意向锁(如果还没有)
        tableLocks.computeIfAbsent(table, k -> new HashSet<>())
                  .add(IntentionLock.IX);

        // 2. 检查表级锁是否冲突
        if (hasConflictingTableLock(table)) {
            wait();  // 等待表级S/X锁释放
        }

        // 3. 在行上加实际的X锁
        rowLocks.put(row, new ExclusiveLock());
    }

    // 意向锁只用于快速检测表级锁冲突,不影响行锁并发
    private boolean hasConflictingTableLock(Table table) {
        // IX锁只与表级S/X锁冲突,不影响其他IX/IS锁
        return tableHasLock(table, TableLock.SHARED) ||
               tableHasLock(table, TableLock.EXCLUSIVE);
    }
}
```

### 查看意向锁

```sql
-- 查看当前会话的锁信息
SELECT
    ENGINE_TRANSACTION_ID,
    OBJECT_NAME,
    INDEX_NAME,
    LOCK_TYPE,
    LOCK_MODE,
    LOCK_DATA
FROM performance_schema.data_locks;

-- 输出示例
-- LOCK_TYPE: TABLE, LOCK_MODE: IX  (意向排他锁)
-- LOCK_TYPE: RECORD, LOCK_MODE: X  (记录排他锁)
```

### 实际意义与性能影响

#### 1. 性能优化

```sql
-- 没有意向锁:O(n)复杂度
-- 需要遍历所有行检查行级锁
LOCK TABLES users WRITE;  -- 检查10万行 → 耗时很长

-- 有意向锁:O(1)复杂度
-- 只需检查表级意向锁
LOCK TABLES users WRITE;  -- 检查1个表级锁 → 瞬间完成
```

#### 2. 不影响并发

```sql
-- 意向锁之间不冲突,允许高并发
-- 1000个并发事务,每个锁不同的行
-- 所有事务都持有IX锁,但不互斥
BEGIN;
SELECT * FROM users WHERE id = ? FOR UPDATE;  -- 1000个并发执行
```

### 常见误解澄清

**误解1**:意向锁会降低并发性能
- **正确**:意向锁之间兼容,不影响行锁的并发,只阻止表级锁

**误解2**:意向锁是行锁的前置锁
- **正确**:意向锁是表级标记,与行锁同时存在,不是前置关系

**误解3**:普通SELECT会加意向锁
- **正确**:只有加锁读(LOCK IN SHARE MODE/FOR UPDATE)才会加意向锁

### 答题总结

意向锁是InnoDB实现多粒度锁定的核心机制,其作用是:
1. **优化表锁检查效率**:避免遍历所有行,将O(n)复杂度降为O(1)
2. **协调行锁与表锁**:意向锁与表级X锁冲突,保护行级锁不被覆盖
3. **不影响并发**:意向锁之间兼容,允许多个事务同时持有

**面试要点**:
- 意向锁是表级锁,但不影响行级锁的并发
- 加行级锁时自动加意向锁
- 理解兼容性矩阵:IS/IX之间兼容,与表级X锁冲突

意向锁是InnoDB高并发性能的关键设计,体现了数据库系统在并发控制中的精巧设计思想。
