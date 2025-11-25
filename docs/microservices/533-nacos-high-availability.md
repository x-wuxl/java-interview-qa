---
layout: default
title: "Nacos 是怎么保障高可用的"
parent: 微服务
nav_order: 533
description: "深入解析Nacos高可用保障机制，包括集群部署、数据同步、故障转移及容错设计"
date: 2025-11-07
---
## 核心概念

**高可用（High Availability）**是指系统能够持续提供服务的能力，即使部分组件故障也能正常工作。Nacos通过**集群部署**、**数据同步**、**故障转移**、**容错设计**等多方面机制保障高可用。

**高可用目标**：
- **可用性**：99.9%+（年停机时间 < 8.76小时）
- **容错性**：单节点故障不影响服务
- **数据一致性**：集群数据最终一致或强一致

## 集群部署架构

### 1. 集群模式

```yaml
# Nacos集群配置
# cluster.conf
192.168.1.10:8848
192.168.1.11:8848
192.168.1.12:8848
```

**集群特点**：
- **无中心化**：所有节点平等，无单点故障
- **数据同步**：节点间数据实时同步
- **负载均衡**：客户端可连接任意节点

### 2. 集群架构图

```
┌─────────────────────────────────────────────┐
│           Nacos Cluster                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Node 1   │  │ Node 2   │  │ Node 3   │  │
│  │ (Leader) │←→│(Follower)│←→│(Follower)│  │
│  └──────────┘  └──────────┘  └──────────┘  │
│       ↑              ↑              ↑        │
└───────┼──────────────┼──────────────┼────────┘
        │              │              │
    ┌───┴──┐      ┌───┴──┐      ┌───┴──┐
    │Client│      │Client│      │Client│
    └──────┘      └──────┘      └──────┘
```

## 数据同步机制

### 1. AP模式数据同步（Distro协议）

**Distro协议**是Nacos自研的AP模式数据同步协议，保证最终一致性。

```java
// DistroProtocol.java - Distro协议实现
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
    
    private void asyncSyncToMember(Member member, Service service) {
        CompletableFuture.runAsync(() -> {
            try {
                // 发送HTTP请求同步数据
                String url = "http://" + member.getAddress() + "/nacos/v1/ns/distro/datum";
                HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .POST(HttpRequest.BodyPublishers.ofString(JSON.toJSONString(service)))
                    .build();
                
                httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            } catch (Exception e) {
                log.error("Sync to member {} failed", member, e);
            }
        });
    }
    
    // 接收其他节点的同步数据
    @PostMapping("/distro/datum")
    public String receiveSync(@RequestBody Service service) {
        // 合并数据
        mergeService(service);
        return "ok";
    }
}
```

**Distro协议特点**：
- **最终一致性**：数据异步同步，可能出现短暂不一致
- **高性能**：异步同步，不阻塞主流程
- **容错性**：同步失败不影响本地服务

### 2. CP模式数据同步（Raft协议）

**Raft协议**保证强一致性，所有写操作必须经过Leader。

```java
// RaftConsistencyServiceImpl.java - Raft协议实现
public class RaftConsistencyServiceImpl implements ConsistencyService {
    private RaftPeer leader;
    private List<RaftPeer> followers;
    
    @Override
    public void put(String key, Record value) throws NacosException {
        // 1. 检查是否为Leader
        if (!isLeader()) {
            // 转发到Leader
            forwardToLeader(key, value);
            return;
        }
        
        // 2. 写入本地
        datastore.put(key, value);
        
        // 3. 同步到Follower（多数派确认）
        int successCount = 0;
        for (RaftPeer follower : followers) {
            if (syncToFollower(follower, key, value)) {
                successCount++;
            }
        }
        
        // 4. 等待多数派确认（至少N/2+1个节点）
        if (successCount < (followers.size() + 1) / 2) {
            throw new NacosException("Failed to sync to majority");
        }
    }
    
    // Leader选举
    public void electLeader() {
        // Raft选举算法
        // 1. 发起选举请求
        // 2. 收集选票
        // 3. 获得多数派支持后成为Leader
    }
}
```

