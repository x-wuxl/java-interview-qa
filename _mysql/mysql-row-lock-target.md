---
title: "MySQL的行级锁锁的到底是什么"
date: 2025-11-02
description: "深入剖析MySQL InnoDB行级锁的底层实现机制,揭示行锁实际锁定的是索引记录而非数据行"
author: "wuxl"
categories: [数据库]
tags: [MySQL, InnoDB, 行级锁, 索引, 锁机制]
nav_order: 325
parent: 数据库MySQL
---
## 问题

MySQL的行级锁锁的到底是什么?

## 答案

### 核心结论

**MySQL InnoDB的行级锁锁定的是索引记录(Index Record),而不是数据行本身。** 这是理解InnoDB加锁机制的关键。

### 原理解析

#### 1. InnoDB的索引组织表结构

InnoDB使用聚簇索引(Clustered Index)组织数据:
- 主键索引的叶子节点存储完整的行数据
- 二级索引的叶子节点存储主键值
- **锁是加在索引的B+树节点上的**

```sql
-- 表结构示例
CREATE TABLE users (
    id INT PRIMARY KEY,           -- 聚簇索引
    name VARCHAR(50),
    age INT,
    INDEX idx_age (age)           -- 二级索引
) ENGINE=InnoDB;
```

#### 2. 不同场景下的加锁目标

**场景1:主键索引查询**
```sql
-- 锁定主键索引的id=10这个索引项
SELECT * FROM users WHERE id = 10 FOR UPDATE;
```
- 加锁对象:主键索引上id=10的记录锁(Record Lock)
- 锁定位置:聚簇索引B+树的叶子节点

**场景2:二级索引查询**
```sql
-- 锁定二级索引和主键索引
SELECT * FROM users WHERE age = 20 FOR UPDATE;
```
- 加锁对象:
  1. 二级索引`idx_age`上age=20的所有索引项
  2. 通过索引项中的主键值,回表锁定主键索引记录
- 锁定位置:二级索引B+树 + 聚簇索引B+树

**场景3:无索引查询(全表扫描)**
```sql
-- 锁定所有索引记录(锁表)
SELECT * FROM users WHERE name = 'Alice' FOR UPDATE;  -- name无索引
```
- 加锁对象:聚簇索引上的**所有记录**
- 锁定位置:主键索引的每一个叶子节点
- 影响:其他事务无法修改表中任何数据

### 关键点示例

#### 示例1:有索引 vs 无索引

```sql
-- 测试表
CREATE TABLE account (
    id INT PRIMARY KEY,
    user_id INT,
    balance DECIMAL(10,2),
    INDEX idx_user_id (user_id)
);

-- 事务A:使用索引,只锁定user_id=100的记录
BEGIN;
SELECT * FROM account WHERE user_id = 100 FOR UPDATE;

-- 事务B:可以并发修改user_id=200的记录
UPDATE account SET balance = 1000 WHERE user_id = 200;  -- 成功

-- 事务C:假设balance无索引
BEGIN;
SELECT * FROM account WHERE balance > 500 FOR UPDATE;  -- 全表扫描,锁所有记录

-- 事务D:被阻塞
UPDATE account SET balance = 1000 WHERE user_id = 200;  -- 等待
```

#### 示例2:唯一索引 vs 非唯一索引

```sql
-- 唯一索引:只锁一条记录
SELECT * FROM users WHERE id = 10 FOR UPDATE;
-- 锁定:id=10的记录锁

-- 非唯一索引:锁多条记录+间隙
SELECT * FROM users WHERE age = 20 FOR UPDATE;
-- 锁定:所有age=20的记录 + 间隙锁(防止插入新的age=20记录)
```

### 底层数据结构视角

```java
/**
 * InnoDB锁结构示意(简化)
 */
class InnoDBLock {
    // 锁定的索引类型
    IndexType indexType;  // PRIMARY or SECONDARY

    // 锁定的索引值
    byte[] indexKey;      // 例如: id=10 或 age=20

    // 锁的类型
    LockType lockType;    // RECORD, GAP, NEXT_KEY

    // 锁的模式
    LockMode lockMode;    // SHARED or EXCLUSIVE
}

// 加锁示例
lock.indexType = PRIMARY;
lock.indexKey = serialize(10);    // 主键id=10
lock.lockType = RECORD;           // 记录锁
lock.lockMode = EXCLUSIVE;        // 排他锁
```

### 性能与优化影响

#### 1. 索引选择影响加锁范围

```sql
-- 假设有复合索引 idx_age_name(age, name)

-- 情况A:使用完整索引,锁定精确
SELECT * FROM users WHERE age = 20 AND name = 'Alice' FOR UPDATE;

-- 情况B:只用索引前缀,锁定更多记录
SELECT * FROM users WHERE age = 20 FOR UPDATE;
```

#### 2. 覆盖索引减少锁竞争

```sql
-- 非覆盖索引:需要回表,锁定主键索引
SELECT * FROM users WHERE age = 20 FOR UPDATE;

-- 覆盖索引:只扫描二级索引,减少锁竞争
SELECT id, age FROM users WHERE age = 20 FOR UPDATE;  -- 索引覆盖
```

#### 3. 避免无索引导致锁表

```sql
-- 错误:导致全表锁定
UPDATE users SET status = 1 WHERE phone = '13800138000';  -- phone无索引

-- 正确:先加索引
ALTER TABLE users ADD INDEX idx_phone (phone);
UPDATE users SET status = 1 WHERE phone = '13800138000';  -- 只锁匹配行
```

### 验证加锁情况

```sql
-- 查看当前锁信息
SELECT
    ENGINE_TRANSACTION_ID,
    OBJECT_NAME,
    INDEX_NAME,
    LOCK_TYPE,
    LOCK_MODE,
    LOCK_DATA
FROM performance_schema.data_locks
WHERE OBJECT_SCHEMA = 'your_db';
```

### 答题总结

InnoDB的行级锁锁定的是**索引记录**,而非物理数据行。这意味着:
1. 查询必须走索引才能实现真正的行级锁
2. 无索引的查询会退化为锁表
3. 二级索引查询会同时锁定二级索引和主键索引
4. 锁的粒度取决于索引的精确度

**面试强调**: "锁索引不锁行"是InnoDB与其他数据库的重要区别,也是为什么索引优化对并发性能至关重要的核心原因。在生产环境中,必须保证高并发的UPDATE/DELETE语句都能走索引,否则会导致严重的锁等待问题。
