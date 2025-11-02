---
layout: post
title: "Redis如何实现高可用"
date: 2025-11-02
description: "全面解析Redis高可用方案，包括主从复制、哨兵模式、集群模式的对比与选型，以及持久化、客户端重连等保障措施"
author: "wuxl"
categories: [中间件]
tags: [Redis, 高可用, 主从复制, 哨兵模式, 集群模式]
---

## 问题

Redis如何实现高可用？

## 答案

### 1. 核心概念

**高可用（High Availability, HA）**指系统在面临硬件故障、网络异常等问题时，仍能持续提供服务的能力。Redis通过多种技术手段实现高可用：

**核心目标**：
- **故障恢复**：主节点宕机后自动切换到从节点
- **数据冗余**：多副本存储防止数据丢失
- **持续服务**：最小化服务中断时间（RTO - Recovery Time Objective）
- **数据完整性**：最小化数据丢失（RPO - Recovery Point Objective）

---

### 2. Redis高可用方案对比

| 方案 | 适用场景 | 高可用能力 | 扩展性 | 复杂度 |
|------|---------|----------|--------|--------|
| **主从复制** | 读多写少，手动故障转移 | ❌ 无自动故障转移 | ❌ 单机容量限制 | ⭐ 简单 |
| **哨兵模式** | 中小规模，需自动故障转移 | ✅ 自动故障转移 | ❌ 单主写入瓶颈 | ⭐⭐ 中等 |
| **集群模式** | 大规模数据，需水平扩展 | ✅ 自动故障转移 + 分片 | ✅ 线性扩展 | ⭐⭐⭐ 复杂 |

---

### 3. 三种高可用方案详解

#### 3.1 主从复制（基础高可用）

**架构**：
```
[Master] --异步复制--> [Slave1]
                  \--> [Slave2]
```

**实现方式**：
```bash
# 从节点配置
replicaof 192.168.1.100 6379
replica-read-only yes  # 从节点只读
```

**优势**：
- 实现简单，配置方便
- 支持读写分离，提升读并发能力

**局限**：
- ❌ 主节点故障需要**手动**提升从节点
- ❌ 主节点写入性能受限于单机
- ❌ 数据同步是异步的，可能丢失部分数据

**适用场景**：开发测试环境、对可用性要求不高的场景

---

#### 3.2 哨兵模式（自动故障转移）

**架构**：
```
    [Sentinel1] [Sentinel2] [Sentinel3]  (哨兵集群)
           |         |         |
        监控 + 故障转移 + 配置提供
           |         |         |
      [Master] --复制--> [Slave1] [Slave2]
```

**核心能力**：
1. **监控**：持续检测主从节点健康状态
2. **故障检测**：半数以上哨兵认为主节点下线后触发故障转移
3. **自动切换**：选举新主节点，通知客户端更新连接

**配置示例**：
```bash
# sentinel.conf
sentinel monitor mymaster 192.168.1.100 6379 2  # quorum=2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000
sentinel parallel-syncs mymaster 1
```

**Java客户端集成**：
```java
Set<String> sentinels = new HashSet<>();
sentinels.add("192.168.1.10:26379");
sentinels.add("192.168.1.11:26379");
sentinels.add("192.168.1.12:26379");

JedisSentinelPool pool = new JedisSentinelPool(
    "mymaster", sentinels, poolConfig, "password"
);

try (Jedis jedis = pool.getResource()) {
    jedis.set("key", "value");
}
```

**优势**：
- ✅ 自动故障转移，RTO通常<1分钟
- ✅ 客户端自动感知主节点切换
- ✅ 配置简单，运维成本低

**局限**：
- ❌ 仍是单主架构，写入性能受限
- ❌ 无法水平扩展存储容量

**适用场景**：数据量<10GB，QPS<10W，对可用性要求高的生产环境

---

#### 3.3 集群模式（水平扩展 + 高可用）

**架构**：
```
  [Master1] --复制--> [Slave1]  (slot 0-5460)
  [Master2] --复制--> [Slave2]  (slot 5461-10922)
  [Master3] --复制--> [Slave3]  (slot 10923-16383)
       \       |       /
        \      |      /
      Gossip协议通信（集群总线）
```

**核心特性**：
1. **数据分片**：16384个槽位分散到多个主节点
2. **去中心化**：无需Proxy，客户端智能路由
3. **故障转移**：主节点下线时从节点自动接管

**创建集群**：
```bash
redis-cli --cluster create \
  192.168.1.10:7000 192.168.1.11:7000 192.168.1.12:7000 \
  192.168.1.10:7001 192.168.1.11:7001 192.168.1.12:7001 \
  --cluster-replicas 1
```

**Java客户端集成**：
```java
Set<HostAndPort> nodes = new HashSet<>();
nodes.add(new HostAndPort("192.168.1.10", 7000));
nodes.add(new HostAndPort("192.168.1.11", 7000));
nodes.add(new HostAndPort("192.168.1.12", 7000));

JedisCluster cluster = new JedisCluster(nodes, poolConfig);
cluster.set("key", "value");  // 自动路由到正确节点
```

