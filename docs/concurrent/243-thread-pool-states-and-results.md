---
layout: default
title: "线程池有哪些状态？如何获取多线程并发执行结果？"
parent: 并发编程
nav_order: 243
description: "详解Java线程池的5种生命周期状态（RUNNING, SHUTDOWN, STOP, TIDYING, TERMINATED），并总结获取并发任务执行结果的三种主流方式。"
date: 2025-11-19
---
### 1. 线程池的 5 种状态

`ThreadPoolExecutor` 使用一个 `AtomicInteger` 类型的变量 `ctl` 同时维护线程数量和线程池状态。高 3 位表示状态，低 29 位表示线程数。

1.  **RUNNING**：
    *   **含义**：最正常的状态。接受新任务，也会处理阻塞队列中的任务。
    *   **转换**：线程池创建后即处于此状态。

2.  **SHUTDOWN**：
    *   **含义**：**不接受**新任务，但**会处理**阻塞队列中已有的任务。
    *   **转换**：调用 `shutdown()` 方法时。

3.  **STOP**：
    *   **含义**：**不接受**新任务，**不处理**阻塞队列中的任务，并且会**中断**正在执行的任务。
    *   **转换**：调用 `shutdownNow()` 方法时。

4.  **TIDYING**：
    *   **含义**：所有任务都已终止，工作线程数为 0。
    *   **转换**：当 SHUTDOWN 状态下队列和线程池都为空，或 STOP 状态下线程池为空时。

5.  **TERMINATED**：
    *   **含义**：线程池彻底关闭。
    *   **转换**：TIDYING 状态下执行完 `terminated()` 钩子方法后。

### 2. 获取并发执行结果的方式

#### 方式一：使用 `Future` (最基础)
通过 `ThreadPoolExecutor.submit()` 提交任务，返回 `Future` 对象。调用 `future.get()` 会阻塞当前线程直到任务完成。

```java
Future<String> future = executor.submit(() -> "Hello");
try {
    String result = future.get(); // 阻塞等待
} catch (Exception e) { e.printStackTrace(); }
```

#### 方式二：使用 `CompletableFuture` (推荐)
Java 8 引入，支持非阻塞的回调链式编程，功能更强大，支持任务编排（如 A 执行完执行 B，或 A、B 并行）。

```java
CompletableFuture.supplyAsync(() -> "Hello", executor)
    .thenApply(s -> s + " World")
    .thenAccept(System.out::println); // 结果就绪后自动执行
```

#### 方式三：使用 `CompletionService` (批量处理)
如果你提交了一组任务，想“谁先完成就先获取谁”，而不是按提交顺序获取，使用 `ExecutorCompletionService`。它内部维护了一个阻塞队列，任务完成后会自动放入队列。

```java
CompletionService<Integer> cs = new ExecutorCompletionService<>(executor);
for (int i = 0; i < 5; i++) cs.submit(task);

for (int i = 0; i < 5; i++) {
    // take() 会阻塞，直到有任意一个任务完成
    System.out.println(cs.take().get()); 
}
```

### 3. 总结

**回答总结：**
“线程池有 RUNNING（正常运行）、SHUTDOWN（平滑关闭）、STOP（强行关闭）、TIDYING（整理中）和 TERMINATED（结束）五种状态。获取结果主要有三种方式：基础的 **Future.get()** 阻塞获取；功能强大的 **CompletableFuture** 异步回调；以及适合批量处理的 **CompletionService**，它能实现‘先做完先拿结果’。”
