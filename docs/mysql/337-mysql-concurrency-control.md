---
layout: default
title: "MySQL并发控制手段详解"
parent: 数据库MySQL
nav_order: 337
description: "全面讲解MySQL的并发控制机制，包括锁机制、MVCC、事务隔离级别等核心技术"
author: "wuxl"
date: 2025-11-02
---
## 问题

MySQL的并发控制手段有哪些？

## 答案

### 1. 核心概念

MySQL的并发控制是指在多个事务同时访问数据库时，保证**数据一致性**和**系统性能**的机制。主要通过以下手段实现：

1. **锁机制**（Lock）
2. **MVCC**（多版本并发控制）
3. **事务隔离级别**
4. **间隙锁与临键锁**

**核心目标**：在保证数据正确性的前提下，尽可能提高并发性能。

---

### 2. 锁机制（Lock）

#### 2.1 按锁粒度分类

##### （1）表级锁（Table Lock）

**特点**：
- 锁定整张表，粒度最大，开销最小
- **并发性能差**，适用于读多写少场景
- MyISAM存储引擎主要使用

**类型**：
```sql
-- 读锁（共享锁）：允许多个会话同时读，但不能写
LOCK TABLES orders READ;

-- 写锁（排他锁）：独占访问，其他会话不能读写
LOCK TABLES orders WRITE;

-- 释放锁
UNLOCK TABLES;
```

**应用场景**：
- 数据导入/导出
- 批量数据维护
- 全表扫描操作

##### （2）行级锁（Row Lock）

**特点**：
- 锁定单行记录，粒度最小，并发性能最好
- 开销较大，可能发生**死锁**
- InnoDB存储引擎主要使用

**类型**：
```sql
-- 共享锁（S锁）：允许多个事务同时读同一行
SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE;

-- 排他锁（X锁）：独占访问，其他事务不能读写
SELECT * FROM orders WHERE id = 1 FOR UPDATE;

-- 普通增删改会自动加排他锁
UPDATE orders SET status = 'paid' WHERE id = 1;
DELETE FROM orders WHERE id = 1;
INSERT INTO orders (id, status) VALUES (1, 'new');
```

**兼容性矩阵**：

|      | S锁 | X锁 |
|------|-----|-----|
| S锁  | ✅   | ❌   |
| X锁  | ❌   | ❌   |

##### （3）页级锁（Page Lock）

**特点**：
- 介于表锁和行锁之间
- BDB存储引擎使用（已淘汰）

#### 2.2 按锁类型分类

##### （1）共享锁（Shared Lock，S锁）

```sql
-- 显式加共享锁
SELECT * FROM orders WHERE user_id = 100 LOCK IN SHARE MODE;

-- 多个事务可以同时持有同一行的共享锁
-- 事务A
BEGIN;
SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE; -- ✅
-- 事务B
SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE; -- ✅（可以）
```

##### （2）排他锁（Exclusive Lock，X锁）

```sql
-- 显式加排他锁
SELECT * FROM orders WHERE user_id = 100 FOR UPDATE;

-- 同一时刻只能有一个事务持有排他锁
-- 事务A
BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE; -- ✅
-- 事务B
SELECT * FROM orders WHERE id = 1 FOR UPDATE; -- ❌（阻塞等待）
```

##### （3）意向锁（Intention Lock）

**作用**：表级锁，用于协调**表锁**和**行锁**的关系。

**类型**：
- **意向共享锁（IS）**：事务打算给某些行加S锁
- **意向排他锁（IX）**：事务打算给某些行加X锁

```sql
-- 自动加意向锁（无需手动）
BEGIN;
SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE;
-- 自动在表上加IS锁，在行上加S锁

BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 自动在表上加IX锁，在行上加X锁
```

**意义**：
- 快速判断表级锁和行级锁的冲突
- 避免全表扫描检查是否有行锁

**兼容性矩阵**：

