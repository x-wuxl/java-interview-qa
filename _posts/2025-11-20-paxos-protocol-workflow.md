---
layout: post
title: "Paxos 协议的工作流程是什么？"
date: 2025-11-20 15:24:28 +0800
categories: [分布式系统, 共识算法]
tags: [Paxos, 一致性, 分布式共识, 算法原理]
description: "详解 Paxos 协议的核心原理、两阶段提交流程、角色划分及在分布式系统中的应用实践"
---

## 一、核心概念

**Paxos** 是一种分布式共识算法，由 Leslie Lamport 于 1990 年提出，用于在分布式系统中解决多个节点对某个值达成一致的问题。它是分布式系统理论的基石，Chubby、Zookeeper 等系统都基于 Paxos 或其变种实现。

### 解决的核心问题

在存在节点故障、网络延迟、消息丢失的分布式环境中，如何保证多个节点最终对某个提案（Proposal）达成一致意见，且一旦达成共识就不可更改。

### 三种角色

1. **Proposer（提议者）**：提出提案（Proposal Number + Value）
2. **Acceptor（接受者）**：投票决定是否接受提案（通常是过半数集群）
3. **Learner（学习者）**：学习已被选定的提案值

> 注：实际系统中，同一个节点可以同时扮演多种角色。

---

## 二、Paxos 工作流程（Basic Paxos）

Paxos 协议分为 **两个阶段**：Prepare 阶段和 Accept 阶段。

### 阶段一：Prepare（准备阶段）

**目标**：探测当前已被接受的最大提案号，占位并获取投票权

1. **Proposer 行为**：
   - 生成全局唯一且递增的提案编号 `N`
   - 向多数 Acceptor 发送 `Prepare(N)` 请求

2. **Acceptor 行为**：
   - 收到 `Prepare(N)` 后，检查自己的状态：
     - 如果 `N` **大于** 自己承诺的所有提案号 `maxN`，则：
       - 承诺不再接受编号 **小于 N** 的提案
       - 返回 `Promise(N, acceptedN, acceptedValue)`
         - `acceptedN`：已接受的最大提案号
         - `acceptedValue`：对应的提案值
     - 如果 `N` **小于或等于** `maxN`，则拒绝并返回 `maxN`

**流程示意**：

```
Proposer                  Acceptor1  Acceptor2  Acceptor3
   |                          |          |          |
   |---Prepare(N=5)---------->|          |          |
   |                          |          |          |
   |---Prepare(N=5)---------------------->|          |
   |                          |          |          |
   |---Prepare(N=5)------------------------------------->|
   |                          |          |          |
   |<--Promise(5, null)-------|          |          |
   |<--Promise(5, 3, "A")---------------- |          |
   |<--Promise(5, 4, "B")-----------------------     |
```

---

### 阶段二：Accept（接受阶段）

**目标**：提交提案值，让多数 Acceptor 接受

1. **Proposer 行为**：
   - 如果收到多数 Acceptor 的 `Promise` 响应：
     - 若所有响应中 `acceptedValue` 都为空，则可以提交自己的值 `V`
     - 若存在 `acceptedValue`，则必须提交 `acceptedN` 最大的那个值（保证一致性）
   - 向多数 Acceptor 发送 `Accept(N, V)` 请求

2. **Acceptor 行为**：
   - 收到 `Accept(N, V)` 后：
     - 如果 `N >= maxN`（承诺的最小提案号）：
       - 接受该提案，更新 `acceptedN = N, acceptedValue = V`
       - 返回 `Accepted(N, V)`
     - 否则拒绝

3. **Learner 行为**：
   - 当 Learner 收到多数 Acceptor 的 `Accepted(N, V)` 后，确认值 `V` 已被选定

**流程示意**：

```
Proposer                  Acceptor1  Acceptor2  Acceptor3
   |                          |          |          |
   |---Accept(5, "B")-------->|          |          |
   |---Accept(5, "B")-------------------->|          |
   |---Accept(5, "B")------------------------------------->|
   |                          |          |          |
   |<--Accepted(5, "B")-------|          |          |
   |<--Accepted(5, "B")------------------ |          |
   |<--Accepted(5, "B")------------------------------     |
   |                          |          |          |
   (值 "B" 达成共识)
```

