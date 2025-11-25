---
title: "什么是RPC，和HTTP有什么区别？"
date: 2025-11-02
categories: [中间件, Dubbo]
tags: [RPC, HTTP, 通信协议, 微服务]
description: "深入理解RPC的概念及其与HTTP协议在功能定位、性能、使用场景上的本质区别"
nav_order: 557
parent: RPC
---
## 核心概念

**RPC（Remote Procedure Call，远程过程调用）** 是一种通信机制，允许程序像调用本地方法一样调用远程服务器上的方法。它屏蔽了底层网络通信的复杂性，使得分布式系统开发更加简单。

**HTTP（HyperText Transfer Protocol）** 是应用层协议，定义了客户端和服务器之间请求和响应的标准格式。

**本质区别**：RPC 是一种**调用方式**（可基于多种传输协议实现），HTTP 是一种**传输协议**。

## 核心区别

### 1. 功能定位

| 维度 | RPC | HTTP |
|------|-----|------|
| **本质** | 远程调用框架 | 传输协议 |
| **目标** | 像调用本地方法一样调用远程服务 | 定义请求/响应格式的标准 |
| **抽象层次** | 更高层的调用抽象 | 底层的传输协议 |

### 2. 传输协议

**RPC**：
- 可基于 TCP（自定义协议）
- 可基于 HTTP/HTTP2
- Dubbo 默认使用 TCP 上的自定义协议

**HTTP**：
- 基于 TCP 协议
- 使用标准的 HTTP/1.1 或 HTTP/2 协议

```java
// RPC 调用示例（Dubbo）
@Reference
private UserService userService;

public void test() {
    // 像调用本地方法一样
    User user = userService.getUserById(123L);
}

// HTTP 调用示例（RestTemplate）
public void test() {
    RestTemplate restTemplate = new RestTemplate();
    // 需要构造 URL、处理序列化等
    String url = "http://user-service/api/user/123";
    User user = restTemplate.getForObject(url, User.class);
}
```

### 3. 序列化方式

**RPC**：
- 使用高效的二进制序列化（Hessian、Protobuf、Kryo）
- 数据体积小，传输速度快
- 可自定义序列化协议

**HTTP**：
- 通常使用 JSON、XML 等文本格式
- 数据体积大，可读性好
- 易于调试和跨语言

```java
// RPC 序列化配置（Dubbo）
@Service(protocol = "dubbo", serialization = "hessian2")
public class UserServiceImpl implements UserService {
    // ...
}

// HTTP 序列化（Spring MVC）
@RestController
public class UserController {
    @GetMapping("/user/{id}")
    public User getUser(@PathVariable Long id) {
        // 自动转为 JSON
        return userService.getUserById(id);
    }
}
```

### 4. 性能对比

**RPC 更快的原因**：
- **传输协议**：基于 TCP 的自定义协议，减少了 HTTP 的头部开销
- **序列化**：二进制序列化比 JSON 更高效
- **连接复用**：长连接复用，减少握手开销
- **负载均衡**：框架内置，无需额外跳转

**HTTP 的优势**：
- 通用性好，兼容性强
- 易于调试和监控
- 天然支持浏览器访问
- 生态丰富

## 典型应用场景

### RPC 适用场景
```java
// 1. 微服务内部调用（高性能要求）
@Service
public class OrderServiceImpl {
    @Reference
    private UserService userService;      // RPC 调用
    @Reference
    private ProductService productService; // RPC 调用
    
    public Order createOrder(CreateOrderDTO dto) {
        User user = userService.getUser(dto.getUserId());
        Product product = productService.getProduct(dto.getProductId());
        // 业务逻辑
    }
}
```

### HTTP 适用场景
```java
// 1. 对外开放的 API（需要跨语言、跨平台）
@RestController
@RequestMapping("/api/v1")
public class OpenApiController {
    @PostMapping("/order")
    public Result createOrder(@RequestBody CreateOrderRequest req) {
        // 提供给第三方调用
        return Result.success(orderService.create(req));
    }
}

// 2. 前后端分离（浏览器访问）
@GetMapping("/user/profile")
public UserProfileVO getUserProfile() {
    return userService.getProfile();
}
```

## 性能与架构考量

### 1. 性能优化

**RPC 优化**：
```java
// 连接池配置
@Service(
    connections = 10,        // 每个服务提供者的最大连接数
    actives = 20,           // 每个服务的最大并发调用数
    timeout = 3000          // 调用超时时间
)
public class UserServiceImpl implements UserService {
    // ...
}
```

### 2. 混合使用

```java
// 对内用 RPC，对外用 HTTP
@Service
public class BizServiceImpl {
    // 内部服务调用，用 RPC
    @Reference
    private UserService userService;
    
    // 调用外部系统，用 HTTP
    @Autowired
    private RestTemplate restTemplate;
    
    public void process() {
        User user = userService.getUser(123L);  // RPC
        String result = restTemplate.getForObject(
            "http://third-party-api.com/api", String.class);  // HTTP
    }
}
```

## 答题总结

**RPC 和 HTTP 的本质区别**：

1. **定位不同**：
   - RPC 是远程调用框架，强调"像本地调用一样"
   - HTTP 是传输协议，定义请求/响应标准

2. **实现差异**：
   - RPC：自定义协议 + 二进制序列化 + 长连接
   - HTTP：标准协议 + JSON/XML + 短连接（HTTP/1.1 可 Keep-Alive）

3. **性能对比**：
   - RPC 性能更高（协议开销小、序列化快）
   - HTTP 通用性更好（跨语言、易调试）

4. **应用场景**：
   - RPC：微服务内部高性能调用
   - HTTP：对外 API、前后端分离、跨语言调用

5. **典型框架**：
   - RPC：Dubbo、gRPC、Thrift
   - HTTP：Spring MVC、Spring Cloud OpenFeign

**面试技巧**：强调 RPC 不是替代 HTTP，而是**补充关系**。在微服务架构中，内部用 RPC 保证性能，对外用 HTTP 保证兼容性，是常见的架构模式。

