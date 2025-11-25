---
layout: default
title: "Nacos和Eureka的区别？"
parent: 微服务
nav_order: 527
description: "深入对比Nacos和Eureka的核心差异、技术选型及适用场景"
date: 2025-11-02
---
## 核心概念

**Eureka**是Netflix开源的服务注册与发现组件，采用AP模型（可用性优先）。

**Nacos**（Dynamic Naming and Configuration Service）是阿里巴巴开源的动态服务发现、配置管理平台，同时支持AP和CP模型。

## 核心区别对比

### 1. CAP模型

| 维度 | Eureka | Nacos |
|------|--------|-------|
| CAP选择 | **AP**（可用性+分区容错）| **AP/CP可切换** |
| 一致性 | 最终一致性 | 支持强一致性（CP模式）|
| 适用场景 | 对一致性要求不高 | 可根据场景选择 |

#### Eureka - AP模型

```
特点：
- 服务注册表可能不一致
- 自我保护机制（宁可保留过期数据）
- 高可用但弱一致性

示例：
节点A: user-service实例 [192.168.1.10, 192.168.1.11]
节点B: user-service实例 [192.168.1.10, 192.168.1.12]
（网络分区导致数据不一致，但服务仍可用）
```

#### Nacos - AP/CP可切换

```yaml
# Nacos配置
spring:
  cloud:
    nacos:
      discovery:
        # AP模式（临时实例，默认）
        ephemeral: true
        
        # CP模式（持久化实例）
        # ephemeral: false
```

**AP模式**（临时实例）：
- 心跳上报，服务端主动剔除
- 类似Eureka，高可用
- 适合云原生、微服务场景

**CP模式**（持久化实例）：
- Raft协议保证强一致性
- 服务端主动健康检查
- 适合DNS、配置中心场景

### 2. 功能对比

| 功能 | Eureka | Nacos |
|------|--------|-------|
| 服务注册发现 | ✅ | ✅ |
| 健康检查 | 客户端心跳 | TCP/HTTP/MySQL多种方式 |
| 配置管理 | ❌ 需Config Server | ✅ 内置配置中心 |
| 负载均衡 | 需集成Ribbon | 内置权重负载均衡 |
| 命名空间 | ❌ | ✅ 支持多环境隔离 |
| 分组管理 | ❌ | ✅ 支持分组 |
| 元数据 | 支持 | 支持更丰富 |
| 权限控制 | ❌ | ✅ 支持ACL |
| 控制台 | 简单 | 功能强大 |

### 3. 健康检查机制

#### Eureka健康检查

```java
// 客户端主动上报心跳
@Scheduled(fixedDelay = 30000)  // 每30秒
public void sendHeartbeat() {
    eurekaClient.sendHeartBeat();
}

// 配置
eureka:
  instance:
    lease-renewal-interval-in-seconds: 30  # 心跳间隔
    lease-expiration-duration-in-seconds: 90  # 过期时间
```

**特点**：
- 客户端主动心跳
- 服务端被动剔除（90秒未心跳）
- 简单但不够灵活

#### Nacos健康检查

```yaml
spring:
  cloud:
    nacos:
      discovery:
        heart-beat-interval: 5000  # 心跳间隔（临时实例）
        heart-beat-timeout: 15000  # 心跳超时
        ip-delete-timeout: 30000  # 实例删除超时
```

**临时实例（AP模式）**：
- 客户端主动心跳
- 15秒未心跳标记不健康
- 30秒未心跳删除实例

**持久化实例（CP模式）**：
```yaml
spring:
  cloud:
    nacos:
      discovery:
        ephemeral: false  # 持久化实例
        metadata:
          preserved.heart.beat.interval: 5000
          preserved.heart.beat.timeout: 15000
          preserved.ip.delete.timeout: 30000
```
- 服务端主动探测（TCP/HTTP/MySQL）
- 探测失败标记不健康，但不删除
- 需要手动下线

### 4. 架构对比

#### Eureka架构

```
┌─────────────────────────────────────┐
│      Eureka Server Cluster          │
│  ┌──────────┐      ┌──────────┐    │
│  │ Server 1 │ ←──→ │ Server 2 │    │
│  └──────────┘      └──────────┘    │
│       ↑                  ↑          │
│       │  互相复制         │          │
└───────┼──────────────────┼──────────┘
        │                  │
    ┌───┴───┐          ┌───┴───┐
    │Client1│          │Client2│
    └───────┘          └───────┘
```

**特点**：
- Peer-to-Peer对等复制
- 无主从，每个节点平等
- 最终一致性

#### Nacos架构

