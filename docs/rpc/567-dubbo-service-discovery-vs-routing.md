---
layout: default
title: "Dubbo服务发现与路由的概念有什么不同？"
parent: RPC
nav_order: 567
description: "深入理解Dubbo中服务发现和路由的概念差异、作用阶段及其在服务调用链路中的职责划分"
date: 2025-11-02
---
## 核心概念

**服务发现**和**路由**是 Dubbo 服务调用链路中的两个**不同阶段**，它们解决不同的问题：

- **服务发现（Service Discovery）**：解决"**有哪些**服务提供者可用"的问题
- **路由（Routing）**：解决"**选择哪个**服务提供者"的问题

**核心区别**：
- **服务发现**是**静态的**，获取全量的可用 Provider 列表
- **路由**是**动态的**，根据规则从 Provider 列表中筛选、排序

## 服务发现（Service Discovery）

### 1. 核心职责

**服务发现负责**：
- Provider 启动时，向注册中心**注册**服务
- Consumer 启动时，从注册中心**订阅**服务
- 实时感知 Provider 的**上线/下线**
- 维护**全量的可用 Provider 列表**

### 2. 实现机制

```java
// ==================== Provider 端：服务注册 ====================
@Service
public class UserServiceImpl implements UserService {
    // 启动时，向注册中心注册服务
}

// 注册的信息：
// dubbo://192.168.1.100:20880/com.example.UserService
//   ?version=1.0.0
//   &group=default
//   &timeout=3000
//   &serialization=hessian2
//   &methods=getUser,updateUser

// ==================== Consumer 端：服务订阅 ====================
@Reference
private UserService userService;

// 启动时，向注册中心订阅服务
// 获取所有 Provider 的地址列表：
// [
//   dubbo://192.168.1.100:20880/com.example.UserService,
//   dubbo://192.168.1.101:20880/com.example.UserService,
//   dubbo://192.168.1.102:20880/com.example.UserService
// ]

// ==================== 动态感知 ====================
// Provider 下线 → 注册中心通知 Consumer → 从列表中移除
// Provider 上线 → 注册中心通知 Consumer → 添加到列表中
```

### 3. 服务发现流程

```java
// Consumer 启动流程
public class ServiceDiscoveryProcess {
    
    public void start() {
        // 1. 连接注册中心
        Registry registry = registryFactory.getRegistry(registryUrl);
        
        // 2. 订阅服务
        registry.subscribe(
            URL.valueOf("consumer://192.168.1.200/com.example.UserService"),
            new NotifyListener() {
                @Override
                public void notify(List<URL> urls) {
                    // 3. 接收 Provider 列表
                    // urls = [
                    //   dubbo://192.168.1.100:20880/UserService,
                    //   dubbo://192.168.1.101:20880/UserService,
                    //   dubbo://192.168.1.102:20880/UserService
                    // ]
                    
                    // 4. 更新本地 Provider 列表
                    updateProviders(urls);
                    
                    // 5. 建立连接
                    for (URL url : urls) {
                        createConnection(url);
                    }
                }
            }
        );
    }
    
    // 实时感知 Provider 变化
    public void handleProviderChange(List<URL> newUrls) {
        // 对比新旧列表
        // 下线的 Provider → 关闭连接
        // 上线的 Provider → 建立连接
    }
}
```

### 4. 注册中心的作用

```java
// Zookeeper 结构示例
/dubbo
  /com.example.UserService
    /providers
      /dubbo%3A%2F%2F192.168.1.100%3A20880%2FUserService  (临时节点)
      /dubbo%3A%2F%2F192.168.1.101%3A20880%2FUserService  (临时节点)
      /dubbo%3A%2F%2F192.168.1.102%3A20880%2FUserService  (临时节点)
    /consumers
      /consumer%3A%2F%2F192.168.1.200%2FUserService  (临时节点)
    /configurators  (配置规则)
    /routers  (路由规则)

// Provider 下线
// 1. Provider 进程退出
// 2. Zookeeper 检测到心跳丢失
// 3. 删除临时节点
// 4. 触发 Watch 机制
// 5. 通知所有订阅的 Consumer
// 6. Consumer 从列表中移除该 Provider
```

