---
layout: post
title: "OutOfMemory和StackOverflow的区别是什么？"
date: 2025-11-01
description: "深入对比OutOfMemoryError和StackOverflowError的区别，包括发生场景、原因分析和解决方案"
author: "wuxl"
categories: [JVM]
tags: [JVM, OOM, StackOverflow, 异常处理, 内存管理]
---

## 问题

OutOfMemory和StackOverflow的区别是什么？

## 答案

### 核心概念

**OutOfMemoryError**和**StackOverflowError**都是Java中的**Error**(而非Exception),表示严重的不可恢复错误。两者的本质区别在于**发生的内存区域和原因不同**。

### 区别对比

| 维度 | OutOfMemoryError (OOM) | StackOverflowError (SOF) |
|------|------------------------|--------------------------|
| 继承关系 | VirtualMachineError | VirtualMachineError |
| 发生区域 | 堆、元空间、直接内存等 | 虚拟机栈/本地方法栈 |
| 根本原因 | 内存空间不足 | 栈深度超过限制 |
| 是否可扩展 | 可以(但达到上限) | 可以(但达到上限) |
| 典型场景 | 内存泄漏、对象过多 | 递归调用层数过深 |
| 解决方向 | 增加内存、修复泄漏 | 优化递归、增加栈大小 |

### OutOfMemoryError详解

#### 1. 堆内存OOM

**发生场景**: Java堆无法分配新对象

```java
/**
 * VM Args: -Xmx20m -Xms20m
 */
public class HeapOOM {
    static class OOMObject {}

    public static void main(String[] args) {
        List<OOMObject> list = new ArrayList<>();
        while (true) {
            list.add(new OOMObject());  // 持续创建对象
        }
    }
}

// 输出:
// Exception in thread "main" java.lang.OutOfMemoryError: Java heap space
```

**原因分析**:
- 创建了大量对象且持有引用
- 对象无法被GC回收
- 堆内存不足以分配新对象

**解决方案**:
```bash
# 1. 增加堆内存
-Xmx4g

# 2. 分析堆转储文件
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/tmp/heapdump.hprof
```

#### 2. 元空间OOM (JDK 8+)

**发生场景**: 加载了过多的类

```java
/**
 * VM Args: -XX:MaxMetaspaceSize=20m
 */
public class MetaspaceOOM {
    public static void main(String[] args) {
        int count = 0;
        try {
            while (true) {
                // 使用CGLib动态生成类
                Enhancer enhancer = new Enhancer();
                enhancer.setSuperclass(Object.class);
                enhancer.setUseCache(false);
                enhancer.setCallback(new MethodInterceptor() {
                    @Override
                    public Object intercept(Object obj, Method method,
                                          Object[] args, MethodProxy proxy) throws Throwable {
                        return proxy.invokeSuper(obj, args);
                    }
                });
                enhancer.create();
                count++;
            }
        } catch (Throwable e) {
            System.out.println("Generated " + count + " classes");
            e.printStackTrace();
        }
    }
}

// 输出:
// java.lang.OutOfMemoryError: Metaspace
```

**原因分析**:
- 动态生成大量类(CGLib、ASM、动态代理等)
- 类加载器泄漏导致类无法卸载
- 元空间配置过小

**解决方案**:
```bash
-XX:MaxMetaspaceSize=512m
-XX:+TraceClassLoading    # 跟踪类加载
-XX:+TraceClassUnloading  # 跟踪类卸载
```

#### 3. 直接内存OOM

**发生场景**: DirectByteBuffer分配超过限制

```java
/**
 * VM Args: -Xmx20m -XX:MaxDirectMemorySize=10m
 */
public class DirectMemoryOOM {
    public static void main(String[] args) throws Exception {
        final int _1MB = 1024 * 1024;
        int count = 0;
        try {
            while (true) {
                ByteBuffer.allocateDirect(_1MB);
                count++;
            }
        } catch (Throwable e) {
            System.out.println("Allocated " + count + " MB");
            e.printStackTrace();
        }
    }
}

// 输出:
// java.lang.OutOfMemoryError: Direct buffer memory
```

**解决方案**:
```bash
-XX:MaxDirectMemorySize=1g
```

#### 4. 无法创建新的本地线程

**发生场景**: 系统无法创建新线程

```java
/**
 * VM Args: -Xss2m (减少每个线程栈大小,可以创建更多线程)
 */
public class ThreadOOM {
    public static void main(String[] args) {
        int count = 0;
        try {
            while (true) {
                new Thread(() -> {
                    try {
                        Thread.sleep(100000);
                    } catch (InterruptedException e) {}
                }).start();
                count++;
            }
        } catch (Throwable e) {
            System.out.println("Created " + count + " threads");
            e.printStackTrace();
        }
    }
}

// 输出:
// java.lang.OutOfMemoryError: unable to create new native thread
```

**原因分析**:
- 系统线程数达到上限
- 内存不足以分配新线程的栈空间
- 操作系统限制(ulimit -u)

**解决方案**:
```bash
# 1. 减少每个线程栈大小
-Xss256k

# 2. 使用线程池控制线程数
ExecutorService executor = Executors.newFixedThreadPool(100);

# 3. 调整系统限制(Linux)
ulimit -u 4096
```

### StackOverflowError详解

#### 1. 典型场景: 递归调用过深

