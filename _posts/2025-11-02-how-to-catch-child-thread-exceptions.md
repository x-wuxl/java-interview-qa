---
layout: post
title: "如何实现主线程捕获子线程异常？"
date: 2025-11-02
description: "总结主线程捕获子线程异常的5种实现方案，包括UncaughtExceptionHandler、Future、CompletableFuture等"
author: "wuxl"
categories: [并发编程]
tags: [异常处理, 多线程, Future, UncaughtExceptionHandler, CompletableFuture]
---

## 问题

如何实现主线程捕获子线程异常？

## 答案

### 核心思路

由于异常无法跨线程传播，需要通过**中间机制**将子线程的异常传递给主线程。常见方案：
1. 在子线程内部捕获异常，通过共享变量传递
2. 使用UncaughtExceptionHandler捕获未捕获异常
3. 使用Future.get()获取异常
4. 使用CompletableFuture的异常处理机制
5. 使用线程池的afterExecute钩子

### 方案一：共享变量传递异常

**原理**：子线程捕获异常后存储到共享变量，主线程读取。

```java
public class SharedVariableDemo {
    // 使用volatile保证可见性
    private static volatile Exception exception = null;

    public static void main(String[] args) throws InterruptedException {
        Thread thread = new Thread(() -> {
            try {
                int result = 10 / 0;
            } catch (Exception e) {
                exception = e;  // 存储异常
            }
        });

        thread.start();
        thread.join();  // 等待子线程结束

        // 主线程检查异常
        if (exception != null) {
            System.out.println("捕获到子线程异常: " + exception.getMessage());
            exception.printStackTrace();
        }
    }
}
```

**优点**：
- 简单直接，容易理解

**缺点**：
- 需要手动管理共享变量，容易出错
- 多线程场景下需要使用ConcurrentHashMap存储每个线程的异常
- 必须调用join()等待线程结束

### 方案二：UncaughtExceptionHandler（推荐）

**原理**：为线程设置异常处理器，当线程抛出未捕获异常时自动回调。

#### 2.1 线程实例级别的Handler

```java
public class UncaughtExceptionHandlerDemo {
    public static void main(String[] args) throws InterruptedException {
        // 用于存储异常的容器
        final Exception[] exceptionHolder = new Exception[1];
        final CountDownLatch latch = new CountDownLatch(1);

        Thread thread = new Thread(() -> {
            int result = 10 / 0;  // 抛出异常
        });

        // 设置异常处理器
        thread.setUncaughtExceptionHandler((t, e) -> {
            System.out.println("线程 " + t.getName() + " 抛出异常");
            exceptionHolder[0] = (Exception) e;
            latch.countDown();
        });

        thread.start();
        latch.await();  // 等待异常处理完成

        // 主线程处理异常
        if (exceptionHolder[0] != null) {
            System.out.println("主线程捕获到异常: " + exceptionHolder[0].getMessage());
        }
    }
}

// 输出：
// 线程 Thread-0 抛出异常
// 主线程捕获到异常: / by zero
```

#### 2.2 全局默认Handler

```java
public class GlobalExceptionHandler {
    public static void main(String[] args) {
        // 设置全局默认异常处理器
        Thread.setDefaultUncaughtExceptionHandler((t, e) -> {
            System.err.println("全局捕获异常: " + t.getName());
            e.printStackTrace();
            // 可以记录日志、发送告警等
        });

        new Thread(() -> {
            throw new RuntimeException("子线程异常");
        }).start();

        new Thread(() -> {
            int result = 10 / 0;
        }).start();
    }
}
```

**优点**：
- 无需修改业务代码，统一处理未捕获异常
- 适合全局日志记录、监控告警

**缺点**：
- 只能捕获**未捕获的异常**（如果子线程内部已经catch，则不会触发）
- 无法获取返回值

### 方案三：Future.get()（推荐）

**原理**：使用线程池的submit()方法，返回Future对象，通过get()获取异常。