**Raft协议特点**：
- **强一致性**：所有节点数据一致
- **Leader选举**：自动选举Leader，处理写请求
- **容错性**：最多容忍(N-1)/2个节点故障

### 3. 数据同步对比

| 维度 | Distro协议（AP） | Raft协议（CP） |
|------|----------------|---------------|
| **一致性** | 最终一致性 | 强一致性 |
| **性能** | 高（异步） | 中等（同步） |
| **容错** | 高（无Leader） | 中等（需要Leader） |
| **适用场景** | 临时实例注册 | 持久化实例、配置中心 |

## 故障转移机制

### 1. 客户端故障转移

```java
// NacosNamingService.java - 多Server配置
public class NacosNamingService {
    private List<String> serverList;
    private int currentServerIndex = 0;
    
    public NacosNamingService(List<String> serverList) {
        this.serverList = serverList;
    }
    
    // 请求时自动故障转移
    private <T> T executeRequest(RequestCallBack<T> callBack) {
        int retryCount = 0;
        Exception lastException = null;
        
        while (retryCount < serverList.size()) {
            try {
                String server = getCurrentServer();
                return callBack.execute(server);
            } catch (Exception e) {
                lastException = e;
                // 切换到下一个Server
                switchToNextServer();
                retryCount++;
            }
        }
        
        throw new NacosException("All servers failed", lastException);
    }
    
    private void switchToNextServer() {
        currentServerIndex = (currentServerIndex + 1) % serverList.size();
        log.warn("Switch to next server: {}", getCurrentServer());
    }
}
```

**客户端配置**：
```yaml
spring:
  cloud:
    nacos:
      discovery:
        # 配置多个Server地址
        server-addr: 192.168.1.10:8848,192.168.1.11:8848,192.168.1.12:8848
```

### 2. 服务端故障转移

```java
// 服务端节点故障检测
public class ClusterMemberManager {
    private final ScheduledExecutorService healthCheckExecutor;
    
    @PostConstruct
    public void init() {
        // 定期检查节点健康状态
        healthCheckExecutor.scheduleAtFixedRate(
            this::checkMemberHealth,
            0,
            5,
            TimeUnit.SECONDS
        );
    }
    
    private void checkMemberHealth() {
        for (Member member : clusterMembers) {
            if (member.isSelf()) {
                continue;
            }
            
            // 检查节点是否可达
            boolean healthy = pingMember(member);
            
            if (!healthy && member.isHealthy()) {
                // 节点故障，标记为不健康
                member.setHealthy(false);
                log.warn("Member {} is unhealthy", member);
                
                // 触发故障转移
                handleMemberFailure(member);
            } else if (healthy && !member.isHealthy()) {
                // 节点恢复
                member.setHealthy(true);
                log.info("Member {} recovered", member);
            }
        }
    }
    
    private void handleMemberFailure(Member member) {
        // 1. 如果是Leader故障，触发重新选举
        if (member.isLeader()) {
            electNewLeader();
        }
        
        // 2. 重新分配数据同步任务
        redistributeSyncTasks();
    }
}
```

### 3. Leader选举（CP模式）

```java
// RaftLeaderElection.java - Leader选举
public class RaftLeaderElection {
    private volatile RaftPeer leader;
    private volatile long electionTimeout;
    
    // 发起选举
    public void startElection() {
        // 1. 增加term
        currentTerm++;
        
        // 2. 投票给自己
        voteFor = self;
        votesReceived = 1;
        
        // 3. 向其他节点请求投票
        for (RaftPeer peer : clusterMembers) {
            if (!peer.isSelf()) {
                requestVote(peer);
            }
        }
        
        // 4. 等待投票结果
        waitForVotes();
    }
    
    private void requestVote(RaftPeer peer) {
        VoteRequest request = new VoteRequest();
        request.setTerm(currentTerm);
        request.setCandidateId(self.getId());
        request.setLastLogIndex(lastLogIndex);
        request.setLastLogTerm(lastLogTerm);
        
        // 发送投票请求
        VoteResponse response = sendVoteRequest(peer, request);
        
        if (response.isVoteGranted()) {
            votesReceived++;
        }
    }
    
    // 检查是否获得多数派支持
    private boolean hasMajority() {
        return votesReceived > (clusterMembers.size() / 2);
    }
}
```