|      | IS  | IX  | S   | X   |
|------|-----|-----|-----|-----|
| IS   | ✅   | ✅   | ✅   | ❌   |
| IX   | ✅   | ✅   | ❌   | ❌   |
| S    | ✅   | ❌   | ✅   | ❌   |
| X    | ❌   | ❌   | ❌   | ❌   |

#### 2.3 InnoDB特有锁

##### （1）记录锁（Record Lock）

锁定**索引记录**本身：

```sql
-- 锁定id=1的记录
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
```

##### （2）间隙锁（Gap Lock）

锁定**索引记录之间的间隙**，防止幻读：

```sql
-- 假设存在id=1和id=10的记录
-- 锁定(1, 10)之间的间隙，防止插入id=2~9的记录
SELECT * FROM orders WHERE id BETWEEN 1 AND 10 FOR UPDATE;
```

**特点**：
- 仅在**可重复读（RR）**隔离级别生效
- 锁定的是范围，不是记录本身
- 防止**幻读**（Phantom Read）

##### （3）临键锁（Next-Key Lock）

**记录锁 + 间隙锁**的组合，锁定**记录及其前面的间隙**：

```sql
-- 假设存在id=1, 5, 10的记录
-- WHERE id = 5会锁定：
-- 1. 记录5本身（记录锁）
-- 2. 间隙(1, 5)（间隙锁）
SELECT * FROM orders WHERE id = 5 FOR UPDATE;

-- 实际锁定范围：(1, 5]
-- 其他事务无法插入id=2,3,4，也无法修改id=5
```

**锁范围示例**：

```sql
-- 表中存在：id = 1, 5, 10, 15
SELECT * FROM orders WHERE id = 10 FOR UPDATE;
-- 锁定范围：(5, 10]

SELECT * FROM orders WHERE id > 10 FOR UPDATE;
-- 锁定范围：(10, +∞)
```

##### （4）插入意向锁（Insert Intention Lock）

特殊的**间隙锁**，在插入时使用：

```sql
-- 事务A：锁定(1, 10)的间隙
SELECT * FROM orders WHERE id BETWEEN 1 AND 10 FOR UPDATE;

-- 事务B：尝试插入id=5（会被阻塞）
INSERT INTO orders (id, status) VALUES (5, 'new'); -- 等待事务A释放

-- 事务C：插入id=20（不冲突）
INSERT INTO orders (id, status) VALUES (20, 'new'); -- ✅
```

**特点**：
- 插入意向锁之间**不冲突**（多个事务可以同时插入不同位置）
- 与间隙锁**冲突**（插入前需要获取插入意向锁）

---

### 3. MVCC（多版本并发控制）

#### 3.1 核心原理

**MVCC**通过保存数据的**多个历史版本**，实现**读不加锁，读写不冲突**，大幅提升并发性能。

**适用场景**：
- **读已提交（RC）**
- **可重复读（RR）**

**不适用**：
- 串行化（Serializable）：完全依赖锁

#### 3.2 实现机制

##### （1）隐藏字段

每行记录包含以下隐藏字段：

| 字段 | 说明 |
|------|------|
| **DB_TRX_ID** | 最后修改该行的**事务ID**（6字节） |
| **DB_ROLL_PTR** | 回滚指针，指向**Undo Log**中的历史版本（7字节） |
| **DB_ROW_ID** | 隐藏主键（6字节，仅无主键表） |

```sql
-- 实际存储示例
CREATE TABLE orders (
    id INT PRIMARY KEY,
    status VARCHAR(20),
    -- 隐藏字段（自动添加）
    DB_TRX_ID,    -- 事务ID
    DB_ROLL_PTR   -- 回滚指针
);
```

##### （2）Undo Log版本链

每次修改都会生成旧版本记录，通过`DB_ROLL_PTR`串联：

```
当前版本: id=1, status='paid', TRX_ID=100
           ↓ (ROLL_PTR)
旧版本1:  id=1, status='pending', TRX_ID=95
           ↓ (ROLL_PTR)
旧版本2:  id=1, status='new', TRX_ID=90
```

