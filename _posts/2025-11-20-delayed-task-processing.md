---
layout: post
title: "如何处理延时任务场景？"
date: 2025-11-20 15:51:36 +0800
categories: [任务调度, 中间件]
tags: [延时任务, 定时任务, 消息队列, Redis, RabbitMQ, 任务调度]
description: "详解延时任务的多种实现方案，包括定时轮询、DelayQueue、时间轮、消息队列延时消息、Redis 过期监听等方案的原理和选型"
---

## 核心概念

**延时任务**（Delayed Task）是指需要在指定时间后执行的任务，而不是立即执行。典型场景包括：
- **订单超时自动取消**（下单 30 分钟未支付）
- **优惠券到期提醒**（到期前 3 天提醒用户）
- **定时消息推送**（预约时间发送通知）
- **会员到期处理**（会员到期降级）

延时任务的核心挑战在于：**如何高效、可靠地在未来某个时间点触发任务执行**。

---

## 常见实现方案

### 1. 定时轮询数据库（最简单但不推荐）

**原理**：启动定时任务（如每分钟一次），扫描数据库中到期的记录并处理。

```java
@Scheduled(cron = "0 * * * * ?")  // 每分钟执行
public void scanExpiredOrders() {
    List<Order> expiredOrders = orderMapper.selectList(
        new QueryWrapper<Order>()
            .eq("status", "UNPAID")
            .lt("create_time", LocalDateTime.now().minusMinutes(30))
    );
    
    for (Order order : expiredOrders) {
        cancelOrder(order.getId());
    }
}
```

**优点**：实现简单，不依赖额外组件  
**缺点**：
- 数据库压力大（频繁全表扫描）
- 时效性差（最多延迟 1 分钟）
- 分布式环境下需处理重复执行问题

**适用场景**：数据量小、时效性要求不高的小型系统

---

### 2. JDK DelayQueue（单机内存方案）

**原理**：基于优先级队列（PriorityQueue）+ 延时元素（Delayed）实现的阻塞队列，元素按到期时间排序，只有到期元素才能被取出。

```java
public class DelayedTask implements Delayed {
    private final String taskId;
    private final long executeTime;  // 执行时间戳

    public DelayedTask(String taskId, long delayMs) {
        this.taskId = taskId;
        this.executeTime = System.currentTimeMillis() + delayMs;
    }

    @Override
    public long getDelay(TimeUnit unit) {
        long diff = executeTime - System.currentTimeMillis();
        return unit.convert(diff, TimeUnit.MILLISECONDS);
    }

    @Override
    public int compareTo(Delayed o) {
        return Long.compare(this.executeTime, ((DelayedTask) o).executeTime);
    }
}

// 使用示例
@Component
public class DelayTaskManager {
    private final DelayQueue<DelayedTask> delayQueue = new DelayQueue<>();

    @PostConstruct
    public void startConsumer() {
        new Thread(() -> {
            while (true) {
                try {
                    DelayedTask task = delayQueue.take();  // 阻塞直到有到期任务
                    processTask(task);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
        }).start();
    }

    public void addTask(String taskId, long delayMs) {
        delayQueue.offer(new DelayedTask(taskId, delayMs));
    }
}
```

**优点**：性能高，时效性准确  
**缺点**：
- 单机方案，不支持集群
- 数据存在内存中，重启后丢失
- 无法处理大量任务（内存限制）

**适用场景**：单机应用，任务量少，可容忍重启丢失

---

### 3. Redis 有序集合 ZSet + 定时扫描

**原理**：利用 ZSet 的 score 存储任务执行时间戳，定时扫描到期任务并执行。

