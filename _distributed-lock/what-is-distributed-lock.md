---
title: "什么是分布式锁？"
date: 2025-11-02
categories: [分布式, 分布式锁]
tags: [分布式锁, 并发控制, 微服务]
description: "深入理解分布式锁的核心概念、应用场景及其在分布式系统中的重要性"
nav_order: 510
parent: 分布式锁
---
## 核心概念

**分布式锁**是在分布式系统中用于控制多个节点对共享资源访问的一种互斥机制。它解决了多个进程或服务实例在不同机器上同时访问同一资源时的并发冲突问题。

与单机环境下的锁（如 `synchronized`、`ReentrantLock`）不同，分布式锁需要跨多个 JVM 进程协调，确保在任意时刻只有一个客户端能够持有锁。

## 核心特性

一个完善的分布式锁应具备以下特性：

### 1. 互斥性
在任意时刻，只有一个客户端能够持有锁，这是锁的最基本特性。

### 2. 防死锁
- **超时释放**：必须设置过期时间，防止客户端崩溃后锁永久无法释放
- **自动续期**：对于长时间任务，需要自动延长锁的过期时间

### 3. 可重入性
同一个线程或客户端可以多次获取同一把锁，避免自己阻塞自己。

### 4. 高可用
锁服务本身需要高可用，不能成为系统的单点故障。

### 5. 正确释放
- **所有权校验**：只有持锁者才能释放锁，避免误删他人持有的锁
- **原子性释放**：释放锁的操作必须是原子的

## 典型应用场景

### 1. 防止重复执行
```java
// 定时任务在多实例部署时，确保同一时刻只有一个实例执行
@Scheduled(cron = "0 0 2 * * ?")
public void syncData() {
    String lockKey = "task:sync:data";
    if (distributedLock.tryLock(lockKey, 300)) {
        try {
            // 执行数据同步任务
            doSyncData();
        } finally {
            distributedLock.unlock(lockKey);
        }
    }
}
```

### 2. 库存扣减
```java
// 秒杀场景中，确保库存扣减的准确性
public boolean decreaseStock(Long productId, Integer count) {
    String lockKey = "stock:" + productId;
    if (distributedLock.tryLock(lockKey, 10)) {
        try {
            Integer stock = getStock(productId);
            if (stock >= count) {
                updateStock(productId, stock - count);
                return true;
            }
            return false;
        } finally {
            distributedLock.unlock(lockKey);
        }
    }
    return false;
}
```

### 3. 缓存更新
```java
// 防止缓存击穿，只让一个请求去查询数据库并更新缓存
public User getUserById(Long userId) {
    String cacheKey = "user:" + userId;
    User user = redis.get(cacheKey);
    
    if (user == null) {
        String lockKey = "lock:user:" + userId;
        if (distributedLock.tryLock(lockKey, 5)) {
            try {
                // 双重检查
                user = redis.get(cacheKey);
                if (user == null) {
                    user = userMapper.selectById(userId);
                    redis.set(cacheKey, user, 3600);
                }
            } finally {
                distributedLock.unlock(lockKey);
            }
        }
    }
    return user;
}
```

## 与单机锁的对比

| 特性 | 单机锁 | 分布式锁 |
|------|--------|----------|
| **作用范围** | 单个JVM进程内 | 跨多个JVM、多台机器 |
| **实现方式** | synchronized、ReentrantLock | Redis、Zookeeper、数据库 |
| **性能** | 高（内存操作） | 相对较低（网络IO） |
| **复杂度** | 低 | 高（需要考虑网络、超时、一致性） |
| **适用场景** | 单机应用 | 分布式系统、微服务架构 |

## 答题总结

**分布式锁是分布式系统中用于控制多节点并发访问共享资源的互斥机制**，核心要解决跨 JVM 的资源竞争问题。

面试中需要强调：
1. **本质**：解决分布式环境下的并发控制问题
2. **核心特性**：互斥性、防死锁、高可用、正确释放
3. **应用场景**：定时任务防重、库存扣减、缓存更新等
4. **与单机锁的区别**：作用范围、实现方式、性能开销

常见实现方案包括 Redis（性能好）、Zookeeper（可靠性高）、数据库（简单但性能较低）三种，需要根据具体业务场景选择合适的方案。