##### （3）ReadView（读视图）

每个事务开始时创建的**快照**，用于判断哪些版本可见：

**ReadView核心字段**：
- `m_ids`：当前活跃事务ID列表
- `min_trx_id`：最小活跃事务ID
- `max_trx_id`：下一个事务ID
- `creator_trx_id`：当前事务ID

**可见性判断规则**：
```java
// 伪代码
boolean isVisible(long trx_id) {
    if (trx_id < min_trx_id) {
        return true;  // 已提交的旧事务，可见
    }
    if (trx_id >= max_trx_id) {
        return false; // 未来事务，不可见
    }
    if (m_ids.contains(trx_id)) {
        return trx_id == creator_trx_id; // 活跃事务，仅自己可见
    }
    return true; // 已提交事务，可见
}
```

#### 3.3 快照读 vs 当前读

##### （1）快照读（Snapshot Read）

使用**MVCC**机制，读取历史版本：

```sql
-- 普通SELECT（不加锁）
SELECT * FROM orders WHERE id = 1;

-- 特点：
-- ✅ 不加锁
-- ✅ 读写不冲突
-- ✅ 读取的是快照版本
```

##### （2）当前读（Current Read）

读取**最新版本**，需要加锁：

```sql
-- 加锁SELECT
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE;

-- 增删改（自动加锁）
UPDATE orders SET status = 'paid' WHERE id = 1;
DELETE FROM orders WHERE id = 1;
INSERT INTO orders VALUES (1, 'new');

-- 特点：
-- ❌ 需要加锁
-- ✅ 读取最新数据
-- ✅ 保证实时性
```

#### 3.4 不同隔离级别下的MVCC

##### （1）读已提交（RC）

**ReadView创建时机**：每次SELECT都创建新的ReadView

```sql
-- 事务A
BEGIN;
UPDATE orders SET status = 'paid' WHERE id = 1;

-- 事务B（读已提交）
BEGIN;
SELECT status FROM orders WHERE id = 1; -- 读到'pending'（旧版本）
-- 事务A提交
SELECT status FROM orders WHERE id = 1; -- 读到'paid'（新版本）✅
```

##### （2）可重复读（RR）

**ReadView创建时机**：事务开始时创建一次，后续复用

```sql
-- 事务A
BEGIN;
UPDATE orders SET status = 'paid' WHERE id = 1;

-- 事务B（可重复读）
BEGIN;
SELECT status FROM orders WHERE id = 1; -- 读到'pending'（旧版本）
-- 事务A提交
SELECT status FROM orders WHERE id = 1; -- 仍读到'pending'（旧版本）✅
```

---

### 4. 事务隔离级别

MySQL支持4种事务隔离级别（SQL标准定义）：

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 并发性能 |
|---------|------|-----------|------|---------|
| **读未提交（RU）** | ❌ 可能 | ❌ 可能 | ❌ 可能 | 最高 |
| **读已提交（RC）** | ✅ 避免 | ❌ 可能 | ❌ 可能 | 高 |
| **可重复读（RR）** | ✅ 避免 | ✅ 避免 | ✅ 避免（InnoDB） | 中 |
| **串行化（Serializable）** | ✅ 避免 | ✅ 避免 | ✅ 避免 | 最低 |

**InnoDB默认**：**可重复读（RR）**

#### 4.1 设置隔离级别

```sql
-- 查看隔离级别
SELECT @@transaction_isolation;
SHOW VARIABLES LIKE 'transaction_isolation';

-- 设置全局隔离级别
SET GLOBAL transaction_isolation = 'READ-COMMITTED';

-- 设置会话隔离级别
SET SESSION transaction_isolation = 'REPEATABLE-READ';

-- 设置下一个事务的隔离级别
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

#### 4.2 各级别对比

##### （1）读未提交（RU）

```sql
-- 事务A
BEGIN;
UPDATE orders SET amount = 200 WHERE id = 1;

