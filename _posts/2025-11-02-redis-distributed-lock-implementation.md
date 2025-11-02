---
layout: post
title: "Redis分布式锁的实现"
date: 2025-11-02
description: "深入解析Redis分布式锁的实现原理，包括SET NX EX、Lua脚本、Redisson框架以及分布式场景下的注意事项"
author: "wuxl"
categories: [中间件]
tags: [Redis, 分布式锁, Redisson, 高并发]
---

## 问题

如何使用Redis实现分布式锁？

## 答案

### 1. 核心概念

**分布式锁**是在分布式系统中控制多个节点对共享资源互斥访问的机制。Redis因其高性能和原子性操作，是实现分布式锁的常用选择。

---

### 2. 实现原理与关键点

#### 2.1 基础实现：SET NX EX

Redis 2.6.12+ 版本支持 `SET key value NX EX seconds` 原子命令：

```java
/**
 * 基础分布式锁实现
 */
public class RedisDistributedLock {
    private StringRedisTemplate redisTemplate;

    public boolean tryLock(String lockKey, String requestId, int expireTime) {
        // SET key value NX EX seconds
        Boolean result = redisTemplate.opsForValue()
            .setIfAbsent(lockKey, requestId, expireTime, TimeUnit.SECONDS);
        return Boolean.TRUE.equals(result);
    }

    public void unlock(String lockKey, String requestId) {
        // Lua脚本保证原子性：校验requestId再删除
        String script =
            "if redis.call('get', KEYS[1]) == ARGV[1] then " +
            "   return redis.call('del', KEYS[1]) " +
            "else " +
            "   return 0 " +
            "end";

        redisTemplate.execute(
            new DefaultRedisScript<>(script, Long.class),
            Collections.singletonList(lockKey),
            requestId
        );
    }
}
```

**关键点**：
- **NX（Not Exists）**：只在key不存在时设置，保证互斥性
- **EX（Expire）**：设置过期时间，防止死锁（进程崩溃导致锁永不释放）
- **原子性**：SET NX EX 是一条原子命令，避免加锁和设置过期分离导致的问题
- **requestId**：唯一标识（如UUID），防止误删其他客户端的锁

---

#### 2.2 进阶实现：Redisson框架

Redisson提供了开箱即用的分布式锁，解决了原生实现的诸多问题：

```java
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;

public class RedissonLockExample {
    private RedissonClient redisson;

    public void executeWithLock(String lockKey) {
        RLock lock = redisson.getLock(lockKey);
        try {
            // 尝试加锁，最多等待10秒，锁30秒后自动释放
            boolean isLocked = lock.tryLock(10, 30, TimeUnit.SECONDS);
            if (isLocked) {
                // 执行业务逻辑
                doSomething();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            // 释放锁（内部会校验当前线程是否持有锁）
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

**Redisson核心特性**：
- **看门狗机制（WatchDog）**：自动续期，默认每10秒检查，若业务未完成则延长锁过期时间至30秒
- **可重入性**：基于ThreadLocal和Hash结构，支持同一线程多次加锁
- **RedLock算法**：支持多Redis实例的分布式锁（解决单点故障）
- **公平锁/读写锁**：提供更丰富的锁类型

---

### 3. 分布式场景的考量

#### 3.1 锁过期时间设置
- **过短**：业务未完成锁已释放，导致并发问题
- **过长**：异常情况下锁长时间占用，影响可用性
- **建议**：评估业务耗时，设置合理值，或使用Redisson的自动续期

#### 3.2 主从切换导致的锁丢失

**场景**：
1. 客户端A在Master上加锁成功
2. Master宕机，锁数据未同步到Slave
3. Slave提升为新Master，客户端B可再次加锁

**解决方案**：
- **RedLock算法**：在多个独立的Redis实例上加锁，半数以上成功才算获取锁
- **Zookeeper/etcd**：对一致性要求极高的场景改用强一致性方案

#### 3.3 线程安全与性能优化

- **避免长时间持锁**：将锁粒度细化，缩短临界区代码
- **使用分段锁**：如`lock:user:1001`、`lock:user:1002`，降低锁冲突
- **监控锁超时**：记录加锁失败日志，及时发现性能瓶颈

---

### 4. 面试答题总结

**标准回答模板**：

> Redis分布式锁通过 `SET key value NX EX seconds` 命令实现，核心要点是：
> 1. **加锁**：使用 NX 保证互斥，EX 设置过期防止死锁，value 设置唯一ID防止误删
> 2. **解锁**：通过Lua脚本原子性校验ID并删除
> 3. **实战推荐**：使用Redisson框架，提供看门狗自动续期、可重入、RedLock等特性
> 4. **注意事项**：主从切换可能丢锁，极端场景考虑RedLock或Zookeeper

**常见追问**：
- **为什么要用Lua脚本解锁？** → 保证"判断+删除"的原子性
- **Redisson的看门狗如何工作？** → 定时任务检查锁，自动续期
- **RedLock算法原理？** → 在N个独立实例上加锁，超过N/2+1成功才算获取锁
