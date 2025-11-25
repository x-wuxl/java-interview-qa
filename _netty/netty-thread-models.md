---
title: "Netty 提供了哪些线程模型？"
date: 2025-11-20
categories: [Java, Netty]
tags: [Netty, 线程模型, Reactor, 并发]
description: "详细讲解 Netty 支持的三种 Reactor 线程模型及其适用场景。"
nav_order: 595
parent: Netty
---
## 核心概念

Netty 基于 **Reactor 模式** 提供了三种线程模型：

1. **单 Reactor 单线程模型**
2. **单 Reactor 多线程模型**
3. **主从 Reactor 多线程模型**（推荐）

---

## 1. 单 Reactor 单线程模型

```java
EventLoopGroup group = new NioEventLoopGroup(1);
ServerBootstrap b = new ServerBootstrap();
b.group(group).channel(NioServerSocketChannel.class);
```

**特点**：所有操作（Accept、Read、Write）在一个线程完成

**适用场景**：低并发、简单业务

---

## 2. 单 Reactor 多线程模型

```java
EventLoopGroup group = new NioEventLoopGroup();
ServerBootstrap b = new ServerBootstrap();
b.group(group).channel(NioServerSocketChannel.class);
```

**特点**：一个 Reactor 处理 Accept，多个 Worker 处理读写

**适用场景**：中等并发

---

## 3. 主从 Reactor 多线程模型（推荐）

```java
EventLoopGroup bossGroup = new NioEventLoopGroup(1);
EventLoopGroup workerGroup = new NioEventLoopGroup();
ServerBootstrap b = new ServerBootstrap();
b.group(bossGroup, workerGroup).channel(NioServerSocketChannel.class);
```

**特点**：
- BossGroup：负责 Accept 新连接
- WorkerGroup：负责读写事件

**优势**：职责分离，充分利用多核 CPU

---

## 面试总结

**推荐使用主从 Reactor 模型**，BossGroup 负责连接，WorkerGroup 负责读写，性能最优。
