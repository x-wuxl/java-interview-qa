---
title: "Redis实现分布式锁的原理？"
date: 2025-11-02
categories: [分布式, 分布式锁, Redis]
tags: [Redis, 分布式锁, SET NX, Redisson, RedLock]
description: "深入剖析Redis分布式锁的实现原理，从基础SET NX到Redisson的完整解决方案，以及RedLock算法"
nav_order: 512
parent: 分布式锁
---
## 核心概念

Redis 分布式锁的核心是利用 **SET NX（SET if Not eXists）** 命令的原子性来实现互斥，配合 **过期时间** 防止死锁，使用 **Lua 脚本** 保证加锁和解锁操作的原子性。

## 一、基础实现原理

### 1.1 加锁：SET NX + EX

```bash
# SET key value NX EX seconds
# NX：仅当key不存在时设置
# EX：设置过期时间（秒）
SET lock:resource:123 uuid-value-xxx NX EX 30
```

**返回值：**
- `OK`：加锁成功
- `nil`：key已存在，加锁失败

**关键点：**
- `SET NX EX` 是一条**原子命令**（Redis 2.6.12 之后），避免分两步操作时客户端崩溃导致死锁
- `value` 通常使用 UUID，用于解锁时校验持锁者身份

```java
public boolean tryLock(String key, String requestId, int expireTime) {
    // 使用 SET NX EX 一次性完成加锁和设置过期时间
    String result = jedis.set(key, requestId, 
        SetParams.setParams().nx().ex(expireTime));
    return "OK".equals(result);
}
```

### 1.2 解锁：Lua 脚本保证原子性

**错误示范：**
```java
// ❌ 非原子操作，可能误删其他客户端的锁
if (redis.get(lockKey).equals(requestId)) {
    redis.del(lockKey); // 可能在这之间锁过期，其他客户端获得锁
}
```

**正确做法：使用 Lua 脚本**
```lua
-- 解锁脚本
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

```java
public boolean unlock(String key, String requestId) {
    String script = 
        "if redis.call('get', KEYS[1]) == ARGV[1] then " +
        "    return redis.call('del', KEYS[1]) " +
        "else " +
        "    return 0 " +
        "end";
    
    Object result = jedis.eval(script, 
        Collections.singletonList(key), 
        Collections.singletonList(requestId));
    
    return Long.valueOf(1L).equals(result);
}
```

**Lua 脚本的优势：**
- Redis 保证脚本执行的原子性
- 避免「检查-删除」之间的时间窗口问题

## 二、基础方案存在的问题

### 问题1：锁过期时间难以设置

如果业务执行时间超过锁的过期时间，锁会自动释放，导致并发问题。

**解决方案：看门狗机制（Watch Dog）**

### 问题2：不可重入

同一个线程无法多次获取同一把锁。

**解决方案：使用 Hash 结构记录重入次数**

### 问题3：主从架构下的锁丢失

Redis 主从复制是**异步**的，主节点宕机时，从节点可能未同步锁数据：

```
1. 客户端 A 在主节点获取锁
2. 主节点宕机，锁数据未同步到从节点
3. 从节点提升为主节点
4. 客户端 B 在新主节点获取相同的锁 ✓（锁丢失）
```

**解决方案：RedLock 算法（后续介绍）**

## 三、Redisson 完整解决方案

Redisson 是一个成熟的 Redis 客户端，提供了完整的分布式锁实现。

### 3.1 基本使用

```java
@Autowired
private RedissonClient redissonClient;

public void doSomething() {
    // 获取锁对象
    RLock lock = redissonClient.getLock("myLock");
    
    try {
        // 尝试加锁
        // waitTime: 等待获取锁的最大时间
        // leaseTime: 锁自动释放时间
        boolean locked = lock.tryLock(10, 30, TimeUnit.SECONDS);
        
        if (locked) {
            // 执行业务逻辑
            processBusinessLogic();
        } else {
            // 获取锁失败
            throw new RuntimeException("获取锁失败");
        }
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
    } finally {
        // 释放锁（只有持锁线程才能释放）
        if (lock.isHeldByCurrentThread()) {
            lock.unlock();
        }
    }
}
```

### 3.2 核心特性

#### （1）看门狗机制（Watch Dog）

**问题：** 业务执行时间超过锁的过期时间怎么办？

**Redisson 的解决方案：**
```java
// 不指定 leaseTime，使用默认的看门狗机制
lock.lock(); // 默认 30 秒过期

// 后台线程每隔 10 秒（leaseTime / 3）检查一次
// 如果锁还被持有，自动续期到 30 秒
```

**看门狗工作原理：**
1. 加锁时不指定过期时间，Redisson 会设置默认的 30 秒
2. 启动一个后台定时任务，每 10 秒检查一次
3. 如果当前线程还持有锁，就将过期时间续期到 30 秒
4. 直到业务执行完毕，手动释放锁

**源码关键逻辑：**
```java
// Redisson 加锁源码简化
private void scheduleExpirationRenewal(long threadId) {
    ExpirationEntry entry = new ExpirationEntry();
    
    // 每隔 internalLockLeaseTime / 3 执行一次
    Timeout task = commandExecutor.getConnectionManager().newTimeout(
        timeout -> {
            // 续期 Lua 脚本
            renewExpiration();
            // 递归调用，持续续期
            scheduleExpirationRenewal(threadId);
        }, 
        internalLockLeaseTime / 3, 
        TimeUnit.MILLISECONDS
    );
}
```

#### （2）可重入锁

**实现原理：** 使用 Redis Hash 结构存储锁信息

```bash
# 锁的数据结构
HSET myLock thread-1 1  # 第一次加锁，重入次数为 1
HSET myLock thread-1 2  # 第二次加锁，重入次数为 2
```

**加锁 Lua 脚本（简化版）：**
```lua
-- 锁不存在
if (redis.call('exists', KEYS[1]) == 0) then
    redis.call('hincrby', KEYS[1], ARGV[2], 1); -- 设置重入次数为 1
    redis.call('pexpire', KEYS[1], ARGV[1]); -- 设置过期时间
    return nil;
