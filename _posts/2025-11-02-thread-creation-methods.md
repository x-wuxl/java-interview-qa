---
layout: post
title: "创建线程有几种方式？"
date: 2025-11-02
categories: [并发编程, 线程基础]
tags: [Java, 多线程, 并发, Thread]
description: "深入解析Java中创建线程的四种方式，包括继承Thread、实现Runnable、实现Callable和使用线程池，以及各自的适用场景和优缺点。"
---

## 核心概念

Java创建线程主要有**4种方式**：
1. 继承`Thread`类
2. 实现`Runnable`接口
3. 实现`Callable`接口（配合`FutureTask`）
4. 使用线程池（推荐）

## 详细解析

### 1. 继承Thread类

```java
public class MyThread extends Thread {
    @Override
    public void run() {
        System.out.println("线程执行：" + Thread.currentThread().getName());
    }
}

// 使用
MyThread thread = new MyThread();
thread.start();
```

**缺点**：Java单继承限制，扩展性差。

### 2. 实现Runnable接口

```java
public class MyRunnable implements Runnable {
    @Override
    public void run() {
        System.out.println("线程执行：" + Thread.currentThread().getName());
    }
}

// 使用
Thread thread = new Thread(new MyRunnable());
thread.start();

// 或使用Lambda（推荐）
new Thread(() -> System.out.println("执行任务")).start();
```

**优点**：避免单继承限制，代码解耦，更符合面向对象思想。

### 3. 实现Callable接口

```java
public class MyCallable implements Callable<String> {
    @Override
    public String call() throws Exception {
        Thread.sleep(1000);
        return "任务执行结果";
    }
}

// 使用
FutureTask<String> futureTask = new FutureTask<>(new MyCallable());
new Thread(futureTask).start();

// 获取返回值（阻塞）
String result = futureTask.get();
```

**优点**：
- 有返回值
- 可以抛出异常
- 支持泛型

### 4. 使用线程池（推荐）

```java
ExecutorService executor = Executors.newFixedThreadPool(10);

// 提交Runnable
executor.execute(() -> System.out.println("执行任务"));

// 提交Callable
Future<String> future = executor.submit(() -> {
    return "任务结果";
});

executor.shutdown();
```

**优点**：
- 复用线程，减少创建销毁开销
- 统一管理线程资源
- 提供队列缓冲和拒绝策略
- 生产环境首选方案

## 性能与最佳实践

### 线程安全考量
- 多个线程共享同一个`Runnable`实例时，注意成员变量的线程安全
- 优先使用局部变量或`ThreadLocal`

### 生产环境建议
```java
// 避免使用Executors工具类，手动创建线程池
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    10,                      // 核心线程数
    20,                      // 最大线程数
    60L,                     // 空闲线程存活时间
    TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(100),  // 任务队列
    new ThreadFactoryBuilder()
        .setNameFormat("business-pool-%d")
        .build(),
    new ThreadPoolExecutor.CallerRunsPolicy()  // 拒绝策略
);
```

## 答题总结

**面试标准答案**：
- **继承Thread**：简单但受单继承限制
- **实现Runnable**：解耦灵活，无返回值
- **实现Callable**：有返回值，可抛异常
- **线程池**：生产首选，资源复用，统一管理

**关键点**：本质上只有一种创建线程的方式——`new Thread()`，其他都是在定义线程执行的任务。`Runnable`和`Callable`是任务抽象，线程池是管理方式。

**推荐方案**：生产环境统一使用自定义线程池 + `Runnable`/`Callable`。

