---
layout: post
title: "Dubbo支持哪些序列化方式？"
date: 2025-11-02
categories: [中间件, Dubbo]
tags: [Dubbo, 序列化, Hessian, Protobuf, 性能优化]
description: "详细对比Dubbo支持的多种序列化方式及其性能、兼容性和适用场景"
---

## 核心概念

**序列化**是将对象转换为字节流的过程，**反序列化**是将字节流还原为对象。在 RPC 调用中，序列化的性能直接影响整体调用效率。

Dubbo 支持**多种序列化方式**，可以根据**性能、兼容性、跨语言**等需求灵活选择。

**核心指标**：
- **性能**：序列化/反序列化速度
- **体积**：序列化后的数据大小
- **兼容性**：跨版本、跨语言支持
- **易用性**：是否需要额外配置

## 支持的序列化方式

### 1. hessian2（默认，推荐）

**特点**：
- Dubbo 的**默认序列化方式**
- 二进制格式，性能好，体积小
- 跨语言支持（Java、C++、Python、PHP）
- **不需要额外依赖**

**配置方式**：
```java
// 注解配置
@Service(serialization = "hessian2")
public class UserServiceImpl implements UserService {
    // ...
}

// YAML 配置
dubbo:
  protocol:
    name: dubbo
    serialization: hessian2
```

**性能数据**：
```
序列化速度：⭐⭐⭐⭐
反序列化速度：⭐⭐⭐⭐
数据体积：⭐⭐⭐⭐
跨语言：⭐⭐⭐⭐
```

**适用场景**：
- ✅ 默认选择，兼顾性能和兼容性
- ✅ 常规业务场景
- ✅ 不需要极致性能优化的场景
- ❌ 复杂对象图（循环引用）可能有问题

**示例**：
```java
// 实体类（无需特殊注解）
public class User implements Serializable {
    private Long id;
    private String name;
    private Integer age;
    // getter/setter
}

@Service(serialization = "hessian2")
public class UserServiceImpl implements UserService {
    @Override
    public User getUser(Long userId) {
        return userMapper.selectById(userId);
    }
}
```

### 2. kryo（高性能，推荐优化场景）

**特点**：
- **性能最优**，速度最快
- 数据体积最小
- 需要提前**注册类**（否则性能下降）
- 不支持跨语言

**配置方式**：
```xml
<!-- 添加依赖 -->
<dependency>
    <groupId>org.apache.dubbo</groupId>
    <artifactId>dubbo-serialization-kryo</artifactId>
</dependency>
```

```java
// 注解配置
@Service(serialization = "kryo")
public class UserServiceImpl implements UserService {
    // ...
}

// 注册类（可选，但推荐）
public class KryoConfig {
    static {
        // 预先注册类，提升性能
        SerializationOptimizer optimizer = new SerializationOptimizer() {
            @Override
            public Collection<Class> getSerializableClasses() {
                return Arrays.asList(
                    User.class,
                    Order.class,
                    Product.class
                );
            }
        };
        // 设置优化器
        System.setProperty(
            "dubbo.application.serialization-optimizer",
            "com.example.KryoConfig"
        );
    }
}
```

**性能数据**：
```
序列化速度：⭐⭐⭐⭐⭐
反序列化速度：⭐⭐⭐⭐⭐
数据体积：⭐⭐⭐⭐⭐
跨语言：❌
```

**适用场景**：
- ✅ 对性能要求极高的场景
- ✅ 内部微服务调用（Java to Java）
- ✅ 对象结构固定，可以预先注册
- ❌ 跨语言调用
- ❌ 频繁变更实体类的场景

**性能对比**：
```java
// 基准测试（相同对象）
Hessian2：序列化 100ms，体积 1000 字节
Kryo：    序列化  50ms，体积  600 字节
提升：    速度快 2 倍，体积减少 40%
```

### 3. protobuf（跨语言，高性能）

**特点**：
- Google 开源的序列化框架
- 性能优秀，接近 Kryo
- **跨语言支持最好**（Java、Go、Python、C++等）
- 需要定义 `.proto` 文件
- **强类型**，向后兼容性好

**配置方式**：
```xml
<!-- 添加依赖 -->
<dependency>
    <groupId>org.apache.dubbo</groupId>
    <artifactId>dubbo-serialization-protobuf</artifactId>
</dependency>
<dependency>
    <groupId>com.google.protobuf</groupId>
    <artifactId>protobuf-java</artifactId>
</dependency>
```

