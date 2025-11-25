---
layout: default
title: "Dubbo支持哪些负载均衡策略？"
parent: RPC
nav_order: 565
description: "详细介绍Dubbo的负载均衡机制及其支持的Random、RoundRobin、LeastActive等多种策略"
date: 2025-11-02
---
## 核心概念

**负载均衡**是指在多个服务提供者（Provider）之间分配请求的策略。Dubbo 在 **Consumer 端实现负载均衡**，由客户端根据策略选择一个 Provider 发起调用，避免了中心化代理的性能瓶颈。

**核心特点**：
- **客户端负载均衡**：在 Consumer 端选择 Provider
- **多种策略**：支持随机、轮询、最少活跃数等
- **可扩展**：基于 SPI 机制，可自定义策略
- **动态权重**：支持服务提供者权重配置

## Dubbo 支持的负载均衡策略

### 1. Random（随机，默认）

**原理**：
- 按**权重随机**选择 Provider
- 权重相同时，完全随机
- 权重不同时，权重越大被选中概率越高

**实现代码**：
```java
public class RandomLoadBalance extends AbstractLoadBalance {
    
    @Override
    protected <T> Invoker<T> doSelect(List<Invoker<T>> invokers, Invocation invocation) {
        int length = invokers.size();
        
        // 1. 计算总权重
        int totalWeight = 0;
        boolean sameWeight = true;
        
        for (int i = 0; i < length; i++) {
            int weight = getWeight(invokers.get(i), invocation);
            totalWeight += weight;
            
            if (sameWeight && i > 0 && weight != getWeight(invokers.get(i - 1), invocation)) {
                sameWeight = false;
            }
        }
        
        // 2. 如果权重不同，按权重随机
        if (totalWeight > 0 && !sameWeight) {
            int offset = ThreadLocalRandom.current().nextInt(totalWeight);
            
            for (Invoker<T> invoker : invokers) {
                offset -= getWeight(invoker, invocation);
                if (offset < 0) {
                    return invoker;
                }
            }
        }
        
        // 3. 权重相同，直接随机
        return invokers.get(ThreadLocalRandom.current().nextInt(length));
    }
}
```

**配置方式**：
```java
// 服务级别配置
@Service(loadbalance = "random")
public class UserServiceImpl implements UserService {
    // ...
}

// 方法级别配置
@Service
public class UserServiceImpl implements UserService {
    
    @Method(name = "getUser", loadbalance = "random")
    public User getUser(Long userId) {
        // ...
    }
}

// Consumer 端配置（优先级更高）
@Reference(loadbalance = "random")
private UserService userService;
```

**权重配置**：
```java
// Provider 端配置权重
@Service(weight = 200)  // 默认权重 100
public class UserServiceImpl implements UserService {
    // ...
}

// 动态配置权重（Dubbo Admin）
// dubbo.registry.address=zookeeper://127.0.0.1:2181
// 服务A：权重 200（处理能力强）
// 服务B：权重 100（处理能力一般）
// 服务C：权重  50（处理能力弱）
```

**适用场景**：
- ✅ **默认选择**，适合大多数场景
- ✅ 服务提供者性能差异大（通过权重调整）
- ✅ 无状态服务
- ❌ 需要严格均匀分配的场景

**示例**：
```java
// 假设有 3 个 Provider
// Provider A: 权重 100
// Provider B: 权重 200
// Provider C: 权重 100
// 
// 总权重 = 400
// 随机数 offset = random(0, 400)
// 
// offset ∈ [0, 100)   → 选择 A
// offset ∈ [100, 300) → 选择 B
// offset ∈ [300, 400) → 选择 C
// 
// 结果：B 的调用量是 A 和 C 的 2 倍
```

### 2. RoundRobin（轮询）

**原理**：
- 按**权重轮询**
- 每个 Provider 依次被调用
- 支持权重，权重越大被调用次数越多

