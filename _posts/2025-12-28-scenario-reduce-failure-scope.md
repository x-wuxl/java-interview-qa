---
layout: post
title: "如何缩小系统故障的影响范围？"
date: 2025-12-28
categories: [大厂项目场景实战, 系统高可用]
tags: [高可用, 隔离, 灰度发布, 单元化, 资源隔离]
description: "从故障隔离、资源隔离、流量隔离、灰度发布四个维度，讲解如何控制故障爆炸半径。"
---

# 如何缩小系统故障的影响范围？

## 面试场景

面试官："你的系统出了问题，如何保证不会影响所有用户？"

这道题考察的是**故障隔离能力**，核心目标是**控制爆炸半径**，即使出问题也只影响一小部分用户或功能。

---

## 核心思想：隔离

```
单点故障 ──隔离──> 局部故障
     │                  │
  影响所有用户      只影响部分用户
```

隔离的本质是**划分故障域**，让故障只在某个边界内传播。

---

## 策略一：服务隔离

### 核心读写分离

将读和写请求分离到不同的服务实例，写故障不影响读。

```
     ┌─────────────────────────────────────┐
     │            API Gateway              │
     └────────────┬───────────┬────────────┘
                  │           │
           ┌──────┴───┐ ┌─────┴──────┐
           │ 读服务集群 │ │ 写服务集群   │
           │ (可降级)  │ │ (核心保护) │
           └──────────┘ └────────────┘
```

### 核心和非核心分离

```java
// 线程池隔离示例
@Bean("coreExecutor")
public ThreadPoolExecutor coreExecutor() {
    return new ThreadPoolExecutor(50, 100, 60, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(1000),
        new ThreadPoolExecutor.AbortPolicy());  // 核心任务拒绝策略
}

@Bean("nonCoreExecutor")
public ThreadPoolExecutor nonCoreExecutor() {
    return new ThreadPoolExecutor(10, 20, 60, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(100),
        new ThreadPoolExecutor.DiscardPolicy()); // 非核心直接丢弃
}
```

---

## 策略二：资源隔离

### 线程池隔离

不同调用方/接口使用独立线程池，防止慢接口拖垮整个服务。

```java
// Hystrix线程池隔离配置
@HystrixCommand(
    commandKey = "getOrder",
    threadPoolKey = "orderPool",  // 独立线程池
    threadPoolProperties = {
        @HystrixProperty(name = "coreSize", value = "20"),
        @HystrixProperty(name = "maxQueueSize", value = "100")
    }
)
public Order getOrder(Long orderId) {
    return orderClient.get(orderId);
}
```

### 数据库连接池隔离

不同业务使用不同的数据源，避免慢查询耗尽所有连接。

```yaml
# 多数据源配置
spring:
  datasource:
    core:  # 核心业务数据源
      url: jdbc:mysql://core-db:3306/order
      maximum-pool-size: 50
    report:  # 报表数据源
      url: jdbc:mysql://report-db:3306/order  # 从库
      maximum-pool-size: 10
```

### 信号量隔离

适用于本地调用，开销更小。

```java
// Sentinel信号量隔离
@SentinelResource(
    value = "localMethod",
    entryType = EntryType.IN,
    resourceType = ResourceTypeConstants.COMMON
)
public void localMethod() {
    // ...
}
```

---

## 策略三：流量隔离

### 灰度发布

新版本先只对部分用户生效，验证无问题后再全量发布。

```
全量用户
    │
    ├── 1% 用户 ──> 新版本 v2.0
    │
    └── 99% 用户 ──> 稳定版本 v1.9
```

**灰度策略**：
- 按用户ID尾号分流
- 按地域分流  
- 按渠道分流

### 多租户隔离

SaaS场景下，不同租户使用独立的资源配额。

```java
// 租户限流示例
public void handleRequest(String tenantId, Request request) {
    RateLimiter limiter = tenantLimiters.computeIfAbsent(tenantId, 
        k -> RateLimiter.create(getTenantQps(k)));
    
    if (!limiter.tryAcquire()) {
        throw new TenantRateLimitException(tenantId);
    }
    // 处理请求...
}
```

---

## 策略四：单元化架构

### 什么是单元化？

将用户请求按规则（如城市ID）路由到不同的**逻辑单元**，每个单元内是完整闭环，单元间完全隔离。

```
                   ┌── 单元A（北京用户）
                   │    - 应用服务
用户请求 → 路由层 ─┼    - 数据库
                   │    - 缓存
                   │
                   └── 单元B（上海用户）
                        - 应用服务
                        - 数据库
                        - 缓存
```

### 典型案例

- **美团外卖**：按城市ID分单元（Set化）
- **阿里巴巴**：按用户ID分单元（Cell化）

### 单元化的优势

1. **故障隔离**：一个单元故障不影响其他单元
2. **容灾切换**：可以快速切换用户到其他单元
3. **弹性扩容**：按单元独立扩容

---

## 策略五：发布隔离

### 分批发布

不要一次性全量发布，分批逐步放量。

```
第1批：1台机器 → 观察10分钟
第2批：10%机器 → 观察10分钟
第3批：50%机器 → 观察10分钟
第4批：全量
```

### 蓝绿发布

同时维护两套环境，通过流量切换实现发布。

```
         ┌── 蓝环境（当前生产）
用户 ───┤
         └── 绿环境（新版本）← 发布到这里
                 ↓
      验证通过后，切换流量到绿环境
```

### 金丝雀发布

小流量验证后再逐步放大。

```java
// 金丝雀路由规则
@Component
public class CanaryRouter {
    public String route(String userId) {
        // 1%流量到新版本
        if (userId.hashCode() % 100 < 1) {
            return "v2";
        }
        return "v1";
    }
}
```

---

## 面试答题要点

1. **明确目标**：控制爆炸半径，不让单点故障演变为全局故障
2. **分层阐述**：服务隔离、资源隔离、流量隔离、单元化
3. **结合场景**：说明每种隔离策略的适用场景
4. **提及工具**：Hystrix线程池隔离、灰度发布平台等

---

## 总结

缩小故障影响范围的核心策略：

| 策略 | 方式 | 效果 |
|------|------|------|
| 服务隔离 | 读写分离、核心/非核心分离 | 功能级隔离 |
| 资源隔离 | 线程池、连接池隔离 | 资源不互抢 |
| 流量隔离 | 灰度发布、多租户 | 用户级隔离 |
| 单元化 | 按业务维度分单元 | 物理级隔离 |
| 发布隔离 | 分批/蓝绿/金丝雀 | 降低发布风险 |
