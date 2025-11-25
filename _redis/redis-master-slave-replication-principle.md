---
title: "Redis的主从复制原理"
date: 2025-11-02
description: "深入解析Redis主从复制的工作原理，包括全量同步、增量同步、复制偏移量、复制积压缓冲区等核心机制"
author: "wuxl"
categories: [中间件]
tags: [Redis, 主从复制, 高可用, 同步机制]
nav_order: 418
parent: Redis
---
## 问题

Redis的主从复制原理是什么？

## 答案

### 1. 核心概念

**主从复制（Replication）**是Redis实现读写分离和高可用的基础机制。通过将主节点（Master）的数据复制到一个或多个从节点（Slave/Replica），实现：
- **读写分离**：主节点处理写请求，从节点处理读请求，提升并发能力
- **数据冗余**：多副本存储，防止单点故障
- **故障恢复**：主节点宕机时，从节点可以快速升级为主节点

---

### 2. 主从复制的工作原理

#### 2.1 复制流程概览

```
[从节点]                          [主节点]
   |                                 |
   |-- (1) PSYNC replicationId offset -->
   |                                 |
   |                判断同步类型      |
   |                                 |
   |<-- (2) +FULLRESYNC runId offset --  (全量同步)
   |                                 |
   |<-- (3) RDB快照文件 ---------------
   |                                 |
   |-- (4) 加载RDB到内存              |
   |                                 |
   |<-- (5) 发送复制期间的写命令缓冲 ---
   |                                 |
   |<-- (6) 持续接收增量命令 ----------  (增量同步)
```

---

#### 2.2 全量同步（Full Resynchronization）

**触发条件**：
- 从节点首次连接主节点
- 从节点重启后复制ID改变
- 主节点重启后复制ID改变
- 复制偏移量过大，超出复制积压缓冲区范围

**执行步骤**：

```java
// 伪代码描述全量同步流程
public class FullResync {
    public void execute() {
        // 1. 从节点发送PSYNC命令
        String command = "PSYNC ? -1"; // ? 表示首次同步

        // 2. 主节点执行BGSAVE生成RDB快照
        masterNode.bgsave();

        // 3. 主节点将RDB文件发送给从节点
        sendRDBFile(slaveNode);

        // 4. 从节点清空旧数据，加载RDB文件
        slaveNode.flushAll();
        slaveNode.loadRDB();

        // 5. 主节点将BGSAVE期间的写命令（缓存在复制缓冲区）发送给从节点
        sendReplicationBuffer(slaveNode);

        // 6. 进入增量同步阶段
        enterIncrementalSync();
    }
}
```

**关键点**：
- **BGSAVE**：主节点fork子进程生成RDB，不阻塞主进程（写时复制机制）
- **复制缓冲区**：记录BGSAVE期间的写命令，避免数据丢失
- **网络开销**：全量同步会传输完整的RDB文件，数据量大时耗时较长

---

#### 2.3 增量同步（Partial Resynchronization）

**触发条件**：
- 从节点短时间断开后重连
- 复制偏移量仍在主节点的复制积压缓冲区（repl_backlog_buffer）范围内

**执行步骤**：

```
1. 从节点发送 PSYNC <replicationId> <offset>
2. 主节点判断offset是否在repl_backlog_buffer中
3. 如果在，返回 +CONTINUE，发送offset之后的增量命令
4. 从节点执行增量命令，完成数据同步
```

**关键配置**：

```bash
# 复制积压缓冲区大小（默认1MB）
repl-backlog-size 1mb

# 主节点无从节点连接时，保留缓冲区的时间（默认3600秒）
repl-backlog-ttl 3600
```

**优势**：
- 无需传输RDB文件，同步速度快
- 减轻网络和磁盘IO压力

---

### 3. 核心机制详解

#### 3.1 复制偏移量（Replication Offset）

- **主节点偏移量**：记录已发送给从节点的字节数
- **从节点偏移量**：记录已接收并执行的字节数
- **作用**：通过比对偏移量判断主从数据是否一致

