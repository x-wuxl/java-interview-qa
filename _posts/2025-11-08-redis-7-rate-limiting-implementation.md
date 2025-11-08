---
layout: post
title: "Redis 7 实现限流"
date: 2025-11-08
description: "全面解析Redis 7限流实现方案，涵盖固定窗口、滑动窗口、令牌桶、漏桶四种算法，以及分布式场景下的多维度限流策略与性能优化"
author: "wuxl"
categories: [中间件]
tags: [Redis, 限流, 令牌桶, 滑动窗口, 分布式, Lua脚本]
---
# Redis 7 实现限流

## 核心概念

限流（Rate Limiting）是控制系统访问频率的重要手段，用于保护系统免受突发流量冲击。Redis 7 提供了多种限流算法实现：
- **固定窗口**：在固定时间窗口内限制请求数量
- **滑动窗口**：更平滑的流量控制，避免窗口边界突刺
- **令牌桶**：允许一定程度的突发流量
- **漏桶**：平滑输出，严格控制流量速率

## Redis 7 限流实现原理

### 1. 固定窗口算法

基于 Redis 的 `INCR` 和 `EXPIRE` 命令实现：

```java
@Component
public class FixedWindowRateLimiter {
  
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
  
    /**
     * 固定窗口限流
     * @param key 限流键
     * @param limit 限制次数
     * @param window 时间窗口（秒）
     * @return 是否允许通过
     */
    public boolean isAllowed(String key, int limit, int window) {
        String windowKey = key + ":" + (System.currentTimeMillis() / 1000 / window);
      
        return redisTemplate.execute((RedisCallback<Boolean>) connection -> {
            // 使用 Lua 脚本保证原子性
            String script = 
                "local current = redis.call('INCR', KEYS[1]) " +
                "if current == 1 then " +
                "    redis.call('EXPIRE', KEYS[1], ARGV[1]) " +
                "end " +
                "return current <= tonumber(ARGV[2])";
          
            Object result = connection.eval(
                script.getBytes(),
                ReturnType.BOOLEAN,
                1,
                windowKey.getBytes(),
                String.valueOf(window).getBytes(),
                String.valueOf(limit).getBytes()
            );
          
            return (Boolean) result;
        });
    }
}
```

### 2. 滑动窗口算法

基于 Redis 的 `ZSET` 数据结构实现：

```java
@Component
public class SlidingWindowRateLimiter {
  
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
  
    /**
     * 滑动窗口限流
     */
    public boolean isAllowed(String key, int limit, int window) {
        long now = System.currentTimeMillis();
        long windowStart = now - window * 1000L;
      
        return redisTemplate.execute((RedisCallback<Boolean>) connection -> {
            String script = 
                "local key = KEYS[1] " +
                "local now = tonumber(ARGV[1]) " +
                "local window = tonumber(ARGV[2]) " +
                "local limit = tonumber(ARGV[3]) " +
                "local windowStart = now - window * 1000 " +
              
                // 清理过期数据
                "redis.call('ZREMRANGEBYSCORE', key, 0, windowStart) " +
              
                // 获取当前窗口内的请求数
                "local current = redis.call('ZCARD', key) " +
                "if current < limit then " +
                "    redis.call('ZADD', key, now, now) " +
                "    redis.call('EXPIRE', key, window + 1) " +
                "    return true " +
                "else " +
                "    return false " +
                "end";
          
            Object result = connection.eval(
                script.getBytes(),
                ReturnType.BOOLEAN,
                1,
                key.getBytes(),
                String.valueOf(now).getBytes(),
                String.valueOf(window).getBytes(),
                String.valueOf(limit).getBytes()
            );
          
            return (Boolean) result;
        });
    }
}
```

### 3. 令牌桶算法

