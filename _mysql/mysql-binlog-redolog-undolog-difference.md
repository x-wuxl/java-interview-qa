---
title: "binlog、redolog和undolog的区别"
date: 2025-11-02
description: "详细解析MySQL三种核心日志的区别：binlog、redolog和undolog的作用、实现原理及使用场景"
author: "wuxl"
categories: [数据库]
tags: [MySQL, binlog, redolog, undolog, 日志系统, 事务]
nav_order: 373
parent: 数据库MySQL
---
## 问题

binlog、redolog和undolog区别?

## 答案

### 1. 核心概念

MySQL的三种日志分别在不同层面保障数据的**持久性、一致性和可恢复性**：

- **binlog（二进制日志）**：Server层日志，记录所有DDL和DML语句，用于主从复制和数据恢复
- **redolog（重做日志）**：InnoDB引擎层日志，记录数据页的物理修改，保证事务的持久性（Durability）
- **undolog（回滚日志）**：InnoDB引擎层日志，记录数据修改前的版本，用于事务回滚和MVCC

### 2. 详细对比

| 对比维度 | binlog | redolog | undolog |
|---------|--------|---------|---------|
| **所属层次** | Server层（所有引擎共享） | InnoDB引擎层 | InnoDB引擎层 |
| **日志类型** | 逻辑日志 | 物理日志 | 逻辑日志 |
| **记录内容** | SQL语句或行变更 | 数据页的物理修改 | 修改前的旧值 |
| **写入时机** | 事务提交时写入 | 事务执行过程中循环写入 | 事务执行前写入 |
| **写入方式** | 追加写（append） | 循环写（circular） | 随机写 |
| **文件大小** | 持续增长（可配置清理） | 固定大小（如1GB×4） | 动态增长（可清理） |
| **主要作用** | 主从复制、数据恢复 | 崩溃恢复（crash-safe） | 事务回滚、MVCC |
| **保证特性** | 数据一致性 | 持久性（D） | 原子性（A）、隔离性（I） |

### 3. 工作原理

#### binlog工作流程
```sql
-- 事务提交时写入binlog
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;
-- 此时binlog还未写入
COMMIT;  -- 提交时才写入binlog
```

**binlog写入过程**：
1. 事务执行时，将变更写入binlog cache（内存）
2. 事务提交时，将binlog cache写入binlog文件的page cache
3. 根据`sync_binlog`参数决定何时刷盘（fsync）

#### redolog工作流程
```
更新语句执行流程：
1. 从内存/磁盘读取数据页到Buffer Pool
2. 修改数据页（脏页）
3. 写redo log buffer
4. 写redo log file（WAL机制）
5. 返回客户端"执行成功"
6. 后台线程异步刷脏页到磁盘
```

**redolog循环写**：
- 固定大小空间（如4个1GB文件）
- write pos：当前写入位置
- checkpoint：当前擦除位置
- write pos追上checkpoint时需要停止更新，先推进checkpoint

#### undolog工作流程
```sql
-- 事务开始前写入undolog
UPDATE account SET balance = 200 WHERE id = 1;
-- undolog记录: id=1, balance=100（旧值）

-- 如果回滚
ROLLBACK;  -- 使用undolog恢复 balance=100
```

### 4. 使用场景与考量

#### 性能优化场景

**binlog配置**：
```ini
# 0: 不主动sync，由操作系统决定（性能最好，可能丢失）
# 1: 每次事务提交都sync（最安全，性能较差）
# N: 每N个事务提交sync一次（折中方案）
sync_binlog = 1
```

**redolog配置**：
```ini
# 控制redolog刷盘策略
# 0: 每秒写入并刷盘
# 1: 每次事务提交都刷盘（默认，最安全）
# 2: 每次事务提交写入OS缓存，每秒刷盘
innodb_flush_log_at_trx_commit = 1
```

#### 双1配置（生产推荐）
```ini
# 保证数据不丢失的双1配置
innodb_flush_log_at_trx_commit = 1
sync_binlog = 1
```

#### 高可用场景
- **主从复制**：依赖binlog实现数据同步
- **崩溃恢复**：先用redolog恢复已提交事务，再用undolog回滚未提交事务
- **MVCC**：通过undolog实现多版本并发控制，避免读写冲突

### 5. 答题总结

面试时可这样回答：

> MySQL有三种核心日志，分别工作在不同层面：
>
> **binlog**是Server层的逻辑日志，记录所有表的变更，主要用于主从复制和数据恢复，采用追加写方式。
>
> **redolog**是InnoDB的物理日志，记录数据页的具体修改，保证事务持久性。它采用固定大小的循环写，配合WAL机制实现crash-safe能力。
>
> **undolog**也是InnoDB的逻辑日志，记录修改前的旧值，用于事务回滚和MVCC实现。
>
> 生产环境通常采用"双1配置"（innodb_flush_log_at_trx_commit=1, sync_binlog=1）来保证数据安全，这三种日志配合两阶段提交协议，共同保证了MySQL的ACID特性。

**关键要点**：
- binlog用于复制和备份（Server层）
- redolog用于崩溃恢复（持久性）
- undolog用于回滚和MVCC（原子性和隔离性）
- 三者通过两阶段提交协议保持一致性
