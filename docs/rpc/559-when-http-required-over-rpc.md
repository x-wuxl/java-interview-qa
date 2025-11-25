---
layout: default
title: "什么场景只能用HTTP，不能用RPC？"
parent: RPC
nav_order: 559
description: "明确HTTP和RPC的适用边界，理解在跨语言、开放API、浏览器访问等场景下HTTP的不可替代性"
date: 2025-11-02
---
## 核心概念

虽然 RPC 性能更高，但在**通用性**、**兼容性**、**可访问性**要求高的场景下，必须使用 HTTP。这些场景的共同特点是：需要**跨语言**、**跨平台**或**标准化的通信协议**。

**核心判断标准**：
- 如果服务的调用方**不可控**（第三方、浏览器、跨语言）→ 用 HTTP
- 如果服务需要**广泛兼容**（标准化、易调试、生态丰富）→ 用 HTTP
- 如果服务是**内部微服务**间高频调用 → 用 RPC

## 必须使用 HTTP 的场景

### 1. 对外开放的 API（Open API）

**场景特点**：
- 调用方是第三方（合作伙伴、客户）
- 无法要求对方使用特定的 RPC 框架
- 需要标准化的协议和文档

```java
/**
 * 对外开放的订单 API
 * 调用方：电商平台、ERP 系统、第三方物流等
 */
@RestController
@RequestMapping("/open-api/v1/order")
public class OpenOrderApiController {
    
    @PostMapping("/create")
    @ApiOperation("创建订单")
    public ApiResponse<OrderDTO> createOrder(
            @RequestHeader("X-Api-Key") String apiKey,
            @RequestBody CreateOrderRequest request) {
        // 验证 API Key
        validateApiKey(apiKey);
        // 创建订单
        Order order = orderService.create(request);
        return ApiResponse.success(OrderDTO.from(order));
    }
    
    @GetMapping("/{orderId}")
    @ApiOperation("查询订单")
    public ApiResponse<OrderDTO> getOrder(
            @PathVariable String orderId,
            @RequestHeader("X-Api-Key") String apiKey) {
        validateApiKey(apiKey);
        Order order = orderService.getById(orderId);
        return ApiResponse.success(OrderDTO.from(order));
    }
}

// HTTP 请求示例（通用性强，任何语言都能调用）
// curl -X POST https://api.example.com/open-api/v1/order/create \
//   -H "X-Api-Key: xxx" \
//   -H "Content-Type: application/json" \
//   -d '{"productId": 123, "quantity": 1}'
```

**为什么不能用 RPC**：
- 无法要求所有第三方集成 Dubbo SDK
- 跨语言支持有限（虽然 Dubbo 支持多语言，但生态不如 HTTP）
- 调试困难（二进制协议无法用浏览器或 Postman 测试）

### 2. 前后端分离架构

**场景特点**：
- 前端运行在浏览器（JavaScript）
- 浏览器只支持 HTTP 协议
- 需要跨域支持（CORS）

```java
/**
 * 前端页面访问的 API
 */
@RestController
@RequestMapping("/api/v1")
@CrossOrigin(origins = "*")  // 支持跨域
public class WebApiController {
    
    @GetMapping("/user/info")
    public Result<UserVO> getUserInfo() {
        Long userId = UserContext.getCurrentUserId();
        User user = userService.getById(userId);
        return Result.success(UserVO.from(user));
    }
    
    @PostMapping("/user/update")
    public Result<Void> updateUser(@RequestBody UpdateUserRequest req) {
        userService.update(req);
        return Result.success();
    }
}

// 前端调用（axios）
// axios.get('/api/v1/user/info')
//   .then(response => {
//     console.log(response.data);
//   });
```

```javascript
// 浏览器前端代码
fetch('/api/v1/user/info', {
    method: 'GET',
    headers: {
        'Authorization': 'Bearer ' + token
    }
})
.then(response => response.json())
.then(data => {
    // 处理用户信息
    console.log(data);
});
```

