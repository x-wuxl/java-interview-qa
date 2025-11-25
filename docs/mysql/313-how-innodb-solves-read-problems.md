---
layout: default
title: "InnoDB如何解决脏读、不可重复读和幻读？"
parent: 数据库MySQL
nav_order: 313
description: "深入解析InnoDB通过MVCC和锁机制解决并发读问题的实现原理"
author: "wuxl"
date: 2025-11-02
---
## 问题

InnoDB如何解决脏读、不可重复读和幻读的？

## 答案

### 核心机制

InnoDB通过两大核心机制解决并发读问题：
1. **MVCC（多版本并发控制）** - 解决快照读的脏读、不可重复读问题
2. **锁机制（Next-Key Lock）** - 解决当前读的幻读问题

---

### 1. 解决脏读

#### 实现原理

通过**READ COMMITTED及以上隔离级别** + **MVCC机制**实现。

#### 关键点

- 事务只能读取到**已提交事务**的数据版本
- ReadView的`trx_ids`数组记录生成快照时所有活跃（未提交）的事务ID
- 通过版本链（Undo Log）和可见性算法，过滤掉未提交事务的修改

#### 可见性判断规则

```java
// 简化的可见性判断逻辑
boolean isVisible(long trx_id, ReadView readView) {
    // 1. 如果数据版本的事务ID小于ReadView中最小的活跃事务ID，可见
    if (trx_id < readView.min_trx_id) return true;

    // 2. 如果数据版本的事务ID在活跃事务列表中，不可见（未提交）
    if (readView.trx_ids.contains(trx_id)) return false;

    // 3. 如果是当前事务自己修改的，可见
    if (trx_id == readView.creator_trx_id) return true;

    // 4. 否则（已提交的其他事务），可见
    return true;
}
```

#### 示例

```sql
-- 事务A（隔离级别：READ COMMITTED）
START TRANSACTION;
SELECT * FROM user WHERE id = 1; -- 读到已提交的版本

-- 事务B修改但未提交
UPDATE user SET name = 'Bob' WHERE id = 1;
-- 未COMMIT

-- 事务A再次查询
SELECT * FROM user WHERE id = 1; -- 仍读到原值，不会脏读
```

---

### 2. 解决不可重复读

#### 实现原理

通过**REPEATABLE READ隔离级别** + **一致性快照**实现。

#### 关键点

- **RC级别**：每次SELECT生成新的ReadView（可能读到不同值）
- **RR级别**：事务第一次SELECT时生成ReadView，之后复用同一个ReadView
- 同一事务内，多次读取看到的是同一个快照版本

#### 对比示例

```sql
-- READ COMMITTED（不可重复读）
-- 事务A
START TRANSACTION;
SELECT balance FROM account WHERE id = 1; -- 1000
-- 此时生成ReadView1

-- 事务B提交修改
UPDATE account SET balance = 500 WHERE id = 1;
COMMIT;

-- 事务A再次查询
SELECT balance FROM account WHERE id = 1; -- 500（生成ReadView2，读到新值）
COMMIT;

---

-- REPEATABLE READ（可重复读）
-- 事务A
START TRANSACTION;
SELECT balance FROM account WHERE id = 1; -- 1000
-- 第一次SELECT生成ReadView，后续复用

-- 事务B提交修改
UPDATE account SET balance = 500 WHERE id = 1;
COMMIT;

-- 事务A再次查询
SELECT balance FROM account WHERE id = 1; -- 仍是1000（使用同一ReadView）
COMMIT;
```

---

### 3. 解决幻读

#### 实现原理

通过**Next-Key Lock（记录锁 + 间隙锁）**实现。

#### 关键点

- **快照读**（普通SELECT）：MVCC机制避免大部分幻读
- **当前读**（SELECT FOR UPDATE、UPDATE、DELETE）：需要加锁防止幻读

#### Next-Key Lock组成

1. **Record Lock（记录锁）**：锁定索引记录
2. **Gap Lock（间隙锁）**：锁定索引记录之间的间隙
3. **Next-Key Lock = Record Lock + Gap Lock**：锁定记录+前面的间隙

#### 示例场景

```sql
-- 假设表中有 id: 1, 5, 10

-- 事务A（REPEATABLE READ + 当前读）
START TRANSACTION;
SELECT * FROM user WHERE id > 3 FOR UPDATE;
-- 加锁范围：(3, 5], (5, 10], (10, +∞)

-- 事务B尝试插入
INSERT INTO user (id, name) VALUES (6, 'Test');
-- 被阻塞，因为id=6落在间隙(5, 10]中

-- 事务A提交后，事务B才能执行
COMMIT;
```

#### 快照读 vs 当前读

```sql
-- 快照读（MVCC，不加锁）
SELECT * FROM user WHERE age > 20;
-- 即使其他事务插入了新记录，当前事务也看不到（使用快照）

-- 当前读（加锁，读最新数据）
SELECT * FROM user WHERE age > 20 FOR UPDATE;
-- 加Next-Key Lock，阻止其他事务插入age>20的记录
```

---

### 解决方案总结

| 问题类型 | 隔离级别要求 | 实现机制 | 读类型 |
|---------|------------|---------|--------|
| **脏读** | READ COMMITTED | MVCC + ReadView可见性判断 | 快照读 |
| **不可重复读** | REPEATABLE READ | MVCC + 事务级ReadView复用 | 快照读 |
| **幻读** | REPEATABLE READ | MVCC（快照读）<br/>Next-Key Lock（当前读） | 快照读/当前读 |

---

### 面试要点

1. **InnoDB的RR级别不是完全串行化**，而是通过MVCC+锁的组合实现高并发下的一致性读
2. **MVCC只对快照读有效**，当前读必须通过锁机制保证一致性
3. **Next-Key Lock是InnoDB的特色**，结合了行锁和间隙锁，在RR级别下有效防止幻读
4. **间隙锁可能导致死锁**，这也是大厂改用RC级别的原因之一
5. 理解**快照读和当前读的区别**是理解InnoDB并发控制的关键
6. **RC级别下没有间隙锁**，只有记录锁，减少了锁竞争但可能产生幻读
