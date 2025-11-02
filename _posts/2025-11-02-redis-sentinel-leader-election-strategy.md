---
layout: post
title: "Redis哨兵模式选主策略详解"
date: 2025-11-02
description: "深入解析Redis哨兵模式的选主策略，包括从节点优先级、复制偏移量、runID的比较规则，以及优先级的动态调整方法"
author: "wuxl"
categories: [中间件]
tags: [Redis, 哨兵模式, 选主策略, 故障转移, 优先级配置]
---

## 问题

Redis哨兵模式选主策略是什么？优先级是否可变？

## 答案

### 1. 核心概念

**选主（Leader Election）**是哨兵模式在主节点故障时，从多个从节点中选出新主节点的过程。选主策略直接影响故障转移后的服务质量和数据完整性。

**两层选举**：
1. **选举领头哨兵（Sentinel Leader）**：决定由哪个哨兵执行故障转移
2. **选择新主节点（New Master）**：从从节点中挑选最合适的升级为主节点

---

### 2. 领头哨兵的选举（Sentinel Leader Election）

#### 2.1 选举触发条件

当哨兵检测到主节点 **客观下线（ODOWN）** 时，触发领头哨兵选举。

---

#### 2.2 选举算法（基于Raft）

```
时间线：
T1: 哨兵A首先检测到主节点主观下线（SDOWN）
T2: 哨兵A向其他哨兵发送 is-master-down-by-addr 命令询问
T3: 收到quorum个确认，判定客观下线（ODOWN）
T4: 哨兵A发起选举，向其他哨兵请求投票
T5: 各哨兵投票给最先请求的哨兵（先到先得）
T6: 获得超过半数投票的哨兵成为Leader
```

**选举规则**：
- 每个哨兵在一次选举周期内只能投票一次
- 先发起选举的哨兵优先获得投票（先到先得原则）
- 需要获得 **超过半数**（N/2 + 1）的投票才能成为Leader
- 选举超时后重新发起选举

**示例**（5个哨兵）：
```java
// 伪代码描述哨兵选举
public class SentinelElection {
    private int totalSentinels = 5;
    private int requiredVotes = totalSentinels / 2 + 1;  // 3票

    public Sentinel electLeader() {
        Map<Sentinel, Integer> votes = new HashMap<>();

        // 哨兵A首先发起选举
        for (Sentinel sentinel : allSentinels) {
            Sentinel vote = sentinel.requestVote();
            votes.put(vote, votes.getOrDefault(vote, 0) + 1);
        }

        // 获得3票以上的哨兵成为Leader
        for (Map.Entry<Sentinel, Integer> entry : votes.entrySet()) {
            if (entry.getValue() >= requiredVotes) {
                return entry.getKey();  // 返回Leader哨兵
            }
        }

        return null;  // 选举失败，重新发起
    }
}
```

---

### 3. 新主节点的选择策略（重点）

领头哨兵选出后，按以下 **三层过滤规则** 选择新主节点：

---

#### 3.1 第一优先级：从节点优先级（replica-priority）

**配置参数**：
```bash
# redis.conf 中配置（从节点）
replica-priority 100  # 默认值100，0表示永不晋升为主节点
```

**规则**：
- 优先级值**越小**，优先级**越高**
- 优先级为 `0` 的从节点永远不会被选为主节点
- 所有从节点中，选择优先级最高（数值最小）的

**示例**：
```
Slave1: replica-priority 10   # 最高优先级
Slave2: replica-priority 50
Slave3: replica-priority 100
Slave4: replica-priority 0    # 永不晋升

选举结果：Slave1 被选为新主节点
```

---

#### 3.2 第二优先级：复制偏移量（replication offset）

**作用**：当多个从节点的 `replica-priority` 相同时，比较复制偏移量。

**规则**：
- 选择复制偏移量**最大**的从节点（数据最新）
- 偏移量越大，说明从主节点同步的数据越多

**查看复制偏移量**：
```bash
redis-cli INFO replication

# 输出示例：
role:slave
master_repl_offset:12345678  # 从节点当前偏移量
```

**示例**：
```
Slave1: priority=100, offset=12345678
Slave2: priority=100, offset=12340000
Slave3: priority=100, offset=12345500

选举结果：Slave1（偏移量最大，数据最新）
```

---

#### 3.3 第三优先级：runID字典序

**作用**：当优先级和偏移量都相同时，按 `runID` 的字典序排序。

**规则**：
- 选择 `runID` 字典序**最小**的从节点
- 保证选举的确定性（避免随机性）

**runID获取**：
```bash
redis-cli INFO server | grep run_id

# 输出示例：
run_id:a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
```

**示例**：
```
Slave1: priority=100, offset=12345678, runID=a1b2c3...
Slave2: priority=100, offset=12345678, runID=z9y8x7...

选举结果：Slave1（runID字典序更小）
```

---

### 4. 完整选主流程