**实现代码**：
```java
public class RoundRobinLoadBalance extends AbstractLoadBalance {
    
    // 每个服务的调用计数器
    private final ConcurrentMap<String, AtomicPositiveInteger> sequences = 
        new ConcurrentHashMap<>();
    
    @Override
    protected <T> Invoker<T> doSelect(List<Invoker<T>> invokers, Invocation invocation) {
        String key = invokers.get(0).getUrl().getServiceKey() + "." + invocation.getMethodName();
        
        int length = invokers.size();
        int maxWeight = 0;
        int minWeight = Integer.MAX_VALUE;
        
        // 1. 计算最大、最小权重
        for (Invoker<T> invoker : invokers) {
            int weight = getWeight(invoker, invocation);
            maxWeight = Math.max(maxWeight, weight);
            minWeight = Math.min(minWeight, weight);
        }
        
        // 2. 如果权重不同，使用加权轮询
        if (maxWeight > 0 && minWeight < maxWeight) {
            AtomicPositiveInteger sequence = sequences.computeIfAbsent(key, 
                k -> new AtomicPositiveInteger());
            
            int currentWeight = sequence.getAndIncrement() % (maxWeight * length);
            
            for (int i = 0; i < length; i++) {
                int weight = getWeight(invokers.get(i), invocation);
                if (currentWeight < weight) {
                    return invokers.get(i);
                }
                currentWeight -= weight;
            }
        }
        
        // 3. 权重相同，简单轮询
        AtomicPositiveInteger sequence = sequences.computeIfAbsent(key, 
            k -> new AtomicPositiveInteger());
        return invokers.get(sequence.getAndIncrement() % length);
    }
}
```

**配置方式**：
```java
@Service(loadbalance = "roundrobin")
public class UserServiceImpl implements UserService {
    // ...
}

@Reference(loadbalance = "roundrobin")
private UserService userService;
```

**适用场景**：
- ✅ 需要**均匀分配**请求
- ✅ 每个请求的处理时间相近
- ✅ 服务提供者性能一致
- ❌ 请求处理时间差异大（可能导致某些 Provider 积压）

**示例**：
```java
// 假设有 3 个 Provider（权重相同）
// Provider A、B、C
// 
// 调用顺序：A → B → C → A → B → C → ...
// 
// 假设权重不同：
// Provider A: 权重 100
// Provider B: 权重 200
// Provider C: 权重 100
// 
// 调用顺序：A → B → B → C → A → B → B → C → ...
// 结果：B 的调用次数是 A 和 C 的 2 倍
```

### 3. LeastActive（最少活跃数，推荐）

**原理**：
- 选择**活跃调用数最少**的 Provider
- 活跃数：正在处理的请求数量
- 慢的 Provider 收到更少请求，快的 Provider 收到更多请求
- **自动负载均衡**，适应不同性能的 Provider

**实现代码**：
```java
public class LeastActiveLoadBalance extends AbstractLoadBalance {
    
    @Override
    protected <T> Invoker<T> doSelect(List<Invoker<T>> invokers, Invocation invocation) {
        int length = invokers.size();
        
        // 1. 找出最少活跃数
        int leastActive = -1;
        int leastCount = 0;  // 最少活跃数的 Provider 数量
        int[] leastIndexes = new int[length];
        int totalWeight = 0;
        int firstWeight = 0;
        boolean sameWeight = true;
        
        for (int i = 0; i < length; i++) {
            Invoker<T> invoker = invokers.get(i);
            // 获取活跃数（正在处理的请求数）
            int active = RpcStatus.getStatus(invoker.getUrl(), invocation.getMethodName()).getActive();
            int weight = getWeight(invoker, invocation);
            
            if (leastActive == -1 || active < leastActive) {
                leastActive = active;
                leastCount = 1;
                leastIndexes[0] = i;
                totalWeight = weight;
                firstWeight = weight;
                sameWeight = true;
            } else if (active == leastActive) {
                leastIndexes[leastCount++] = i;
                totalWeight += weight;
                if (sameWeight && weight != firstWeight) {
                    sameWeight = false;
                }
            }
        }
        
        // 2. 如果只有一个最少活跃数的 Provider，直接返回
        if (leastCount == 1) {
            return invokers.get(leastIndexes[0]);
        }
        
        // 3. 有多个最少活跃数的 Provider，按权重随机
        if (!sameWeight && totalWeight > 0) {
            int offsetWeight = ThreadLocalRandom.current().nextInt(totalWeight);
            for (int i = 0; i < leastCount; i++) {
                int leastIndex = leastIndexes[i];
                offsetWeight -= getWeight(invokers.get(leastIndex), invocation);
                if (offsetWeight < 0) {
                    return invokers.get(leastIndex);
                }
            }
        }
        
        // 4. 权重相同，随机选择
        return invokers.get(leastIndexes[ThreadLocalRandom.current().nextInt(leastCount)]);
    }
}
```

**配置方式**：
```java
@Service(loadbalance = "leastactive")
public class UserServiceImpl implements UserService {
    // ...
}

@Reference(loadbalance = "leastactive")
private UserService userService;
```

**适用场景**：
- ✅ **推荐使用**，智能负载均衡
- ✅ Provider 性能差异大
- ✅ 请求处理时间差异大
- ✅ 自动避开慢节点
- ✅ 异构集群（不同配置的服务器）

