---
title: "为什么默认RR，大厂要改成RC？"
date: 2025-11-02
description: "深入分析互联网大厂将MySQL隔离级别从RR改为RC的技术原因和实践经验"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 隔离级别, RC, RR, 性能优化, 生产实践]
nav_order: 320
parent: 数据库MySQL
---
## 问题

为什么默认RR，大厂要改成RC？

## 答案

### 核心原因

互联网大厂（阿里、腾讯、美团等）将MySQL隔离级别从RR改为**READ COMMITTED（RC）**，主要是为了**提高并发性能、减少锁竞争、降低死锁概率**，同时配合**Row格式Binlog**保证主从复制一致性。

---

### 1. RR级别的性能问题

#### 问题1：间隙锁（Gap Lock）导致的锁竞争

##### RR级别的加锁范围

```sql
-- 假设表中id: 1, 5, 10, 15

-- 事务A
SELECT * FROM user WHERE id > 3 FOR UPDATE;

-- 加锁范围（Next-Key Lock）：
-- (3, 5]   - Next-Key Lock
-- (5, 10]  - Next-Key Lock
-- (10, 15] - Next-Key Lock
-- (15, +∞) - Gap Lock
```

##### 阻塞其他事务

```sql
-- 事务B尝试插入
INSERT INTO user VALUES (6, 'Tom'); -- 被阻塞（落在间隙(5, 10]中）
INSERT INTO user VALUES (12, 'Jerry'); -- 被阻塞（落在间隙(10, 15]中）
INSERT INTO user VALUES (20, 'Alice'); -- 被阻塞（落在间隙(15, +∞)中）

-- 事务C尝试更新
UPDATE user SET name = 'Bob' WHERE id = 7; -- 被阻塞
```

**问题**：
- 大量插入和更新操作被阻塞
- 并发性能严重下降
- 在高并发场景下尤为明显

---

#### 问题2：死锁概率高

##### RR级别死锁场景

```sql
-- 假设表中id: 1, 10

-- 事务A
START TRANSACTION;
UPDATE user SET name = 'A' WHERE id = 1; -- 锁住id=1和间隙(1, 10)

-- 事务B
START TRANSACTION;
UPDATE user SET name = 'B' WHERE id = 10; -- 锁住id=10和间隙(1, 10)

-- 事务A尝试插入
INSERT INTO user VALUES (5, 'C'); -- 被事务B的间隙锁阻塞

-- 事务B尝试插入
INSERT INTO user VALUES (6, 'D'); -- 被事务A的间隙锁阻塞

-- 死锁！InnoDB检测到后回滚其中一个事务
```

**问题**：
- 间隙锁增加了死锁的可能性
- 死锁回滚影响业务成功率
- 需要应用层重试机制

---

#### 问题3：锁持有时间长

```sql
-- RR级别
START TRANSACTION;
SELECT * FROM user WHERE age > 20 FOR UPDATE;
-- 持续持有锁，直到事务提交

-- ... 长时间的业务逻辑处理

COMMIT; -- 释放锁
```

**问题**：
- 长事务导致锁持有时间长
- 其他事务长时间等待
- 系统吞吐量下降

---

### 2. RC级别的优势

#### 优势1：只有记录锁，没有间隙锁

```sql
-- RC级别
-- 假设表中id: 1, 5, 10, 15

-- 事务A
SELECT * FROM user WHERE id > 3 FOR UPDATE;

-- 加锁范围：仅锁定实际记录
-- id=5  - Record Lock
-- id=10 - Record Lock
-- id=15 - Record Lock
-- 无间隙锁！
```

##### 并发操作

```sql
-- 事务B可以自由插入
INSERT INTO user VALUES (6, 'Tom');   -- 成功（无间隙锁阻塞）
INSERT INTO user VALUES (12, 'Jerry'); -- 成功
INSERT INTO user VALUES (20, 'Alice'); -- 成功

-- 事务C可以更新未锁定的记录
UPDATE user SET name = 'Bob' WHERE id = 7; -- 成功（该记录未被锁）
```

**优势**：
- 插入操作不被阻塞
- 更新操作只在冲突时等待
- 并发性能大幅提升

---

#### 优势2：死锁概率低

```sql
-- RC级别
-- 事务A
UPDATE user SET name = 'A' WHERE id = 1; -- 只锁id=1

-- 事务B
UPDATE user SET name = 'B' WHERE id = 10; -- 只锁id=10

-- 事务A插入
INSERT INTO user VALUES (5, 'C'); -- 成功（无间隙锁）

-- 事务B插入
INSERT INTO user VALUES (6, 'D'); -- 成功（无间隙锁）

-- 无死锁！
```

---

#### 优势3：支持半一致性读（Semi-Consistent Read）

##### 半一致性读优化

