---
layout: post
title: "Kafka如何保证消息不丢失？"
date: 2025-11-02
description: "全面解析Kafka在Producer、Broker、Consumer三个层面保证消息可靠性的机制，包括acks、副本、ISR、幂等性等核心技术"
author: "wuxl"
categories: [中间件]
tags: [Kafka, 消息可靠性, 高可用, 分布式]
---

## 问题

Kafka如何保证消息不丢失?

## 答案

### 一、核心概念

Kafka 消息可靠性需要从**生产者、Broker、消费者**三个环节综合保障。任何一个环节出现问题都可能导致消息丢失。

### 二、消息丢失的三种场景

```
Producer → Broker → Consumer
   ↓         ↓         ↓
 丢失点1   丢失点2   丢失点3
```

1. **Producer 端丢失**：消息未成功发送到 Broker
2. **Broker 端丢失**：消息写入 Broker 后丢失（磁盘故障、未同步副本）
3. **Consumer 端丢失**：消息被标记为已消费，但业务处理失败

### 三、Producer 端保证消息不丢失

#### 1. **设置 acks 参数（核心）**

```java
props.put("acks", "all"); // 或 acks=-1
```

**acks 参数说明**：
- **acks=0**：Producer 不等待 Broker 确认（最快，但可能丢失）
- **acks=1**：等待 Leader 副本确认写入（默认，Leader 宕机前未同步会丢失）
- **acks=all（-1）**：等待**所有 ISR 副本**确认写入（最可靠）

```
acks=all 工作流程：
Producer → Leader Broker（写入成功）
              ↓
         Follower 1（同步成功）
              ↓
         Follower 2（同步成功）
              ↓
         返回确认给 Producer
```

#### 2. **配置重试机制**

```java
props.put("retries", Integer.MAX_VALUE);          // 无限重试
props.put("retry.backoff.ms", 100);               // 重试间隔
props.put("request.timeout.ms", 30000);           // 请求超时时间
props.put("delivery.timeout.ms", 120000);         // 总超时时间
```

**可重试的错误**：
- `NOT_LEADER_FOR_PARTITION`：Leader 切换
- `NETWORK_EXCEPTION`：网络异常
- `NOT_ENOUGH_REPLICAS`：副本数不足

**不可重试的错误**：
- `INVALID_TOPIC_EXCEPTION`：Topic 不存在
- `RECORD_TOO_LARGE`：消息过大

#### 3. **开启幂等性（避免重复）**

```java
props.put("enable.idempotence", true); // 开启幂等性
```

**幂等性保证**：
- 避免因重试导致消息重复
- Producer 自动分配 PID（Producer ID）+ Sequence Number
- Broker 端去重，保证单分区、单会话的 Exactly Once

#### 4. **同步发送 + 异常处理**

```java
// 方式1：同步发送（可靠但性能低）
try {
    RecordMetadata metadata = producer.send(record).get();
    System.out.println("发送成功：" + metadata.offset());
} catch (Exception e) {
    // 发送失败，执行补偿逻辑（如写入死信队列）
    handleSendFailure(record, e);
}

// 方式2：异步发送 + 回调（推荐）
producer.send(record, (metadata, exception) -> {
    if (exception != null) {
        // 发送失败处理
        handleSendFailure(record, exception);
    }
});
```

### 四、Broker 端保证消息不丢失

#### 1. **副本机制（Replication）**

```bash
# Topic 创建时指定副本数
kafka-topics.sh --create --topic my-topic \
  --replication-factor 3 \
  --partitions 3
```

**副本角色**：
- **Leader**：处理读写请求
- **Follower**：从 Leader 同步数据，作为备份
- **ISR（In-Sync Replicas）**：与 Leader 保持同步的副本集合

```
Partition 0 的副本分布：
  Leader   → Broker 1 (处理读写)
  Follower → Broker 2 (同步数据)
  Follower → Broker 3 (同步数据)
```

#### 2. **配置 min.insync.replicas（关键）**

```bash
# Broker 配置或 Topic 级别配置
min.insync.replicas=2
```

**作用**：
- 指定 ISR 中至少有多少个副本写入成功，Producer 才能收到确认
- 配合 `acks=all` 使用，防止 ISR 中只剩 Leader 时丢失数据

**最佳实践**：
- `replication-factor=3` + `min.insync.replicas=2` + `acks=all`
- 保证至少 2 个副本写入成功，允许 1 个副本故障

```
ISR 副本不足时的行为：
  ISR = [Leader]（只剩一个副本）
    ↓
  acks=all 的 Producer 写入会失败
    ↓
  抛出 NOT_ENOUGH_REPLICAS 异常
    ↓
  Producer 重试，等待副本恢复
```

#### 3. **禁用 unclean.leader.election（重要）**

```bash
unclean.leader.election.enable=false  # Kafka 1.0+ 默认为 false
```

**作用**：
- 禁止从非 ISR 副本中选举 Leader
- 如果所有 ISR 副本都宕机，宁可服务不可用，也不从落后的副本中选举 Leader（避免数据丢失）

