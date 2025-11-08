---
layout: post
title: "Redis 7 实现延时队列"
date: 2025-11-08
description: "深入讲解如何使用 Redis 7 实现延时队列，包括 Sorted Set 和 Stream 两种方案的原理、实现与对比"
author: "wuxl"
categories: [中间件]
tags: [Redis, 延时队列, Sorted Set, Stream, 消息队列]
---

## 问题

Redis 7 实现延时队列

## 答案

### 一、核心概念

**延时队列**（Delayed Queue）是指消息发送后不会立即被消费，而是在指定的延迟时间后才能被消费者获取。常用于订单超时取消、定时任务触发、消息重试等场景。

Redis 提供了多种数据结构可以实现延时队列，Redis 7 中最常用的两种方案是：
1. **Sorted Set（有序集合）+ 轮询**
2. **Stream + 消费者组**

---

### 二、方案一：Sorted Set 实现延时队列

#### 原理

利用 Sorted Set 的 **score 作为时间戳**，将消息按执行时间排序：
- 生产者将消息存入 Sorted Set，score 设置为 `当前时间 + 延迟时间`
- 消费者定时轮询，使用 `ZRANGEBYSCORE` 查询 score 小于当前时间的消息
- 消费后使用 `ZREM` 删除消息，避免重复消费

#### 实现代码

```java
import redis.clients.jedis.Jedis;
import redis.clients.jedis.params.ZRangeParams;

import java.util.Set;

public class RedisDelayQueue {

    private static final String DELAY_QUEUE_KEY = "delay_queue";
    private final Jedis jedis;

    public RedisDelayQueue(Jedis jedis) {
        this.jedis = jedis;
    }

    /**
     * 生产消息：将消息加入延时队列
     * @param message 消息内容
     * @param delaySeconds 延迟秒数
     */
    public void produce(String message, long delaySeconds) {
        long executeTime = System.currentTimeMillis() + delaySeconds * 1000;
        jedis.zadd(DELAY_QUEUE_KEY, executeTime, message);
        System.out.println("消息已加入队列: " + message + ", 执行时间: " + executeTime);
    }

    /**
     * 消费消息：轮询获取到期的消息
     */
    public void consume() {
        while (true) {
            try {
                long currentTime = System.currentTimeMillis();

                // 查询 score <= currentTime 的消息（最多取 1 条）
                Set<String> messages = jedis.zrangeByScore(
                    DELAY_QUEUE_KEY,
                    0,
                    currentTime,
                    0,
                    1
                );

                if (messages.isEmpty()) {
                    Thread.sleep(500); // 无消息时休眠 500ms
                    continue;
                }

                String message = messages.iterator().next();

                // 删除消息（防止重复消费）
                Long removed = jedis.zrem(DELAY_QUEUE_KEY, message);

                if (removed > 0) {
                    // 成功删除，处理消息
                    handleMessage(message);
                }

            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    /**
     * 处理消息的业务逻辑
     */
    private void handleMessage(String message) {
        System.out.println("消费消息: " + message + ", 时间: " + System.currentTimeMillis());
        // 实际业务处理...
    }
}
```

#### 使用示例

```java
public class DelayQueueDemo {
    public static void main(String[] args) {
        Jedis jedis = new Jedis("localhost", 6379);
        RedisDelayQueue delayQueue = new RedisDelayQueue(jedis);

        // 生产者：发送延时消息
        new Thread(() -> {
            delayQueue.produce("订单超时取消-001", 10); // 10秒后执行
            delayQueue.produce("订单超时取消-002", 20); // 20秒后执行
        }).start();

        // 消费者：轮询消费
        new Thread(delayQueue::consume).start();
    }
}
```

#### 优化：使用 Lua 脚本保证原子性

为避免多个消费者同时获取同一消息，可使用 Lua 脚本实现 **查询 + 删除** 的原子操作：

```java
public String consumeWithLua() {
    String luaScript =
        "local messages = redis.call('ZRANGEBYSCORE', KEYS[1], 0, ARGV[1], 'LIMIT', 0, 1) " +
        "if #messages > 0 then " +
        "    redis.call('ZREM', KEYS[1], messages[1]) " +
        "    return messages[1] " +
        "end " +
        "return nil";

    Object result = jedis.eval(
        luaScript,
        1,
        DELAY_QUEUE_KEY,
        String.valueOf(System.currentTimeMillis())
    );

    return result != null ? result.toString() : null;
}
```

---

### 三、方案二：Redis Stream 实现延时队列（Redis 7 推荐）

#### 原理

Redis 7 增强了 Stream 的功能，可以结合 **消费者组** 和 **XPENDING** 实现延时队列：
- 生产者将消息写入 Stream，附带延迟时间戳
- 消费者使用 `XREADGROUP` 读取消息，但不立即 ACK
- 通过 `XPENDING` 查询未确认消息，判断是否到期后再处理

#### 实现代码

