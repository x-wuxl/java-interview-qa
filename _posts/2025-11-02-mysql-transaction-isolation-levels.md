---
layout: post
title: "MySQL中的事务隔离级别"
date: 2025-11-02
description: "详解MySQL四种事务隔离级别的概念、区别及应用场景"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 事务隔离级别, 并发控制, 数据库原理]
---

## 问题

MySQL中的事务隔离级别？

## 答案

### 核心概念

MySQL支持SQL标准定义的四种事务隔离级别，用于控制并发事务之间的可见性和数据一致性，隔离级别越高，数据一致性越好，但并发性能越低。

### 四种隔离级别

#### 1. 读未提交（READ UNCOMMITTED）

- **特点**：事务可以读取其他事务未提交的数据
- **问题**：会产生脏读、不可重复读、幻读
- **实现**：不加锁，直接读取最新数据
- **应用场景**：几乎不使用

```sql
-- 设置隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
```

#### 2. 读已提交（READ COMMITTED，RC）

- **特点**：事务只能读取其他事务已提交的数据
- **问题**：避免了脏读，但仍有不可重复读和幻读问题
- **实现**：每次查询都生成新的ReadView（快照）
- **应用场景**：Oracle数据库默认级别，互联网大厂常用

```sql
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 示例场景
-- 事务A第一次读取：balance = 100
-- 事务B修改并提交：balance = 200
-- 事务A第二次读取：balance = 200（读到不同的值）
```

#### 3. 可重复读（REPEATABLE READ，RR）

- **特点**：在同一事务中多次读取相同数据，结果一致
- **问题**：避免了脏读和不可重复读，InnoDB通过MVCC和间隙锁在很大程度上解决了幻读
- **实现**：事务开始时创建ReadView，整个事务期间复用同一个ReadView
- **应用场景**：**MySQL InnoDB默认隔离级别**

```sql
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- 示例场景
-- 事务A第一次读取：balance = 100
-- 事务B修改并提交：balance = 200
-- 事务A第二次读取：balance = 100（读到相同的值）
```

#### 4. 串行化（SERIALIZABLE）

- **特点**：最高隔离级别，强制事务串行执行
- **问题**：完全避免脏读、不可重复读、幻读，但性能最差
- **实现**：读写都加锁，读锁和写锁互斥
- **应用场景**：对数据一致性要求极高且并发量极低的场景

```sql
SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

### 隔离级别对比

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 并发性能 |
|---------|------|-----------|------|---------|
| READ UNCOMMITTED | 可能 | 可能 | 可能 | 最高 |
| READ COMMITTED | 不可能 | 可能 | 可能 | 较高 |
| REPEATABLE READ | 不可能 | 不可能 | 理论可能* | 较低 |
| SERIALIZABLE | 不可能 | 不可能 | 不可能 | 最低 |

*注：InnoDB在RR级别下通过Next-Key Lock（记录锁+间隙锁）在很大程度上解决了幻读问题。

### 查看和设置隔离级别

```sql
-- 查看全局隔离级别
SELECT @@global.transaction_isolation;

-- 查看会话隔离级别
SELECT @@session.transaction_isolation;
-- 或
SELECT @@transaction_isolation;

-- 设置全局隔离级别（需要SUPER权限）
SET GLOBAL TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- 设置会话隔离级别
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

### 面试要点总结

1. **MySQL InnoDB默认使用RR（可重复读）隔离级别**，而Oracle默认使用RC
2. **RC和RR的核心区别**：RC每次读取生成新快照，RR整个事务使用同一快照
3. **隔离级别的选择**是一致性和性能的权衡
4. InnoDB通过**MVCC（多版本并发控制）**实现RC和RR，避免了读写冲突
5. RR级别下，InnoDB通过**Next-Key Lock**基本解决了幻读问题（当前读场景）
6. 大厂生产环境常改为**RC级别**，原因是减少锁竞争、降低死锁概率、支持半一致性读