-- 事务B（读未提交）
BEGIN;
SELECT amount FROM orders WHERE id = 1; -- 读到200（脏读）❌
-- 事务A回滚
SELECT amount FROM orders WHERE id = 1; -- 读到100（数据不一致）
```

##### （2）读已提交（RC）

```sql
-- 事务A
BEGIN;
UPDATE orders SET amount = 200 WHERE id = 1;

-- 事务B（读已提交）
BEGIN;
SELECT amount FROM orders WHERE id = 1; -- 读到100 ✅
-- 事务A提交
SELECT amount FROM orders WHERE id = 1; -- 读到200（不可重复读）❌
```

##### （3）可重复读（RR）

```sql
-- 事务B（可重复读）
BEGIN;
SELECT amount FROM orders WHERE id = 1; -- 读到100

-- 事务A
BEGIN;
UPDATE orders SET amount = 200 WHERE id = 1;
COMMIT;

-- 事务B
SELECT amount FROM orders WHERE id = 1; -- 仍读到100 ✅
```

##### （4）串行化（Serializable）

```sql
-- 所有SELECT自动变为SELECT ... LOCK IN SHARE MODE
-- 强制串行执行，性能最差
BEGIN;
SELECT * FROM orders WHERE id = 1; -- 加共享锁
```

---

### 5. 并发控制实战场景

#### 5.1 库存扣减（防止超卖）

**错误示例**：

```sql
-- 事务A和事务B同时执行
SELECT stock FROM products WHERE id = 1; -- 读到库存=10
-- 两个事务都认为库存充足
UPDATE products SET stock = stock - 1 WHERE id = 1;
-- 最终库存变成9，但实际卖了2个（超卖）❌
```

**正确方案1：FOR UPDATE**

```sql
BEGIN;
-- 加排他锁，串行化处理
SELECT stock FROM products WHERE id = 1 FOR UPDATE;
-- 检查库存
IF stock > 0 THEN
    UPDATE products SET stock = stock - 1 WHERE id = 1;
    -- 创建订单
    INSERT INTO orders ...;
END IF;
COMMIT;
```

**正确方案2：原子更新**

```sql
-- 一条SQL完成，利用数据库的原子性
UPDATE products
SET stock = stock - 1
WHERE id = 1 AND stock > 0;

-- 判断affected_rows是否为1
-- 为0则表示库存不足
```

**正确方案3：乐观锁（版本号）**

```sql
-- 1. 读取库存和版本号
SELECT stock, version FROM products WHERE id = 1;

-- 2. 更新时校验版本号
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = #{oldVersion} AND stock > 0;

-- 3. 判断affected_rows是否为1
-- 为0则重试或失败
```

#### 5.2 账户转账（防止脏读）

```sql
BEGIN;

-- 加排他锁，确保读到最新数据
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
SELECT balance FROM accounts WHERE id = 2 FOR UPDATE;

-- 检查余额
IF balance1 >= 100 THEN
    UPDATE accounts SET balance = balance - 100 WHERE id = 1;
    UPDATE accounts SET balance = balance + 100 WHERE id = 2;
END IF;

COMMIT;
```

#### 5.3 防止幻读（范围查询）

**问题场景**：

```sql
-- 事务A（可重复读）
BEGIN;
SELECT COUNT(*) FROM orders WHERE user_id = 100; -- 结果：10

-- 事务B
INSERT INTO orders (user_id, status) VALUES (100, 'new');
COMMIT;

-- 事务A
SELECT COUNT(*) FROM orders WHERE user_id = 100; -- 仍是10（MVCC）
UPDATE orders SET status = 'paid' WHERE user_id = 100;
-- 更新了11行（当前读，出现幻读）❌
```

**解决方案**：使用**临键锁**

```sql
BEGIN;
-- 加临键锁，锁定范围
SELECT * FROM orders WHERE user_id = 100 FOR UPDATE;
-- 其他事务无法插入user_id=100的记录

