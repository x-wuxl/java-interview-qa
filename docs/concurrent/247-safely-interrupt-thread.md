---
layout: default
title: "如何安全地中断一个正在运行的线程？"
parent: 并发编程
nav_order: 247
description: "废弃的stop()方法为何危险？详解Java线程中断的协作机制，以及如何正确处理InterruptedException以避免'吞掉'中断信号。"
date: 2025-11-19
---
### 1. 核心概念简述

在 Java 中，中断（Interrupt）是一种**协作机制**，而不是强制命令。调用 `thread.interrupt()` 并不会立即停止目标线程的运行，它仅仅是把目标线程的**中断标志位**设置为 `true`。目标线程需要自己去检测这个标志位，并决定如何响应（通常是清理资源后退出）。

### 2. 原理与源码关键点

#### 三个关键方法
1.  **`interrupt()`**：设置中断标志位。如果线程处于阻塞状态（如 `sleep`, `wait`），会抛出 `InterruptedException` 并**清除**标志位。
2.  **`isInterrupted()`**：查询当前中断标志位，**不改变**状态。
3.  **`Thread.interrupted()`**：静态方法，查询当前线程的中断标志位，并**重置（清除）**该标志位。

#### 为什么不能用 `stop()`？
`Thread.stop()` 方法已被废弃。因为它太暴力，会立即终止线程并释放该线程持有的所有锁（Monitors）。这可能导致受保护的数据处于**不一致**的状态（例如转账转了一半），从而破坏数据完整性。

### 3. 最佳实践

#### 场景一：循环任务
在循环条件中显式检查中断标志。

```java
while (!Thread.currentThread().isInterrupted()) {
    // 执行任务
}
```

#### 场景二：处理 `InterruptedException`
这是面试中的高频考点。当捕获到 `InterruptedException` 时，标志位会被自动清除。如果你不打算抛出该异常，**必须手动再次中断当前线程**，以恢复中断状态，否则上层调用者无法感知线程已被中断。

```java
try {
    Thread.sleep(1000);
} catch (InterruptedException e) {
    // 错误做法：打印日志后什么都不做（吞掉中断）
    // e.printStackTrace(); 
    
    // 正确做法：恢复中断状态
    Thread.currentThread().interrupt(); 
    // 或者：抛出异常 throw e;
}
```

### 4. 总结与示例

**回答总结：**
“安全中断线程必须使用 `interrupt()` 协作机制，坚决避免使用废弃的 `stop()`。线程内部应通过 `isInterrupted()` 轮询标志位。如果捕获了 `InterruptedException`，由于异常抛出时会清除标志位，必须在 `catch` 块中调用 `Thread.currentThread().interrupt()` **恢复中断状态**，或者直接抛出异常，确保中断信号能传递给上层。”
