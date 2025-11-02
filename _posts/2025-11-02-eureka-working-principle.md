---
layout: post
title: "Eureka的工作原理是什么？"
date: 2025-11-02
categories: [Spring框架, SpringCloud, 服务注册]
tags: [Eureka, 服务发现, 微服务, SpringCloud]
description: "深入理解Eureka服务注册与发现的工作原理、核心机制及高可用设计"
---

## 核心概念

**Eureka**是Netflix开源的服务注册与发现组件，采用**AP模型**（可用性和分区容错性），是SpringCloud生态中服务治理的核心组件之一。

### 架构角色

```
┌──────────────────────────────────────────┐
│             Eureka架构                    │
├──────────────────────────────────────────┤
│  Eureka Server                           │
│  ├─ 服务注册表（Registry）                │
│  ├─ 接收心跳（Heartbeat）                 │
│  └─ 提供服务列表                          │
│                                          │
│  Eureka Client                           │
│  ├─ 服务提供者（Provider）                │
│  │  ├─ 注册服务                          │
│  │  └─ 发送心跳                          │
│  └─ 服务消费者（Consumer）                │
│     └─ 获取服务列表                       │
└──────────────────────────────────────────┘
```

## 工作流程

### 1. 服务注册（Register）

```java
// 服务提供者启动时注册
@SpringBootApplication
@EnableEurekaClient
public class UserServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(UserServiceApplication.class, args);
    }
}
```

**注册流程**：
1. 服务启动时，读取配置文件中的服务名、IP、端口等信息
2. 向Eureka Server发送REST请求：`POST /eureka/apps/{serviceName}`
3. Eureka Server将服务信息存入注册表（ConcurrentHashMap）
4. 默认服务状态为**UP**

```yaml
eureka:
  client:
    service-url:
      defaultZone: http://localhost:8761/eureka/
  instance:
    instance-id: ${spring.application.name}:${server.port}
    prefer-ip-address: true  # 优先使用IP注册
```

### 2. 心跳续约（Renew）

**心跳机制**：
- 默认每**30秒**发送一次心跳
- Eureka Server收到心跳后更新服务的最后心跳时间
- 如果90秒未收到心跳，触发服务剔除

```java
// DiscoveryClient核心源码
class DiscoveryClient {
    // 心跳任务
    private class HeartbeatThread implements Runnable {
        public void run() {
            if (renew()) {
                // 续约成功
                lastSuccessfulHeartbeatTimestamp = System.currentTimeMillis();
            }
        }
    }
    
    boolean renew() {
        // 发送心跳到Eureka Server
        EurekaHttpResponse<InstanceInfo> httpResponse = 
            eurekaTransport.registrationClient.sendHeartBeat(
                instanceInfo.getAppName(),
                instanceInfo.getId(),
                instanceInfo,
                null
            );
        return httpResponse.getStatusCode() == 200;
    }
}
```

配置优化：
```yaml
eureka:
  instance:
    lease-renewal-interval-in-seconds: 30  # 心跳间隔（默认30s）
    lease-expiration-duration-in-seconds: 90  # 过期时间（默认90s）
```

### 3. 服务发现（Fetch）

**获取服务列表**：
- 客户端启动时从Eureka Server拉取全量注册表
- 之后每**30秒**增量拉取更新
- 客户端本地缓存服务列表

```java
@Service
public class OrderService {
    @Autowired
    private DiscoveryClient discoveryClient;
    
    public void callUserService() {
        // 从本地缓存获取服务实例
        List<ServiceInstance> instances = 
            discoveryClient.getInstances("user-service");
        
        if (!instances.isEmpty()) {
            ServiceInstance instance = instances.get(0);
            String url = "http://" + instance.getHost() + ":" 
                       + instance.getPort() + "/api/users";
            // 发起调用
        }
    }
}
```

**多级缓存机制**：
```
Client Request
    ↓
ReadOnlyCache（每30s同步）
    ↓
ReadWriteCache（实时更新）
    ↓
Registry（注册表）
```

配置：
```yaml
eureka:
  client:
    fetch-registry: true  # 拉取注册表
    registry-fetch-interval-seconds: 30  # 拉取间隔
```

### 4. 服务下线（Cancel）

**正常下线**：
- 服务关闭时发送REST请求：`DELETE /eureka/apps/{serviceName}/{instanceId}`
- Eureka Server立即移除该实例

**异常下线**：
- 心跳超时（默认90秒）
- Eureka Server执行剔除任务（每60秒执行一次）

```java
// 服务关闭时触发
@PreDestroy
public void destroy() {
    // 自动向Eureka发送下线请求
}
```

### 5. 自我保护机制

**触发条件**：
- 15分钟内心跳成功率低于85%
- 网络分区导致大量服务心跳失败

**保护措施**：
- **不再剔除任何服务实例**（宁可保留错误信息，也不误删正确信息）
- Eureka Server页面显示红色警告

```yaml
eureka:
  server:
    enable-self-preservation: true  # 开启自我保护（默认true）
    eviction-interval-timer-in-ms: 60000  # 剔除任务间隔
    renewal-percent-threshold: 0.85  # 心跳阈值
```

