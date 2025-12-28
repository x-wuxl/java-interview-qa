---
layout: post
title: "定时任务服务器宕机了，怎么解决？"
date: 2025-12-28
categories: [大厂项目场景实战, 数据库高可用]
tags: [定时任务, 高可用, XXL-JOB, 分布式调度]
description: "讲解定时任务高可用方案，包括分布式调度框架、任务分片、故障转移等机制。"
---

# 定时任务服务器宕机了，怎么解决？

## 面试场景

面试官："你们的定时任务跑在单机上，如果这台机器挂了怎么办？"

这道题考察定时任务的**高可用设计**。

---

## 单机定时任务的问题

```
        ┌─────────────┐
        │  定时任务    │
        │  服务器     │
        └──────┬──────┘
               │
               ↓
         任务执行
               │
               ↓
         服务器宕机！
               │
               ↓
         任务停止...
               │
         没人执行了！
```

**问题**：
- 单点故障
- 无法水平扩展
- 无法监控管控

---

## 解决方案：分布式调度框架

### 主流框架对比

| 框架 | 优点 | 缺点 |
|------|------|------|
| XXL-JOB | 简单易用、功能全面 | 依赖数据库 |
| Elastic-Job | 弹性扩容、失效转移 | 依赖ZK |
| SchedulerX | 阿里云托管 | 收费 |
| PowerJob | 工作流、DAG | 较新 |

---

## 方案一：XXL-JOB

### 架构图

```
┌──────────────────────────────────────────────────────┐
│                   XXL-JOB Admin                      │
│              （调度中心，可集群部署）                  │
└───────────────────────┬──────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
    │ 执行器1  │    │ 执行器2  │    │ 执行器3  │
    └─────────┘    └─────────┘    └─────────┘
```

### 高可用机制

1. **调度中心集群**：多台Admin互为备份
2. **执行器注册**：多个执行器实例
3. **路由策略**：轮询、随机、故障转移

### 核心代码

```java
@Component
public class MyJobHandler {
    
    @XxlJob("orderTimeoutJob")
    public void orderTimeoutHandler() throws Exception {
        // 查询超时未支付订单
        List<Order> orders = orderMapper.findTimeout();
        
        for (Order order : orders) {
            orderService.cancel(order.getId());
        }
        
        XxlJobHelper.log("处理超时订单: {} 个", orders.size());
    }
}
```

### 配置

```yaml
xxl:
  job:
    admin:
      addresses: http://xxl-job-admin1:8080/xxl-job-admin,http://xxl-job-admin2:8080/xxl-job-admin
    executor:
      appname: order-service
      port: 9999
```

---

## 方案二：数据库锁（简单方案）

### 原理
利用数据库的唯一约束或行锁，保证只有一个实例执行任务。

### 实现方式

```java
@Scheduled(cron = "0 0 * * * ?")  // 每小时执行
public void executeWithDbLock() {
    String taskName = "orderTimeoutTask";
    
    // 尝试获取锁（INSERT或UPDATE）
    boolean locked = taskLockMapper.tryLock(taskName, 
                                            LocalDateTime.now(),
                                            "instance-1");
    
    if (!locked) {
        log.info("其他实例正在执行，跳过");
        return;
    }
    
    try {
        doExecute();
    } finally {
        taskLockMapper.unlock(taskName);
    }
}
```

```sql
-- 锁表
CREATE TABLE task_lock (
    task_name VARCHAR(64) PRIMARY KEY,
    locked_by VARCHAR(64),
    locked_at DATETIME,
    expire_at DATETIME
);

-- 获取锁（利用唯一约束）
INSERT INTO task_lock (task_name, locked_by, locked_at, expire_at)
VALUES ('orderTimeoutTask', 'instance-1', NOW(), DATE_ADD(NOW(), INTERVAL 10 MINUTE))
ON DUPLICATE KEY UPDATE
    locked_by = IF(expire_at < NOW(), VALUES(locked_by), locked_by),
    locked_at = IF(expire_at < NOW(), VALUES(locked_at), locked_at),
    expire_at = IF(expire_at < NOW(), VALUES(expire_at), expire_at);
```

---

## 方案三：Redis分布式锁

```java
@Scheduled(cron = "0 0 * * * ?")
public void executeWithRedisLock() {
    String lockKey = "task:lock:orderTimeout";
    String requestId = UUID.randomUUID().toString();
    
    // 尝试获取锁
    boolean locked = redis.opsForValue()
        .setIfAbsent(lockKey, requestId, 10, TimeUnit.MINUTES);
    
    if (!locked) {
        log.info("其他实例正在执行，跳过");
        return;
    }
    
    try {
        doExecute();
    } finally {
        // 释放锁（确保只释放自己的锁）
        String script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            end
            return 0
            """;
        redis.execute(new DefaultRedisScript<>(script, Long.class),
            List.of(lockKey), requestId);
    }
}
```

---

## 任务分片

### 场景
需要处理100万订单，单机处理太慢。

### XXL-JOB分片

```java
@XxlJob("bigDataJob")
public void bigDataHandler() throws Exception {
    // 获取分片参数
    int shardIndex = XxlJobHelper.getShardIndex();
    int shardTotal = XxlJobHelper.getShardTotal();
    
    // 按分片处理数据
    List<Order> orders = orderMapper.findByMod(shardTotal, shardIndex);
    
    for (Order order : orders) {
        process(order);
    }
    
    XxlJobHelper.log("分片{}/{}，处理{}条", shardIndex, shardTotal, orders.size());
}
```

```sql
-- 按取模分片查询
SELECT * FROM orders WHERE MOD(id, #{shardTotal}) = #{shardIndex}
```

---

## 故障转移

### XXL-JOB路由策略

```
任务配置：
  路由策略：故障转移（FAILOVER）
  执行器：executor1, executor2, executor3
  
执行流程：
  1. 尝试executor1 → 失败
  2. 尝试executor2 → 成功
  3. 任务在executor2执行
```

### 配置方式
在XXL-JOB Admin控制台选择路由策略为"故障转移"。

---

## 幂等设计

无论哪种高可用方案，都要保证任务**幂等**。

```java
@XxlJob("orderTimeoutJob")
public void orderTimeoutHandler() {
    List<Order> orders = orderMapper.findTimeoutUnprocessed();
    
    for (Order order : orders) {
        // 乐观锁保证幂等
        int affected = orderMapper.markProcessing(order.getId(), order.getVersion());
        if (affected == 0) {
            continue;  // 已被其他实例处理
        }
        
        orderService.cancel(order.getId());
    }
}
```

---

## 面试答题框架

```
问题分析：
- 单点故障
- 任务中断无感知
- 无法水平扩展

解决方案：
1. 分布式调度框架（XXL-JOB/Elastic-Job）
2. 数据库锁/Redis锁（简单场景）

高可用机制：
- 调度中心集群
- 执行器多实例
- 故障转移路由
- 任务分片

关键设计：
- 幂等性保证
- 执行日志监控
- 失败重试策略
```

---

## 总结

| 方案 | 复杂度 | 适用场景 |
|------|--------|----------|
| XXL-JOB | 中 | 通用场景，推荐 |
| 数据库锁 | 低 | 简单场景 |
| Redis锁 | 低 | 简单场景 |
| Elastic-Job | 高 | 大规模分片 |
