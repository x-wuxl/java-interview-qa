---
layout: default
title: "MySQL三种日志类型综合说明"
parent: 数据库MySQL
nav_order: 379
description: "全面解析MySQL三种核心日志（binlog、redolog、undolog）的特性、协同工作机制及在ACID中的作用"
author: "wuxl"
date: 2025-11-02
---
## 问题

binlog记录更改数据的SQL、redolog重做日志、undolog回滚日志

## 答案

本文全面解析MySQL三种核心日志的特性、作用及协同工作机制。

### 1. 三种日志的定位

```
MySQL日志体系架构：

┌──────────────────────────────────────────────────────────┐
│                      Server层                             │
│  ┌────────────────────────────────────────────────────┐  │
│  │ binlog（二进制日志）                                │  │
│  │ - 记录所有DDL和DML语句                              │  │
│  │ - 用于主从复制和数据恢复                            │  │
│  │ - 所有存储引擎共享                                  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────────────────────────────────────┐
│                   InnoDB引擎层                            │
│  ┌─────────────────────┐  ┌──────────────────────────┐  │
│  │ redolog（重做日志）  │  │ undolog（回滚日志）       │  │
│  │ - 记录物理页修改     │  │ - 记录修改前的旧值        │  │
│  │ - 保证持久性（D）    │  │ - 保证原子性（A）         │  │
│  │ - 用于崩溃恢复       │  │ - 用于事务回滚和MVCC      │  │
│  └─────────────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 2. binlog（二进制日志）

#### 核心特性

```
名称：binlog（Binary Log）
层次：Server层（MySQL服务器层）
类型：逻辑日志
作用：
  1. 主从复制：主库将binlog发送给从库回放
  2. 数据恢复：基于时间点恢复（PITR）
  3. 数据审计：追踪数据变更历史
```

#### 记录内容

```sql
-- STATEMENT格式：记录SQL语句
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;

-- ROW格式：记录行变更
BEGIN;
### UPDATE `db`.`account`
### WHERE @1=1 @2=1000  -- 旧值
### SET   @1=1 @2=900   -- 新值
COMMIT;

-- MIXED格式：自动选择STATEMENT或ROW
```

#### 写入时机

```
事务执行流程中的binlog写入：

T1: 事务开始
    └─> 分配binlog cache

T2: 执行SQL语句
    └─> 变更写入binlog cache（内存）

T3: 事务提交（两阶段提交）
    ├─> redolog进入prepare状态
    ├─> binlog cache写入binlog文件（OS缓存）
    ├─> fsync刷盘（根据sync_binlog参数）
    └─> redolog改为commit状态

关键点：binlog在事务提交时才写入文件
```

#### 文件管理

```sql
-- 查看binlog文件列表
SHOW BINARY LOGS;
/*
+------------------+-----------+
| Log_name         | File_size |
+------------------+-----------+
| mysql-bin.000001 | 177       |
| mysql-bin.000002 | 156428    |
| mysql-bin.000003 | 1073741824|
+------------------+-----------+
*/

-- 查看binlog事件
SHOW BINLOG EVENTS IN 'mysql-bin.000003' LIMIT 10;

-- 删除旧的binlog（保留最近7天）
PURGE BINARY LOGS BEFORE DATE_SUB(NOW(), INTERVAL 7 DAY);

-- 配置binlog过期时间（MySQL 8.0）
SET GLOBAL binlog_expire_logs_seconds = 604800;  -- 7天
```

### 3. redolog（重做日志）

#### 核心特性

```
名称：redolog（Redo Log）
层次：InnoDB引擎层
类型：物理日志
作用：
  1. 崩溃恢复：数据库崩溃后重做已提交事务
  2. WAL机制：先写日志，后写数据（提升性能）
  3. 持久性保证：保证事务的ACID特性中的D
```

#### 记录内容

```
物理日志记录格式：

"在表空间5的数据页300的偏移量50位置，
 将4字节的值从0x00000064改为0x000000C8"

特点：
- 记录数据页的物理修改
- 记录最小修改单元（页级别）
- 可以快速重做（不需要重新执行SQL逻辑）
```

#### 写入机制：循环写

```
redolog循环写结构（ib_logfile）：

文件组：4个文件 × 1GB = 4GB
┌─────────────────────────────────────────┐
│ ib_logfile0 (1GB)                       │ ←─┐
├─────────────────────────────────────────┤   │
│ ib_logfile1 (1GB)                       │   │
├─────────────────────────────────────────┤   │ 循环写
│ ib_logfile2 (1GB)                       │   │
├─────────────────────────────────────────┤   │
│ ib_logfile3 (1GB)                       │ ──┘
└─────────────────────────────────────────┘
     ↑                            ↑
 checkpoint                   write pos
     │                            │
 可以擦除的位置              当前写入位置

