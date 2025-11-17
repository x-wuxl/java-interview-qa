---
layout: post
title: "final、finally、finalize 有何区别？"
date: 2025-11-16
description: "详解 Java 中 final 关键字、finally 代码块和 finalize 方法的区别与使用场景"
author: "wuxl"
categories: [Java基础]
tags: [final, finally, finalize, 关键字, 异常处理, 垃圾回收]
---

## 问题

final、finally、finalize 有何区别？

## 答案

### 核心概念

这三个关键字虽然名称相似，但用途完全不同：

- **`final`**：关键字，用于声明**不可变**的类、方法或变量
- **`finally`**：异常处理机制的一部分，用于定义**必定执行**的代码块
- **`finalize`**：Object 类的方法，用于对象被垃圾回收前的**清理工作**（已废弃）

### 1. final 关键字

#### 作用范围

| 修饰对象 | 作用 | 示例 |
|---------|------|------|
| **类** | 该类不能被继承 | `final class String` |
| **方法** | 该方法不能被重写 | `public final void show()` |
| **变量** | 该变量只能赋值一次（常量） | `final int MAX = 100` |

#### 典型应用

```java
// 1. final 修饰类：不可继承
public final class ImmutableClass {
    // String、Integer 等包装类都是 final 类
}

// 2. final 修饰方法：不可重写
public class Parent {
    public final void show() {
        System.out.println("不可被子类重写");
    }
}

// 3. final 修饰变量
public class FinalDemo {
    // 常量：必须初始化，不可修改
    private final int MAX_SIZE = 100;

    // final 引用：引用不可变，但对象内容可变
    private final List<String> list = new ArrayList<>();

    public void test() {
        // list = new ArrayList<>();  // 编译错误：不能重新赋值
        list.add("可以修改内容");      // 正确：对象内容可变
    }
}
```

#### 性能优化

- **方法内联**：final 方法可能被 JVM 内联优化
- **线程安全**：final 字段在构造函数完成后对其他线程可见（happens-before 保证）

```java
public class SafePublication {
    private final int value;

    public SafePublication(int value) {
        this.value = value;  // final 字段保证安全发布
    }
}
```

### 2. finally 代码块

#### 核心特性

- **必定执行**：无论是否发生异常，finally 块都会执行
- **执行时机**：在 try-catch 之后，return 之前执行

#### 典型应用场景

```java
// 资源释放（传统方式）
public void readFile() {
    FileInputStream fis = null;
    try {
        fis = new FileInputStream("file.txt");
        // 读取文件操作
    } catch (IOException e) {
        e.printStackTrace();
    } finally {
        // 无论是否异常，都会执行资源释放
        if (fis != null) {
            try {
                fis.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }
}

// 现代写法：try-with-resources（推荐）
public void readFileModern() {
    try (FileInputStream fis = new FileInputStream("file.txt")) {
        // 读取文件操作
    } catch (IOException e) {
        e.printStackTrace();
    }
    // 自动调用 close()，无需 finally
}
```

#### 特殊情况

```java
public int testFinally() {
    try {
        return 1;  // 先计算返回值，但不立即返回
    } finally {
        return 2;  // finally 中的 return 会覆盖 try 中的 return
    }
    // 最终返回 2
}

public int testFinally2() {
    int x = 1;
    try {
        return x;  // 返回 x 的副本（值为 1）
    } finally {
        x = 2;     // 修改 x 不影响返回值
    }
    // 最终返回 1
}
```

#### 不执行 finally 的极端情况

```java
// 1. System.exit() 终止 JVM
try {
    System.exit(0);
} finally {
    System.out.println("不会执行");
}

// 2. 守护线程中 JVM 退出
// 3. 无限循环或死锁
// 4. 操作系统强制终止进程
```

### 3. finalize 方法

#### 基本概念

```java
@Override
protected void finalize() throws Throwable {
    try {
        // 对象被 GC 回收前的清理工作
        System.out.println("对象即将被回收");
    } finally {
        super.finalize();
    }
}
```

#### 为什么已废弃（Java 9+）

1. **不确定性**：无法预测何时执行，甚至可能不执行
2. **性能问题**：有 finalize 的对象需要两次 GC 才能回收
3. **异常处理**：finalize 中的异常会被忽略
4. **资源泄漏风险**：依赖 finalize 释放资源不可靠

#### 替代方案

```java
// 1. try-with-resources（推荐）
try (Connection conn = DriverManager.getConnection(url)) {
    // 使用连接
}  // 自动调用 close()

// 2. Cleaner API（Java 9+）
public class ResourceHolder implements AutoCloseable {
    private static final Cleaner cleaner = Cleaner.create();

    private final Cleaner.Cleanable cleanable;

    public ResourceHolder() {
        this.cleanable = cleaner.register(this, new CleanupAction());
    }

    @Override
    public void close() {
        cleanable.clean();
    }

    private static class CleanupAction implements Runnable {
        @Override
        public void run() {
            // 清理资源
        }
    }
}

// 3. 显式 close 方法
public class Resource implements AutoCloseable {
    @Override
    public void close() {
        // 释放资源
    }
}
```

### 对比总结

| 特性 | final | finally | finalize |
|------|-------|---------|----------|
| **类型** | 关键字 | 关键字 | 方法 |
| **作用** | 声明不可变 | 异常处理必执行代码 | GC 前清理（已废弃） |
| **使用场景** | 常量、不可继承类、不可重写方法 | 资源释放、清理工作 | 不推荐使用 |
| **执行时机** | 编译期/运行期 | try-catch 之后 | GC 回收前（不确定） |
| **性能影响** | 可能优化性能 | 无明显影响 | 降低 GC 性能 |

### 答题总结

**面试要点**：
- **final**：修饰类（不可继承）、方法（不可重写）、变量（不可修改），常用于常量定义和线程安全
- **finally**：异常处理的一部分，保证资源释放等清理代码必定执行，现代开发推荐 try-with-resources
- **finalize**：已废弃的 GC 回收前钩子方法，存在不确定性和性能问题，应使用 AutoCloseable 或 Cleaner 替代

**记忆技巧**：
- final = 最终的（不可变）
- finally = 最终执行（必定执行）
- finalize = 最终化（对象生命周期结束，但已过时）
