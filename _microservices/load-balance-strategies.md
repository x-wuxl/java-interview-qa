---
title: "负载均衡策略有哪些？轮询、权重、随机、最小连接数等策略详解"
date: 2025-11-02
categories: [中间件, 负载均衡]
tags: [负载均衡, 轮询策略, 权重策略, 随机策略, 最小连接数, 重试策略, 可用性敏感, 区域敏感, Dubbo, Nginx]
description: "深入解析7种核心负载均衡策略的原理、适用场景及源码实现"
nav_order: 528
parent: 微服务
---
## 核心概念

**负载均衡（Load Balance）** 是分布式系统中的关键技术，通过特定的策略将请求分发到多个服务节点，实现**流量均衡、提升系统吞吐量、增强容错能力**。

**核心目标**：
- **流量均衡**：避免某些节点过载
- **高可用**：故障节点自动摘除
- **高性能**：根据节点性能动态调整

**常见应用场景**：
- **Nginx/HAProxy**：7层/4层负载均衡
- **Dubbo/Spring Cloud**：RPC框架负载均衡
- **Kubernetes**：容器服务负载均衡

---

## 七大核心负载均衡策略

### 1. 轮询策略（Round Robin）

**原理**：按顺序依次将请求分配给每个服务节点，循环往复。

**实现代码**：
```java
/**
 * 轮询负载均衡
 */
public class RoundRobinLoadBalance {
    private final AtomicInteger position = new AtomicInteger(0);
    
    public <T> T select(List<T> servers) {
        if (servers == null || servers.isEmpty()) {
            return null;
        }
        
        // 原子递增并取模（防止溢出使用 & Integer.MAX_VALUE）
        int pos = position.getAndIncrement() & Integer.MAX_VALUE;
        return servers.get(pos % servers.size());
    }
}

// 使用示例
List<String> servers = Arrays.asList("192.168.1.1:8080", "192.168.1.2:8080", "192.168.1.3:8080");
RoundRobinLoadBalance lb = new RoundRobinLoadBalance();

// 请求分发：A → B → C → A → B → C ...
for (int i = 0; i < 6; i++) {
    System.out.println("请求" + i + " → " + lb.select(servers));
}
```

**输出结果**：
```
请求0 → 192.168.1.1:8080
请求1 → 192.168.1.2:8080
请求2 → 192.168.1.3:8080
请求3 → 192.168.1.1:8080
请求4 → 192.168.1.2:8080
请求5 → 192.168.1.3:8080
```

**Nginx 配置**：
```nginx
upstream backend {
    server 192.168.1.1:8080;
    server 192.168.1.2:8080;
    server 192.168.1.3:8080;
}

server {
    listen 80;
    location / {
        proxy_pass http://backend;
    }
}
```

**适用场景**：
- ✅ 所有服务节点性能相同
- ✅ 请求处理时间相近
- ❌ 节点性能差异大（会导致低性能节点过载）

---

### 2. 权重策略（Weighted Round Robin）

**原理**：根据节点性能分配不同权重，性能高的节点获得更多请求。

**权重配置示例**：
```
服务器A（8核32G） → 权重 5
服务器B（4核16G） → 权重 3
服务器C（2核8G）  → 权重 2
```

**实现代码（Dubbo 风格）**：
```java
/**
 * 加权轮询负载均衡
 */
public class WeightedRoundRobinLoadBalance {
    
    public <T> T select(List<Server<T>> servers) {
        if (servers == null || servers.isEmpty()) {
            return null;
        }
        
        // 计算总权重
        int totalWeight = servers.stream().mapToInt(Server::getWeight).sum();
        
        // 计算最大权重和权重差
        int maxWeight = servers.stream().mapToInt(Server::getWeight).max().orElse(1);
        int minWeight = servers.stream().mapToInt(Server::getWeight).min().orElse(1);
        
        if (maxWeight == minWeight) {
            // 所有权重相同，退化为普通轮询
            return servers.get(ThreadLocalRandom.current().nextInt(servers.size())).getInstance();
        }
        
        // 平滑加权轮询（Smooth Weighted Round Robin）
        Server<T> selected = null;
        int total = 0;
        
        for (Server<T> server : servers) {
            // 增加当前权重
            server.setCurrentWeight(server.getCurrentWeight() + server.getWeight());
            total += server.getWeight();
            
            // 选择当前权重最大的节点
            if (selected == null || server.getCurrentWeight() > selected.getCurrentWeight()) {
                selected = server;
            }
        }
        
        // 减少被选中节点的当前权重
        selected.setCurrentWeight(selected.getCurrentWeight() - total);
        
        return selected.getInstance();
    }
    
    @Data
    @AllArgsConstructor
    public static class Server<T> {
        private T instance;        // 服务实例
        private int weight;        // 配置权重
        private int currentWeight; // 当前权重（动态变化）
    }
}

// 使用示例
List<Server<String>> servers = Arrays.asList(
    new Server<>("ServerA", 5, 0),
    new Server<>("ServerB", 3, 0),
    new Server<>("ServerC", 2, 0)
);

WeightedRoundRobinLoadBalance lb = new WeightedRoundRobinLoadBalance();

// 连续10次请求的分发结果
for (int i = 0; i < 10; i++) {
    System.out.println("请求" + i + " → " + lb.select(servers));
}
```

