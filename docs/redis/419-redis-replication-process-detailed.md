---
layout: default
title: "Redis主从复制过程详解"
parent: Redis
nav_order: 419
description: "详细剖析Redis主从复制的完整流程，包括连接建立、数据同步、命令传播、心跳检测等各个阶段的具体实现"
author: "wuxl"
date: 2025-11-02
---
## 问题

Redis主从复制的完整过程是怎样的？

## 答案

### 1. 核心概念

**Redis主从复制（Replication）**是将主节点的数据复制到从节点的过程，分为 **全量同步** 和 **增量同步** 两种方式。整个过程包括连接建立、数据同步、命令传播、心跳检测等多个阶段。

---

### 2. 主从复制完整流程

```
[从节点]                                    [主节点]
   |                                          |
   |  阶段1: 建立连接                          |
   |-- (1) PSYNC replicationId offset ------->|
   |                                          |
   |  阶段2: 判断同步类型                      |
   |                                          |
   |<-- (2) +FULLRESYNC runId offset ---------| (全量同步)
   |   或                                      |
   |<-- (2) +CONTINUE -------------------------| (增量同步)
   |                                          |
   |  阶段3: 数据同步                          |
   |<-- (3) RDB快照文件 -----------------------|
   |-- (4) 加载RDB到内存                      |
   |<-- (5) 发送RDB期间的写命令缓冲 -----------|
   |                                          |
   |  阶段4: 命令传播                          |
   |<-- (6) 持续接收写命令 ---------------------|
   |                                          |
   |  阶段5: 心跳检测                          |
   |-- (7) REPLCONF ACK <offset> ------------->|
   |                                          |
```

---

### 3. 各阶段详细解析

#### 阶段1: 建立连接与身份验证

**步骤1：从节点发起连接**
```bash
# 从节点配置
replicaof 192.168.1.100 6379
```

**步骤2：身份验证（如果主节点设置了密码）**
```bash
# 从节点配置文件
masterauth <password>
```

**步骤3：从节点发送监听端口信息**
```bash
REPLCONF listening-port 6380
```

**步骤4：从节点发送能力声明**
```bash
REPLCONF capa eof capa psync2  # 支持PSYNC2协议
```

**步骤5：从节点发送PSYNC命令**
```bash
# 首次复制
PSYNC ? -1

# 部分复制
PSYNC <replicationId> <offset>
```

---

#### 阶段2: 主节点判断同步类型

**判断逻辑**：
```java
public class SyncTypeDecision {
    public String decideSyncType(String replId, long offset) {
        // 情况1: 首次复制（replId为?或offset为-1）
        if ("?".equals(replId) || offset == -1) {
            return "FULLRESYNC";  // 全量同步
        }

        // 情况2: replId不匹配（主节点重启或从节点连接了新主节点）
        if (!replId.equals(currentReplId)) {
            return "FULLRESYNC";
        }

        // 情况3: offset不在复制积压缓冲区范围内
        if (offset < replBacklogFirstByte || offset > replBacklogOffset) {
            return "FULLRESYNC";
        }

        // 情况4: offset在复制积压缓冲区范围内
        return "CONTINUE";  // 增量同步
    }
}
```

**主节点响应**：
```bash
# 全量同步
+FULLRESYNC <runId> <offset>

# 增量同步
+CONTINUE
```

---

#### 阶段3: 数据同步（全量同步）

**步骤1：主节点执行BGSAVE**
```java
// 主节点伪代码
public class FullSync {
    public void execute() {
        // 1. fork子进程生成RDB快照
        pid_t pid = fork();
        if (pid == 0) {
            // 子进程执行RDB持久化
            rdbSave("/tmp/dump.rdb");
            exit(0);
        }

        // 2. 主进程继续处理写命令，并缓存到复制缓冲区
        while (rdbSaving) {
            Command cmd = receiveWriteCommand();
            replicationBuffer.add(cmd);  // 缓存写命令
        }
    }
}
```

**步骤2：传输RDB文件**
```
主节点 ---> 发送RDB文件 (可能数GB) ---> 从节点
```

