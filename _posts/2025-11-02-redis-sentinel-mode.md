---
layout: post
title: "Redis的哨兵模式详解"
date: 2025-11-02
description: "深入讲解Redis哨兵模式的工作原理，包括监控、故障检测、自动故障转移、选主策略等核心机制"
author: "wuxl"
categories: [中间件]
tags: [Redis, 哨兵模式, Sentinel, 故障转移, 高可用]
---

## 问题

Redis的哨兵模式是什么？

## 答案

### 1. 核心概念

**Redis Sentinel（哨兵模式）**是Redis官方提供的高可用解决方案，通过监控主从节点，在主节点故障时自动完成故障转移（Failover），无需人工介入。

**核心功能**：
- **监控（Monitoring）**：持续检测主从节点和其他哨兵节点是否正常运行
- **通知（Notification）**：当监控的实例出现问题时，通过API发送通知
- **自动故障转移（Automatic Failover）**：主节点故障时，自动将从节点升级为主节点，并通知客户端
- **配置提供者（Configuration Provider）**：客户端连接哨兵获取当前主节点地址

---

### 2. 哨兵模式架构

```
        +----------------+
        |   Client       |
        +-------+--------+
                |
                | (1) 获取主节点地址
                v
    +----------+----------+----------+
    |          |          |          |
[Sentinel1] [Sentinel2] [Sentinel3]  (哨兵集群，至少3个)
    |          |          |
    +----------+----------+----------+
                |
        (2) 监控主从节点
                |
    +-----------+-----------+
    |                       |
 [Master]              [Slave1] [Slave2]
    |                       ^
    +------- 主从复制 -------+
```

**关键要点**：
- **哨兵集群**：通常部署奇数个（3/5/7个），通过投票机制保证决策的可靠性
- **客户端连接**：客户端不直接连接Redis节点，而是先从哨兵获取主节点地址
- **独立进程**：哨兵是独立的Redis进程，但只使用监控和管理功能

---

### 3. 哨兵模式工作原理

#### 3.1 监控机制

每个哨兵节点会执行以下任务：

```
1. 每10秒向主从节点发送 INFO 命令
   - 发现主从拓扑结构
   - 获取从节点信息和复制状态

2. 每2秒向所有节点的 __sentinel__:hello 频道发送消息
   - 交换哨兵之间的信息
   - 发现其他哨兵节点

3. 每1秒向主从节点和其他哨兵发送 PING 命令
   - 检测节点是否存活
   - 判断是否主观下线
```

---

#### 3.2 故障检测与判定

**主观下线（SDOWN - Subjectively Down）**：
- 单个哨兵认为节点下线
- 条件：哨兵在配置的 `down-after-milliseconds` 时间内未收到有效PING回复

```bash
# 哨兵配置示例
sentinel monitor mymaster 192.168.1.100 6379 2  # 至少2个哨兵同意才能故障转移
sentinel down-after-milliseconds mymaster 5000   # 5秒未响应判定主观下线
```

**客观下线（ODOWN - Objectively Down）**：
- 多个哨兵（达到quorum数量）认为节点下线
- 流程：
  1. 哨兵A检测到主节点主观下线
  2. 哨兵A向其他哨兵发送 `SENTINEL is-master-down-by-addr` 命令询问
  3. 收到quorum个确认后，判定主节点客观下线
  4. 触发故障转移流程

---

#### 3.3 自动故障转移流程

**完整流程**：

```java
// 伪代码描述故障转移流程
public class SentinelFailover {
    public void execute() {
        // 1. 选举领头哨兵（Leader Election）
        Sentinel leader = electLeader(); // Raft算法，先到先得

        // 2. 领头哨兵从从节点中选出新主节点
        Slave newMaster = selectNewMaster();

        // 3. 向新主节点发送 SLAVEOF NO ONE 命令，升级为主节点
        newMaster.execute("SLAVEOF NO ONE");

        // 4. 向其他从节点发送 SLAVEOF <new_master_ip> <port>，改变复制目标
        for (Slave slave : otherSlaves) {
            slave.execute("SLAVEOF " + newMaster.ip + " " + newMaster.port);
        }

        // 5. 更新哨兵配置，记录新主节点信息
        updateSentinelConfig(newMaster);

        // 6. 持续监控旧主节点，恢复后降级为从节点
        monitorOldMaster();
    }
}
```

**关键步骤详解**：

1️⃣ **选举领头哨兵**：
   - 使用Raft算法的简化版本
   - 先发起选举的哨兵成为候选者，向其他哨兵请求投票
   - 每个哨兵只投票一次，先到先得
   - 获得超过半数投票的哨兵成为Leader

2️⃣ **选出新主节点**（详见后续"选主策略"）：
   - 优先级高的从节点优先
   - 复制偏移量大的从节点优先（数据最新）
   - runID最小的从节点优先

