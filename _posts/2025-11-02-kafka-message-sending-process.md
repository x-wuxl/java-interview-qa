---
layout: post
title: "Kafka消息的发送过程简单介绍一下？"
date: 2025-11-02
description: "详解Kafka Producer发送消息的完整流程，包括拦截器、序列化、分区选择、批量累加、Sender线程发送及响应处理等核心步骤"
author: "wuxl"
categories: [中间件]
tags: [Kafka, Producer, 消息发送, 源码分析]
---

## 问题

Kafka消息的发送过程简单介绍一下？

## 答案

### 一、核心概念

Kafka Producer 发送消息的过程涉及**拦截器、序列化、分区选择、批量累加、网络发送**等多个环节，采用**异步批量**的方式提升吞吐量。

### 二、消息发送完整流程

```
Producer API
    ↓
① 拦截器（Interceptor）
    ↓
② 序列化器（Serializer）
    ↓
③ 分区器（Partitioner）
    ↓
④ 累加器（RecordAccumulator）
    ↓
⑤ Sender线程（发送线程）
    ↓
⑥ Broker响应处理
    ↓
⑦ 回调函数（Callback）
```

### 三、各阶段详细解析

#### 1. **Producer API 调用**

```java
// 同步发送
Future<RecordMetadata> future = producer.send(record);
RecordMetadata metadata = future.get(); // 阻塞等待响应

// 异步发送（推荐）
producer.send(record, new Callback() {
    @Override
    public void onCompletion(RecordMetadata metadata, Exception exception) {
        if (exception == null) {
            System.out.println("发送成功：" + metadata.offset());
        } else {
            System.err.println("发送失败：" + exception.getMessage());
        }
    }
});
```

#### 2. **拦截器处理（Interceptor）**

- **作用**：在消息发送前后执行自定义逻辑（如监控、埋点、消息修改）
- **核心方法**：
  - `onSend(ProducerRecord)`：发送前调用，可修改消息
  - `onAcknowledgement(RecordMetadata, Exception)`：响应后调用

```java
// 自定义拦截器示例
public class CustomInterceptor implements ProducerInterceptor<String, String> {
    @Override
    public ProducerRecord<String, String> onSend(ProducerRecord<String, String> record) {
        // 添加时间戳前缀
        String newValue = System.currentTimeMillis() + ":" + record.value();
        return new ProducerRecord<>(record.topic(), record.key(), newValue);
    }
}
```

#### 3. **序列化（Serializer）**

- **作用**：将 Key 和 Value 对象序列化为字节数组
- **常用序列化器**：
  - `StringSerializer`：字符串序列化
  - `IntegerSerializer`、`LongSerializer`：基本类型
  - `JsonSerializer`、`AvroSerializer`：复杂对象

```java
props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");
```

#### 4. **分区选择（Partitioner）**

**分区策略**：
- **指定分区**：如果 `ProducerRecord` 中指定了 Partition，直接使用
- **有 Key**：对 Key 进行哈希，`hash(key) % partition_count`，保证相同 Key 进入同一分区
- **无 Key**：使用**粘性分区策略**（Sticky Partitioning，Kafka 2.4+）
  - 旧版本：轮询（Round-Robin）
  - 新版本：随机选择一个分区，填满一个 Batch 后再切换（减少请求数，提升性能）

```java
// 自定义分区器
public class CustomPartitioner implements Partitioner {
    @Override
    public int partition(String topic, Object key, byte[] keyBytes,
                         Object value, byte[] valueBytes, Cluster cluster) {
        // 根据业务逻辑自定义分区
        if (key != null && key.toString().startsWith("VIP")) {
            return 0; // VIP用户路由到分区0
        }
        return Math.abs(key.hashCode()) % cluster.partitionCountForTopic(topic);
    }
}
```

#### 5. **累加器（RecordAccumulator）**

- **作用**：消息暂存区，实现批量发送
- **核心机制**：
  - 为每个 `<Topic, Partition>` 维护一个双端队列（Deque）
  - 消息追加到队列的批次（Batch）中
  - 当批次满足发送条件时，唤醒 Sender 线程

**发送条件**（满足任一条件即发送）：
1. Batch 大小达到 `batch.size`（默认 16KB）
2. 等待时间达到 `linger.ms`（默认 0ms，立即发送）
3. 累加器内存不足
4. 手动调用 `flush()` 或 `close()`

