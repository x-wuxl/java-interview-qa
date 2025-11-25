---
title: ZooKeeper 的服务器有几种角色？Server 有哪些工作状态？
category: [Java后端, 分布式, 中间件, ZooKeeper]
tags: [ZooKeeper, 集群角色, 服务器状态, 面试题]
description: 详解 ZooKeeper 集群中的 Leader、Follower、Observer 角色及其职责，以及 Looking, Leading, Following 等工作状态。
nav_order: 585
parent: ZooKeeper
---
## 1. 服务器角色 (Roles)

ZooKeeper 集群中的服务器主要有三种角色：

### 1.1 Leader (领导者)
*   **核心职责**：**事务请求的唯一处理者**。
*   **功能**：
    *   处理所有的**事务请求**（写请求），并发起投票。
    *   协调集群内所有节点的数据同步。
    *   处理读请求。

### 1.2 Follower (跟随者)
*   **核心职责**：**参与投票**，处理读请求。
*   **功能**：
    *   处理**非事务请求**（读请求），如果收到写请求，会转发给 Leader。
    *   **参与 Proposal 投票**：参与 ZAB 协议的事务提交投票。
    *   **参与 Leader 选举投票**：当 Leader 挂掉时，有资格竞选新 Leader。

### 1.3 Observer (观察者)
*   **核心职责**：**只提供读服务，不参与投票**。
*   **功能**：
    *   处理读请求，转发写请求给 Leader。
    *   **不参与**任何投票（既不参与事务提交，也不参与选举）。
*   **存在意义**：**扩展系统读性能**。增加 Follower 会导致投票节点增多，从而拖慢写性能（因为需要更多 ACK）。Observer 可以在不影响写性能的前提下，线性扩展读性能。

## 2. 服务器工作状态 (States)

服务器在运行过程中，会在以下几种状态间切换：

1.  **LOOKING (寻找状态)**
    *   服务器处于**寻找 Leader** 的状态。
    *   通常发生在服务器刚启动，或者 Leader 宕机后进行新一轮选举时。

2.  **LEADING (领导状态)**
    *   当前节点是 **Leader**。
    *   负责广播事务、同步数据。

3.  **FOLLOWING (跟随状态)**
    *   当前节点是 **Follower**，且已经和 Leader 建立同步。

4.  **OBSERVING (观察状态)**
    *   当前节点是 **Observer**，且已经和 Leader 建立同步。

## 3. 总结

> **面试官**：ZooKeeper 的服务器有几种角色？Server 有哪些工作状态？
>
> **候选人**：
> ZooKeeper 集群主要有三种角色：
> 1.  **Leader**：核心主节点，负责处理所有写请求，协调数据同步。
> 2.  **Follower**：从节点，处理读请求，**参与选举和事务投票**。
> 3.  **Observer**：观察者，只处理读请求，**不参与任何投票**。它的作用是扩展读性能而不降低写性能。
>
> 对应的，服务器有四种工作状态：
> 1.  **LOOKING**：正在选举 Leader。
> 2.  **LEADING**：我是 Leader。
> 3.  **FOLLOWING**：我是 Follower，正在跟随 Leader。
> 4.  **OBSERVING**：我是 Observer，正在观察 Leader。
