---
title: "JDK21中的虚拟线程是怎么回事？"
date: 2025-11-02
description: "深入解析JDK21虚拟线程的设计原理、M:N调度模型及其与平台线程的核心差异"
author: "wuxl"
categories: [并发编程]
tags: [虚拟线程, JDK21, Project Loom, 协程, 并发模型]
nav_order: 270
parent: 并发编程
---
## 问题

JDK21中的虚拟线程是怎么回事？

## 答案

### 核心概念

**虚拟线程**（Virtual Threads）是JDK19预览、JDK21正式发布的**轻量级线程实现**，是**Project Loom**项目的核心成果。它通过**M:N调度模型**，让大量虚拟线程（M）映射到少量平台线程（N）上执行，从而实现**百万级并发**能力。

**关键特性**：
- **轻量级**：创建成本极低（~1KB内存），可轻松创建百万级线程
- **用户态调度**：由JVM自行调度，无需经过操作系统
- **阻塞不占用线程**：阻塞时自动卸载（unmount），释放平台线程
- **同步编程模型**：无需回调，代码结构清晰

### 设计原理

#### 1. M:N调度模型

```
虚拟线程（Virtual Threads）    平台线程（Carrier Threads）    OS线程
    VThread-1                           ↘
    VThread-2                    →  Platform-1  →  OS-Thread-1
    VThread-3                           ↗
    VThread-4                           ↘
    VThread-5                    →  Platform-2  →  OS-Thread-2
    ...                                 ↗
    VThread-1000000              →  Platform-N  →  OS-Thread-N
```

**调度流程**：
1. 虚拟线程运行时会**挂载（mount）**到平台线程（carrier thread）上执行
2. 遇到阻塞操作（如IO、sleep）时，虚拟线程会**卸载（unmount）**
3. 平台线程被释放，可以执行其他虚拟线程
4. 阻塞结束后，虚拟线程重新调度到可用的平台线程上

#### 2. ForkJoinPool调度器

虚拟线程默认使用**ForkJoinPool**作为调度器：

```java
// JDK源码简化
class VirtualThread extends Thread {
    private static final ForkJoinPool DEFAULT_SCHEDULER = 
        new ForkJoinPool(
            Runtime.getRuntime().availableProcessors(),
            pool -> new CarrierThread(pool),
            null, 
            false
        );

    // 挂载到carrier thread
    private void mount() {
        carrierThread = Thread.currentThread();
        // 切换上下文
    }

    // 卸载
    private void unmount() {
        carrierThread = null;
        // 切换回调度器
    }
}
```

**调度器参数**：
```java
// 可通过系统属性调整
-Djdk.virtualThreadScheduler.parallelism=10    // 平台线程数，默认CPU核心数
-Djdk.virtualThreadScheduler.maxPoolSize=256   // 最大线程数
```

#### 3. Continuation延续机制

虚拟线程的核心是**Continuation**（延续）技术：

```java
// Continuation伪代码
class Continuation {
    void run() {
        while (true) {
            executeTask();
            if (needBlock()) {
                yield();  // 保存当前执行状态，让出CPU
            }
        }
    }

    void yield() {
        saveStackFrames();      // 保存栈帧
        saveLocalVariables();   // 保存局部变量
        // 返回调度器
    }

    void resume() {
        restoreStackFrames();   // 恢复栈帧
        restoreLocalVariables();// 恢复局部变量
        // 继续执行
    }
}
```

### 创建与使用

#### 1. 基本创建方式

```java
// 方式1：Thread.ofVirtual()
Thread vThread = Thread.ofVirtual().start(() -> {
    System.out.println("Hello from virtual thread");
});

// 方式2：Thread.startVirtualThread()
Thread.startVirtualThread(() -> {
    System.out.println("Hello from virtual thread");
});

// 方式3：Executors.newVirtualThreadPerTaskExecutor()
ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
executor.submit(() -> {
    System.out.println("Task in virtual thread");
});
```

#### 2. 批量创建示例

```java
// 创建100万个虚拟线程（秒级完成）
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    IntStream.range(0, 1_000_000).forEach(i -> {
        executor.submit(() -> {
            Thread.sleep(Duration.ofSeconds(1));
            return i;
        });
    });
}  // 自动等待所有任务完成

// 等价的平台线程代码（会OOM）
var executor = Executors.newCachedThreadPool();  // 创建100万个OS线程 → 崩溃！
```

#### 3. 高并发场景对比

**传统平台线程**：
```java
// 处理10000个请求，需要大线程池
ExecutorService executor = Executors.newFixedThreadPool(200);
for (int i = 0; i < 10000; i++) {
    executor.submit(() -> {
        // 阻塞IO操作，线程被占用
        String data = httpClient.get(url);  // 等待1秒
        processData(data);
    });
}
// 需要200个OS线程 + 排队等待
```

**虚拟线程方案**：
```java
// 直接创建10000个虚拟线程
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    for (int i = 0; i < 10000; i++) {
        executor.submit(() -> {
            // IO阻塞时自动卸载，不占用平台线程
            String data = httpClient.get(url);  // 虚拟线程yield
            processData(data);
        });
    }
}
// 只需8-16个平台线程（CPU核心数）
```

### 与平台线程的核心差异