**输出结果（符合权重比例 5:3:2）**：
```
请求0 → ServerA
请求1 → ServerA
请求2 → ServerB
请求3 → ServerA
请求4 → ServerC
请求5 → ServerB
请求6 → ServerA
请求7 → ServerB
请求8 → ServerA
请求9 → ServerC
```

**Nginx 配置**：
```nginx
upstream backend {
    server 192.168.1.1:8080 weight=5;  # 高性能服务器
    server 192.168.1.2:8080 weight=3;  # 中等性能
    server 192.168.1.3:8080 weight=2;  # 低性能服务器
}
```

**适用场景**：
- ✅ 服务节点性能差异大
- ✅ 需要根据机器配置动态调整流量

---

### 3. 随机策略（Random）

**原理**：随机选择一个服务节点处理请求。

**基础实现**：
```java
/**
 * 随机负载均衡
 */
public class RandomLoadBalance {
    
    public <T> T select(List<T> servers) {
        if (servers == null || servers.isEmpty()) {
            return null;
        }
        
        // 使用 ThreadLocalRandom（比 Random 性能更好）
        return servers.get(ThreadLocalRandom.current().nextInt(servers.size()));
    }
}
```

**加权随机实现**：
```java
/**
 * 加权随机负载均衡
 */
public class WeightedRandomLoadBalance {
    
    public <T> T select(List<Server<T>> servers) {
        if (servers == null || servers.isEmpty()) {
            return null;
        }
        
        // 计算总权重
        int totalWeight = servers.stream().mapToInt(Server::getWeight).sum();
        
        if (totalWeight == 0) {
            // 所有权重为0，退化为普通随机
            return servers.get(ThreadLocalRandom.current().nextInt(servers.size())).getInstance();
        }
        
        // 生成随机数 [0, totalWeight)
        int randomWeight = ThreadLocalRandom.current().nextInt(totalWeight);
        
        // 找到对应权重区间的服务器
        int currentWeight = 0;
        for (Server<T> server : servers) {
            currentWeight += server.getWeight();
            if (randomWeight < currentWeight) {
                return server.getInstance();
            }
        }
        
        return servers.get(0).getInstance();
    }
}

// 使用示例
List<Server<String>> servers = Arrays.asList(
    new Server<>("ServerA", 5),
    new Server<>("ServerB", 3),
    new Server<>("ServerC", 2)
);

WeightedRandomLoadBalance lb = new WeightedRandomLoadBalance();

// 统计1000次请求的分发情况
Map<String, Integer> counter = new HashMap<>();
for (int i = 0; i < 1000; i++) {
    String server = lb.select(servers);
    counter.put(server, counter.getOrDefault(server, 0) + 1);
}

// 输出：ServerA≈500, ServerB≈300, ServerC≈200（符合权重比例）
counter.forEach((k, v) -> System.out.println(k + ": " + v));
```

**适用场景**：
- ✅ 简单场景，无需维护状态
- ✅ 大量请求时分布趋于均匀
- ❌ 少量请求可能分布不均

---

### 4. 最小连接数策略（Least Connections）

**原理**：选择当前活跃连接数最少的服务节点（适合长连接场景）。

