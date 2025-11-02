---
layout: post
title: "什么是单例模式，如何实现一个单例？"
date: 2025-11-02
description: "深入讲解单例模式的概念、应用场景、多种实现方式及其线程安全性对比，包括饿汉式、懒汉式、双重检查锁、静态内部类和枚举实现"
author: "wuxl"
categories: [设计模式]
tags: [单例模式, 设计模式, 线程安全, 双重检查锁, 枚举]
---

## 问题

什么是单例模式，如何实现一个单例？

## 答案

### 1. 核心概念

**单例模式（Singleton Pattern）** 是一种创建型设计模式，确保一个类在整个应用程序生命周期中只有一个实例，并提供全局访问点。

**典型应用场景**：
- 数据库连接池、线程池
- 配置管理器、日志管理器
- Spring 中的 Bean 默认是单例
- 系统全局缓存、计数器

### 2. 实现方式与原理

#### 方式1：饿汉式（线程安全）

```java
public class Singleton {
    // 类加载时即创建实例
    private static final Singleton INSTANCE = new Singleton();

    private Singleton() {}

    public static Singleton getInstance() {
        return INSTANCE;
    }
}
```

**特点**：
- ✅ 天然线程安全（类加载机制保证）
- ✅ 实现简单
- ❌ 可能造成资源浪费（类加载时就创建，即使不使用）

#### 方式2：懒汉式（线程不安全）

```java
public class Singleton {
    private static Singleton instance;

    private Singleton() {}

    public static Singleton getInstance() {
        if (instance == null) {
            instance = new Singleton();
        }
        return instance;
    }
}
```

**特点**：
- ❌ 多线程下会创建多个实例
- ✅ 延迟加载

#### 方式3：懒汉式同步方法（线程安全但低效）

```java
public class Singleton {
    private static Singleton instance;

    private Singleton() {}

    public static synchronized Singleton getInstance() {
        if (instance == null) {
            instance = new Singleton();
        }
        return instance;
    }
}
```

**特点**：
- ✅ 线程安全
- ❌ 性能差（每次调用都要同步）

#### 方式4：双重检查锁（推荐）

```java
public class Singleton {
    // volatile 防止指令重排序
    private static volatile Singleton instance;

    private Singleton() {}

    public static Singleton getInstance() {
        if (instance == null) {  // 第一次检查（无锁）
            synchronized (Singleton.class) {
                if (instance == null) {  // 第二次检查（加锁）
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```

**关键点**：
- **volatile** 必不可少：防止指令重排序导致返回未初始化完成的对象
- **双重检查**：第一次检查避免不必要的同步，第二次检查防止创建多个实例
- 兼顾性能与线程安全

#### 方式5：静态内部类（推荐）

```java
public class Singleton {
    private Singleton() {}

    // 静态内部类在使用时才加载
    private static class SingletonHolder {
        private static final Singleton INSTANCE = new Singleton();
    }

    public static Singleton getInstance() {
        return SingletonHolder.INSTANCE;
    }
}
```

**特点**：
- ✅ 延迟加载（调用 `getInstance()` 时才加载内部类）
- ✅ 线程安全（类加载机制保证）
- ✅ 性能好（无同步开销）
- **最佳实践之一**

#### 方式6：枚举（最安全，推荐）

```java
public enum Singleton {
    INSTANCE;

    public void doSomething() {
        // 业务方法
    }
}
```

**特点**：
- ✅ 天然线程安全
- ✅ 防止反序列化创建新实例
- ✅ 防止反射攻击
- **《Effective Java》推荐方式**

### 3. 线程安全与性能考量

| 实现方式 | 线程安全 | 延迟加载 | 性能 | 推荐指数 |
|---------|---------|---------|------|---------|
| 饿汉式 | ✅ | ❌ | ⭐⭐⭐ | ⭐⭐⭐ |
| 懒汉式（不同步） | ❌ | ✅ | ⭐⭐⭐ | ❌ |
| 懒汉式（同步方法） | ✅ | ✅ | ⭐ | ⭐ |
| 双重检查锁 | ✅ | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 静态内部类 | ✅ | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 枚举 | ✅ | ❌ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**注意事项**：
- **防反射攻击**：在构造方法中加入判断，枚举天然防护
- **防序列化破坏**：实现 `readResolve()` 方法或使用枚举
- **分布式环境**：JVM 级别单例无法保证分布式唯一性，需要分布式锁或注册中心

### 4. 答题总结

**简洁回答模板**：

"单例模式确保类只有一个实例并提供全局访问点。常用于线程池、配置管理等场景。

主要实现方式：
1. **饿汉式**：类加载时创建，线程安全但无延迟加载
2. **双重检查锁**：需要 volatile 防止指令重排序
3. **静态内部类**：利用类加载机制，兼顾延迟加载和线程安全
4. **枚举**：最安全，防反射和反序列化

推荐使用**静态内部类**或**枚举**实现，前者写法优雅且高效，后者最安全。"
