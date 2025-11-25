---
layout: default
title: "如何对多线程进行编排？"
parent: 并发编程
nav_order: 249
description: "深入探讨Java多线程编排的各种方案，包括CompletableFuture、CountDownLatch、CyclicBarrier等工具的使用场景和最佳实践"
date: 2025-11-02
---
## 一、什么是多线程编排

**多线程编排**指的是协调多个异步任务的执行顺序和依赖关系，常见场景包括：
- 串行执行：任务A → 任务B → 任务C
- 并行执行后汇总：任务A、B、C并行，等待全部完成后汇总
- 任一完成即返回：任务A、B、C并行，任一完成即可
- 复杂依赖：任务D依赖A和B，任务E依赖C和D

---

## 二、方案一：CompletableFuture（推荐）

### 1. 串行执行

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    System.out.println("执行任务A");
    return "结果A";
})
.thenApplyAsync(resultA -> {
    System.out.println("执行任务B，依赖：" + resultA);
    return "结果B";
})
.thenApplyAsync(resultB -> {
    System.out.println("执行任务C，依赖：" + resultB);
    return "结果C";
});

String finalResult = future.join();  // 等待完成
System.out.println("最终结果：" + finalResult);
```

**输出**：
```
执行任务A
执行任务B，依赖：结果A
执行任务C，依赖：结果B
最终结果：结果C
```

---

### 2. 并行执行后汇总

#### 方案1：allOf + 收集结果

```java
// 创建多个异步任务
CompletableFuture<String> task1 = CompletableFuture.supplyAsync(() -> {
    sleep(1000);
    return "任务1结果";
});

CompletableFuture<String> task2 = CompletableFuture.supplyAsync(() -> {
    sleep(1500);
    return "任务2结果";
});

CompletableFuture<String> task3 = CompletableFuture.supplyAsync(() -> {
    sleep(800);
    return "任务3结果";
});

// 等待所有任务完成
CompletableFuture<Void> allOf = CompletableFuture.allOf(task1, task2, task3);

// 汇总结果
CompletableFuture<List<String>> allResults = allOf.thenApply(v -> {
    return Arrays.asList(
        task1.join(),
        task2.join(),
        task3.join()
    );
});

List<String> results = allResults.join();
System.out.println("所有结果：" + results);
```

#### 方案2：thenCombine（两个任务组合）

```java
CompletableFuture<String> task1 = CompletableFuture.supplyAsync(() -> "任务1");
CompletableFuture<String> task2 = CompletableFuture.supplyAsync(() -> "任务2");

// 组合两个任务的结果
CompletableFuture<String> combined = task1.thenCombine(task2, (r1, r2) -> {
    return r1 + " + " + r2;
});

System.out.println(combined.join());  // "任务1 + 任务2"
```

#### 方案3：多任务组合（自定义工具）

```java
public class CompletableFutureUtil {
    
    /**
     * 并行执行多个任务并收集结果
     */
    public static <T> CompletableFuture<List<T>> sequence(
        List<CompletableFuture<T>> futures) {
        
        CompletableFuture<Void> allDone = CompletableFuture.allOf(
            futures.toArray(new CompletableFuture[0])
        );
        
        return allDone.thenApply(v ->
            futures.stream()
                .map(CompletableFuture::join)
                .collect(Collectors.toList())
        );
    }
}

// 使用
List<CompletableFuture<String>> tasks = Arrays.asList(
    CompletableFuture.supplyAsync(() -> "任务1"),
    CompletableFuture.supplyAsync(() -> "任务2"),
    CompletableFuture.supplyAsync(() -> "任务3")
);

List<String> results = CompletableFutureUtil.sequence(tasks).join();
System.out.println(results);
```

---

### 3. 任一完成即返回

```java
CompletableFuture<String> task1 = CompletableFuture.supplyAsync(() -> {
    sleep(2000);
    return "任务1";
});

CompletableFuture<String> task2 = CompletableFuture.supplyAsync(() -> {
    sleep(1000);
    return "任务2";
});

CompletableFuture<String> task3 = CompletableFuture.supplyAsync(() -> {
    sleep(1500);
    return "任务3";
});

