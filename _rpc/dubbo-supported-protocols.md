---
title: "Dubbo支持哪些调用协议？"
date: 2025-11-02
categories: [中间件, Dubbo]
tags: [Dubbo, 协议, RPC, 网络通信]
description: "详细介绍Dubbo支持的多种通信协议及其特点、适用场景和配置方式"
nav_order: 563
parent: RPC
---
## 核心概念

Dubbo 采用**协议可插拔**设计，支持多种通信协议。每种协议在**性能、兼容性、适用场景**上各有特点，可以根据业务需求灵活选择。

**核心协议分类**：
- **RPC 协议**：dubbo、triple、rmi、hessian
- **HTTP 协议**：rest、http
- **消息队列**：redis、memcached
- **其他**：thrift、grpc、webservice

## 主要协议详解

### 1. dubbo 协议（默认，推荐）

**特点**：
- Dubbo 框架的**默认协议**，性能最优
- 基于 **TCP + NIO**，单一长连接
- 序列化：Hessian2（默认）、Kryo、Protobuf 等
- 适合小数据量、高并发的场景

**配置方式**：
```java
// 注解配置
@Service(protocol = "dubbo")
public class UserServiceImpl implements UserService {
    // ...
}

// YAML 配置
dubbo:
  protocol:
    name: dubbo
    port: 20880
    threads: 200          # 业务线程池大小
    serialization: hessian2
```

**协议格式**：
```
+---------------+---------------+---------------+
| Magic(2字节)  | Flag(1字节)   | Status(1字节) |
+---------------+---------------+---------------+
| Request ID (8字节)                            |
+---------------+---------------+---------------+
| Data Length (4字节)   | Serialized Data      |
+---------------+---------------+---------------+
```

**适用场景**：
- ✅ 微服务内部调用（常规业务场景）
- ✅ 高性能要求的场景
- ✅ 小数据量、高并发调用
- ❌ 大文件传输（单一长连接，容易阻塞）
- ❌ 跨语言调用（需要 Dubbo SDK）

**性能数据**：
```java
// 单机 QPS：约 3000-5000
// 延迟：1-3ms（局域网）
// 适合：服务数量多、单次传输数据量小
```

### 2. triple 协议（推荐，新一代）

**特点**：
- 基于 **HTTP/2** 协议
- 兼容 **gRPC**（可以互相调用）
- 支持流式调用（Stream RPC）
- 跨语言友好

**配置方式**：
```java
// 注解配置
@Service(protocol = "triple")
public class UserServiceImpl implements UserService {
    // ...
}

// YAML 配置
dubbo:
  protocol:
    name: triple
    port: 50051
```

**支持流式调用**：
```java
// 服务端流式
public interface VideoService {
    void downloadVideo(Long videoId, StreamObserver<VideoChunk> observer);
}

// 客户端流式
public interface UploadService {
    void uploadFile(StreamObserver<FileChunk> request, StreamObserver<Result> response);
}

// 双向流式
public interface ChatService {
    void chat(StreamObserver<Message> request, StreamObserver<Message> response);
}
```

**适用场景**：
- ✅ 跨语言调用（与 gRPC 互通）
- ✅ 流式传输（大文件、视频流）
- ✅ 浏览器直接调用（HTTP/2 支持）
- ✅ 云原生环境（符合标准）
- ❌ 对性能极致追求的场景（比 dubbo 协议略慢）

**对比 dubbo 协议**：
| 维度 | dubbo 协议 | triple 协议 |
|------|-----------|------------|
| **传输协议** | TCP 自定义协议 | HTTP/2 |
| **性能** | 最优 | 较好 |
| **跨语言** | 需要 Dubbo SDK | 兼容 gRPC |
| **流式支持** | 不支持 | 支持 |
| **云原生** | 一般 | 友好 |

### 3. rest 协议（对外暴露）

**特点**：
- 基于 **HTTP/REST** 风格
- 使用 JSON 序列化
- 可以被任何 HTTP 客户端调用
- 集成 Spring MVC、JAX-RS