---

## 三、关键原理与保证

### 1. 提案编号的唯一性与递增性

- 提案号 `N` 通常使用 **时间戳 + Server ID** 组合生成，确保全局唯一且递增
- 示例：`N = timestamp * 1000 + serverId`

### 2. 多数派原则（Quorum）

- **过半数（Majority）** 是共识的关键：任意两个多数派集合必有交集
- 例如 5 个节点，至少需要 3 个节点同意
- 保证了新提案一定能看到已被接受的旧提案

### 3. 为什么要选择 acceptedN 最大的值？

**场景**：Prepare 阶段收到多个 Acceptor 返回的已接受提案

- 编号最大的提案最有可能已经被多数派接受
- 选择它可以避免破坏已达成的共识（**一致性保证**）

**示例**：

```
Acceptor1: Promise(10, acceptedN=5, acceptedValue="A")
Acceptor2: Promise(10, acceptedN=8, acceptedValue="B")
Acceptor3: Promise(10, null)

→ Proposer 必须选择 "B"（acceptedN=8 最大）
```

---

## 四、活锁问题与 Multi-Paxos 优化

### Basic Paxos 的活锁问题

**场景**：多个 Proposer 并发提案，互相覆盖对方的 Prepare 请求

```
时间线：
T1: Proposer1 发送 Prepare(N=5)
T2: Proposer2 发送 Prepare(N=6)  [覆盖 N=5]
T3: Proposer1 发现被拒绝，发送 Prepare(N=7)  [覆盖 N=6]
T4: Proposer2 发现被拒绝，发送 Prepare(N=8)  [覆盖 N=7]
... (无法达成共识)
```

**解决方案**：
- **随机退避**：提案失败后随机等待一段时间再重试
- **Leader 选举**：引入 Multi-Paxos，选举唯一 Leader 负责提案

---

### Multi-Paxos（生产环境常用）

**核心改进**：

1. **选举 Leader**：只有 Leader 可以提议，避免冲突
2. **省略 Prepare 阶段**：Leader 稳定后，后续提案直接进入 Accept 阶段
3. **连续决策**：将多个值的共识变为日志序列的共识（如 Zookeeper 的 ZAB 协议）

**简化流程**：

```
Leader 当选后：
1. 初始时执行一次完整 Paxos（确立 Leader 身份）
2. 后续提案直接发送 Accept(N, V) 给 Acceptors
3. Acceptors 无需再执行 Prepare 判断，直接接受
```

---

## 五、应用场景

### 1. Zookeeper（ZAB 协议）

- ZAB（Zookeeper Atomic Broadcast）是 Paxos 的工程化实现
- 保证事务请求的全局顺序一致性

### 2. Chubby（Google 分布式锁服务）

- 使用 Paxos 选举 Master 节点
- 提供分布式锁和配置中心功能

### 3. 分布式数据库

- **TiDB**：使用 Raft（Paxos 的简化版）实现多副本一致性
- **CockroachDB**：基于 Raft 的分布式事务

---

## 六、答题总结

**Paxos 协议** 通过 **两阶段提交** 解决分布式共识问题：

1. **Prepare 阶段**：
   - Proposer 发送编号 `N`，Acceptor 承诺不接受更小的编号
   - 返回已接受的最大提案（若有）

2. **Accept 阶段**：
   - Proposer 提交值（必须选择 acceptedN 最大的值）
   - Acceptor 接受并通知 Learner

**关键要点**：

- **多数派原则**保证任意两次投票必有交集
- **提案号递增**避免旧提案覆盖新共识
- **活锁问题**通过 Multi-Paxos 或 Leader 选举解决

**面试加分项**：

- 对比 Raft 算法（Raft 更易理解，工程实现更友好）
- 说明 Zookeeper 的 ZAB 与 Paxos 的关系
- 提到 Paxos Made Simple 论文的经典地位

**口述建议**：先讲两阶段流程，再解释多数派和提案号作用，最后补充 Multi-Paxos 优化，逻辑清晰更易理解。