```
┌────────────────────────────────────────┐
│         Nacos Server Cluster           │
│  ┌────────┐  ┌────────┐  ┌────────┐   │
│  │Leader  │→ │Follower│→ │Follower│   │
│  │(Raft)  │← │        │← │        │   │
│  └────────┘  └────────┘  └────────┘   │
│       ↑          ↑          ↑          │
└───────┼──────────┼──────────┼──────────┘
        │          │          │
    ┌───┴──┐   ┌───┴──┐   ┌───┴──┐
    │Client│   │Client│   │Client│
    └──────┘   └──────┘   └──────┘
```

**特点**（CP模式）：
- Raft一致性协议
- Leader负责写入，Follower同步
- 强一致性

### 5. 命名空间与分组

#### Eureka

```yaml
# 只能通过服务名隔离
eureka:
  instance:
    appname: user-service-dev  # 通过命名区分环境
```

#### Nacos

```yaml
spring:
  cloud:
    nacos:
      discovery:
        namespace: dev  # 命名空间（环境隔离）
        group: DEFAULT_GROUP  # 分组（业务隔离）
        service: user-service
```

**多级隔离**：
```
Namespace(命名空间): dev / test / prod
    ↓
Group(分组): order-group / user-group
    ↓
Service(服务): user-service / order-service
    ↓
Cluster(集群): BJ / SH / GZ
    ↓
Instance(实例): 192.168.1.10:8080
```

### 6. 配置管理

#### Eureka

```
不支持配置管理，需要额外使用：
- Spring Cloud Config
- Apollo
- 其他配置中心
```

#### Nacos

```java
// 同时支持服务注册和配置管理
@SpringBootApplication
@EnableDiscoveryClient  // 服务注册
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}

@RestController
@RefreshScope  // 动态刷新配置
public class ConfigController {
    @Value("${config.info}")
    private String configInfo;
    
    @GetMapping("/config")
    public String getConfig() {
        return configInfo;
    }
}
```

```yaml
# bootstrap.yml
spring:
  cloud:
    nacos:
      config:
        server-addr: localhost:8848
        namespace: dev
        group: DEFAULT_GROUP
        file-extension: yaml
        refresh-enabled: true  # 自动刷新
      discovery:
        server-addr: localhost:8848
        namespace: dev
```

**Nacos配置特性**：
- ✅ 统一配置管理
- ✅ 动态配置推送
- ✅ 版本管理与回滚
- ✅ 灰度发布
- ✅ 配置加密

### 7. 权重负载均衡

#### Eureka

```java
// 需要自定义Ribbon策略
@Configuration
public class RibbonConfig {
    @Bean
    public IRule ribbonRule() {
        return new WeightedResponseTimeRule();  // 基于响应时间的权重
    }
}
```

#### Nacos

```java
// 内置权重负载均衡
@GetMapping("/user/{id}")
public User getUser(@PathVariable Long id) {
    // Nacos自动根据权重选择实例
    return restTemplate.getForObject("http://user-service/users/" + id, User.class);
}
```

```yaml
# 设置实例权重（0-1，默认1）
spring:
  cloud:
    nacos:
      discovery:
        weight: 0.5  # 权重0.5（接收一半流量）
```

**应用场景**：
- 灰度发布：新版本权重0.1，老版本0.9
- 机器性能差异：高配置机器权重1，低配置0.5

### 8. 社区与维护

| 维度 | Eureka | Nacos |
|------|--------|-------|
| 开发公司 | Netflix | 阿里巴巴 |
| 开源时间 | 2012年 | 2018年 |
| 维护状态 | **2018年停更** | **活跃维护** |
| GitHub Stars | 12k+ | 29k+ |
| 社区活跃度 | 低 | 高 |
| 中文文档 | 较少 | 丰富 |
| Spring Cloud版本 | 集成良好 | 集成良好 |

## 性能对比

### 注册性能

| 指标 | Eureka | Nacos（AP） | Nacos（CP） |
|------|--------|-------------|-------------|
| TPS | ~10000 | ~15000 | ~5000 |
| 延迟 | 低 | 低 | 中等 |

### 查询性能

| 指标 | Eureka | Nacos |
|------|--------|-------|
| QPS | ~30000 | ~50000+ |
| 内存占用 | 较高 | 较低 |

### 服务感知速度

| 场景 | Eureka | Nacos（AP） | Nacos（CP） |
|------|--------|-------------|-------------|
| 服务上线 | 30秒+ | 5秒左右 | 实时 |
| 服务下线 | 90秒+ | 15秒左右 | 实时 |

## 实战对比

### 1. 服务注册

#### Eureka

```xml
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-netflix-eureka-client</artifactId>
</dependency>
```

