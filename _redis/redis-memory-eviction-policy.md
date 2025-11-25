---
title: "Redis内存淘汰策略详解"
date: 2025-11-02
categories: [Redis, 缓存]
tags: [Redis, 内存淘汰, LRU, LFU, maxmemory, 面试]
description: "全面解析Redis的8种内存淘汰策略，包括LRU、LFU算法原理、源码实现、性能对比，以及在不同业务场景下的选择建议。"
nav_order: 433
parent: Redis
---
## 一、核心概念

Redis内存淘汰策略（Memory Eviction Policy）是指当Redis使用的内存达到 `maxmemory` 限制时，Redis会根据配置的淘汰策略选择并删除部分数据，以腾出空间存储新数据。

**与过期策略的区别：**
- **过期策略：** 处理已过期的key（基于TTL时间）
- **内存淘汰策略：** 处理内存不足的情况（不限于过期key）

---

## 二、8种内存淘汰策略

Redis提供了8种内存淘汰策略，可通过 `maxmemory-policy` 配置：

### 1. noeviction（默认策略）
- **行为：** 不淘汰任何数据，内存满时直接返回错误
- **适用场景：** 数据绝对不能丢失的场景，如数据库缓存
- **优点：** 保证数据完整性
- **缺点：** 内存满后无法写入新数据

```bash
# 当内存不足时返回错误
127.0.0.1:6379> SET key1 value1
(error) OOM command not allowed when used memory > 'maxmemory'
```

---

### 2. allkeys-lru（最常用）
- **行为：** 从所有key中，使用LRU算法淘汰最近最少使用的key
- **适用场景：** 通用缓存场景，访问热点数据
- **优点：** 符合大多数业务场景，保留热点数据
- **推荐指数：** ⭐⭐⭐⭐⭐

---

### 3. allkeys-lfu（Redis 4.0+）
- **行为：** 从所有key中，使用LFU算法淘汰访问频率最低的key
- **适用场景：** 区分热点数据，某些key访问频率持续较高
- **优点：** 比LRU更精准，考虑访问频率而非时间
- **推荐指数：** ⭐⭐⭐⭐

---

### 4. allkeys-random
- **行为：** 从所有key中随机淘汰
- **适用场景：** 所有key访问概率相似，或测试环境
- **优点：** 实现简单，速度快
- **缺点：** 可能淘汰热点数据

---

### 5. volatile-lru
- **行为：** 仅从设置了过期时间的key中，使用LRU算法淘汰
- **适用场景：** 区分持久数据和临时数据，只淘汰临时缓存
- **注意：** 如果没有设置过期时间的key，则无法淘汰，行为类似noeviction

---

### 6. volatile-lfu（Redis 4.0+）
- **行为：** 仅从设置了过期时间的key中，使用LFU算法淘汰
- **适用场景：** 同上，但更关注访问频率

---

### 7. volatile-random
- **行为：** 仅从设置了过期时间的key中随机淘汰
- **适用场景：** 设置了过期时间的都是可淘汰数据，且无明显访问偏好

---

### 8. volatile-ttl
- **行为：** 仅从设置了过期时间的key中，淘汰TTL最小（即将过期）的key
- **适用场景：** 优先清理快要过期的数据
- **优点：** 符合"即将过期的数据价值更低"的逻辑

---

## 三、LRU与LFU算法原理

### 1. LRU（Least Recently Used）算法

**标准LRU原理：**
- 维护一个双向链表，按访问时间排序
- 访问一个key时，将其移到链表头部
- 淘汰时，删除链表尾部的key

**Redis近似LRU实现（源码关键点）：**

Redis并未使用严格的LRU算法（需要额外的链表结构和大量内存），而是使用了**近似LRU算法**：

```c
typedef struct redisObject {
    unsigned type:4;
    unsigned encoding:4;
    unsigned lru:24;  // 存储最后访问时间戳（秒级）或LFU数据
    int refcount;
    void *ptr;
} robj;
```

**淘汰过程：**
1. 随机抽样N个key（默认5个，由 `maxmemory-samples` 配置）
2. 从这N个key中选出最久未使用的key
3. 删除该key
4. 如果内存仍不足，重复上述步骤

```c
int evict = 0;
for (int i = 0; i < server.maxmemory_samples; i++) {
    robj *o = dictGetRandomKey(dict);
    
    // 计算idle时间
    unsigned long idle = estimateObjectIdleTime(o);
    
    // 选择idle时间最长的
    if (idle > max_idle) {
        max_idle = idle;
        evict = o;
    }
}
// 淘汰选中的key
dbDelete(db, evict);
```

**优点：**
- 节省内存，无需维护链表
- 性能好，O(1)时间复杂度

**缺点：**
- 近似算法，不保证绝对准确
- 抽样数量（maxmemory-samples）越大越精确，但性能开销也越大

---

### 2. LFU（Least Frequently Used）算法

**原理：**
- 记录key的访问频率（访问次数）
- 淘汰访问频率最低的key

**Redis LFU实现：**

Redis复用了 `redisObject` 的24位lru字段存储LFU信息：
- 高16位：存储上次递减时间（分钟级）
- 低8位：存储访问频率计数器（0-255）