## 路由（Routing）

### 1. 核心职责

**路由负责**：
- 从全量 Provider 列表中**筛选**符合条件的
- 根据规则**排序**或**分组**
- 实现**流量控制**（灰度、AB测试、地域就近）
- **不改变** Provider 列表的可用性，只影响选择

### 2. 路由类型

**（1）条件路由（Condition Router）**
```java
// 规则格式：condition://0.0.0.0/com.example.UserService
//   ?category=routers
//   &rule=<条件> => <结果>

// 示例 1：VIP 用户路由到高性能服务器
// consumer.vip = true => host = 192.168.1.100

// 示例 2：测试环境路由到测试服务器
// consumer.env = test => host = 192.168.1.101

// 示例 3：按地域就近路由
// consumer.region = beijing => provider.region = beijing

// 示例 4：强制路由（排除某些 Provider）
// => host != 192.168.1.102
```

```java
// 代码实现
public class ConditionRouter implements Router {
    
    @Override
    public <T> List<Invoker<T>> route(List<Invoker<T>> invokers, Invocation invocation) {
        // 1. 解析条件
        String vip = RpcContext.getContext().getAttachment("vip");
        
        if ("true".equals(vip)) {
            // 2. 筛选符合条件的 Provider
            return invokers.stream()
                .filter(invoker -> "192.168.1.100".equals(invoker.getUrl().getHost()))
                .collect(Collectors.toList());
        }
        
        // 3. 不满足条件，返回所有
        return invokers;
    }
}
```

**（2）标签路由（Tag Router）**
```java
// Provider 配置标签
@Service(tag = "gray")
public class UserServiceGrayImpl implements UserService {
    // 灰度环境
}

@Service(tag = "stable")
public class UserServiceImpl implements UserService {
    // 稳定环境
}

// Consumer 指定标签
RpcContext.getContext().setAttachment("tag", "gray");
User user = userService.getUser(123L);  // 路由到灰度环境

// 路由逻辑
public class TagRouter implements Router {
    
    @Override
    public <T> List<Invoker<T>> route(List<Invoker<T>> invokers, Invocation invocation) {
        String requestTag = RpcContext.getContext().getAttachment("tag");
        
        if (requestTag != null) {
            // 筛选匹配标签的 Provider
            List<Invoker<T>> taggedInvokers = invokers.stream()
                .filter(invoker -> requestTag.equals(invoker.getUrl().getParameter("tag")))
                .collect(Collectors.toList());
            
            if (!taggedInvokers.isEmpty()) {
                return taggedInvokers;
            }
        }
        
        // 没有匹配标签，返回无标签的 Provider
        return invokers.stream()
            .filter(invoker -> invoker.getUrl().getParameter("tag") == null)
            .collect(Collectors.toList());
    }
}
```

**（3）脚本路由（Script Router）**
```javascript
// 使用 JavaScript 脚本自定义路由
function route(invokers, invocation) {
    var result = new java.util.ArrayList();
    
    // 获取请求参数
    var userId = invocation.getArguments()[0];
    
    // 自定义路由逻辑：按用户 ID 哈希分流
    var targetRegion = (userId % 2 == 0) ? "regionA" : "regionB";
    
    for (var i = 0; i < invokers.size(); i++) {
        var invoker = invokers.get(i);
        var region = invoker.getUrl().getParameter("region");
        
        if (region == targetRegion) {
            result.add(invoker);
        }
    }
    
    return result;
}
```

### 3. 路由链

Dubbo 支持**多个路由规则**组成路由链：

