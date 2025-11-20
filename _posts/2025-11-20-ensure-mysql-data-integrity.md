---
layout: post
title: 如何保证 MySQL 数据不丢失？
categories: [Database]
tags: [MySQL, ACID, Transaction, WAL]
description: 深入解析 MySQL 保证数据持久性（Durability）的核心机制：Redo Log、Binlog 与双 1 配置。
keywords: MySQL Data Integrity, Redo Log, Binlog, WAL, ACID
---

## 1. 核心概念

保证数据不丢失，本质上是保证事务的 **持久性 (Durability)**。即便数据库宕机或断电，已提交的事务修改也不能丢失。

MySQL InnoDB 引擎依靠 **WAL (Write-Ahead Logging)** 技术，即“先写日志，再写磁盘”来保证数据安全。

## 2. 关键机制

### 2.1 Redo Log (重做日志)
- **作用**：记录物理数据页的修改（“在第 X 页第 Y 偏移量写了 Z”）。
- **机制**：事务提交时，必须先将 Redo Log 持久化到磁盘。如果系统崩溃，重启时通过重放 Redo Log 恢复内存中未刷盘的脏页数据。
- **特点**：循环写，物理日志。

### 2.2 Binlog (归档日志)
- **作用**：记录逻辑 SQL 语句（或行修改）。主要用于主从复制和数据恢复（Point-in-Time Recovery）。
- **机制**：事务提交时追加写入。

### 2.3 两阶段提交 (2PC)
为了保证 Redo Log 和 Binlog 的逻辑一致性，MySQL 使用两阶段提交：
1.  **Prepare 阶段**：写 Redo Log，标记为 Prepare。
2.  **Write 阶段**：写 Binlog。
3.  **Commit 阶段**：将 Redo Log 标记为 Commit。

## 3. 生产配置：双 1 设置

要真正保证数据 **零丢失**，必须在 `my.cnf` 中配置以下两个参数：

1.  **`innodb_flush_log_at_trx_commit = 1`**
    - 每次事务提交时，都将 Redo Log 强制刷入磁盘（fsync）。
    - 缺省为 1。如果设为 0 或 2，虽然性能提升，但断电会丢失 1秒 数据。

2.  **`sync_binlog = 1`**
    - 每次事务提交时，都将 Binlog 强制刷入磁盘。
    - 缺省可能为 0（由 OS 调度刷盘），宕机可能丢失 Binlog，导致主从不一致。

## 4. 总结

**面试回答示例：**
"保证 MySQL 数据不丢失主要靠 **Redo Log** 和 **Binlog**。
在底层，InnoDB 使用 **WAL** 技术，事务提交时优先持久化日志。
为了防止断电丢数据，生产环境必须开启 **'双1' 配置**：即 `innodb_flush_log_at_trx_commit=1` 和 `sync_binlog=1`，强制每次提交都刷盘。同时，MySQL 内部通过 **两阶段提交** 保证了 Redo Log 和 Binlog 的一致性。"
