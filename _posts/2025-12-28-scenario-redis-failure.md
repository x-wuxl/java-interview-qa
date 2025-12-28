---
layout: post
title: "Redis挂了，你要如何处理应对？"
date: 2025-12-28
categories: [大厂项目场景实战, 缓存故障处理]
tags: [Redis, 高可用, 降级, 缓存, 容灾]
description: "讲解Redis故障的应对方案，包括本地缓存降级、熔断保护、预热恢复等策略。"
---

# Redis挂了，你要如何处理应对？

## 面试场景

面试官："如果你项目中的Redis挂了，整个系统会怎么样？你会怎么处理？"

这道题考察**缓存故障处理能力**。回答需要涵盖：
1. Redis挂了会有什么影响
2. 如何降级
3. 如何恢复

---

## Redis在系统中的角色

首先分析Redis在系统中承担什么职责：

| 场景 | 影响 | 严重程度 |
|------|------|----------|
| 缓存 | 请求直接打到DB | 🔴 高 |
| Session存储 | 用户登录失效 | 🔴 高 |
| 分布式锁 | 并发控制失效 | 🔴 高 |
| 计数器/限流 | 限流失效 | 🟡 中 |
| 消息队列 | 消息丢失 | 🟡 中 |

---

## 故障场景分析

### 场景一：Redis完全不可用

所有Redis节点宕机，无法连接。

```
用户请求 → 应用 → Redis（超时）→ ???
                      ↓
              可能导致：
              1. 请求超时
              2. 线程池耗尽
              3. 级联故障
```

### 场景二：Redis响应变慢

Redis未宕机，但响应延迟很高（如从5ms变成500ms）。

**危害**：比完全宕机更危险，会慢慢拖垮系统。

---

## 应对方案

### 方案一：本地缓存降级

当Redis不可用时，降级到本地缓存。

```java
@Service
public class ProductService {
    
    @Autowired
    private Cache<Long, Product> localCache;  // Caffeine
    
    @Autowired
    private RedisTemplate<String, Product> redisTemplate;
    
    @Autowired
    private CircuitBreaker redisCircuitBreaker;
    
    public Product getProduct(Long productId) {
        // L1: 本地缓存（始终先查）
        Product product = localCache.getIfPresent(productId);
        if (product != null) {
            return product;
        }
        
        // L2: Redis（带熔断保护）
        if (redisCircuitBreaker.allowRequest()) {
            try {
                product = redisTemplate.opsForValue().get("product:" + productId);
                if (product != null) {
                    localCache.put(productId, product);
                    redisCircuitBreaker.recordSuccess();
                    return product;
                }
            } catch (Exception e) {
                redisCircuitBreaker.recordFailure();
                log.warn("Redis访问失败，降级到DB", e);
            }
        }
        
        // L3: 数据库
        product = productMapper.findById(productId);
        if (product != null) {
            localCache.put(productId, product);
            // 注意：Redis故障期间不写入Redis
        }
        return product;
    }
}
```

### 本地缓存配置

```java
@Bean
public Cache<Long, Product> productLocalCache() {
    return Caffeine.newBuilder()
        .maximumSize(10000)           // 最多1万条
        .expireAfterWrite(5, TimeUnit.MINUTES)  // 5分钟过期
        .build();
}
```

---

### 方案二：熔断保护

防止Redis故障导致线程池耗尽。

```java
// 使用Sentinel实现熔断
@SentinelResource(
    value = "getFromRedis",
    fallback = "getFromRedisFallback",
    blockHandler = "getFromRedisBlockHandler"
)
public Product getFromRedis(Long productId) {
    return redisTemplate.opsForValue().get("product:" + productId);
}

// 降级逻辑
public Product getFromRedisFallback(Long productId, Throwable t) {
    log.warn("Redis熔断，降级处理");
    return productMapper.findById(productId);
}
```

### 熔断配置

```yaml
# Sentinel规则
[
  {
    "resource": "getFromRedis",
    "grade": 1,           # 1=异常数, 0=慢调用比例
    "count": 5,           # 异常数阈值
    "timeWindow": 10,     # 熔断时长(秒)
    "statIntervalMs": 10000  # 统计窗口
  }
]
```

---

### 方案三：超时设置

避免Redis慢响应拖垮系统。

```java
@Bean
public LettuceConnectionFactory redisConnectionFactory() {
    LettuceClientConfiguration clientConfig = LettuceClientConfiguration.builder()
        .commandTimeout(Duration.ofMillis(200))  // 命令超时200ms
        .shutdownTimeout(Duration.ofMillis(100))
        .build();
    
    return new LettuceConnectionFactory(redisConfig(), clientConfig);
}
```