end;

-- 锁存在且是当前线程持有
if (redis.call('hexists', KEYS[1], ARGV[2]) == 1) then
    redis.call('hincrby', KEYS[1], ARGV[2], 1); -- 重入次数 +1
    redis.call('pexpire', KEYS[1], ARGV[1]); -- 刷新过期时间
    return nil;
end;

-- 锁被其他线程持有
return redis.call('pttl', KEYS[1]); -- 返回剩余过期时间
```

**解锁 Lua 脚本（简化版）：**
```lua
-- 锁不存在或不是当前线程持有
if (redis.call('hexists', KEYS[1], ARGV[3]) == 0) then
    return nil;
end;

-- 重入次数 -1
local counter = redis.call('hincrby', KEYS[1], ARGV[3], -1);

-- 重入次数 > 0，只刷新过期时间
if (counter > 0) then
    redis.call('pexpire', KEYS[1], ARGV[2]);
    return 0;
else
    -- 重入次数为 0，删除锁
    redis.call('del', KEYS[1]);
    return 1;
end;
```

#### （3）公平锁

Redisson 提供了公平锁实现，保证先到先得：

```java
RLock fairLock = redissonClient.getFairLock("fairLock");
fairLock.lock();
try {
    // 业务逻辑
} finally {
    fairLock.unlock();
}
```

**实现原理：** 使用 Redis List 维护等待队列

## 四、RedLock 算法（高可靠方案）

### 4.1 为什么需要 RedLock？

Redis 主从架构下，异步复制可能导致锁丢失：

```
主节点宕机 → 从节点提升 → 锁数据未同步 → 新主节点可以再次加锁
```

### 4.2 RedLock 原理

**核心思想：** 在多个独立的 Redis 实例（≥3个，通常5个）上同时加锁，超过半数成功才算加锁成功。

**加锁流程：**
1. 获取当前时间戳 T1
2. 依次向 N 个 Redis 实例请求加锁（使用相同的 key 和随机值）
3. 设置较短的超时时间（如 5-50ms），避免阻塞在宕机的节点上
4. 计算加锁耗时：T2 - T1
5. **判断是否成功：**
   - 在超过半数的实例上加锁成功（如 5 个实例中成功 3 个）
   - 总耗时 < 锁的有效时间
6. 如果成功，锁的实际有效时间 = 初始有效时间 - 加锁耗时
7. 如果失败，向所有实例发送解锁请求

**Redisson 使用 RedLock：**
```java
RLock lock1 = redissonClient1.getLock("myLock");
RLock lock2 = redissonClient2.getLock("myLock");
RLock lock3 = redissonClient3.getLock("myLock");

// 创建 RedLock
RLock redLock = redissonClient.getRedLock(lock1, lock2, lock3);

try {
    redLock.lock();
    // 业务逻辑
} finally {
    redLock.unlock();
}
```

### 4.3 RedLock 的争议

**争议点：** Redis 作者 Antirez 与分布式系统专家 Martin Kleppmann 的辩论

- **Antirez**：RedLock 在多数节点正常的情况下是安全的
- **Martin**：RedLock 无法解决所有分布式一致性问题（如时钟漂移、长时间 GC）

**结论：** RedLock 在大多数场景下足够可靠，但不能替代基于共识算法（如 Paxos、Raft）的强一致性方案。

## 五、实战注意事项

### 1. 锁的粒度要合理
```java
// ❌ 锁粒度过大，影响并发
lock("global-lock");

// ✅ 根据业务细化锁粒度
lock("order:" + orderId);
```

### 2. 设置合理的超时时间
```java
// 考虑业务执行时间，设置合理的过期时间
// 或使用 Redisson 的看门狗机制
lock.tryLock(5, 30, TimeUnit.SECONDS);
```

### 3. 避免死锁
```java
// ✅ 必须在 finally 中释放锁
try {
    lock.lock();
    // 业务逻辑
} finally {
    if (lock.isHeldByCurrentThread()) {
        lock.unlock();
    }
}
```

### 4. 监控告警
- 监控锁的持有时间，发现异常长时间持锁
- 监控锁的竞争情况，优化锁粒度
- 监控 Redis 主从切换对锁的影响

## 答题总结

**Redis 分布式锁的核心原理：**

1. **基础实现**：使用 `SET NX EX` 原子命令加锁，Lua 脚本原子性解锁
2. **核心命令**：
   - 加锁：`SET lock:key uuid NX EX 30`
   - 解锁：Lua 脚本保证「检查持锁者 + 删除」的原子性

3. **Redisson 增强**：
   - **看门狗机制**：自动续期，避免业务未执行完锁就过期
   - **可重入锁**：基于 Hash 结构记录重入次数
   - **公平锁**：基于 List 维护等待队列

4. **高可用方案**：RedLock 算法，在多个独立 Redis 实例上加锁，超过半数成功才算成功

**面试加分项：**
- 提到 Lua 脚本保证原子性的重要性
- 了解 Redisson 的看门狗机制
- 知道 RedLock 算法及其适用场景
- 能够分析 Redis 主从架构下锁丢失的风险

**推荐方案：** 大多数场景使用 **Redisson + Redis 哨兵/集群** 即可，极端情况下考虑 RedLock 或 Zookeeper。

