---
layout: post
title: "Nacos 如何实现服务注册与发现"
date: 2025-11-07
categories: [中间件, Nacos, 服务注册]
tags: [Nacos, 服务注册, 服务发现, 微服务, 分布式]
description: "深入解析Nacos服务注册与发现的核心实现原理，包括AP/CP模式、注册流程、发现机制及源码关键点"
---

## 核心概念

**Nacos**（Dynamic Naming and Configuration Service）是阿里巴巴开源的服务注册与发现、配置管理平台。服务注册与发现是Nacos的核心功能，支持**AP模式**（临时实例）和**CP模式**（持久化实例）两种模型。

**核心组件**：
- **NamingService**：服务注册与发现的客户端接口
- **ServiceRegistry**：服务注册表，存储服务实例信息
- **Distro协议**：AP模式下的数据同步协议
- **Raft协议**：CP模式下的强一致性协议

## 服务注册实现原理

### 1. 注册流程

```java
// 客户端注册服务
@SpringBootApplication
@EnableDiscoveryClient
public class UserServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(UserServiceApplication.class, args);
    }
}
```

**注册步骤**：
1. 客户端启动时，读取配置（服务名、IP、端口、命名空间等）
2. 构建`Instance`对象，包含服务元数据
3. 调用`NacosNamingService.registerInstance()`方法
4. 发送HTTP请求到Nacos Server：`POST /nacos/v1/ns/instance`
5. Server将实例信息写入内存注册表（ConcurrentHashMap）
6. 根据模式选择同步策略（AP模式用Distro，CP模式用Raft）

### 2. 注册表数据结构

```java
// Nacos Server端核心数据结构
public class ServiceManager {
    // 服务注册表：Map<namespace, Map<group::serviceName, Service>>
    private final ConcurrentHashMap<String, ConcurrentHashMap<String, Service>> serviceMap;
    
    // 实例存储：Service -> Set<Instance>
    public class Service {
        private String namespaceId;
        private String name;  // serviceName
        private String groupName;
        private Map<String, Cluster> clusterMap;  // 集群信息
        
        public class Cluster {
            private String name;
            private Set<Instance> persistentInstances;  // 持久化实例
            private Set<Instance> ephemeralInstances;   // 临时实例
        }
    }
}
```

**数据结构特点**：
- **三级索引**：Namespace → Group::ServiceName → Cluster → Instance
- **实例分类**：临时实例（ephemeral）和持久化实例（persistent）分开存储
- **线程安全**：使用ConcurrentHashMap保证并发安全

### 3. AP模式注册（临时实例）

```java
// 临时实例注册（默认模式）
spring:
  cloud:
    nacos:
      discovery:
        ephemeral: true  # 临时实例
        server-addr: localhost:8848
        namespace: dev
        group: DEFAULT_GROUP
```

**AP模式特点**：
- **客户端心跳**：客户端每5秒发送心跳，服务端15秒未收到标记不健康，30秒未收到删除实例
- **Distro协议**：采用最终一致性，数据异步同步到其他节点
- **高可用**：网络分区时仍可提供服务，但可能数据不一致

**源码关键点**：
```java
// InstanceController.java - 注册接口
@PostMapping("/instance")
public String register(HttpServletRequest request) {
    // 1. 解析请求参数
    String namespaceId = WebUtils.optional(request, CommonParams.NAMESPACE_ID, Constants.DEFAULT_NAMESPACE_ID);
    String serviceName = WebUtils.required(request, CommonParams.SERVICE_NAME);
    Instance instance = parseInstance(request);
    
    // 2. 创建或获取Service
    Service service = serviceManager.getService(namespaceId, serviceName);
    if (service == null) {
        service = createServiceIfAbsent(namespaceId, serviceName);
    }
    
    // 3. 添加实例
    serviceManager.registerInstance(namespaceId, serviceName, instance);
    
    // 4. 触发事件通知（服务变更）
    NotifyCenter.publishEvent(new InstanceMetadataEvent.InstanceMetadataEventBuilder()
        .setService(service)
        .setInstance(instance)
        .build());
    
    return "ok";
}
```

### 4. CP模式注册（持久化实例）

```java
// 持久化实例注册
spring:
  cloud:
    nacos:
      discovery:
        ephemeral: false  # 持久化实例
```

**CP模式特点**：
- **Raft协议**：使用Raft保证强一致性，所有写操作必须经过Leader
- **服务端健康检查**：服务端主动探测（TCP/HTTP/MySQL），不依赖客户端心跳
- **数据持久化**：实例信息持久化到数据库，重启后恢复

