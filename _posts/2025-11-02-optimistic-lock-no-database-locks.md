---
layout: post
title: "数据库乐观锁的过程中完全没有加任何锁吗"
date: 2025-11-02
description: "深入剖析乐观锁实现过程中数据库锁的真实情况,揭示常见误解"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 乐观锁, 锁机制, MVCC, 并发控制]
---

## 问题

数据库乐观锁的过程中,完全没有加任何锁吗?

## 答案

### 核心结论

**不是!** 乐观锁并非完全无锁,在UPDATE执行时仍然会加锁,只是锁的持有时间非常短,且读取阶段不加锁。准确地说,乐观锁是"读不加锁,写时短暂加锁"。

### 乐观锁的真实加锁过程

#### 1. 读取阶段:不加锁(MVCC)

```sql
-- 步骤1:读取数据(不加锁)
SELECT id, stock, version FROM products WHERE id = 1;
-- 结果: stock=100, version=5

-- 此时使用MVCC(多版本并发控制)读取一致性快照
-- 不会阻塞其他事务的读写操作
```

**原理**:
- InnoDB通过MVCC实现非锁定读
- 每个事务看到的是数据的快照版本
- 不会对索引记录加任何锁

#### 2. 更新阶段:加排他锁(X锁)

```sql
-- 步骤2:更新数据(加排他锁)
BEGIN;
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;  -- 条件匹配时加锁

-- 实际执行过程:
-- 1. 扫描索引定位到id=1的记录
-- 2. 对该记录加排他锁(X Lock)
-- 3. 检查version是否为5
-- 4. 如果匹配,执行更新;否则返回affected_rows=0
-- 5. COMMIT时释放锁

COMMIT;
```

### 详细加锁分析

#### 场景1:版本号匹配(更新成功)

```sql
-- 事务A
BEGIN;
SELECT id, stock, version FROM products WHERE id = 1;  -- version=5, 无锁

-- 事务B(并发执行)
BEGIN;
SELECT id, stock, version FROM products WHERE id = 1;  -- version=5, 无锁(MVCC)

-- 事务A先执行UPDATE
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;
-- 1. 对id=1加排他锁
-- 2. 检查version=5 ✓
-- 3. 更新成功,version变为6
-- 4. 持有X锁直到COMMIT

COMMIT;  -- 释放X锁

-- 事务B随后执行UPDATE
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;
-- 1. 尝试对id=1加排他锁(等待事务A释放)
-- 2. 事务A提交后获取到锁
-- 3. 检查version是否为5,发现已经是6 ✗
-- 4. WHERE条件不匹配,affected_rows=0
-- 5. 更新失败,释放锁

COMMIT;
```

#### 场景2:通过EXPLAIN分析加锁

```sql
-- 查看执行计划
EXPLAIN SELECT id, stock, version FROM products WHERE id = 1;
-- type: const (主键查询,无锁)

EXPLAIN UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;
-- type: const (主键查询,但UPDATE会加X锁)
```

#### 场景3:查看实际锁信息

```sql
-- 事务A:执行更新但不提交
BEGIN;
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;

-- 另一个会话:查看锁信息
SELECT
    ENGINE_TRANSACTION_ID,
    OBJECT_NAME,
    INDEX_NAME,
    LOCK_TYPE,
    LOCK_MODE,
    LOCK_DATA
FROM performance_schema.data_locks
WHERE OBJECT_NAME = 'products';

-- 输出示例:
-- LOCK_TYPE: RECORD
-- LOCK_MODE: X,REC_NOT_GAP  (排他记录锁,不含间隙锁)
-- LOCK_DATA: 1               (主键id=1)
```

### 与悲观锁的加锁对比

```sql
-- 悲观锁:读写都加锁,锁持有时间长
BEGIN;
SELECT * FROM products WHERE id = 1 FOR UPDATE;  -- 加X锁,持有直到COMMIT
-- 执行业务逻辑(可能耗时5秒)...
UPDATE products SET stock = stock - 1 WHERE id = 1;
COMMIT;  -- 总锁持有时间:5秒+

-- 乐观锁:只有写时加锁,锁持有时间短
BEGIN;
SELECT * FROM products WHERE id = 1;  -- 无锁
-- 执行业务逻辑(可能耗时5秒)...
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = ?;  -- 加X锁,持有直到COMMIT
COMMIT;  -- 锁持有时间:仅UPDATE执行时间(毫秒级)
```

### 乐观锁的锁特点

#### 1. 锁的粒度

```sql
-- 主键查询:只锁单行
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;
-- 锁定:id=1的记录锁(Record Lock)

-- 非唯一索引查询:可能锁多行
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE category = 'electronics' AND version = 5;
-- 锁定:所有category='electronics'的记录 + 间隙锁(RR级别)
```

#### 2. 锁的持有时间

