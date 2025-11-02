---
layout: post
title: "undolog会一直存在吗？什么时候删除"
date: 2025-11-02
description: "深入解析undolog的生命周期、purge清理机制及如何避免undolog膨胀导致的性能问题"
author: "wuxl"
categories: [数据库]
tags: [MySQL, undolog, MVCC, purge, 事务, 性能优化]
---

## 问题

undolog会一直存在吗？什么时候删除？

## 答案

### 1. 核心概念

**undolog不会一直存在**，MySQL有专门的**purge线程**负责清理不再需要的undolog。

**undolog的双重作用**：
1. **事务回滚**：记录修改前的旧值，ROLLBACK时恢复
2. **MVCC（多版本并发控制）**：为其他事务提供历史版本快照读

只有当这两个作用都不再需要时，undolog才会被删除。

### 2. undolog删除的时机

#### 删除条件（必须同时满足）

```
undolog可以删除的条件：
┌────────────────────────────────────┐
│ 条件1: 事务已经提交或回滚          │
│        └─> 不再需要用于回滚        │
└────────────────────────────────────┘
              AND
┌────────────────────────────────────┐
│ 条件2: 没有其他事务需要读取该版本  │
│        └─> MVCC不再需要            │
│        └─> 取决于系统中最早的活跃  │
│            事务（Read View）       │
└────────────────────────────────────┘
```

#### 关键概念：Read View

```sql
-- 场景演示
-- T1时刻：事务A开始（RR隔离级别）
BEGIN;  -- 事务A，trx_id=100
SELECT * FROM user WHERE id = 1;  -- 生成Read View

-- T2时刻：事务B修改数据
-- 另一个连接
BEGIN;  -- 事务B，trx_id=101
UPDATE user SET age = 20 WHERE id = 1;  -- 产生undolog
COMMIT;  -- 事务B提交

-- T3时刻：事务C修改数据
BEGIN;  -- 事务C，trx_id=102
UPDATE user SET age = 30 WHERE id = 1;  -- 产生undolog
COMMIT;  -- 事务C提交

-- T4时刻：事务A再次查询（快照读）
SELECT * FROM user WHERE id = 1;  -- 仍然读到age=10（原始值）

-- 此时undolog无法删除：
-- 因为事务A的Read View需要trx_id=101和102的undolog来构建快照
```

### 3. Purge清理机制

#### Purge线程工作流程

```
Purge线程清理流程：
┌──────────────────────────────────────┐
│ 1. 获取purge_sys.view（可清理边界）  │
│    └─> 系统中最早的活跃Read View     │
└──────────────────────────────────────┘
                ↓
┌──────────────────────────────────────┐
│ 2. 扫描History List（undolog链表）   │
│    └─> 按事务提交顺序组织            │
└──────────────────────────────────────┘
                ↓
┌──────────────────────────────────────┐
│ 3. 判断undolog是否可清理              │
│    └─> trx_id < purge_sys.view?      │
└──────────────────────────────────────┘
                ↓
┌──────────────────────────────────────┐
│ 4. 删除undolog记录                    │
│    └─> 释放回滚段空间                │
└──────────────────────────────────────┘
                ↓
┌──────────────────────────────────────┐
│ 5. 清理索引上的标记删除记录          │
│    └─> delete mark标记的记录物理删除 │
└──────────────────────────────────────┘
```

#### Purge触发时机

```ini
# 相关配置参数
[mysqld]
# purge线程数（MySQL 5.6+支持多线程purge）
innodb_purge_threads = 4

# purge操作的批处理大小
innodb_purge_batch_size = 300

# 每次purge后等待的时间（毫秒）
innodb_purge_rseg_truncate_frequency = 128
```

**Purge触发条件**：
1. 后台线程定期触发（每秒执行一次）
2. History List长度超过阈值
3. undolog文件空间不足时

### 4. undolog膨胀问题

#### 问题场景

```sql
-- 场景1：长事务导致undolog无法清理
-- 连接1: 开启长事务（未提交）
BEGIN;
SELECT * FROM user WHERE id = 1;  -- 生成Read View
-- ... 事务长时间不提交（如执行了sleep(3600)）

-- 连接2-N: 大量更新操作
-- 每次更新都产生undolog，但因为连接1的事务未提交
-- 这些undolog都无法被清理

-- 查看undolog堆积情况
SHOW ENGINE INNODB STATUS\G
-- History list length: 10000（堆积了1万个undolog）
```

#### 膨胀的危害

```
undolog膨胀的影响：

1. 空间问题
   └─> ibdata1文件或独立undo表空间持续增长
       └─> 可能占用数百GB磁盘空间

2. 性能问题
   ├─> MVCC回溯链变长
   │   └─> SELECT性能下降（需要回溯多个版本）
   ├─> B+树索引膨胀
   │   └─> 标记删除的记录无法清理
   └─> 锁竞争增加
       └─> History List锁争用

3. 恢复时间变长
   └─> 崩溃恢复需要处理大量undolog
```

### 5. 监控和诊断

#### 查看undolog堆积情况