```java
// 路由链执行顺序
public class RouterChain {
    
    private List<Router> routers = Arrays.asList(
        new ConditionRouter(),  // 条件路由
        new TagRouter(),        // 标签路由
        new ScriptRouter()      // 脚本路由
    );
    
    public <T> List<Invoker<T>> route(List<Invoker<T>> invokers, Invocation invocation) {
        List<Invoker<T>> result = invokers;
        
        // 依次执行每个路由规则
        for (Router router : routers) {
            result = router.route(result, invocation);
            
            // 如果某个路由规则筛选后为空，终止路由链
            if (result.isEmpty()) {
                break;
            }
        }
        
        return result;
    }
}

// 执行流程示例
// 初始 Provider 列表：[A, B, C, D, E]
// 
// 1. ConditionRouter 筛选
//    条件：consumer.region = beijing
//    结果：[A, B, C]  (只有 A、B、C 在北京)
// 
// 2. TagRouter 筛选
//    条件：tag = gray
//    结果：[A, B]  (只有 A、B 是灰度标签)
// 
// 3. ScriptRouter 筛选
//    条件：userId % 2 == 0
//    结果：[A]  (只有 A 符合自定义规则)
// 
// 最终：从 [A] 中进行负载均衡
```

## 服务发现 vs 路由对比

### 1. 核心区别

| 维度 | 服务发现 | 路由 |
|------|----------|------|
| **目标** | 获取全量 Provider 列表 | 从列表中筛选符合条件的 |
| **时机** | 服务启动、Provider 上下线 | 每次 RPC 调用前 |
| **频率** | 低频（Provider 变化时） | 高频（每次调用） |
| **依赖** | 注册中心（Zookeeper、Nacos） | 本地内存（路由规则） |
| **作用范围** | 所有 Consumer | 单次调用 |
| **可配置性** | 自动（框架完成） | 灵活（规则可配置） |

### 2. 调用链路中的位置

```java
// ==================== 完整调用流程 ====================

// 1. 服务发现阶段（启动时）
@Reference
private UserService userService;
// ↓
// Consumer 启动，订阅服务
// 从注册中心获取 Provider 列表：
// [Provider-A, Provider-B, Provider-C, Provider-D, Provider-E]

// 2. 调用阶段（运行时）
User user = userService.getUser(123L);
// ↓
// 【路由阶段】从 Provider 列表中筛选
// 条件路由 → [Provider-A, Provider-B, Provider-C]
// 标签路由 → [Provider-A, Provider-B]
// ↓
// 【负载均衡】从筛选后的列表中选择一个
// 负载均衡策略（LeastActive） → Provider-A
// ↓
// 【发起 RPC 调用】
// 调用 Provider-A 的 getUser 方法
```

### 3. 职责划分

```java
// 服务发现的职责
public interface ServiceDiscovery {
    // 注册服务
    void register(URL url);
    
    // 注销服务
    void unregister(URL url);
    
    // 订阅服务（获取全量 Provider 列表）
    void subscribe(URL url, NotifyListener listener);
    
    // 取消订阅
    void unsubscribe(URL url, NotifyListener listener);
    
    // 查询服务（返回所有可用 Provider）
    List<URL> lookup(URL url);
}

// 路由的职责
public interface Router {
    // 从 Provider 列表中筛选符合条件的
    <T> List<Invoker<T>> route(List<Invoker<T>> invokers, Invocation invocation);
    
    // 路由规则优先级
    int getPriority();
}
```

## 实际应用场景

### 场景 1：灰度发布

```java
// 1. 服务发现：获取所有 Provider
// [
//   Provider-A (stable),
//   Provider-B (stable),
//   Provider-C (gray, version=2.0)
// ]

// 2. 路由：根据标签筛选
@Reference
private UserService userService;

// 普通用户 → 路由到 stable
User user1 = userService.getUser(123L);
// 路由结果：[Provider-A, Provider-B]

// 灰度用户 → 路由到 gray
RpcContext.getContext().setAttachment("tag", "gray");
User user2 = userService.getUser(456L);
// 路由结果：[Provider-C]
```

### 场景 2：跨机房调用

