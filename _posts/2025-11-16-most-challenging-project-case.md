---
layout: post
title: "介绍你做过的最具挑战性的项目、负责的模块以及应对方案。"
date: 2025-11-16
categories: ["系统设计与高并发实战"]
tags: ["项目经验", "高并发", "系统稳定性"]
description: "回顾高并发项目的挑战、负责模块与解决方案。"
---

### 核心概念
以“百亿级流量的双十一营销平台”为例，我负责的模块是实时优惠结算与风控。核心目标：在秒级流量洪峰下保证价格准确、风控可控、系统稳定。

### 原理或源码关键点
1. **架构设计**：采用微服务拆分为下单、优惠、库存、风控四域；优惠计算服务基于 Spring Cloud + gRPC，内部通过规则引擎（Drools）+ 缓存。
2. **数据链路**：Redis 多级缓存（本地 Caffeine + Redis Cluster）承载优惠规则，Kafka 流水写入以供审计；库存模块采用 RocketMQ 可靠事件驱动。
3. **风控策略**：实时流量在 Flink 中聚合埋点，计算用户风险分；风控结果通过 Redis TTL + Bloom Filter 与下单链路同步。
4. **故障演练**：接入 Sentinel 进行限流熔断，配合灰度发布和自动扩容；日志链路使用 ELK + 自研链路追踪便于定位。

### 性能与高并发考量
- 高峰期部署 200+ Pod，QPS 过百万；通过异步化（CompletableFuture）将平均响应压缩至 80ms。
- 采用多活部署，Redis 与 MQ 均做跨 AZ 同步；关键写操作具备幂等和补偿机制。
- 引入自动调参：根据 Prometheus 指标动态调整线程池和限流阈值。

### 示例与总结
```java
CompletableFuture<Pricing> pricing = CompletableFuture.supplyAsync(() -> pricingService.calc(ctx));
CompletableFuture<Risk> risk = CompletableFuture.supplyAsync(() -> riskService.check(ctx));
OrderResult result = pricing.thenCombine(risk, this::merge).get(100, TimeUnit.MILLISECONDS);
```
该项目的经验在于“服务拆分 + 流量治理 + 数据校验”三层防护：结构上消峰分治，执行上异步化、缓存化，治理上实时监控与压测演练，最终保障了活动零事故。