3️⃣ **通知客户端**：
   - 哨兵通过发布/订阅机制向客户端发送 `+switch-master` 消息
   - 客户端（如Jedis、Lettuce）自动连接新主节点

---

### 4. 哨兵配置与部署

#### 4.1 哨兵配置文件（sentinel.conf）

```bash
# 监控的主节点（mymaster是别名，2是quorum值）
sentinel monitor mymaster 192.168.1.100 6379 2

# 主节点密码
sentinel auth-pass mymaster <password>

# 主观下线判定时间（毫秒）
sentinel down-after-milliseconds mymaster 5000

# 故障转移超时时间（毫秒）
sentinel failover-timeout mymaster 60000

# 同时向新主节点发起复制的从节点数量（并行度）
sentinel parallel-syncs mymaster 1

# 拒绝连接的客户端IP（可选）
sentinel deny-scripts-reconfig yes
```

#### 4.2 启动哨兵

```bash
# 方式1：使用redis-sentinel命令
redis-sentinel /path/to/sentinel.conf

# 方式2：使用redis-server并指定sentinel模式
redis-server /path/to/sentinel.conf --sentinel
```

---

### 5. 客户端集成

#### 5.1 Jedis集成示例

```java
import redis.clients.jedis.JedisSentinelPool;

public class SentinelClient {
    public static void main(String[] args) {
        // 哨兵节点地址集合
        Set<String> sentinels = new HashSet<>();
        sentinels.add("192.168.1.10:26379");
        sentinels.add("192.168.1.11:26379");
        sentinels.add("192.168.1.12:26379");

        // 创建哨兵连接池
        JedisSentinelPool pool = new JedisSentinelPool(
            "mymaster",        // 主节点名称
            sentinels,         // 哨兵节点集合
            "password"         // Redis密码
        );

        // 获取连接（自动连接当前主节点）
        try (Jedis jedis = pool.getResource()) {
            jedis.set("key", "value");
            System.out.println(jedis.get("key"));
        }

        pool.close();
    }
}
```

**客户端工作原理**：
1. 连接任意哨兵节点，发送 `SENTINEL get-master-addr-by-name mymaster` 获取主节点地址
2. 连接主节点进行读写操作
3. 订阅哨兵的 `+switch-master` 频道，监听主节点变化
4. 故障转移时，自动切换到新主节点

---

### 6. 性能优化与注意事项

#### 6.1 哨兵数量选择

- **最少3个**：支持一个哨兵故障时仍能正常工作
- **推荐5个**：支持两个哨兵故障，适合生产环境
- **避免偶数**：偶数个哨兵可能出现选举平票，影响决策效率

#### 6.2 quorum与majority的区别

- **quorum**：判定主节点客观下线需要的哨兵数量（配置文件中设置）
- **majority**：选举领头哨兵需要的投票数（哨兵总数 / 2 + 1）

**示例**：
- 5个哨兵，quorum=2：2个哨兵认为下线即可触发故障转移，但需要3个投票才能选出Leader
- 生产建议：quorum = 哨兵总数 / 2 + 1

#### 6.3 脑裂问题

**场景**：
- 网络分区导致旧主节点与哨兵失联
- 哨兵将从节点升级为新主节点
- 旧主节点仍接受写请求，导致数据丢失

**解决方案**：
```bash
# 主节点至少有N个从节点连接才允许写入
min-replicas-to-write 1

# 从节点延迟小于N秒才算有效连接
min-replicas-max-lag 10
```

---

### 7. 面试答题总结

**标准回答模板**：

> Redis哨兵模式是官方的高可用解决方案，通过多个哨兵节点（建议3/5个）监控主从节点，实现：
> 1. **监控**：每秒PING检测节点存活，每10秒INFO获取拓扑结构
> 2. **故障检测**：单个哨兵检测到主观下线（SDOWN）后，询问其他哨兵，达到quorum数量判定客观下线（ODOWN）
> 3. **自动故障转移**：选举领头哨兵（Raft算法）→ 选出新主节点（优先级、复制偏移量、runID）→ 通知客户端切换
>
> **核心配置**：
> - `sentinel monitor <name> <ip> <port> <quorum>`：监控主节点，quorum为判定下线的投票数
> - `sentinel down-after-milliseconds`：主观下线判定时间（建议5秒）
>
> **客户端集成**：通过JedisSentinelPool等连接哨兵，自动获取主节点地址并监听切换事件

**常见追问**：
- **哨兵如何发现其他哨兵？** → 通过向 `__sentinel__:hello` 频道发布消息
- **领头哨兵如何选举？** → Raft算法简化版，先发起选举的获得投票，超过半数即成为Leader
- **quorum和majority的区别？** → quorum判定下线，majority选举Leader（哨兵总数/2+1）
