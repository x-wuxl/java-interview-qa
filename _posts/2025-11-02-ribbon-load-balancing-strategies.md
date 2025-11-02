---
layout: post
title: "Ribbon的负载均衡策略有哪些？"
date: 2025-11-02
categories: [Spring框架, SpringCloud, 负载均衡]
tags: [Ribbon, 负载均衡, SpringCloud, 微服务]
description: "详解Ribbon客户端负载均衡的核心策略、工作原理及自定义实现"
---

## 核心概念

**Ribbon**是Netflix开源的客户端负载均衡器，与Eureka集成后可以自动从服务注册中心获取服务实例列表，并根据负载均衡策略选择目标实例进行调用。

### 客户端负载均衡 vs 服务端负载均衡

```
客户端负载均衡（Ribbon）              服务端负载均衡（Nginx）
┌──────────┐                         ┌──────────┐
│  Client  │                         │  Client  │
└────┬─────┘                         └────┬─────┘
     │ 1. 获取服务列表                      │
     ↓                                     ↓
┌──────────┐                         ┌──────────┐
│  Eureka  │                         │  Nginx   │
└────┬─────┘                         └────┬─────┘
     │ 2. 返回实例列表                      │ 选择实例
     ↓                                     ↓
┌──────────┐                         ┌──────────┐
│  Client  │ 3. 本地选择实例          │ Server 1 │
└────┬─────┘                         │ Server 2 │
     │ 4. 直接调用                    │ Server 3 │
     ↓                                └──────────┘
┌──────────┐
│ Server N │
└──────────┘
```

## 内置负载均衡策略

### 1. RoundRobinRule（轮询策略）- 默认

**原理**：按顺序循环选择服务实例

```java
public class RoundRobinRule extends AbstractLoadBalancerRule {
    private AtomicInteger nextServerCyclicCounter;
    
    public Server choose(ILoadBalancer lb, Object key) {
        List<Server> allServers = lb.getAllServers();
        int count = 0;
        Server server = null;
        
        while (server == null && count++ < 10) {
            List<Server> reachableServers = lb.getReachableServers();
            int upCount = reachableServers.size();
            
            if (upCount == 0) {
                return null;
            }
            
            // 轮询索引递增
            int nextServerIndex = incrementAndGetModulo(upCount);
            server = reachableServers.get(nextServerIndex);
            
            if (server.isAlive() && server.isReadyToServe()) {
                return server;
            }
        }
        return server;
    }
    
    private int incrementAndGetModulo(int modulo) {
        int current, next;
        do {
            current = nextServerCyclicCounter.get();
            next = (current + 1) % modulo;
        } while (!nextServerCyclicCounter.compareAndSet(current, next));
        return next;
    }
}
```

**适用场景**：
- 服务实例性能相近
- 简单均匀分配流量
- 最常用的策略

### 2. RandomRule（随机策略）

**原理**：随机选择一个可用实例

```java
public class RandomRule extends AbstractLoadBalancerRule {
    Random rand = new Random();
    
    public Server choose(ILoadBalancer lb, Object key) {
        List<Server> upList = lb.getReachableServers();
        int serverCount = upList.size();
        
        if (serverCount == 0) {
            return null;
        }
        
        // 随机选择索引
        int index = rand.nextInt(serverCount);
        return upList.get(index);
    }
}
```

**适用场景**：
- 服务实例性能相近
- 简单随机分布
- 无状态服务

### 3. WeightedResponseTimeRule（响应时间加权策略）

**原理**：
- 根据每个实例的平均响应时间计算权重
- 响应时间越短，权重越大，被选中概率越高
- 刚启动时使用轮询，统计信息足够后切换