```sql
-- 1. 查看History List长度
SHOW ENGINE INNODB STATUS\G
/*
------------
TRANSACTIONS
------------
...
History list length 523  -- undolog堆积数量
...
*/

-- 2. 查看当前活跃事务（找出长事务）
SELECT
    trx_id,
    trx_state,
    trx_started,
    TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS duration_sec,
    trx_rows_modified,
    trx_isolation_level
FROM information_schema.INNODB_TRX
ORDER BY trx_started;

-- 3. 查看undolog表空间大小
SELECT
    FILE_NAME,
    TABLESPACE_NAME,
    FILE_SIZE/1024/1024 AS size_mb
FROM information_schema.FILES
WHERE TABLESPACE_NAME LIKE '%undo%';

-- 4. MySQL 8.0查看undolog详情
SELECT
    SPACE,
    STATE,
    SIZE/1024/1024 AS size_mb
FROM information_schema.INNODB_TABLESPACES
WHERE NAME LIKE 'innodb_undo%';
```

#### 预警阈值

```sql
-- 建立监控告警
-- History list length > 10000: 警告
-- History list length > 100000: 严重告警

-- 长事务告警（超过30分钟的事务）
SELECT COUNT(*) FROM information_schema.INNODB_TRX
WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 1800;
```

### 6. 避免undolog膨胀的最佳实践

#### 代码层面

```java
// ❌ 错误示例：长事务
@Transactional
public void badExample() {
    // 1. 大批量操作
    for (int i = 0; i < 100000; i++) {
        userMapper.update(user);
    }

    // 2. 事务中执行耗时操作
    callExternalAPI();  // 外部API调用
    Thread.sleep(60000);  // 睡眠

    // 3. 事务中有大量查询
    List<User> users = userMapper.selectAll();  // 全表扫描
}

// ✅ 正确示例：短事务
public void goodExample() {
    // 1. 分批处理
    int batchSize = 1000;
    for (int i = 0; i < 100; i++) {
        List<User> batch = getBatch(i * batchSize, batchSize);
        // 每批开启独立事务
        transactionTemplate.execute(status -> {
            userMapper.batchUpdate(batch);
            return null;
        });
    }

    // 2. 耗时操作移到事务外
    String result = callExternalAPI();

    // 3. 最后再开启事务提交
    transactionTemplate.execute(status -> {
        userMapper.saveResult(result);
        return null;
    });
}
```

#### 数据库配置

```ini
# MySQL 8.0独立undo表空间（推荐）
innodb_undo_tablespaces = 2  # undo表空间数量
innodb_undo_log_truncate = ON  # 开启undo表空间自动收缩

# purge优化
innodb_purge_threads = 4  # 多线程purge
innodb_max_purge_lag = 0  # 不限制purge滞后

# 事务隔离级别（RC隔离级别下undolog清理更及时）
transaction_isolation = READ-COMMITTED
```

#### 应用层面

```java
// 1. 避免隐式长事务
@Service
public class UserService {

    // ❌ 错误：整个方法都在事务中
    @Transactional
    public void process() {
        List<User> users = selectUsers();  // 慢查询
        processUsers(users);  // 复杂计算
        updateUsers(users);  // 写入
    }

    // ✅ 正确：只对写操作加事务
    public void process() {
        List<User> users = selectUsers();  // 无事务
        processUsers(users);  // 无事务
        saveWithTransaction(users);  // 有事务
    }

    @Transactional
    private void saveWithTransaction(List<User> users) {
        userMapper.batchUpdate(users);
    }
}

// 2. 设置事务超时
@Transactional(timeout = 30)  // 30秒超时
public void updateUser(User user) {
    userMapper.update(user);
}
```

### 7. MySQL 8.0的改进

```sql
-- MySQL 8.0支持独立undo表空间
CREATE UNDO TABLESPACE undo_003 ADD DATAFILE 'undo_003.ibu';

-- 自动truncate（收缩）undo表空间
SET GLOBAL innodb_undo_log_truncate = ON;
SET GLOBAL innodb_max_undo_log_size = 1G;  -- 超过1G时truncate

-- 查看truncate历史
SELECT * FROM performance_schema.events_statements_history
WHERE SQL_TEXT LIKE '%truncate%undo%';
```

### 8. 答题总结

面试时可这样回答：

> undolog不会一直存在，MySQL有purge线程负责清理。
>
> **删除时机**：必须同时满足两个条件：
> 1. 事务已提交或回滚
> 2. 没有其他事务的Read View需要该版本（取决于最早的活跃事务）
>
> **Purge机制**：后台purge线程定期扫描History List，删除早于系统最早Read View的undolog。MySQL 5.6+支持多线程purge提升清理效率。
>
> **常见问题**：长事务会阻止undolog清理，导致空间膨胀和性能下降。生产环境需要：
> - 避免长事务（超过30秒的事务）
> - 监控History list length指标
> - 及时kill长时间未提交的事务
> - MySQL 8.0可开启innodb_undo_log_truncate自动收缩
>
> 可以通过`SHOW ENGINE INNODB STATUS`查看History list length来监控undolog堆积情况。

**关键要点**：
- undolog由purge线程异步清理
- 长事务会阻止undolog清理
- 监控History list length避免膨胀
- 代码层面避免长事务和隐式事务