```java
props.put("batch.size", 16384);        // 16KB
props.put("linger.ms", 10);            // 等待10ms收集更多消息
props.put("buffer.memory", 33554432);  // 32MB总缓冲区
```

#### 6. **Sender 线程发送**

- **独立后台线程**：负责从 RecordAccumulator 中取出批次并发送到 Broker
- **网络请求构建**：
  - 将批次封装为 `ProduceRequest`
  - 通过 `NetworkClient` 发送请求（基于 NIO）
  - 每个 Broker 连接维护一个 InFlightRequests 队列（控制未响应请求数）

**关键参数**：
```java
props.put("max.in.flight.requests.per.connection", 5); // 每个连接最多5个未响应请求
props.put("retries", Integer.MAX_VALUE);               // 重试次数
props.put("request.timeout.ms", 30000);                // 请求超时时间
```

#### 7. **Broker 响应处理**

**acks 参数决定响应时机**：
- **acks=0**：Producer 不等待响应（最高吞吐，可能丢失）
- **acks=1**：等待 Leader 确认写入（默认）
- **acks=all（-1）**：等待所有 ISR 副本确认（最高可靠性）

**响应处理**：
- **成功**：返回 RecordMetadata（包含 offset、partition、timestamp）
- **失败**：可重试的错误自动重试，不可重试的错误返回异常

#### 8. **回调函数（Callback）**

- 异步发送完成后，调用用户指定的回调函数
- **执行线程**：在 Producer 的 I/O 线程中执行，**不要执行耗时操作**
- **参数**：RecordMetadata（成功时）、Exception（失败时）

```java
producer.send(record, (metadata, exception) -> {
    if (exception == null) {
        // 成功处理
        log.info("Offset: {}, Partition: {}", metadata.offset(), metadata.partition());
    } else {
        // 失败处理
        log.error("Send failed", exception);
    }
});
```

### 四、发送模式对比

| 模式 | 实现方式 | 性能 | 可靠性 | 适用场景 |
|------|----------|------|--------|----------|
| **同步发送** | `send().get()` | 低 | 高 | 需要立即知道结果 |
| **异步发送** | `send(callback)` | 高 | 高 | 推荐，生产环境常用 |
| **Fire-and-Forget** | `send()` | 最高 | 低 | 允许少量丢失的日志场景 |

### 五、关键参数配置

```java
Properties props = new Properties();
// 基础配置
props.put("bootstrap.servers", "localhost:9092");
props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");

// 性能优化
props.put("batch.size", 16384);                // 批次大小
props.put("linger.ms", 10);                    // 等待时间
props.put("compression.type", "lz4");          // 压缩算法
props.put("buffer.memory", 33554432);          // 缓冲区大小

// 可靠性保证
props.put("acks", "all");                      // 等待所有ISR确认
props.put("retries", Integer.MAX_VALUE);       // 无限重试
props.put("max.in.flight.requests.per.connection", 1); // 保证顺序
props.put("enable.idempotence", true);         // 开启幂等性
```

### 六、幂等性和事务（高级特性）

#### 1. **幂等性（Idempotence）**
```java
props.put("enable.idempotence", true); // 开启幂等性
```
- **作用**：避免因重试导致的消息重复
- **原理**：Producer 和 Broker 为每条消息分配唯一 ID（PID + Sequence Number）
- **限制**：仅保证单分区、单会话的幂等性

#### 2. **事务（Transaction）**
```java
props.put("transactional.id", "my-transactional-id");
producer.initTransactions();
producer.beginTransaction();
try {
    producer.send(record1);
    producer.send(record2);
    producer.commitTransaction();
} catch (Exception e) {
    producer.abortTransaction();
}
```

### 七、总结

**Kafka 消息发送流程核心步骤**：

1. **拦截器**：自定义前置/后置处理
2. **序列化**：对象 → 字节数组
3. **分区选择**：确定消息发往哪个 Partition
4. **累加器**：批量缓存，提升吞吐量
5. **Sender 线程**：异步发送到 Broker
6. **响应处理**：根据 acks 参数等待确认
7. **回调函数**：异步通知发送结果

**面试答题要点**：
- **异步批量**：通过 RecordAccumulator 实现批量发送
- **分区策略**：指定分区 > Key哈希 > 粘性分区
- **可靠性保证**：acks=all + 重试 + 幂等性
- **性能优化**：批量 + 压缩 + 异步发送