**步骤3：从节点清空旧数据并加载RDB**
```java
public class SlaveLoadRDB {
    public void execute() {
        // 1. 清空从节点现有数据
        flushAll();

        // 2. 加载RDB文件到内存
        loadRDB("/tmp/dump.rdb");

        // 3. 更新复制偏移量和复制ID
        this.replOffset = masterReplOffset;
        this.replId = masterReplId;
    }
}
```

**步骤4：发送BGSAVE期间的写命令**
```
主节点 ---> 发送复制缓冲区中的命令 ---> 从节点执行
```

---

#### 阶段3: 数据同步（增量同步）

**触发条件**：从节点短暂断开后重连，且复制偏移量仍在复制积压缓冲区范围内。

**执行流程**：
```java
public class PartialSync {
    public void execute(long slaveOffset) {
        // 1. 从复制积压缓冲区中提取缺失的命令
        List<Command> commands = extractCommands(slaveOffset, currentOffset);

        // 2. 发送给从节点
        for (Command cmd : commands) {
            sendToSlave(cmd);
        }

        // 3. 从节点执行命令
        slave.executeCommands(commands);
    }

    private List<Command> extractCommands(long startOffset, long endOffset) {
        // 从环形缓冲区中按偏移量提取命令
        return replBacklogBuffer.getRange(startOffset, endOffset);
    }
}
```

**优势**：
- 无需传输RDB文件，速度快
- 对主节点性能影响小（无需BGSAVE）

---

#### 阶段4: 命令传播（持续同步）

**同步完成后的正常运行阶段**：

**主节点操作**：
```java
public class CommandPropagation {
    public void propagateCommand(Command cmd) {
        // 1. 主节点执行写命令
        executeCommand(cmd);

        // 2. 将命令发送给所有从节点
        for (Slave slave : connectedSlaves) {
            slave.sendCommand(cmd);
        }

        // 3. 写入复制积压缓冲区
        replBacklogBuffer.append(cmd);

        // 4. 更新复制偏移量
        this.replOffset += cmd.getBytes().length;
    }
}
```

**从节点操作**：
```java
public class SlaveExecuteCommand {
    public void execute(Command cmd) {
        // 1. 执行接收到的命令
        executeCommand(cmd);

        // 2. 更新复制偏移量
        this.replOffset += cmd.getBytes().length;
    }
}
```

---

#### 阶段5: 心跳检测与延迟监控

**从节点定期发送心跳**：
```bash
# 从节点每秒发送一次（默认1秒）
REPLCONF ACK <offset>
```

**心跳的三大作用**：

**1. 检测主从网络状态**
```java
// 主节点检测从节点是否在线
public boolean isSlaveAlive(Slave slave) {
    long lastAck = slave.getLastAckTime();
    long timeout = System.currentTimeMillis() - lastAck;
    return timeout < repl_timeout;  // 默认60秒
}
```

**2. 汇报复制偏移量**
```java
// 主节点计算主从延迟
public long calculateLag(Slave slave) {
    return this.replOffset - slave.getReplOffset();
}
```

**3. 实现min-replicas机制**
```bash
# 主节点配置：至少1个从节点延迟<10秒才允许写入
min-replicas-to-write 1
min-replicas-max-lag 10
```

```java
// 主节点写入前检查
public boolean canWrite() {
    int validSlaves = 0;
    for (Slave slave : connectedSlaves) {
        long lag = (System.currentTimeMillis() - slave.getLastAckTime()) / 1000;
        if (lag <= minReplicasMaxLag) {
            validSlaves++;
        }
    }
    return validSlaves >= minReplicasToWrite;
}
```

---

### 4. 关键机制详解

#### 4.1 复制偏移量（Replication Offset）

**主节点偏移量**：
```bash
redis-cli INFO replication | grep master_repl_offset
# 输出: master_repl_offset:123456
```

**从节点偏移量**：
```bash
redis-cli INFO replication | grep slave_repl_offset
# 输出: slave0:offset=123450,lag=0
```

**偏移量作用**：
- 判断主从数据是否一致（差值为0表示同步）
- 决定是否可以进行增量同步

