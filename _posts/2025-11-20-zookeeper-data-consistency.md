---
layout: post
title: ZooKeeper 如何保证主从节点数据一致性？
category: [Java后端, 分布式, 中间件, ZooKeeper]
tags: [ZooKeeper, 数据一致性, ZAB协议, 两阶段提交]
description: 详解 Leader 与 Follower 之间的数据同步机制，包括 Diff 同步、Trunc 同步和 Snap 同步。
---

## 1. 核心机制：ZAB 协议的原子广播

ZooKeeper 保证主从节点数据一致性的核心在于 **ZAB 协议（ZooKeeper Atomic Broadcast）**。
当 Leader 接收到写请求时，它会将该请求封装成一个 **Proposal（提案）**，并广播给所有 Follower。

### 1.1 两阶段提交 (2PC)
1.  **Propose 阶段**：Leader 将 Proposal 发送给所有 Follower。Follower 接收到后，写入本地事务日志，并返回 ACK。
2.  **Commit 阶段**：当 Leader 收到**过半** Follower 的 ACK 后，认为该事务可以提交。Leader 向所有 Follower 发送 Commit 消息，Follower 收到后正式应用该事务到内存数据树中。

## 2. 异常场景下的数据同步 (Recovery Mode)

当新 Leader 选举产生，或者某个 Follower 断线重连时，需要进行**数据同步**，以保证与 Leader 的一致性。同步策略主要有三种：

### 2.1 DIFF 同步 (差异同步)
*   **场景**：Follower 的数据滞后于 Leader，但滞后不多（在 Leader 的内存缓存队列中能找到）。
*   **机制**：Leader 将 Follower 缺失的 Proposal 发送给它，Follower 补齐数据。

### 2.2 TRUNC 同步 (回滚同步)
*   **场景**：Follower 的数据比 Leader 还“新”（通常是因为旧 Leader 刚发出 Proposal 就挂了，未提交，但该 Follower 记录了）。
*   **机制**：Leader 要求 Follower 回滚到某个特定的 Zxid，丢弃未提交的脏数据。

### 2.3 SNAP 同步 (全量同步)
*   **场景**：Follower 滞后太多，或者 Leader 的缓存队列已满，无法进行增量同步。
*   **机制**：Leader 将整个内存数据树生成快照（Snapshot），全量发送给 Follower。

## 3. 总结

> **面试官**：ZooKeeper 如何保证主从节点数据一致性？
>
> **候选人**：
> ZooKeeper 通过 **ZAB 协议** 来保证一致性。
>
> 正常运行时，采用**两阶段提交**：Leader 将写请求转化为 Proposal 广播给 Follower，收到过半 ACK 后再广播 Commit，从而保证集群数据一致。
>
> 在异常恢复（如节点重连）时，ZK 会根据 Follower 的 Zxid 与 Leader 的差异，自动选择同步策略：
> 1.  **DIFF 同步**：增量补齐缺失的数据。
> 2.  **TRUNC 同步**：回滚未提交的脏数据。
> 3.  **SNAP 同步**：全量发送快照。
>
> 这种机制保证了无论是正常写入还是故障恢复，集群最终都能达到一致状态。
