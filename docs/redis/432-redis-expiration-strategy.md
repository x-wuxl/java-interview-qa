---
layout: default
title: "Redis的过期策略详解"
parent: Redis
nav_order: 432
description: "深入解析Redis的过期删除策略，包括惰性删除和定期删除的原理、定期删除如何检索key，以及在实际应用中的性能考量。"
date: 2025-11-02
---
## 一、核心概念

Redis的过期策略是指Redis如何处理设置了过期时间（TTL）的key。当key到达过期时间后，Redis需要通过一定的策略将其删除，以释放内存空间。

Redis采用了**惰性删除**（Lazy Expiration）和**定期删除**（Active Expiration）相结合的过期策略。

---

## 二、两种过期删除策略

### 1. 惰性删除（Lazy Expiration）

**原理：**
- 当客户端访问一个key时，Redis会先检查该key是否已过期
- 如果已过期，则删除该key并返回空值
- 如果未过期，则正常返回数据

**优点：**
- 对CPU友好，只在访问时才检查，不会额外占用CPU时间
- 实现简单

**缺点：**
- 如果某些key过期后一直没有被访问，会一直占用内存
- 可能导致内存浪费

**源码关键点：**
在Redis源码中，每次执行命令前都会调用 `expireIfNeeded()` 函数检查key是否过期：

```c
int expireIfNeeded(redisDb *db, robj *key) {
    // 获取过期时间
    mstime_t when = getExpire(db,key);
    
    if (when < 0) return 0; // 没有设置过期时间
    
    // 检查是否过期
    if (mstime() <= when) return 0; // 未过期
    
    // 已过期，删除key
    deleteKey(db,key);
    return 1;
}
```

---

### 2. 定期删除（Active Expiration）

**原理：**
Redis会定期随机抽取一批设置了过期时间的key，检查是否过期并删除。

**定期删除如何检索key（详细流程）：**

1. **触发时机：** Redis的定期删除由 `activeExpireCycle()` 函数执行，默认每秒执行10次（由 `hz` 参数控制，默认为10）

2. **抽样检查流程：**
   - 从所有设置了过期时间的key中**随机抽取20个**（默认值 `ACTIVE_EXPIRE_CYCLE_LOOKUPS_PER_LOOP`）
   - 检查这20个key是否过期，删除所有已过期的key
   - 如果过期key的比例**超过25%**，则继续重复上述步骤
   - 如果过期key比例低于25%，则停止当前数据库的检查，进入下一个数据库

3. **时间限制：**
   - 单次执行时间不超过一定阈值（默认25ms），避免阻塞主线程过久
   - 分为快速模式和慢速模式，快速模式执行时间更短（1ms）

4. **遍历数据库：**
   - Redis会遍历所有数据库（db0-db15），对每个数据库执行上述抽样检查
   - 采用自适应算法，优先处理过期key较多的数据库

**优点：**
- 可以主动清理过期key，减少内存浪费
- 通过限制执行时间和抽样比例，平衡了CPU和内存开销

**缺点：**
- 占用CPU时间
- 采用随机抽样，无法保证所有过期key都能及时删除

**源码关键点：**

```c
void activeExpireCycle(int type) {
    static unsigned int current_db = 0;
    unsigned int dbs_per_call = CRON_DBS_PER_CALL;
    long long start = ustime();
    
    // 遍历数据库
    for (int j = 0; j < dbs_per_call; j++) {
        redisDb *db = server.db + (current_db % server.dbnum);
        
        do {
            // 随机抽取20个设置了过期时间的key
            num = dictSize(db->expires);
            if (num == 0) break;
            
            sampled = 0;
            expired = 0;
            
            while (sampled < ACTIVE_EXPIRE_CYCLE_LOOKUPS_PER_LOOP) {
                // 随机获取一个key
                de = dictGetRandomKey(db->expires);
                ttl = dictGetSignedIntegerVal(de) - now;
                
                if (ttl < 0) {
                    // 已过期，删除
                    deleteKey(db, key);
                    expired++;
                }
                sampled++;
            }
            
            // 如果过期key比例超过25%，继续循环
        } while (expired > ACTIVE_EXPIRE_CYCLE_LOOKUPS_PER_LOOP / 4);
        
        // 检查执行时间，避免阻塞过久
        if ((ustime() - start) > timelimit) break;
    }
}
```

---

## 三、性能与实际应用考量

### 1. 为什么采用两种策略结合？

- **单纯惰性删除：** 无法清理不再访问的过期key，会造成内存泄漏
- **单纯定期删除：** 如果检查过于频繁会占用过多CPU；如果检查不频繁，又无法及时释放内存
- **结合使用：** 既保证了大部分过期key能被及时删除，又不会过度消耗CPU资源

### 2. 配置调优

在 `redis.conf` 中可以调整相关参数：

```bash
# 定期删除的频率（每秒执行的次数）
hz 10

# 最大内存限制
maxmemory 2gb

# 内存淘汰策略（当内存不足时触发）
maxmemory-policy allkeys-lru
```

### 3. 实际场景注意事项

- **大量key同时过期：** 避免在同一时间设置大量key过期，会导致定期删除集中执行，造成CPU峰值。可以在过期时间上加一个随机值：
  
```java
// 避免缓存雪崩
int randomExpire = 3600 + new Random().nextInt(300); // 1小时 + 随机0-5分钟
redisTemplate.expire(key, randomExpire, TimeUnit.SECONDS);
```

- **监控过期key数量：** 使用 `INFO stats` 命令查看 `expired_keys` 指标，监控过期删除是否正常工作

```bash
redis> INFO stats
# Stats
expired_keys:1000
evicted_keys:200
```

---

## 四、答题总结

**Redis的过期策略采用惰性删除和定期删除相结合的方式：**

1. **惰性删除：** 访问key时检查是否过期，过期则删除
2. **定期删除：** 定期随机抽取20个有过期时间的key进行检查，如果过期比例超过25%则继续抽样，单次执行有时间限制（默认25ms）

**定期删除的检索机制：**
- 每秒执行10次（由hz参数控制）
- 随机抽样20个key，删除其中过期的key
- 如果过期率>25%，重复抽样
- 限制单次执行时间，避免阻塞

**实际应用中要注意：**
- 避免大量key同时过期（加随机时间）
- 设置合理的maxmemory和淘汰策略
- 即使有过期策略，当内存不足时仍会触发内存淘汰策略

这种组合策略在CPU开销和内存占用之间取得了良好的平衡，是Redis高性能的重要保障之一。