```java
@Component
public class TokenBucketRateLimiter {
  
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
  
    /**
     * 令牌桶限流
     * @param key 限流键
     * @param capacity 桶容量
     * @param refillRate 令牌补充速率（个/秒）
     * @param tokens 请求令牌数
     */
    public boolean isAllowed(String key, int capacity, double refillRate, int tokens) {
        long now = System.currentTimeMillis();
      
        return redisTemplate.execute((RedisCallback<Boolean>) connection -> {
            String script = 
                "local key = KEYS[1] " +
                "local capacity = tonumber(ARGV[1]) " +
                "local refillRate = tonumber(ARGV[2]) " +
                "local tokens = tonumber(ARGV[3]) " +
                "local now = tonumber(ARGV[4]) " +
              
                // 获取桶状态
                "local bucket = redis.call('HMGET', key, 'tokens', 'lastRefill') " +
                "local currentTokens = tonumber(bucket[1]) or capacity " +
                "local lastRefill = tonumber(bucket[2]) or now " +
              
                // 计算需要补充的令牌数
                "local timePassed = (now - lastRefill) / 1000 " +
                "local tokensToAdd = math.floor(timePassed * refillRate) " +
                "currentTokens = math.min(capacity, currentTokens + tokensToAdd) " +
              
                // 检查是否有足够令牌
                "if currentTokens >= tokens then " +
                "    currentTokens = currentTokens - tokens " +
                "    redis.call('HMSET', key, 'tokens', currentTokens, 'lastRefill', now) " +
                "    redis.call('EXPIRE', key, 3600) " +
                "    return true " +
                "else " +
                "    redis.call('HMSET', key, 'tokens', currentTokens, 'lastRefill', now) " +
                "    redis.call('EXPIRE', key, 3600) " +
                "    return false " +
                "end";
          
            Object result = connection.eval(
                script.getBytes(),
                ReturnType.BOOLEAN,
                1,
                key.getBytes(),
                String.valueOf(capacity).getBytes(),
                String.valueOf(refillRate).getBytes(),
                String.valueOf(tokens).getBytes(),
                String.valueOf(now).getBytes()
            );
          
            return (Boolean) result;
        });
    }
}
```

## 分布式场景应用

### 1. 多维度限流策略

```java
@Component
public class MultiDimensionRateLimiter {
  
    @Autowired
    private SlidingWindowRateLimiter slidingWindowLimiter;
  
    @Autowired
    private TokenBucketRateLimiter tokenBucketLimiter;
  
    /**
     * 多维度限流检查
     */
    public boolean checkRateLimit(String userId, String api, String ip) {
        // 用户维度限流：每分钟100次
        String userKey = "rate_limit:user:" + userId;
        if (!slidingWindowLimiter.isAllowed(userKey, 100, 60)) {
            return false;
        }
      
        // API维度限流：每秒1000次
        String apiKey = "rate_limit:api:" + api;
        if (!tokenBucketLimiter.isAllowed(apiKey, 1000, 1000.0, 1)) {
            return false;
        }
      
        // IP维度限流：每分钟50次
        String ipKey = "rate_limit:ip:" + ip;
        if (!slidingWindowLimiter.isAllowed(ipKey, 50, 60)) {
            return false;
        }
      
        return true;
    }
}
```

### 2. 限流拦截器实现

```java
@Component
public class RateLimitInterceptor implements HandlerInterceptor {
  
    @Autowired
    private MultiDimensionRateLimiter rateLimiter;
  
    @Override
    public boolean preHandle(HttpServletRequest request, 
                           HttpServletResponse response, 
                           Object handler) throws Exception {
      
        // 获取限流注解
        RateLimit rateLimit = getRateLimitAnnotation(handler);
        if (rateLimit == null) {
            return true;
        }
      
        // 构建限流键
        String key = buildRateLimitKey(request, rateLimit);
      
        // 执行限流检查
        boolean allowed = rateLimiter.checkRateLimit(
            getUserId(request),
            getApiPath(request),
            getClientIP(request)
        );
      
        if (!allowed) {
            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(
                "{\"code\":429,\"message\":\"请求过于频繁，请稍后重试\"}"
            );
            return false;
        }
      
        return true;
    }
  
    private String buildRateLimitKey(HttpServletRequest request, RateLimit rateLimit) {
        StringBuilder keyBuilder = new StringBuilder("rate_limit:");
      
        switch (rateLimit.type()) {
            case USER:
                keyBuilder.append("user:").append(getUserId(request));
                break;
            case IP:
                keyBuilder.append("ip:").append(getClientIP(request));
                break;
            case API:
                keyBuilder.append("api:").append(getApiPath(request));
                break;
        }
      
        return keyBuilder.toString();
    }
}
```

### 3. 限流注解定义

