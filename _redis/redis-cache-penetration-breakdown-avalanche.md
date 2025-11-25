---
title: "Redis 7 缓存穿透、缓存击穿、缓存雪崩问题"
date: 2025-11-08
description: "深入解析Redis缓存三大经典问题：缓存穿透、缓存击穿、缓存雪崩的原理、危害及解决方案"
author: "wuxl"
categories: [中间件]
tags: [Redis, 缓存, 高可用, 性能优化]
nav_order: 429
parent: Redis
---
## 问题

Redis 7 缓存穿透，缓存击穿，缓存雪崩问题

## 答案

### 一、核心概念

这三个问题是Redis缓存架构中最常见的高并发场景下的故障模式，都会导致大量请求直接打到数据库，造成数据库压力剧增甚至宕机。

| 问题类型 | 核心特征 | 典型场景 |
|---------|---------|---------|
| **缓存穿透** | 查询不存在的数据 | 恶意攻击、业务漏洞 |
| **缓存击穿** | 热点key突然失效 | 秒杀、热点新闻 |
| **缓存雪崩** | 大量key同时失效 | 缓存集中过期、Redis宕机 |

---

### 二、缓存穿透（Cache Penetration）

#### 2.1 问题原理

查询一个**缓存和数据库中都不存在**的数据，每次请求都会穿透缓存直达数据库。

```
请求 → Redis(未命中) → DB(查无数据) → 返回空
```

#### 2.2 危害

- 恶意攻击者可以构造大量不存在的key，绕过缓存直接打垮数据库
- 缓存失去保护作用

#### 2.3 解决方案

**方案1：布隆过滤器（Bloom Filter）**

```java
@Component
public class BloomFilterCache {

    private final RedissonClient redissonClient;

    // 初始化布隆过滤器
    public RBloomFilter<String> initBloomFilter() {
        RBloomFilter<String> bloomFilter = redissonClient.getBloomFilter("user:bloom");
        // 预期元素数量100万，误判率1%
        bloomFilter.tryInit(1000000L, 0.01);

        // 将所有有效key加载到布隆过滤器
        List<String> validKeys = loadAllValidKeysFromDB();
        validKeys.forEach(bloomFilter::add);

        return bloomFilter;
    }

    public User getUser(String userId) {
        RBloomFilter<String> bloomFilter = redissonClient.getBloomFilter("user:bloom");

        // 先判断key是否可能存在
        if (!bloomFilter.contains(userId)) {
            return null; // 一定不存在，直接返回
        }

        // 可能存在，继续查询缓存和数据库
        return queryFromCacheOrDB(userId);
    }
}
```

**方案2：缓存空值**

```java
public User getUserWithNullCache(String userId) {
    // 1. 查询Redis
    String cacheKey = "user:" + userId;
    String cached = redisTemplate.opsForValue().get(cacheKey);

    if (cached != null) {
        return "NULL".equals(cached) ? null : JSON.parseObject(cached, User.class);
    }

    // 2. 查询数据库
    User user = userMapper.selectById(userId);

    // 3. 缓存结果（包括空值）
    if (user == null) {
        // 缓存空值，设置较短过期时间（5分钟）
        redisTemplate.opsForValue().set(cacheKey, "NULL", 5, TimeUnit.MINUTES);
    } else {
        redisTemplate.opsForValue().set(cacheKey, JSON.toJSONString(user), 30, TimeUnit.MINUTES);
    }

    return user;
}
```

**方案3：参数校验**

```java
// 在接口层进行参数合法性校验
public User getUser(String userId) {
    // 校验参数格式
    if (!isValidUserId(userId)) {
        throw new IllegalArgumentException("Invalid userId format");
    }

    // 限制查询频率（结合限流）
    if (!rateLimiter.tryAcquire()) {
        throw new TooManyRequestsException();
    }

    return queryUser(userId);
}
```

---

### 三、缓存击穿（Cache Breakdown/Hotspot Invalid）

#### 3.1 问题原理

某个**热点key**在高并发访问时突然失效，导致大量请求同时穿透到数据库。