UPDATE orders SET status = 'paid' WHERE user_id = 100;
COMMIT;
```

---

### 6. 性能优化建议

#### 6.1 锁优化

```sql
-- ❌ 避免长事务（长时间持有锁）
BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 执行耗时业务逻辑（如调用外部API）
sleep(10);
COMMIT;

-- ✅ 缩短事务范围
-- 先完成业务逻辑，最后提交事务
BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
UPDATE orders SET status = 'paid' WHERE id = 1;
COMMIT;

-- ❌ 避免大事务
BEGIN;
-- 更新100万行
UPDATE orders SET status = 'paid';
COMMIT;

-- ✅ 分批处理
WHILE true DO
    UPDATE orders SET status = 'paid' LIMIT 1000;
    -- 提交
    COMMIT;
    -- 间隔
    sleep(0.1);
END WHILE;
```

#### 6.2 索引优化（减少锁范围）

```sql
-- ❌ 无索引，锁全表
UPDATE orders SET status = 'paid' WHERE user_id = 100;

-- ✅ 添加索引，只锁匹配行
CREATE INDEX idx_user_id ON orders(user_id);
UPDATE orders SET status = 'paid' WHERE user_id = 100;
```

#### 6.3 死锁避免

**死锁场景**：

```sql
-- 事务A
BEGIN;
UPDATE orders SET status = 'paid' WHERE id = 1; -- 锁住id=1
UPDATE orders SET status = 'paid' WHERE id = 2; -- 等待id=2

-- 事务B
BEGIN;
UPDATE orders SET status = 'paid' WHERE id = 2; -- 锁住id=2
UPDATE orders SET status = 'paid' WHERE id = 1; -- 等待id=1（死锁）
```

**避免方法**：
1. **按固定顺序访问资源**（如按ID升序）
2. **减少事务粒度**
3. **使用较低隔离级别**（如RC）
4. **设置锁等待超时**：`innodb_lock_wait_timeout`

```sql
-- 查看死锁日志
SHOW ENGINE INNODB STATUS;

-- 设置锁等待超时（默认50秒）
SET innodb_lock_wait_timeout = 10;
```

---

### 7. 总结

#### 7.1 MySQL并发控制手段

| 手段 | 机制 | 优点 | 缺点 |
|------|------|------|------|
| **表级锁** | 锁整张表 | 开销小 | 并发性差 |
| **行级锁** | 锁单行记录 | 并发性好 | 开销大，可能死锁 |
| **MVCC** | 多版本快照 | 读写不冲突 | 占用Undo Log空间 |
| **间隙锁** | 锁定范围 | 防止幻读 | 可能降低并发 |
| **隔离级别** | 控制可见性 | 灵活权衡 | 级别越高性能越差 |

#### 7.2 选择建议

**场景1：读多写少**
- 使用**读已提交（RC）** + **快照读**
- 优点：并发高，无幻读影响

**场景2：强一致性要求**
- 使用**可重复读（RR）** + **FOR UPDATE**
- 优点：数据一致性强

**场景3：高并发写入**
- 使用**乐观锁**（版本号）
- 优点：无锁等待，吞吐量高

**场景4：防止超卖**
- 使用**原子更新** + **WHERE条件判断**
- 优点：简单高效

#### 7.3 面试要点

1. **锁机制**：理解表锁、行锁、共享锁、排他锁、意向锁、间隙锁、临键锁
2. **MVCC原理**：隐藏字段、Undo Log版本链、ReadView可见性判断
3. **隔离级别**：4种级别的区别和适用场景
4. **实战应用**：库存扣减、转账、防幻读等场景的解决方案
5. **性能优化**：避免长事务、添加索引、防止死锁

**核心答题思路**：先说明锁机制（表锁、行锁、间隙锁），再解释MVCC原理（快照读和当前读），最后结合事务隔离级别和实战场景，体现对MySQL并发控制的深度理解。

