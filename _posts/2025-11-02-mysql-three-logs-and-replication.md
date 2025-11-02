---
layout: post
title: "MySQL三种日志、主从架构与复制原理"
date: 2025-11-02
description: "全面解析MySQL的redo log、binlog、undo log三大日志机制，以及主从架构和复制原理的深度解读"
author: "wuxl"
categories: [数据库]
tags: [MySQL, redo log, binlog, undo log, 主从复制]
---

## 问题

MySQL三种日志是什么？主从架构？主从复制原理？

## 答案

### 一、MySQL三种日志

#### 1. redo log（重做日志）

**作用：** 保证事务的**持久性（Durability）**，实现**Crash Recovery（崩溃恢复）**

**核心机制：WAL（Write-Ahead Logging）**
```
修改数据流程：
1. 更新内存中的数据页（Buffer Pool）
2. 将修改记录写入redo log（顺序IO，快速）
3. 后台异步将脏页刷新到磁盘（随机IO，慢速）
```

**特点：**
- **物理日志**：记录"在某个数据页上做了什么修改"
- **循环写入**：固定大小，写满后从头覆盖（类似环形队列）
- **InnoDB特有**：属于存储引擎层，与MySQL Server层无关

**文件结构：**
```bash
# redo log文件（默认2个，各48MB）
ib_logfile0
ib_logfile1
```

**配置参数：**
```properties
innodb_log_file_size=512M          # 单个redo log文件大小
innodb_log_files_in_group=2        # redo log文件数量
innodb_flush_log_at_trx_commit=1   # 刷盘策略
# =0 每秒写入并刷盘（性能高，可能丢1秒数据）
# =1 每次事务提交都刷盘（最安全，性能低）
# =2 每次提交写入OS缓存，每秒刷盘（折中）
```

**工作示例：**
```sql
UPDATE users SET age = 30 WHERE id = 1;

-- redo log记录（伪代码）
-- 在表空间1，数据页100，偏移500处，将值从25改为30
Record: space_id=1, page_no=100, offset=500, old=25, new=30
```

**崩溃恢复流程：**
```
MySQL启动 → 读取redo log → 重放未刷盘的修改 → 恢复到崩溃前状态
```

#### 2. binlog（二进制日志）

**作用：** 用于**主从复制、数据恢复、审计**

**核心机制：** 记录所有DDL和DML语句

**特点：**
- **逻辑日志**：记录SQL语句（STATEMENT）或行变更（ROW）
- **追加写入**：写满后生成新文件，不会覆盖
- **Server层日志**：所有存储引擎都可以使用

**文件结构：**
```bash
mysql-bin.000001  # 第1个binlog文件
mysql-bin.000002  # 第2个binlog文件
mysql-bin.index   # binlog索引文件
```

**配置参数：**
```properties
log-bin=mysql-bin                  # 开启binlog
binlog_format=ROW                  # 格式（STATEMENT/ROW/MIXED）
sync_binlog=1                      # 刷盘策略
# =0 由操作系统控制刷盘
# =1 每次事务提交都刷盘（最安全）
# =N 每N个事务提交后刷盘
expire_logs_days=7                 # binlog保留天数
```

**三种格式对比：**
| 格式 | 记录内容 | 日志大小 | 一致性 |
|-----|---------|---------|-------|
| STATEMENT | SQL语句 | 小 | 可能不一致 |
| ROW | 行变更 | 大 | 强一致 |
| MIXED | 自动选择 | 中等 | 较好 |

#### 3. undo log（回滚日志）

**作用：** 保证事务的**原子性（Atomicity）**，实现**MVCC（多版本并发控制）**

**核心机制：** 记录数据修改前的旧值

**特点：**
- **逻辑日志**：记录相反的操作
- **存储位置**：存储在表空间的undo segment中
- **两大作用**：事务回滚 + MVCC快照读

**工作示例：**
```sql
-- 执行UPDATE
UPDATE users SET age = 30 WHERE id = 1;

-- undo log记录（回滚操作）
UPDATE users SET age = 25 WHERE id = 1;  -- 记录旧值25

-- 如果事务回滚
ROLLBACK;  -- 执行undo log中的操作，恢复到age=25
```

**MVCC应用：**
```sql
-- 事务A
BEGIN;
UPDATE users SET age = 30 WHERE id = 1;
-- 未提交，undo log保存旧值age=25

-- 事务B（并发执行）
SELECT age FROM users WHERE id = 1;  -- 快照读
-- 通过undo log读取旧版本数据：age=25
-- 实现了隔离性，不会读到事务A未提交的数据
```

**undo log清理：**
```sql
-- undo log在所有比它更早的ReadView（快照）都关闭后才会被清理
-- 长事务会导致undo log堆积，占用大量空间

-- 查看undo log占用
SELECT COUNT(*) FROM information_schema.INNODB_TRX
WHERE TIME_TO_SEC(TIMEDIFF(NOW(), trx_started)) > 60;
```

### 三种日志对比表

| 日志类型 | 层级 | 日志类型 | 主要作用 | 写入时机 | 文件特点 |
|---------|------|---------|---------|---------|---------|
| redo log | 引擎层 | 物理日志 | 崩溃恢复 | 事务执行中 | 循环覆盖 |
| binlog | Server层 | 逻辑日志 | 主从复制/数据恢复 | 事务提交时 | 追加写入 |
| undo log | 引擎层 | 逻辑日志 | 事务回滚/MVCC | 事务执行前 | 自动清理 |