```java
/**
 * 完整的从节点选主算法
 */
public class MasterElection {
    public Slave selectNewMaster(List<Slave> slaves) {
        // 1. 过滤掉主观下线的从节点
        slaves = slaves.stream()
            .filter(s -> !s.isSubjectivelyDown())
            .collect(Collectors.toList());

        // 2. 过滤掉优先级为0的从节点
        slaves = slaves.stream()
            .filter(s -> s.getReplicaPriority() > 0)
            .collect(Collectors.toList());

        // 3. 过滤掉与主节点断开连接超过10倍down-after-milliseconds的从节点
        slaves = slaves.stream()
            .filter(s -> s.getDisconnectTime() < 10 * downAfterMilliseconds)
            .collect(Collectors.toList());

        // 4. 按优先级、偏移量、runID排序
        slaves.sort((s1, s2) -> {
            // 4.1 比较优先级（值越小越优先）
            if (s1.getReplicaPriority() != s2.getReplicaPriority()) {
                return Integer.compare(s1.getReplicaPriority(), s2.getReplicaPriority());
            }

            // 4.2 比较复制偏移量（值越大越优先）
            if (s1.getReplOffset() != s2.getReplOffset()) {
                return Long.compare(s2.getReplOffset(), s1.getReplOffset());
            }

            // 4.3 比较runID（字典序越小越优先）
            return s1.getRunId().compareTo(s2.getRunId());
        });

        // 5. 返回排序后的第一个从节点
        return slaves.isEmpty() ? null : slaves.get(0);
    }
}
```

---

### 5. 优先级是否可变？（重点）

**答案：可以动态调整**

#### 5.1 修改方式

**方式1：修改配置文件（需重启）**
```bash
# redis.conf
replica-priority 50

# 重启Redis
redis-server /path/to/redis.conf
```

**方式2：动态修改（无需重启，推荐）**
```bash
# 通过CONFIG SET命令
redis-cli CONFIG SET replica-priority 50

# 持久化配置到文件
redis-cli CONFIG REWRITE
```

**方式3：通过Jedis客户端**
```java
Jedis jedis = new Jedis("192.168.1.10", 6379);
jedis.configSet("replica-priority", "50");
jedis.configRewrite();  // 写入配置文件
```

---

#### 5.2 动态调整场景

**场景1：机房优先级调整**
```bash
# 同机房的从节点设置更高优先级（值更小）
redis-cli -h 192.168.1.11 CONFIG SET replica-priority 10  # 本地机房
redis-cli -h 192.168.2.11 CONFIG SET replica-priority 100 # 异地机房
```

**场景2：硬件升级后提升优先级**
```bash
# 升级SSD、增加内存后，调高优先级
redis-cli CONFIG SET replica-priority 5
```

**场景3：临时下线维护**
```bash
# 维护前设置优先级为0，避免被选为主节点
redis-cli CONFIG SET replica-priority 0

# 维护完成后恢复
redis-cli CONFIG SET replica-priority 100
```

---

#### 5.3 查看当前优先级

```bash
# 方式1：CONFIG GET
redis-cli CONFIG GET replica-priority

# 方式2：INFO replication
redis-cli INFO replication | grep slave_priority
```

---

### 6. 实战建议

#### 6.1 优先级配置最佳实践

```bash
# 生产环境推荐配置
主节点所在机房的从节点:  replica-priority 10
备用机房的从节点:       replica-priority 50
灾备机房的从节点:       replica-priority 100
只读备份节点:          replica-priority 0
```

#### 6.2 注意事项

1. **避免所有从节点优先级相同**
   - 导致选主完全依赖复制偏移量，可能选中性能较差的节点

2. **合理设置优先级为0**
   - 用于只读备份、数据分析等不希望参与主节点选举的场景

3. **监控复制偏移量**
   - 即使优先级高，若复制延迟严重（偏移量小），也可能丢失数据

4. **配合min-replicas保证数据安全**
   ```bash
   # 至少有1个从节点复制成功才允许写入
   min-replicas-to-write 1
   min-replicas-max-lag 10
   ```

---

### 7. 面试答题总结

**标准回答模板**：

> Redis哨兵选主分为两步：
> 1. **选举领头哨兵**：基于Raft算法，先发起选举的哨兵获得投票，超过半数投票成为Leader
> 2. **选择新主节点**：按以下三层规则过滤：
>    - **优先级**：`replica-priority` 值越小优先级越高（0表示永不晋升）
>    - **复制偏移量**：优先级相同时，选择偏移量最大的（数据最新）
>    - **runID**：前两者都相同时，选择runID字典序最小的
>
> **优先级可动态调整**：
> - 通过 `CONFIG SET replica-priority <value>` 实时修改
> - 用于机房优先级、硬件升级、临时维护等场景
>
> **工程实践**：
> - 本地机房从节点设置高优先级（如10）
> - 异地机房设置低优先级（如100）
> - 只读备份节点设置为0

**常见追问**：
- **为什么优先级值越小越优先？** → 遵循Unix惯例（如nice值），0表示特殊含义（不参与选举）
- **如何保证选出的新主节点数据最新？** → 通过复制偏移量比较，偏移量大的数据更新
- **领头哨兵选举和新主节点选举的区别？** → 前者是哨兵之间选举（Raft），后者是从节点之间比较（优先级规则）