**配置方式**：
```java
// 注解配置
@Service(protocol = "rest")
@Path("/user")  // REST 路径
public class UserServiceImpl implements UserService {
    
    @GET
    @Path("/{id}")
    @Produces(MediaType.APPLICATION_JSON)
    public User getUser(@PathParam("id") Long userId) {
        return userMapper.selectById(userId);
    }
    
    @POST
    @Path("/create")
    @Consumes(MediaType.APPLICATION_JSON)
    public Result createUser(User user) {
        userService.save(user);
        return Result.success();
    }
}

// YAML 配置
dubbo:
  protocol:
    name: rest
    port: 8080
    server: netty  # 或 tomcat、jetty
```

**适用场景**：
- ✅ 对外开放的 API（第三方调用）
- ✅ 前后端分离（浏览器访问）
- ✅ 跨语言集成（通用 HTTP 协议）
- ✅ 同时提供 RPC 和 REST 接口
- ❌ 内部高性能调用（性能较低）

**混合使用**：
```java
// 同时暴露 dubbo 和 rest 协议
@Service(protocol = {"dubbo", "rest"})
@Path("/user")
public class UserServiceImpl implements UserService {
    // 内部服务通过 dubbo 协议调用
    // 外部系统通过 HTTP REST 调用
}
```

### 4. http 协议

**特点**：
- 基于 **HTTP/1.1** 表单提交
- 序列化：表单序列化（form）
- 适合简单的 HTTP 请求

**配置方式**：
```java
dubbo:
  protocol:
    name: http
    port: 8080
```

**适用场景**：
- ✅ 简单的 HTTP 调用
- ✅ 与传统系统集成
- ❌ 现代微服务（推荐用 rest 或 triple）

### 5. rmi 协议

**特点**：
- 基于 **Java RMI**
- 使用 Java 标准序列化
- 短连接，偶尔长连接

**配置方式**：
```java
dubbo:
  protocol:
    name: rmi
    port: 1099
```

**适用场景**：
- ✅ 与遗留 RMI 系统集成
- ❌ 新项目（性能不如 dubbo 协议）

### 6. hessian 协议

**特点**：
- 基于 **Hessian** 二进制序列化
- HTTP 短连接
- 传输简单对象

**配置方式**：
```java
dubbo:
  protocol:
    name: hessian
    port: 8080
```

**适用场景**：
- ✅ 与 Hessian 服务集成
- ✅ 页面传输、文件上传
- ❌ 内部高性能调用

### 7. webservice 协议

**特点**：
- 基于 **SOAP** 协议
- 使用 XML 格式
- 跨语言、跨平台

**配置方式**：
```java
dubbo:
  protocol:
    name: webservice
    port: 8080
```

**适用场景**：
- ✅ 与传统企业系统集成（SAP、Oracle）
- ❌ 现代微服务（性能低、冗余数据多）

### 8. thrift / grpc 协议

**特点**：
- 集成第三方 RPC 框架
- Thrift：Facebook 开源
- gRPC：Google 开源

**配置方式**：
```java
// gRPC 协议（通过 triple 协议兼容）
dubbo:
  protocol:
    name: triple  # triple 兼容 gRPC
    port: 50051
```

## 协议选择建议

### 场景 1：微服务内部调用

```java
// 推荐：dubbo 协议（默认）
@Service(protocol = "dubbo")
public class OrderServiceImpl implements OrderService {
    
    @Reference
    private UserService userService;
    
    @Reference
    private ProductService productService;
}

// 配置
dubbo:
  protocol:
    name: dubbo
    port: 20880
    serialization: hessian2
    threads: 200
```

### 场景 2：对外开放 API

```java
// 推荐：rest 协议
@Service(protocol = "rest")
@Path("/api/v1/order")
public class OrderApiServiceImpl implements OrderApiService {
    
    @POST
    @Path("/create")
    public ApiResponse<OrderDTO> createOrder(CreateOrderRequest req) {
        // ...
    }
}
```

### 场景 3：跨语言调用

```java
// 推荐：triple 协议（兼容 gRPC）
@Service(protocol = "triple")
public class UserServiceImpl implements UserService {
    // Python、Go、Node.js 可以通过 gRPC 客户端调用
}
```

