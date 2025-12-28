---
layout: post
title: "iPhone秒杀场景如何设计？"
date: 2025-12-28
categories: [大厂项目场景实战, 高并发实战]
tags: [秒杀, 高并发, Redis, 限流, 库存扣减]
description: "通过iPhone秒杀场景讲解秒杀系统设计，包括流量控制、库存预扣、防超卖等核心技术。"
---

# iPhone秒杀场景如何设计？

## 业务场景

公司年会抽奖活动，100台iPhone秒杀，预计10万人参与，秒杀开始瞬间QPS达10万+。

**核心挑战**：
- 瞬时流量极高
- 库存有限（100台）
- 绝对不能超卖
- 用户体验要好

---

## 秒杀系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      秒杀架构                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   用户 → CDN静态化 → 网关限流 → 秒杀服务 → Redis预扣     │
│                                      ↓                  │
│                               MQ → 订单服务 → 数据库     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 核心策略

1. **流量过滤**：层层削减，只放行有效请求
2. **Redis预扣**：库存操作不落库
3. **异步下单**：MQ削峰

---

## 策略一：层层限流

### 前端限流

```javascript
// 按钮置灰，禁止重复点击
let clicked = false;
function seckill() {
    if (clicked) return;
    clicked = true;
    setTimeout(() => clicked = false, 3000);
    // 发起请求
}
```

### 网关限流

```yaml
# Sentinel网关限流
spring:
  cloud:
    sentinel:
      filter:
        url-patterns: /seckill/**
      datasource:
        flow:
          nacos:
            rule-type: gw-flow
            data-id: seckill-flow-rules
```

```json
[{
  "resource": "/seckill/buy",
  "count": 1000,
  "intervalSec": 1,
  "burst": 0,
  "grade": 1
}]
```

### 应用层限流

```java
// 用户级别限流：每人每秒最多1次
@SentinelResource(
    value = "seckillBuy",
    blockHandler = "seckillBlockHandler"
)
public Result buy(Long userId, Long itemId) {
    // ...
}
```

---

## 策略二：Redis库存预扣

### 为什么不直接操作数据库？

数据库扛不住10万QPS的库存扣减，且存在超卖风险。

### Redis预扣方案

```java
@Service
public class SeckillService {
    
    private static final String STOCK_KEY = "seckill:stock:";
    private static final String BOUGHT_KEY = "seckill:bought:";
    
    public Result seckill(Long userId, Long itemId) {
        String stockKey = STOCK_KEY + itemId;
        String boughtKey = BOUGHT_KEY + itemId;
        
        // 1. 检查是否已购买（防止重复购买）
        Boolean bought = redis.opsForSet().isMember(boughtKey, userId.toString());
        if (Boolean.TRUE.equals(bought)) {
            return Result.fail("您已参与过秒杀");
        }
        
        // 2. Lua脚本原子扣减库存
        String script = """
            local stock = redis.call('GET', KEYS[1])
            if stock == false or tonumber(stock) <= 0 then
                return -1
            end
            local bought = redis.call('SISMEMBER', KEYS[2], ARGV[1])
            if bought == 1 then
                return -2
            end
            redis.call('DECR', KEYS[1])
            redis.call('SADD', KEYS[2], ARGV[1])
            return 1
            """;
        
        Long result = redis.execute(new DefaultRedisScript<>(script, Long.class),
            List.of(stockKey, boughtKey), userId.toString());
        
        if (result == -1) {
            return Result.fail("商品已售罄");
        }
        if (result == -2) {
            return Result.fail("您已参与过秒杀");
        }
        
        // 3. 发送MQ，异步创建订单
        kafkaTemplate.send("seckill-order", JSON.toJSONString(
            new SeckillOrder(userId, itemId)));
        
        return Result.success("秒杀成功，正在创建订单");
    }
}
```

### 库存预热

