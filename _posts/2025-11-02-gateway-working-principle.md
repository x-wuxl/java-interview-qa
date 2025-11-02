---
layout: post
title: "Gateway的工作原理是什么？"
date: 2025-11-02
categories: [Spring框架, SpringCloud, API网关]
tags: [Gateway, 网关, SpringCloud, WebFlux, 路由]
description: "深入解析Spring Cloud Gateway的工作原理、核心组件、路由机制及实战应用"
---

## 核心概念

**Spring Cloud Gateway**是SpringCloud官方推出的**新一代API网关**，基于**Spring WebFlux**（响应式编程）实现，提供路由转发、负载均衡、限流、熔断、认证等功能，性能优于Zuul。

### Gateway vs Zuul

| 对比项 | Zuul 1.x | Gateway | Zuul 2.x |
|--------|----------|---------|----------|
| 技术栈 | Servlet（阻塞）| WebFlux（非阻塞）| Netty（非阻塞）|
| 性能 | 一般 | 高 | 高 |
| 维护方 | Netflix | Spring官方 | Netflix |
| 生态集成 | 较好 | 完美 | 一般 |
| 推荐度 | 不推荐 | **推荐** | 较少使用 |

### 架构图

```
Client Request
     ↓
┌─────────────────────────────────────┐
│      Spring Cloud Gateway           │
│  ┌───────────────────────────────┐  │
│  │  Handler Mapping              │  │
│  │  (路由匹配)                    │  │
│  └─────────────┬─────────────────┘  │
│                ↓                     │
│  ┌───────────────────────────────┐  │
│  │  Gateway Handler              │  │
│  │  (执行过滤器链)                │  │
│  └─────────────┬─────────────────┘  │
│                ↓                     │
│  ┌───────────────────────────────┐  │
│  │  Pre Filters                  │  │
│  │  (前置过滤器)                  │  │
│  └─────────────┬─────────────────┘  │
│                ↓                     │
│  ┌───────────────────────────────┐  │
│  │  Routing Filter               │  │
│  │  (路由到目标服务)              │  │
│  └─────────────┬─────────────────┘  │
│                ↓                     │
│  ┌───────────────────────────────┐  │
│  │  Post Filters                 │  │
│  │  (后置过滤器)                  │  │
│  └─────────────┬─────────────────┘  │
└─────────────────┼───────────────────┘
                  ↓
            Target Service
```

## 核心组件

### 1. Route（路由）

路由是Gateway的基本构建块，包含：
- **ID**：路由唯一标识
- **目标URI**：请求转发的目标地址
- **Predicates**：路由匹配条件
- **Filters**：过滤器链

```java
@Bean
public RouteLocator customRouteLocator(RouteLocatorBuilder builder) {
    return builder.routes()
        .route("user_route", r -> r
            .path("/api/users/**")  // Predicate: 路径匹配
            .filters(f -> f
                .stripPrefix(1)  // Filter: 去掉路径前缀
                .addRequestHeader("X-Request-Source", "Gateway"))
            .uri("lb://user-service"))  // 目标URI（负载均衡）
        .build();
}
```

### 2. Predicate（断言/谓词）

判断请求是否匹配路由的条件，类似于if判断。