**权衡**：
- `false`：数据可靠性优先（推荐）
- `true`：可用性优先（可能丢失数据）

#### 4. **刷盘策略（可选）**

```bash
# 强制刷盘配置（降低性能）
log.flush.interval.messages=1        # 每条消息刷盘
log.flush.interval.ms=1000           # 每秒刷盘
```

**默认行为**：
- Kafka 依赖操作系统的页缓存，不强制刷盘（性能优先）
- 通过副本机制保证可靠性，而非刷盘

**生产建议**：
- **不建议配置强制刷盘**，严重影响性能
- 依赖副本机制 + `acks=all` 保证可靠性

### 五、Consumer 端保证消息不丢失

#### 1. **手动提交 Offset（核心）**

```java
props.put("enable.auto.commit", false); // 禁用自动提交
```

**自动提交的问题**：
- 消费者拉取消息后，Offset 自动提交
- 如果业务处理失败（如数据库写入失败），消息已被标记为消费，导致丢失

**手动提交方案**：

```java
// 方式1：同步提交（可靠但性能低）
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, String> record : records) {
        try {
            processRecord(record); // 业务处理
            consumer.commitSync();  // 同步提交Offset
        } catch (Exception e) {
            // 处理失败，不提交Offset，下次重新消费
            log.error("处理失败：" + record, e);
        }
    }
}

// 方式2：异步提交（推荐）
consumer.commitAsync((offsets, exception) -> {
    if (exception != null) {
        log.error("Offset提交失败", exception);
    }
});

// 方式3：批量处理 + 手动提交
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    processBatch(records); // 批量处理
    consumer.commitSync();  // 批次处理成功后提交
}
```

#### 2. **先处理后提交（核心原则）**

```java
// ✅ 正确做法：先处理，后提交
processRecord(record);    // 1. 业务处理（如写数据库）
consumer.commitSync();    // 2. 提交Offset

// ❌ 错误做法：先提交，后处理
consumer.commitSync();    // 1. 提交Offset
processRecord(record);    // 2. 业务处理（失败则消息丢失）
```

#### 3. **处理 Rebalance（避免重复消费）**

```java
consumer.subscribe(Arrays.asList("my-topic"), new ConsumerRebalanceListener() {
    @Override
    public void onPartitionsRevoked(Collection<TopicPartition> partitions) {
        // Rebalance 前提交当前 Offset
        consumer.commitSync();
    }

    @Override
    public void onPartitionsAssigned(Collection<TopicPartition> partitions) {
        // Rebalance 后从上次提交的位置继续消费
    }
});
```

### 六、完整的高可靠配置

#### Producer 配置
```java
Properties producerProps = new Properties();
producerProps.put("bootstrap.servers", "localhost:9092");
producerProps.put("acks", "all");                          // 等待所有ISR确认
producerProps.put("retries", Integer.MAX_VALUE);           // 无限重试
producerProps.put("max.in.flight.requests.per.connection", 1); // 保证顺序
producerProps.put("enable.idempotence", true);             // 开启幂等性
producerProps.put("compression.type", "lz4");              // 压缩
```

#### Broker 配置
```bash
replication.factor=3                    # 3个副本
min.insync.replicas=2                   # 至少2个副本写入
unclean.leader.election.enable=false    # 禁止非ISR选举
log.flush.interval.messages=10000       # 可选：刷盘策略
```

#### Consumer 配置
```java
Properties consumerProps = new Properties();
consumerProps.put("bootstrap.servers", "localhost:9092");
consumerProps.put("group.id", "my-group");
consumerProps.put("enable.auto.commit", false);            // 手动提交
consumerProps.put("auto.offset.reset", "earliest");        // 从最早位置消费
consumerProps.put("isolation.level", "read_committed");    // 只读已提交消息（事务场景）
```

### 七、可靠性与性能的权衡

| 配置 | 高可靠 | 高性能 |
|------|--------|--------|
| **acks** | all | 0 或 1 |
| **retries** | 无限重试 | 0 |
| **replication.factor** | 3 | 1 |
| **min.insync.replicas** | 2 | 1 |
| **enable.auto.commit** | false | true |
| **刷盘** | 每条刷盘 | 依赖OS |

### 八、总结

**Kafka 保证消息不丢失的核心机制**：

1. **Producer 端**：
   - `acks=all`：等待所有 ISR 副本确认
   - 开启幂等性：避免重试导致重复
   - 同步发送 + 异常处理

2. **Broker 端**：
   - 副本机制：`replication-factor ≥ 3`
   - ISR 机制：`min.insync.replicas=2`
   - 禁止非 ISR 选举：`unclean.leader.election.enable=false`

3. **Consumer 端**：
   - 手动提交 Offset：`enable.auto.commit=false`
   - 先处理后提交：业务处理成功后再提交
   - 处理 Rebalance：避免重复消费

**面试答题要点**：
- **三端保证**：Producer（acks=all + 重试）、Broker（副本 + ISR）、Consumer（手动提交）
- **核心参数**：`acks=all` + `min.insync.replicas=2` + `enable.auto.commit=false`
- **权衡点**：可靠性 vs 性能、可用性 vs 一致性