```java
@Component
public class RedisDelayQueue {
    @Autowired
    private StringRedisTemplate redisTemplate;
    
    private static final String DELAY_QUEUE_KEY = "delay:queue";

    // 添加延时任务
    public void addTask(String taskId, long delayMs) {
        long executeTime = System.currentTimeMillis() + delayMs;
        redisTemplate.opsForZSet().add(DELAY_QUEUE_KEY, taskId, executeTime);
    }

    // 定时扫描（可用 @Scheduled 或独立线程）
    @Scheduled(fixedDelay = 1000)  // 每秒扫描
    public void consumeTasks() {
        long now = System.currentTimeMillis();
        
        // 查询到期任务（score <= now）
        Set<String> tasks = redisTemplate.opsForZSet()
            .rangeByScore(DELAY_QUEUE_KEY, 0, now);
        
        if (tasks != null && !tasks.isEmpty()) {
            for (String taskId : tasks) {
                // 使用 Lua 保证原子性（避免重复消费）
                Long removed = redisTemplate.execute(
                    new DefaultRedisScript<>(
                        "if redis.call('zscore', KEYS[1], ARGV[1]) then " +
                        "    redis.call('zrem', KEYS[1], ARGV[1]) " +
                        "    return 1 " +
                        "else " +
                        "    return 0 " +
                        "end",
                        Long.class
                    ),
                    Collections.singletonList(DELAY_QUEUE_KEY),
                    taskId
                );
                
                if (removed != null && removed == 1) {
                    processTask(taskId);
                }
            }
        }
    }
}
```

**优点**：
- 支持分布式，多实例部署
- 数据持久化，不怕重启
- 时效性较好（秒级）

**缺点**：
- 需要定时扫描，仍有轮询开销
- 分布式锁保证原子性略复杂

**适用场景**：中小型分布式系统，延时精度要求秒级

---

### 4. Redis Keyspace Notifications（过期通知）

**原理**：利用 Redis 的 key 过期事件通知机制，key 过期时触发回调。

```yaml
# redis.conf 配置
notify-keyspace-events Ex
```

```java
@Configuration
public class RedisExpireConfig {
    @Bean
    public RedisMessageListenerContainer container(RedisConnectionFactory factory) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(factory);
        
        // 监听所有 DB 的过期事件
        container.addMessageListener(new KeyExpirationListener(container), 
            new PatternTopic("__keyevent@*__:expired"));
        
        return container;
    }
}

@Component
public class KeyExpirationListener extends KeyExpirationEventMessageListener {
    public KeyExpirationListener(RedisMessageListenerContainer listenerContainer) {
        super(listenerContainer);
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        String expiredKey = message.toString();
        if (expiredKey.startsWith("order:")) {
            String orderId = expiredKey.substring(6);
            cancelOrder(orderId);
        }
    }
}

// 使用示例
public void createOrder(String orderId) {
    // 业务逻辑...
    
    // 设置 30 分钟过期
    redisTemplate.opsForValue().set(
        "order:" + orderId, 
        orderId, 
        30, 
        TimeUnit.MINUTES
    );
}
```

**优点**：实现简单，无需轮询  
**缺点**：
- **过期通知不可靠**（Redis 文档明确说明可能丢失）
- 通知时 key 已删除，无法获取原始数据
- 高并发下可能丢消息

**适用场景**：辅助方案，不适合核心业务

---

### 5. RabbitMQ 延时队列（推荐）

**原理**：利用 RabbitMQ 的 **死信交换机（DLX）** + **TTL** 实现延时消息。

```java
@Configuration
public class DelayQueueConfig {
    // 延时队列（消息过期后转到死信交换机）
    @Bean
    public Queue delayQueue() {
        return QueueBuilder.durable("delay.queue")
            .withArgument("x-dead-letter-exchange", "business.exchange")
            .withArgument("x-dead-letter-routing-key", "business.key")
            .build();
    }

    // 业务队列（接收死信消息）
    @Bean
    public Queue businessQueue() {
        return new Queue("business.queue", true);
    }

    @Bean
    public DirectExchange businessExchange() {
        return new DirectExchange("business.exchange");
    }

    @Bean
    public Binding businessBinding() {
        return BindingBuilder.bind(businessQueue())
            .to(businessExchange())
            .with("business.key");
    }
}

// 发送延时消息
public void sendDelayMessage(String orderId, long delayMs) {
    rabbitTemplate.convertAndSend("", "delay.queue", orderId, message -> {
        message.getMessageProperties().setExpiration(String.valueOf(delayMs));
        return message;
    });
}

// 消费业务消息
@RabbitListener(queues = "business.queue")
public void handleExpiredOrder(String orderId) {
    cancelOrder(orderId);
}
```