**Raft写入流程**：
```java
// RaftConsistencyServiceImpl.java
public void put(String key, Record value) throws NacosException {
    // 1. 检查是否为Leader
    if (!isLeader()) {
        throw new NacosException(NacosException.NO_LEADER, "not leader");
    }
    
    // 2. 写入本地
    datastore.put(key, value);
    
    // 3. 同步到Follower（多数派确认）
    RaftPeer leader = getLeader();
    for (RaftPeer peer : peers.values()) {
        if (!peer.ip.equals(leader.ip)) {
            syncToPeer(peer, key, value);
        }
    }
    
    // 4. 等待多数派确认
    waitForMajorityConfirm();
}
```

## 服务发现实现原理

### 1. 订阅机制

```java
// 客户端订阅服务
@Autowired
private DiscoveryClient discoveryClient;

public List<ServiceInstance> getInstances() {
    // 自动订阅并获取实例列表
    return discoveryClient.getInstances("user-service");
}
```

**订阅流程**：
1. 客户端启动时，调用`subscribe()`方法订阅服务
2. 首次拉取全量服务列表
3. 建立长轮询连接，等待服务变更推送
4. 收到变更事件后，更新本地缓存

### 2. 长轮询机制（Push + Pull）

```java
// NacosNamingService.java - 订阅服务
public void subscribe(String serviceName, EventListener listener) {
    // 1. 首次全量拉取
    List<Instance> instances = getServiceInfo(serviceName);
    listener.onEvent(new NamingEvent(serviceName, instances));
    
    // 2. 启动长轮询任务
    hostReactor.scheduleUpdateIfAbsent(serviceName, instances);
}

// HostReactor.java - 长轮询实现
public void scheduleUpdateIfAbsent(String serviceName, List<Instance> instances) {
    // 发送长轮询请求
    String url = buildLongPollingUrl(serviceName);
    
    // 设置超时时间（默认30秒）
    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(url))
        .timeout(Duration.ofSeconds(30))
        .build();
    
    // 异步等待响应
    CompletableFuture<HttpResponse<String>> future = 
        httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString());
    
    future.thenAccept(response -> {
        // 收到变更通知，更新本地缓存
        updateServiceInfo(serviceName, response.body());
    });
}
```

**长轮询优势**：
- **实时性**：服务变更后立即推送，无需等待定时拉取
- **减少请求**：相比短轮询，大幅减少无效请求
- **兼容性**：超时后自动降级为短轮询

### 3. 服务变更推送

```java
// Nacos Server端 - 服务变更通知
public class ServiceManager {
    public void registerInstance(String namespaceId, String serviceName, Instance instance) {
        // 1. 添加实例
        Service service = getService(namespaceId, serviceName);
        service.addInstance(instance);
        
        // 2. 触发变更事件
        NotifyCenter.publishEvent(new ServiceChangeEvent(service));
        
        // 3. 通知订阅的客户端
        pushServiceInfo(service);
    }
    
    private void pushServiceInfo(Service service) {
        // 获取所有订阅该服务的客户端
        Set<String> subscribers = getSubscribers(service);
        
        for (String clientId : subscribers) {
            // 通过UDP推送（AP模式）或HTTP推送（CP模式）
            pushToClient(clientId, service);
        }
    }
}
```

## AP模式 vs CP模式对比

| 维度 | AP模式（临时实例） | CP模式（持久化实例） |
|------|------------------|-------------------|
| **一致性** | 最终一致性（Distro） | 强一致性（Raft） |
| **健康检查** | 客户端心跳 | 服务端主动探测 |
| **数据同步** | 异步复制 | 同步复制 |
| **性能** | 高（~15000 TPS） | 中等（~5000 TPS） |
| **适用场景** | 微服务注册发现 | 配置中心、DNS |
| **网络分区** | 可用但可能不一致 | 保证一致但可能不可用 |

## 性能优化与线程安全

### 1. 多级缓存

```java
// Nacos Server端缓存设计
public class ServiceManager {
    // L1缓存：本地内存（ConcurrentHashMap）
    private final ConcurrentHashMap<String, Service> serviceMap;
    
    // L2缓存：本地文件（防止重启丢失）
    private final FileBasedServiceInfoStorage storage;
    
    // L3缓存：数据库（持久化实例）
    private final PersistService persistService;
}
```

**缓存策略**：
- **读多写少**：服务发现是读多写少的场景，多级缓存大幅提升性能
- **异步刷新**：缓存更新采用异步方式，不阻塞请求
- **一致性保证**：通过事件机制保证缓存一致性

### 2. 线程安全设计

```java
// 使用ConcurrentHashMap保证并发安全
private final ConcurrentHashMap<String, ConcurrentHashMap<String, Service>> serviceMap;

// 使用CopyOnWriteArraySet存储实例（读多写少场景）
public class Cluster {
    private final Set<Instance> ephemeralInstances = new CopyOnWriteArraySet<>();
    private final Set<Instance> persistentInstances = new CopyOnWriteArraySet<>();
}
```

**线程安全考量**：
- **无锁读取**：使用ConcurrentHashMap和CopyOnWriteArraySet，读操作无锁
- **CAS写入**：实例注册使用CAS操作，避免锁竞争
- **分段锁**：按Namespace和ServiceName分段，减少锁粒度

