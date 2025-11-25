---
title: "如何防止优惠券被重复刷取？"
date: 2025-11-20 15:56:03 +0800
categories: [分布式系统, 安全防护]
tags: [分布式锁, 幂等性, Redis, 优惠券系统, 防刷]
description: "系统讲解防止优惠券被重复刷取的多层防护方案，涵盖幂等性设计、分布式锁、令牌机制、风控策略及数据库约束等实战技术。"
nav_order: 609
parent: 架构设计与实战
---
## 一、核心概念

优惠券防刷是**分布式系统安全防护**的经典场景，核心考察点：

1. **幂等性设计**：同一请求多次执行，结果一致（防止重复领取）
2. **分布式锁**：并发环境下保证操作的原子性
3. **防刷策略**：识别并拦截恶意请求（频率限制、风控规则）
4. **数据一致性**：Redis 与 MySQL 的数据同步问题

## 二、技术难点分析

### 为什么会被重复刷取？

| 攻击场景 | 产生原因 | 示例 |
|---------|---------|------|
| **前端重复点击** | 用户快速点击"领取"按钮 | 按钮未置灰，1 秒内点击 10 次 |
| **接口重放攻击** | 抓包后重复发送请求 | Postman 循环发送领取请求 |
| **并发请求** | 多线程同时调用领取接口 | 脚本开 100 个线程并发领取 |
| **缓存击穿** | 缓存失效瞬间，大量请求打到数据库 | Redis 过期，1000 个请求同时查 DB |
| **分布式竞态条件** | 多实例同时判断"未领取" | 实例 A 和 B 同时读取余量为 1 |

## 三、多层防护方案架构

```
┌────────────────────────────────────────────┐
│ Layer 1: 前端防护（按钮防抖 + 验证码）    │
├────────────────────────────────────────────┤
│ Layer 2: 网关层（IP 限流 + 黑名单）       │
├────────────────────────────────────────────┤
│ Layer 3: 应用层（令牌桶 + 幂等性校验）    │
├────────────────────────────────────────────┤
│ Layer 4: 缓存层（Redis 锁 + Lua 脚本）    │
├────────────────────────────────────────────┤
│ Layer 5: 数据库层（唯一索引 + 乐观锁）    │
└────────────────────────────────────────────┘
```

## 四、核心技术方案

### 方案 1：幂等性设计（数据库唯一索引）

```sql
CREATE TABLE `user_coupon` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `coupon_id` BIGINT NOT NULL,
  `receive_time` DATETIME NOT NULL,
  UNIQUE KEY `uk_user_coupon` (`user_id`, `coupon_id`)
) ENGINE=InnoDB;
```

**Redis Set 前置校验**：

```java
public boolean receiveCoupon(Long userId, Long couponId) {
    String key = "coupon:received:" + couponId;
    
    // Redis Set 判断是否已领取
    Boolean isNew = redisTemplate.opsForSet()
        .add(key, String.valueOf(userId));
    
    if (Boolean.FALSE.equals(isNew)) {
        throw new BizException("您已领取过该优惠券");
    }
    
    return true;
}
```

### 方案 2：分布式锁（Redisson）

```java
public boolean receiveCoupon(Long userId, Long couponId) {
    String lockKey = "lock:coupon:" + couponId + ":" + userId;
    RLock lock = redissonClient.getLock(lockKey);
    
    try {
        if (lock.tryLock(5, 10, TimeUnit.SECONDS)) {
            // 1. 校验是否已领取
            if (checkReceived(userId, couponId)) {
                throw new BizException("已领取");
            }
            
            // 2. 扣减库存
            if (!deductStock(couponId)) {
                throw new BizException("已抢光");
            }
            
            // 3. 保存记录
            saveUserCoupon(userId, couponId);
            
            return true;
        }
    } finally {
        lock.unlock();
    }
}
```

### 方案 3：Redis Lua 脚本（原子操作）

```java
String luaScript = 
    "local stock = redis.call('get', KEYS[1]) " +
    "if tonumber(stock) <= 0 then return 0 end " +
    "local received = redis.call('sismember', KEYS[2], ARGV[1]) " +
    "if received == 1 then return -1 end " +
    "redis.call('decr', KEYS[1]) " +
    "redis.call('sadd', KEYS[2], ARGV[1]) " +
    "return 1";

Long result = redisTemplate.execute(
    new DefaultRedisScript<>(luaScript, Long.class),
    Arrays.asList("coupon:stock:" + couponId, "coupon:received:" + couponId),
    String.valueOf(userId)
);
// result: 1=成功, 0=库存不足, -1=已领取
```