**优势**：
- ✅ 线性扩展：增加节点提升容量和吞吐量
- ✅ 自动故障转移
- ✅ 官方支持，无需第三方组件

**局限**：
- ❌ 运维复杂度高（槽位迁移、数据倾斜）
- ❌ 多键操作受限（需使用HashTag）
- ❌ 事务和Lua脚本要求key在同一slot

**适用场景**：数据量>10GB，需水平扩展的大规模生产环境

---

### 4. 高可用保障措施

#### 4.1 持久化保障数据安全

**RDB持久化**：
```bash
# 自动触发快照
save 900 1      # 900秒内至少1个key变化
save 300 10     # 300秒内至少10个key变化
save 60 10000   # 60秒内至少10000个key变化
```

**AOF持久化**：
```bash
# 开启AOF
appendonly yes
appendfsync everysec  # 每秒同步一次（折中方案）

# AOF重写
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

**混合持久化（推荐）**：
```bash
# Redis 4.0+
aof-use-rdb-preamble yes  # AOF文件以RDB格式开头，后接增量命令
```

---

#### 4.2 客户端高可用策略

**连接池配置**：
```java
JedisPoolConfig config = new JedisPoolConfig();
config.setMaxTotal(200);           // 最大连接数
config.setMaxIdle(50);             // 最大空闲连接
config.setMinIdle(10);             // 最小空闲连接
config.setTestOnBorrow(true);      // 获取连接时测试可用性
config.setTestWhileIdle(true);     // 空闲时定期检测
config.setTimeBetweenEvictionRunsMillis(30000);  // 检测周期30秒
```

**超时与重试**：
```java
// 设置合理的超时时间
JedisPoolConfig config = new JedisPoolConfig();
config.setMaxWaitMillis(3000);  // 获取连接超时3秒

// 使用Spring Redis的重试机制
RedisTemplate<String, Object> template = new RedisTemplate<>();
template.setConnectionFactory(connectionFactory);

// 捕获异常并降级
try {
    return redisTemplate.opsForValue().get(key);
} catch (RedisConnectionFailureException e) {
    log.error("Redis连接失败，降级到数据库查询", e);
    return queryFromDB(key);
}
```

---

#### 4.3 监控与告警

**关键监控指标**：
```bash
# 内存使用率
INFO memory | grep used_memory_human

# 主从延迟
INFO replication | grep master_repl_offset

# 连接数
INFO clients | grep connected_clients

# 命中率
INFO stats | grep keyspace_hits
```

**告警规则**：
- 内存使用率 > 80%
- 主从复制延迟 > 10秒
- 连接数 > 最大连接数的80%
- 命中率 < 90%

---

### 5. 高可用方案选型指南

#### 5.1 决策流程图

```
数据量 < 10GB 且 QPS < 10W?
    ├─ 是 → 是否需要自动故障转移?
    │        ├─ 是 → 哨兵模式 ✅
    │        └─ 否 → 主从复制（手动切换）
    │
    └─ 否 → 集群模式 ✅
```

#### 5.2 实际案例参考

**案例1：电商网站商品缓存**
- 数据量：5GB
- QPS：5W
- 方案：**哨兵模式**（3主节点 + 3哨兵）

**案例2：社交平台用户关系**
- 数据量：50GB
- QPS：100W
- 方案：**集群模式**（10主10从）

**案例3：秒杀库存扣减**
- 数据量：<1GB
- QPS：峰值10W
- 方案：**哨兵模式 + Lua脚本**保证原子性

---

### 6. 面试答题总结

**标准回答模板**：

> Redis高可用主要通过三种方案实现：
> 1. **主从复制**：基础方案，实现数据冗余和读写分离，但需手动故障转移
> 2. **哨兵模式**：在主从复制基础上增加哨兵集群，实现自动故障转移，适合中小规模应用
> 3. **集群模式**：通过数据分片实现水平扩展，内置故障转移，适合大规模分布式场景
>
> **选型依据**：
> - 数据量<10GB且需自动切换 → 哨兵模式
> - 数据量>10GB或需水平扩展 → 集群模式
>
> **配套措施**：
> - 持久化：AOF+RDB混合模式，平衡性能和数据安全
> - 客户端：连接池 + 超时重试 + 异常降级
> - 监控：内存、延迟、连接数、命中率等关键指标

**常见追问**：
- **哨兵模式和集群模式如何选择？** → 根据数据量和扩展需求：<10GB选哨兵，>10GB选集群
- **如何保证主从切换时数据不丢失？** → 配置 `min-replicas-to-write` 和 `min-replicas-max-lag`，保证至少有N个从节点同步成功才允许写入
- **Redis高可用的RTO和RPO是多少？** → 哨兵模式RTO约30秒，RPO几秒（异步复制）；集群模式类似