### 3. 批量操作优化

```java
// 批量注册实例（减少网络请求）
public void batchRegisterInstance(String serviceName, List<Instance> instances) {
    // 合并多个实例注册请求
    BatchInstanceRequest request = new BatchInstanceRequest();
    request.setInstances(instances);
    
    // 单次HTTP请求完成批量注册
    httpClient.post("/nacos/v1/ns/instance/batch", request);
}
```

## 分布式场景考量

### 1. 集群数据同步

**AP模式（Distro协议）**：
```java
// Distro协议：最终一致性
public class DistroProtocol {
    // 数据同步到其他节点
    public void sync(Service service) {
        for (Member member : clusterMembers) {
            if (!member.isSelf()) {
                // 异步同步，不等待响应
                asyncSyncToMember(member, service);
            }
        }
    }
}
```

**CP模式（Raft协议）**：
```java
// Raft协议：强一致性
public class RaftConsistencyService {
    public void put(String key, Record value) {
        // 1. Leader写入本地
        datastore.put(key, value);
        
        // 2. 同步到Follower
        syncToFollowers(key, value);
        
        // 3. 等待多数派确认
        waitForMajority();
    }
}
```

### 2. 脑裂处理

**AP模式**：
- 网络分区时，各节点独立提供服务
- 分区恢复后，通过Distro协议合并数据
- 可能出现短暂的数据不一致

**CP模式**：
- Raft协议保证只有一个Leader
- 网络分区时，少数派节点不可用
- 分区恢复后，自动选举新Leader

### 3. 服务发现的高可用

```java
// 客户端多Server配置
spring:
  cloud:
    nacos:
      discovery:
        server-addr: 192.168.1.10:8848,192.168.1.11:8848,192.168.1.12:8848
```

**高可用策略**：
- **多Server配置**：客户端配置多个Nacos Server地址
- **故障转移**：某个Server不可用时，自动切换到其他Server
- **本地缓存**：服务列表缓存在本地，Server不可用时仍可使用缓存

## 实战示例

### 1. 服务注册

```java
@SpringBootApplication
@EnableDiscoveryClient
public class UserServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(UserServiceApplication.class, args);
    }
}

// 配置
spring:
  application:
    name: user-service
  cloud:
    nacos:
      discovery:
        server-addr: localhost:8848
        namespace: dev
        group: DEFAULT_GROUP
        ephemeral: true  # 临时实例
        metadata:
          version: v1.0
          zone: beijing
```

### 2. 服务发现

```java
@RestController
public class OrderController {
    @Autowired
    private DiscoveryClient discoveryClient;
    
    @Autowired
    private RestTemplate restTemplate;
    
    @GetMapping("/order/{userId}")
    public Order getOrder(@PathVariable Long userId) {
        // 1. 服务发现：获取user-service实例列表
        List<ServiceInstance> instances = 
            discoveryClient.getInstances("user-service");
        
        // 2. 负载均衡：选择实例
        ServiceInstance instance = loadBalance(instances);
        
        // 3. 发起调用
        String url = "http://" + instance.getHost() + ":" + instance.getPort() + "/user/" + userId;
        return restTemplate.getForObject(url, Order.class);
    }
}
```

### 3. 动态感知服务变更

```java
@Component
public class ServiceChangeListener implements EventListener {
    @Override
    public void onEvent(Event event) {
        if (event instanceof NamingEvent) {
            NamingEvent namingEvent = (NamingEvent) event;
            String serviceName = namingEvent.getServiceName();
            List<Instance> instances = namingEvent.getInstances();
            
            // 服务实例变更，更新本地缓存
            updateLocalCache(serviceName, instances);
        }
    }
}
```

## 面试总结

**Nacos服务注册与发现核心要点**：

1. **双模式支持**：
   - AP模式（临时实例）：客户端心跳，Distro协议，最终一致性，高性能
   - CP模式（持久化实例）：服务端探测，Raft协议，强一致性，适合配置中心

2. **注册流程**：
   - 客户端构建Instance对象 → HTTP POST到Server → 写入注册表 → 触发事件通知

3. **发现机制**：
   - 首次全量拉取 → 长轮询等待变更 → 收到推送后更新本地缓存

4. **性能优化**：
   - 多级缓存（内存+文件+数据库）
   - 无锁读取（ConcurrentHashMap + CopyOnWriteArraySet）
   - 批量操作减少网络请求

5. **高可用设计**：
   - 多Server配置，故障自动转移
   - 本地缓存，Server不可用时仍可用
   - 集群数据同步（Distro/Raft）

**技术亮点**：
- 支持AP/CP双模式，灵活适配不同场景
- 长轮询机制，实时感知服务变更
- 多级缓存+无锁设计，高性能
- 完善的集群同步机制，保证高可用