**RabbitMQ 3.6+ 延时插件方案**：

```bash
# 安装插件
rabbitmq-plugins enable rabbitmq_delayed_message_exchange
```

```java
@Bean
public CustomExchange delayExchange() {
    Map<String, Object> args = new HashMap<>();
    args.put("x-delayed-type", "direct");
    return new CustomExchange("delay.exchange", "x-delayed-message", true, false, args);
}

// 发送延时消息
rabbitTemplate.convertAndSend("delay.exchange", "delay.key", orderId, message -> {
    message.getMessageProperties().setHeader("x-delay", delayMs);
    return message;
});
```

**优点**：
- 消息可靠性高（持久化 + 确认机制）
- 支持分布式
- 时效性好（毫秒级）

**缺点**：
- 需要引入 RabbitMQ
- 延时插件需单独安装

**适用场景**：**生产环境首选**，特别是已有 RabbitMQ 的系统

---

### 6. 时间轮算法（Netty/Kafka 使用）

**原理**：类似时钟，将任务分配到不同时间刻度的槽位，指针滚动触发任务。

```java
// Netty 的 HashedWheelTimer
HashedWheelTimer timer = new HashedWheelTimer(
    100, TimeUnit.MILLISECONDS,  // tickDuration: 每格时长
    10                            // ticksPerWheel: 时间轮格数
);

// 添加延时任务
timer.newTimeout(timeout -> {
    cancelOrder(orderId);
}, 30, TimeUnit.MINUTES);
```

**优点**：高性能，适合大量短延时任务  
**缺点**：精度受限于 tick 间隔，单机方案

**适用场景**：框架内部（如 Dubbo 超时检测），高性能场景

---

## 方案选型建议

| 方案 | 时效性 | 可靠性 | 分布式 | 适用场景 |
|------|-------|-------|--------|---------|
| 定时轮询 DB | 分钟级 | ⭐⭐ | ✅ | 小型系统 |
| DelayQueue | 毫秒级 | ⭐⭐ | ❌ | 单机应用 |
| Redis ZSet | 秒级 | ⭐⭐⭐ | ✅ | 中小型系统 |
| Redis 过期通知 | 秒级 | ⭐ | ✅ | 辅助方案 |
| **RabbitMQ** | 毫秒级 | ⭐⭐⭐⭐⭐ | ✅ | **生产推荐** |
| 时间轮 | 毫秒级 | ⭐⭐⭐ | ❌ | 高性能场景 |

---

## 线程安全与分布式考量

### 1. 分布式锁防止重复执行

```java
public void processTask(String taskId) {
    String lockKey = "lock:task:" + taskId;
    Boolean lock = redisTemplate.opsForValue()
        .setIfAbsent(lockKey, "1", 10, TimeUnit.SECONDS);
    
    if (Boolean.TRUE.equals(lock)) {
        try {
            // 执行任务
            doProcess(taskId);
        } finally {
            redisTemplate.delete(lockKey);
        }
    }
}
```

### 2. 幂等性设计

- 任务执行前检查状态（如订单是否已取消）
- 使用唯一 ID 防重表
- 数据库乐观锁（version 字段）

---

## 面试答题总结

**核心考点**：
1. 延时任务的常见场景（订单超时、定时提醒等）
2. 多种实现方案的原理对比（重点是 RabbitMQ 和 Redis）
3. 分布式环境下的重复执行问题
4. 方案选型依据（可靠性、性能、时效性）

**回答框架**：
- 先说典型场景（如订单超时取消）
- 列举方案：简单的轮询 DB → DelayQueue → Redis → RabbitMQ
- 重点讲 RabbitMQ 死信队列原理（生产常用）
- 补充分布式锁和幂等性设计
- 结合项目经验（如"我们用 RabbitMQ 延时队列处理订单超时"）
