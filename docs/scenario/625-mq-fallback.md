---
layout: default
title: "消息队列挂了，你的Plan B是什么？"
parent: 大厂项目场景实战
nav_order: 625
description: "详细讲解MQ故障的降级方案，包括本地消息表、备用MQ切换等策略"
date: 2025-12-28
---

# 消息队列挂了，你的Plan B是什么？

## 面试场景

面试官："假如你项目中的Kafka挂了，怎么办？"

这是考察**系统容灾能力**的问题。高分回答需要：
1. 说明MQ在系统中的作用
2. 给出具体的降级方案
3. 说明恢复后如何保证数据一致性

---

## 明确MQ的使用场景

首先要分析MQ在系统中承担什么角色：

| 场景 | 影响 | 降级优先级 |
|------|------|-----------|
| 异步解耦 | 功能受损 | 高 |
| 削峰填谷 | 系统过载 | 高 |
| 数据同步 | 数据延迟 | 中 |
| 日志采集 | 日志丢失 | 低 |

---

## 方案一：降级为同步调用

### 适用场景
- 调用量不大
- 下游服务能承受直接调用

### 实现方式

```java
@Service
public class OrderService {
    
    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;
    
    @Autowired
    private InventoryService inventoryService;
    
    @Value("${mq.enabled:true}")
    private boolean mqEnabled;
    
    public void createOrder(Order order) {
        // 1. 保存订单
        orderMapper.insert(order);
        
        // 2. 通知库存服务
        if (mqEnabled && isKafkaAvailable()) {
            // 正常走MQ
            kafkaTemplate.send("inventory-topic", JSON.toJSONString(order));
        } else {
            // 降级为同步调用
            inventoryService.deductStock(order);
        }
    }
    
    private boolean isKafkaAvailable() {
        // 健康检查逻辑
        return kafkaHealthIndicator.check();
    }
}
```

### 开关控制

通过配置中心（如Nacos）实现动态开关：

```yaml
# Nacos配置
mq:
  enabled: true  # 紧急情况改为false
```

---

## 方案二：本地消息表

### 适用场景
- 必须保证消息不丢
- 需要最终一致性

### 架构图

```
┌──────────────────────────────────────────────────────────┐
│                      订单服务                             │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐     ┌─────────────────┐                │
│  │  业务逻辑    │ →→→ │  本地消息表        │                │
│  └─────────────┘     └─────────────────┘                │
│                              ↓                          │
│                       ┌─────────────┐                   │
│                       │  定时任务    │                   │
│                       └─────────────┘                   │
│                              ↓                          │
│                    MQ可用？─────┬─────否───→ 重试/告警    │
│                              是                         │
│                              ↓                          │
│                     发送到Kafka                          │
└──────────────────────────────────────────────────────────┘
```

### 数据库设计

```sql
CREATE TABLE local_message (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    message_key VARCHAR(128) NOT NULL,
    message_body TEXT NOT NULL,
    topic VARCHAR(64) NOT NULL,
    status TINYINT DEFAULT 0 COMMENT '0:待发送 1:已发送 2:失败',
    retry_count INT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_status_create (status, create_time)
);
```

### 代码实现

```java
@Service
public class OrderService {
    
    @Transactional
    public void createOrder(Order order) {
        // 1. 保存订单
        orderMapper.insert(order);
        
        // 2. 写入本地消息表（同一事务）
        LocalMessage message = new LocalMessage();
        message.setMessageKey(order.getOrderId());
        message.setMessageBody(JSON.toJSONString(order));
        message.setTopic("order-created");
        message.setStatus(0);
        localMessageMapper.insert(message);
    }
}

@Scheduled(fixedDelay = 1000)  // 每秒执行
public void sendPendingMessages() {
    List<LocalMessage> messages = localMessageMapper.findPending(100);
    
    for (LocalMessage msg : messages) {
        try {
            kafkaTemplate.send(msg.getTopic(), msg.getMessageKey(), msg.getMessageBody())
                .get(3, TimeUnit.SECONDS);  // 同步等待
            
            // 发送成功，更新状态
            localMessageMapper.updateStatus(msg.getId(), 1);
        } catch (Exception e) {
            // 发送失败，重试计数
            localMessageMapper.incrementRetry(msg.getId());
            
            if (msg.getRetryCount() >= 10) {
                // 超过重试次数，告警
                alertService.sendAlert("消息发送失败: " + msg.getId());
            }
        }
    }
}
```