```c
// LFU字段结构
// [16位时间戳][8位计数器]

// 访问时增加计数器
void updateLFU(robj *o) {
    unsigned long counter = LFUDecrAndReturn(o);  // 先衰减
    counter = LFULogIncr(counter);                // 再增加
    o->lru = (LFUGetTimeInMinutes() << 8) | counter;
}
```

**关键特性：**
1. **对数递增：** 访问次数不是线性增加，而是按对数递增，避免老数据计数过高
   
```c
uint8_t LFULogIncr(uint8_t counter) {
    if (counter == 255) return 255;
    double r = (double)rand() / RAND_MAX;
    double baseval = counter - LFU_INIT_VAL;
    double p = 1.0 / (baseval * server.lfu_log_factor + 1);
    if (r < p) counter++;
    return counter;
}
```

2. **时间衰减：** 长时间未访问的key，其计数器会逐渐衰减

```c
unsigned long LFUDecrAndReturn(robj *o) {
    unsigned long ldt = o->lru >> 8;  // 获取上次衰减时间
    unsigned long counter = o->lru & 255;  // 获取计数器
    
    // 计算需要衰减的次数
    unsigned long num_periods = server.lfu_decay_time ? 
        LFUTimeElapsed(ldt) / server.lfu_decay_time : 0;
    
    // 衰减计数器
    if (num_periods)
        counter = (num_periods > counter) ? 0 : counter - num_periods;
    
    return counter;
}
```

**配置参数：**
```bash
# LFU计数器对数增长因子（默认10）
lfu-log-factor 10

# LFU计数器衰减时间（分钟，默认1）
lfu-decay-time 1
```

---

## 四、策略选择建议

### 场景一：通用Web应用缓存
```bash
maxmemory 2gb
maxmemory-policy allkeys-lru
maxmemory-samples 5  # 默认值，可根据需要调整
```

**理由：** 大多数Web应用符合80/20原则，20%的热点数据占据80%的访问，LRU能很好地保留热点数据。

---

### 场景二：明确的热点数据访问模式
```bash
maxmemory 2gb
maxmemory-policy allkeys-lfu
lfu-log-factor 10
lfu-decay-time 1
```

**理由：** 某些key持续高频访问（如热门商品），LFU比LRU更精准。

---

### 场景三：混合持久数据和缓存数据
```bash
maxmemory 2gb
maxmemory-policy volatile-lru
```

**理由：** 
- 持久数据不设置过期时间，永远不会被淘汰
- 缓存数据设置过期时间，内存不足时会被淘汰

```java
// 持久数据（如配置信息）
redisTemplate.opsForValue().set("config:app", configData);

// 缓存数据（设置过期时间）
redisTemplate.opsForValue().set("cache:user:1001", userData, 3600, TimeUnit.SECONDS);
```

---

### 场景四：数据绝对不能丢失
```bash
maxmemory 2gb
maxmemory-policy noeviction
```

**理由：** 宁愿拒绝写入，也不能丢失数据。配合监控告警，及时扩容。

---

## 五、性能与监控

### 1. 查看当前策略
```bash
127.0.0.1:6379> CONFIG GET maxmemory-policy
1) "maxmemory-policy"
2) "allkeys-lru"
```

### 2. 动态修改策略
```bash
127.0.0.1:6379> CONFIG SET maxmemory-policy allkeys-lfu
OK
```

### 3. 监控淘汰情况
```bash
127.0.0.1:6379> INFO stats
# Stats
evicted_keys:5000        # 淘汰的key数量
expired_keys:10000       # 过期删除的key数量
keyspace_hits:1000000    # 命中次数
keyspace_misses:50000    # 未命中次数
```

**关键指标：**
- `evicted_keys`：淘汰数量激增说明内存不足
- 命中率 = `keyspace_hits / (keyspace_hits + keyspace_misses)`，命中率下降可能需要调整淘汰策略

---

## 六、答题总结

**Redis提供8种内存淘汰策略，核心分类：**

| 策略 | 范围 | 算法 | 使用场景 |
|------|------|------|----------|
| **allkeys-lru** | 全部key | LRU近似 | 通用缓存（推荐） |
| **allkeys-lfu** | 全部key | LFU | 明确热点数据 |
| **allkeys-random** | 全部key | 随机 | 访问无偏好 |
| **volatile-lru** | 带过期时间 | LRU近似 | 混合持久和缓存数据 |
| **volatile-lfu** | 带过期时间 | LFU | 同上，关注频率 |
| **volatile-ttl** | 带过期时间 | 最小TTL | 优先清理即将过期 |
| **volatile-random** | 带过期时间 | 随机 | 临时数据随机淘汰 |
| **noeviction** | 不淘汰 | - | 数据不能丢失 |

**LRU vs LFU：**
- **LRU：** 关注访问时间，最近访问的保留，适合大部分场景
- **LFU：** 关注访问频率，高频访问的保留，更精准但计算复杂

**Redis实现特点：**
- 采用近似LRU/LFU算法，通过随机采样实现，节省内存
- 不需要额外的链表结构，利用redisObject的24位lru字段存储信息
- 可通过 `maxmemory-samples` 调整精度（默认5）

**生产环境建议：**
- 通用场景选择 `allkeys-lru`
- 设置合理的 `maxmemory`（通常为物理内存的70-80%）
- 监控 `evicted_keys` 和命中率，及时调整策略或扩容