```java
@SpringBootApplication
@EnableEurekaClient
public class UserServiceApplication {
    // ...
}
```

```yaml
eureka:
  client:
    service-url:
      defaultZone: http://localhost:8761/eureka/
  instance:
    prefer-ip-address: true
```

#### Nacos

```xml
<dependency>
    <groupId>com.alibaba.cloud</groupId>
    <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
</dependency>
```

```java
@SpringBootApplication
@EnableDiscoveryClient
public class UserServiceApplication {
    // ...
}
```

```yaml
spring:
  cloud:
    nacos:
      discovery:
        server-addr: localhost:8848
        namespace: dev
        group: DEFAULT_GROUP
```

### 2. 服务发现

#### Eureka

```java
@Autowired
private DiscoveryClient discoveryClient;

public List<ServiceInstance> getInstances() {
    return discoveryClient.getInstances("user-service");
}
```

#### Nacos

```java
@Autowired
private DiscoveryClient discoveryClient;

// 相同的API
public List<ServiceInstance> getInstances() {
    return discoveryClient.getInstances("user-service");
}

// Nacos特有API（获取带权重实例）
@Autowired
private NacosDiscoveryClient nacosDiscoveryClient;

public List<ServiceInstance> getHealthyInstances() {
    return nacosDiscoveryClient.getInstances("user-service", true);
}
```

### 3. 元数据

#### Eureka

```yaml
eureka:
  instance:
    metadata-map:
      zone: beijing
      version: v1.0
```

#### Nacos

```yaml
spring:
  cloud:
    nacos:
      discovery:
        metadata:
          zone: beijing
          version: v1.0
          preserved.register.source: SPRING_CLOUD  # 内置元数据
```

## 技术选型建议

### 选择Eureka的场景

- ❌ **不推荐新项目使用**（已停止维护）
- ✅ 已有项目稳定运行，无迁移需求
- ✅ 团队熟悉Netflix技术栈

### 选择Nacos的场景

- ✅ **新项目强烈推荐**
- ✅ 需要配置管理功能
- ✅ 需要多环境/多租户隔离
- ✅ 需要更好的性能和更快的感知速度
- ✅ 需要CP模式保证强一致性
- ✅ 中文文档和社区支持

### 从Eureka迁移到Nacos

```yaml
# 1. 修改依赖
# 移除 spring-cloud-starter-netflix-eureka-client
# 添加 spring-cloud-starter-alibaba-nacos-discovery

# 2. 修改配置
spring:
  cloud:
    nacos:
      discovery:
        server-addr: localhost:8848  # Nacos地址
        # namespace: dev  # 可选：命名空间
        # group: DEFAULT_GROUP  # 可选：分组

# 3. 修改启动类注解（可选）
# @EnableEurekaClient → @EnableDiscoveryClient

# 4. 业务代码无需修改（兼容Spring Cloud标准API）
```

## 高级特性对比

### 1. 同步模式

| 特性 | Eureka | Nacos |
|------|--------|-------|
| 集群同步 | Peer-to-Peer | Raft（CP）/ Distro（AP） |
| 数据同步 | 异步复制 | 同步/异步可选 |
| 脑裂处理 | 自我保护 | Raft选举 |

### 2. 持久化

| 特性 | Eureka | Nacos |
|------|--------|-------|
| 数据持久化 | 内存（不持久化）| 支持MySQL持久化 |
| 重启后 | 数据丢失 | 数据恢复 |

### 3. 服务订阅推送

| 特性 | Eureka | Nacos |
|------|--------|-------|
| 推送模式 | 客户端定时拉取（30秒）| UDP推送 + 定时拉取 |
| 实时性 | 较差 | 较好 |

## 面试总结

**Nacos vs Eureka核心区别**：

1. **CAP模型**：
   - Eureka：AP（可用性优先）
   - Nacos：AP/CP可切换

2. **功能**：
   - Eureka：只支持服务注册发现
   - Nacos：服务注册发现 + 配置管理 + 更多高级特性

3. **健康检查**：
   - Eureka：客户端心跳（90秒过期）
   - Nacos：多种方式（TCP/HTTP/MySQL），更快感知（15秒）

4. **隔离机制**：
   - Eureka：无命名空间和分组
   - Nacos：支持Namespace + Group多级隔离

5. **性能**：
   - Nacos在注册、查询、感知速度上全面优于Eureka

6. **社区**：
   - Eureka：2018年停止维护
   - Nacos：活跃维护，功能持续更新

**选型建议**：
- 新项目：**强烈推荐Nacos**
- 老项目：评估迁移成本，逐步迁移到Nacos
- 不推荐继续使用Eureka

**迁移成本**：低（API兼容，主要修改配置）