```java
public class FutureExceptionDemo {
    public static void main(String[] args) {
        ExecutorService executor = Executors.newFixedThreadPool(1);

        // 提交Callable任务
        Future<Integer> future = executor.submit(() -> {
            System.out.println("子线程开始执行");
            int result = 10 / 0;  // 抛出异常
            return result;
        });

        try {
            // 调用get()会重新抛出异常（包装为ExecutionException）
            Integer result = future.get();
        } catch (ExecutionException e) {
            System.out.println("捕获到子线程异常: " + e.getCause().getMessage());
            e.getCause().printStackTrace();
        } catch (InterruptedException e) {
            e.printStackTrace();
        } finally {
            executor.shutdown();
        }
    }
}

// 输出：
// 子线程开始执行
// 捕获到子线程异常: / by zero
// java.lang.ArithmeticException: / by zero
```

**源码分析**：

```java
// FutureTask.get()源码（简化）
public V get() throws InterruptedException, ExecutionException {
    int s = state;
    if (s <= COMPLETING)
        s = awaitDone(false, 0L);  // 等待任务完成
    return report(s);
}

private V report(int s) throws ExecutionException {
    Object x = outcome;
    if (s == NORMAL)
        return (V)x;  // 正常返回结果
    if (s >= CANCELLED)
        throw new CancellationException();
    throw new ExecutionException((Throwable)x);  // 抛出包装后的异常
}
```

**优点**：
- 标准API，使用简单
- 同时支持获取返回值和异常
- 适合需要等待任务结果的场景

**缺点**：
- 必须使用线程池（不适合new Thread()场景）
- get()是阻塞调用，可能影响性能

### 方案四：CompletableFuture（现代化方案）

**原理**：使用CompletableFuture的异步编程模型，支持链式异常处理。

```java
public class CompletableFutureExceptionDemo {
    public static void main(String[] args) throws InterruptedException {
        CompletableFuture<Integer> future = CompletableFuture.supplyAsync(() -> {
            System.out.println("子线程执行中...");
            int result = 10 / 0;  // 抛出异常
            return result;
        });

        // 方式1: exceptionally处理异常
        future.exceptionally(ex -> {
            System.out.println("捕获到异常: " + ex.getMessage());
            return null;  // 返回默认值
        });

        // 方式2: handle同时处理正常结果和异常
        future.handle((result, ex) -> {
            if (ex != null) {
                System.out.println("异常处理: " + ex.getCause().getMessage());
                return -1;
            }
            return result;
        });

        // 方式3: whenComplete观察结果（不改变结果）
        future.whenComplete((result, ex) -> {
            if (ex != null) {
                System.out.println("任务失败: " + ex.getMessage());
            } else {
                System.out.println("任务成功: " + result);
            }
        });

        Thread.sleep(1000);  // 等待异步任务完成
    }
}
```

**高级用法：组合多个任务**

```java
public class CompletableFutureChainDemo {
    public static void main(String[] args) {
        CompletableFuture.supplyAsync(() -> {
            // 任务1
            return getUserId();
        }).thenApply(userId -> {
            // 任务2
            return queryUserInfo(userId);
        }).thenAccept(userInfo -> {
            // 任务3
            System.out.println("用户信息: " + userInfo);
        }).exceptionally(ex -> {
            // 统一异常处理（任何一个任务失败都会触发）
            System.err.println("任务链执行失败: " + ex.getMessage());
            return null;
        });
    }
}
```

**优点**：
- 支持链式调用，代码简洁
- 支持异步非阻塞，性能更好
- 提供丰富的异常处理API（exceptionally、handle、whenComplete）
- 支持多任务组合（thenCompose、thenCombine等）

**缺点**：
- JDK8+才支持
- 学习曲线稍高

### 方案五：线程池afterExecute钩子

**原理**：重写ThreadPoolExecutor的afterExecute方法，在任务执行后检查异常。