| 特性 | 平台线程（Platform Thread） | 虚拟线程（Virtual Thread） |
|------|---------------------------|--------------------------|
| **底层实现** | 1:1映射OS线程 | M:N映射，多个虚拟线程共享少量平台线程 |
| **创建成本** | 高（~2MB栈空间） | 极低（~1KB） |
| **数量上限** | 几千至几万 | 百万级 |
| **调度方式** | 操作系统内核调度 | JVM用户态调度 |
| **阻塞影响** | 阻塞时OS线程被占用 | 阻塞时自动卸载，释放平台线程 |
| **上下文切换** | 内核态切换（慢） | 用户态切换（快） |
| **ThreadLocal** | 开销小 | 开销大（每个虚拟线程独立） |
| **线程池** | 需要复用线程 | 无需池化，按需创建 |

### 性能优势场景

**适合虚拟线程**：
```java
// 1. IO密集型任务
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<CompletableFuture<String>> futures = urls.stream()
        .map(url -> CompletableFuture.supplyAsync(() -> 
            httpClient.get(url),  // 阻塞IO自动卸载
            executor
        ))
        .toList();
    
    // 处理100万个HTTP请求，只需几个平台线程
    CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
}

// 2. 高并发请求处理
@RestController
public class UserController {
    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        // Spring Boot 3.2+ 自动在虚拟线程中处理
        User user = userService.findById(id);        // DB查询，自动卸载
        Orders orders = orderService.getOrders(id);  // 再次IO，再次卸载
        return enrichUser(user, orders);
    }
}
```

**不适合虚拟线程**：
```java
// CPU密集型任务（无阻塞，无法卸载，反而增加调度开销）
for (int i = 0; i < 1_000_000; i++) {
    Thread.startVirtualThread(() -> {
        // 纯计算任务，虚拟线程无法卸载，白白占用调度资源
        BigInteger result = fibonacci(100000);
    });
}
// 应使用固定大小的平台线程池
```

### 实现细节：阻塞点改造

JDK对阻塞API进行了改造，使其支持虚拟线程卸载：

**已适配的阻塞点**：
```java
// 1. Thread.sleep() - 会卸载
Thread.sleep(Duration.ofSeconds(1));

// 2. 网络IO - 会卸载
Socket socket = new Socket("example.com", 80);
InputStream in = socket.getInputStream();
in.read();  // 自动卸载

// 3. Lock.lock() - 会卸载（ReentrantLock等）
ReentrantLock lock = new ReentrantLock();
lock.lock();  // 等待锁时卸载
try {
    // ...
} finally {
    lock.unlock();
}
```

**未适配的阻塞点**（会固定虚拟线程，pinning问题）：
```java
// 1. synchronized - 不会卸载！
synchronized (obj) {
    Thread.sleep(1000);  // 虚拟线程被pinning到平台线程
}

// 2. native方法
// 3. 外部资源等待
```

### 监控与诊断

```java
// 1. 获取虚拟线程信息
Thread vThread = Thread.ofVirtual().start(() -> {});
System.out.println(vThread.isVirtual());  // true

// 2. JFR事件监控
jcmd <pid> JFR.start settings=profile
jcmd <pid> JFR.dump filename=virtual-threads.jfr

// 关键事件：
// - jdk.VirtualThreadStart
// - jdk.VirtualThreadEnd
// - jdk.VirtualThreadPinned  // 关注pinning问题

// 3. JMX监控
ThreadMXBean mxBean = ManagementFactory.getThreadMXBean();
long[] ids = mxBean.getAllThreadIds();  // 包含虚拟线程
```

### 迁移注意事项

**1. Spring Boot集成**：
```yaml
# application.yml (Spring Boot 3.2+)
spring:
  threads:
    virtual:
      enabled: true  # 启用虚拟线程
```

**2. 代码调整原则**：
```java
// ❌ 避免
synchronized (lock) {
    blockingCall();  // 导致pinning
}

// ✅ 改用
ReentrantLock lock = new ReentrantLock();
lock.lock();
try {
    blockingCall();  // 正常卸载
} finally {
    lock.unlock();
}

// ❌ 避免使用线程池
ExecutorService pool = Executors.newFixedThreadPool(10);

// ✅ 直接创建虚拟线程
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    // ...
}
```

### 面试答题要点

1. **核心定义**：虚拟线程是JDK21正式发布的轻量级线程，通过M:N调度模型实现百万级并发
2. **关键技术**：基于Continuation机制，阻塞时自动卸载释放平台线程，由ForkJoinPool调度
3. **适用场景**：IO密集型、高并发请求处理，不适合CPU密集型任务
4. **主要优势**：创建成本低、无需线程池、同步编程模型简化代码
5. **注意事项**：避免synchronized（导致pinning）、避免过度使用ThreadLocal、需要JDK21+
6. **性能对比**：单个虚拟线程仅占1KB内存，可轻松创建百万线程；平台线程需2MB，上限几千

**高级回答**：虚拟线程本质是将操作系统的M:N线程模型上移到JVM层实现，类似Go的goroutine和Kotlin的协程。通过用户态调度避免内核态切换开销，配合JDK改造的阻塞API（如NIO、ReentrantLock）实现自动卸载。但需注意synchronized等未改造的阻塞点会导致虚拟线程pinning到平台线程，降低并发能力。

