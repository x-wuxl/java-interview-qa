---
layout: default
title: "线程池的拒绝策略有哪些？"
parent: 并发编程
nav_order: 237
description: "详解Java线程池的四种内置拒绝策略及自定义拒绝策略的实现方式，掌握不同场景下的策略选择"
date: 2025-11-02
---
## 一、核心概念

**拒绝策略（RejectedExecutionHandler）**是当线程池无法接受新任务时的处理机制。触发条件：
- 线程池已关闭（shutdown或shutdownNow）
- 任务队列已满 **且** 线程数达到 `maximumPoolSize`

---

## 二、四种内置拒绝策略

### 1. AbortPolicy（默认策略）

**行为**：直接抛出 `RejectedExecutionException` 异常，拒绝新任务。

```java
public static class AbortPolicy implements RejectedExecutionHandler {
    public void rejectedExecution(Runnable r, ThreadPoolExecutor e) {
        throw new RejectedExecutionException(
            "Task " + r.toString() + 
            " rejected from " + e.toString()
        );
    }
}
```

**适用场景**：
- 需要明确感知任务被拒绝的情况
- 可以通过捕获异常进行后续处理（如告警、重试等）

**示例**：
```java
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    2, 2, 0L, TimeUnit.SECONDS,
    new ArrayBlockingQueue<>(1),  // 队列容量为1
    new ThreadPoolExecutor.AbortPolicy()
);

try {
    // 提交3个长任务，第3个会被拒绝
    for (int i = 0; i < 3; i++) {
        executor.execute(() -> {
            try { Thread.sleep(5000); } catch (InterruptedException e) {}
        });
    }
} catch (RejectedExecutionException e) {
    System.out.println("任务被拒绝：" + e.getMessage());
}
```

---

### 2. CallerRunsPolicy（调用者运行策略）

**行为**：由提交任务的线程（调用 `execute` 方法的线程）自己执行该任务。

```java
public static class CallerRunsPolicy implements RejectedExecutionHandler {
    public void rejectedExecution(Runnable r, ThreadPoolExecutor e) {
        if (!e.isShutdown()) {
            r.run();  // 在调用者线程中执行
        }
    }
}
```

**特点**：
- **降低任务提交速度**：调用者线程被阻塞执行任务，无法继续提交新任务
- **不丢弃任务**：保证任务一定会被执行
- **适度降级**：通过牺牲吞吐量来保证任务不丢失

**适用场景**：
- 任务不能丢失，且可以容忍提交速度变慢
- 需要自动调节任务提交速度的场景

**示例**：
```java
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    1, 1, 0L, TimeUnit.SECONDS,
    new SynchronousQueue<>(),  // 不缓存任务
    new ThreadPoolExecutor.CallerRunsPolicy()
);

executor.execute(() -> {
    System.out.println("任务1 - " + Thread.currentThread().getName());
    try { Thread.sleep(2000); } catch (InterruptedException e) {}
});

executor.execute(() -> {
    System.out.println("任务2 - " + Thread.currentThread().getName());
    // 这个任务会在main线程中执行
});
```

---

### 3. DiscardPolicy（丢弃策略）

**行为**：静默丢弃被拒绝的任务，不抛出异常，不做任何处理。

```java
public static class DiscardPolicy implements RejectedExecutionHandler {
    public void rejectedExecution(Runnable r, ThreadPoolExecutor e) {
        // 什么都不做，直接丢弃
    }
}
```

**特点**：
- **无感知丢失**：调用者无法得知任务被丢弃
- **适合允许丢失的场景**：如日志记录、统计类任务

**适用场景**：
- 任务可以丢失，对业务无影响
- 需要保证系统稳定性，宁可丢任务也不能影响主流程

**注意事项**：
- 使用时需要有监控措施，避免大量任务丢失而不自知

---

### 4. DiscardOldestPolicy（丢弃最旧策略）

**行为**：丢弃队列中最早的未处理任务，然后尝试重新提交当前任务。

```java
public static class DiscardOldestPolicy implements RejectedExecutionHandler {
    public void rejectedExecution(Runnable r, ThreadPoolExecutor e) {
        if (!e.isShutdown()) {
            e.getQueue().poll();  // 移除队列头部任务
            e.execute(r);         // 重新尝试提交
        }
    }
}
```

**特点**：
- **优先级反转**：新任务优先于旧任务
- **适合时效性任务**：如实时数据处理，旧数据意义不大

**适用场景**：
- 任务有时效性，新任务更重要
- 队列中的旧任务可以被丢弃

**潜在问题**：
- 可能导致某些任务永远得不到执行（一直被新任务挤掉）
- 结合优先级队列使用时，行为可能不符合预期

---

## 三、自定义拒绝策略

### 示例1：记录日志并告警