```
时刻T: 热点key过期
时刻T+1ms: 10000个并发请求 → Redis(未命中) → 10000个DB查询
```

#### 3.2 解决方案

**方案1：互斥锁（Mutex Lock）**

```java
public User getUserWithMutex(String userId) {
    String cacheKey = "user:" + userId;
    String lockKey = "lock:user:" + userId;

    // 1. 查询缓存
    User user = getFromCache(cacheKey);
    if (user != null) {
        return user;
    }

    // 2. 缓存未命中，尝试获取分布式锁
    RLock lock = redissonClient.getLock(lockKey);

    try {
        // 尝试加锁，最多等待10秒，锁自动释放时间30秒
        if (lock.tryLock(10, 30, TimeUnit.SECONDS)) {
            try {
                // 双重检查：再次查询缓存（可能其他线程已经加载）
                user = getFromCache(cacheKey);
                if (user != null) {
                    return user;
                }

                // 查询数据库
                user = userMapper.selectById(userId);

                // 写入缓存
                if (user != null) {
                    redisTemplate.opsForValue().set(cacheKey, user, 30, TimeUnit.MINUTES);
                }

                return user;
            } finally {
                lock.unlock();
            }
        } else {
            // 获取锁失败，等待后重试或返回降级数据
            Thread.sleep(50);
            return getFromCache(cacheKey);
        }
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new RuntimeException("Lock interrupted", e);
    }
}
```

**方案2：逻辑过期（热点数据永不过期）**

```java
@Data
public class CacheData<T> {
    private T data;
    private LocalDateTime expireTime; // 逻辑过期时间
}

public User getUserWithLogicalExpire(String userId) {
    String cacheKey = "user:" + userId;

    // 1. 查询缓存（物理上永不过期）
    CacheData<User> cacheData = redisTemplate.opsForValue().get(cacheKey);

    if (cacheData == null) {
        return null; // 缓存未命中
    }

    // 2. 判断逻辑过期时间
    if (cacheData.getExpireTime().isAfter(LocalDateTime.now())) {
        return cacheData.getData(); // 未过期，直接返回
    }

    // 3. 已过期，尝试获取锁进行重建
    String lockKey = "lock:rebuild:" + userId;
    if (tryLock(lockKey)) {
        // 开启独立线程异步重建缓存
        CACHE_REBUILD_EXECUTOR.submit(() -> {
            try {
                User user = userMapper.selectById(userId);
                CacheData<User> newData = new CacheData<>();
                newData.setData(user);
                newData.setExpireTime(LocalDateTime.now().plusMinutes(30));

                redisTemplate.opsForValue().set(cacheKey, newData);
            } finally {
                unlock(lockKey);
            }
        });
    }

    // 4. 返回旧数据（保证可用性）
    return cacheData.getData();
}
```

**方案3：热点数据预热**

```java
@Component
public class CacheWarmUp {

    @Scheduled(cron = "0 0 2 * * ?") // 每天凌晨2点执行
    public void warmUpHotKeys() {
        // 从数据库或日志分析系统获取热点key列表
        List<String> hotKeys = getHotKeysFromAnalytics();

        hotKeys.forEach(userId -> {
            User user = userMapper.selectById(userId);
            if (user != null) {
                String cacheKey = "user:" + userId;
                // 设置较长过期时间，并添加随机值防止同时过期
                int expireTime = 3600 + RandomUtils.nextInt(0, 300);
                redisTemplate.opsForValue().set(cacheKey, user, expireTime, TimeUnit.SECONDS);
            }
        });
    }
}
```

---

### 四、缓存雪崩（Cache Avalanche）

#### 4.1 问题原理

**大量缓存key在同一时间失效**，或者**Redis服务宕机**，导致所有请求瞬间打到数据库。

#### 4.2 解决方案

**方案1：过期时间打散**

