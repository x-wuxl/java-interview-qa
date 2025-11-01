---
layout: post
title: "什么是序列化与反序列化"
date: 2025-11-01
description: "深入理解Java序列化与反序列化的概念、作用场景及核心机制"
author: "wuxl"
categories: [Java基础]
tags: [序列化, IO, 对象持久化]
---

## 问题

什么是序列化与反序列化？

## 答案

### 核心概念

**序列化（Serialization）**：将对象的状态信息转换为可存储或可传输的字节流的过程。

**反序列化（Deserialization）**：将字节流还原为对象的过程。

### 作用场景

1. **对象持久化**：将对象保存到文件、数据库等存储介质
2. **网络传输**：通过网络发送对象数据（如RPC调用、分布式缓存）
3. **跨进程通信**：在不同JVM进程间传递对象
4. **深拷贝**：通过序列化/反序列化实现对象的深度复制

### 实现方式

#### 1. Java原生序列化

对象需实现 `java.io.Serializable` 接口：

```java
public class User implements Serializable {
    private static final long serialVersionUID = 1L;

    private String name;
    private int age;
    private transient String password; // transient修饰的字段不会被序列化

    // getter/setter
}

// 序列化
try (ObjectOutputStream oos = new ObjectOutputStream(
        new FileOutputStream("user.ser"))) {
    oos.writeObject(new User("张三", 25));
}

// 反序列化
try (ObjectInputStream ois = new ObjectInputStream(
        new FileInputStream("user.ser"))) {
    User user = (User) ois.readObject();
}
```

#### 2. JSON序列化

使用JSON库（如Jackson、Gson、Fastjson）进行序列化：

```java
// Jackson示例
ObjectMapper mapper = new ObjectMapper();
String json = mapper.writeValueAsString(user); // 序列化
User user = mapper.readValue(json, User.class); // 反序列化
```

#### 3. 其他方式

- **Protobuf**：Google的高效二进制序列化协议
- **Hessian**：Dubbo默认使用的序列化方式
- **Kryo**：高性能的Java序列化库

### 关键考量

| 维度 | Java原生 | JSON | Protobuf |
|------|---------|------|----------|
| 性能 | 较慢 | 中等 | 快 |
| 体积 | 较大 | 中等 | 小 |
| 跨语言 | 否 | 是 | 是 |
| 可读性 | 否 | 是 | 否 |

### 答题总结

序列化是对象转字节流，反序列化是字节流转对象，主要用于**持久化、网络传输和跨进程通信**。Java原生通过`Serializable`接口实现，但实际项目中更常用JSON、Protobuf等跨语言、高性能的序列化方案。
