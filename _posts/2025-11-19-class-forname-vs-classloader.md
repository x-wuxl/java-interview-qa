---
layout: post
title: "反射中 Class.forName 与 ClassLoader 有何区别？"
date: 2025-11-19
categories: [Java基础]
tags: [Java, 反射, ClassLoader, 类加载]
description: "深入解析 Java 反射机制中 Class.forName 与 ClassLoader.loadClass 的核心区别，从源码层面分析初始化行为的不同，并结合 JDBC 驱动加载等实际场景进行说明。"
---

在 Java 后端面试中，**类加载机制**是考察 Java 基础深度的必问环节。`Class.forName` 和 `ClassLoader` 都可以用来加载类，但它们在行为上有着本质的区别，尤其是在**类初始化**（Initialization）这一步。

## 1. 核心概念

简而言之，两者的主要区别在于**是否执行类的静态初始化块（static block）**：

*   **`Class.forName(String className)`**：默认会加载类，并**执行**类的静态初始化块。
*   **`ClassLoader.loadClass(String className)`**：默认只加载类文件到内存，**不执行**类的静态初始化块，只有在真正使用该类（如实例化）时才会触发初始化。

---

## 2. 原理与源码分析

### 2.1 Class.forName

`Class.forName` 是 `java.lang.Class` 的静态方法。查看 JDK 源码，最终调用的是一个 native 方法：

```java
// Class.java
public static Class<?> forName(String className) throws ClassNotFoundException {
    Class<?> caller = Reflection.getCallerClass();
    // 第二个参数 initialize = true，表示默认进行初始化
    return forName0(className, true, ClassLoader.getClassLoader(caller), caller);
}
```

关键在于 `initialize` 参数默认为 `true`。这意味着类加载后，JVM 会立即链接并初始化该类，执行 `<clinit>` 方法（包含静态变量赋值和静态代码块）。

### 2.2 ClassLoader.loadClass

`ClassLoader.loadClass` 是实例方法。其源码逻辑如下：

```java
// ClassLoader.java
public Class<?> loadClass(String name) throws ClassNotFoundException {
    return loadClass(name, false);
}

protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
    // ... 双亲委派逻辑 ...
    // findClass(name) 找到类文件并定义 Class 对象
    // resolve 参数默认为 false，表示不进行链接（Linking）
}
```

这里的 `resolve` 参数默认为 `false`，且该方法主要负责“加载”阶段。根据 JVM 规范，类的初始化被延迟到了真正使用类的时候（如 `new`、访问静态字段等）。

---

## 3. 实际应用场景

### 3.1 JDBC 驱动加载（Class.forName 的典型应用）

在 JDBC 4.0 之前，我们通常使用如下代码加载数据库驱动：

```java
Class.forName("com.mysql.cj.jdbc.Driver");
```

**为什么必须用 `Class.forName`？**
因为 JDBC 规范要求 Driver 类在加载时必须向 `DriverManager` 注册自己。查看 MySQL 驱动源码：

```java
// com.mysql.cj.jdbc.Driver
static {
    try {
        // 静态代码块中将自己注册到 DriverManager
        java.sql.DriverManager.registerDriver(new Driver());
    } catch (SQLException E) {
        throw new RuntimeException("Can't register driver!");
    }
}
```

如果使用 `ClassLoader.loadClass`，静态代码块不会执行，驱动就无法注册，导致连接数据库失败。

### 3.2 Spring 的延迟加载（ClassLoader 的应用）

Spring IoC 容器在扫描包或延迟加载 Bean 时，为了提高启动速度，可能会先用 `ClassLoader` 加载类元数据，但不立即触发类的初始化。只有当 Bean 真正被实例化（`getBean`）时，才会触发完整的初始化流程。

---

## 4. 总结与示例

我们可以通过一个简单的示例来验证：

```java
public class ClassLoadTest {
    public static void main(String[] args) throws Exception {
        String className = "com.example.Demo";

        System.out.println("--- 使用 ClassLoader.loadClass ---");
        ClassLoader loader = ClassLoadTest.class.getClassLoader();
        loader.loadClass(className); // 不会输出静态块内容

        System.out.println("\n--- 使用 Class.forName ---");
        Class.forName(className); // 会输出 "Static Block Executed!"
    }
}

class Demo {
    static {
        System.out.println("Static Block Executed!");
    }
}
```

**面试回答总结：**

> `Class.forName` 和 `ClassLoader` 的核心区别在于**类初始化**的时机。
> `Class.forName` 默认在加载类的同时会立即执行类的静态代码块（`initialize=true`），常用于需要通过静态块注册资源的场景（如 JDBC 驱动）。
> 而 `ClassLoader.loadClass` 默认只将类加载到内存，不执行静态代码块（`resolve=false`），实现了延迟加载，常用于框架层面的类扫描或懒加载优化。
