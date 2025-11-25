---
title: "类的生命周期是怎么样的？"
date: 2025-11-01
description: "深入理解Java类的完整生命周期，从加载到卸载的全过程及各阶段的顺序关系"
author: "wuxl"
categories: [JVM]
tags: [类加载, JVM, 类生命周期, 面试]
nav_order: 150
parent: JVM
---
## 问题

类的生命周期是怎么样的？

## 答案

### 核心概念

Java类的生命周期是指一个类从被加载到JVM内存开始，到被卸载出内存为止的整个过程。完整的生命周期包括**7个阶段**，其中前5个阶段是类加载过程。

### 类的生命周期完整流程

```
加载(Loading) → 验证(Verification) → 准备(Preparation)
    → 解析(Resolution) → 初始化(Initialization)
    → 使用(Using) → 卸载(Unloading)
```

#### 各阶段详解

#### 1. **加载（Loading）**
- **定义**：将类的字节码数据读入JVM内存
- **完成任务**：
  - 获取类的二进制字节流
  - 转换为方法区的运行时数据结构
  - 在堆中生成Class对象
- **时机**：类的首次主动使用

#### 2. **验证（Verification）**
- **定义**：确保Class文件的字节流符合JVM规范
- **子阶段**：
  - 文件格式验证（魔数、版本号）
  - 元数据验证（类继承关系）
  - 字节码验证（数据流和控制流分析）
  - 符号引用验证（可访问性检查）

#### 3. **准备（Preparation）**
- **定义**：为类变量（static变量）分配内存并设置零值
- **关键点**：
  - `public static int value = 123;` → 准备阶段value=0
  - `public static final int VALUE = 123;` → 准备阶段直接=123

#### 4. **解析（Resolution）**
- **定义**：将常量池的符号引用替换为直接引用
- **内容**：类/接口、字段、方法的解析
- **时机**：可在初始化之前或之后进行（JVM实现决定）

#### 5. **初始化（Initialization）**
- **定义**：执行类构造器`<clinit>()`方法
- **完成任务**：
  - 执行静态代码块
  - 为类变量赋予代码中的实际值
- **特点**：
  - 父类先于子类初始化
  - JVM保证线程安全
  - 只执行一次

#### 6. **使用（Using）**
- **定义**：类被程序正常使用的阶段
- **操作**：
  - 创建实例对象
  - 访问类的静态成员
  - 调用方法
  - 通过反射操作

#### 7. **卸载（Unloading）**
- **定义**：类的Class对象被GC回收，类从JVM中移除
- **条件**（需同时满足3个）：
  1. 该类的所有实例都已被GC回收
  2. 加载该类的ClassLoader已被GC回收
  3. 该类的Class对象没有在任何地方被引用

### 阶段顺序关系

```
严格顺序：加载 → 验证 → 准备 → 初始化
弹性顺序：解析可以在初始化之后（支持动态绑定）
```

**特殊情况**：
- **验证**阶段的符号引用验证可以在**解析**阶段进行
- **解析**阶段可以推迟到**初始化**之后（动态解析）

### 实战示例

```java
public class ClassLifecycleDemo {

    // 准备阶段：staticValue = 0
    // 初始化阶段：staticValue = 100 → staticValue = 200
    static {
        System.out.println("1. 初始化阶段：执行静态代码块");
        staticValue = 100;
    }

    public static int staticValue = 200;

    static {
        System.out.println("2. 初始化阶段：静态代码块执行完成，staticValue=" + staticValue);
    }

    // 使用阶段
    public ClassLifecycleDemo() {
        System.out.println("3. 使用阶段：构造对象");
    }

    public static void main(String[] args) {
        System.out.println("开始加载类...");
        // 触发类初始化
        new ClassLifecycleDemo();
        System.out.println("最终值：" + staticValue);
    }
}
```

**输出**：
```
开始加载类...
1. 初始化阶段：执行静态代码块
2. 初始化阶段：静态代码块执行完成，staticValue=200
3. 使用阶段：构造对象
最终值：200
```

### 类卸载场景

```java
public class ClassUnloadingDemo {
    public static void main(String[] args) throws Exception {
        // 自定义类加载器
        URLClassLoader loader = new URLClassLoader(
            new URL[]{new URL("file:///path/to/classes/")});

        // 加载类
        Class<?> clazz = loader.loadClass("com.example.MyClass");
        Object instance = clazz.newInstance();

        System.out.println("类已加载并实例化");

        // 清除引用
        instance = null;
        clazz = null;

        // 关闭类加载器
        loader.close();
        loader = null;

        // 触发GC
        System.gc();

        System.out.println("类可能已被卸载");
    }
}
```

**常见不能卸载的情况**：
- **启动类加载器**加载的类（如`java.lang.String`）永远不会被卸载
- **应用类加载器**加载的应用主类通常不会被卸载
- **自定义类加载器**加载的类才可能被卸载（如热部署场景）

### 类卸载的实际应用

**1. Web容器的热部署**
```java
// Tomcat每个Web应用使用独立的WebappClassLoader
// 卸载时：
// 1. 停止应用
// 2. 清除所有Servlet、Filter实例
// 3. 清除ClassLoader引用
// 4. 触发GC卸载旧类
// 5. 创建新ClassLoader加载新版本类
```

**2. OSGi模块化框架**
```java
// 支持模块的动态加载和卸载
// 每个Bundle使用独立的ClassLoader
// 可实现类的热替换
```

### 内存位置的演变

不同JDK版本类信息存储位置：

| JDK版本 | 类元数据位置 | 类静态变量位置 | 常量池位置 |
|---------|-------------|---------------|-----------|
| JDK 7及之前 | 永久代(PermGen) | 永久代 | 永久代 |
| JDK 8及之后 | 元空间(Metaspace) | 堆 | 堆 |

### 面试要点总结

1. **完整7阶段**：加载→验证→准备→解析→初始化→使用→卸载
2. **准备阶段零值赋值** vs **初始化阶段实际值赋值**（高频考点）
3. **类卸载的3个条件**需同时满足（特别是ClassLoader被回收）
4. **由启动类加载器加载的类不会被卸载**（如核心类库）
5. **热部署原理**：通过自定义ClassLoader实现类的卸载和重新加载
6. **解析阶段的弹性时机**：支持Java的动态绑定特性
