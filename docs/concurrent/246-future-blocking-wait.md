---
layout: default
title: "Future 如何通过阻塞等待获取结果？"
parent: 并发编程
nav_order: 246
description: "深入FutureTask源码，解析Future.get()方法是如何通过LockSupport.park()实现线程阻塞，以及任务完成后如何唤醒等待线程的机制。"
date: 2025-11-19
---
### 1. 核心概念简述

`Future` 是 Java 5 引入的接口，用于代表一个异步计算的结果。它的核心功能是允许调用者在任务提交后继续执行其他操作，直到需要结果时再调用 `get()` 方法获取。如果此时任务尚未完成，`get()` 方法会**阻塞**当前线程，直到任务完成或超时。

### 2. 原理与源码关键点

`Future` 的最常用实现类是 `FutureTask`。其阻塞等待机制的核心在于**状态机**和**线程挂起**。

#### 核心字段
```java
// 任务状态
private volatile int state;
private static final int NEW          = 0;
private static final int COMPLETING   = 1;
private static final int NORMAL       = 2;
// ... 其他异常或取消状态

// 等待节点（Treiber Stack 简单栈结构）
private volatile WaitNode waiters;
```

#### `get()` 方法原理
当调用 `get()` 时：
1.  **检查状态**：如果 `state > COMPLETING`（即已完成、异常或取消），直接返回结果。
2.  **入队等待**：如果任务未完成，当前线程会被封装成一个 `WaitNode` 节点，加入到 `waiters` 链表中。
3.  **挂起线程**：在一个死循环中，通过 `LockSupport.park(this)` 挂起当前线程（让出 CPU，进入 WAITING 状态）。

#### `run()` 方法原理（唤醒）
当任务执行完毕（`run()` 方法结束）时：
1.  **设置结果**：将计算结果赋值给 `outcome` 变量。
2.  **更新状态**：CAS 修改 `state` 为 `NORMAL`。
3.  **唤醒等待者**：遍历 `waiters` 链表，通过 `LockSupport.unpark(thread)` 依次唤醒所有阻塞在 `get()` 上的线程。

### 3. 性能与使用考量

1.  **避免永久阻塞**：
    *   强烈建议使用 `get(long timeout, TimeUnit unit)` 带超时的版本。如果任务因为死锁或死循环永远不结束，无参的 `get()` 会导致调用线程永久卡死。

2.  **CPU 消耗**：
    *   `LockSupport.park()` 挂起线程后，线程不占用 CPU 时间片，比忙轮询（Busy Spin）效率高得多。

### 4. 总结与示例

**回答总结：**
“`Future.get()` 的阻塞是通过 `FutureTask` 内部的状态机和 `LockSupport` 实现的。调用 `get()` 时，如果任务未完成，当前线程会被封装成节点加入等待队列，并被 `park()` 挂起。当任务执行完后，会更新状态并 `unpark()` 唤醒所有等待线程。生产环境中建议使用带超时的 `get()` 以防止死等。”

**代码示例：**

```java
FutureTask<String> futureTask = new FutureTask<>(() -> {
    Thread.sleep(2000);
    return "Done";
});
new Thread(futureTask).start();

try {
    // 内部会调用 LockSupport.park() 挂起主线程
    String result = futureTask.get(); 
    System.out.println(result);
} catch (Exception e) {
    e.printStackTrace();
}
```