```java
// 秒杀开始前预热库存到Redis
@Scheduled(cron = "0 55 11 * * ?")  // 12点秒杀，11:55预热
public void warmUpStock() {
    List<SeckillItem> items = seckillItemMapper.findToday();
    for (SeckillItem item : items) {
        redis.opsForValue().set(
            STOCK_KEY + item.getId(), 
            String.valueOf(item.getStock())
        );
    }
}
```

---

## 策略三：异步创建订单

```java
@KafkaListener(topics = "seckill-order")
public void createOrder(String message) {
    SeckillOrder order = JSON.parseObject(message, SeckillOrder.class);
    
    try {
        // 1. 创建订单
        Order orderEntity = orderService.create(order);
        
        // 2. 扣减数据库库存（兜底）
        int affected = stockMapper.deduct(order.getItemId(), 1);
        if (affected == 0) {
            // 库存不足，回滚Redis
            compensate(order);
            return;
        }
        
        // 3. 通知用户
        messageService.sendSeckillSuccess(order.getUserId(), orderEntity);
        
    } catch (Exception e) {
        // 异常回滚
        compensate(order);
    }
}

private void compensate(SeckillOrder order) {
    redis.opsForValue().increment(STOCK_KEY + order.getItemId());
    redis.opsForSet().remove(BOUGHT_KEY + order.getItemId(), 
                             order.getUserId().toString());
    messageService.sendSeckillFailed(order.getUserId(), "系统异常");
}
```

---

## 策略四：防刷防作弊

### 隐藏秒杀入口

```java
// 秒杀开始前，接口不暴露
@GetMapping("/seckill/url")
public Result getSeckillUrl(Long itemId) {
    SeckillItem item = seckillItemMapper.findById(itemId);
    
    if (LocalDateTime.now().isBefore(item.getStartTime())) {
        return Result.fail("秒杀尚未开始");
    }
    
    // 返回带Token的秒杀链接
    String token = generateToken(itemId);
    return Result.success("/seckill/buy?token=" + token);
}
```

### 验证码

```java
// 增加验证码，分散请求
@PostMapping("/seckill/buy")
public Result buy(@RequestParam String captcha, 
                  @RequestParam Long itemId,
                  @RequestParam Long userId) {
    if (!captchaService.verify(userId, captcha)) {
        return Result.fail("验证码错误");
    }
    // ...
}
```

### 黑名单

```java
// 风控拦截
if (riskService.isBlacklist(userId)) {
    return Result.fail("账号异常");
}
```

---

## 策略五：降级兜底

```java
// 熔断降级
@SentinelResource(
    value = "seckillBuy",
    fallback = "seckillFallback"
)
public Result seckill(Long userId, Long itemId) {
    // ...
}

public Result seckillFallback(Long userId, Long itemId, Throwable t) {
    return Result.fail("系统繁忙，请稍后重试");
}
```

---

## 完整流程图

```
用户点击秒杀
    │
    ├── 前端：按钮防重复
    │
    ├── 网关：限流1000 QPS
    │
    ├── 应用：用户级限流
    │
    ├── 风控：黑名单检查
    │
    ├── Redis：Lua脚本原子扣库存
    │       ├── 库存不足 → 返回"已售罄"
    │       ├── 已购买 → 返回"已参与"
    │       └── 成功 → 继续
    │
    ├── MQ：异步下单
    │
    └── 返回"秒杀成功，创建订单中"
```

---

## 面试答题框架

```
核心挑战：瞬时10万QPS、100库存、不能超卖

解决方案：
1. 层层限流：前端→网关→应用
2. Redis预扣：Lua脚本原子操作
3. 异步下单：MQ削峰
4. 防刷措施：隐藏入口、验证码、黑名单

技术细节：
- Lua保证原子性
- Set记录已购用户
- 库存预热到Redis
- 失败补偿机制
```

---

## 总结

| 层级 | 策略 | 作用 |
|------|------|------|
| 前端 | 按钮防重 | 减少无效请求 |
| 网关 | 限流 | 保护后端 |
| 应用 | 风控+限流 | 过滤恶意请求 |
| Redis | Lua原子扣减 | 防超卖 |
| MQ | 异步下单 | 削峰 |