**示例**：
```java
// 假设有 3 个 Provider
// Provider A: 当前活跃数 10（慢）
// Provider B: 当前活跃数  2（快）
// Provider C: 当前活跃数  5（中）
// 
// 选择：Provider B（活跃数最少）
// 
// 优势：
// - 慢的 Provider 自动收到更少请求
// - 快的 Provider 自动承担更多流量
// - 无需手动配置权重
```

### 4. ConsistentHash（一致性哈希）

**原理**：
- 根据**请求参数**进行哈希，相同参数总是路由到同一个 Provider
- 适合**有状态服务**（如缓存、会话）
- 基于**一致性哈希环**，节点变化时影响范围小

**实现代码**：
```java
public class ConsistentHashLoadBalance extends AbstractLoadBalance {
    
    @Override
    protected <T> Invoker<T> doSelect(List<Invoker<T>> invokers, Invocation invocation) {
        String methodName = invocation.getMethodName();
        String key = invokers.get(0).getUrl().getServiceKey() + "." + methodName;
        
        // 获取或创建一致性哈希选择器
        ConsistentHashSelector<T> selector = selectors.get(key);
        if (selector == null || selector.getInvokerHashCode() != invokers.hashCode()) {
            selector = new ConsistentHashSelector<>(invokers, methodName, invocation);
            selectors.put(key, selector);
        }
        
        return selector.select(invocation);
    }
    
    private static class ConsistentHashSelector<T> {
        
        // 虚拟节点（160 个虚拟节点）
        private final TreeMap<Long, Invoker<T>> virtualInvokers;
        
        ConsistentHashSelector(List<Invoker<T>> invokers, String methodName, Invocation invocation) {
            virtualInvokers = new TreeMap<>();
            
            // 为每个 Provider 创建虚拟节点
            for (Invoker<T> invoker : invokers) {
                String address = invoker.getUrl().getAddress();
                
                // 每个 Provider 创建 160 个虚拟节点
                for (int i = 0; i < 160; i++) {
                    byte[] digest = md5(address + i);
                    for (int j = 0; j < 4; j++) {
                        long hash = hash(digest, j);
                        virtualInvokers.put(hash, invoker);
                    }
                }
            }
        }
        
        public Invoker<T> select(Invocation invocation) {
            // 根据请求参数计算哈希值
            String key = toKey(invocation.getArguments());
            byte[] digest = md5(key);
            long hash = hash(digest, 0);
            
            // 在哈希环上找到最近的 Provider
            Map.Entry<Long, Invoker<T>> entry = virtualInvokers.ceilingEntry(hash);
            if (entry == null) {
                entry = virtualInvokers.firstEntry();
            }
            
            return entry.getValue();
        }
    }
}
```

**配置方式**：
```java
// 默认根据第一个参数进行哈希
@Service(loadbalance = "consistenthash")
public class UserServiceImpl implements UserService {
    // ...
}

// 指定哈希参数位置（多个参数）
@Service(loadbalance = "consistenthash", 
         parameters = {"hash.arguments", "0,1"})  // 根据第1、2个参数哈希
public class UserServiceImpl implements UserService {
    User getUser(Long userId, String type);
}

// 指定虚拟节点数
@Service(loadbalance = "consistenthash", 
         parameters = {"hash.nodes", "320"})  // 320 个虚拟节点
public class UserServiceImpl implements UserService {
    // ...
}
```

**适用场景**：
- ✅ 有状态服务（缓存、会话保持）
- ✅ 需要**请求亲和性**（相同参数路由到同一节点）
- ✅ 分布式缓存场景
- ❌ 无状态服务（推荐用其他策略）

**示例**：
```java
// 缓存场景
@Service(loadbalance = "consistenthash")
public class CacheServiceImpl implements CacheService {
    
    @Override
    public String get(String key) {
        // 相同的 key 总是路由到同一个 Provider
        // 提高缓存命中率
        return cache.get(key);
    }
}

// 调用示例
cacheService.get("user:123");  // 路由到 Provider A
cacheService.get("user:123");  // 路由到 Provider A（相同节点）
cacheService.get("user:456");  // 可能路由到 Provider B
```

### 5. ShortestResponse（最短响应时间，Dubbo 3.0+）

**原理**：
- 选择**平均响应时间最短**的 Provider
- 综合考虑活跃数和响应时间
- 比 LeastActive 更智能

**配置方式**：
```java
@Service(loadbalance = "shortestresponse")
public class UserServiceImpl implements UserService {
    // ...
}
```

**适用场景**：
- ✅ Dubbo 3.0+ 推荐使用
- ✅ 替代 LeastActive
- ✅ 更精准的负载均衡

