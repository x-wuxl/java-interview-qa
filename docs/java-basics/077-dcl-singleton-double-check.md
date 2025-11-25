---
layout: default
title: "在 DCL 单例写法中为什么要做两次检查？"
parent: Java基础
nav_order: 77
description: "深入解析双重检查锁定（DCL）单例模式的实现原理、为什么需要两次检查、volatile关键字的作用及线程安全保证"
author: "wuxl"
date: 2025-11-17
---
## 问题

在 DCL 单例写法中为什么要做两次检查?

## 答案

### 一、DCL 单例模式完整代码

```java
public class Singleton {
    // 必须使用 volatile 关键字
    private static volatile Singleton instance;

    private Singleton() {
        // 私有构造函数
    }

    public static Singleton getInstance() {
        // 第一次检查：避免不必要的同步
        if (instance == null) {
            synchronized (Singleton.class) {
                // 第二次检查：避免重复创建实例
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```

### 二、为什么需要第一次检查？

#### 目的：提高性能，避免不必要的同步开销

**如果没有第一次检查**：

```java
public static Singleton getInstance() {
    synchronized (Singleton.class) {  // 每次都要加锁
        if (instance == null) {
            instance = new Singleton();
        }
    }
    return instance;
}
```

**问题分析**：
- 实例创建后，每次调用 `getInstance()` 仍然需要获取锁
- `synchronized` 有性能开销（即使是轻量级锁）
- 单例对象通常会被频繁访问，性能损失明显

**第一次检查的作用**：

```java
if (instance == null) {  // 第一次检查：快速返回已创建的实例
    // 只有 instance 为 null 时才进入同步块
    synchronized (Singleton.class) {
        // ...
    }
}
```

- 实例已创建时，直接返回，无需加锁
- 大幅提升性能（避免 99.99% 的锁竞争）

### 三、为什么需要第二次检查？

#### 目的：避免多线程环境下创建多个实例

**如果没有第二次检查**：

```java
public static Singleton getInstance() {
    if (instance == null) {
        synchronized (Singleton.class) {
            // 缺少第二次检查
            instance = new Singleton();  // 可能创建多个实例
        }
    }
    return instance;
}
```

**多线程场景分析**：

```java
// 初始状态：instance = null

// 时刻1：线程 A 和线程 B 同时调用 getInstance()
线程 A: if (instance == null)  // true，准备进入同步块
线程 B: if (instance == null)  // true，准备进入同步块

// 时刻2：线程 A 先获得锁
线程 A: synchronized (Singleton.class) {
    instance = new Singleton();  // 创建实例
}  // 释放锁

// 时刻3：线程 B 获得锁
线程 B: synchronized (Singleton.class) {
    // 如果没有第二次检查，会再次创建实例！
    instance = new Singleton();  // 创建第二个实例（错误）
}
```

**第二次检查的作用**：

```java
synchronized (Singleton.class) {
    if (instance == null) {  // 第二次检查：确保只创建一次
        instance = new Singleton();
    }
}
```

- 线程 A 创建实例后释放锁
- 线程 B 获得锁后，再次检查 `instance` 已不为 null
- 避免重复创建实例

### 四、为什么必须使用 volatile？

#### volatile 的两个关键作用

**1. 禁止指令重排序**

`instance = new Singleton()` 不是原子操作，实际分为三步：

```java
// instance = new Singleton() 的字节码指令
memory = allocate();   // 1. 分配内存空间
ctorInstance(memory);  // 2. 初始化对象
instance = memory;     // 3. 将 instance 指向内存地址
```

**指令重排序问题**：

JVM 可能优化为：

```java
memory = allocate();   // 1. 分配内存空间
instance = memory;     // 3. 将 instance 指向内存地址（重排序）
ctorInstance(memory);  // 2. 初始化对象
```

**多线程场景下的问题**：

