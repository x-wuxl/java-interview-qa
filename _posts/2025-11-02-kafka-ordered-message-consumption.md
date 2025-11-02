---
layout: post
title: "Kafka如何实现顺序消费？"
date: 2025-11-02
description: "深入剖析Kafka顺序消费的实现机制，包括分区顺序保证、生产者分区策略、消费者单线程消费及顺序与性能的权衡"
author: "wuxl"
categories: [中间件]
tags: [Kafka, 顺序消费, 分区策略, 消息顺序]
---

## 问题

Kafka如何实现顺序消费？

## 答案

### 一、核心概念

Kafka **无法保证 Topic 级别的全局顺序**，但可以保证 **Partition 内的消息有序**。顺序消费的核心是：**将需要保证顺序的消息路由到同一个 Partition，并由单线程 Consumer 顺序处理**。

### 二、Kafka 的顺序性保证

#### 1. **Partition 内有序，Topic 内无序**

```
Topic: order_events (3个分区)
  Partition 0: msg1 → msg2 → msg3 (有序)
  Partition 1: msg4 → msg5 → msg6 (有序)
  Partition 2: msg7 → msg8 → msg9 (有序)

整体顺序：msg1, msg4, msg7, msg2, msg5, msg8, ... (无序)
```

**原因**：
- Kafka 通过追加写（Append-Only）保证 Partition 内消息按写入顺序存储
- 多个 Partition 之间没有顺序关系，并行写入

#### 2. **顺序性的来源**

**生产者端**：
- 消息按发送顺序写入 Partition
- 通过分区策略控制消息路由

**Broker 端**：
- 顺序追加写入 Partition 日志
- 通过 Offset（偏移量）标识消息位置

**消费者端**：
- 按 Offset 顺序拉取消息
- 单线程处理保证消费顺序

### 三、生产者端实现顺序发送

#### 1. **使用 Key 路由到同一分区**

**原理**：相同 Key 的消息通过哈希算法路由到同一个 Partition

```java
// 示例：保证同一用户的订单消息有序
String userId = "user-12345";
ProducerRecord<String, String> record = new ProducerRecord<>(
    "order_events",     // Topic
    userId,             // Key（分区键）
    orderData           // Value
);
producer.send(record);
```

**分区策略（DefaultPartitioner）**：
```java
// Kafka 内置的分区算法
partition = hash(key) % partition_count

// 示例
hash("user-12345") % 3 = Partition 1
// 所有 key="user-12345" 的消息都发往 Partition 1
```

#### 2. **自定义分区器**

```java
public class OrderPartitioner implements Partitioner {
    @Override
    public int partition(String topic, Object key, byte[] keyBytes,
                         Object value, byte[] valueBytes, Cluster cluster) {
        int partitionCount = cluster.partitionCountForTopic(topic);

        if (key == null) {
            return 0; // 无 Key 时默认分区 0
        }

        // 按业务规则分区（如按订单号的最后一位）
        String orderId = key.toString();
        int lastDigit = Integer.parseInt(orderId.substring(orderId.length() - 1));
        return lastDigit % partitionCount;
    }
}

// 配置自定义分区器
props.put("partitioner.class", "com.example.OrderPartitioner");
```

#### 3. **指定分区**

```java
// 直接指定消息发往 Partition 0
ProducerRecord<String, String> record = new ProducerRecord<>(
    "order_events",     // Topic
    0,                  // Partition（指定分区）
    userId,             // Key
    orderData           // Value
);
producer.send(record);
```

#### 4. **保证单分区内的发送顺序**

**配置参数**：
```java
props.put("max.in.flight.requests.per.connection", 1); // 每个连接最多1个未响应请求
props.put("enable.idempotence", true);                  // 开启幂等性（自动设置上述参数）
```

**为什么需要这个配置？**

```
场景：max.in.flight.requests.per.connection = 5（默认）

  发送消息1 → 请求1（网络延迟）
  发送消息2 → 请求2（先到达 Broker）
  ↓
  Broker 收到顺序：消息2 → 消息1（乱序）

解决：max.in.flight.requests.per.connection = 1
  发送消息1 → 等待响应
  收到响应 → 发送消息2
  ↓
  Broker 收到顺序：消息1 → 消息2（有序）
```

**注意**：
- `enable.idempotence=true` 时，自动设置 `max.in.flight.requests.per.connection=5`
- 但幂等性保证了即使并发请求也能保持顺序（通过 Sequence Number）

### 四、消费者端实现顺序消费

#### 1. **单线程消费（最简单）**

```java
props.put("enable.auto.commit", false); // 手动提交

KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props);
consumer.subscribe(Arrays.asList("order_events"));

while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));

    // 单线程顺序处理
    for (ConsumerRecord<String, String> record : records) {
        processRecord(record); // 顺序处理每条消息
    }

    consumer.commitSync(); // 处理完成后提交 Offset
}
```

**优点**：
- ✅ 简单可靠，保证顺序
- ✅ 无并发问题

**缺点**：
- ❌ 性能低，无法并行处理

#### 2. **多线程消费 + 按 Key 分组（推荐）**

**思路**：按 Key 将消息分配到不同的线程池队列，同一 Key 的消息由同一个线程处理

```java
// 创建多个线程池，每个线程池处理一个 Key 的消息
Map<String, ExecutorService> executorMap = new ConcurrentHashMap<>();

while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));

    for (ConsumerRecord<String, String> record : records) {
        String key = record.key(); // 订单 ID 或用户 ID

        // 为每个 Key 创建独立的线程池（单线程池）
        ExecutorService executor = executorMap.computeIfAbsent(key, k ->
            Executors.newSingleThreadExecutor() // 单线程池保证顺序
        );

        executor.submit(() -> processRecord(record));
    }

    consumer.commitSync();
}
```

