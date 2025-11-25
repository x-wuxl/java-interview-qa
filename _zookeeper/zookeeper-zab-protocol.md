---
title: ZooKeeper 如何保证一致性？ZAB 协议的原理是什么？ZooKeeper 属于强一致性吗？
category: [Java后端, 分布式, 中间件, ZooKeeper]
tags: [ZooKeeper, ZAB协议, 一致性, 面试题]
description: 深度解析 ZAB 协议的原子广播与崩溃恢复模式，并澄清 ZooKeeper 一致性级别的误区。
nav_order: 589
parent: ZooKeeper
---
## 1. ZAB 协议 (ZooKeeper Atomic Broadcast)

ZooKeeper 的一致性完全依赖于 **ZAB 协议**（ZooKeeper 原子广播协议）。它是为分布式协调服务专门设计的，支持**崩溃恢复**。

ZAB 协议主要有两种模式：

### 1.1 消息广播模式 (Message Broadcast)
*   **类似 2PC**：当集群正常运行时，进入广播模式。
*   **流程**：
    1.  Leader 接收写请求，生成 Proposal。
    2.  Leader 广播 Proposal 给 Follower。
    3.  Follower 写日志并返回 ACK。
    4.  Leader 收到过半 ACK，广播 Commit。
*   **特点**：它不是严格的 2PC，因为 Leader 不需要等待**所有** Follower 回复，只要**过半**即可。这提高了可用性，但也带来了数据差异的可能。

### 1.2 崩溃恢复模式 (Crash Recovery)
*   **触发时机**：当 Leader 宕机，或 Leader 失去了过半 Follower 的支持时。
*   **目标**：
    1.  选出新 Leader。
    2.  确保**已提交**的事务不丢失。
    3.  确保**未提交**（只在旧 Leader 上存在）的事务被丢弃。
*   **流程**：选举新 Leader -> 数据同步（Diff/Trunc/Snap） -> 恢复广播。

## 2. ZooKeeper 是强一致性吗？

这是一个常见的**面试陷阱**。

*   **官方定义**：ZooKeeper 保证的是 **顺序一致性 (Sequential Consistency)**。
*   **实际表现**：
    *   它**不是**严格的强一致性（Linearizability）。
    *   因为写操作虽然在 Leader 提交了，但同步到所有 Follower 需要时间。
    *   客户端 A 写入数据，客户端 B 连接到另一个 Follower，可能在短时间内读不到最新数据。
*   **如何实现强一致读？**
    *   客户端在读取数据前，先调用 `sync()` 方法。这会强制 Follower 跟 Leader 同步最新数据，从而达到强一致读的效果。

## 3. 总结

> **面试官**：ZooKeeper 如何保证一致性？ZAB 协议的原理是什么？
>
> **候选人**：
> ZooKeeper 通过 **ZAB 协议** 保证一致性。ZAB 协议核心分为两种模式：
> 1.  **消息广播模式**：类似两阶段提交，Leader 收到过半 ACK 即提交，保证了高性能。
> 2.  **崩溃恢复模式**：当 Leader 宕机时，通过选举和数据同步，保证数据不丢失且集群恢复一致。
>
> 关于一致性级别，严格来说 ZK 保证的是**顺序一致性**，而不是线性强一致性。因为 Follower 的数据同步存在延迟，客户端可能读到旧数据。如果业务要求必须读到最新数据，需要在读取前调用 `sync()` 方法。