### 二、主从架构

#### 常见主从架构模式

**1. 一主多从（最常见）**
```
         主库（Master）
           /  |  \
          /   |   \
       从库1 从库2 从库3
```

**优点：**
- 读写分离：主库写，从库读
- 横向扩展读能力
- 数据备份与高可用

**2. 级联复制**
```
      主库
       ↓
      从库1
      /  \
   从库2 从库3
```

**优点：** 减轻主库网络压力
**缺点：** 延迟累加

**3. 双主架构**
```
  主库A ←→ 主库B
```

**优点：** 互为备份，快速切换
**缺点：** 可能数据冲突

### 三、主从复制原理

#### 复制流程三步曲

```
【主库】                           【从库】
  ↓
1. 执行SQL → 写binlog              
  ↓                                 ↓
2. [Binlog Dump Thread] -------→ [IO Thread]
                                   ↓
                              3. 写relay log
                                   ↓
                               [SQL Thread]
                                   ↓
                              4. 执行SQL
```

**详细步骤：**

**步骤1：主库记录binlog**
```sql
-- 主库执行
UPDATE users SET age = 30 WHERE id = 1;

-- 写入binlog
BEGIN;
UPDATE users SET age = 30 WHERE id = 1;
COMMIT;
```

**步骤2：从库IO线程拉取binlog**
- 从库IO线程连接主库
- 主库启动Binlog Dump线程
- IO线程读取binlog事件
- 写入本地relay log（中继日志）

**步骤3：从库SQL线程重放**
- SQL线程读取relay log
- 按顺序执行SQL语句
- 更新从库数据

#### 复制位点

**基于位置的复制：**
```sql
-- 主库查看binlog位置
SHOW MASTER STATUS;
+------------------+----------+
| File             | Position |
+------------------+----------+
| mysql-bin.000003 |      154 |
+------------------+----------+

-- 从库配置
CHANGE MASTER TO
  MASTER_LOG_FILE='mysql-bin.000003',
  MASTER_LOG_POS=154;
```

**基于GTID的复制（推荐）：**
```sql
-- GTID：全局事务ID（server_uuid:transaction_id）
-- 示例：3e11fa47-71ca-11e5-9e11-fa163e6dd4e8:1-20

-- 主库配置
gtid_mode=ON
enforce_gtid_consistency=ON

-- 从库配置（自动定位，无需指定文件和位置）
CHANGE MASTER TO
  MASTER_HOST='192.168.1.100',
  MASTER_USER='repl',
  MASTER_PASSWORD='password',
  MASTER_AUTO_POSITION=1;
```

#### 三种复制模式

**1. 异步复制（默认）**
```
主库：写binlog → 立即返回成功
从库：异步拉取和应用
```
- 性能高，可能丢数据

**2. 半同步复制**
```
主库：写binlog → 等待至少1个从库确认 → 返回成功
从库：接收到binlog后立即确认
```
- 更可靠，性能略降

**3. 全同步（MGR）**
```
主库：写binlog → 等待多数节点确认 → 返回成功
```
- 强一致，性能损失大

#### redo log与binlog的两阶段提交

**为什么需要两阶段提交？**
保证redo log和binlog的一致性，防止主从数据不一致。

**提交流程：**
```
1. 执行器调用InnoDB执行更新
   ↓
2. InnoDB写redo log（prepare状态）
   ↓
3. 执行器写binlog
   ↓
4. InnoDB提交事务，redo log改为commit状态
```

**崩溃恢复策略：**
- redo log处于prepare，binlog完整 → 提交事务
- redo log处于prepare，binlog不完整 → 回滚事务
- redo log处于commit → 事务已完成

**示例场景：**
```sql
UPDATE users SET age = 30 WHERE id = 1;

-- 步骤1：redo log写入prepare
-- 步骤2：binlog写入
-- [此时MySQL崩溃]
-- 步骤3：重启后，发现redo log为prepare且binlog完整
-- 步骤4：自动提交事务（保证主从一致）
```

### 监控关键指标

```sql
-- 从库状态
SHOW SLAVE STATUS\G

-- 关键指标
Slave_IO_Running: Yes           -- IO线程正常
Slave_SQL_Running: Yes          -- SQL线程正常
Seconds_Behind_Master: 0        -- 延迟秒数
Master_Log_File                 -- 主库binlog文件
Read_Master_Log_Pos             -- 已读取位置
Exec_Master_Log_Pos             -- 已执行位置
```

### 面试答题总结

**MySQL三种日志：**
1. **redo log**：InnoDB引擎层物理日志，保证持久性，循环写入，用于崩溃恢复
2. **binlog**：Server层逻辑日志，保证主从复制和数据恢复，追加写入
3. **undo log**：InnoDB逻辑日志，保证原子性和MVCC，记录旧值用于回滚

**主从架构：** 一主多从最常见，主库写入，从库读取，实现读写分离和高可用。

**主从复制原理：** 三步走：主库写binlog → 从库IO线程拉取到relay log → 从库SQL线程重放执行。使用GTID简化复制配置。redo log和binlog通过两阶段提交保证一致性，防止崩溃时数据不一致。