```java
/**
 * 悲观锁 vs 乐观锁的锁持有时间对比
 */
public class LockDurationComparison {

    // 悲观锁:锁持有时间 = 整个事务时间
    @Transactional
    public void pessimisticLock() {
        long start = System.currentTimeMillis();

        // 1. 加锁(持有直到事务结束)
        Product product = selectForUpdate(1L);  // 加锁点

        // 2. 业务逻辑(持有锁期间,其他事务等待)
        doBusinessLogic();  // 耗时5000ms

        // 3. 更新(仍然持有锁)
        updateProduct(product);

        // 4. 提交,释放锁
        long duration = System.currentTimeMillis() - start;
        // 锁持有时间: ~5000ms
    }

    // 乐观锁:锁持有时间 = UPDATE执行时间
    @Transactional
    public void optimisticLock() {
        long start = System.currentTimeMillis();

        // 1. 无锁读取
        Product product = selectById(1L);  // 无锁

        // 2. 业务逻辑(不持有锁,其他事务可并发执行)
        doBusinessLogic();  // 耗时5000ms

        // 3. 更新(加锁)
        long lockStart = System.currentTimeMillis();
        updateWithVersion(product);  // 加锁点
        long lockDuration = System.currentTimeMillis() - lockStart;
        // 锁持有时间: ~10ms (仅UPDATE执行时间)

        long duration = System.currentTimeMillis() - start;
        // 总时间: ~5010ms,但锁持有仅10ms
    }
}
```

### 为什么说乐观锁"不加锁"

这是一种**概念上的说法**,相对于悲观锁而言:

1. **读取阶段不加锁**:这是乐观锁的核心特点
2. **写入阶段虽然加锁,但时间极短**:通常在毫秒级
3. **应用层逻辑无锁竞争**:业务逻辑执行期间不持有数据库锁

```sql
-- 乐观锁的"无锁"是相对的
-- 读:无锁(MVCC)
SELECT * FROM products WHERE id = 1;  -- ✓ 真的无锁

-- 写:有锁(X锁),但持有时间短
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;  -- ✗ 实际加锁,但仅持有毫秒级
```

### 乐观锁的MVCC机制

```sql
-- 多个事务并发读取
-- 事务A (开始时间: T1)
BEGIN;  -- 创建Read View
SELECT * FROM products WHERE id = 1;  -- 读取version=5的快照

-- 事务B (开始时间: T2)
BEGIN;
UPDATE products SET stock = 99, version = 6 WHERE id = 1;  -- 加X锁更新
COMMIT;  -- 释放锁

-- 事务A (T3时刻)
SELECT * FROM products WHERE id = 1;
-- RR隔离级别:仍然读取version=5的快照(一致性读)
-- RC隔离级别:读取最新的version=6
```

### 实际性能测试

```java
/**
 * 性能测试:乐观锁 vs 悲观锁
 */
@SpringBootTest
public class LockPerformanceTest {

    @Test
    public void testLockPerformance() throws InterruptedException {
        int threadCount = 100;
        int iterations = 10;

        // 测试悲观锁:TPS ~200
        long pessimisticStart = System.currentTimeMillis();
        testPessimisticLock(threadCount, iterations);
        long pessimisticDuration = System.currentTimeMillis() - pessimisticStart;
        System.out.println("悲观锁总耗时: " + pessimisticDuration + "ms");

        // 测试乐观锁:TPS ~1500
        long optimisticStart = System.currentTimeMillis();
        testOptimisticLock(threadCount, iterations);
        long optimisticDuration = System.currentTimeMillis() - optimisticStart;
        System.out.println("乐观锁总耗时: " + optimisticDuration + "ms");

        // 结论:乐观锁性能约为悲观锁的7-8倍(低冲突场景)
    }
}
```

### 答题总结

数据库乐观锁**并非完全无锁**,准确地说:

1. **读取阶段**:通过MVCC实现非锁定读,完全不加锁
2. **更新阶段**:UPDATE执行时会加排他锁(X Lock),但持有时间极短(毫秒级)
3. **对比悲观锁**:
   - 悲观锁:读写全程持锁,锁持有时间长
   - 乐观锁:只在UPDATE时短暂持锁,并发性能高

**面试要点**:
- 能说清楚乐观锁在UPDATE时仍然会加排他锁
- 理解"乐观锁不加锁"是相对概念,指的是读不加锁
- 知道锁的持有时间短是乐观锁高并发性能的关键
- 了解MVCC在乐观锁中的作用

**关键误区澄清**:
- ✗ 错误:乐观锁完全不用数据库锁
- ✓ 正确:乐观锁在写操作时仍然加锁,但持有时间极短,读操作通过MVCC实现无锁

这个细节考察对数据库锁机制和MVCC的深入理解,是高级面试中的常见追问点。
