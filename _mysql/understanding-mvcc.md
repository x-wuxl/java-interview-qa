---
title: "如何理解MVCC？"
date: 2025-11-02
description: "深入解析MySQL InnoDB的MVCC多版本并发控制机制及其实现原理"
author: "wuxl"
categories: [数据库]
tags: [MySQL, MVCC, InnoDB, 并发控制, 数据库原理]
nav_order: 315
parent: 数据库MySQL
---
## 问题

如何理解MVCC？

## 答案

### 核心概念

**MVCC（Multi-Version Concurrency Control，多版本并发控制）**是InnoDB实现高并发读写的核心机制，通过保存数据的多个历史版本，实现**读不加锁、读写不冲突**，从而大幅提升并发性能。

---

### 1. MVCC解决的问题

#### 传统锁机制的问题

```sql
-- 传统方式：读写互斥
-- 事务A读取数据时加共享锁
SELECT * FROM user WHERE id = 1 LOCK IN SHARE MODE;

-- 事务B想要修改数据，被阻塞
UPDATE user SET age = 20 WHERE id = 1; -- 等待事务A释放锁
```

#### MVCC的优势

```sql
-- MVCC方式：读写不阻塞
-- 事务A读取数据（快照读，不加锁）
SELECT * FROM user WHERE id = 1;

-- 事务B可以同时修改数据
UPDATE user SET age = 20 WHERE id = 1; -- 不会被阻塞

-- 事务A读到的仍是旧版本数据，保证一致性
```

**核心优势**：
- **写操作不阻塞读操作**
- **读操作不阻塞写操作**
- **提高并发性能**

---

### 2. MVCC的实现原理

MVCC依赖三个核心组件：**隐藏字段** + **Undo Log版本链** + **ReadView**

#### 组件1：隐藏字段

InnoDB为每行记录添加了3个隐藏字段：

| 隐藏字段 | 长度 | 说明 |
|---------|------|------|
| `DB_TRX_ID` | 6字节 | 最后修改该记录的事务ID |
| `DB_ROLL_PTR` | 7字节 | 回滚指针，指向Undo Log中的历史版本 |
| `DB_ROW_ID` | 6字节 | 隐藏主键（无主键时使用） |

```
+----+------+-----+------------+--------------+--------+
| id | name | age | DB_TRX_ID  | DB_ROLL_PTR  | ...    |
+----+------+-----+------------+--------------+--------+
| 1  | Tom  | 20  | 100        | 0x1A2B3C     | ...    |
+----+------+-----+------------+--------------+--------+
```

---

#### 组件2：Undo Log版本链

每次UPDATE操作都会：
1. 将旧版本记录到Undo Log
2. 更新DB_ROLL_PTR指向旧版本
3. 形成版本链

```
最新版本（当前数据）
+----+------+-----+------------+--------------+
| id | name | age | DB_TRX_ID  | DB_ROLL_PTR  |
+----+------+-----+------------+--------------+
| 1  | Tom  | 22  | 103        | 0x3C3D3E ----+
+----+------+-----+------------+--------------+  |
                                                  |
        +-----------------------------------------+
        |
        v
历史版本1（Undo Log）
+----+------+-----+------------+--------------+
| id | name | age | DB_TRX_ID  | DB_ROLL_PTR  |
+----+------+-----+------------+--------------+
| 1  | Tom  | 21  | 102        | 0x2B2C2D ----+
+----+------+-----+------------+--------------+  |
                                                  |
        +-----------------------------------------+
        |
        v
历史版本2（Undo Log）
+----+------+-----+------------+--------------+
| id | name | age | DB_TRX_ID  | DB_ROLL_PTR  |
+----+------+-----+------------+--------------+
| 1  | Tom  | 20  | 101        | NULL         |
+----+------+-----+------------+--------------+
```

---

#### 组件3：ReadView（一致性视图）

ReadView用于判断版本链中哪个版本对当前事务可见。

**ReadView的核心字段**：

| 字段 | 说明 |
|------|------|
| `m_ids`（trx_ids） | 生成ReadView时，所有活跃（未提交）的事务ID列表 |
| `min_trx_id` | m_ids中的最小事务ID |
| `max_trx_id` | 生成ReadView时，系统应该分配给下一个事务的ID |
| `creator_trx_id` | 创建该ReadView的事务ID |

---

### 3. 可见性判断算法

当事务读取一条记录时，按以下规则判断该版本是否可见：

