---
layout: default
title: "Redis缓存一致性问题与解决方案"
parent: Redis
nav_order: 435
description: "深入分析Redis缓存与数据库的一致性问题，包括Cache Aside模式、延迟双删、订阅binlog等解决方案及分布式场景下的权衡"
author: "wuxl"
date: 2025-11-02
---
## 问题

如何保证Redis缓存与数据库的数据一致性？

## 答案

### 1. 核心概念

**缓存一致性问题**是指在使用Redis作为数据库缓存时，如何保证缓存中的数据与数据库中的数据保持同步。核心矛盾在于：**数据库和缓存的更新不是原子操作**，并发场景下容易产生数据不一致。

---

### 2. 常见的缓存更新策略

#### 2.1 Cache Aside（旁路缓存）- 最常用

**读流程**：
1. 先读缓存，命中则直接返回
2. 缓存未命中，读数据库
3. 将数据库结果写入缓存并返回

**写流程**：
1. **先更新数据库**
2. **再删除缓存**

```java
/**
 * Cache Aside模式示例
 */
public class CacheAsideService {
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private StringRedisTemplate redisTemplate;

    // 读操作
    public User getUser(Long userId) {
        String cacheKey = "user:" + userId;

        // 1. 查缓存
        String userJson = redisTemplate.opsForValue().get(cacheKey);
        if (userJson != null) {
            return JSON.parseObject(userJson, User.class);
        }

        // 2. 缓存未命中，查数据库
        User user = userMapper.selectById(userId);
        if (user != null) {
            // 3. 写入缓存
            redisTemplate.opsForValue().set(
                cacheKey,
                JSON.toJSONString(user),
                30, TimeUnit.MINUTES
            );
        }
        return user;
    }

    // 写操作
    public void updateUser(User user) {
        String cacheKey = "user:" + user.getId();

        // 1. 先更新数据库
        userMapper.updateById(user);

        // 2. 再删除缓存（下次读取时重新加载）
        redisTemplate.delete(cacheKey);
    }
}
```

#### 2.2 其他策略（了解即可）

- **Read/Write Through**：应用程序只操作缓存，由缓存层负责同步数据库（类似MyBatis二级缓存）
- **Write Behind（异步写回）**：先写缓存，异步批量刷新数据库（性能最高，但可能丢数据）

---

### 3. 数据不一致的典型场景与解决方案

#### 3.1 为什么选择"先更新数据库，再删缓存"？

**反例1：先删缓存，再更新数据库**
- 线程A删除缓存 → 线程B读取（缓存未命中，读到旧数据并写入缓存）→ 线程A更新数据库
- **结果**：缓存中是旧数据，数据库是新数据

**反例2：先更新数据库，再更新缓存**
- 并发更新时，缓存可能被旧值覆盖
- 写多读少场景下，缓存频繁更新但很少使用，浪费资源

**最佳实践：先更新数据库，再删缓存**
- 不一致窗口期更短（只有极端情况才出现）
- 删除操作比更新操作更轻量

---

#### 3.2 极端不一致场景：数据库主从延迟

**场景**：
1. 线程A更新主库并删除缓存
2. 线程B立即读取，缓存未命中，查询从库（此时从库数据尚未同步，读到旧值）
3. 线程B将旧值写入缓存

**解决方案1：延迟双删**

```java
public void updateUserWithDelayedDoubleDelete(User user) {
    String cacheKey = "user:" + user.getId();

    // 1. 删除缓存
    redisTemplate.delete(cacheKey);

    // 2. 更新数据库
    userMapper.updateById(user);

    // 3. 延迟N毫秒后再次删除缓存
    CompletableFuture.runAsync(() -> {
        try {
            Thread.sleep(500); // 延迟时间需大于主从同步延迟
            redisTemplate.delete(cacheKey);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    });
}
```

**延迟时间设置**：需大于主从同步时间（通常100-300ms），可通过监控确定。

---

**解决方案2：订阅数据库binlog**

使用Canal、Maxwell等中间件监听MySQL binlog，异步更新缓存：

```java
/**
 * 基于Canal的缓存更新（伪代码）
 */
@Component
public class CanalCacheUpdater {
    @CanalListener(destination = "example", schema = "test", table = "user")
    public void onUserChange(CanalEntry.EventType eventType, CanalEntry.RowData rowData) {
        if (eventType == CanalEntry.EventType.UPDATE ||
            eventType == CanalEntry.EventType.DELETE) {

            String userId = rowData.getAfterColumnsList().stream()
                .filter(col -> "id".equals(col.getName()))
                .findFirst()
                .map(CanalEntry.Column::getValue)
                .orElse(null);

            if (userId != null) {
                redisTemplate.delete("user:" + userId);
            }
        }
    }
}
```

**优势**：
- 解耦业务代码和缓存更新逻辑
- 天然处理主从延迟（binlog同步后才触发）
- 支持异构数据源同步（如同步到ES、MongoDB）

---

#### 3.3 并发写场景：分布式锁保证

对于热点数据的并发更新，可用分布式锁串行化：

```java
public void updateUserWithLock(User user) {
    String lockKey = "lock:user:" + user.getId();
    String cacheKey = "user:" + user.getId();

    RLock lock = redissonClient.getLock(lockKey);
    try {
        lock.lock(5, TimeUnit.SECONDS);

        // 更新数据库
        userMapper.updateById(user);

        // 删除缓存
        redisTemplate.delete(cacheKey);

    } finally {
        if (lock.isHeldByCurrentThread()) {
            lock.unlock();
        }
    }
}
```

---

### 4. 强一致性 vs 最终一致性权衡

#### 4.1 最终一致性（推荐）

- **适用场景**：大多数互联网业务（如商品详情、用户信息）
- **方案**：Cache Aside + 合理的缓存过期时间（如5-30分钟）
- **优势**：性能高，实现简单
- **不一致窗口**：毫秒级到秒级（可接受）

#### 4.2 强一致性

- **适用场景**：金融交易、库存扣减等强一致性需求
- **方案**：
  - 不使用缓存，直接查数据库
  - 使用分布式锁 + 缓存
  - 订阅binlog + 重试机制
- **代价**：性能下降，复杂度提升

---

### 5. 面试答题总结

**标准回答模板**：

> 缓存一致性的核心挑战是数据库和缓存更新不是原子操作。常用的 **Cache Aside** 模式采用：
> 1. **读**：先查缓存，未命中再查数据库并回写缓存
> 2. **写**：先更新数据库，再删除缓存
>
> **不一致场景及解决方案**：
> - **主从延迟导致脏数据**：延迟双删（更新后延迟N毫秒再删一次缓存）
> - **解耦与可靠性**：订阅binlog（Canal）异步更新缓存
> - **并发热点**：分布式锁串行化更新
>
> **工程实践**：
> - 设置合理的缓存过期时间作为兜底
> - 大多数场景接受最终一致性（秒级）
> - 强一致性场景考虑不用缓存或引入分布式事务

**常见追问**：
- **为什么不先删缓存再更新数据库？** → 并发时更容易产生脏数据
- **延迟双删的延迟时间如何确定？** → 需大于主从同步时间，通过监控测试确定（通常100-500ms）
- **Canal的原理是什么？** → 伪装成MySQL从库，订阅并解析binlog事件