```java
public void setCacheWithRandomExpire(String key, Object value, int baseExpireSeconds) {
    // 在基础过期时间上增加随机值（±20%）
    int randomRange = (int) (baseExpireSeconds * 0.2);
    int finalExpire = baseExpireSeconds + RandomUtils.nextInt(-randomRange, randomRange);

    redisTemplate.opsForValue().set(key, value, finalExpire, TimeUnit.SECONDS);
}

// 批量设置缓存
public void batchSetCache(Map<String, User> userMap) {
    userMap.forEach((userId, user) -> {
        String cacheKey = "user:" + userId;
        // 基础30分钟，实际过期时间在24-36分钟之间
        setCacheWithRandomExpire(cacheKey, user, 1800);
    });
}
```

**方案2：Redis高可用架构**

```yaml
# Redis Cluster 或 哨兵模式配置
spring:
  redis:
    cluster:
      nodes:
        - 192.168.1.101:6379
        - 192.168.1.102:6379
        - 192.168.1.103:6379
      max-redirects: 3
    lettuce:
      pool:
        max-active: 8
        max-idle: 8
        min-idle: 2
```

**方案3：多级缓存架构**

```java
@Component
public class MultiLevelCache {

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    // 本地缓存（Caffeine）
    private final Cache<String, User> localCache = Caffeine.newBuilder()
            .maximumSize(10000)
            .expireAfterWrite(5, TimeUnit.MINUTES)
            .build();

    public User getUser(String userId) {
        String cacheKey = "user:" + userId;

        // 1. 查询本地缓存
        User user = localCache.getIfPresent(cacheKey);
        if (user != null) {
            return user;
        }

        // 2. 查询Redis
        user = (User) redisTemplate.opsForValue().get(cacheKey);
        if (user != null) {
            localCache.put(cacheKey, user);
            return user;
        }

        // 3. 查询数据库
        user = userMapper.selectById(userId);
        if (user != null) {
            // 同时更新两级缓存
            localCache.put(cacheKey, user);
            redisTemplate.opsForValue().set(cacheKey, user, 30, TimeUnit.MINUTES);
        }

        return user;
    }
}
```

**方案4：限流降级**

```java
@RestController
public class UserController {

    @Autowired
    private RateLimiter rateLimiter;

    @GetMapping("/user/{id}")
    @SentinelResource(value = "getUser",
                      blockHandler = "handleBlock",
                      fallback = "handleFallback")
    public Result<User> getUser(@PathVariable String id) {
        // 限流保护
        if (!rateLimiter.tryAcquire()) {
            return Result.error("系统繁忙，请稍后重试");
        }

        User user = userService.getUser(id);
        return Result.success(user);
    }

    // 降级处理
    public Result<User> handleFallback(String id, Throwable ex) {
        // 返回默认数据或提示
        return Result.error("服务暂时不可用");
    }
}
```

---

### 五、Redis 7 新特性支持

Redis 7 提供了一些新特性来更好地应对这些问题：

1. **Client-side caching**：客户端缓存，减少网络往返
2. **Functions**：替代Lua脚本，更好的原子性操作支持
3. **ACL增强**：更细粒度的权限控制，防止恶意访问

```java
// Redis 7 客户端缓存示例（Lettuce 6.2+）
RedisClient client = RedisClient.create("redis://localhost:6379");
StatefulRedisConnection<String, String> connection = client.connect();

// 启用客户端缓存
connection.setClientName("cache-client");
CacheFrontend<String, String> frontend = ClientSideCaching.enable(
    CacheAccessor.forMap(new ConcurrentHashMap<>()),
    connection,
    TrackingArgs.Builder.enabled()
);
```

---

### 六、答题总结

面试时可以按照以下思路回答：

1. **先区分三个概念**：穿透（不存在的数据）、击穿（热点key失效）、雪崩（大量key失效）
2. **说明危害**：都会导致数据库压力剧增
3. **针对性方案**：
   - 穿透 → 布隆过滤器 + 缓存空值
   - 击穿 → 互斥锁 + 逻辑过期
   - 雪崩 → 过期时间打散 + 高可用 + 多级缓存
4. **补充**：结合限流降级、监控告警形成完整的高可用方案

**关键点**：这三个问题的本质都是**缓存失效导致数据库承压**，解决思路是**减少失效概率 + 控制并发量 + 提升系统容错能力**。