```java
public class WeightedResponseTimeRule extends RoundRobinRule {
    // 每个实例的权重
    private volatile List<Double> accumulatedWeights = new ArrayList<>();
    
    public Server choose(ILoadBalancer lb, Object key) {
        List<Server> allList = lb.getAllServers();
        List<Double> currentWeights = accumulatedWeights;
        
        if (currentWeights.isEmpty()) {
            // 权重未初始化，使用轮询
            return super.choose(lb, key);
        }
        
        // 根据权重随机选择
        double randomWeight = random.nextDouble() * currentWeights.get(currentWeights.size() - 1);
        
        int serverIndex = 0;
        for (int i = 0; i < currentWeights.size(); i++) {
            if (currentWeights.get(i) >= randomWeight) {
                serverIndex = i;
                break;
            }
        }
        
        return allList.get(serverIndex);
    }
    
    // 定期计算权重
    void maintainWeights() {
        List<Server> allServers = lb.getAllServers();
        List<Double> weights = new ArrayList<>();
        double totalResponseTime = 0;
        
        // 计算总响应时间
        for (Server server : allServers) {
            ServerStats stats = lb.getLoadBalancerStats().getSingleServerStat(server);
            double avgResponseTime = stats.getResponseTimeAvg();
            totalResponseTime += avgResponseTime;
        }
        
        // 计算累积权重（响应时间越小，权重越大）
        double accumulatedWeight = 0;
        for (Server server : allServers) {
            ServerStats stats = lb.getLoadBalancerStats().getSingleServerStat(server);
            double weight = totalResponseTime - stats.getResponseTimeAvg();
            accumulatedWeight += weight;
            weights.add(accumulatedWeight);
        }
        
        accumulatedWeights = weights;
    }
}
```

**适用场景**：
- 服务实例性能差异较大
- 需要自动感知性能差异
- 追求整体响应速度

### 4. RetryRule（重试策略）

**原理**：
- 在指定时间内（默认500ms）循环重试
- 内部使用另一个规则（默认轮询）选择实例
- 如果选择的实例不可用，继续尝试

```java
public class RetryRule extends AbstractLoadBalancerRule {
    IRule subRule = new RoundRobinRule();  // 内部策略
    long maxRetryMillis = 500;  // 最大重试时间
    
    public Server choose(ILoadBalancer lb, Object key) {
        long requestTime = System.currentTimeMillis();
        long deadline = requestTime + maxRetryMillis;
        
        Server chosenServer = null;
        
        while (chosenServer == null || !chosenServer.isAlive()) {
            if (System.currentTimeMillis() > deadline) {
                // 超时，返回null
                return null;
            }
            
            // 使用内部策略选择
            chosenServer = subRule.choose(key);
            
            if (Thread.interrupted()) {
                return null;
            }
        }
        
        return chosenServer;
    }
}
```

**适用场景**：
- 服务偶尔不可用
- 需要容错重试
- 配合健康检查使用

### 5. BestAvailableRule（最低并发策略）

**原理**：
- 过滤掉故障实例
- 选择并发请求数最小的实例

```java
public class BestAvailableRule extends ClientConfigEnabledRoundRobinRule {
    public Server choose(Object key) {
        List<Server> serverList = getLoadBalancer().getAllServers();
        
        int minimalConcurrentConnections = Integer.MAX_VALUE;
        long currentTime = System.currentTimeMillis();
        Server chosen = null;
        
        for (Server server : serverList) {
            ServerStats stats = loadBalancerStats.getSingleServerStat(server);
            
            // 跳过熔断的实例
            if (!stats.isCircuitBreakerTripped(currentTime)) {
                int concurrentConnections = stats.getActiveRequestsCount(currentTime);
                
                if (concurrentConnections < minimalConcurrentConnections) {
                    minimalConcurrentConnections = concurrentConnections;
                    chosen = server;
                }
            }
        }
        
        return chosen == null ? super.choose(key) : chosen;
    }
}
```

**适用场景**：
- 请求耗时差异较大
- 长连接场景
- 需要避免某个实例过载

### 6. AvailabilityFilteringRule（可用性过滤策略）

**原理**：
- 过滤掉故障或连接数过多的实例
- 对剩余实例使用轮询