### 场景 4：同时支持内外部调用

```java
// 多协议暴露
@Service(protocol = {"dubbo", "rest"})
@Path("/user")
public class UserServiceImpl implements UserService {
    // dubbo 协议：供内部微服务调用
    // rest 协议：供前端、第三方调用
}

// 配置
dubbo:
  protocols:
    - name: dubbo
      port: 20880
    - name: rest
      port: 8080
```

### 场景 5：大文件传输

```java
// 推荐：triple 协议（支持流式）
@Service(protocol = "triple")
public class FileServiceImpl implements FileService {
    
    @Override
    public void downloadFile(String fileId, StreamObserver<FileChunk> observer) {
        // 流式传输大文件
        try (InputStream input = getFileStream(fileId)) {
            byte[] buffer = new byte[8192];
            int len;
            while ((len = input.read(buffer)) != -1) {
                FileChunk chunk = FileChunk.newBuilder()
                    .setData(ByteString.copyFrom(buffer, 0, len))
                    .build();
                observer.onNext(chunk);
            }
            observer.onCompleted();
        }
    }
}
```

## 协议性能对比

| 协议 | QPS | 延迟 | 数据量 | 特点 |
|------|-----|------|--------|------|
| **dubbo** | ⭐⭐⭐⭐⭐ | 1-3ms | 小 | 性能最优，单一长连接 |
| **triple** | ⭐⭐⭐⭐ | 2-5ms | 中大 | 支持流式，兼容 gRPC |
| **rest** | ⭐⭐⭐ | 5-10ms | 中 | 通用性好，易调试 |
| **http** | ⭐⭐ | 10-20ms | 小 | 简单但性能低 |
| **rmi** | ⭐⭐ | 10-15ms | 中 | Java 标准，性能一般 |
| **hessian** | ⭐⭐⭐ | 5-10ms | 中 | HTTP 短连接 |

## 配置最佳实践

```yaml
dubbo:
  application:
    name: my-service
  registry:
    address: nacos://127.0.0.1:8848
  
  # 多协议配置
  protocols:
    # 默认协议：内部调用
    - name: dubbo
      port: 20880
      serialization: hessian2
      threads: 200
      accepts: 1000
    
    # REST 协议：对外暴露
    - name: rest
      port: 8080
      server: netty
    
    # Triple 协议：跨语言调用
    - name: triple
      port: 50051
  
  # 服务级别指定协议
  provider:
    protocol: dubbo  # 默认使用 dubbo 协议
```

```java
// 服务级别覆盖
@Service(protocol = "rest")
public class OpenApiServiceImpl { }

@Service(protocol = "dubbo")
public class InternalServiceImpl { }

@Service(protocol = {"dubbo", "rest"})
public class HybridServiceImpl { }
```

## 答题总结

**Dubbo 支持的主要协议及选择建议**：

**1. 核心协议（按推荐度）**：
- **dubbo**：默认协议，性能最优，适合内部调用
- **triple**：新一代协议，兼容 gRPC，支持流式
- **rest**：HTTP REST 风格，适合对外 API
- **http/rmi/hessian**：传统协议，适合系统集成

**2. 场景选择**：
- **内部高性能** → dubbo 协议
- **跨语言调用** → triple 协议
- **对外开放 API** → rest 协议
- **大文件传输** → triple 协议（流式）
- **浏览器访问** → rest 协议

**3. 多协议支持**：
```java
@Service(protocol = {"dubbo", "rest"})
// 同时暴露多个协议，满足不同场景
```

**4. 协议对比**：
| 协议 | 性能 | 适用场景 |
|------|-----|----------|
| dubbo | ⭐⭐⭐⭐⭐ | 内部调用 |
| triple | ⭐⭐⭐⭐ | 跨语言、流式 |
| rest | ⭐⭐⭐ | 对外 API |

**面试技巧**：强调 **dubbo 协议是默认和最优选择**，triple 是**未来趋势**（兼容 gRPC、支持流式），rest 用于**对外暴露**。可以结合具体业务场景说明协议选择理由。