## 容错设计

### 1. 本地缓存

```java
// 客户端本地缓存，Server不可用时仍可使用
public class ServiceInfoHolder {
    private final Map<String, ServiceInfo> serviceInfoMap = new ConcurrentHashMap<>();
    
    // 获取服务信息（优先从缓存读取）
    public ServiceInfo getServiceInfo(String serviceName) {
        ServiceInfo serviceInfo = serviceInfoMap.get(serviceName);
        
        if (serviceInfo == null) {
            // 缓存未命中，从Server拉取
            serviceInfo = pullServiceInfo(serviceName);
            if (serviceInfo != null) {
                serviceInfoMap.put(serviceName, serviceInfo);
            }
        }
        
        return serviceInfo;
    }
    
    // 更新缓存
    public void updateServiceInfo(ServiceInfo serviceInfo) {
        serviceInfoMap.put(serviceInfo.getName(), serviceInfo);
    }
}
```

### 2. 降级策略

```java
// 服务降级：Server不可用时的处理策略
public class NacosNamingService {
    private boolean fallbackEnabled = true;
    
    public List<Instance> getAllInstances(String serviceName) {
        try {
            // 尝试从Server获取
            return serverProxy.queryInstances(serviceName);
        } catch (Exception e) {
            if (fallbackEnabled) {
                // 降级：从本地缓存获取
                log.warn("Server unavailable, use local cache", e);
                return getInstancesFromCache(serviceName);
            } else {
                throw e;
            }
        }
    }
}
```

### 3. 重试机制

```java
// 请求重试机制
public class RetryableRequest {
    private static final int MAX_RETRY = 3;
    private static final long RETRY_DELAY = 1000;  // 1秒
    
    public <T> T executeWithRetry(Supplier<T> supplier) {
        int retryCount = 0;
        Exception lastException = null;
        
        while (retryCount < MAX_RETRY) {
            try {
                return supplier.get();
            } catch (Exception e) {
                lastException = e;
                retryCount++;
                
                if (retryCount < MAX_RETRY) {
                    // 指数退避
                    long delay = RETRY_DELAY * (1 << (retryCount - 1));
                    Thread.sleep(delay);
                }
            }
        }
        
        throw new NacosException("Request failed after retries", lastException);
    }
}
```

## 数据持久化

### 1. 数据持久化策略

```java
// 数据持久化到数据库
public class PersistService {
    @Autowired
    private DataSource dataSource;
    
    // 持久化服务信息
    public void persistService(Service service) {
        String sql = "INSERT INTO services (namespace_id, service_name, group_name, metadata) " +
                     "VALUES (?, ?, ?, ?) " +
                     "ON DUPLICATE KEY UPDATE metadata = ?";
        
        try (Connection conn = dataSource.getConnection();
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            
            stmt.setString(1, service.getNamespaceId());
            stmt.setString(2, service.getName());
            stmt.setString(3, service.getGroupName());
            stmt.setString(4, JSON.toJSONString(service.getMetadata()));
            stmt.setString(5, JSON.toJSONString(service.getMetadata()));
            
            stmt.executeUpdate();
        } catch (SQLException e) {
            log.error("Persist service failed", e);
        }
    }
    
    // 从数据库恢复数据
    public List<Service> loadServices() {
        String sql = "SELECT * FROM services";
        // 查询并恢复服务信息
        return queryServices(sql);
    }
}
```

### 2. 启动时数据恢复

```java
// Nacos Server启动时恢复数据
@PostConstruct
public void init() {
    // 1. 从数据库加载持久化数据
    List<Service> services = persistService.loadServices();
    
    // 2. 恢复到内存
    for (Service service : services) {
        serviceMap.put(buildKey(service), service);
    }
    
    // 3. 从其他节点同步数据（AP模式）
    if (isAPMode()) {
        syncFromOtherNodes();
    }
    
    log.info("Data recovery completed, services: {}", services.size());
}
```

## 监控与告警

### 1. 健康检查