```java
public class ThreadPoolHookDemo {
    public static void main(String[] args) {
        ThreadPoolExecutor executor = new ThreadPoolExecutor(
            2, 2, 0L, TimeUnit.MILLISECONDS,
            new LinkedBlockingQueue<>()
        ) {
            @Override
            protected void afterExecute(Runnable r, Throwable t) {
                super.afterExecute(r, t);

                // execute()提交的任务，异常在t参数中
                if (t != null) {
                    System.out.println("捕获到异常(execute): " + t.getMessage());
                }

                // submit()提交的任务，异常封装在FutureTask中
                if (r instanceof FutureTask) {
                    try {
                        ((FutureTask<?>) r).get();
                    } catch (ExecutionException e) {
                        System.out.println("捕获到异常(submit): " + e.getCause().getMessage());
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                }
            }
        };

        // 测试execute()
        executor.execute(() -> {
            int result = 10 / 0;
        });

        // 测试submit()
        executor.submit(() -> {
            throw new RuntimeException("submit任务异常");
        });

        executor.shutdown();
    }
}
```

**优点**：
- 统一处理线程池中所有任务的异常
- 适合监控、日志记录场景

**缺点**：
- 需要自定义线程池
- 无法直接传递异常给特定的调用者

### 方案对比

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **共享变量** | 简单场景 | 实现简单 | 需要手动管理，易出错 |
| **UncaughtExceptionHandler** | 全局异常处理 | 无侵入性，适合监控 | 只能捕获未捕获异常 |
| **Future.get()** | 需要返回值的任务 | 标准API，简单可靠 | 阻塞调用，需要线程池 |
| **CompletableFuture** | 异步编程 | 功能强大，非阻塞 | 学习曲线高 |
| **afterExecute** | 线程池监控 | 统一处理 | 需要自定义线程池 |

### 实战案例：批量任务异常收集

```java
public class BatchTaskExceptionCollector {
    public static void main(String[] args) throws InterruptedException {
        ExecutorService executor = Executors.newFixedThreadPool(5);
        List<Future<String>> futures = new ArrayList<>();

        // 提交10个任务
        for (int i = 0; i < 10; i++) {
            int taskId = i;
            Future<String> future = executor.submit(() -> {
                if (taskId % 3 == 0) {
                    throw new RuntimeException("任务" + taskId + "失败");
                }
                return "任务" + taskId + "成功";
            });
            futures.add(future);
        }

        // 收集结果和异常
        List<String> results = new ArrayList<>();
        List<Exception> exceptions = new ArrayList<>();

        for (int i = 0; i < futures.size(); i++) {
            try {
                String result = futures.get(i).get();
                results.add(result);
            } catch (ExecutionException e) {
                exceptions.add((Exception) e.getCause());
                System.err.println("任务" + i + "异常: " + e.getCause().getMessage());
            }
        }

        System.out.println("成功: " + results.size() + ", 失败: " + exceptions.size());
        executor.shutdown();
    }
}
```

### 最佳实践

| 场景 | 推荐方案 |
|------|---------|
| **需要任务返回值** | Future.get() 或 CompletableFuture |
| **全局异常监控** | setDefaultUncaughtExceptionHandler |
| **线程池任务监控** | 重写afterExecute |
| **异步非阻塞** | CompletableFuture |
| **简单场景** | 子线程内部try-catch + 共享变量 |

### 面试答题要点

1. **核心思路**：异常无法跨线程传播，需通过中间机制传递（共享变量、回调、Future等）
2. **推荐方案**：线程池场景用Future.get()或CompletableFuture，全局监控用UncaughtExceptionHandler
3. **Future原理**：submit()返回FutureTask，异常被捕获并存储，get()时重新抛出ExecutionException
4. **注意区分**：execute()异常直接打印，submit()异常封装在Future中
5. **现代化方案**：CompletableFuture提供更强大的异步异常处理能力，支持链式调用