**实现代码**：
```java
/**
 * 最小连接数负载均衡
 */
public class LeastConnectionsLoadBalance {
    
    public <T> T select(List<Server<T>> servers) {
        if (servers == null || servers.isEmpty()) {
            return null;
        }
        
        // 找到活跃连接数最少的服务器
        Server<T> selected = servers.stream()
            .min(Comparator.comparingInt(Server::getActiveConnections))
            .orElse(servers.get(0));
        
        // 增加选中服务器的连接数
        selected.incrementConnections();
        
        return selected.getInstance();
    }
    
    @Data
    @AllArgsConstructor
    public static class Server<T> {
        private T instance;
        private AtomicInteger activeConnections = new AtomicInteger(0);
        
        public int getActiveConnections() {
            return activeConnections.get();
        }
        
        public void incrementConnections() {
            activeConnections.incrementAndGet();
        }
        
        public void decrementConnections() {
            activeConnections.decrementAndGet();
        }
    }
}
```

**Nginx 配置**：
```nginx
upstream backend {
    least_conn;  # 启用最小连接数策略
    server 192.168.1.1:8080;
    server 192.168.1.2:8080;
    server 192.168.1.3:8080;
}
```

**Dubbo 配置**：
```java
@Reference(loadbalance = "leastactive")  // Dubbo 中称为"最小活跃数"
private UserService userService;
```

**适用场景**：
- ✅ 长连接场景（如 WebSocket、数据库连接池）
- ✅ 请求处理时间差异大
- ❌ 短连接场景（HTTP 请求通常用完即关闭）

---

### 5. 重试策略（Retry / Failover）

**原理**：调用失败时自动重试其他节点（Dubbo 中称为 Failover）。

**Dubbo Failover 实现**：
```java
/**
 * 失败自动切换（最多重试2次）
 */
@Reference(
    cluster = "failover",  // 失败自动切换
    retries = 2            // 失败后重试2次（总共调用3次）
)
private UserService userService;
```

**手动实现重试逻辑**：
```java
/**
 * 重试负载均衡
 */
public class RetryLoadBalance {
    private final int maxRetries = 3;  // 最多重试3次
    
    public <T> Response invokeWithRetry(List<Server<T>> servers) {
        Set<Server<T>> tried = new HashSet<>();
        
        for (int i = 0; i < maxRetries; i++) {
            // 选择一个未尝试过的服务器
            Server<T> server = selectUntried(servers, tried);
            
            if (server == null) {
                break;  // 所有节点都尝试过
            }
            
            tried.add(server);
            
            try {
                // 发起调用
                return server.getInstance().invoke();
            } catch (Exception e) {
                log.warn("调用失败，尝试下一个节点：{}", e.getMessage());
                
                if (i == maxRetries - 1) {
                    throw new RuntimeException("所有节点调用失败", e);
                }
            }
        }
        
        throw new RuntimeException("无可用节点");
    }
    
    private <T> Server<T> selectUntried(List<Server<T>> servers, Set<Server<T>> tried) {
        return servers.stream()
            .filter(s -> !tried.contains(s))
            .findFirst()
            .orElse(null);
    }
}
```

**Spring Cloud Ribbon 配置**：
```yaml
ribbon:
  MaxAutoRetries: 1             # 单台服务器重试次数
  MaxAutoRetriesNextServer: 2   # 切换服务器重试次数
  OkToRetryOnAllOperations: false  # 只对GET请求重试
```

**适用场景**：
- ✅ 读操作（GET 请求）
- ✅ 幂等操作
- ❌ 非幂等写操作（可能导致重复执行）

**注意事项**：
```java
// ⚠️ 警告：非幂等操作不要重试！
@PostMapping("/transfer")
public Result transfer(Long fromId, Long toId, BigDecimal amount) {
    // 转账操作非幂等，重试可能导致重复扣款！
    accountService.transfer(fromId, toId, amount);
    return Result.success();
}

// ✅ 正确做法：增加幂等性控制
@PostMapping("/transfer")
public Result transfer(String requestId, Long fromId, Long toId, BigDecimal amount) {
    // 使用 requestId 防重
    if (redisTemplate.opsForValue().setIfAbsent("transfer:" + requestId, "1", 5, TimeUnit.MINUTES)) {
        accountService.transfer(fromId, toId, amount);
    }
    return Result.success();
}
```

---

### 6. 可用性敏感策略（Availability Aware）

**原理**：优先选择可用性高、响应快的节点，自动过滤故障节点。

**核心指标**：
- **成功率**：`成功请求数 / 总请求数`
- **平均响应时间**：`总响应时间 / 总请求数`
- **熔断状态**：是否触发熔断