## 负载均衡策略对比

| 策略 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **Random** | 随机 + 权重 | 简单，性能好 | 可能不均匀 | 默认选择 |
| **RoundRobin** | 轮询 + 权重 | 分配均匀 | 慢节点可能积压 | 性能一致的集群 |
| **LeastActive** | 最少活跃数 | 自动避开慢节点 | 稍复杂 | **推荐**，异构集群 |
| **ConsistentHash** | 一致性哈希 | 请求亲和性 | 不均匀 | 有状态服务 |
| **ShortestResponse** | 最短响应时间 | 最智能 | Dubbo 3.0+ | Dubbo 3.0+ |

## 自定义负载均衡策略

```java
// 1. 实现 LoadBalance 接口
@SPI
public class MyLoadBalance extends AbstractLoadBalance {
    
    @Override
    protected <T> Invoker<T> doSelect(List<Invoker<T>> invokers, Invocation invocation) {
        // 自定义选择逻辑
        // 例如：根据地理位置、机房就近选择
        String clientRegion = RpcContext.getContext().getAttachment("region");
        
        for (Invoker<T> invoker : invokers) {
            String providerRegion = invoker.getUrl().getParameter("region");
            if (clientRegion.equals(providerRegion)) {
                return invoker;
            }
        }
        
        // 没有同地域的，随机选择
        return invokers.get(ThreadLocalRandom.current().nextInt(invokers.size()));
    }
}

// 2. 配置 SPI
// META-INF/dubbo/org.apache.dubbo.rpc.cluster.LoadBalance
// myloadbalance=com.example.MyLoadBalance

// 3. 使用自定义策略
@Service(loadbalance = "myloadbalance")
public class UserServiceImpl implements UserService {
    // ...
}
```

## 最佳实践

### 1. 根据场景选择策略

```java
// 常规业务：Random（默认）
@Service(loadbalance = "random")
public class OrderServiceImpl { }

// 异构集群：LeastActive
@Service(loadbalance = "leastactive")
public class PaymentServiceImpl { }

// 缓存服务：ConsistentHash
@Service(loadbalance = "consistenthash")
public class CacheServiceImpl { }
```

### 2. 配置权重

```java
// Provider 端配置权重
@Service(weight = 200)  // 高性能服务器
public class UserServiceImpl { }

@Service(weight = 100)  // 普通服务器
public class UserServiceImpl { }

// 动态调整权重（Dubbo Admin）
// 实时调整，无需重启
```

### 3. Consumer 端覆盖

```java
// Consumer 端可以覆盖 Provider 的配置
@Reference(
    loadbalance = "leastactive",  // 覆盖 Provider 的配置
    retries = 2                    // 失败重试
)
private UserService userService;
```

### 4. 方法级别配置

```java
@Service
public class UserServiceImpl implements UserService {
    
    // 读操作：轮询
    @Method(name = "getUser", loadbalance = "roundrobin")
    public User getUser(Long userId) { }
    
    // 写操作：最少活跃数
    @Method(name = "updateUser", loadbalance = "leastactive")
    public void updateUser(User user) { }
}
```

## 答题总结

**Dubbo 支持的负载均衡策略及选择建议**：

**1. 核心策略（按推荐度）**：
- **Random**：随机 + 权重，**默认策略** ⭐⭐⭐⭐
- **LeastActive**：最少活跃数，**推荐使用** ⭐⭐⭐⭐⭐
- **RoundRobin**：轮询 + 权重 ⭐⭐⭐⭐
- **ConsistentHash**：一致性哈希，有状态服务 ⭐⭐⭐⭐
- **ShortestResponse**：最短响应时间（Dubbo 3.0+） ⭐⭐⭐⭐⭐

**2. 选择建议**：
- **默认/通用** → Random
- **异构集群/智能** → LeastActive
- **均匀分配** → RoundRobin
- **有状态/缓存** → ConsistentHash
- **Dubbo 3.0+** → ShortestResponse

**3. 核心机制**：
- **客户端负载均衡**：在 Consumer 端选择 Provider
- **权重支持**：可配置不同 Provider 的权重
- **活跃数统计**：实时统计每个 Provider 的活跃请求数
- **可扩展**：基于 SPI，可自定义策略

**4. 配置方式**：
```java
@Service(loadbalance = "leastactive", weight = 200)
@Reference(loadbalance = "random")
```

**面试技巧**：强调 **Random 是默认策略**，**LeastActive 更智能**（自动避开慢节点），**ConsistentHash 适合有状态服务**。可以画出负载均衡的选择流程图，体现对分布式系统的理解。