可用空间 = write pos 到 checkpoint 之间的空间
```

#### 刷盘策略

```ini
# innodb_flush_log_at_trx_commit参数控制
# 0: 每秒写入并刷盘（可能丢失1秒数据）
# 1: 每次事务提交都刷盘（最安全，默认）
# 2: 每次提交写OS缓存，每秒刷盘
innodb_flush_log_at_trx_commit = 1

性能对比：
- 0: 1000+ TPS（高性能，低安全）
- 1: 500 TPS（低性能，高安全）
- 2: 800 TPS（中等性能，中等安全）
```

### 4. undolog（回滚日志）

#### 核心特性

```
名称：undolog（Undo Log）
层次：InnoDB引擎层
类型：逻辑日志
作用：
  1. 事务回滚：记录修改前的旧值，支持ROLLBACK
  2. MVCC：为其他事务提供一致性视图（快照读）
  3. 原子性保证：保证事务的ACID特性中的A
```

#### 记录内容

```sql
-- 场景：UPDATE操作
UPDATE user SET age = 30, name = 'Bob' WHERE id = 1;

-- undolog记录（逻辑日志）：
/*
表：user
主键：id = 1
旧值：age = 20, name = 'Alice'
操作类型：UPDATE
事务ID：trx_id = 12345
*/

-- 如果需要回滚：
-- 执行逆操作：UPDATE user SET age = 20, name = 'Alice' WHERE id = 1;
```

#### MVCC版本链

```
数据行的版本链（通过undolog形成）：

当前版本（数据页中）：
┌─────────────────────────────────────────┐
│ id=1, age=30, trx_id=103, roll_ptr=0x123│
└─────────────────────────────────────────┘
              │
              │ roll_ptr指向undolog
              ↓
历史版本1（undolog）：
┌─────────────────────────────────────────┐
│ id=1, age=25, trx_id=102, roll_ptr=0x124│
└─────────────────────────────────────────┘
              │
              ↓
历史版本2（undolog）：
┌─────────────────────────────────────────┐
│ id=1, age=20, trx_id=101, roll_ptr=NULL │
└─────────────────────────────────────────┘

不同事务根据Read View读取不同版本
```

#### Purge清理机制

```sql
-- undolog清理条件：
-- 1. 事务已提交或回滚
-- 2. 没有其他事务的Read View需要该版本

-- 查看undolog堆积
SHOW ENGINE INNODB STATUS\G
-- History list length: 1523  -- undolog数量

-- Purge线程定期清理
-- MySQL 5.6+支持多线程purge
innodb_purge_threads = 4  -- 4个purge线程

-- 清理速度监控
SHOW STATUS LIKE 'Innodb_purge%';
```

### 5. 三种日志的协同工作

#### 完整的更新流程

```
UPDATE语句的完整执行流程：

┌────────────────────────────────────────────────────┐
│ 1. 开始事务，分配事务ID（trx_id）                  │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 2. 写undolog                                        │
│    - 记录旧值（age=20）                             │
│    - 用于回滚和MVCC                                 │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 3. 更新Buffer Pool                                  │
│    - 修改内存中的数据页（age=30）                   │
│    - 标记为脏页                                     │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 4. 写redolog（prepare状态）                         │
│    - 记录物理修改                                   │
│    - 刷盘（根据innodb_flush_log_at_trx_commit）    │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 5. 写binlog                                         │
│    - 记录逻辑变更（SQL或行）                        │
│    - 刷盘（根据sync_binlog）                        │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 6. redolog状态改为commit                            │
│    - 事务提交完成                                   │
│    - 释放锁资源                                     │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 7. 异步刷脏页                                       │
│    - 后台线程将脏页写入磁盘                         │
│    - 推进checkpoint                                 │
└────────────────────────────────────────────────────┘
```

#### 两阶段提交保证一致性

```
为什么需要两阶段提交？

场景分析：
┌────────────────────────────────────────┐
│ 如果redolog和binlog分别写入：           │
├────────────────────────────────────────┤
│ Case 1: redolog成功，binlog失败        │
│ 结果：主库有数据，从库没有（不一致）   │
├────────────────────────────────────────┤
│ Case 2: binlog成功，redolog失败        │
│ 结果：主库崩溃恢复后数据丢失，          │
│       但从库有数据（不一致）            │
└────────────────────────────────────────┘

两阶段提交解决方案：
┌────────────────────────────────────────┐
│ Phase 1: Prepare                       │
│ - redolog写入并标记为prepare           │
├────────────────────────────────────────┤
│ Phase 2: Commit                        │
│ - 写binlog                              │
│ - redolog状态改为commit                │
└────────────────────────────────────────┘

