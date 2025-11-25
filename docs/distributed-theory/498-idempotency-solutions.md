---
layout: default
title: "什么是幂等？如何解决幂等性问题？"
parent: 分布式理论
nav_order: 498
description: "深入解析幂等性概念、应用场景及常见解决方案，包括唯一ID、状态机、Token机制等实践方法"
date: 2025-11-20 15:24:28 +0800
---
## 一、核心概念

**幂等性（Idempotence）** 是指同一个操作执行一次和执行多次的效果完全相同，不会因为重复执行而产生副作用或不一致的结果。

在分布式系统中，由于网络超时、重试机制、消息队列重复消费等原因，同一个请求可能被执行多次，幂等性保证了系统的正确性和数据一致性。

### 典型场景

- **支付订单**：用户点击支付按钮多次，只扣款一次
- **消息队列消费**：消息重复投递时，业务逻辑只执行一次
- **API 重试**：网络超时导致客户端重试，服务端不重复处理
- **数据库操作**：UPDATE、DELETE 操作天然幂等，INSERT 需要特殊处理

---

## 二、原理与关键点

### 为什么需要幂等性？

1. **网络不可靠**：请求可能因超时重发，但第一次请求实际已成功
2. **消息队列重复消费**：Kafka、RabbitMQ 在某些模式下会重复投递消息
3. **用户重复操作**：前端防抖失效，用户快速点击提交按钮
4. **微服务重试**：Ribbon、Feign 等框架的自动重试机制

### 幂等与防重的区别

- **防重（去重）**：阻止重复请求的提交（如前端按钮置灰）
- **幂等**：允许重复请求，但保证结果一致（后端兜底保障）

---

## 三、常见解决方案

### 1. 唯一索引（数据库层面）

**原理**：利用数据库唯一索引约束，重复插入会抛出异常

```sql
CREATE TABLE `orders` (
  `id` BIGINT PRIMARY KEY,
  `order_no` VARCHAR(64) UNIQUE NOT NULL COMMENT '订单号-唯一索引',
  `user_id` BIGINT,
  `amount` DECIMAL(10,2),
  `status` TINYINT
) ENGINE=InnoDB;
```

```java
public void createOrder(String orderNo, Long userId, BigDecimal amount) {
    try {
        orderMapper.insert(new Order(orderNo, userId, amount));
    } catch (DuplicateKeyException e) {
        log.warn("订单已存在: {}", orderNo);
        // 查询并返回已有订单
        return orderMapper.selectByOrderNo(orderNo);
    }
}
```

**优点**：简单可靠，数据库层面强制约束  
**缺点**：依赖数据库性能，异常处理略显繁琐

---

### 2. 状态机 + 乐观锁

**原理**：通过状态流转和版本号控制，避免重复操作

```java
@Transactional
public boolean payOrder(Long orderId) {
    // 查询订单当前状态
    Order order = orderMapper.selectById(orderId);
    
    // 只有待支付状态才能执行支付
    if (order.getStatus() != OrderStatus.PENDING) {
        log.warn("订单状态不允许支付: {}", order.getStatus());
        return false;
    }
    
    // 乐观锁更新（WHERE version = #{oldVersion}）
    int updated = orderMapper.updateByVersion(
        orderId, 
        OrderStatus.PAID, 
        order.getVersion()
    );
    
    if (updated == 0) {
        throw new OptimisticLockException("订单状态已变更");
    }
    
    // 执行扣款等业务逻辑
    paymentService.deduct(order.getAmount());
    return true;
}
```

```sql
UPDATE orders 
SET status = 2, version = version + 1
WHERE id = #{orderId} 
  AND status = 1 
  AND version = #{oldVersion}
```

**优点**：业务语义清晰，适合有明确状态流转的场景  
**缺点**：需要设计合理的状态机

---

### 3. Token 机制（防重令牌）

**原理**：客户端先获取唯一 Token，提交时携带并校验，使用后立即删除

**流程**：
1. 客户端请求获取 Token（存入 Redis）
2. 客户端提交时携带 Token
3. 服务端验证并删除 Token（原子操作）
4. 若 Token 不存在，说明已处理过

```java
// 1. 获取 Token
public String generateToken(Long userId) {
    String token = UUID.randomUUID().toString();
    String key = "idempotent:token:" + userId + ":" + token;
    redisTemplate.opsForValue().set(key, "1", 5, TimeUnit.MINUTES);
    return token;
}

// 2. 提交时验证
@Transactional
public void submitOrder(OrderRequest request, String token) {
    String key = "idempotent:token:" + request.getUserId() + ":" + token;
    
    // Lua 脚本保证原子性删除
    Boolean deleted = redisTemplate.execute(
        new DefaultRedisScript<>(
            "if redis.call('get', KEYS[1]) then " +
            "  redis.call('del', KEYS[1]) " +
            "  return 1 " +
            "else " +
            "  return 0 " +
            "end",
            Boolean.class
        ),
        Collections.singletonList(key)
    );
    
    if (!deleted) {
        throw new IdempotentException("请勿重复提交");
    }
    
    // 执行业务逻辑
    orderService.create(request);
}
```

