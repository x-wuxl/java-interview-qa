---
layout: default
title: "WatchDog 的实现原理是什么？"
parent: Redis
nav_order: 445
description: "深入剖析 Redisson 分布式锁中的 WatchDog（看门狗）机制，解释其如何通过自动续期解决业务执行时间超过锁过期时间的问题。"
date: 2025-11-20
---
## 1. 核心概念

**WatchDog（看门狗）** 是 Redisson 框架中用于处理 **分布式锁自动续期** 的核心机制。

在分布式锁场景下，如果业务逻辑执行时间超过了锁的过期时间（TTL），锁会被 Redis 自动释放，导致其他线程可以获取锁，从而破坏互斥性。WatchDog 的作用就是：**在业务逻辑未执行完之前，定期延长锁的过期时间，确保锁不会被意外释放。**

## 2. 原理与源码关键点

### 2.1 触发条件
WatchDog **仅在未指定锁的过期时间（leaseTime）时** 才会生效。
*   `lock()`：默认启用 WatchDog。
*   `lock(10, TimeUnit.SECONDS)`：**不启用** WatchDog，锁会在 10秒后强制自动释放。

### 2.2 默认配置
*   **lockWatchdogTimeout**：默认值为 **30,000 毫秒（30秒）**。这是锁的初始过期时间。

### 2.3 运行流程
1.  **加锁成功**：当客户端成功获取锁后，Redisson 会在后台启动一个 `TimeTask`（定时任务）。
2.  **定时检查**：该任务每隔 `lockWatchdogTimeout / 3`（默认 **10秒**）执行一次。
3.  **续期逻辑**：任务会检查当前线程是否还持有这把锁。
    *   **是**：执行 Lua 脚本，将锁的过期时间重置为 `lockWatchdogTimeout`（30秒）。
    *   **否**：取消定时任务。
4.  **递归执行**：一旦续期成功，会再次调度该定时任务，形成循环，直到锁被释放或客户端崩溃。

### 2.4 宕机保护
如果客户端宕机（JVM 挂掉），后台的定时续期任务也会停止。Redis 中的锁会因为不再被续期，在等待约 30 秒后自动过期，从而避免死锁。

## 3. 源码简析（Java 伪代码）

```java
// 1. 加锁时，若未指定 leaseTime，则使用默认的 lockWatchdogTimeout (30s)
long leaseTime = unit.toMillis(leaseTime);
if (leaseTime == -1) {
    // 启动 WatchDog
    scheduleExpirationRenewal(threadId);
}

// 2. 定时任务逻辑
private void scheduleExpirationRenewal(long threadId) {
    ExpirationEntry entry = EXPIRATION_RENEWAL_MAP.get(getEntryName());
    if (entry == null) return;
    
    // 3. 创建定时任务，延迟时间为 internalLockLeaseTime / 3 (10s)
    Timeout task = commandExecutor.getConnectionManager().newTimeout(new TimerTask() {
        @Override
        public void run(Timeout timeout) throws Exception {
            // 4. 异步执行 Lua 脚本进行续期
            RFuture<Boolean> future = renewExpirationAsync(threadId);
            
            future.onComplete((res, e) -> {
                if (e != null) return; // 异常处理
                if (res) {
                    // 5. 续期成功，递归调用自己，继续监听
                    scheduleExpirationRenewal(threadId);
                }
            });
        }
    }, internalLockLeaseTime / 3, TimeUnit.MILLISECONDS);
}
```

## 4. 总结

WatchDog 是 Redisson 保证分布式锁安全性的重要组件。

**面试回答示例：**
> "WatchDog 是 Redisson 用于解决'业务执行时间超长导致锁过期'问题的自动续期机制。
> 当我们调用 `lock()` 方法且未指定过期时间时，Redisson 会默认设置锁的过期时间为 30 秒，并启动一个后台定时任务。
> 这个任务每隔 10 秒（1/3 周期）检查一次，如果当前线程还持有锁，就将锁的过期时间重置为 30 秒。
> 这样既保证了业务未完成时锁不失效，又能在客户端宕机后依靠 Redis 的 TTL 机制自动释放锁，避免死锁。"