```java
/**
 * VM Args: -Xss128k (减小栈大小,更容易复现)
 */
public class StackOverflowExample {
    private int depth = 0;

    public void recursion() {
        depth++;
        recursion();  // 无限递归
    }

    public static void main(String[] args) {
        StackOverflowExample example = new StackOverflowExample();
        try {
            example.recursion();
        } catch (Throwable e) {
            System.out.println("Stack depth: " + example.depth);
            e.printStackTrace();
        }
    }
}

// 输出:
// Stack depth: 1000 (具体数值取决于-Xss设置)
// java.lang.StackOverflowError
```

#### 2. 原因分析

**栈帧过多**:
- 每次方法调用都会创建栈帧
- 栈帧包含局部变量表、操作数栈、返回地址等
- 递归深度超过栈空间限制

**栈帧过大**:
```java
public void largeLocalVariables() {
    int[] array1 = new int[100000];  // 局部变量过大
    int[] array2 = new int[100000];
    int[] array3 = new int[100000];
    // 单个栈帧占用空间过大,也可能导致SOF
}
```

#### 3. 常见错误代码

**错误的递归终止条件**:
```java
// 错误: 条件永远为true
public int factorial(int n) {
    if (n > 0) {  // 应该是 n == 1 或 n <= 1
        return n * factorial(n - 1);
    }
    return 1;
}
```

**循环引用导致无限递归**:
```java
class Node {
    String data;
    Node next;

    @Override
    public String toString() {
        return data + " -> " + next;  // 如果存在循环引用,toString会无限递归
    }
}

// 使用:
Node n1 = new Node();
Node n2 = new Node();
n1.next = n2;
n2.next = n1;  // 循环引用
System.out.println(n1);  // StackOverflowError
```

#### 4. 解决方案

**方案1: 优化算法,改递归为迭代**:
```java
// 递归版本(可能SOF)
public int factorialRecursive(int n) {
    if (n <= 1) return 1;
    return n * factorialRecursive(n - 1);
}

// 迭代版本(不会SOF)
public int factorialIterative(int n) {
    int result = 1;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}
```

**方案2: 使用尾递归优化**(Java不支持尾递归优化,但可以手动改写):
```java
// 普通递归
public int sum(int n) {
    if (n == 1) return 1;
    return n + sum(n - 1);  // 不是尾递归
}

// 尾递归形式(Java仍会SOF,但逻辑上更优)
public int sumTail(int n, int accumulator) {
    if (n == 1) return accumulator + 1;
    return sumTail(n - 1, accumulator + n);  // 尾递归
}
```

**方案3: 增加栈大小**:
```bash
-Xss2m  # 将栈大小从默认1MB增加到2MB
```

**方案4: 使用栈数据结构模拟递归**:
```java
// 使用栈模拟递归
public void traverseTree(TreeNode root) {
    Stack<TreeNode> stack = new Stack<>();
    stack.push(root);

    while (!stack.isEmpty()) {
        TreeNode node = stack.pop();
        System.out.println(node.val);

        if (node.right != null) stack.push(node.right);
        if (node.left != null) stack.push(node.left);
    }
}
```

### 如何区分和诊断

#### 1. 异常信息判断

```java
try {
    // 可能抛出OOM或SOF的代码
} catch (OutOfMemoryError e) {
    System.err.println("发生内存溢出: " + e.getMessage());
    // Java heap space / Metaspace / Direct buffer memory / unable to create new native thread
} catch (StackOverflowError e) {
    System.err.println("发生栈溢出");
    e.printStackTrace();  // 查看调用栈,找到递归调用链
}
```

#### 2. 分析堆转储

```bash
# OOM时自动生成堆转储
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/tmp/heapdump.hprof

# 使用MAT或jhat分析
jhat heapdump.hprof
# 浏览器访问 http://localhost:7000
```

#### 3. 查看GC日志

```bash
# 启用GC日志
-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:/tmp/gc.log

# OOM前通常有频繁的Full GC
[Full GC 1024K->1024K(2048K), 1.2345678 secs]  # GC后内存几乎不下降
```

### 实战案例

#### 案例1: 定位堆OOM

```java
// 使用MAT(Memory Analyzer Tool)分析
// 1. Leak Suspects Report: 自动找出疑似泄漏点
// 2. Dominator Tree: 查看占用内存最多的对象
// 3. Path to GC Roots: 查看对象为何无法被GC

// 常见原因:
// - ThreadLocal未清理
// - 静态集合持有对象引用
// - 缓存无限增长
// - 监听器未注销
```

#### 案例2: 定位StackOverflow

```java
// 分析异常栈:
java.lang.StackOverflowError
    at com.example.MyClass.method(MyClass.java:10)
    at com.example.MyClass.method(MyClass.java:10)  // 重复调用
    at com.example.MyClass.method(MyClass.java:10)
    ...

// 查看MyClass.java第10行,找到递归调用
```

### 面试总结

**OutOfMemoryError**:
- 发生在堆、元空间、直接内存等区域
- 根本原因是内存不足
- 解决: 增加内存、修复内存泄漏、优化对象创建
- 典型场景: 内存泄漏、创建大量对象、类加载过多

**StackOverflowError**:
- 发生在虚拟机栈/本地方法栈
- 根本原因是栈深度超限
- 解决: 优化递归算法、改用迭代、增加栈大小
- 典型场景: 无限递归、递归深度过大

**关键区别**: OOM是"空间不够了",SOF是"调用太深了"。