```java
// 线程 A 执行到步骤 3（对象未初始化完成）
线程 A: instance = memory;  // instance 不为 null，但对象未初始化

// 线程 B 执行第一次检查
线程 B: if (instance == null)  // false
线程 B: return instance;  // 返回未初始化完成的对象（错误）
```

**volatile 的作用**：

```java
private static volatile Singleton instance;
```

- 禁止 `instance = new Singleton()` 的指令重排序
- 保证对象完全初始化后才赋值给 `instance`

**2. 保证可见性**

```java
// 线程 A 修改 instance
instance = new Singleton();

// 线程 B 读取 instance
if (instance == null)  // 保证能立即看到线程 A 的修改
```

- `volatile` 保证一个线程修改后，其他线程立即可见
- 避免线程从本地缓存读取旧值

### 五、完整的线程安全分析

#### 场景1：单线程访问

```java
线程 A: if (instance == null)  // true
线程 A: synchronized (Singleton.class) {
    if (instance == null) {  // true
        instance = new Singleton();
    }
}
线程 A: return instance;
```

#### 场景2：实例已创建

```java
线程 A: if (instance == null)  // false，直接返回
线程 B: if (instance == null)  // false，直接返回
// 无锁竞争，性能最优
```

#### 场景3：多线程同时创建

```java
// 初始：instance = null

线程 A: if (instance == null)  // true
线程 B: if (instance == null)  // true

线程 A: synchronized (Singleton.class) {
    if (instance == null) {  // true
        instance = new Singleton();  // 创建实例
    }
}  // 释放锁

线程 B: synchronized (Singleton.class) {  // 等待锁
    if (instance == null) {  // false（第二次检查）
        // 不会执行
    }
}
线程 B: return instance;  // 返回线程 A 创建的实例
```

### 六、常见错误写法对比

#### 错误1：缺少第一次检查

```java
// ❌ 性能差：每次都要加锁
public static Singleton getInstance() {
    synchronized (Singleton.class) {
        if (instance == null) {
            instance = new Singleton();
        }
    }
    return instance;
}
```

#### 错误2：缺少第二次检查

```java
// ❌ 线程不安全：可能创建多个实例
public static Singleton getInstance() {
    if (instance == null) {
        synchronized (Singleton.class) {
            instance = new Singleton();
        }
    }
    return instance;
}
```

#### 错误3：缺少 volatile

```java
// ❌ 可能返回未初始化完成的对象
private static Singleton instance;  // 缺少 volatile

public static Singleton getInstance() {
    if (instance == null) {
        synchronized (Singleton.class) {
            if (instance == null) {
                instance = new Singleton();  // 可能指令重排序
            }
        }
    }
    return instance;
}
```

### 七、更优雅的单例实现方式

#### 推荐：静态内部类（推荐）

```java
public class Singleton {
    private Singleton() { }

    private static class Holder {
        private static final Singleton INSTANCE = new Singleton();
    }

    public static Singleton getInstance() {
        return Holder.INSTANCE;
    }
}
```

**优点**：
- 线程安全（类加载机制保证）
- 懒加载（首次调用 `getInstance()` 时才加载）
- 无需 `synchronized`，性能最优
- 代码简洁

#### 推荐：枚举（最安全）

```java
public enum Singleton {
    INSTANCE;

    public void doSomething() {
        // 业务方法
    }
}

// 使用
Singleton.INSTANCE.doSomething();
```

**优点**：
- 天然线程安全
- 防止反射攻击
- 防止序列化破坏
- 代码最简洁

### 八、面试答题要点

1. **第一次检查**：提高性能，避免实例创建后每次都加锁
2. **第二次检查**：保证线程安全，避免多个线程同时创建多个实例
3. **volatile 作用**：禁止指令重排序 + 保证可见性
4. **指令重排序问题**：能说明 `new` 操作的三个步骤及重排序风险
5. **更优方案**：静态内部类（推荐）、枚举（最安全）
6. **实际应用**：Spring 的单例 Bean 使用 ConcurrentHashMap + DCL 实现
