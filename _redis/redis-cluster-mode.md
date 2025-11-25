---
title: "Redis的集群模式详解"
date: 2025-11-02
description: "深入解析Redis Cluster集群模式的原理，包括数据分片、槽位分配、节点通信、故障转移等核心机制"
author: "wuxl"
categories: [中间件]
tags: [Redis, 集群模式, Redis Cluster, 数据分片, 分布式]
nav_order: 423
parent: Redis
---
## 问题

Redis的集群模式是什么？

## 答案

### 1. 核心概念

**Redis Cluster（集群模式）**是Redis官方提供的分布式解决方案，通过数据分片（Sharding）实现水平扩展，解决单机内存和性能瓶颈。

**核心特性**：
- **去中心化**：无需代理节点（如Codis的Proxy），客户端直接访问数据节点
- **数据分片**：将数据分散到多个主节点，每个主节点负责一部分数据
- **高可用**：支持主从复制和自动故障转移
- **横向扩展**：可在线增减节点，动态调整槽位分配

---

### 2. 集群架构

```
      客户端
        |
        | (1) 计算key所属slot
        v
  +-----+-----+-----+
  |     |     |     |
Master1 M2   M3   (主节点，各负责部分slot)
  |     |     |
Slave1  S2   S3   (从节点，主从复制)

Master1: slot 0-5460
Master2: slot 5461-10922
Master3: slot 10923-16383
```

**关键要点**：
- **最少6个节点**：3主3从，保证高可用
- **16384个槽位（slot）**：每个key通过CRC16哈希后对16384取模，映射到对应槽位
- **槽位分配**：每个主节点负责一段连续或分散的槽位

---

### 3. 数据分片机制

#### 3.1 槽位（Slot）算法

Redis Cluster将数据空间划分为 **16384个槽位**（0-16383），每个key根据以下算法映射到槽位：

```java
// 槽位计算算法
public class RedisClusterSlot {
    private static final int SLOT_COUNT = 16384;

    public static int calculateSlot(String key) {
        // 1. 检查是否有HashTag（用于将多个key映射到同一slot）
        String hashKey = getHashTagKey(key);

        // 2. CRC16计算并对16384取模
        int slot = CRC16.crc16(hashKey.getBytes()) % SLOT_COUNT;
        return slot;
    }

    // HashTag提取：{user:1001}:info -> user:1001
    private static String getHashTagKey(String key) {
        int start = key.indexOf('{');
        if (start != -1) {
            int end = key.indexOf('}', start + 1);
            if (end != -1 && end > start + 1) {
                return key.substring(start + 1, end);
            }
        }
        return key;
    }
}
```

**HashTag用途**：
```java
// 场景：保证同一用户的多个key在同一节点，支持批量操作
jedis.mset(
    "{user:1001}:name", "Alice",
    "{user:1001}:age", "30"
);
// 两个key的HashTag都是"user:1001"，映射到同一slot
```

---

#### 3.2 槽位分配策略

**初始化集群时**：
```bash
# 创建集群（Redis 5.0+）
redis-cli --cluster create \
  192.168.1.10:7000 192.168.1.11:7000 192.168.1.12:7000 \
  192.168.1.10:7001 192.168.1.11:7001 192.168.1.12:7001 \
  --cluster-replicas 1  # 每个主节点1个从节点

# 输出示例：
# Master1 (7000): slots 0-5460
# Master2 (7000): slots 5461-10922
# Master3 (7000): slots 10923-16383
```

**在线迁移槽位**：
```bash
# 迁移slot 100从节点A到节点B
redis-cli --cluster reshard 192.168.1.10:7000 \
  --cluster-from <nodeA_id> \
  --cluster-to <nodeB_id> \
  --cluster-slots 1 \
  --cluster-yes
```

---

### 4. 节点通信机制（Gossip协议）

#### 4.1 Gossip协议

Redis Cluster节点通过 **Gossip协议** 交换集群状态信息：

```
节点A                节点B                节点C
  |                    |                    |
  |-- PING ----------->|                    |
  |<-- PONG -----------|                    |
  |                    |-- PING ----------->|
  |                    |<-- PONG -----------|
  |-- MEET ----------->|                    |
  |                    |-- MEET ----------->|
```

**消息类型**：
- **PING/PONG**：心跳检测，携带自身状态和部分其他节点信息
- **MEET**：通知节点加入集群
- **FAIL**：广播节点下线消息

**通信端口**：
- **数据端口**：如7000，用于客户端读写
- **集群总线端口**：数据端口+10000（如17000），用于节点间通信

---

#### 4.2 槽位信息同步

每个节点维护 **槽位映射表**：
```
Slot 0-5460    -> 节点A (192.168.1.10:7000)
Slot 5461-10922 -> 节点B (192.168.1.11:7000)
Slot 10923-16383 -> 节点C (192.168.1.12:7000)
```

**客户端请求流程**：
1. 客户端连接任意节点，计算key所属slot
2. 若slot不在当前节点，返回 `MOVED <slot> <ip>:<port>` 重定向
3. 客户端缓存槽位映射表，后续请求直接访问正确节点