#### 内置Predicate工厂

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: user_route
          uri: lb://user-service
          predicates:
            # 路径匹配
            - Path=/api/users/**
            
            # 请求方法匹配
            - Method=GET,POST
            
            # 请求头匹配
            - Header=X-Request-Id, \d+  # 正则表达式
            
            # 查询参数匹配
            - Query=token
            - Query=userId, \d+  # 带值匹配
            
            # Cookie匹配
            - Cookie=session, abc.*
            
            # 主机匹配
            - Host=**.example.com
            
            # IP地址匹配
            - RemoteAddr=192.168.1.1/24
            
            # 时间匹配
            - After=2025-01-01T00:00:00+08:00[Asia/Shanghai]
            - Before=2025-12-31T23:59:59+08:00[Asia/Shanghai]
            - Between=2025-01-01T00:00:00+08:00,2025-12-31T23:59:59+08:00
            
            # 权重匹配（用于金丝雀发布）
            - Weight=group1, 8  # 80%流量
```

#### 自定义Predicate

```java
@Component
public class CustomRoutePredicateFactory 
    extends AbstractRoutePredicateFactory<CustomRoutePredicateFactory.Config> {
    
    public CustomRoutePredicateFactory() {
        super(Config.class);
    }
    
    @Override
    public Predicate<ServerWebExchange> apply(Config config) {
        return exchange -> {
            // 自定义匹配逻辑
            String userType = exchange.getRequest()
                .getHeaders()
                .getFirst("User-Type");
            
            return config.getUserType().equals(userType);
        };
    }
    
    public static class Config {
        private String userType;
        
        public String getUserType() {
            return userType;
        }
        
        public void setUserType(String userType) {
            this.userType = userType;
        }
    }
}
```

使用：
```yaml
predicates:
  - Custom=vip  # 自定义断言
```

### 3. Filter（过滤器）

对请求和响应进行处理，类似于Servlet Filter。

#### 内置Filter工厂

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: user_route
          uri: lb://user-service
          filters:
            # 去掉路径前缀（/api/users/1 → /users/1）
            - StripPrefix=1
            
            # 添加路径前缀（/users/1 → /v1/users/1）
            - PrefixPath=/v1
            
            # 添加请求头
            - AddRequestHeader=X-Request-Source, Gateway
            - AddRequestParameter=version, 1.0
            
            # 添加响应头
            - AddResponseHeader=X-Response-Time, ${timestamp}
            
            # 移除请求头
            - RemoveRequestHeader=Cookie
            - RemoveResponseHeader=Set-Cookie
            
            # 重写路径
            - RewritePath=/api/(?<segment>.*), /$\{segment}
            
            # 设置响应状态码
            - SetStatus=200
            
            # 重定向
            - RedirectTo=302, https://www.example.com
            
            # 限流
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 10  # 每秒生成令牌数
                redis-rate-limiter.burstCapacity: 20  # 令牌桶容量
                key-resolver: "#{@ipKeyResolver}"  # Key解析器
            
            # 熔断
            - name: CircuitBreaker
              args:
                name: myCircuitBreaker
                fallbackUri: forward:/fallback
            
            # 重试
            - name: Retry
              args:
                retries: 3
                statuses: BAD_GATEWAY,SERVICE_UNAVAILABLE
                methods: GET,POST
                backoff:
                  firstBackoff: 100ms
                  maxBackoff: 500ms
                  factor: 2
```

#### 全局Filter

```java
@Component
@Order(-1)  // 优先级（数字越小优先级越高）
public class GlobalAuthFilter implements GlobalFilter {
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        
        // 1. 前置处理
        String token = request.getHeaders().getFirst("Authorization");
        
        if (token == null || !validateToken(token)) {
            // 认证失败，返回401
            ServerHttpResponse response = exchange.getResponse();
            response.setStatusCode(HttpStatus.UNAUTHORIZED);
            return response.setComplete();
        }
        
        // 2. 添加用户信息到请求头
        ServerHttpRequest mutatedRequest = request.mutate()
            .header("X-User-Id", getUserIdFromToken(token))
            .build();
        
        ServerWebExchange mutatedExchange = exchange.mutate()
            .request(mutatedRequest)
            .build();
        
        // 3. 继续执行过滤器链
        return chain.filter(mutatedExchange).then(Mono.fromRunnable(() -> {
            // 4. 后置处理
            ServerHttpResponse response = exchange.getResponse();
            response.getHeaders().add("X-Gateway-Response", "success");
        }));
    }
    
    private boolean validateToken(String token) {
        // JWT验证逻辑
        return true;
    }
    
    private String getUserIdFromToken(String token) {
        // 解析Token获取用户ID
        return "123456";
    }
}
```

#### 自定义GatewayFilter

```java
@Component
public class CustomGatewayFilterFactory 
    extends AbstractGatewayFilterFactory<CustomGatewayFilterFactory.Config> {
    
    public CustomGatewayFilterFactory() {
        super(Config.class);
    }
    
    @Override
    public GatewayFilter apply(Config config) {
        return (exchange, chain) -> {
            ServerHttpRequest request = exchange.getRequest();
            
            // 前置处理
            log.info("请求路径: {}", request.getURI().getPath());
            
            // 修改请求
            ServerHttpRequest modifiedRequest = request.mutate()
                .header("X-Custom-Header", config.getValue())
                .build();
            
            // 继续执行
            return chain.filter(exchange.mutate().request(modifiedRequest).build())
                .then(Mono.fromRunnable(() -> {
                    // 后置处理
                    ServerHttpResponse response = exchange.getResponse();
                    log.info("响应状态码: {}", response.getStatusCode());
                }));
        };
    }
    
    public static class Config {
        private String value;
        
        public String getValue() {
            return value;
        }
        
        public void setValue(String value) {
            this.value = value;
        }
    }
}
```

## 核心源码解析

### 1. 路由匹配流程

```java
// RoutePredicateHandlerMapping 路由匹配入口
public class RoutePredicateHandlerMapping extends AbstractHandlerMapping {
    
    @Override
    protected Mono<?> getHandlerInternal(ServerWebExchange exchange) {
        // 1. 查找匹配的路由
        return lookupRoute(exchange)
            .flatMap(route -> {
                // 2. 将匹配的路由保存到exchange
                exchange.getAttributes().put(GATEWAY_ROUTE_ATTR, route);
                return Mono.just(webHandler);
            })
            .switchIfEmpty(Mono.empty().then(Mono.fromRunnable(() -> {
                // 3. 未找到匹配路由
                exchange.getResponse().setStatusCode(HttpStatus.NOT_FOUND);
            })));
    }
    
    protected Mono<Route> lookupRoute(ServerWebExchange exchange) {
        return this.routeLocator.getRoutes()
            // 遍历所有路由
            .concatMap(route -> Mono.just(route)
                .filterWhen(r -> {
                    // 测试Predicate是否匹配
                    exchange.getAttributes().put(GATEWAY_PREDICATE_ROUTE_ATTR, r.getId());
                    return r.getPredicate().apply(exchange);
                })
                .doOnError(e -> log.error("路由匹配错误", e))
                .onErrorResume(e -> Mono.empty()))
            // 取第一个匹配的路由
            .next();
    }
}
```

### 2. 过滤器链执行

```java
// FilteringWebHandler 过滤器链执行器
public class FilteringWebHandler implements WebHandler {
    private final List<GlobalFilter> globalFilters;
    
    @Override
    public Mono<Void> handle(ServerWebExchange exchange) {
        Route route = exchange.getRequiredAttribute(GATEWAY_ROUTE_ATTR);
        List<GatewayFilter> gatewayFilters = route.getFilters();
        
        // 1. 合并全局过滤器和路由过滤器
        List<GatewayFilter> combined = new ArrayList<>(this.globalFilters);
        combined.addAll(gatewayFilters);
        
        // 2. 排序（按Order）
        AnnotationAwareOrderComparator.sort(combined);
        
        // 3. 构建过滤器链并执行
        return new DefaultGatewayFilterChain(combined).filter(exchange);
    }
}

// DefaultGatewayFilterChain 过滤器链
private static class DefaultGatewayFilterChain implements GatewayFilterChain {
    private final int index;
    private final List<GatewayFilter> filters;
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange) {
        // 递归执行过滤器
        if (this.index < filters.size()) {
            GatewayFilter filter = filters.get(this.index);
            DefaultGatewayFilterChain chain = 
                new DefaultGatewayFilterChain(this, this.index + 1);
            return filter.filter(exchange, chain);
        } else {
            return Mono.empty();  // 过滤器执行完毕
        }
    }
}
```

### 3. 路由转发

```java
// NettyRoutingFilter 执行实际的HTTP请求
public class NettyRoutingFilter implements GlobalFilter, Ordered {
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        URI requestUrl = exchange.getRequiredAttribute(GATEWAY_REQUEST_URL_ATTR);
        
        // 1. 构建HTTP请求
        HttpMethod method = exchange.getRequest().getMethod();
        
        return this.httpClient.request(method)
            .uri(requestUrl)
            .send((req, nettyOutbound) -> {
                // 2. 发送请求体
                return nettyOutbound.send(exchange.getRequest().getBody()
                    .map(dataBuffer -> {
                        return nettyOutbound.alloc().wrap(dataBuffer.asByteBuffer());
                    }));
            })
            .responseConnection((res, connection) -> {
                // 3. 处理响应
                ServerHttpResponse response = exchange.getResponse();
                response.setStatusCode(HttpStatus.valueOf(res.status().code()));
                response.getHeaders().putAll(res.responseHeaders());
                
                // 4. 写入响应体
                return response.writeWith(connection.inbound().receive()
                    .map(byteBuf -> {
                        return response.bufferFactory().wrap(byteBuf.nioBuffer());
                    }));
            })
            .then(chain.filter(exchange));
    }
    
    @Override
    public int getOrder() {
        return Ordered.LOWEST_PRECEDENCE;  // 最后执行
    }
}
```

## 限流实现

### 基于Redis的令牌桶限流

```java
// RedisRateLimiter 核心实现
public class RedisRateLimiter implements RateLimiter<RedisRateLimiter.Config> {
    
    @Override
    public Mono<Response> isAllowed(String routeId, String id) {
        Config config = getConfig().get(routeId);
        
        // 令牌桶参数
        int replenishRate = config.getReplenishRate();  // 每秒生成令牌数
        int burstCapacity = config.getBurstCapacity();  // 桶容量
        
        // Lua脚本（保证原子性）
        List<String> keys = Arrays.asList(
            routeId + ".tokens",  // 当前令牌数
            routeId + ".timestamp"  // 上次填充时间
        );
        
        return redisTemplate.execute(script, keys, 
            replenishRate, burstCapacity, Instant.now().getEpochSecond(), 1)
            .map(results -> {
                boolean allowed = (Long) results.get(0) == 1L;
                long tokensLeft = (Long) results.get(1);
                
                return new Response(allowed, 
                    getHeaders(config, tokensLeft));
            });
    }
}
```

Lua脚本：
```lua
-- 令牌桶算法
local tokens_key = KEYS[1]
local timestamp_key = KEYS[2]

local rate = tonumber(ARGV[1])  -- 每秒生成令牌数
local capacity = tonumber(ARGV[2])  -- 桶容量
local now = tonumber(ARGV[3])  -- 当前时间
local requested = tonumber(ARGV[4])  -- 请求令牌数

-- 获取当前令牌数和上次填充时间
local tokens = tonumber(redis.call("get", tokens_key))
if tokens == nil then
  tokens = capacity
end

local last_refreshed = tonumber(redis.call("get", timestamp_key))
if last_refreshed == nil then
  last_refreshed = 0
end

-- 计算新增令牌
local delta = math.max(0, now - last_refreshed)
local filled_tokens = math.min(capacity, tokens + (delta * rate))

-- 判断是否允许请求
local allowed = filled_tokens >= requested
local new_tokens = filled_tokens
if allowed then
  new_tokens = filled_tokens - requested
end

-- 更新Redis
redis.call("setex", tokens_key, 3600, new_tokens)
redis.call("setex", timestamp_key, 3600, now)

return {allowed, new_tokens}
```

### Key解析器

```java
@Configuration
public class KeyResolverConfig {
    
    // 基于IP限流
    @Bean
    public KeyResolver ipKeyResolver() {
        return exchange -> Mono.just(
            exchange.getRequest()
                .getRemoteAddress()
                .getAddress()
                .getHostAddress()
        );
    }
    
    // 基于用户限流
    @Bean
    public KeyResolver userKeyResolver() {
        return exchange -> Mono.just(
            exchange.getRequest()
                .getHeaders()
                .getFirst("X-User-Id")
        );
    }
    
    // 基于API限流
    @Bean
    public KeyResolver apiKeyResolver() {
        return exchange -> Mono.just(
            exchange.getRequest()
                .getPath()
                .value()
        );
    }
}
```

## 统一异常处理

```java
@Component
@Order(-1)
public class GlobalExceptionHandler implements WebExceptionHandler {
    
    @Override
    public Mono<Void> handle(ServerWebExchange exchange, Throwable ex) {
        ServerHttpResponse response = exchange.getResponse();
        
        if (response.isCommitted()) {
            return Mono.error(ex);
        }
        
        // 设置响应头
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        
        // 构建错误响应
        ErrorResponse errorResponse = new ErrorResponse();
        
        if (ex instanceof ResponseStatusException) {
            ResponseStatusException rse = (ResponseStatusException) ex;
            response.setStatusCode(rse.getStatus());
            errorResponse.setCode(rse.getStatus().value());
            errorResponse.setMessage(rse.getReason());
        } else if (ex instanceof TimeoutException) {
            response.setStatusCode(HttpStatus.GATEWAY_TIMEOUT);
            errorResponse.setCode(504);
            errorResponse.setMessage("请求超时");
        } else {
            response.setStatusCode(HttpStatus.INTERNAL_SERVER_ERROR);
            errorResponse.setCode(500);
            errorResponse.setMessage("服务器内部错误");
        }
        
        // 写入响应
        return response.writeWith(Mono.fromSupplier(() -> {
            DataBufferFactory bufferFactory = response.bufferFactory();
            try {
                byte[] bytes = new ObjectMapper().writeValueAsBytes(errorResponse);
                return bufferFactory.wrap(bytes);
            } catch (Exception e) {
                return bufferFactory.wrap(new byte[0]);
            }
        }));
    }
}
```

## 跨域配置

```yaml
spring:
  cloud:
    gateway:
      globalcors:
        cors-configurations:
          '[/**]':
            allowedOriginPatterns: "*"  # 允许的源
            allowedMethods:  # 允许的方法
              - GET
              - POST
              - PUT
              - DELETE
              - OPTIONS
            allowedHeaders: "*"  # 允许的请求头
            allowCredentials: true  # 允许携带Cookie
            maxAge: 3600  # 预检请求缓存时间
```

## 最佳实践

### 1. 统一前缀配置

```yaml
spring:
  cloud:
    gateway:
      default-filters:
        - PrefixPath=/api  # 所有路由统一添加/api前缀
      routes:
        - id: user_route
          uri: lb://user-service
          predicates:
            - Path=/users/**
          # 实际请求路径: /api/users/**
```

### 2. 超时配置

```yaml
spring:
  cloud:
    gateway:
      httpclient:
        connect-timeout: 3000  # 连接超时
        response-timeout: 5s  # 响应超时
      routes:
        - id: slow_route
          uri: lb://slow-service
          predicates:
            - Path=/slow/**
          metadata:
            response-timeout: 30000  # 针对特定路由
            connect-timeout: 10000
```

### 3. 熔断配置

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: user_route
          uri: lb://user-service
          predicates:
            - Path=/api/users/**
          filters:
            - name: CircuitBreaker
              args:
                name: userServiceCircuitBreaker
                fallbackUri: forward:/fallback/users
                
resilience4j:
  circuitbreaker:
    instances:
      userServiceCircuitBreaker:
        sliding-window-size: 10  # 滑动窗口大小
        failure-rate-threshold: 50  # 失败率阈值
        wait-duration-in-open-state: 10s  # 熔断等待时间
```

## 面试总结

**Spring Cloud Gateway工作原理**：

1. **路由匹配**：`RoutePredicateHandlerMapping`根据Predicates匹配请求到具体路由
2. **过滤器链**：`FilteringWebHandler`构建并执行全局过滤器和路由过滤器链
3. **请求转发**：`NettyRoutingFilter`使用Netty客户端转发请求到目标服务
4. **响应处理**：通过过滤器链处理响应，最后返回给客户端

**核心组件**：
- **Route**：路由规则（ID + URI + Predicates + Filters）
- **Predicate**：路由匹配条件（Path、Method、Header等）
- **Filter**：请求/响应处理（全局Filter和GatewayFilter）

**技术特点**：
- 基于**WebFlux响应式编程**，性能优于Zuul
- 使用**Netty**作为底层HTTP客户端
- 天然集成**Spring生态**（Eureka、Hystrix、Ribbon）

**常见应用**：路由转发、负载均衡、限流、熔断、认证鉴权、日志记录、跨域处理

**推荐指数**：⭐⭐⭐⭐⭐（SpringCloud官方推荐的网关方案）

