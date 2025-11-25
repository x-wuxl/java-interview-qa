---
title: "MySQL主从复制的过程"
date: 2025-11-02
description: "详细解析MySQL主从复制的完整流程，包括binlog记录、IO线程、SQL线程的工作原理"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 主从复制, binlog, 高可用]
nav_order: 374
parent: 数据库MySQL
---
## 问题

MySQL主从复制的过程是怎样的？

## 答案

### 核心概念

MySQL主从复制是一种**异步复制机制**，通过将主库的变更操作记录到binlog（二进制日志）中，从库读取并重放这些日志来实现数据同步。

### 复制过程的三个关键步骤

#### 1. 主库记录binlog
- 主库在执行写操作（INSERT、UPDATE、DELETE、DDL等）时，将变更记录到**二进制日志（binlog）**
- binlog按照事务提交的顺序记录，保证数据的一致性
- 存储位置：通常在MySQL的数据目录下，文件名如`mysql-bin.000001`

#### 2. 从库IO线程拉取日志
- 从库启动**IO线程**，连接到主库
- IO线程通过主库的**binlog dump线程**读取binlog事件
- 将读取到的binlog内容写入到从库本地的**中继日志（relay log）**
- IO线程记录读取位置（master_log_file, master_log_pos）

#### 3. 从库SQL线程重放日志
- 从库启动**SQL线程**（也称为应用线程）
- SQL线程读取relay log中的事件，并按顺序执行SQL语句
- 执行完成后更新自己的数据，完成数据同步
- SQL线程记录应用位置（relay_log_file, relay_log_pos）

### 完整流程图示

```
主库（Master）                               从库（Slave）
    |                                            |
 [执行SQL]                                       |
    ↓                                            |
 [写入binlog]                                    |
    ↓                                            |
 [binlog dump线程] --------binlog事件------→ [IO线程]
                                                 ↓
                                          [写入relay log]
                                                 ↓
                                             [SQL线程]
                                                 ↓
                                          [执行SQL，同步数据]
```

### 关键配置参数

**主库配置：**
```properties
# 开启binlog
log-bin=mysql-bin
# 指定server-id（集群内唯一）
server-id=1
# binlog格式（ROW/STATEMENT/MIXED）
binlog_format=ROW
```

**从库配置：**
```properties
# 指定server-id（与主库不同）
server-id=2
# 开启中继日志
relay-log=mysql-relay-bin
# 从库只读（可选）
read_only=1
```

### 复制模式

1. **异步复制（默认）**：主库写入binlog后立即返回，不等待从库确认
2. **半同步复制**：主库至少等待一个从库确认接收binlog后才返回
3. **全同步复制**（组复制）：等待所有从库确认，类似于分布式事务

### 性能考量

- **主从延迟**：从库应用relay log的速度跟不上主库写入速度
- **优化方向**：
  - 使用并行复制（基于GTID或逻辑时钟）
  - 优化从库硬件（SSD、更多内存）
  - binlog格式选择ROW模式减少冲突
  - 监控`Seconds_Behind_Master`指标

### 面试答题总结

MySQL主从复制分三步：**主库写binlog → 从库IO线程拉取到relay log → 从库SQL线程重放执行**。这是一个异步过程，通过binlog记录和重放实现数据同步，常用于读写分离、高可用架构。需要注意主从延迟问题，可通过半同步复制或并行复制优化。