```java
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface RateLimit {
  
    /**
     * 限流类型
     */
    LimitType type() default LimitType.USER;
  
    /**
     * 限制次数
     */
    int limit() default 100;
  
    /**
     * 时间窗口（秒）
     */
    int window() default 60;
  
    /**
     * 限流算法
     */
    Algorithm algorithm() default Algorithm.SLIDING_WINDOW;
  
    enum LimitType {
        USER,    // 用户维度
        IP,      // IP维度
        API      // API维度
    }
  
    enum Algorithm {
        FIXED_WINDOW,     // 固定窗口
        SLIDING_WINDOW,   // 滑动窗口
        TOKEN_BUCKET      // 令牌桶
    }
}
```

## 性能优化与监控

### 1. 限流性能优化

```java
@Configuration
public class RateLimitConfig {
  
    /**
     * 限流结果缓存
     */
    @Bean
    public CacheManager rateLimitCacheManager() {
        CaffeineCacheManager cacheManager = new CaffeineCacheManager();
        cacheManager.setCaffeine(Caffeine.newBuilder()
            .maximumSize(10000)
            .expireAfterWrite(1, TimeUnit.SECONDS)
            .recordStats());
        return cacheManager;
    }
  
    /**
     * 异步限流统计
     */
    @Bean
    public RateLimitMetrics rateLimitMetrics() {
        return new RateLimitMetrics();
    }
}

@Component
public class RateLimitMetrics {
  
    private final Counter allowedCounter = Counter.builder("rate_limit_allowed")
        .description("Rate limit allowed requests")
        .register(Metrics.globalRegistry);
  
    private final Counter blockedCounter = Counter.builder("rate_limit_blocked")
        .description("Rate limit blocked requests")
        .register(Metrics.globalRegistry);
  
    public void recordAllowed(String dimension) {
        allowedCounter.increment(Tags.of("dimension", dimension));
    }
  
    public void recordBlocked(String dimension) {
        blockedCounter.increment(Tags.of("dimension", dimension));
    }
}
```

### 2. 分布式限流一致性

```java
@Component
public class DistributedRateLimiter {
  
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
  
    /**
     * 分布式限流，考虑多节点时钟偏差
     */
    public boolean isAllowedWithClockSkew(String key, int limit, int window) {
        return redisTemplate.execute((RedisCallback<Boolean>) connection -> {
            String script = 
                "local key = KEYS[1] " +
                "local limit = tonumber(ARGV[1]) " +
                "local window = tonumber(ARGV[2]) " +
                "local now = redis.call('TIME') " +
                "local timestamp = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000) " +
                "local windowStart = timestamp - window * 1000 " +
              
                // 使用 Redis 服务器时间，避免客户端时钟偏差
                "redis.call('ZREMRANGEBYSCORE', key, 0, windowStart) " +
                "local current = redis.call('ZCARD', key) " +
              
                "if current < limit then " +
                "    redis.call('ZADD', key, timestamp, timestamp .. ':' .. math.random()) " +
                "    redis.call('EXPIRE', key, window + 1) " +
                "    return true " +
                "else " +
                "    return false " +
                "end";
          
            Object result = connection.eval(
                script.getBytes(),
                ReturnType.BOOLEAN,
                1,
                key.getBytes(),
                String.valueOf(limit).getBytes(),
                String.valueOf(window).getBytes()
            );
          
            return (Boolean) result;
        });
    }
}
```

## 最佳实践总结

### 1. 算法选择原则
- **固定窗口**：实现简单，适合粗粒度限流
- **滑动窗口**：流量平滑，推荐用于用户限流
- **令牌桶**：允许突发，适合API网关场景
- **漏桶**：严格限速，适合下游保护

### 2. 限流维度设计
- **用户维度**：防止单用户滥用
- **IP维度**：防止恶意攻击
- **API维度**：保护核心接口
- **全局维度**：系统整体保护

### 3. 关键注意事项
- 使用 **Lua 脚本**保证操作原子性
- 考虑 **时钟偏差**问题，使用 Redis 服务器时间
- 设置合理的 **过期时间**，避免内存泄漏
- 实现 **降级策略**，限流失败时的处理逻辑
- 添加 **监控告警**，及时发现限流异常

Redis 7 的限流实现通过多种算法组合，能够满足不同场景的流量控制需求。合理的限流策略不仅能保护系统稳定性，还能提升用户体验和系统可用性。