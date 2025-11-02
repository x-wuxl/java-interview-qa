---
layout: post
title: "数据库读写分离的代码实现方案"
date: 2025-11-02
description: "详解MySQL读写分离在应用层的多种实现方案，包括Spring AOP、AbstractRoutingDataSource、ShardingSphere等技术栈"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 读写分离, Spring, 动态数据源, ShardingSphere]
---

## 问题

数据库读写分离，如何改代码？

## 答案

### 核心概念

**读写分离**是通过**主库处理写操作，从库处理读操作**，实现数据库负载分散和性能提升。代码层面需要实现**动态数据源路由**。

### 实现方案

#### 方案1：AbstractRoutingDataSource + AOP

**核心组件：**

1. **数据源上下文** - 使用ThreadLocal保存当前数据源类型
2. **动态数据源** - 继承AbstractRoutingDataSource实现路由
3. **自定义注解** - @Master和@Slave标记方法
4. **AOP切面** - 拦截注解并设置数据源

**关键代码结构：**

```
DataSourceContextHolder → 存储数据源类型
DynamicDataSource → 动态选择数据源
@Master/@Slave → 业务方法注解
DataSourceAspect → AOP切面路由
```

**优点：** 代码侵入性低，灵活控制

#### 方案2：ShardingSphere（企业级推荐）

**特点：**
- 零代码侵入，配置驱动
- 自动识别SQL类型并路由
- 支持多从库负载均衡
- 支持从库高可用

**配置示例（application.yml）：**

```yaml
spring:
  shardingsphere:
    datasource:
      names: master,slave
      master:
        jdbc-url: jdbc:mysql://master:3306/db
        username: root
        password: password
      slave:
        jdbc-url: jdbc:mysql://slave:3306/db
        username: root
        password: password
    rules:
      readwrite-splitting:
        data-sources:
          readwrite_ds:
            write-data-source-name: master
            read-data-source-names: slave
            load-balancer-name: round_robin
```

**优点：** 零侵入，自动路由，功能强大

### 关键场景处理

#### 1. 强制读主库
刚写入的数据立即查询时，需强制读主库避免主从延迟影响

#### 2. 事务内操作
同一事务内的所有操作必须使用同一数据源（主库）

#### 3. 缓存结合
写操作更新缓存，读操作先查缓存再查从库，减少主从延迟影响

### 注意事项

1. **主从延迟** - 关键数据强制读主库或使用缓存
2. **事务一致性** - 事务内所有操作走主库
3. **连接池配置** - 主库池小，从库池大
4. **监控告警** - 监控延迟和连接池状态

### 面试答题总结

读写分离代码实现主要有两种方案：

1. **AbstractRoutingDataSource + AOP**：通过自定义注解+AOP切面+ThreadLocal实现动态数据源切换，适合中型项目

2. **ShardingSphere**：零代码侵入，配置驱动，自动SQL路由和负载均衡，企业级推荐

核心技术是**AbstractRoutingDataSource + ThreadLocal**。需要注意主从延迟、事务一致性、强制读主库等场景。生产环境推荐ShardingSphere，配合缓存和监控保证系统高可用。