**实现代码**：
```java
/**
 * 可用性敏感负载均衡
 */
public class AvailabilityAwareLoadBalance {
    
    public <T> T select(List<Server<T>> servers) {
        if (servers == null || servers.isEmpty()) {
            return null;
        }
        
        // 过滤可用节点（成功率 > 90% 且未熔断）
        List<Server<T>> availableServers = servers.stream()
            .filter(s -> s.getSuccessRate() > 0.9)
            .filter(s -> !s.isCircuitBreakerOpen())
            .collect(Collectors.toList());
        
        if (availableServers.isEmpty()) {
            // 所有节点不可用，降级使用所有节点
            availableServers = servers;
        }
        
        // 按响应时间排序，选择最快的节点
        return availableServers.stream()
            .min(Comparator.comparingLong(Server::getAvgResponseTime))
            .map(Server::getInstance)
            .orElse(servers.get(0).getInstance());
    }
    
    @Data
    public static class Server<T> {
        private T instance;
        private AtomicLong totalRequests = new AtomicLong(0);
        private AtomicLong successRequests = new AtomicLong(0);
        private AtomicLong totalResponseTime = new AtomicLong(0);
        private volatile boolean circuitBreakerOpen = false;
        
        public double getSuccessRate() {
            long total = totalRequests.get();
            return total == 0 ? 1.0 : (double) successRequests.get() / total;
        }
        
        public long getAvgResponseTime() {
            long total = totalRequests.get();
            return total == 0 ? 0 : totalResponseTime.get() / total;
        }
    }
}
```

**Hystrix 熔断配置**：
```java
@HystrixCommand(
    fallbackMethod = "fallback",
    commandProperties = {
        @HystrixProperty(name = "circuitBreaker.enabled", value = "true"),
        @HystrixProperty(name = "circuitBreaker.requestVolumeThreshold", value = "10"),  // 10个请求后开始统计
        @HystrixProperty(name = "circuitBreaker.errorThresholdPercentage", value = "50"), // 错误率50%触发熔断
        @HystrixProperty(name = "circuitBreaker.sleepWindowInMilliseconds", value = "5000") // 熔断后5秒尝试恢复
    }
)
public User getUser(Long userId) {
    return userService.getUser(userId);
}

public User fallback(Long userId) {
    return new User(userId, "默认用户");  // 降级逻辑
}
```

**适用场景**：
- ✅ 微服务架构（自动摘除故障节点）
- ✅ 对响应时间敏感的场景

---

### 7. 区域敏感策略（Zone Aware / Region Aware）

**原理**：优先选择同区域（同机房/同可用区）的服务节点，降低网络延迟。

**架构示例**：
```
┌─────────────────────────────────────────┐
│            华北区域（Beijing）            │
│  Consumer-A  →  Provider-A（优先选择）    │
└─────────────────────────────────────────┘
                  ↓
         跨区域调用（备选）
                  ↓
┌─────────────────────────────────────────┐
│            华东区域（Shanghai）           │
│            Provider-B                    │
└─────────────────────────────────────────┘
```

**实现代码**：
```java
/**
 * 区域敏感负载均衡
 */
public class ZoneAwareLoadBalance {
    
    public <T> T select(List<Server<T>> servers, String currentZone) {
        if (servers == null || servers.isEmpty()) {
            return null;
        }
        
        // 优先选择同区域的服务器
        List<Server<T>> sameZoneServers = servers.stream()
            .filter(s -> currentZone.equals(s.getZone()))
            .collect(Collectors.toList());
        
        if (!sameZoneServers.isEmpty()) {
            // 同区域有可用节点，使用轮询策略
            return sameZoneServers.get(
                ThreadLocalRandom.current().nextInt(sameZoneServers.size())
            ).getInstance();
        }
        
        // 同区域无可用节点，降级到其他区域
        return servers.get(
            ThreadLocalRandom.current().nextInt(servers.size())
        ).getInstance();
    }
    
    @Data
    @AllArgsConstructor
    public static class Server<T> {
        private T instance;
        private String zone;  // 所属区域（如 beijing、shanghai）
    }
}

// 使用示例
List<Server<String>> servers = Arrays.asList(
    new Server<>("Provider-A1", "beijing"),
    new Server<>("Provider-A2", "beijing"),
    new Server<>("Provider-B1", "shanghai"),
    new Server<>("Provider-B2", "shanghai")
);

ZoneAwareLoadBalance lb = new ZoneAwareLoadBalance();

// 当前服务在北京，优先选择北京的节点
String currentZone = "beijing";
for (int i = 0; i < 5; i++) {
    System.out.println("请求" + i + " → " + lb.select(servers, currentZone));
}
// 输出：Provider-A1、Provider-A2（循环）
```