**为什么不能用 RPC**：
- 浏览器不支持 TCP 自定义协议
- JavaScript 无法直接调用 Dubbo 服务
- WebSocket 虽然可以，但非标准实践

### 3. 跨语言系统集成

**场景特点**：
- 调用方使用非 Java 语言（Python、Go、Node.js）
- 对方系统已有 HTTP 客户端
- 需要快速集成，不想引入额外依赖

```java
/**
 * 提供给 Python 数据分析系统的接口
 */
@RestController
@RequestMapping("/api/data")
public class DataApiController {
    
    @GetMapping("/user/behavior")
    public List<UserBehaviorDTO> getUserBehavior(
            @RequestParam Long userId,
            @RequestParam String startDate,
            @RequestParam String endDate) {
        return behaviorService.query(userId, startDate, endDate);
    }
}

// Python 调用（无需安装 Dubbo SDK）
// import requests
// response = requests.get('http://api.example.com/api/data/user/behavior', 
//                         params={'userId': 123, 'startDate': '2025-01-01', 'endDate': '2025-01-31'})
// data = response.json()
```

**Go 语言调用示例**：
```go
// Go 服务调用 Java 的 HTTP API
package main

import (
    "encoding/json"
    "net/http"
)

func getUserBehavior(userId int64) ([]UserBehavior, error) {
    url := fmt.Sprintf("http://api.example.com/api/data/user/behavior?userId=%d", userId)
    resp, err := http.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var behaviors []UserBehavior
    json.NewDecoder(resp.Body).Decode(&behaviors)
    return behaviors, nil
}
```

**为什么不能用 RPC**：
- Dubbo 主要支持 Java，其他语言生态不成熟
- gRPC 跨语言支持好，但需要 Protobuf 定义和代码生成
- HTTP + JSON 最通用，零额外成本

### 4. Webhook 回调通知

**场景特点**：
- 需要通知第三方系统（支付回调、物流推送）
- 对方提供的是 HTTP 回调地址
- 标准化的通知格式

```java
/**
 * 支付成功后，回调第三方系统
 */
@Service
public class PaymentCallbackService {
    
    @Autowired
    private RestTemplate restTemplate;
    
    public void notifyMerchant(Payment payment, String callbackUrl) {
        // 构造回调数据
        PaymentNotifyDTO notify = PaymentNotifyDTO.builder()
            .orderId(payment.getOrderId())
            .amount(payment.getAmount())
            .status("SUCCESS")
            .timestamp(System.currentTimeMillis())
            .sign(generateSign(payment))  // 签名防篡改
            .build();
        
        try {
            // HTTP POST 回调
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<PaymentNotifyDTO> request = new HttpEntity<>(notify, headers);
            
            ResponseEntity<String> response = restTemplate.postForEntity(
                callbackUrl, request, String.class);
            
            if (response.getStatusCode() == HttpStatus.OK) {
                log.info("回调成功: {}", callbackUrl);
            }
        } catch (Exception e) {
            log.error("回调失败: {}", callbackUrl, e);
            // 重试机制
        }
    }
}
```

**为什么不能用 RPC**：
- 第三方提供的是 HTTP URL，无法改成 RPC 地址
- Webhook 是标准化的 HTTP 回调机制
- 需要穿透公网，RPC 长连接不适合

### 5. 移动端 App 调用

**场景特点**：
- iOS/Android 原生应用
- 网络环境复杂（弱网、4G/5G/WiFi 切换）
- 需要 RESTful 风格的标准接口