```java
import redis.clients.jedis.Jedis;
import redis.clients.jedis.StreamEntryID;
import redis.clients.jedis.resps.StreamEntry;

import java.util.AbstractMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class RedisStreamDelayQueue {

    private static final String STREAM_KEY = "delay_stream";
    private static final String GROUP_NAME = "delay_group";
    private static final String CONSUMER_NAME = "consumer_1";

    private final Jedis jedis;

    public RedisStreamDelayQueue(Jedis jedis) {
        this.jedis = jedis;
        // 创建消费者组（如果不存在）
        try {
            jedis.xgroupCreate(STREAM_KEY, GROUP_NAME, new StreamEntryID(), true);
        } catch (Exception e) {
            // 组已存在，忽略
        }
    }

    /**
     * 生产消息
     */
    public void produce(String message, long delaySeconds) {
        long executeTime = System.currentTimeMillis() + delaySeconds * 1000;

        Map<String, String> messageBody = new HashMap<>();
        messageBody.put("content", message);
        messageBody.put("executeTime", String.valueOf(executeTime));

        jedis.xadd(STREAM_KEY, StreamEntryID.NEW_ENTRY, messageBody);
        System.out.println("消息已加入 Stream: " + message);
    }

    /**
     * 消费消息
     */
    public void consume() {
        while (true) {
            try {
                // 读取新消息
                List<Map.Entry<String, List<StreamEntry>>> entries = jedis.xreadGroup(
                    GROUP_NAME,
                    CONSUMER_NAME,
                    1,
                    1000,
                    false,
                    new AbstractMap.SimpleEntry<>(STREAM_KEY, StreamEntryID.UNRECEIVED_ENTRY)
                );

                if (entries != null && !entries.isEmpty()) {
                    for (Map.Entry<String, List<StreamEntry>> entry : entries) {
                        for (StreamEntry streamEntry : entry.getValue()) {
                            processMessage(streamEntry);
                        }
                    }
                }

                Thread.sleep(500);

            } catch (Exception e) {
                e.printStackTrace();
            }
        }
    }

    /**
     * 处理消息（检查是否到期）
     */
    private void processMessage(StreamEntry entry) {
        Map<String, String> fields = entry.getFields();
        long executeTime = Long.parseLong(fields.get("executeTime"));
        long currentTime = System.currentTimeMillis();

        if (currentTime >= executeTime) {
            // 消息已到期，执行业务逻辑
            String content = fields.get("content");
            System.out.println("消费消息: " + content);

            // 确认消息
            jedis.xack(STREAM_KEY, GROUP_NAME, entry.getID());
        } else {
            // 未到期，暂不处理（下次轮询再检查）
            System.out.println("消息未到期，跳过: " + fields.get("content"));
        }
    }
}
```

---

### 四、两种方案对比

| 特性 | Sorted Set 方案 | Stream 方案 |
|------|----------------|-------------|
| **实现复杂度** | 简单，代码量少 | 较复杂，需处理消费者组 |
| **消息可靠性** | 需手动保证原子性（Lua 脚本） | 内置 ACK 机制，可靠性高 |
| **并发消费** | 需 Lua 脚本避免重复消费 | 天然支持多消费者 |
| **消息持久化** | 依赖 Redis 持久化 | 支持 AOF/RDB，更可靠 |
| **适用场景** | 简单延时任务、单消费者 | 高可靠性、多消费者场景 |
| **性能** | 轮询开销较大 | 阻塞读取，性能更优 |

---

### 五、生产环境优化建议

1. **设置过期时间**：为 Sorted Set 或 Stream 设置 TTL，避免消息堆积
   ```java
   jedis.expire(DELAY_QUEUE_KEY, 86400); // 1天过期
   ```

2. **监控队列长度**：定期检查队列积压情况
   ```java
   long queueSize = jedis.zcard(DELAY_QUEUE_KEY);
   ```

3. **消息重试机制**：消费失败时重新加入队列
   ```java
   delayQueue.produce(message, 60); // 1分钟后重试
   ```

4. **分布式锁**：多实例部署时，使用 Redisson 的分布式锁避免重复消费

5. **使用 Redisson 封装**：Redisson 提供了开箱即用的延时队列实现
   ```java
   RDelayedQueue<String> delayedQueue = redisson.getDelayedQueue(
       redisson.getQueue("myQueue")
   );
   delayedQueue.offer("message", 10, TimeUnit.SECONDS);
   ```

---

### 六、答题总结

**Redis 7 实现延时队列的核心思路**：
1. **Sorted Set 方案**：利用 score 存储执行时间，轮询查询到期消息，适合简单场景
2. **Stream 方案**：结合消费者组和 ACK 机制，可靠性更高，适合生产环境
3. **关键点**：保证消费原子性（Lua 脚本）、监控队列积压、设置消息过期时间
4. **生产推荐**：优先使用 Redisson 的 `RDelayedQueue`，或基于 Stream 自研方案

面试时可根据场景选择方案，并说明优化点（如 Lua 脚本、分布式锁、监控告警等）。