```java
// 1. 服务发现：获取所有 Provider
// [
//   Provider-A (region=beijing),
//   Provider-B (region=beijing),
//   Provider-C (region=shanghai)
// ]

// 2. 路由：就近路由
// 北京的 Consumer → 路由到北京的 Provider
RpcContext.getContext().setAttachment("region", "beijing");
User user = userService.getUser(123L);
// 路由结果：[Provider-A, Provider-B]

// 3. 负载均衡：从 [Provider-A, Provider-B] 中选择一个
```

### 场景 3：AB 测试

```java
// 1. 服务发现：获取所有 Provider
// [Provider-A (v1), Provider-B (v1), Provider-C (v2)]

// 2. 路由：根据用户分组
public class ABTestRouter implements Router {
    
    @Override
    public <T> List<Invoker<T>> route(List<Invoker<T>> invokers, Invocation invocation) {
        Long userId = (Long) invocation.getArguments()[0];
        
        // 10% 用户体验新版本
        if (userId % 10 == 0) {
            // 路由到 v2
            return invokers.stream()
                .filter(i -> "v2".equals(i.getUrl().getParameter("version")))
                .collect(Collectors.toList());
        } else {
            // 路由到 v1
            return invokers.stream()
                .filter(i -> "v1".equals(i.getUrl().getParameter("version")))
                .collect(Collectors.toList());
        }
    }
}
```

## 最佳实践

### 1. 服务发现配置

```yaml
dubbo:
  registry:
    # 注册中心地址
    address: nacos://127.0.0.1:8848
    
    # 注册超时时间
    timeout: 5000
    
    # 会话超时时间
    session: 60000
    
    # 是否注册（Provider）
    register: true
    
    # 是否订阅（Consumer）
    subscribe: true
    
    # 是否动态注册（false 表示不会被自动下线）
    dynamic: true
```

### 2. 路由规则配置

```yaml
# 通过 Dubbo Admin 动态配置
# 或通过配置中心（Nacos、Apollo）

# 条件路由示例
dubbo:
  router:
    condition:
      - "consumer.region = beijing => provider.region = beijing"
      - "consumer.vip = true => provider.host = 192.168.1.100"
    
    # 标签路由
    tag:
      enabled: true
      force: false  # 找不到匹配标签时，是否强制返回空（false 表示降级到无标签）
```

### 3. 混合使用

```java
// 服务发现 + 路由 + 负载均衡 + 容错
@Reference(
    // 服务发现（自动）
    registry = "nacos://127.0.0.1:8848",
    
    // 路由（规则配置）
    // 通过 Dubbo Admin 配置条件路由、标签路由
    
    // 负载均衡
    loadbalance = "leastactive",
    
    // 容错
    cluster = "failover",
    retries = 2
)
private UserService userService;
```

## 答题总结

**服务发现与路由的核心区别**：

**1. 概念差异**：
- **服务发现**：解决"有哪些 Provider 可用"（获取全量列表）
- **路由**：解决"选择哪个 Provider"（从列表中筛选）

**2. 执行时机**：
- **服务发现**：启动时、Provider 上下线时（低频）
- **路由**：每次 RPC 调用前（高频）

**3. 数据来源**：
- **服务发现**：注册中心（Zookeeper、Nacos）
- **路由**：本地内存（路由规则）

**4. 调用链路**：
```
服务发现 → 获取全量 Provider 列表
  ↓
路由 → 根据规则筛选
  ↓
负载均衡 → 选择一个 Provider
  ↓
发起 RPC 调用
```

**5. 典型应用**：
- **服务发现**：Provider 上下线感知、健康检查
- **路由**：灰度发布、AB 测试、跨机房就近调用

**6. 路由类型**：
- **条件路由**：基于条件表达式筛选
- **标签路由**：基于标签匹配
- **脚本路由**：自定义脚本逻辑

**面试技巧**：强调服务发现和路由是**调用链路的不同阶段**，服务发现是**静态的全量获取**，路由是**动态的规则筛选**。可以画出调用链路图，说明两者的协作关系，体现对分布式系统的深入理解。

