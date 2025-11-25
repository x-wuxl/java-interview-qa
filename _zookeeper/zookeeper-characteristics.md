---
title: 你对 ZooKeeper 的特性有哪些了解？
category: [Java后端, 分布式, 中间件, ZooKeeper]
tags: [ZooKeeper, 特性, CAP理论, 面试题]
description: 总结 ZooKeeper 的核心特性，包括顺序一致性、原子性、单一系统映像、可靠性等。
nav_order: 583
parent: ZooKeeper
---
## 1. 核心特性概览

ZooKeeper 的设计目标是提供高性能、高可用的分布式协调服务，其核心特性可以概括为以下几点：

### 1.1 顺序一致性 (Sequential Consistency)
这是 ZK 最重要的特性。来自同一个客户端的更新请求，会严格按照其发送顺序被应用到 ZooKeeper 中。
*   *原理*：每个写请求都会被分配一个全局唯一的、单调递增的事务 ID (**Zxid**)。

### 1.2 原子性 (Atomicity)
更新操作要么成功，要么失败，没有中间状态。
*   *原理*：基于 ZAB 协议，Leader 只有在收到过半 Follower 的 ACK 后才会提交事务。

### 1.3 单一系统映像 (Single System Image)
无论客户端连接到集群中的哪个服务器（Leader 或 Follower），它看到的服务端数据模型都是一致的。
*   *注意*：严格来说，由于同步延迟，Follower 的数据可能会滞后于 Leader，但 ZK 保证客户端在同一个 Session 中看到的数据视图不会回退（Client-side FIFO Order）。

### 1.4 可靠性 (Reliability)
一旦一次更新被应用，它就会被持久化，直到下一次更新覆盖它。

### 1.5 实时性 (Timeliness)
ZooKeeper 保证在一定时间范围内，客户端能读到最新的数据。
*   *注意*：ZK 保证的是**最终一致性**，而不是强一致性（Linearizability）。如果需要读取绝对最新的数据，客户端在读取前可以调用 `sync()` 方法。

## 2. CAP 理论中的定位

在 CAP 理论中，ZooKeeper 保证的是 **CP**（Consistency & Partition Tolerance）。
*   **C (一致性)**：ZK 保证数据的一致性（通过 ZAB 协议）。
*   **P (分区容错性)**：ZK 能够容忍网络分区。
*   **A (可用性)**：在 Leader 选举期间，集群对外不可用（无法处理写请求），因此牺牲了部分可用性。

## 3. 总结

> **面试官**：你对 ZooKeeper 的特性有哪些了解？
>
> **候选人**：
> ZooKeeper 的核心特性主要包括：
> 1.  **顺序一致性**：这是最重要的，所有写操作都通过全局唯一的 Zxid 排序，保证了操作顺序。
> 2.  **原子性**：所有事务请求要么全成功，要么全失败。
> 3.  **单一视图**：客户端连接任意节点，看到的数据模型是一致的。
> 4.  **高可用**：只要半数以上节点存活，集群就能正常工作。
>
> 从 CAP 角度来看，ZooKeeper 是一个 **CP 系统**。它优先保证一致性和分区容错性，在 Leader 选举期间会短暂牺牲可用性。