**源码逻辑**：
```java
public class PeerAwareInstanceRegistryImpl {
    public void evict() {
        // 判断是否触发自我保护
        if (!isLeaseExpirationEnabled()) {
            return;  // 自我保护开启，跳过剔除
        }
        
        // 查找过期实例
        List<Lease<InstanceInfo>> expiredLeases = new ArrayList<>();
        for (Entry<String, Map<String, Lease<InstanceInfo>>> entry : registry.entrySet()) {
            for (Entry<String, Lease<InstanceInfo>> leaseEntry : entry.getValue().entrySet()) {
                if (leaseEntry.getValue().isExpired()) {
                    expiredLeases.add(leaseEntry.getValue());
                }
            }
        }
        
        // 剔除过期实例
        for (Lease<InstanceInfo> lease : expiredLeases) {
            internalCancel(lease.getHolder().getAppName(), 
                          lease.getHolder().getId(), false);
        }
    }
}
```

## Eureka Server集群

### 高可用设计

```yaml
# Eureka Server 1 配置
eureka:
  instance:
    hostname: eureka1
  client:
    service-url:
      defaultZone: http://eureka2:8762/eureka/,http://eureka3:8763/eureka/

# Eureka Server 2 配置
eureka:
  instance:
    hostname: eureka2
  client:
    service-url:
      defaultZone: http://eureka1:8761/eureka/,http://eureka3:8763/eureka/
```

**集群同步机制**：
- Eureka Server之间**互相注册**
- 接收到注册请求后，**同步复制**到其他节点
- 采用**最终一致性**模型

```java
// 集群复制源码
public class PeerAwareInstanceRegistryImpl {
    @Override
    public void register(InstanceInfo info, boolean isReplication) {
        // 本地注册
        super.register(info, isReplication);
        
        // 同步到其他节点
        if (!isReplication) {
            replicateToPeers(Action.Register, info.getAppName(), 
                           info.getId(), info, null, isReplication);
        }
    }
    
    private void replicateToPeers(Action action, String appName, 
                                 String id, InstanceInfo info, 
                                 InstanceStatus newStatus, 
                                 boolean isReplication) {
        for (PeerEurekaNode node : peerEurekaNodes.getPeerEurekaNodes()) {
            // 向每个节点发送同步请求
            node.register(info);
        }
    }
}
```

## 核心数据结构

### 注册表结构

```java
// 双层Map结构
ConcurrentHashMap<String, Map<String, Lease<InstanceInfo>>> registry;
// 第一层Key: 服务名（如user-service）
// 第二层Key: 实例ID（如user-service:8080）
// Value: Lease（租约对象，包含服务信息和最后心跳时间）

public class Lease<T> {
    T holder;  // InstanceInfo
    long evictionTimestamp;  // 剔除时间戳
    long registrationTimestamp;  // 注册时间戳
    long lastUpdateTimestamp;  // 最后更新时间
}
```

### 缓存机制

```java
public class ResponseCacheImpl {
    // 读写缓存（Guava Cache）
    private final LoadingCache<Key, Value> readWriteCacheMap;
    
    // 只读缓存（ConcurrentMap）
    private final ConcurrentMap<Key, Value> readOnlyCacheMap;
    
    // 定时任务：每30秒同步readWrite到readOnly
    private void updateReadOnlyCache() {
        for (Key key : readOnlyCacheMap.keySet()) {
            Value cacheValue = readWriteCacheMap.get(key);
            Value currentValue = readOnlyCacheMap.get(key);
            if (cacheValue != currentValue) {
                readOnlyCacheMap.put(key, cacheValue);
            }
        }
    }
}
```

## 关键配置优化

### 快速感知服务下线

```yaml
# 服务端配置
eureka:
  server:
    eviction-interval-timer-in-ms: 5000  # 剔除间隔改为5秒
    enable-self-preservation: false  # 开发环境关闭自我保护
    
# 客户端配置
eureka:
  instance:
    lease-renewal-interval-in-seconds: 5  # 心跳间隔5秒
    lease-expiration-duration-in-seconds: 10  # 10秒未心跳则过期
  client:
    registry-fetch-interval-seconds: 5  # 5秒拉取一次注册表
```

**注意**：生产环境不建议过度缩短时间，会增加网络开销。

### 生产环境配置

```yaml
eureka:
  server:
    enable-self-preservation: true  # 开启自我保护
    eviction-interval-timer-in-ms: 60000
  instance:
    lease-renewal-interval-in-seconds: 30
    lease-expiration-duration-in-seconds: 90
  client:
    registry-fetch-interval-seconds: 30
```

## Eureka vs Nacos

| 对比项 | Eureka | Nacos |
|--------|--------|-------|
| CAP模型 | AP（最终一致性） | AP+CP可切换 |
| 健康检查 | 客户端心跳 | TCP/HTTP/MySQL |
| 配置管理 | 不支持 | 支持 |
| 监控界面 | 简单 | 功能强大 |
| 社区维护 | 已停更 | 活跃 |

## 面试总结

Eureka工作原理包括**服务注册、心跳续约、服务发现、服务下线**四个核心流程：

1. **服务注册**：服务启动时向Eureka Server注册，存入双层Map结构的注册表
2. **心跳续约**：每30秒发送心跳，90秒未心跳则触发剔除
3. **服务发现**：客户端启动拉取全量注册表，之后每30秒增量更新，采用多级缓存优化性能
4. **自我保护**：心跳失败率超过15%时，不再剔除服务，防止网络分区误删

Eureka采用**AP模型**，保证高可用但牺牲强一致性；集群通过互相注册实现高可用；核心数据结构是ConcurrentHashMap + Lease租约机制。生产环境建议开启自我保护，使用默认心跳配置。目前Eureka已停止维护，新项目推荐使用Nacos替代。