```java
public class LogAndAlertPolicy implements RejectedExecutionHandler {
    private static final Logger logger = LoggerFactory.getLogger(LogAndAlertPolicy.class);
    
    @Override
    public void rejectedExecution(Runnable r, ThreadPoolExecutor executor) {
        // 记录日志
        logger.error("任务被拒绝 - 任务: {}, 线程池状态: 活跃线程={}, 队列大小={}, 最大线程数={}",
            r.toString(),
            executor.getActiveCount(),
            executor.getQueue().size(),
            executor.getMaximumPoolSize()
        );
        
        // 发送告警（接入告警系统）
        AlertService.sendAlert("线程池任务被拒绝");
        
        // 可选：将任务持久化到数据库或MQ，后续补偿处理
        TaskRepository.save(r);
    }
}
```

### 示例2：存入备用队列

```java
public class BackupQueuePolicy implements RejectedExecutionHandler {
    private final BlockingQueue<Runnable> backupQueue;
    
    public BackupQueuePolicy(BlockingQueue<Runnable> backupQueue) {
        this.backupQueue = backupQueue;
    }
    
    @Override
    public void rejectedExecution(Runnable r, ThreadPoolExecutor executor) {
        if (!executor.isShutdown()) {
            try {
                // 尝试放入备用队列
                if (!backupQueue.offer(r, 100, TimeUnit.MILLISECONDS)) {
                    // 备用队列也满了，记录日志
                    logger.warn("备用队列也已满，任务丢失: {}", r);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }
}
```

### 示例3：动态调整线程池参数

```java
public class DynamicAdjustPolicy implements RejectedExecutionHandler {
    private final AtomicInteger rejectCount = new AtomicInteger(0);
    
    @Override
    public void rejectedExecution(Runnable r, ThreadPoolExecutor executor) {
        int count = rejectCount.incrementAndGet();
        
        // 连续拒绝10次，尝试扩容
        if (count >= 10 && executor.getMaximumPoolSize() < 100) {
            int newMax = Math.min(executor.getMaximumPoolSize() * 2, 100);
            executor.setMaximumPoolSize(newMax);
            logger.info("线程池扩容至: {}", newMax);
            rejectCount.set(0);
            
            // 重新尝试执行
            executor.execute(r);
        } else {
            // 扩容后仍失败，使用CallerRunsPolicy
            new ThreadPoolExecutor.CallerRunsPolicy()
                .rejectedExecution(r, executor);
        }
    }
}
```

---

## 四、策略对比与选择

| 策略 | 任务丢失 | 异常抛出 | 性能影响 | 适用场景 |
|------|---------|---------|---------|---------|
| **AbortPolicy** | 是 | 是 | 无 | 需要感知任务失败并处理 |
| **CallerRunsPolicy** | 否 | 否 | 中等（阻塞调用者） | 任务不能丢失，可降速 |
| **DiscardPolicy** | 是 | 否 | 无 | 任务可丢失，如日志统计 |
| **DiscardOldestPolicy** | 是（旧任务） | 否 | 无 | 时效性任务，新任务优先 |

---

## 五、实战考量

### 1. 生产环境推荐配置

```java
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    10, 20, 60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000),
    new ThreadFactoryBuilder()
        .setNameFormat("业务线程池-%d")
        .setUncaughtExceptionHandler((t, e) -> 
            logger.error("线程异常", e))
        .build(),
    new CallerRunsPolicy()  // 大多数场景推荐
);
```

### 2. 监控指标

```java
// 定期监控线程池状态
ScheduledExecutorService monitor = Executors.newScheduledThreadPool(1);
monitor.scheduleAtFixedRate(() -> {
    logger.info("线程池监控 - 活跃线程: {}, 队列大小: {}, 完成任务数: {}, 拒绝任务数: {}",
        executor.getActiveCount(),
        executor.getQueue().size(),
        executor.getCompletedTaskCount(),
        ((ThreadPoolExecutor) executor).getRejectedExecutionHandler()
    );
}, 0, 1, TimeUnit.MINUTES);
```

### 3. 注意事项

- **避免无界队列 + AbortPolicy**：任务永远不会触发拒绝策略，可能导致OOM
- **CallerRunsPolicy注意死锁**：如果调用者线程持有锁，任务执行也需要该锁，会死锁
- **自定义策略要考虑线程安全**：多个线程可能同时触发拒绝策略

---

## 六、面试答题总结

**简洁版回答**：

Java线程池有四种内置拒绝策略：

1. **AbortPolicy（默认）**：直接抛出 `RejectedExecutionException` 异常
2. **CallerRunsPolicy**：由调用者线程执行任务，降低提交速度
3. **DiscardPolicy**：静默丢弃任务，不抛异常
4. **DiscardOldestPolicy**：丢弃队列中最旧的任务，重新提交当前任务

**选择建议**：
- 重要任务不能丢失：用 `CallerRunsPolicy`
- 需要感知失败并处理：用 `AbortPolicy` + try-catch
- 任务可丢失（如日志）：用 `DiscardPolicy`
- 时效性任务，新优于旧：用 `DiscardOldestPolicy`

生产环境推荐 `CallerRunsPolicy`，既不丢任务，又能自动调节速度，或者自定义策略记录日志并告警。

