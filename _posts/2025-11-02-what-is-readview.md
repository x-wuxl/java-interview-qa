---
layout: post
title: "什么是ReadView，什么样的ReadView可见？"
date: 2025-11-02
description: "深入解析InnoDB MVCC机制中ReadView的概念、结构及可见性判断规则"
author: "wuxl"
categories: [数据库]
tags: [MySQL, ReadView, MVCC, 事务可见性, 数据库原理]
---

## 问题

什么是ReadView，什么样的ReadView可见？

## 答案

### 核心概念

**ReadView（一致性视图/读视图）**是InnoDB MVCC机制中用于判断事务可见性的核心数据结构，它记录了创建快照时系统中所有活跃事务的信息，用于确定当前事务能看到哪些数据版本。

---

### 1. ReadView的数据结构

#### 核心字段

```java
class ReadView {
    // 1. 活跃事务ID列表
    List<Long> m_ids;  // 生成ReadView时，所有未提交的事务ID集合

    // 2. 最小活跃事务ID
    long min_trx_id;   // m_ids中的最小值

    // 3. 最大事务ID
    long max_trx_id;   // 生成ReadView时，系统即将分配给下一个事务的ID

    // 4. 创建者事务ID
    long creator_trx_id; // 创建该ReadView的事务ID
}
```

#### 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| **m_ids** | 生成ReadView时所有活跃（未提交）的事务ID数组 | [101, 103, 105] |
| **min_trx_id** | m_ids中的最小事务ID | 101 |
| **max_trx_id** | 系统下一个将要分配的事务ID | 106 |
| **creator_trx_id** | 创建ReadView的事务ID | 102 |

---

### 2. ReadView的创建时机

#### READ COMMITTED（RC）

**每次SELECT都生成新的ReadView**

```sql
START TRANSACTION; -- trx_id = 100

-- 第一次查询，生成ReadView1
SELECT * FROM user WHERE id = 1;

-- 其他事务提交了修改...

-- 第二次查询，生成ReadView2（能看到新提交的数据）
SELECT * FROM user WHERE id = 1;

COMMIT;
```

#### REPEATABLE READ（RR）

**事务第一次SELECT时生成ReadView，后续复用**

```sql
START TRANSACTION; -- trx_id = 100

-- 第一次查询，生成ReadView
SELECT * FROM user WHERE id = 1;

-- 其他事务提交了修改...

-- 第二次查询，复用ReadView（看不到新提交的数据）
SELECT * FROM user WHERE id = 1;

COMMIT;
```

---

### 3. 可见性判断规则

当事务读取一条记录时，通过以下算法判断该版本是否可见：

#### 完整判断逻辑

```java
/**
 * 判断某个数据版本是否对当前ReadView可见
 * @param trx_id 数据版本的事务ID（记录的DB_TRX_ID字段）
 * @param readView 当前事务的ReadView
 * @return true-可见，false-不可见
 */
public boolean isVisible(long trx_id, ReadView readView) {
    // 规则1：如果数据版本是当前事务自己修改的，可见
    if (trx_id == readView.creator_trx_id) {
        return true;
    }

    // 规则2：如果数据版本的事务ID < min_trx_id
    // 说明该事务在ReadView生成之前就已经提交了，可见
    if (trx_id < readView.min_trx_id) {
        return true;
    }

    // 规则3：如果数据版本的事务ID >= max_trx_id
    // 说明该事务是在ReadView生成之后才开启的，不可见
    if (trx_id >= readView.max_trx_id) {
        return false;
    }

    // 规则4：如果 min_trx_id <= trx_id < max_trx_id
    // 需要检查该事务是否在活跃事务列表中
    if (readView.m_ids.contains(trx_id)) {
        return false; // 在活跃列表中，说明未提交，不可见
    } else {
        return true;  // 不在活跃列表中，说明已提交，可见
    }
}
```

#### 四条规则图解

```
事务时间线：
|----[已提交事务]----| min_trx_id |----[活跃事务]----| max_trx_id |----[未开启事务]----|
       (可见)                            (不可见)                      (不可见)

规则1: trx_id == creator_trx_id  →  可见（自己修改的）
规则2: trx_id < min_trx_id        →  可见（早已提交）
规则3: trx_id >= max_trx_id       →  不可见（还未开启）
规则4: 在[min, max)之间           →  看是否在m_ids中
       - 在m_ids中                →  不可见（未提交）
       - 不在m_ids中              →  可见（已提交）
```