**定义 Proto 文件**：
```protobuf
// user.proto
syntax = "proto3";

package com.example;

message UserProto {
    int64 id = 1;
    string name = 2;
    int32 age = 3;
    string email = 4;
}

message GetUserRequest {
    int64 user_id = 1;
}

message GetUserResponse {
    UserProto user = 1;
}
```

**生成 Java 类**：
```bash
protoc --java_out=./src/main/java user.proto
```

**使用示例**：
```java
@Service(serialization = "protobuf")
public class UserServiceImpl implements UserService {
    
    @Override
    public UserProto getUser(Long userId) {
        User user = userMapper.selectById(userId);
        // 转换为 Protobuf 对象
        return UserProto.newBuilder()
            .setId(user.getId())
            .setName(user.getName())
            .setAge(user.getAge())
            .setEmail(user.getEmail())
            .build();
    }
}
```

**性能数据**：
```
序列化速度：⭐⭐⭐⭐⭐
反序列化速度：⭐⭐⭐⭐⭐
数据体积：⭐⭐⭐⭐⭐
跨语言：⭐⭐⭐⭐⭐
```

**适用场景**：
- ✅ 跨语言调用（Java、Go、Python 互调）
- ✅ 对性能和体积要求高
- ✅ 长期维护的项目（向后兼容性好）
- ✅ 配合 triple 协议使用（兼容 gRPC）
- ❌ 开发成本较高（需要维护 .proto 文件）

### 4. fastjson / jackson（JSON 系列）

**特点**：
- 文本格式，**可读性好**
- 易于调试
- 跨语言支持好
- **性能较差，体积大**

**配置方式**：
```xml
<!-- FastJson -->
<dependency>
    <groupId>org.apache.dubbo</groupId>
    <artifactId>dubbo-serialization-fastjson</artifactId>
</dependency>

<!-- Jackson -->
<dependency>
    <groupId>org.apache.dubbo</groupId>
    <artifactId>dubbo-serialization-jackson</artifactId>
</dependency>
```

```java
@Service(serialization = "fastjson")
public class UserServiceImpl implements UserService {
    // ...
}
```

**性能数据**：
```
序列化速度：⭐⭐⭐
反序列化速度：⭐⭐
数据体积：⭐⭐（文本格式，体积大）
跨语言：⭐⭐⭐⭐
```

**适用场景**：
- ✅ 开发调试阶段（可以直接查看传输内容）
- ✅ 对性能要求不高的场景
- ✅ 需要与前端直接交互
- ❌ 内部高性能调用（推荐二进制格式）

**示例**：
```json
// JSON 序列化后的数据（可读性好，但体积大）
{
    "id": 123456789,
    "name": "张三",
    "age": 25,
    "email": "zhangsan@example.com"
}
```

### 5. fst（快速序列化）

**特点**：
- Fast Serialization，Java 对象序列化
- 性能接近 Kryo
- 兼容 JDK 序列化

**配置方式**：
```xml
<dependency>
    <groupId>org.apache.dubbo</groupId>
    <artifactId>dubbo-serialization-fst</artifactId>
</dependency>
```

```java
@Service(serialization = "fst")
public class UserServiceImpl implements UserService {
    // ...
}
```

**适用场景**：
- ✅ Java 内部调用
- ✅ 替代 JDK 序列化
- ❌ 跨语言场景

### 6. jdk（Java 原生序列化）

**特点**：
- Java 原生支持
- **性能最差**
- 数据体积最大
- 不推荐使用

**配置方式**：
```java
@Service(serialization = "jdk")
public class UserServiceImpl implements UserService {
    // ...
}
```

**性能数据**：
```
序列化速度：⭐
反序列化速度：⭐
数据体积：⭐
跨语言：❌
```

**适用场景**：
- ❌ 不推荐使用（已过时）
- ✅ 与遗留系统兼容

## 序列化方式对比

### 性能对比表

| 序列化方式 | 序列化速度 | 反序列化速度 | 体积 | 跨语言 | 推荐度 |
|-----------|----------|------------|------|--------|--------|
| **kryo** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ | ⭐⭐⭐⭐⭐ |
| **protobuf** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **hessian2** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **fst** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ | ⭐⭐⭐ |
| **fastjson** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **jackson** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **jdk** | ⭐ | ⭐ | ⭐ | ❌ | ❌ |

### 实际测试数据（同一对象）

```java
// 测试对象：User (id, name, age, email, createTime)

序列化时间（10000次）：
- Kryo:      50ms
- Protobuf:  60ms
- Hessian2:  100ms
- FastJson:  200ms
- JDK:       500ms

序列化后体积：
- Kryo:      45 字节
- Protobuf:  50 字节
- Hessian2:  80 字节
- FastJson:  120 字节
- JDK:       200 字节
```