```java
public class AvailabilityFilteringRule extends PredicateBasedRule {
    private AbstractServerPredicate predicate;
    
    public AvailabilityFilteringRule() {
        // 组合过滤条件
        predicate = CompositePredicate.withPredicates(
            new AvailabilityPredicate(this),  // 可用性过滤
            new CircuitBreakerPredicate(this)  // 熔断过滤
        );
    }
    
    @Override
    public AbstractServerPredicate getPredicate() {
        return predicate;
    }
}

// 可用性判断
class AvailabilityPredicate extends AbstractServerPredicate {
    public boolean apply(PredicateKey input) {
        Server server = input.getServer();
        ServerStats stats = getServerStats(server);
        
        // 过滤掉连接失败次数过多的实例
        if (stats.getFailureCount() > threshold) {
            return false;
        }
        
        // 过滤掉并发连接数过多的实例
        if (stats.getActiveRequestsCount() >= connectionLimit) {
            return false;
        }
        
        return true;
    }
}
```

**适用场景**：
- 需要自动过滤故障实例
- 防止雪崩效应
- 生产环境推荐

### 7. ZoneAvoidanceRule（区域感知策略）- SpringCloud默认

**原理**：
- 优先选择同区域（Zone）的实例
- 区域内使用轮询策略
- 复合判断服务器性能和可用性

```java
public class ZoneAvoidanceRule extends PredicateBasedRule {
    private CompositePredicate compositePredicate;
    
    public ZoneAvoidanceRule() {
        ZoneAvoidancePredicate zonePredicate = new ZoneAvoidancePredicate(this);
        AvailabilityPredicate availabilityPredicate = new AvailabilityPredicate(this);
        
        compositePredicate = createCompositePredicate(zonePredicate, availabilityPredicate);
    }
}
```

**适用场景**：
- 多机房部署
- 跨区域服务调用
- 追求低延迟

## 使用方式

### 1. 全局配置

```java
@Configuration
public class RibbonConfig {
    @Bean
    public IRule ribbonRule() {
        return new RandomRule();  // 全局使用随机策略
    }
}
```

### 2. 针对特定服务配置

```java
// 配置类不能在@ComponentScan扫描路径下
@Configuration
public class UserServiceRibbonConfig {
    @Bean
    public IRule ribbonRule() {
        return new WeightedResponseTimeRule();
    }
}

// 主启动类
@SpringBootApplication
@RibbonClient(name = "user-service", configuration = UserServiceRibbonConfig.class)
public class OrderServiceApplication {
    // ...
}
```

### 3. 配置文件方式

```yaml
# 全局配置
ribbon:
  NFLoadBalancerRuleClassName: com.netflix.loadbalancer.RandomRule

# 针对特定服务
user-service:
  ribbon:
    NFLoadBalancerRuleClassName: com.netflix.loadbalancer.WeightedResponseTimeRule
    ConnectTimeout: 3000  # 连接超时
    ReadTimeout: 5000     # 读取超时
    MaxAutoRetries: 1     # 同一实例重试次数
    MaxAutoRetriesNextServer: 2  # 切换实例重试次数
```

### 4. 与RestTemplate集成

```java
@Configuration
public class RestTemplateConfig {
    @Bean
    @LoadBalanced  // 开启负载均衡
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}

@Service
public class OrderService {
    @Autowired
    private RestTemplate restTemplate;
    
    public User getUser(Long userId) {
        // 通过服务名调用，Ribbon自动负载均衡
        return restTemplate.getForObject(
            "http://user-service/api/users/" + userId,
            User.class
        );
    }
}
```

## 自定义负载均衡策略

### 基于IP Hash的策略

```java
public class IpHashRule extends AbstractLoadBalancerRule {
    
    @Override
    public Server choose(Object key) {
        List<Server> servers = getLoadBalancer().getReachableServers();
        
        if (servers.isEmpty()) {
            return null;
        }
        
        // 获取客户端IP（实际项目中从请求上下文获取）
        String clientIp = getClientIp();
        
        // IP Hash取模
        int hash = Math.abs(clientIp.hashCode());
        int index = hash % servers.size();
        
        return servers.get(index);
    }
    
    private String getClientIp() {
        // 从RequestContextHolder或其他上下文获取
        return "192.168.1.100";
    }
}
```

### 基于权重的自定义策略