---

#### 4.2 复制积压缓冲区（Replication Backlog）

**环形缓冲区结构**：
```
+---+---+---+---+---+---+---+---+
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |  (固定大小，如1MB)
+---+---+---+---+---+---+---+---+
  ^                           ^
  oldest_offset           newest_offset
```

**配置参数**：
```bash
# 缓冲区大小（默认1MB）
repl-backlog-size 1mb

# 主节点无从节点连接后，保留缓冲区的时间（默认1小时）
repl-backlog-ttl 3600
```

**大小设置建议**：
```
repl-backlog-size = 平均写入速率 × 2 × 预计断线时间

例如：
- 平均写入速率: 100KB/s
- 预计断线时间: 60秒
- 计算: 100KB/s × 2 × 60s = 12MB
```

---

#### 4.3 无盘复制（Diskless Replication）

**传统方式**：主节点 → 磁盘RDB → 网络 → 从节点

**无盘复制**：主节点 → 直接通过网络发送 → 从节点

**配置开启**：
```bash
# 开启无盘复制
repl-diskless-sync yes

# 延迟开始时间（等待更多从节点连接，批量传输）
repl-diskless-sync-delay 5
```

**优势**：
- 节省磁盘IO，适合磁盘慢但网络快的场景
- 多个从节点可同时接收数据

---

### 5. 异常场景处理

#### 5.1 从节点断线重连

**场景**：从节点断开30秒后重连

**处理流程**：
```
1. 从节点发送 PSYNC <replId> <offset>
2. 主节点检查offset是否在复制积压缓冲区
3. 若在范围内 → 增量同步
4. 若超出范围 → 全量同步
```

---

#### 5.2 主节点重启

**场景**：主节点重启后replId改变

**处理流程**：
```
1. 从节点发送 PSYNC <old_replId> <offset>
2. 主节点检测到replId不匹配
3. 返回 +FULLRESYNC <new_replId> <new_offset>
4. 执行全量同步
```

---

#### 5.3 从节点延迟过大

**监控命令**：
```bash
redis-cli INFO replication | grep lag
# 输出: slave0:lag=15  (延迟15秒)
```

**原因分析**：
- 主节点写入压力大
- 从节点性能不足（慢查询、持久化阻塞）
- 网络带宽不足

**解决方案**：
- 关闭从节点的AOF持久化（`appendonly no`）
- 优化从节点慢查询
- 增加从节点硬件配置

---

### 6. 面试答题总结

**标准回答模板**：

> Redis主从复制分为五个阶段：
> 1. **建立连接**：从节点发送 `PSYNC <replId> <offset>` 命令到主节点
> 2. **判断同步类型**：主节点根据replId和offset判断全量同步（+FULLRESYNC）或增量同步（+CONTINUE）
> 3. **数据同步**：
>    - 全量同步：主节点BGSAVE生成RDB → 发送RDB → 发送缓冲区命令
>    - 增量同步：主节点从复制积压缓冲区发送缺失命令
> 4. **命令传播**：主节点持续将写命令发送给从节点
> 5. **心跳检测**：从节点每秒发送 `REPLCONF ACK <offset>`，汇报复制进度
>
> **核心机制**：
> - **复制偏移量**：判断主从数据一致性
> - **复制积压缓冲区**：支持增量同步（默认1MB，建议10MB+）
> - **无盘复制**：适合磁盘慢网络快的场景（repl-diskless-sync yes）
>
> **优化建议**：
> - 合理配置 `repl-backlog-size`，减少全量同步频率
> - 从节点关闭AOF持久化，降低IO压力
> - 配置 `min-replicas-to-write` 保证数据安全

**常见追问**：
- **BGSAVE期间主节点崩溃怎么办？** → 从节点会重新发起PSYNC，主节点重新执行全量同步
- **复制积压缓冲区满了会怎样？** → 旧数据被覆盖，从节点重连时offset超出范围，触发全量同步
- **主从复制是同步还是异步？** → 异步复制，主节点不等待从节点确认即返回（可能丢数据，但性能高）