```bash
# 查看复制信息
redis-cli INFO replication

# 输出示例
role:master
connected_slaves:2
slave0:ip=192.168.1.10,port=6379,state=online,offset=12345,lag=0
master_repl_offset:12345  # 主节点当前偏移量
```

---

#### 3.2 复制积压缓冲区（Replication Backlog Buffer）

**环形缓冲区**，默认1MB，记录最近的写命令：

```
[ CMD1 | CMD2 | CMD3 | ... | CMDn ]
  ^                              ^
  oldest                      newest
```

**大小设置建议**：
```bash
# 计算公式：repl-backlog-size = 平均写命令速率 × 2 × 预计断线时间
# 例如：100KB/s × 2 × 60s = 12MB
repl-backlog-size 12mb
```

---

#### 3.3 复制ID（Replication ID）

每个Redis实例有唯一的40位十六进制复制ID：
- **作用**：标识主节点身份，从节点通过复制ID判断是否需要全量同步
- **变化时机**：
  - 实例首次启动
  - 从节点晋升为主节点
  - 主节点重启

---

### 4. 主从复制的配置与命令

#### 4.1 配置从节点

```bash
# 方式1：配置文件 redis.conf
replicaof 192.168.1.100 6379
masterauth <password>  # 主节点设置了密码时需要

# 方式2：命令行动态配置
redis-cli REPLICAOF 192.168.1.100 6379
```

#### 4.2 常用命令

```bash
# 查看复制状态
INFO replication

# 手动触发全量同步
REPLICAOF NO ONE  # 断开复制
REPLICAOF 192.168.1.100 6379  # 重新连接

# 查看主从延迟
redis-cli --latency -h 192.168.1.10
```

---

### 5. 性能优化与注意事项

#### 5.1 全量同步的性能开销

- **主节点**：BGSAVE会短暂阻塞（fork子进程时），占用CPU和内存
- **网络**：RDB文件传输占用带宽
- **从节点**：加载RDB期间无法提供服务

**优化方法**：
- 避免频繁的全量同步（合理设置repl-backlog-size）
- 主从节点部署在同一机房，减少网络延迟
- 使用无盘复制（repl-diskless-sync yes），直接通过网络发送RDB

#### 5.2 主从延迟问题

**原因**：
- 网络抖动
- 从节点性能不足（慢查询、持久化阻塞）
- 主节点写入压力大

**监控指标**：
```bash
# 从节点延迟（lag）秒数
INFO replication | grep lag
```

**解决方案**：
- 从节点开启只读模式（replica-read-only yes）
- 关闭从节点的AOF持久化，减轻IO压力
- 升级从节点硬件配置

---

### 6. 面试答题总结

**标准回答模板**：

> Redis主从复制通过 **异步方式** 将主节点的数据同步到从节点，分为两种模式：
> 1. **全量同步**：从节点首次连接或复制ID改变时，主节点执行BGSAVE生成RDB快照并发送给从节点
> 2. **增量同步**：从节点短暂断线重连后，主节点只发送复制积压缓冲区中缺失的命令
>
> **核心机制**：
> - **复制偏移量**：主从节点通过偏移量判断数据一致性
> - **复制积压缓冲区**：环形缓冲区（默认1MB），支持增量同步
> - **复制ID**：标识主节点身份，重启或切换时会变化
>
> **工程实践**：
> - 合理配置 `repl-backlog-size`，减少全量同步频率
> - 监控主从延迟（lag），及时发现性能瓶颈
> - 生产环境建议部署至少2个从节点，配合哨兵模式实现高可用

**常见追问**：
- **全量同步会阻塞主节点吗？** → BGSAVE通过fork子进程执行，仅fork时短暂阻塞（通常几十毫秒）
- **复制积压缓冲区大小如何设置？** → 根据写入速率和预计断线时间计算，建议10MB以上
- **主从复制是同步还是异步？** → 异步复制，主节点不等待从节点确认即返回（提升性能，但可能丢数据）