```java
/**
 * 移动端 API
 */
@RestController
@RequestMapping("/mobile/v1")
public class MobileApiController {
    
    @GetMapping("/products")
    @ApiOperation("商品列表")
    public Result<PageResult<ProductVO>> getProducts(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String keyword) {
        PageResult<ProductVO> result = productService.search(keyword, page, pageSize);
        return Result.success(result);
    }
    
    @PostMapping("/order/submit")
    @ApiOperation("提交订单")
    public Result<OrderVO> submitOrder(@RequestBody SubmitOrderRequest req) {
        Order order = orderService.submit(req);
        return Result.success(OrderVO.from(order));
    }
}

// iOS 调用示例（Swift）
// let url = URL(string: "https://api.example.com/mobile/v1/products")!
// URLSession.shared.dataTask(with: url) { data, response, error in
//     if let data = data {
//         let products = try? JSONDecoder().decode([Product].self, from: data)
//     }
// }.resume()
```

**为什么不能用 RPC**：
- 移动端网络不稳定，长连接容易断开
- iOS/Android SDK 主要支持 HTTP
- 需要标准的 RESTful 规范

### 6. 服务网格（Service Mesh）边缘场景

**场景特点**：
- 微服务网关（如 Spring Cloud Gateway）
- Ingress 流量入口
- 需要 HTTP 作为南北向流量标准

```java
/**
 * 网关统一入口
 */
@Configuration
public class GatewayRoutesConfig {
    
    @Bean
    public RouteLocator customRouteLocator(RouteLocatorBuilder builder) {
        return builder.routes()
            // 用户服务路由（HTTP）
            .route("user-service", r -> r.path("/api/user/**")
                .filters(f -> f.stripPrefix(1))
                .uri("http://user-service"))
            // 订单服务路由（HTTP）
            .route("order-service", r -> r.path("/api/order/**")
                .filters(f -> f.stripPrefix(1))
                .uri("http://order-service"))
            .build();
    }
}

// 外部请求 → 网关（HTTP） → 后端服务
// 网关需要 HTTP 协议进行统一路由
```

**为什么不能用 RPC**：
- Nginx、Kong 等网关只支持 HTTP 协议
- Istio/Envoy 基于 HTTP/gRPC，不支持 Dubbo 协议
- 需要标准化的协议进行流量治理

## 混合使用模式

在实际架构中，通常**对内 RPC + 对外 HTTP**：

```java
/**
 * 同一个服务，同时暴露 RPC 和 HTTP
 */
// RPC 接口（内部调用）
@Service(protocol = "dubbo")
public class UserServiceImpl implements UserService {
    @Override
    public User getUser(Long userId) {
        return userMapper.selectById(userId);
    }
}

// HTTP 接口（对外暴露）
@RestController
@RequestMapping("/api/user")
public class UserController {
    
    @Autowired
    private UserService userService;  // 本地调用
    
    @GetMapping("/{userId}")
    public Result<UserVO> getUser(@PathVariable Long userId) {
        User user = userService.getUser(userId);
        return Result.success(UserVO.from(user));
    }
}

// 架构图：
// 外部系统/浏览器 → HTTP → UserController
//                                 ↓ (本地调用)
//                          UserServiceImpl
//                                 ↑ (RPC 调用)
//                          其他微服务
```

## 答题总结

**必须使用 HTTP 的六大场景**：

1. **对外开放 API**：第三方调用，无法统一 RPC 框架
2. **前后端分离**：浏览器只支持 HTTP
3. **跨语言集成**：HTTP 生态最成熟，零依赖
4. **Webhook 回调**：标准化的 HTTP 回调机制
5. **移动端调用**：网络不稳定，需要标准 RESTful API
6. **网关/边缘流量**：基础设施只支持 HTTP

**核心判断依据**：
- 调用方**不可控** → HTTP
- 需要**广泛兼容** → HTTP  
- **内部高频调用** → RPC

**典型架构模式**：
```
外部流量（HTTP） → 网关 → BFF层（HTTP）
                              ↓
                  核心微服务（RPC 互调）
```

**面试技巧**：强调 HTTP 和 RPC **不是对立**而是**互补**。好的架构应该根据场景选择：
- **对外用 HTTP**：保证通用性和兼容性
- **对内用 RPC**：保证性能和效率
- **Dubbo 支持多协议**：可以同时暴露 Dubbo、Rest、Triple 协议