```java
boolean isVisible(long trx_id, ReadView view) {
    // 1. 如果是当前事务自己修改的，可见
    if (trx_id == view.creator_trx_id) {
        return true;
    }

    // 2. 如果版本的事务ID小于ReadView中最小的活跃事务ID，说明该事务已提交，可见
    if (trx_id < view.min_trx_id) {
        return true;
    }

    // 3. 如果版本的事务ID大于等于max_trx_id，说明该事务是在ReadView创建之后才开启的，不可见
    if (trx_id >= view.max_trx_id) {
        return false;
    }

    // 4. 如果版本的事务ID在[min_trx_id, max_trx_id)之间
    //    - 如果在活跃事务列表中，说明未提交，不可见
    //    - 如果不在活跃事务列表中，说明已提交，可见
    if (view.m_ids.contains(trx_id)) {
        return false; // 未提交，不可见
    } else {
        return true;  // 已提交，可见
    }
}
```

---

### 4. MVCC工作流程示例

#### 场景演示

```sql
-- 初始数据：id=1, name='Tom', age=20, DB_TRX_ID=100

-- 时刻1：事务101开始
START TRANSACTION; -- trx_id = 101

-- 时刻2：事务102开始并修改数据
START TRANSACTION; -- trx_id = 102
UPDATE user SET age = 21 WHERE id = 1;
-- 数据变为：age=21, DB_TRX_ID=102
-- Undo Log保存：age=20, DB_TRX_ID=100
COMMIT;

-- 时刻3：事务103开始并修改数据
START TRANSACTION; -- trx_id = 103
UPDATE user SET age = 22 WHERE id = 1;
-- 数据变为：age=22, DB_TRX_ID=103
-- 未提交

-- 时刻4：事务101读取数据（RR隔离级别）
SELECT age FROM user WHERE id = 1;
```

#### ReadView创建（事务101第一次SELECT）

```
ReadView {
    m_ids: [101, 103],      // 活跃事务：101（自己）, 103（未提交）
    min_trx_id: 101,
    max_trx_id: 104,        // 下一个将分配的事务ID
    creator_trx_id: 101
}
```

#### 版本链遍历

```
当前版本：age=22, DB_TRX_ID=103
-> trx_id=103 在m_ids中（未提交），不可见
-> 沿着DB_ROLL_PTR找到历史版本

历史版本1：age=21, DB_TRX_ID=102
-> trx_id=102 < min_trx_id（已提交且在ReadView之前），可见！
-> 返回 age=21
```

**结果**：事务101读到age=21，而不是最新的22（因为103未提交）。

---

### 5. RC vs RR 的ReadView差异

| 隔离级别 | ReadView生成时机 | 特性 |
|---------|-----------------|------|
| **READ COMMITTED** | 每次SELECT生成新的ReadView | 能读到其他事务最新提交的数据 |
| **REPEATABLE READ** | 事务第一次SELECT时生成，后续复用 | 同一事务内读到一致的快照 |

```sql
-- RC级别
START TRANSACTION;
SELECT age FROM user WHERE id = 1; -- 生成ReadView1，读到21

-- 其他事务提交了age=22

SELECT age FROM user WHERE id = 1; -- 生成ReadView2，读到22（不可重复读）
COMMIT;

---

-- RR级别
START TRANSACTION;
SELECT age FROM user WHERE id = 1; -- 生成ReadView，读到21

-- 其他事务提交了age=22

SELECT age FROM user WHERE id = 1; -- 复用ReadView，仍读到21（可重复读）
COMMIT;
```

---

### 6. MVCC的局限性

1. **只对快照读有效**
   - 快照读：`SELECT`（不加锁）
   - 当前读：`SELECT FOR UPDATE`、`UPDATE`、`DELETE`（加锁）

2. **不能完全解决幻读**
   - 快照读场景可以避免
   - 当前读场景需要Next-Key Lock配合

3. **Undo Log空间占用**
   - 长事务导致Undo Log无法清理
   - 可能占用大量磁盘空间

---

### 面试要点总结

1. **MVCC是实现高并发的核心**，通过版本链避免读写冲突
2. **三大组件**：隐藏字段（DB_TRX_ID、DB_ROLL_PTR）+ Undo Log + ReadView
3. **可见性判断算法**是MVCC的核心逻辑
4. **RC和RR的区别**在于ReadView的生成时机
5. **MVCC只对快照读有效**，当前读需要加锁
6. **避免长事务**，否则会导致Undo Log堆积
7. MVCC配合锁机制，实现了InnoDB的高性能事务处理