## 选择建议

### 场景 1：常规业务（默认选择）

```java
// 推荐：hessian2（默认）
@Service(serialization = "hessian2")
public class UserServiceImpl implements UserService {
    // 性能好，兼容性好，无需额外配置
}
```

### 场景 2：高性能要求（Java 内部调用）

```java
// 推荐：kryo
@Service(serialization = "kryo")
public class OrderServiceImpl implements OrderService {
    // 性能最优，适合内部调用
}

// 注册类以提升性能
public class KryoOptimizer implements SerializationOptimizer {
    @Override
    public Collection<Class> getSerializableClasses() {
        return Arrays.asList(
            Order.class, OrderItem.class, User.class
        );
    }
}
```

### 场景 3：跨语言调用

```java
// 推荐：protobuf + triple 协议
@Service(
    protocol = "triple",
    serialization = "protobuf"
)
public class UserServiceImpl implements UserService {
    // 支持 Java、Go、Python 等多语言调用
}
```

### 场景 4：开发调试

```java
// 推荐：fastjson / jackson
@Service(serialization = "fastjson")
public class DebugServiceImpl implements DebugService {
    // JSON 格式，方便查看传输内容
}
```

### 场景 5：混合使用

```yaml
# 不同服务使用不同序列化方式
dubbo:
  protocol:
    name: dubbo
    serialization: hessian2  # 默认序列化
```

```java
// 服务级别覆盖
@Service(serialization = "kryo")  // 高性能服务
public class OrderServiceImpl { }

@Service(serialization = "protobuf")  // 跨语言服务
public class OpenApiServiceImpl { }

@Service(serialization = "hessian2")  // 常规服务
public class UserServiceImpl { }
```

## 最佳实践

### 1. 性能优化

```java
// 1. 使用 Kryo 并注册类
@Bean
public SerializationOptimizer kryoOptimizer() {
    return () -> Arrays.asList(
        User.class, Order.class, Product.class
    );
}

// 2. 避免大对象传输
// 不推荐：传输整个列表
List<Order> getOrders(Long userId);

// 推荐：分页传输
PageResult<Order> getOrders(Long userId, int page, int size);

// 3. 使用 DTO 减少传输字段
// 不推荐：传输 Entity（字段多）
User getUser(Long userId);

// 推荐：传输 DTO（只包含必要字段）
UserDTO getUser(Long userId);
```

### 2. 兼容性考虑

```java
// Protobuf 的向后兼容性
message UserProto {
    int64 id = 1;
    string name = 2;
    int32 age = 3;
    
    // 新增字段，不影响旧版本
    string email = 4;  // 新版本添加
}

// 旧版本的客户端仍然可以正常工作
// 新字段会被忽略
```

### 3. 序列化异常处理

```java
@Service
public class UserServiceImpl implements UserService {
    
    @Override
    public User getUser(Long userId) {
        User user = userMapper.selectById(userId);
        
        // 确保返回的对象可以被序列化
        if (user != null) {
            // 清理不能序列化的字段
            user.setTransientField(null);
        }
        
        return user;
    }
}
```

## 答题总结

**Dubbo 支持的序列化方式及选择建议**：

**1. 主要序列化方式（按推荐度）**：
- **hessian2**：默认，性能与兼容性平衡 ⭐⭐⭐⭐
- **kryo**：性能最优，Java 内部调用 ⭐⭐⭐⭐⭐
- **protobuf**：跨语言最优，高性能 ⭐⭐⭐⭐⭐
- **fastjson/jackson**：可读性好，调试友好 ⭐⭐⭐
- **fst**：性能好，Java 内部使用 ⭐⭐⭐
- **jdk**：不推荐，性能差 ❌

**2. 选择建议**：
- **常规场景** → hessian2（默认）
- **高性能** → kryo
- **跨语言** → protobuf + triple
- **调试** → fastjson

**3. 性能对比**（速度和体积）：
```
kryo > protobuf > hessian2 > fst > fastjson > jackson > jdk
```

**4. 配置方式**：
```java
@Service(serialization = "kryo")  // 服务级别

dubbo:
  protocol:
    serialization: hessian2  // 全局配置
```

**面试技巧**：强调 **hessian2 是默认选择**，**kryo 适合性能优化**，**protobuf 适合跨语言**。可以结合实际测试数据（速度、体积）说明差异，体现对性能优化的理解。