```java
// Nacos Server健康检查
@RestController
@RequestMapping("/nacos/actuator")
public class HealthController {
    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> result = new HashMap<>();
        
        // 检查数据库连接
        boolean dbHealthy = checkDatabase();
        
        // 检查集群状态
        boolean clusterHealthy = checkCluster();
        
        // 检查内存使用
        boolean memoryHealthy = checkMemory();
        
        boolean overallHealthy = dbHealthy && clusterHealthy && memoryHealthy;
        
        result.put("status", overallHealthy ? "UP" : "DOWN");
        result.put("db", dbHealthy ? "UP" : "DOWN");
        result.put("cluster", clusterHealthy ? "UP" : "DOWN");
        result.put("memory", memoryHealthy ? "UP" : "DOWN");
        
        return result;
    }
}
```

### 2. 监控指标

```java
// 监控指标收集
public class NacosMetrics {
    private final MeterRegistry meterRegistry;
    
    public void recordRequest(String endpoint, long duration, boolean success) {
        // 记录请求次数
        meterRegistry.counter("nacos.request.total",
            "endpoint", endpoint,
            "status", success ? "success" : "error"
        ).increment();
        
        // 记录请求耗时
        meterRegistry.timer("nacos.request.duration",
            "endpoint", endpoint
        ).record(duration, TimeUnit.MILLISECONDS);
    }
    
    public void recordClusterStatus(int healthyNodes, int totalNodes) {
        // 记录集群健康节点数
        meterRegistry.gauge("nacos.cluster.healthy.nodes", healthyNodes);
        meterRegistry.gauge("nacos.cluster.total.nodes", totalNodes);
    }
}
```

## 实战部署

### 1. 集群部署配置

```properties
# application.properties
# 集群配置
nacos.naming.data.dir=${user.home}/nacos/data
nacos.naming.log.dir=${user.home}/nacos/logs

# 数据库配置（持久化）
spring.datasource.platform=mysql
db.num=1
db.url.0=jdbc:mysql://192.168.1.20:3306/nacos?characterEncoding=utf8&connectTimeout=1000&socketTimeout=3000&autoReconnect=true
db.user.0=nacos
db.password.0=nacos

# 集群节点配置（cluster.conf）
# 192.168.1.10:8848
# 192.168.1.11:8848
# 192.168.1.12:8848
```

### 2. 客户端配置

```yaml
spring:
  cloud:
    nacos:
      discovery:
        # 配置多个Server地址
        server-addr: 192.168.1.10:8848,192.168.1.11:8848,192.168.1.12:8848
        # 启用本地缓存
        naming-load-cache-at-start: true
        # 故障转移
        naming-request-domain-retry-count: 3
```

### 3. 高可用验证

```bash
# 1. 停止一个节点
kill -9 <nacos-pid>

# 2. 验证服务是否正常
curl http://192.168.1.11:8848/nacos/v1/ns/instance/list?serviceName=user-service

# 3. 验证数据同步
# 在另一个节点注册服务，检查是否同步到其他节点
```

## 面试总结

**Nacos高可用保障机制核心要点**：

1. **集群部署**：
   - 多节点部署，无单点故障
   - 节点间数据实时同步

2. **数据同步**：
   - **AP模式**：Distro协议，最终一致性，高性能
   - **CP模式**：Raft协议，强一致性，需要Leader

3. **故障转移**：
   - 客户端多Server配置，自动故障转移
   - 服务端节点故障检测，自动切换
   - Leader选举（CP模式）

4. **容错设计**：
   - 本地缓存，Server不可用时仍可用
   - 降级策略，从缓存获取数据
   - 重试机制，指数退避

5. **数据持久化**：
   - 持久化到数据库，重启后恢复
   - 启动时自动恢复数据

6. **监控告警**：
   - 健康检查
   - 监控指标收集
   - 告警机制

**技术亮点**：
- 双模式数据同步（Distro/Raft），灵活适配不同场景
- 完善的故障转移机制，保证服务连续性
- 本地缓存+降级策略，提高可用性
- 数据持久化，防止数据丢失

**最佳实践**：
- 至少部署3个节点（保证CP模式容错）
- 配置多个Server地址，启用故障转移
- 启用本地缓存，提高容错能力
- 配置监控告警，及时发现问题