### 连接池配置

```yaml
spring:
  redis:
    lettuce:
      pool:
        max-active: 50
        max-idle: 20
        min-idle: 5
        max-wait: 100ms  # 获取连接超时
```

---

### 方案四：分布式锁降级

Redis挂了，分布式锁失效，如何处理？

```java
public class DistributedLockService {
    
    @Autowired
    private RedissonClient redisson;
    
    @Autowired
    private RateLimiter localRateLimiter;  // 本地限流
    
    public boolean tryLock(String key, long timeout, TimeUnit unit) {
        try {
            RLock lock = redisson.getLock(key);
            return lock.tryLock(timeout, unit);
        } catch (Exception e) {
            log.warn("Redis分布式锁获取失败，降级为本地限流");
            // 降级方案1: 本地限流（保证不超卖）
            return localRateLimiter.tryAcquire();
        }
    }
}
```

**更完善的方案**：
- 备用数据库锁（ZooKeeper、MySQL）
- 接受短时间内的部分超卖，事后补偿

---

### 方案五：Session降级

```java
@Component
public class SessionManager {
    
    @Autowired
    private RedisTemplate<String, UserSession> redisTemplate;
    
    // 本地Session缓存（降级用）
    private Cache<String, UserSession> localSessionCache = Caffeine.newBuilder()
        .maximumSize(50000)
        .expireAfterWrite(30, TimeUnit.MINUTES)
        .build();
    
    public UserSession getSession(String token) {
        // 优先Redis
        try {
            UserSession session = redisTemplate.opsForValue().get("session:" + token);
            if (session != null) {
                localSessionCache.put(token, session);  // 同步到本地
                return session;
            }
        } catch (Exception e) {
            log.warn("Redis不可用，使用本地Session");
        }
        
        // 降级到本地缓存
        return localSessionCache.getIfPresent(token);
    }
}
```

---

## 恢复后的处理

### 1. 缓存预热

Redis恢复后，需要预热，避免冷启动导致DB压力过大。

```java
@Component
public class CacheWarmer {
    
    @EventListener(ApplicationReadyEvent.class)
    public void warmUpCache() {
        // 1. 热点商品预热
        List<Long> hotProductIds = getHotProductIds();
        for (Long id : hotProductIds) {
            Product product = productMapper.findById(id);
            redisTemplate.opsForValue().set("product:" + id, product);
        }
        
        // 2. 控制预热速度，避免瞬间压力
        Thread.sleep(10);  // 每条休息10ms
    }
}
```

### 2. 流量灰度

```
恢复后流量控制：
1. 先放10%流量到Redis
2. 观察Redis负载，无问题后逐步放量
3. 完全切换后关闭降级开关
```

### 3. 数据一致性修复

降级期间可能产生数据不一致：

```java
@Scheduled(cron = "0 0 3 * * ?")  // 每天凌晨3点
public void syncCacheWithDB() {
    // 全量对比DB和Redis数据
    // 发现不一致则以DB为准刷新Redis
}
```

---

## 监控告警

```yaml
# Redis监控指标
- redis_connected_clients  # 连接数
- redis_memory_used_bytes  # 内存使用
- redis_ops_per_sec       # OPS
- redis_slow_log          # 慢查询

# 告警规则
- alert: RedisDown
  expr: redis_up == 0
  for: 30s
  labels:
    severity: P0
    
- alert: RedisHighLatency
  expr: redis_commands_duration_seconds_sum > 0.1
  for: 1m
  labels:
    severity: P1
```

---

## 面试答题框架

```
影响分析：
- 缓存失效：DB压力剧增
- Session失效：用户掉线
- 分布式锁失效：并发问题

应对方案：
1. 本地缓存降级（Caffeine兜底）
2. 熔断保护（Sentinel/Hystrix）
3. 超时设置（避免线程阻塞）
4. 分布式锁降级（本地限流/备用锁）

恢复处理：
1. 缓存预热
2. 流量灰度
3. 数据一致性修复

预防措施：
- Redis集群/哨兵高可用
- 完善监控告警
```

---

## 总结

| 场景 | 降级方案 | 注意事项 |
|------|----------|----------|
| 缓存 | 本地缓存 | 容量限制、过期时间 |
| Session | 本地缓存 | 多实例数据不同步 |
| 分布式锁 | 本地限流 | 可能短时超卖 |
| 限流 | 本地限流 | 精度下降 |
