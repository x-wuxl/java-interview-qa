---
title: "在什么情况下会发生栈内存溢出？"
date: 2025-11-19
categories: [JVM]
tags: [JVM, 内存溢出, StackOverflowError, 故障排查]
description: "详解 Java 虚拟机中 StackOverflowError 的发生原因，包括无限递归、循环依赖等经典场景，并介绍如何通过 -Xss 参数进行调优。"
nav_order: 115
parent: JVM
---
`StackOverflowError` 是 JVM 中一种非常经典的错误，它与 `OutOfMemoryError` 不同，主要发生在**虚拟机栈**（Java Virtual Machine Stack）耗尽时。面试中除了回答“递归”外，还需要展示对 JVM 内存模型的理解。

## 1. 核心概念

在 JVM 运行时数据区中，每个线程都有一个私有的**虚拟机栈**。栈由一个个**栈帧**（Stack Frame）组成，每次方法调用都会创建一个栈帧压入栈中，方法返回时栈帧出栈。

**栈内存溢出（StackOverflowError）** 发生在：
> 当线程请求的栈深度（Stack Depth）超过了虚拟机所允许的最大深度时，JVM 就会抛出该错误。

简单来说，就是方法调用的层次太深，把栈空间塞满了。

---

## 2. 常见触发场景

### 2.1 无限递归（最常见）

这是最直接的原因。如果递归调用没有正确的终止条件（Base Case），或者终止条件无法达成，栈帧会不断堆积直到溢出。

```java
public void recursiveCall() {
    recursiveCall(); // 没有退出条件
}
```

### 2.2 对象之间循环依赖的 `toString` 调用

这是一个容易被忽视的陷阱。如果两个对象互相引用，并且它们的 `toString()` 方法都打印对方，就会形成无限递归。

```java
class A {
    B b;
    public String toString() { return "A: " + b; } // 调用 b.toString()
}
class B {
    A a;
    public String toString() { return "B: " + a; } // 调用 a.toString()，形成死循环
}
```

### 2.3 栈帧过大（局部变量过多）

虽然少见，但如果一个方法内部定义了海量的局部变量，或者方法参数列表非常长，会导致单个栈帧占用内存过大。在栈总大小固定的情况下，能容纳的栈帧数量就会变少，更容易触发溢出。

---

## 3. 调优与解决方案

### 3.1 调整栈大小（-Xss）

JVM 提供了 `-Xss` 参数来设置每个线程的栈大小。
*   **默认值**：通常是 1MB（视操作系统和 JVM 版本而定，如 Linux 64-bit 下默认为 1024KB）。
*   **调整**：如果业务确实需要较深的递归（如深度优先搜索算法），可以适当调大该值，例如 `-Xss2m`。

### 3.2 优化代码逻辑

*   **尾递归优化**：虽然 Java 编译器目前对尾递归的优化支持有限，但将递归改写为**迭代（循环）**是解决此类问题的根本方法。
*   **检查死循环**：确保所有递归都有明确的退出条件。
*   **避免循环依赖**：在 `toString`、`hashCode` 等方法中小心处理双向引用，可以使用 `@ToString.Exclude` (Lombok) 或手动排除。

---

## 4. 总结与示例

**面试回答总结：**

> `StackOverflowError` 发生在线程请求的栈深度超过 JVM 限制时。
> 最常见的原因是**无限递归**或**过深的递归调用**，例如斐波那契数列的朴素递归实现，或者对象间循环调用 `toString` 方法。
> 此外，如果单个方法内的局部变量非常多，导致栈帧过大，也可能在较浅的深度触发溢出。
> 解决思路首先是**检查代码逻辑**，将递归改为循环；其次可以通过 JVM 参数 **`-Xss`** 调大线程栈空间。

**代码示例（模拟溢出）：**

```java
public class StackErrorDemo {
    private static int stackDepth = 0;

    public static void deepMethod() {
        stackDepth++;
        deepMethod();
    }

    public static void main(String[] args) {
        try {
            deepMethod();
        } catch (StackOverflowError e) {
            System.out.println("Stack overflow at depth: " + stackDepth);
            // 输出结果通常在几千到几万之间，取决于 -Xss 配置和栈帧大小
        }
    }
}
```