**优点**：通用性强，适合各种业务场景  
**缺点**：需要额外的 Token 获取接口，增加网络开销

---

### 4. 分布式锁

**原理**：使用 Redis 或 Zookeeper 实现分布式锁，同一时刻只允许一个请求执行

```java
public void processOrder(String orderNo) {
    String lockKey = "order:lock:" + orderNo;
    RLock lock = redissonClient.getLock(lockKey);
    
    try {
        // 尝试加锁，最多等待 0 秒，锁自动释放时间 10 秒
        boolean locked = lock.tryLock(0, 10, TimeUnit.SECONDS);
        if (!locked) {
            throw new BizException("订单处理中，请稍后再试");
        }
        
        // 检查订单是否已处理
        if (orderService.isProcessed(orderNo)) {
            return;
        }
        
        // 执行业务逻辑
        orderService.process(orderNo);
        
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
    } finally {
        lock.unlock();
    }
}
```

**优点**：强一致性保证  
**缺点**：性能开销大，锁粒度需要精细设计

---

### 5. 唯一请求 ID（全局去重表）

**原理**：客户端生成全局唯一请求 ID，服务端记录已处理的 ID

```java
@Transactional
public void handleRequest(String requestId, BizRequest request) {
    // 检查请求是否已处理
    if (requestRecordMapper.existsByRequestId(requestId)) {
        log.info("请求已处理: {}", requestId);
        return;
    }
    
    // 插入请求记录（唯一索引保证原子性）
    try {
        requestRecordMapper.insert(new RequestRecord(requestId));
    } catch (DuplicateKeyException e) {
        log.warn("并发重复请求: {}", requestId);
        return;
    }
    
    // 执行业务逻辑
    bizService.process(request);
}
```

**优点**：简单直观，易于审计和排查  
**缺点**：去重表数据量大，需要定期清理

---

## 四、性能优化与场景考量

### 1. 消息队列幂等

在 Kafka、RabbitMQ 消费端，推荐使用 **消息 ID + 去重表** 或 **业务主键去重**：

```java
@RabbitListener(queues = "order.queue")
public void consumeMessage(OrderMessage message) {
    String messageId = message.getMessageId();
    
    // 基于消息 ID 的幂等处理
    if (redisTemplate.opsForValue().setIfAbsent(
        "mq:consumed:" + messageId, "1", 1, TimeUnit.DAYS)) {
        
        orderService.process(message);
    } else {
        log.info("消息已消费: {}", messageId);
    }
}
```

### 2. 接口幂等注解

封装通用幂等注解，减少重复代码：

```java
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface Idempotent {
    String key() default ""; // SpEL 表达式
    long timeout() default 10; // 锁超时时间
}

// 使用示例
@Idempotent(key = "#orderNo")
public void createOrder(String orderNo, OrderDTO dto) {
    // 业务逻辑
}
```

### 3. 性能权衡

| 方案 | 性能 | 一致性 | 适用场景 |
|------|------|--------|----------|
| 唯一索引 | ⭐⭐⭐ | 强 | 插入操作 |
| 状态机 | ⭐⭐⭐⭐ | 强 | 有状态流转的业务 |
| Token | ⭐⭐⭐ | 强 | 表单提交 |
| 分布式锁 | ⭐⭐ | 强 | 高并发竞争场景 |
| 请求 ID | ⭐⭐⭐⭐ | 强 | 通用场景 |

---

## 五、答题总结

**幂等性** 是分布式系统中保证操作可重复执行而结果一致的关键特性。常见解决方案包括：

1. **数据库唯一索引**：适合插入操作
2. **状态机 + 乐观锁**：适合有明确状态流转的业务
3. **Token 机制**：适合表单提交等用户操作
4. **分布式锁**：适合需要严格串行化的场景
5. **唯一请求 ID**：通用方案，易于实现

**实践建议**：

- 优先使用业务主键（如订单号）作为幂等依据
- 结合 Redis 缓存提升去重查询性能
- 对于消息队列，使用消息 ID 或业务唯一键去重
- 设计时考虑**先判断再执行**的原则，减少无效操作

在面试中，展示对不同方案的理解和选型能力，结合实际业务场景分析，更能体现技术深度。