### 方案 4：令牌机制（防重放）

```java
// 1. 生成令牌
@GetMapping("/coupon/token")
public String generateToken(@RequestParam Long couponId) {
    String token = UUID.randomUUID().toString();
    String key = "coupon:token:" + couponId + ":" + token;
    redisTemplate.opsForValue().set(key, "1", 5, TimeUnit.MINUTES);
    return token;
}

// 2. 领取时校验
@PostMapping("/coupon/receive")
public Result receiveCoupon(@RequestParam String token) {
    String key = "coupon:token:" + couponId + ":" + token;
    Long deleted = redisTemplate.delete(key);
    if (deleted == null || deleted == 0) {
        throw new BizException("令牌无效或已使用");
    }
    // 执行领取逻辑...
}
```

### 方案 5：风控策略

#### 频率限制

```java
public boolean preHandle(HttpServletRequest request) {
    String key = "rate:limit:coupon:" + userId;
    Long count = redisTemplate.opsForValue().increment(key);
    
    if (count == 1) {
        redisTemplate.expire(key, 1, TimeUnit.MINUTES);
    }
    
    if (count > 3) {
        throw new BizException("操作过于频繁");
    }
    return true;
}
```

#### 用户行为分析

| 风控维度 | 检测规则 | 处置措施 |
|---------|---------|---------|
| **IP 维度** | 单 IP 1 分钟超 20 次 | IP 拉黑 1 小时 |
| **设备维度** | 同设备 5+ 账号 | 设备拉黑 |
| **账号维度** | 新注册立即领取 | 需实名认证 |
| **时间维度** | 凌晨 3-5 点大量领取 | 加强验证码 |

## 五、完整实现流程

```java
@Transactional(rollbackFor = Exception.class)
public Result receiveCoupon(Long userId, Long couponId, String token) {
    
    // 1. 验证令牌
    validateToken(token, couponId);
    
    // 2. 风控检查
    riskControlService.checkRisk(userId, getIp(), getDeviceId());
    
    // 3. 幂等性校验（Redis Set）
    String receivedKey = "coupon:received:" + couponId;
    Boolean isNew = redisTemplate.opsForSet()
        .add(receivedKey, String.valueOf(userId));
    if (Boolean.FALSE.equals(isNew)) {
        throw new BizException("您已领取过该优惠券");
    }
    
    // 4. Redis Lua 扣减库存
    Long result = deductStockByLua(couponId, userId);
    if (result <= 0) {
        redisTemplate.opsForSet().remove(receivedKey, String.valueOf(userId));
        throw new BizException("优惠券已抢光");
    }
    
    // 5. 异步写入数据库
    asyncSaveUserCoupon(userId, couponId);
    
    return Result.success("领取成功");
}
```

## 六、性能优化

| 优化点 | 方案 | 效果 |
|-------|------|------|
| **缓存预热** | 活动前 10 分钟预加载库存到 Redis | 避免缓存穿透 |
| **分段库存** | 10000 库存分 100 段，减少锁竞争 | 并发提升 10 倍 |
| **异步化** | 领取记录异步写 DB，先返回成功 | RT 降低 70% |
| **CDN 加速** | 静态资源走 CDN | 加载速度提升 3 倍 |

## 七、常见问题应对

**Q1: Redis 与数据库数据不一致？**  
→ 定时对账 + MQ 异步同步 + 兜底任务

**Q2: 分布式锁失效？**  
→ Redisson 看门狗自动续期

**Q3: 如何应对突发流量？**  
→ 前端排队 + MQ 削峰 + 熔断降级

## 八、总结

**防刷核心**：多层防护 + 幂等性 + 分布式锁 + 风控

| 层级 | 技术方案 | 核心作用 |
|-----|---------|---------|
| **前端** | 按钮防抖 + 验证码 | 减少 40% 无效请求 |
| **网关** | IP 限流 + 黑名单 | 拦截恶意 IP |
| **应用** | 令牌 + 幂等性校验 | 防重放、防重复 |
| **缓存** | Redis 锁 + Lua 脚本 | 并发控制、原子扣减 |
| **数据库** | 唯一索引 + 乐观锁 | 最终兜底 |

**面试回答要点**：  
1. 先讲原理（幂等性、分布式锁）  
2. 再讲方案（Redis Lua、令牌机制）  
3. 补充风控（频率限制、行为分析）  
4. 量化成果（QPS 提升、错误率降低）
