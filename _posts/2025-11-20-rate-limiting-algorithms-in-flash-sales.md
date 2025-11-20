---
layout: post
title: "秒杀场景中常用的限流算法有哪些？"
date: 2025-11-20 15:51:36 +0800
categories: [分布式系统, 高并发]
tags: [限流, 秒杀, 算法, 高并发, 分布式]
description: "深入解析秒杀场景中常用的限流算法，包括固定窗口、滑动窗口、漏桶、令牌桶等算法的原理、实现及适用场景"
---

## 核心概念

限流（Rate Limiting）是高并发系统中保护后端服务的重要手段，通过控制请求速率防止系统过载。在秒杀场景中，限流尤为关键，因为瞬时流量可能是平时的数百倍甚至数千倍。

常见的限流算法主要有以下四种：
- **固定窗口计数器**（Fixed Window Counter）
- **滑动窗口计数器**（Sliding Window Counter）
- **漏桶算法**（Leaky Bucket）
- **令牌桶算法**（Token Bucket）

---

## 各算法原理及实现

### 1. 固定窗口计数器

**原理**：将时间划分为固定的窗口（如 1 秒），每个窗口内维护一个计数器，请求到来时计数器 +1，超过阈值则拒绝。

**优点**：实现简单，内存占用小  
**缺点**：存在 **临界问题**，窗口边界可能出现 2 倍流量（如 0.9s 和 1.1s 各来 100 个请求，实际 200ms 内通过 200 个）

```java
public class FixedWindowRateLimiter {
    private final int limit;
    private final long windowSize;
    private AtomicInteger counter = new AtomicInteger(0);
    private long windowStart = System.currentTimeMillis();

    public FixedWindowRateLimiter(int limit, long windowSizeMs) {
        this.limit = limit;
        this.windowSize = windowSizeMs;
    }

    public synchronized boolean tryAcquire() {
        long now = System.currentTimeMillis();
        // 判断是否进入新窗口
        if (now - windowStart >= windowSize) {
            counter.set(0);
            windowStart = now;
        }
        
        if (counter.get() < limit) {
            counter.incrementAndGet();
            return true;
        }
        return false;
    }
}
```

---

### 2. 滑动窗口计数器

**原理**：将固定窗口细分为多个小窗口（如 1 秒分为 10 个 100ms 的格子），统计滑动时间范围内的总请求数。

**优点**：解决了固定窗口的临界问题，流量更平滑  
**缺点**：内存占用稍大（需存储多个格子的计数）

```java
public class SlidingWindowRateLimiter {
    private final int limit;
    private final long windowSize;
    private final int slotCount;
    private final long slotSize;
    private final AtomicInteger[] slots;
    private long startTime = System.currentTimeMillis();

    public SlidingWindowRateLimiter(int limit, long windowSizeMs, int slotCount) {
        this.limit = limit;
        this.windowSize = windowSizeMs;
        this.slotCount = slotCount;
        this.slotSize = windowSizeMs / slotCount;
        this.slots = new AtomicInteger[slotCount];
        for (int i = 0; i < slotCount; i++) {
            slots[i] = new AtomicInteger(0);
        }
    }

    public synchronized boolean tryAcquire() {
        long now = System.currentTimeMillis();
        int currentSlot = (int) ((now / slotSize) % slotCount);
        
        // 清理过期的格子
        long slideTime = now - windowSize;
        for (int i = 0; i < slotCount; i++) {
            long slotTime = startTime + i * slotSize;
            if (slotTime < slideTime) {
                slots[i].set(0);
            }
        }
        
        // 计算当前窗口内总请求数
        int total = 0;
        for (AtomicInteger slot : slots) {
            total += slot.get();
        }
        
        if (total < limit) {
            slots[currentSlot].incrementAndGet();
            return true;
        }
        return false;
    }
}
```

---

### 3. 漏桶算法

**原理**：请求像水滴进入漏桶，以恒定速率流出，桶满则溢出（拒绝请求）。

**优点**：强制流量以恒定速率处理，流量整形效果好  
**缺点**：无法应对突发流量，响应速度不灵活

```java
public class LeakyBucketRateLimiter {
    private final int capacity;      // 桶容量
    private final int leakRate;      // 漏出速率（个/秒）
    private int water;               // 当前水量
    private long lastLeakTime;

    public LeakyBucketRateLimiter(int capacity, int leakRate) {
        this.capacity = capacity;
        this.leakRate = leakRate;
        this.water = 0;
        this.lastLeakTime = System.currentTimeMillis();
    }

    public synchronized boolean tryAcquire() {
        long now = System.currentTimeMillis();
        
        // 先漏水
        long leaked = (now - lastLeakTime) * leakRate / 1000;
        water = Math.max(0, (int) (water - leaked));
        lastLeakTime = now;
        
        // 判断是否能加水
        if (water < capacity) {
            water++;
            return true;
        }
        return false;
    }
}
```