// 任一完成即返回
CompletableFuture<Object> anyOf = CompletableFuture.anyOf(task1, task2, task3);
System.out.println("最快完成的：" + anyOf.join());  // "任务2"
```

**应用场景**：
- 多个数据源查询，取最快返回的
- 多个算法并行计算，取最快的结果

---

### 4. 复杂依赖编排

```java
/**
 * 场景：电商下单流程
 * 1. 并行查询：用户信息、商品信息
 * 2. 依赖1：计算价格（需要商品信息）
 * 3. 依赖1+2：生成订单（需要用户信息和价格）
 * 4. 依赖3：扣减库存（需要订单信息）
 */
public CompletableFuture<Order> createOrder(Long userId, Long productId) {
    
    // 任务1：查询用户信息
    CompletableFuture<User> userFuture = CompletableFuture.supplyAsync(() -> {
        return userService.getUser(userId);
    });
    
    // 任务2：查询商品信息
    CompletableFuture<Product> productFuture = CompletableFuture.supplyAsync(() -> {
        return productService.getProduct(productId);
    });
    
    // 任务3：计算价格（依赖商品信息）
    CompletableFuture<BigDecimal> priceFuture = productFuture.thenApply(product -> {
        return priceService.calculatePrice(product);
    });
    
    // 任务4：生成订单（依赖用户信息和价格）
    CompletableFuture<Order> orderFuture = userFuture
        .thenCombine(priceFuture, (user, price) -> {
            Order order = new Order();
            order.setUserId(user.getId());
            order.setPrice(price);
            return orderRepository.save(order);
        });
    
    // 任务5：扣减库存（依赖订单）
    CompletableFuture<Order> finalFuture = orderFuture.thenApply(order -> {
        inventoryService.deduct(productId, 1);
        return order;
    });
    
    return finalFuture;
}

// 使用
createOrder(123L, 456L)
    .thenAccept(order -> System.out.println("订单创建成功：" + order))
    .exceptionally(ex -> {
        System.out.println("订单创建失败：" + ex.getMessage());
        return null;
    });
```

---

### 5. 异常处理与重试

```java
public CompletableFuture<String> robustTask() {
    return CompletableFuture.supplyAsync(() -> {
        // 可能失败的任务
        if (Math.random() > 0.7) {
            throw new RuntimeException("任务失败");
        }
        return "成功";
    })
    .exceptionally(ex -> {
        // 异常处理
        log.error("任务失败，使用降级逻辑", ex);
        return "降级结果";
    })
    .thenApply(result -> {
        // 后续处理
        return "处理后的" + result;
    });
}

// 重试机制
public CompletableFuture<String> retryTask(int maxRetries) {
    return CompletableFuture.supplyAsync(() -> {
        return executeWithRetry(maxRetries);
    });
}

