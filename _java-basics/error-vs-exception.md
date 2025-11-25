---
title: "Error 与 Exception 有何区别？CheckedException 与 RuntimeException 有何差异？"
date: 2025-11-16
description: "深入理解 Java 异常体系中 Error 与 Exception 的本质区别，以及 CheckedException 与 RuntimeException 的使用场景和处理方式"
author: "wuxl"
categories: [Java基础]
tags: [异常处理, Error, Exception, CheckedException, RuntimeException]
nav_order: 52
parent: Java基础
---
## 问题

Error 与 Exception 有何区别？CheckedException 与 RuntimeException 有何差异？

## 答案

### 一、Error 与 Exception 的区别

**核心概念：**

`Error` 和 `Exception` 都继承自 `Throwable`，但它们的设计目的和处理方式完全不同：

| 维度 | Error | Exception |
|------|-------|-----------|
| **定义** | 系统级严重错误 | 程序级可处理异常 |
| **可恢复性** | 不可恢复 | 可捕获并恢复 |
| **典型场景** | JVM 内存溢出、栈溢出 | 业务逻辑错误、IO 异常 |
| **处理方式** | 不应捕获，让程序终止 | 应捕获并处理 |

**原理说明：**

```java
// Throwable 继承体系
Throwable
├── Error                    // 系统级错误
│   ├── OutOfMemoryError    // 堆内存溢出
│   ├── StackOverflowError  // 栈溢出
│   └── VirtualMachineError // 虚拟机错误
└── Exception               // 程序级异常
    ├── IOException         // 受检异常
    ├── SQLException
    └── RuntimeException    // 非受检异常
        ├── NullPointerException
        └── IllegalArgumentException
```

**关键点：**
- **Error** 表示 JVM 或系统层面的严重问题，如 `OutOfMemoryError`、`StackOverflowError`，程序无法处理，应该让其快速失败
- **Exception** 表示程序可以处理的异常情况，分为受检异常和非受检异常

---

### 二、CheckedException 与 RuntimeException 的差异

**核心区别：**

| 维度 | CheckedException（受检异常） | RuntimeException（非受检异常） |
|------|------------------------------|-------------------------------|
| **编译检查** | 必须显式捕获或声明抛出 | 无需强制处理 |
| **典型场景** | 外部资源访问（IO、网络、数据库） | 编程错误（空指针、数组越界） |
| **设计意图** | 强制开发者处理可预见的异常 | 表示代码逻辑错误 |
| **性能影响** | 有一定开销（需要栈追踪） | 相同开销，但使用更频繁 |

**代码示例：**

```java
// 1. CheckedException - 必须处理
public void readFile(String path) throws IOException {  // 必须声明
    FileReader reader = new FileReader(path);  // 可能抛出 IOException
    // ...
}

// 调用方必须处理
public void caller() {
    try {
        readFile("data.txt");
    } catch (IOException e) {  // 必须捕获或继续抛出
        log.error("文件读取失败", e);
    }
}

// 2. RuntimeException - 无需强制处理
public int divide(int a, int b) {
    if (b == 0) {
        throw new IllegalArgumentException("除数不能为0");  // 无需声明
    }
    return a / b;
}

// 调用方可以选择不处理
public void caller() {
    int result = divide(10, 0);  // 编译通过，运行时抛出异常
}
```

---

### 三、使用场景与最佳实践

**1. 何时使用 CheckedException？**
- 外部资源操作：文件 IO、网络请求、数据库连接
- 业务规则校验：用户输入验证、权限检查
- 可恢复的异常：重试机制、降级处理

**2. 何时使用 RuntimeException？**
- 编程错误：空指针、数组越界、类型转换错误
- 前置条件检查：参数校验（如 `Objects.requireNonNull()`）
- 不应该发生的异常：配置错误、状态不一致

**3. 性能与线程安全考量**

```java
// 避免在高频路径中使用异常控制流程
// ❌ 错误示例
public Integer parseIntSlow(String str) {
    try {
        return Integer.parseInt(str);
    } catch (NumberFormatException e) {
        return null;  // 异常开销大
    }
}

// ✅ 推荐做法
public Integer parseIntFast(String str) {
    if (str == null || !str.matches("\\d+")) {
        return null;  // 提前校验，避免异常
    }
    return Integer.parseInt(str);
}
```

---

### 四、答题总结

**面试回答要点：**

1. **Error 是系统级错误**（如 OOM），不可恢复，不应捕获；**Exception 是程序级异常**，可处理
2. **CheckedException 必须显式处理**（编译期检查），适用于外部资源操作；**RuntimeException 无需强制处理**，表示编程错误
3. **最佳实践**：
   - 对于可预见的外部异常（IO、网络），使用 CheckedException
   - 对于编程错误（空指针、参数非法），使用 RuntimeException
   - 避免用异常控制正常业务流程（性能开销大）
4. **Spring 等框架的趋势**：倾向于使用 RuntimeException（如 `DataAccessException`），减少样板代码

**关键记忆点：**
- Error = 系统崩溃，不可恢复
- CheckedException = 外部异常，必须处理
- RuntimeException = 编程错误，可选处理
