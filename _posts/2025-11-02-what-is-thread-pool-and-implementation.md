---
layout: post
title: "什么是线程池，如何实现的？"
date: 2025-11-02
categories: [Java并发编程, 线程池]
tags: [ThreadPoolExecutor, 线程池, 并发编程, 面试题]
description: "深入理解Java线程池的概念、实现原理及核心源码，掌握线程池的工作机制和任务执行流程"
---

## 一、核心概念

**线程池**是一种线程使用模式，它预先创建若干工作线程，通过复用这些线程来执行提交的任务，避免频繁创建和销毁线程带来的性能开销。

### 核心价值
- **降低资源消耗**：复用线程，减少线程创建和销毁的开销
- **提高响应速度**：任务无需等待线程创建即可立即执行
- **提高可管理性**：统一管理线程资源，避免无限制创建导致系统资源耗尽

---

## 二、实现原理

### 1. 核心类：ThreadPoolExecutor

Java中线程池的核心实现是 `ThreadPoolExecutor`，继承关系如下：

```java
java.util.concurrent.Executor (接口)
    ↓
java.util.concurrent.ExecutorService (接口)
    ↓
java.util.concurrent.AbstractExecutorService (抽象类)
    ↓
java.util.concurrent.ThreadPoolExecutor (实现类)
```

### 2. 核心参数

```java
public ThreadPoolExecutor(
    int corePoolSize,              // 核心线程数
    int maximumPoolSize,           // 最大线程数
    long keepAliveTime,            // 空闲线程存活时间
    TimeUnit unit,                 // 时间单位
    BlockingQueue<Runnable> workQueue,  // 任务队列
    ThreadFactory threadFactory,   // 线程工厂
    RejectedExecutionHandler handler    // 拒绝策略
)
```

**参数说明**：
- **corePoolSize**：核心线程数，即使空闲也会保留（除非设置allowCoreThreadTimeOut）
- **maximumPoolSize**：线程池最大容量，包含核心线程和非核心线程
- **keepAliveTime**：非核心线程空闲后的存活时间
- **workQueue**：用于存放待执行任务的阻塞队列（ArrayBlockingQueue、LinkedBlockingQueue等）
- **threadFactory**：用于创建新线程，可自定义线程名称、优先级等
- **handler**：当队列满且线程数达到最大值时的拒绝策略

---

## 三、任务执行流程

```java
提交任务
    ↓
当前线程数 < corePoolSize？
    ↓ 是
创建核心线程执行任务
    
    ↓ 否
任务队列已满？
    ↓ 否
任务加入队列等待
    
    ↓ 是
当前线程数 < maximumPoolSize？
    ↓ 是
创建非核心线程执行任务
    
    ↓ 否
执行拒绝策略
```

### 关键源码片段

```java
public void execute(Runnable command) {
    if (command == null)
        throw new NullPointerException();
    
    int c = ctl.get();
    // 1. 如果线程数小于核心线程数，创建核心线程
    if (workerCountOf(c) < corePoolSize) {
        if (addWorker(command, true))
            return;
        c = ctl.get();
    }
    // 2. 尝试将任务加入队列
    if (isRunning(c) && workQueue.offer(command)) {
        int recheck = ctl.get();
        if (!isRunning(recheck) && remove(command))
            reject(command);
        else if (workerCountOf(recheck) == 0)
            addWorker(null, false);
    }
    // 3. 队列满了，尝试创建非核心线程
    else if (!addWorker(command, false))
        reject(command);  // 4. 执行拒绝策略
}
```

---

## 四、核心内部类：Worker

线程池使用 `Worker` 类封装工作线程：

```java
private final class Worker extends AbstractQueuedSynchronizer 
    implements Runnable {
    final Thread thread;        // 持有的线程
    Runnable firstTask;         // 初始任务
    volatile long completedTasks; // 完成任务数
    
    Worker(Runnable firstTask) {
        setState(-1); // 禁止中断直到runWorker
        this.firstTask = firstTask;
        this.thread = getThreadFactory().newThread(this);
    }
    
    public void run() {
        runWorker(this);
    }
}
```

**关键机制**：
- Worker继承AQS实现了简单的不可重入互斥锁
- 通过锁状态判断线程是否正在执行任务（用于shutdown时的处理）

---

## 五、线程安全保障

### 1. ctl变量的原子性

```java
private final AtomicInteger ctl = new AtomicInteger(ctlOf(RUNNING, 0));
```

`ctl` 是一个 `AtomicInteger`，高3位存储线程池状态，低29位存储线程数量，通过位运算保证原子性更新。

### 2. 线程池状态

```java
private static final int RUNNING    = -1 << COUNT_BITS;  // 接受新任务
private static final int SHUTDOWN   =  0 << COUNT_BITS;  // 不接受新任务，处理队列任务
private static final int STOP       =  1 << COUNT_BITS;  // 不接受新任务，不处理队列，中断正在执行的任务
private static final int TIDYING    =  2 << COUNT_BITS;  // 所有任务已终止
private static final int TERMINATED =  3 << COUNT_BITS;  // terminated()已完成
```

---

## 六、使用示例

```java
// 创建线程池
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    5,                          // 核心线程数
    10,                         // 最大线程数
    60L,                        // 空闲线程存活时间
    TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(100),  // 队列容量100
    new ThreadFactoryBuilder()
        .setNameFormat("my-pool-%d")
        .build(),
    new ThreadPoolExecutor.CallerRunsPolicy()  // 调用者运行策略
);

// 提交任务
executor.execute(() -> {
    System.out.println("执行任务：" + Thread.currentThread().getName());
});

// 关闭线程池
executor.shutdown();  // 平滑关闭，等待任务完成
// executor.shutdownNow();  // 立即关闭，尝试中断正在执行的任务
```

---

## 七、面试答题总结

**简洁版回答**：

线程池是一种复用线程的机制，通过预创建线程来执行任务，避免频繁创建销毁线程的开销。

Java中通过 `ThreadPoolExecutor` 实现，核心有7个参数：核心线程数、最大线程数、空闲时间、时间单位、任务队列、线程工厂和拒绝策略。

执行流程：任务提交时，先判断核心线程是否已满，未满则创建核心线程；已满则加入队列；队列满则创建非核心线程；达到最大线程数则执行拒绝策略。

内部使用 `Worker` 类封装工作线程，通过 `AtomicInteger` 的 `ctl` 变量保证线程安全，高3位存储状态，低29位存储线程数。

**关键点**：
- 任务执行优先级：核心线程 → 队列 → 非核心线程 → 拒绝策略
- ctl变量巧妙地用一个整数存储了状态和数量两个信息
- Worker继承AQS实现简单互斥锁，用于判断线程是否空闲