private String executeWithRetry(int maxRetries) {
    for (int i = 0; i < maxRetries; i++) {
        try {
            return doTask();
        } catch (Exception e) {
            if (i == maxRetries - 1) {
                throw e;
            }
            sleep(1000 * (i + 1));  // 指数退避
        }
    }
    throw new RuntimeException("重试失败");
}
```

---

## 三、方案二：CountDownLatch

适用于 **主线程等待多个子线程完成** 的场景。

### 基本用法

```java
public void processWithCountDownLatch() throws InterruptedException {
    int taskCount = 3;
    CountDownLatch latch = new CountDownLatch(taskCount);
    ExecutorService executor = Executors.newFixedThreadPool(3);
    
    // 任务1
    executor.execute(() -> {
        try {
            System.out.println("任务1执行");
            Thread.sleep(1000);
        } finally {
            latch.countDown();  // 计数器-1
        }
    });
    
    // 任务2
    executor.execute(() -> {
        try {
            System.out.println("任务2执行");
            Thread.sleep(1500);
        } finally {
            latch.countDown();
        }
    });
    
    // 任务3
    executor.execute(() -> {
        try {
            System.out.println("任务3执行");
            Thread.sleep(800);
        } finally {
            latch.countDown();
        }
    });
    
    // 等待所有任务完成
    latch.await();  // 阻塞直到计数器归零
    System.out.println("所有任务完成");
    
    executor.shutdown();
}
```

### 带超时的等待

```java
boolean finished = latch.await(5, TimeUnit.SECONDS);
if (!finished) {
    System.out.println("超时，部分任务未完成");
}
```

**优点**：
- 简单直观
- 可以设置超时

**缺点**：
- 无法获取任务结果
- 无法处理任务异常
- 一次性使用，不可重置

---

## 四、方案三：CyclicBarrier

适用于 **多个线程相互等待，达到同步点后一起继续** 的场景。

### 基本用法

```java
public void processWithCyclicBarrier() {
    int threadCount = 3;
    CyclicBarrier barrier = new CyclicBarrier(threadCount, () -> {
        System.out.println("所有线程到达屏障，开始汇总");
    });
    
    ExecutorService executor = Executors.newFixedThreadPool(3);
    
    for (int i = 0; i < threadCount; i++) {
        final int taskId = i;
        executor.execute(() -> {
            try {
                System.out.println("任务" + taskId + "准备阶段");
                Thread.sleep(1000);
                
                // 等待其他线程到达
                barrier.await();
                
                System.out.println("任务" + taskId + "继续执行");
            } catch (Exception e) {
                e.printStackTrace();
            }
        });
    }
    
    executor.shutdown();
}
```

### 多阶段任务

```java
public void multiPhaseTask() throws Exception {
    int threadCount = 3;
    CyclicBarrier barrier = new CyclicBarrier(threadCount);
    
    ExecutorService executor = Executors.newFixedThreadPool(3);
    
    for (int i = 0; i < threadCount; i++) {
        final int taskId = i;
        executor.execute(() -> {
            try {
                // 阶段1
                System.out.println("任务" + taskId + " - 阶段1");
                barrier.await();  // 等待所有线程完成阶段1
                
                // 阶段2
                System.out.println("任务" + taskId + " - 阶段2");
                barrier.await();  // 等待所有线程完成阶段2
                
                // 阶段3
                System.out.println("任务" + taskId + " - 阶段3");
                
            } catch (Exception e) {
                e.printStackTrace();
            }
        });
    }
    
    executor.shutdown();
}
```

**优点**：
- 可重复使用（CyclicBarrier可以reset）
- 支持回调（barrierAction）

**缺点**：
- 必须固定数量的线程
- 无法获取任务结果

---

## 五、方案四：Phaser（Java 7+）

Phaser是CyclicBarrier和CountDownLatch的增强版，支持**动态调整参与线程数**。

### 基本用法

```java
public void processWithPhaser() {
    Phaser phaser = new Phaser(1);  // 主线程注册
    ExecutorService executor = Executors.newFixedThreadPool(3);
    
    for (int i = 0; i < 3; i++) {
        final int taskId = i;
        phaser.register();  // 动态注册
        
        executor.execute(() -> {
            try {
                System.out.println("任务" + taskId + "执行");
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            } finally {
                phaser.arriveAndDeregister();  // 完成并注销
            }
        });
    }
    
    phaser.arriveAndAwaitAdvance();  // 等待所有任务完成
    System.out.println("所有任务完成");
    
    executor.shutdown();
}
```

### 多阶段任务

```java
public void multiPhaseWithPhaser() {
    Phaser phaser = new Phaser() {
        @Override
        protected boolean onAdvance(int phase, int registeredParties) {
            System.out.println("阶段" + phase + "完成，参与者：" + registeredParties);
            return phase >= 2;  // 阶段2后终止
        }
    };
    
    phaser.register();  // 主线程注册
    
    for (int i = 0; i < 3; i++) {
        final int taskId = i;
        phaser.register();
        
        new Thread(() -> {
            // 阶段0
            System.out.println("任务" + taskId + " - 阶段0");
            phaser.arriveAndAwaitAdvance();
            
            // 阶段1
            System.out.println("任务" + taskId + " - 阶段1");
            phaser.arriveAndAwaitAdvance();
            
            // 阶段2
            System.out.println("任务" + taskId + " - 阶段2");
            phaser.arriveAndAwaitAdvance();
            
        }).start();
    }
    
    phaser.arriveAndDeregister();  // 主线程完成
}
```

---

## 六、方案五：Future + 队列

适用于 **生产者-消费者** 模型。

```java
public void processWithFuture() throws Exception {
    ExecutorService executor = Executors.newFixedThreadPool(3);
    List<Future<String>> futures = new ArrayList<>();
    
    // 提交任务
    for (int i = 0; i < 10; i++) {
        final int taskId = i;
        Future<String> future = executor.submit(() -> {
            Thread.sleep(1000);
            return "任务" + taskId + "结果";
        });
        futures.add(future);
    }
    
    // 收集结果
    for (Future<String> future : futures) {
        String result = future.get();  // 阻塞等待
        System.out.println(result);
    }
    
    executor.shutdown();
}
```

---

## 七、实战案例：并行查询多个数据源

```java
@Service
public class DataAggregationService {
    