**优化版本：使用线程安全队列**

```java
// 预先创建固定数量的线程池（如 10 个）
int threadCount = 10;
List<BlockingQueue<ConsumerRecord<String, String>>> queues = new ArrayList<>();
List<Thread> workers = new ArrayList<>();

for (int i = 0; i < threadCount; i++) {
    BlockingQueue<ConsumerRecord<String, String>> queue = new LinkedBlockingQueue<>();
    queues.add(queue);

    // 每个线程从队列中取消息并顺序处理
    Thread worker = new Thread(() -> {
        while (true) {
            try {
                ConsumerRecord<String, String> record = queue.take();
                processRecord(record);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    });
    worker.start();
    workers.add(worker);
}

// 消费者将消息按 Key 哈希分配到队列
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));

    for (ConsumerRecord<String, String> record : records) {
        int queueIndex = Math.abs(record.key().hashCode()) % threadCount;
        queues.get(queueIndex).put(record); // 相同 Key 进入同一队列
    }

    consumer.commitSync();
}
```

**优点**：
- ✅ 相同 Key 的消息顺序处理
- ✅ 不同 Key 的消息并行处理，性能高

**缺点**：
- ❌ 实现复杂
- ❌ 需要注意线程池管理和队列容量

#### 3. **Consumer Group 策略**

**规则**：一个 Partition 只能被 Consumer Group 中的一个 Consumer 消费

```
Partition 0 → Consumer 1（顺序消费）
Partition 1 → Consumer 2（顺序消费）
Partition 2 → Consumer 3（顺序消费）
```

**最佳实践**：
- Consumer 数量 ≤ Partition 数量
- 一个 Consumer 可以消费多个 Partition（顺序处理）

### 五、顺序消费的常见问题

#### 1. **Rebalance 导致顺序性问题**

```
Consumer 1 正在处理 Partition 0 的消息（Offset 100-105）
  ↓
Consumer 2 加入，触发 Rebalance
  ↓
Partition 0 分配给 Consumer 2
  ↓
Consumer 2 从 Offset 106 开始消费（Offset 100-105 可能未提交）
  ↓
重复消费 Offset 100-105，但顺序可能错乱
```

**解决方案**：
- 在 Rebalance 监听器中提交 Offset
- 使用 **Sticky 分区分配策略**（减少 Rebalance 时分区迁移）

```java
props.put("partition.assignment.strategy", "org.apache.kafka.clients.consumer.StickyAssignor");
```

#### 2. **生产者重试导致乱序**

```
发送消息1 → 失败，重试
发送消息2 → 成功
发送消息1（重试）→ 成功
  ↓
Broker 收到顺序：消息2 → 消息1（乱序）
```

**解决方案**：
```java
props.put("max.in.flight.requests.per.connection", 1); // 单请求模式
// 或
props.put("enable.idempotence", true); // 幂等性自动保证顺序
```

#### 3. **多线程消费导致乱序**

```
Consumer 拉取消息：msg1, msg2, msg3
  ↓
线程1处理 msg1（耗时长）
线程2处理 msg2（快速完成）
线程3处理 msg3（快速完成）
  ↓
实际处理顺序：msg2 → msg3 → msg1（乱序）
```

**解决方案**：
- 单线程消费
- 或按 Key 分组到不同线程（同一 Key 单线程）

### 六、顺序性与性能的权衡

| 方案 | 顺序性 | 吞吐量 | 适用场景 |
|------|--------|--------|----------|
| **单分区 + 单 Consumer** | 全局有序 | 极低 | 严格顺序（如账户流水） |
| **多分区 + Key 路由 + 单线程** | 局部有序 | 中 | 同一实体有序（如同一订单） |
| **多分区 + Key 路由 + 多线程（Key 分组）** | 局部有序 | 高 | 高并发场景（如电商订单） |
| **多分区 + 无 Key** | 无序 | 极高 | 无顺序要求（如日志） |

### 七、实战配置示例

#### 场景：保证同一用户的订单消息有序

**Producer 配置**：
```java
Properties props = new Properties();
props.put("bootstrap.servers", "localhost:9092");
props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");
props.put("enable.idempotence", true);  // 开启幂等性，保证分区内有序
props.put("acks", "all");                // 高可靠

// 发送消息，使用 userId 作为 Key
producer.send(new ProducerRecord<>("order_events", userId, orderData));
```

**Consumer 配置**：
```java
Properties props = new Properties();
props.put("bootstrap.servers", "localhost:9092");
props.put("group.id", "order-consumer-group");
props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
props.put("enable.auto.commit", false); // 手动提交
props.put("partition.assignment.strategy", "org.apache.kafka.clients.consumer.StickyAssignor");

// 单线程消费或按 Key 分组消费
```

### 八、总结

**Kafka 如何实现顺序消费？**

1. **生产者端**：
   - 使用 Key 路由（相同 Key 到同一 Partition）
   - 开启幂等性（`enable.idempotence=true`）
   - 单请求模式（`max.in.flight.requests.per.connection=1`，幂等性下可省略）

2. **Broker 端**：
   - Partition 内顺序追加写入
   - Offset 标识消息位置

3. **消费者端**：
   - 单线程消费（简单）
   - 或按 Key 分组到不同线程（性能优）
   - 避免 Rebalance（使用 Sticky 策略）

**面试答题要点**：
- **Partition 内有序，Topic 内无序**
- **Key 路由**：相同 Key 的消息到同一 Partition
- **单线程消费**：保证顺序，但性能低
- **按 Key 分组多线程**：性能和顺序的平衡
- **权衡点**：全局顺序 vs 性能（单分区 vs 多分区）