---

## 方案三：本地缓存兜底

### 适用场景
- 读操作为主
- 可接受短时间数据不一致

### 实现方式

```java
@Service
public class ProductService {
    
    // 多级缓存：本地缓存 → Redis → 数据库
    @Autowired
    private Cache<Long, Product> localCache;  // Caffeine
    
    @Autowired
    private RedisTemplate<String, Product> redisTemplate;
    
    public Product getProduct(Long productId) {
        // L1: 本地缓存
        Product product = localCache.getIfPresent(productId);
        if (product != null) return product;
        
        // L2: Redis（如果Redis也挂了，这里会异常）
        try {
            product = redisTemplate.opsForValue().get("product:" + productId);
            if (product != null) {
                localCache.put(productId, product);
                return product;
            }
        } catch (Exception e) {
            log.warn("Redis不可用，降级到数据库");
        }
        
        // L3: 数据库
        product = productMapper.findById(productId);
        if (product != null) {
            localCache.put(productId, product);
        }
        return product;
    }
}
```

---

## 方案四：备用消息队列

### 适用场景
- 消息非常重要
- 公司有多套MQ集群

### 架构

```
       ┌─────────────────────────────────────┐
       │                                     │
       │   主MQ集群（Kafka）                  │ →  正常情况
       │                                     │
       └─────────────────────────────────────┘
                         ↓ 故障切换
       ┌─────────────────────────────────────┐
       │                                     │
       │   备MQ集群（RocketMQ/Pulsar）        │ →  降级方案
       │                                     │
       └─────────────────────────────────────┘
```

### 代码实现

```java
@Service
public class MessageSender {
    
    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;
    
    @Autowired
    private RocketMQTemplate rocketMQTemplate;
    
    @Autowired
    private MQHealthChecker healthChecker;
    
    public void send(String topic, String message) {
        if (healthChecker.isKafkaHealthy()) {
            kafkaTemplate.send(topic, message);
        } else if (healthChecker.isRocketMQHealthy()) {
            rocketMQTemplate.convertAndSend(topic, message);
            log.warn("Kafka不可用，降级到RocketMQ");
        } else {
            // 两个都不可用，写本地消息表
            saveToLocalMessage(topic, message);
            log.error("所有MQ不可用，写入本地消息表");
        }
    }
}
```

---

## MQ恢复后的数据处理

### 消息去重

MQ恢复后，可能产生重复消息，消费者必须做幂等处理：

```java
@KafkaListener(topics = "order-created")
public void consume(ConsumerRecord<String, String> record) {
    String orderId = record.key();
    
    // 幂等检查
    if (processedOrderIds.contains(orderId)) {
        log.warn("重复消息，跳过: {}", orderId);
        return;
    }
    
    // 处理消息
    doProcess(record.value());
    
    // 标记已处理
    processedOrderIds.add(orderId);
}
```

### 数据补偿

降级期间产生的数据差异需要补偿：

```java
@Scheduled(cron = "0 0 2 * * ?")  // 每天凌晨2点
public void dataReconciliation() {
    // 1. 对比业务数据和MQ消息
    List<Order> missingOrders = findMissingOrders();
    
    // 2. 补发消息
    for (Order order : missingOrders) {
        kafkaTemplate.send("order-created", order.getOrderId(), 
                          JSON.toJSONString(order));
    }
}
```

---

## 面试答题框架

```
明确MQ作用：异步解耦/削峰填谷/数据同步

降级方案优先级：
1. 本地消息表 - 保证消息不丢
2. 降级为同步调用 - 简单直接
3. 本地缓存兜底 - 读操作适用
4. 备用MQ切换 - 大公司方案

恢复后处理：
- 消息去重（幂等）
- 数据补偿（定时对账）

监控告警：
- MQ健康检查
- 本地消息表积压告警
```

---

## 总结

| 方案 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 同步调用 | 调用量小 | 简单 | 耦合、性能差 |
| 本地消息表 | 必须不丢 | 可靠 | 实现复杂 |
| 本地缓存 | 读操作 | 快 | 数据不一致 |
| 备用MQ | 大厂 | 高可用 | 成本高 |