```java
// Jedis客户端示例
JedisCluster jedis = new JedisCluster(
    new HostAndPort("192.168.1.10", 7000)
);

// 自动处理MOVED重定向
jedis.set("key1", "value1");
```

---

### 5. 故障检测与转移

#### 5.1 故障检测

**主观下线（PFAIL）**：
- 单个节点认为目标节点下线
- 条件：超过 `cluster-node-timeout` 未收到PONG回复（默认15秒）

**客观下线（FAIL）**：
- 半数以上主节点认为目标节点下线
- 触发自动故障转移

---

#### 5.2 自动故障转移

```java
// 故障转移流程（伪代码）
public class ClusterFailover {
    public void execute() {
        // 1. 主节点A下线，其从节点发起选举
        Slave slave = findQualifiedSlave();

        // 2. 从节点向其他主节点请求投票
        int votes = requestVotes();

        // 3. 获得半数以上投票，升级为主节点
        if (votes > totalMasters / 2) {
            slave.promoteToMaster();
        }

        // 4. 接管原主节点的槽位
        takeOverSlots();

        // 5. 广播PONG消息，通知集群配置变更
        broadcastConfigUpdate();
    }
}
```

**选主条件**（优先级从高到低）：
1. **数据完整性**：复制偏移量最大的从节点（数据最新）
2. **runID最小**：保证确定性选举

---

### 6. 集群扩缩容

#### 6.1 扩容（添加节点）

```bash
# 1. 启动新节点（主+从）
redis-server /path/to/7003.conf
redis-server /path/to/7004.conf

# 2. 添加主节点到集群
redis-cli --cluster add-node 192.168.1.13:7003 192.168.1.10:7000

# 3. 迁移部分槽位到新节点
redis-cli --cluster reshard 192.168.1.10:7000 \
  --cluster-from <source_node_id> \
  --cluster-to <new_node_id> \
  --cluster-slots 2000  # 迁移2000个slot

# 4. 添加从节点
redis-cli --cluster add-node 192.168.1.13:7004 192.168.1.10:7000 \
  --cluster-slave --cluster-master-id <master_node_id>
```

---

#### 6.2 缩容（删除节点）

```bash
# 1. 迁移待删除节点的槽位到其他节点
redis-cli --cluster reshard 192.168.1.10:7000 \
  --cluster-from <node_to_remove_id> \
  --cluster-to <target_node_id> \
  --cluster-slots <all_slots>

# 2. 删除从节点
redis-cli --cluster del-node 192.168.1.13:7004 <node_id>

# 3. 删除主节点（确保槽位已全部迁移）
redis-cli --cluster del-node 192.168.1.13:7003 <node_id>
```

---

### 7. 集群限制与注意事项

#### 7.1 多键操作限制

**问题**：集群模式下，多键操作（如MGET、MSET）要求所有key在同一slot

**解决方案**：
```java
// 使用HashTag保证key在同一slot
jedis.mget("{user:1001}:name", "{user:1001}:age");

// 或使用Pipeline批量操作（允许跨slot）
Pipeline pipeline = jedis.pipelined();
pipeline.get("key1");
pipeline.get("key2");
pipeline.sync();
```

---

#### 7.2 事务与Lua脚本限制

- **事务（MULTI/EXEC）**：所有key必须在同一slot
- **Lua脚本**：所有操作的key必须在同一slot
- **解决方案**：使用HashTag或设计时避免跨slot操作

---

#### 7.3 性能考量

**优势**：
- 线性扩展：增加节点提升整体吞吐量
- 无代理层：减少网络开销

**劣势**：
- **网络通信开销**：Gossip协议定期交换信息
- **数据倾斜**：热点slot导致某些节点负载高（可通过调整slot分配缓解）

---

### 8. 面试答题总结

**标准回答模板**：

> Redis Cluster是官方分布式方案，通过 **槽位（Slot）分片** 实现水平扩展：
> 1. **数据分片**：16384个槽位，key通过 `CRC16(key) % 16384` 映射到槽位，每个主节点负责一部分槽位
> 2. **去中心化**：节点通过Gossip协议交换状态，客户端直连数据节点（无需Proxy）
> 3. **故障转移**：主节点下线时，从节点自动发起选举并接管槽位
> 4. **在线扩容**：通过 `redis-cli --cluster reshard` 迁移槽位，无需停机
>
> **核心优势**：
> - 官方支持，无需第三方组件
> - 自动分片和故障转移
> - 可线性扩展到1000+节点
>
> **注意事项**：
> - 多键操作需使用HashTag（如 `{user:1001}:field`）
> - 最少6个节点（3主3从）

**常见追问**：
- **为什么是16384个槽位而不是更多？** → CRC16输出16位，16384是2^14，压缩心跳包大小（槽位位图2KB），且足够满足大规模集群
- **集群模式和哨兵模式的区别？** → 哨兵解决高可用（单主），集群解决扩展性（多主分片）
- **如何解决数据倾斜？** → 调整槽位分配、使用HashTag分散热点key、增加节点