---

### 4. 实战演示

#### 场景设置

```sql
-- 初始状态：user表有一条记录
id=1, name='Tom', age=20, DB_TRX_ID=50

-- 当前活跃事务：
-- 事务100：已开启，未提交
-- 事务101：已开启，未提交
-- 事务102：当前事务（即将创建ReadView）
```

#### ReadView生成

事务102执行第一次SELECT：

```sql
START TRANSACTION; -- trx_id = 102
SELECT * FROM user WHERE id = 1;
```

生成的ReadView：

```java
ReadView {
    m_ids: [100, 101, 102],  // 活跃事务列表
    min_trx_id: 100,         // 最小活跃事务ID
    max_trx_id: 103,         // 下一个将分配的事务ID
    creator_trx_id: 102      // 当前事务ID
}
```

---

#### 版本链遍历示例

假设版本链如下（从新到旧）：

```
最新版本：age=24, DB_TRX_ID=101
    ↓ (DB_ROLL_PTR)
历史版本1：age=23, DB_TRX_ID=102
    ↓ (DB_ROLL_PTR)
历史版本2：age=22, DB_TRX_ID=99
    ↓ (DB_ROLL_PTR)
历史版本3：age=21, DB_TRX_ID=50
    ↓
NULL
```

#### 判断过程

```
1. 检查最新版本：age=24, DB_TRX_ID=101
   - trx_id(101) != creator_trx_id(102) ✗
   - trx_id(101) >= min_trx_id(100) ✗
   - trx_id(101) < max_trx_id(103) ✓
   - trx_id(101) in m_ids? 是 → 不可见（事务101未提交）
   - 继续向前遍历

2. 检查历史版本1：age=23, DB_TRX_ID=102
   - trx_id(102) == creator_trx_id(102) ✓
   - 可见！（自己修改的）
   - 返回 age=23
```

**结果**：事务102读到age=23（自己之前修改的版本）

---

### 5. RC vs RR 的ReadView差异

#### 对比示例

```sql
-- 场景：事务A开启后，事务B提交了修改

-- READ COMMITTED
START TRANSACTION;
SELECT age FROM user WHERE id = 1; -- 生成ReadView1，age=20

-- 事务B提交：UPDATE age=30
COMMIT;

SELECT age FROM user WHERE id = 1; -- 生成ReadView2，age=30（能看到）
COMMIT;

---

-- REPEATABLE READ
START TRANSACTION;
SELECT age FROM user WHERE id = 1; -- 生成ReadView，age=20

-- 事务B提交：UPDATE age=30
COMMIT;

SELECT age FROM user WHERE id = 1; -- 复用ReadView，age=20（看不到）
COMMIT;
```

#### 差异原因

| 隔离级别 | ReadView创建时机 | m_ids内容 | 效果 |
|---------|----------------|----------|------|
| RC | 每次SELECT生成新的 | 最新的活跃事务列表 | 能读到新提交的事务 |
| RR | 事务第一次SELECT生成 | 固定的活跃事务列表 | 无法读到后续提交的事务 |

---

### 6. 关键要点

#### ReadView的作用

1. **确定事务的可见性边界**
2. **实现快照读的一致性**
3. **支持不同隔离级别的语义**

#### 配合版本链工作

```
ReadView（判断哪个版本可见）
    +
Undo Log版本链（提供历史版本）
    +
可见性算法（遍历版本链找到可见版本）
    ↓
返回符合条件的数据版本
```

---

### 面试要点总结

1. **ReadView是MVCC可见性判断的核心**，记录了快照时刻的事务状态
2. **四个核心字段**：m_ids、min_trx_id、max_trx_id、creator_trx_id
3. **四条可见性规则**：
   - 自己修改的可见
   - 早已提交的可见
   - 还未开启的不可见
   - 活跃事务不可见，已提交非活跃事务可见
4. **RC和RR的区别**在于ReadView的生成时机
5. ReadView配合**Undo Log版本链**实现快照读
6. 理解ReadView是理解**MVCC、事务隔离级别、可重复读**的关键
