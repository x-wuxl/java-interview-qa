---
layout: default
title: "讲一下 ZooKeeper 的选举机制。"
parent: ZooKeeper
nav_order: 587
description: 深入解析 ZooKeeper 的 Leader 选举流程，包括服务器启动时的选举和运行期间 Leader 宕机后的选举。
---
## 1. 核心概念

Leader 选举是 ZooKeeper 最核心的能力之一。它保证了在集群启动或 Leader 宕机时，能够快速选出一个新的 Leader 来主持工作。
ZK 默认采用 **FastLeaderElection** 算法。

## 2. 选举票据 (Vote)

在选举过程中，每个服务器都会广播自己的选票 `(myid, zxid)`：
*   **myid**：服务器的唯一 ID（配置在 `zoo.cfg` 中）。
*   **zxid**：该服务器上最大的事务 ID（代表数据越新）。

**胜出规则**：优先比较 **zxid**（数据越新越好），如果 zxid 相同，则比较 **myid**（ID 越大越好）。

## 3. 选举流程

### 3.1 服务器启动时的选举
假设有 3 台机器 (Server 1, 2, 3)：
1.  **Server 1 启动**：投自己一票 `(1, 0)`。此时只有 1 票，不足半数，进入 LOOKING 状态。
2.  **Server 2 启动**：投自己一票 `(2, 0)`。Server 1 发现 Server 2 的 myid 更大，于是改投 Server 2。此时 Server 2 获得 2 票（过半），**当选 Leader**。
3.  **Server 3 启动**：发现已有 Leader，直接以 Follower 身份加入。

### 3.2 运行期间 Leader 宕机后的选举
假设 Server 2 (Leader) 宕机：
1.  **状态变更**：Server 1 和 3 发现连接不上 Leader，将状态切换为 **LOOKING**。
2.  **发起投票**：
    *   Server 1 投自己 `(1, 100)`。
    *   Server 3 投自己 `(3, 99)`（假设 Server 3 数据稍微旧一点）。
3.  **PK 选票**：
    *   Server 3 收到 Server 1 的票，发现 Server 1 的 **zxid (100) > 自己的 (99)**。
    *   Server 3 认可 Server 1 更适合做 Leader，改投 Server 1。
4.  **统计结果**：Server 1 获得 2 票（过半），**当选新 Leader**。Server 3 成为 Follower。

## 4. 总结

> **面试官**：讲一下 ZooKeeper 的选举机制。
>
> **候选人**：
> ZooKeeper 的选举机制主要依赖 **FastLeaderElection** 算法。
>
> 核心思想是：**优先选数据最新的节点（Zxid 最大），如果数据一样新，选服务器 ID 最大的节点。**
>
> 选举流程分为两类：
> 1.  **启动时选举**：节点启动后互相交换选票，只要某节点获得过半选票，即当选 Leader。通常是启动顺序靠后的节点更有优势（因为 ID 大），直到满足过半条件。
> 2.  **运行时选举**：当 Leader 宕机，剩余节点进入 LOOKING 状态。它们会再次交换选票，通过比较 `(zxid, myid)` 选出拥有最新数据的节点作为新 Leader。
>
> 这种机制保证了新 Leader 一定拥有之前所有已提交的事务，从而保证数据不丢失。