    @Autowired
    private UserService userService;
    
    @Autowired
    private OrderService orderService;
    
    @Autowired
    private ProductService productService;
    
    private final ExecutorService executor = Executors.newFixedThreadPool(10);
    
    /**
     * 聚合用户的完整信息
     */
    public UserDetail aggregateUserDetail(Long userId) {
        // 并行查询多个数据源
        CompletableFuture<User> userFuture = CompletableFuture.supplyAsync(
            () -> userService.getUser(userId), executor
        );
        
        CompletableFuture<List<Order>> ordersFuture = CompletableFuture.supplyAsync(
            () -> orderService.getUserOrders(userId), executor
        );
        
        CompletableFuture<List<Product>> favoritesFuture = CompletableFuture.supplyAsync(
            () -> productService.getUserFavorites(userId), executor
        );
        
        CompletableFuture<Integer> pointsFuture = CompletableFuture.supplyAsync(
            () -> userService.getUserPoints(userId), executor
        );
        
        // 等待所有查询完成
        CompletableFuture<Void> allOf = CompletableFuture.allOf(
            userFuture, ordersFuture, favoritesFuture, pointsFuture
        );
        
        // 汇总结果
        return allOf.thenApply(v -> {
            UserDetail detail = new UserDetail();
            detail.setUser(userFuture.join());
            detail.setOrders(ordersFuture.join());
            detail.setFavorites(favoritesFuture.join());
            detail.setPoints(pointsFuture.join());
            return detail;
        }).join();  // 阻塞等待最终结果
    }
}
```

---

## 八、方案对比

| 方案 | 适用场景 | 可获取结果 | 可处理异常 | 复杂度 | 推荐度 |
|------|---------|----------|----------|--------|--------|
| **CompletableFuture** | 所有异步编排场景 | ✅ | ✅ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **CountDownLatch** | 主线程等待多个子线程 | ❌ | ❌ | ⭐ | ⭐⭐⭐ |
| **CyclicBarrier** | 多线程相互等待 | ❌ | ❌ | ⭐⭐ | ⭐⭐⭐ |
| **Phaser** | 动态参与者的多阶段任务 | ❌ | ❌ | ⭐⭐⭐ | ⭐⭐ |
| **Future** | 简单异步任务 | ✅ | ⚠️ | ⭐ | ⭐⭐ |

---

## 九、面试答题总结

**简洁版回答**：

Java中多线程编排有以下几种主流方案：

**1. CompletableFuture（推荐）**
- **串行**：`thenApply`、`thenCompose`
- **并行汇总**：`allOf` + 收集结果
- **任一完成**：`anyOf`
- **组合**：`thenCombine`（两个任务）
- 支持异常处理（`exceptionally`）和自定义执行器

**2. CountDownLatch**
- 主线程等待多个子线程完成
- 使用 `countDown()` 递减，`await()` 等待
- 一次性使用，无法获取结果

**3. CyclicBarrier**
- 多个线程相互等待，到达同步点后一起继续
- 可重复使用，支持回调
- 适合多阶段任务

**4. Phaser**
- CyclicBarrier的增强版，支持动态调整参与者
- 适合复杂的多阶段协调

**选择建议**：
- **优先使用 CompletableFuture**：功能最强大，支持结果获取和异常处理
- 简单等待场景：CountDownLatch
- 多阶段协调：CyclicBarrier或Phaser
- 复杂依赖关系：CompletableFuture的组合方法

**典型应用**：电商下单流程、数据聚合查询、批量任务处理等。