崩溃恢复判断：
- redolog=prepare + binlog存在 → 提交事务
- redolog=prepare + binlog不存在 → 回滚事务
```

### 6. 在ACID中的作用

```
ACID特性实现机制：

Atomicity（原子性）
└─> undolog
    - 记录旧值，支持回滚
    - 保证事务要么全部成功，要么全部失败

Consistency（一致性）
└─> binlog + redolog（两阶段提交）
    - 保证主从数据一致
    - 保证binlog和数据文件一致

Isolation（隔离性）
└─> undolog（MVCC）+ 锁
    - undolog提供历史版本，实现快照读
    - 锁机制实现当前读的隔离

Durability（持久性）
└─> redolog
    - 事务提交后，redolog持久化
    - 崩溃后通过redolog恢复已提交事务
```

### 7. 性能优化配置

#### 生产环境推荐配置（安全优先）

```ini
# binlog配置
log_bin = mysql-bin
binlog_format = ROW  # ROW格式保证数据一致性
sync_binlog = 1  # 每次事务提交都刷盘

# redolog配置
innodb_log_file_size = 2G  # 单个文件2GB
innodb_log_files_in_group = 4  # 4个文件
innodb_flush_log_at_trx_commit = 1  # 每次提交都刷盘

# undolog配置
innodb_undo_tablespaces = 2  # 独立undo表空间
innodb_undo_log_truncate = ON  # 自动收缩

# purge优化
innodb_purge_threads = 4  # 4个purge线程
innodb_max_purge_lag = 0  # 不限制purge滞后
```

#### 高性能配置（可容忍少量数据丢失）

```ini
# 适用于非核心业务、可重建的数据

# binlog配置
sync_binlog = 100  # 每100个事务刷盘一次

# redolog配置
innodb_flush_log_at_trx_commit = 2  # 写OS缓存，每秒刷盘

# 性能提升：约2-3倍TPS
# 风险：最多丢失1秒的事务
```

### 8. 监控指标

```sql
-- 1. binlog监控
SHOW STATUS LIKE 'Binlog%';
-- Binlog_cache_use: binlog cache使用次数
-- Binlog_cache_disk_use: 溢出到磁盘次数（应该为0）

-- 2. redolog监控
SHOW ENGINE INNODB STATUS\G
-- Log sequence number: 当前LSN
-- Log flushed up to: 已刷盘的LSN
-- Pages flushed up to: 已刷数据页的LSN
-- Last checkpoint at: 最后checkpoint的LSN

-- 3. undolog监控
SHOW ENGINE INNODB STATUS\G
-- History list length: undolog堆积数量（<10000正常）

-- 4. 事务监控
SELECT COUNT(*) FROM information_schema.INNODB_TRX;
-- 当前活跃事务数
```

### 9. 常见问题排查

#### 问题1：undolog膨胀

```sql
-- 现象
SHOW ENGINE INNODB STATUS\G
-- History list length: 500000  -- 堆积严重

-- 原因排查
SELECT trx_id, trx_started, trx_query
FROM information_schema.INNODB_TRX
ORDER BY trx_started LIMIT 1;
-- 找到最早的事务（长事务）

-- 解决
KILL {thread_id};  -- kill掉长事务
```

#### 问题2：redolog空间不足

```sql
-- 现象：所有写操作阻塞

-- 原因排查
SHOW ENGINE INNODB STATUS\G
-- 查看write pos和checkpoint的位置
-- 如果write pos接近checkpoint，说明空间不足

-- 解决
-- 1. 等待checkpoint推进（刷脏页）
-- 2. 增大redolog文件大小
```

### 10. 答题总结

面试时可这样回答：

> MySQL有三种核心日志，分工明确，协同工作：
>
> **binlog**是Server层的逻辑日志，记录所有变更，主要用于主从复制和数据恢复。采用追加写，支持STATEMENT、ROW、MIXED三种格式。
>
> **redolog**是InnoDB的物理日志，记录数据页的修改，保证事务持久性。采用固定大小的循环写，配合WAL机制实现高性能和crash-safe能力。
>
> **undolog**也是InnoDB的逻辑日志，记录修改前的旧值，用于事务回滚和MVCC。通过版本链实现快照读，由purge线程异步清理。
>
> **协同工作**：三种日志通过两阶段提交协议保持一致性，共同实现ACID特性：undolog保证原子性和隔离性，redolog保证持久性，binlog配合redolog保证一致性。
>
> **生产配置**：推荐双1配置（innodb_flush_log_at_trx_commit=1, sync_binlog=1）+ ROW格式binlog + 多线程purge，确保数据安全和性能平衡。

**关键要点**：
- 三种日志层次、类型、作用各不相同
- 两阶段提交保证binlog和redolog一致性
- undolog支持MVCC，需要及时清理
- WAL机制是性能优化的核心