---

### 4. 令牌桶算法（最常用）

**原理**：系统以恒定速率向桶中放入令牌，请求到来时先获取令牌，有令牌则通过，无令牌则拒绝或等待。桶有最大容量。

**优点**：**可应对突发流量**（桶中积累的令牌可一次性消费），同时限制平均速率  
**缺点**：实现略复杂

```java
public class TokenBucketRateLimiter {
    private final int capacity;      // 桶容量
    private final int refillRate;    // 令牌生成速率（个/秒）
    private int tokens;
    private long lastRefillTime;

    public TokenBucketRateLimiter(int capacity, int refillRate) {
        this.capacity = capacity;
        this.refillRate = refillRate;
        this.tokens = capacity;
        this.lastRefillTime = System.currentTimeMillis();
    }

    public synchronized boolean tryAcquire() {
        refillTokens();
        
        if (tokens > 0) {
            tokens--;
            return true;
        }
        return false;
    }

    private void refillTokens() {
        long now = System.currentTimeMillis();
        long elapsedTime = now - lastRefillTime;
        int tokensToAdd = (int) (elapsedTime * refillRate / 1000);
        
        if (tokensToAdd > 0) {
            tokens = Math.min(capacity, tokens + tokensToAdd);
            lastRefillTime = now;
        }
    }
}
```

---

## 分布式场景考量

### 单机 vs 分布式

**单机限流**：使用上述本地算法即可，Guava 的 `RateLimiter` 基于令牌桶实现。

**分布式限流**：需要共享限流状态，常用方案：

#### 1. Redis + Lua 实现

```java
// 令牌桶的 Redis + Lua 实现
public class RedisTokenBucketRateLimiter {
    private final RedisTemplate<String, String> redisTemplate;
    private final String key;
    private final int capacity;
    private final int refillRate;

    // Lua 脚本保证原子性
    private static final String LUA_SCRIPT = 
        "local key = KEYS[1]\n" +
        "local capacity = tonumber(ARGV[1])\n" +
        "local rate = tonumber(ARGV[2])\n" +
        "local now = tonumber(ARGV[3])\n" +
        "local tokens = tonumber(redis.call('hget', key, 'tokens') or capacity)\n" +
        "local last_time = tonumber(redis.call('hget', key, 'last_time') or now)\n" +
        "local elapsed = now - last_time\n" +
        "local new_tokens = math.min(capacity, tokens + elapsed * rate / 1000)\n" +
        "if new_tokens >= 1 then\n" +
        "    redis.call('hset', key, 'tokens', new_tokens - 1)\n" +
        "    redis.call('hset', key, 'last_time', now)\n" +
        "    redis.call('expire', key, 60)\n" +
        "    return 1\n" +
        "else\n" +
        "    return 0\n" +
        "end";

    public boolean tryAcquire() {
        Long result = redisTemplate.execute(
            new DefaultRedisScript<>(LUA_SCRIPT, Long.class),
            Collections.singletonList(key),
            String.valueOf(capacity),
            String.valueOf(refillRate),
            String.valueOf(System.currentTimeMillis())
        );
        return result != null && result == 1;
    }
}
```

#### 2. 使用现成组件

- **Sentinel**：阿里开源，支持流控、降级、热点参数限流
- **Resilience4j**：轻量级，支持限流、熔断、重试
- **Spring Cloud Gateway**：网关层限流，基于 Redis + Lua

---

## 性能优化建议

1. **网关层限流优先**：尽早拦截无效请求，减轻后端压力
2. **多级限流**：网关 + 应用层 + 数据库层，层层防护
3. **热点参数限流**：针对热门商品单独限流（Sentinel 支持）
4. **限流 + 降级**：超限后返回友好提示或引导到排队页面
5. **预热机制**：秒杀前逐步提升限流阈值，避免冷启动

---

## 面试答题总结

**核心考点**：
1. 四种算法的原理差异（重点是令牌桶 vs 漏桶）
2. 临界问题的理解（固定窗口的缺陷）
3. 分布式场景下 Redis + Lua 的实现思路
4. 实际项目中的限流方案选型（如 Sentinel）

**回答框架**：
- 先说明限流目的（保护系统）
- 列举四种算法并对比（令牌桶最常用）
- 说明分布式场景需要 Redis 共享状态
- 补充实际项目经验（如用过 Sentinel 或网关限流）
