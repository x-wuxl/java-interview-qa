---
layout: post
title: "CountDownLatch、CyclicBarrier、Semaphore区别？"
date: 2025-11-02
description: "详解Java并发工具类CountDownLatch、CyclicBarrier和Semaphore的区别、原理及应用场景"
author: "wuxl"
categories: [并发编程]
tags: [CountDownLatch, CyclicBarrier, Semaphore, 并发工具类, JUC]
---

## 问题

CountDownLatch、CyclicBarrier、Semaphore区别？

## 答案

### 核心概念

这三个都是JUC包提供的同步辅助类，用于控制线程间的协作，但各自解决的问题不同：

- **CountDownLatch（倒计数门栓）**：一个或多个线程等待其他线程完成操作后再执行
- **CyclicBarrier（循环栅栏）**：多个线程互相等待，直到所有线程都到达某个屏障点后再一起继续执行
- **Semaphore（信号量）**：控制同时访问某个资源的线程数量

### 原理与关键区别

| 维度 | CountDownLatch | CyclicBarrier | Semaphore |
|------|---------------|---------------|-----------|
| **等待模式** | 一个或多个线程等待其他线程完成 | 多个线程互相等待 | 控制并发访问数量 |
| **计数器方向** | 递减（`countDown()`） | 递增（每个线程到达屏障） | 可增可减（`acquire()`/`release()`） |
| **是否可重用** | ❌ 不可重用（一次性） | ✅ 可重用（循环使用） | ✅ 可重用 |
| **底层实现** | 基于AQS共享锁 | 基于ReentrantLock + Condition | 基于AQS共享锁 |
| **回调机制** | ❌ 无 | ✅ 支持barrierAction | ❌ 无 |

### 源码关键点

**CountDownLatch核心机制**：
```java
public void countDown() {
    sync.releaseShared(1);  // 递减计数器
}

public void await() throws InterruptedException {
    sync.acquireSharedInterruptibly(1);  // 等待计数器归零
}
```

**CyclicBarrier核心机制**：
```java
public int await() throws InterruptedException, BrokenBarrierException {
    final ReentrantLock lock = this.lock;
    lock.lock();
    try {
        int index = --count;  // 递减到达线程数
        if (index == 0) {     // 最后一个线程
            if (barrierCommand != null)
                barrierCommand.run();  // 执行回调
            nextGeneration();  // 重置栅栏，实现循环复用
            return 0;
        }
        for (;;) {
            trip.await();  // 其他线程在Condition上等待
        }
    } finally {
        lock.unlock();
    }
}
```

**Semaphore核心机制**：
```java
public void acquire() throws InterruptedException {
    sync.acquireSharedInterruptibly(1);  // 获取许可，permits-1
}

public void release() {
    sync.releaseShared(1);  // 释放许可，permits+1
}
```

### 典型应用场景

**CountDownLatch**：
- 主线程等待多个子任务完成（如并行加载多个资源）
- 多个线程等待某个初始化操作完成后再开始执行

**CyclicBarrier**：
- 多线程计算数据，最后合并结果（如MapReduce）
- 多人游戏等待所有玩家准备就绪

**Semaphore**：
- 限流：控制数据库连接池、线程池的并发访问数
- 实现资源池（如对象池、连接池）

### 代码示例

```java
// CountDownLatch示例：并行加载资源
public class CountDownLatchDemo {
    public static void main(String[] args) throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(3);

        for (int i = 1; i <= 3; i++) {
            int taskId = i;
            new Thread(() -> {
                System.out.println("Task-" + taskId + " 开始加载");
                try { Thread.sleep(1000); } catch (InterruptedException e) {}
                System.out.println("Task-" + taskId + " 加载完成");
                latch.countDown();  // 任务完成，计数器-1
            }).start();
        }

        latch.await();  // 主线程等待所有任务完成
        System.out.println("所有资源加载完成，系统启动！");
    }
}

// CyclicBarrier示例：多线程计算后汇总
public class CyclicBarrierDemo {
    public static void main(String[] args) {
        CyclicBarrier barrier = new CyclicBarrier(3, () -> {
            System.out.println("所有线程到达屏障点，开始汇总结果");
        });

        for (int i = 1; i <= 3; i++) {
            int threadId = i;
            new Thread(() -> {
                System.out.println("线程-" + threadId + " 开始计算");
                try {
                    Thread.sleep(1000);
                    System.out.println("线程-" + threadId + " 计算完成，等待其他线程");
                    barrier.await();  // 等待其他线程
                    System.out.println("线程-" + threadId + " 继续执行后续任务");
                } catch (Exception e) {}
            }).start();
        }
    }
}

// Semaphore示例：限流控制
public class SemaphoreDemo {
    public static void main(String[] args) {
        Semaphore semaphore = new Semaphore(2);  // 最多2个线程同时访问

        for (int i = 1; i <= 5; i++) {
            int taskId = i;
            new Thread(() -> {
                try {
                    semaphore.acquire();  // 获取许可
                    System.out.println("Task-" + taskId + " 获得许可，开始执行");
                    Thread.sleep(2000);  // 模拟业务处理
                    System.out.println("Task-" + taskId + " 执行完成");
                } catch (InterruptedException e) {
                } finally {
                    semaphore.release();  // 释放许可
                }
            }).start();
        }
    }
}
```

### 面试答题要点

1. **CountDownLatch**：适合主线程等待多个子任务完成的场景，**一次性使用**，基于AQS共享模式
2. **CyclicBarrier**：适合多线程互相等待的场景，**可循环复用**，支持屏障触发时执行回调任务
3. **Semaphore**：适合限流场景，控制对共享资源的并发访问数量，**可动态增减许可数**
4. 三者都是线程安全的，底层依赖AQS或Lock实现
5. 选择依据：看是"等待完成"还是"互相等待"还是"限制并发数"
