---
title: "谈谈你对 Pulsar 的理解。"
categories: [MessageQueue, Pulsar]
tags: [Pulsar, CloudNative, Architecture]
description: "深入解析下一代云原生消息队列 Pulsar 的核心特性：存算分离、分层存储、多租户与 Geo-Replication。"
nav_order: 540
parent: 消息队列
---
### 1. 核心概念
**Apache Pulsar** 是下一代云原生分布式消息流平台。与 Kafka 相比，它最大的特点是**“存算分离”**（Separation of Compute and Storage）架构。

Pulsar 解决了 Kafka 在扩容、运维和多租户方面的痛点，被誉为“云原生时代的 Kafka”。

### 2. 原理与架构
Pulsar 的架构分为三层：

#### 2.1 Broker 层（计算层 - 无状态）
*   **职责**：负责处理 Producer 的写入和 Consumer 的读取，**但不存储数据**。
*   **优势**：Broker 是无状态的，扩容非常容易。增加 Broker 节点后，流量会自动负载均衡，无需像 Kafka 那样进行繁重的数据 Rebalance（迁移）。

#### 2.2 BookKeeper 层（存储层 - 有状态）
*   **职责**：由一组 Bookie 节点组成，负责持久化存储消息。
*   **核心机制**：
    *   **Segment（分片）**：Pulsar 将 Topic 的数据切分为很多个小的 Segment。
    *   **Striping（条带化）**：这些 Segment 均匀地分散存储在所有的 Bookie 节点上。
*   **优势**：
    *   **独立扩容**：存储不够加 Bookie，计算不够加 Broker，互不干扰。
    *   **高吞吐**：写入时并发写向多个 Bookie，IO 能力随节点数线性增长。

#### 2.3 ZooKeeper 层（元数据层）
*   存储集群配置、Topic 归属、Ledger 索引等元数据。

### 3. 关键特性与场景
1.  **多租户（Multi-tenancy）**：原生支持 `Tenant` 和 `Namespace` 级别的资源隔离和配额管理，非常适合 PaaS 平台。
2.  **分层存储（Tiered Storage）**：支持将冷数据自动卸载到廉价的对象存储（如 S3, HDFS）中，实现无限保留时长的“无限流”存储。
3.  **跨地域复制（Geo-Replication）**：原生支持跨机房、跨地域的数据同步，配置简单，适合全球化业务。
4.  **Pulsar Functions**：内置轻量级 Serverless 计算框架，可在消息流上直接运行简单的 ETL 逻辑。

### 4. 示例与总结
**回答总结：**
“我对 Pulsar 的理解可以用‘**下一代云原生 MQ**’来概括，核心在于**存算分离**。
架构上，它把计算（Broker）和存储（BookKeeper）完全分开。Broker 无状态，扩容时**无需数据迁移**（Rebalance），秒级生效；BookKeeper 负责存储，利用**分片机制**将数据打散，吞吐量极高。
功能上，它原生支持**多租户**、**跨地域复制**和**分层存储**（冷热分离），解决了 Kafka 运维难、扩容慢、不支持资源隔离的痛点。
简单说，如果业务需要极高的弹性、超大规模存储或多租户隔离，Pulsar 是比 Kafka 更好的选择。”

```java
// Pulsar 客户端示例：发送消息
PulsarClient client = PulsarClient.builder()
        .serviceUrl("pulsar://localhost:6650")
        .build();

Producer<byte[]> producer = client.newProducer()
        .topic("my-topic")
        .create();

producer.send("Hello Pulsar".getBytes());
```