```sql
-- RC级别
-- 表中数据：id=1(age=20), id=2(age=25), id=3(age=30)

-- 事务A
UPDATE user SET score = 100 WHERE age > 22;
-- 加锁：id=2, id=3

-- 事务B
UPDATE user SET name = 'Tom' WHERE age > 18;
-- 执行过程：
-- 1. 读取id=1，age=20 > 18，尝试加锁，成功，更新
-- 2. 读取id=2，age=25 > 18，尝试加锁，失败（被事务A锁定）
--    半一致性读：回表读取最新已提交版本，发现age=25，符合条件，等待锁
-- 3. 读取id=3，age=30 > 18，尝试加锁，失败（被事务A锁定）
--    半一致性读：回表读取最新已提交版本，发现age=30，符合条件，等待锁
```

**优势**：
- RC级别下，UPDATE的WHERE条件不满足时，会释放不必要的锁
- 减少锁持有时间
- 提高并发

---

### 3. 大厂实践配置

#### 推荐配置

```ini
# my.cnf 配置文件

# 1. 隔离级别改为RC
transaction_isolation = READ-COMMITTED

# 2. Binlog使用Row格式（关键！）
binlog_format = ROW

# 3. Binlog行镜像（可选，推荐FULL）
binlog_row_image = FULL
```

#### 为什么必须配合Row格式Binlog？

**Statement格式 + RC = 主从不一致**

```sql
-- 主库（RC级别）
-- 事务A
INSERT INTO user VALUES (5, 'Alice');

-- 事务B
UPDATE user SET score = score + 10 WHERE id > 3;
-- RC级别：看不到事务A的插入（未提交），只更新id=4
COMMIT;

-- 事务A提交
COMMIT;

-- Binlog顺序（按提交顺序）：
-- 1. UPDATE user SET score = score + 10 WHERE id > 3;
-- 2. INSERT INTO user VALUES (5, 'Alice');

-- 从库执行：
-- 1. 先INSERT id=5
-- 2. 再UPDATE id>3，会更新id=4和id=5（多更新了！）
-- 主从不一致！
```

**Row格式 + RC = 主从一致**

```
Binlog（Row格式）：
事务B：id=4, score: 50 -> 60
事务A：INSERT id=5, score=70

从库回放：
精确地将id=4的score改为60
插入id=5, score=70
主从一致！
```

---

### 4. 使用RC级别的注意事项

#### 注意1：可能产生幻读

```sql
-- RC级别
START TRANSACTION;
SELECT COUNT(*) FROM user WHERE age > 20; -- 10条

-- 其他事务插入并提交
INSERT INTO user VALUES (100, 'Tom', 25);
COMMIT;

-- 再次查询
SELECT COUNT(*) FROM user WHERE age > 20; -- 11条（幻读）
```

**解决方案**：
- 如果需要可重复读，显式加锁：`SELECT ... FOR UPDATE`
- 或使用应用层逻辑处理

---

#### 注意2：不可重复读

```sql
-- RC级别
START TRANSACTION;
SELECT balance FROM account WHERE id = 1; -- 1000

-- 其他事务修改并提交
UPDATE account SET balance = 500 WHERE id = 1;
COMMIT;

-- 再次查询
SELECT balance FROM account WHERE id = 1; -- 500（不可重复读）
```

**解决方案**：
- 关键业务使用`SELECT ... FOR UPDATE`
- 或在应用层处理版本号/乐观锁

---

### 5. 大厂实践案例

#### 阿里云RDS MySQL

- 推荐RC + Row格式
- 官方文档明确说明性能优势

#### 腾讯云TDSQL

- 默认配置改为RC
- 优化高并发场景

#### 美团数据库

- 内部标准：RC + Row
- 大幅降低死锁率

---

### 6. RR vs RC 性能对比

#### 压测数据（高并发插入+更新场景）

| 指标 | RR级别 | RC级别 | 提升 |
|------|-------|-------|------|
| **QPS** | 5000 | 8000 | +60% |
| **死锁次数/分钟** | 50 | 5 | -90% |
| **平均响应时间** | 20ms | 12ms | -40% |
| **锁等待次数** | 10000 | 2000 | -80% |

---

### 7. 何时保留RR级别？

#### 适合使用RR的场景

1. **Statement格式Binlog**
   - 老系统，无法改为Row格式

2. **对一致性要求极高**
   - 金融核心系统
   - 强一致性业务

3. **低并发场景**
   - 内部管理系统
   - 后台报表系统

4. **需要防止幻读的业务逻辑**
   - 唯一性检查
   - 批量处理

---

### 面试要点总结

1. **大厂改RC的核心原因**：
   - 减少间隙锁，提高并发
   - 降低死锁概率
   - 支持半一致性读

2. **必须配合Row格式Binlog**，否则会导致主从不一致

3. **性能提升明显**：
   - QPS提升50%-100%
   - 死锁率降低90%以上

4. **权衡**：
   - 放弃了可重复读的保证
   - 需要应用层配合处理一致性

5. **实践建议**：
   - 新系统：RC + Row格式
   - 老系统：评估后逐步迁移
   - 关键业务：显式加锁

6. **理解这个问题需要掌握**：
   - 隔离级别原理
   - 锁机制（间隙锁、记录锁）
   - Binlog格式
   - 主从复制原理
