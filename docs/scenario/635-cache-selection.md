---
layout: default
title: "Redis和Caffeine如何选择？"
parent: 大厂项目场景实战
nav_order: 635
description: "从一致性、性能、容量等维度对比Redis和Caffeine缓存选型"
date: 2025-12-28
---

# Redis和Caffeine如何选择？

## 面试场景

面试官："你的项目中缓存用的是Redis还是本地缓存？为什么？"

这道题考察对不同缓存方案的理解和选型能力。

---

## 核心对比

| 对比维度 | Redis | Caffeine |
|----------|-------|----------|
| 部署位置 | 远程服务 | JVM进程内 |
| 访问延迟 | 1-5ms | 纳秒级 |
| 容量上限 | 独立部署，可达TB | 受JVM堆限制 |
| 数据一致性 | 天然一致 | 多实例数据不一致 |
| 可用性 | 需高可用部署 | 随应用，无单点 |
| 适用场景 | 共享数据 | 热点数据 |

---

## Redis的优势场景

### 1. 数据需要跨实例共享

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ 实例1    │  │ 实例2    │  │ 实例3    │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └──────┬──────┴──────┬──────┘
            │             │
       ┌────┴─────────────┴────┐
       │         Redis         │
       │   (数据全局一致)       │
       └───────────────────────┘
```

**典型场景**：
- Session共享
- 分布式锁
- 全局计数器

### 2. 数据量大

```java
// 商品详情缓存，数据量可能达GB级
@Cacheable(value = "products", key = "#productId")
public Product getProduct(Long productId) {
    return productMapper.findById(productId);
}
```

### 3. 需要丰富的数据结构

```java
// 排行榜：使用ZSet
redis.opsForZSet().add("rank:sales", productId, score);
redis.opsForZSet().reverseRangeWithScores("rank:sales", 0, 9);

// 消息队列：使用List
redis.opsForList().leftPush("queue:orders", order);
redis.opsForList().rightPop("queue:orders");

// 位图统计：使用BitMap
redis.opsForValue().setBit("user:sign:" + userId, dayOfMonth, true);
```

---

## Caffeine的优势场景

### 1. 超高频访问的热点数据

```java
// 配置信息：访问频次高，变化少
@Bean
public Cache<String, Config> configCache() {
    return Caffeine.newBuilder()
        .maximumSize(100)
        .expireAfterWrite(5, TimeUnit.MINUTES)
        .build();
}
```

### 2. 对延迟极度敏感

```
Redis访问：1-5ms
Caffeine访问：<0.01ms（纳秒级）
```

**每一毫秒都重要的场景**：
- 调用链路长的系统
- 高频接口（万级QPS）
- 实时竞价系统

### 3. 容忍短暂数据不一致

```java
// 商品分类信息：各实例缓存不同步，但影响不大
Cache<Long, Category> categoryCache = Caffeine.newBuilder()
    .maximumSize(500)
    .expireAfterWrite(10, TimeUnit.MINUTES)
    .build();
```

---

## 最佳实践：多级缓存

### 架构设计

```
请求
 │
 ├── L1: Caffeine（进程内）
 │     命中率：60%，延迟：<0.1ms
 │
 ├── L2: Redis（分布式）
 │     命中率：35%，延迟：1-5ms
 │
 └── L3: 数据库
       命中率：5%，延迟：10-100ms
```

### 代码实现

```java
@Service
public class ProductService {
    
    // L1: 本地缓存
    private Cache<Long, Product> localCache = Caffeine.newBuilder()
        .maximumSize(10000)
        .expireAfterWrite(1, TimeUnit.MINUTES)
        .build();
    
    @Autowired
    private RedisTemplate<String, Product> redisTemplate;
    
    public Product getProduct(Long productId) {
        // L1: 本地缓存
        Product product = localCache.getIfPresent(productId);
        if (product != null) {
            return product;
        }
        
        // L2: Redis
        String key = "product:" + productId;
        product = redisTemplate.opsForValue().get(key);
        if (product != null) {
            localCache.put(productId, product);
            return product;
        }
        
        // L3: 数据库
        product = productMapper.findById(productId);
        if (product != null) {
            redisTemplate.opsForValue().set(key, product, 1, TimeUnit.HOURS);
            localCache.put(productId, product);
        }
        return product;
    }
}
```

### 缓存更新策略

```java
// 数据变更时，清理各级缓存
public void updateProduct(Product product) {
    productMapper.update(product);
    
    // 清理Redis
    redisTemplate.delete("product:" + product.getId());
    
    // 清理本地缓存（通过MQ广播到所有实例）
    kafkaTemplate.send("cache-evict", 
        new CacheEvictEvent("product", product.getId()));
}

@KafkaListener(topics = "cache-evict")
public void onCacheEvict(CacheEvictEvent event) {
    if ("product".equals(event.getCacheName())) {
        localCache.invalidate(event.getKey());
    }
}
```

---

## 选型决策树

```
需要跨实例共享？
    │
    ├── 是 → Redis
    │
    └── 否 → 数据量大吗？
                │
                ├── 是 → Redis
                │
                └── 否 → 访问频率高吗？
                            │
                            ├── 是 → Caffeine
                            │
                            └── 否 → Redis（简单统一）
```

---

## 常见问题处理

### 问题1：本地缓存数据不一致

**方案**：MQ广播失效消息

```java
// 数据变更时广播
rocketMQTemplate.convertAndSend("cache-evict", key);

// 各实例监听并清理本地缓存
@RocketMQMessageListener(topic = "cache-evict")
public class CacheEvictListener implements RocketMQListener<String> {
    public void onMessage(String key) {
        localCache.invalidate(key);
    }
}
```

### 问题2：本地缓存OOM

**方案**：合理设置容量上限

```java
Caffeine.newBuilder()
    .maximumSize(10000)        // 数量限制
    .maximumWeight(100_000_000) // 或权重限制（100MB）
    .weigher((k, v) -> v.getBytes().length)
    .build();
```

### 问题3：缓存穿透

**方案**：缓存空值

```java
public Product getProduct(Long productId) {
    Product product = cache.getIfPresent(productId);
    if (product != null) {
        return product == NULL_PRODUCT ? null : product;
    }
    
    product = productMapper.findById(productId);
    if (product == null) {
        cache.put(productId, NULL_PRODUCT);  // 缓存空对象
    } else {
        cache.put(productId, product);
    }
    return product;
}
```

---

## 面试答题框架

```
选型依据：
- 共享性：Redis天然全局一致
- 性能：Caffeine纳秒级，Redis毫秒级
- 容量：Redis可达TB，Caffeine受堆限制

典型场景：
- Redis：Session、分布式锁、大容量缓存
- Caffeine：热点数据、配置信息、对延迟敏感

最佳实践：
- 多级缓存：L1 Caffeine + L2 Redis
- 一致性保障：MQ广播失效消息
```

---

## 总结

| 场景 | 推荐方案 |
|------|----------|
| Session共享 | Redis |
| 分布式锁 | Redis |
| 热点商品 | Caffeine + Redis |
| 配置信息 | Caffeine |
| 排行榜 | Redis ZSet |
| 通用缓存 | 多级缓存 |