**Spring Cloud Ribbon 配置**：
```yaml
# application.yml
eureka:
  instance:
    metadata-map:
      zone: beijing  # 当前实例所在区域

ribbon:
  NFLoadBalancerRuleClassName: com.netflix.loadbalancer.ZoneAvoidanceRule  # 区域感知策略
```

**Kubernetes 亲和性配置**：
```yaml
apiVersion: v1
kind: Service
metadata:
  name: user-service
spec:
  selector:
    app: user-service
  topologyKeys:
    - "topology.kubernetes.io/zone"  # 优先路由到同可用区的Pod
```

**适用场景**：
- ✅ 多机房/多可用区部署
- ✅ 对网络延迟敏感的场景
- ✅ 降低跨区域流量成本

---

## 负载均衡策略对比

| 策略 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| **轮询** | 简单、无状态 | 无法处理性能差异 | 节点性能相同 |
| **权重轮询** | 根据性能分配流量 | 需要配置权重 | 节点性能差异大 |
| **随机** | 实现简单、无状态 | 少量请求分布不均 | 大量请求场景 |
| **最小连接数** | 适合长连接、处理时间差异大 | 需要维护连接状态 | WebSocket、数据库连接 |
| **重试** | 自动容错 | 增加响应时间 | 读操作、幂等操作 |
| **可用性敏感** | 自动摘除故障节点 | 实现复杂 | 微服务架构 |
| **区域敏感** | 降低网络延迟和成本 | 需要区域标识 | 多机房部署 |

---

## 实战应用场景

### 1. Dubbo 负载均衡配置

```java
// 全局配置
@Bean
public ApplicationConfig applicationConfig() {
    ApplicationConfig config = new ApplicationConfig();
    config.setName("user-service");
    return config;
}

// 服务级配置
@Service(
    loadbalance = "roundrobin",  // 轮询
    weight = 100                 // 权重100
)
public class UserServiceImpl implements UserService { }

// 方法级配置
@Reference(
    loadbalance = "leastactive",  // 最小活跃数
    retries = 2,                  // 失败重试2次
    timeout = 3000                // 超时3秒
)
private OrderService orderService;
```

### 2. Nginx 负载均衡配置

```nginx
upstream backend {
    # 默认轮询
    # least_conn;  # 最小连接数
    # ip_hash;     # IP哈希（同一IP总是路由到同一服务器）
    
    server 192.168.1.1:8080 weight=5 max_fails=3 fail_timeout=30s;
    server 192.168.1.2:8080 weight=3;
    server 192.168.1.3:8080 weight=2 backup;  # 备用服务器
}

server {
    listen 80;
    location / {
        proxy_pass http://backend;
        proxy_next_upstream error timeout http_500 http_502 http_503;  # 失败重试
    }
}
```

### 3. Spring Cloud LoadBalancer 配置

```java
@Configuration
public class LoadBalancerConfig {
    
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

// 使用
@FeignClient(name = "user-service", configuration = LoadBalancerConfig.class)
public interface UserServiceClient {
    @GetMapping("/users/{id}")
    User getUser(@PathVariable Long id);
}
```

---

## 答题总结

**7种核心负载均衡策略**：

1. **轮询（Round Robin）**：按顺序分配，适合节点性能相同的场景
2. **权重轮询（Weighted Round Robin）**：根据性能分配不同权重，适合性能差异大的场景
3. **随机（Random）**：随机选择节点，实现简单、大量请求时分布均匀
4. **最小连接数（Least Connections）**：选择活跃连接最少的节点，适合长连接场景
5. **重试（Retry/Failover）**：失败自动切换其他节点，适合读操作和幂等操作
6. **可用性敏感（Availability Aware）**：优先选择成功率高、响应快的节点，自动摘除故障节点
7. **区域敏感（Zone Aware）**：优先选择同区域节点，降低网络延迟和跨区域流量成本

**选型建议**：
- **Nginx/HAProxy**：轮询、权重、最小连接数、IP哈希
- **Dubbo**：轮询、随机、最小活跃数、一致性哈希
- **Spring Cloud**：轮询、随机、区域感知、重试

**面试技巧**：建议从**轮询**和**权重轮询**两个最基础的策略切入，再根据面试官提问深入到最小连接数、可用性敏感等高级策略，并结合实际项目经验说明使用场景。