```java
public class CustomWeightRule extends AbstractLoadBalancerRule {
    
    @Override
    public Server choose(Object key) {
        List<Server> servers = getLoadBalancer().getReachableServers();
        
        // 从配置中心获取权重配置
        Map<String, Integer> weights = getWeightConfig();
        
        int totalWeight = 0;
        for (Server server : servers) {
            String serverKey = server.getHost() + ":" + server.getPort();
            totalWeight += weights.getOrDefault(serverKey, 1);
        }
        
        // 随机选择
        int randomWeight = ThreadLocalRandom.current().nextInt(totalWeight);
        int currentWeight = 0;
        
        for (Server server : servers) {
            String serverKey = server.getHost() + ":" + server.getPort();
            currentWeight += weights.getOrDefault(serverKey, 1);
            
            if (randomWeight < currentWeight) {
                return server;
            }
        }
        
        return servers.get(0);
    }
    
    private Map<String, Integer> getWeightConfig() {
        // 从配置中心或数据库读取
        return Map.of(
            "192.168.1.10:8080", 5,
            "192.168.1.11:8080", 3,
            "192.168.1.12:8080", 2
        );
    }
}
```

## 性能优化建议

### 1. 合理配置超时时间

```yaml
ribbon:
  ConnectTimeout: 1000  # 连接超时1秒
  ReadTimeout: 3000     # 读取超时3秒
  MaxAutoRetries: 0     # 禁用同实例重试（幂等接口可开启）
  MaxAutoRetriesNextServer: 1  # 只重试一次其他实例
  OkToRetryOnAllOperations: false  # 只对GET请求重试
```

### 2. 禁用Eureka定时刷新（小规模集群）

```yaml
ribbon:
  ServerListRefreshInterval: 30000  # 30秒刷新一次（默认）
```

### 3. 开启饥饿加载

```yaml
ribbon:
  eager-load:
    enabled: true  # 启动时立即加载，避免首次调用慢
    clients: user-service, order-service
```

## Ribbon vs Spring Cloud LoadBalancer

| 对比项 | Ribbon | Spring Cloud LoadBalancer |
|--------|--------|---------------------------|
| 维护状态 | 停止维护 | 活跃维护 |
| 依赖 | Netflix Ribbon | Spring官方 |
| 性能 | 较好 | 更好（响应式支持） |
| 扩展性 | 较复杂 | 更简洁 |
| 推荐度 | 不推荐新项目使用 | 推荐 |

### LoadBalancer示例

```java
@Configuration
@LoadBalancerClient(name = "user-service", configuration = CustomLoadBalancerConfig.class)
public class LoadBalancerConfig {
    // 新版本推荐使用
}

public class CustomLoadBalancerConfig {
    @Bean
    public ReactorLoadBalancer<ServiceInstance> randomLoadBalancer(
        Environment environment,
        LoadBalancerClientFactory loadBalancerClientFactory) {
        String name = environment.getProperty(LoadBalancerClientFactory.PROPERTY_NAME);
        return new RandomLoadBalancer(
            loadBalancerClientFactory.getLazyProvider(name, ServiceInstanceListSupplier.class),
            name
        );
    }
}
```

## 面试总结

Ribbon提供**7种内置负载均衡策略**：

1. **RoundRobinRule**（轮询）- 默认策略，按顺序循环
2. **RandomRule**（随机）- 随机选择实例
3. **WeightedResponseTimeRule**（响应时间加权）- 响应快的实例权重高
4. **RetryRule**（重试）- 失败后在指定时间内重试
5. **BestAvailableRule**（最低并发）- 选择并发数最小的实例
6. **AvailabilityFilteringRule**（可用性过滤）- 过滤故障和高并发实例
7. **ZoneAvoidanceRule**（区域感知）- SpringCloud默认，优先同区域

**选择建议**：
- 通用场景：RoundRobinRule或ZoneAvoidanceRule
- 性能差异大：WeightedResponseTimeRule
- 需要容错：RetryRule + AvailabilityFilteringRule
- 会话保持：自定义IpHashRule

**注意**：Ribbon已停止维护，新项目推荐使用**Spring Cloud LoadBalancer**替代。

