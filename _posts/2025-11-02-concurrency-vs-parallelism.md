---
layout: post
title: "什么是并发，什么是并行？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [并发, 并行, Concurrency, Parallelism]
description: "深入理解并发和并行的概念、区别及其在实际编程中的应用"
---

## 核心概念

### 并发（Concurrency）

**并发** 是指在**同一时间段内**，多个任务交替执行，看起来像是同时进行。核心在于**任务的调度和切换**。

**比喻**：一个厨师在多个灶台之间切换做菜，虽然同时只能操作一个灶台，但通过快速切换，看起来是在同时做多道菜。

### 并行（Parallelism）

**并行** 是指在**同一时刻**，多个任务真正同时执行。核心在于**多个执行单元同时工作**。

**比喻**：多个厨师同时在各自的灶台上做菜，真正实现了同时进行。

---

## 核心区别

| 维度 | 并发（Concurrency） | 并行（Parallelism） |
|------|-------------------|-------------------|
| **定义** | 同一时间段内交替执行 | 同一时刻同时执行 |
| **硬件要求** | 单核或多核均可 | 必须是多核/多处理器 |
| **执行方式** | 时间片轮转，任务切换 | 多个任务真正同时运行 |
| **目标** | 提高系统吞吐量和响应性 | 提高计算速度 |
| **关注点** | 任务调度、资源竞争 | 任务分解、负载均衡 |
| **编程模型** | 线程、协程、异步 | 多线程、多进程、分布式 |

---

## 详细对比

### 1. 单核CPU上的并发

```java
// 单核CPU上的并发示例
public class ConcurrencyOnSingleCore {
    public static void main(String[] args) {
        // 创建两个线程
        Thread t1 = new Thread(() -> {
            for (int i = 0; i < 5; i++) {
                System.out.println("任务1-" + i);
            }
        });
        
        Thread t2 = new Thread(() -> {
            for (int i = 0; i < 5; i++) {
                System.out.println("任务2-" + i);
            }
        });
        
        t1.start();
        t2.start();
    }
}

// 可能的输出（任务交替执行）：
// 任务1-0
// 任务2-0
// 任务1-1
// 任务2-1
// 任务1-2
// ...
```

**特点**：
- 虽然创建了两个线程，但在单核CPU上只能交替执行
- CPU通过时间片轮转，快速切换两个任务
- **并发但不并行**

### 2. 多核CPU上的并行

```java
// 多核CPU上的并行示例
public class ParallelismOnMultiCore {
    public static void main(String[] args) {
        // 使用并行流
        List<Integer> numbers = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8);
        
        // 并行计算
        int sum = numbers.parallelStream()
                        .mapToInt(n -> {
                            System.out.println(Thread.currentThread().getName() 
                                             + " processing " + n);
                            return n * n;
                        })
                        .sum();
        
        System.out.println("Sum: " + sum);
    }
}

// 可能的输出（多个线程真正同时执行）：
// ForkJoinPool-1-worker-1 processing 5
// ForkJoinPool-1-worker-2 processing 3
// ForkJoinPool-1-worker-3 processing 7
// ForkJoinPool-1-worker-4 processing 1
// ...
```

**特点**：
- 多个CPU核心真正同时处理不同的数据
- 不需要任务切换（在同一时刻）
- **既并发又并行**

### 3. 图示对比

```
【并发 - 单核CPU】
时间 →
CPU: [任务A] [任务B] [任务A] [任务B] [任务A] [任务B]
     |--时间片--|--时间片--|--时间片--|

【并行 - 多核CPU】
时间 →
CPU1: [任务A] [任务A] [任务A] [任务A]
CPU2: [任务B] [任务B] [任务B] [任务B]
      ↑ 同一时刻，两个任务真正同时执行
```

---

## 实际应用场景

### 场景1：Web服务器（并发）

```java
// Web服务器处理并发请求
public class WebServer {
    private final ExecutorService executor = Executors.newFixedThreadPool(100);
    
    public void handleRequest(Request request) {
        // 将请求提交到线程池
        executor.submit(() -> {
            processRequest(request);
        });
    }
    
    private void processRequest(Request request) {
        // 处理请求：查询数据库、调用API等
        // 即使在单核上，通过I/O等待时切换，也能提高吞吐量
    }
}
```

**特点**：
- 主要利用**并发**处理大量请求
- 即使在单核上，由于大量I/O等待，并发也能显著提高吞吐量
- **目标**：提高系统响应性和吞吐量

### 场景2：大数据处理（并行）

```java
// 大数据并行处理
public class BigDataProcessing {
    public void processLargeDataset() {
        List<String> dataset = loadLargeDataset(); // 假设有1000万条数据
        
        // 使用并行流处理
        Map<String, Long> result = dataset.parallelStream()
            .filter(s -> s.length() > 10)
            .map(String::toLowerCase)
            .collect(Collectors.groupingBy(
                s -> s.substring(0, 1),
                Collectors.counting()
            ));
    }
}
```

**特点**：
- 主要利用**并行**加速计算
- 数据可以独立处理，适合分配到多个CPU核心
- **目标**：缩短计算时间

### 场景3：图形渲染（并行）

```java
// 图像并行处理
public class ImageProcessor {
    public BufferedImage processImage(BufferedImage input) {
        int width = input.getWidth();
        int height = input.getHeight();
        BufferedImage output = new BufferedImage(width, height, input.getType());
        
        // 将图像分块并行处理
        IntStream.range(0, height).parallel().forEach(y -> {
            for (int x = 0; x < width; x++) {
                int rgb = input.getRGB(x, y);
                // 处理像素（如滤镜效果）
                int processed = applyFilter(rgb);
                output.setRGB(x, y, processed);
            }
        });
        
        return output;
    }
    
    private int applyFilter(int rgb) {
        // 像素处理逻辑
        return rgb;
    }
}
```

**特点**：
- 每个像素独立处理，天然适合并行
- 充分利用多核CPU的计算能力

### 场景4：消息队列（并发）

```java
// 消息队列消费者
public class MessageConsumer {
    private final BlockingQueue<Message> queue = new LinkedBlockingQueue<>();
    
    // 生产者线程
    public void produce(Message msg) {
        queue.offer(msg);
    }
    
    // 多个消费者线程并发消费
    public void startConsumers(int consumerCount) {
        for (int i = 0; i < consumerCount; i++) {
            new Thread(() -> {
                while (true) {
                    try {
                        Message msg = queue.take();
                        processMessage(msg);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                }
            }).start();
        }
    }
    
    private void processMessage(Message msg) {
        // 处理消息
    }
}
```

**特点**：
- 多个消费者并发处理消息
- 即使在单核上，利用I/O等待时间也能提高效率

---

## 编程模型对比

### 1. 并发编程

```java
// 并发：关注任务调度和资源竞争
public class ConcurrentCounter {
    private int count = 0;
    private final Object lock = new Object();
    
    public void increment() {
        synchronized (lock) {  // 同步机制处理竞争
            count++;
        }
    }
    
    public int getCount() {
        synchronized (lock) {
            return count;
        }
    }
}
```

**关注点**：
- 线程安全（synchronized、Lock）
- 死锁避免
- 资源竞争
- 任务调度

### 2. 并行编程

```java
// 并行：关注任务分解和结果合并
public class ParallelSum {
    public long calculateSum(List<Integer> numbers) {
        // Fork/Join框架实现并行计算
        return numbers.parallelStream()
                     .mapToLong(Integer::longValue)
                     .sum();
    }
    
    // 或使用ForkJoinPool
    public long calculateSumWithForkJoin(int[] array) {
        return new SumTask(array, 0, array.length).compute();
    }
    
    static class SumTask extends RecursiveTask<Long> {
        private final int[] array;
        private final int start, end;
        private static final int THRESHOLD = 1000;
        
        SumTask(int[] array, int start, int end) {
            this.array = array;
            this.start = start;
            this.end = end;
        }
        
        @Override
        protected Long compute() {
            if (end - start <= THRESHOLD) {
                // 直接计算
                long sum = 0;
                for (int i = start; i < end; i++) {
                    sum += array[i];
                }
                return sum;
            } else {
                // 分解任务
                int mid = (start + end) / 2;
                SumTask left = new SumTask(array, start, mid);
                SumTask right = new SumTask(array, mid, end);
                
                left.fork();  // 异步执行左半部分
                long rightResult = right.compute();  // 执行右半部分
                long leftResult = left.join();  // 等待左半部分结果
                
                return leftResult + rightResult;
            }
        }
    }
}
```

**关注点**：
- 任务分解（Divide and Conquer）
- 数据分区
- 负载均衡
- 结果合并

---

## 并发不等于并行

### 示例1：异步I/O（并发但非并行）

```java
// 异步I/O：并发处理多个I/O操作
public class AsyncIOExample {
    public CompletableFuture<String> fetchData(String url) {
        return CompletableFuture.supplyAsync(() -> {
            // 发起HTTP请求
            return httpGet(url);  // I/O阻塞时，线程可以处理其他任务
        });
    }
    
    public void fetchMultipleUrls() {
        List<String> urls = Arrays.asList("url1", "url2", "url3");
        
        // 并发发起多个请求
        List<CompletableFuture<String>> futures = urls.stream()
            .map(this::fetchData)
            .collect(Collectors.toList());
        
        // 等待所有请求完成
        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
    }
}
```

**特点**：
- 多个任务并发执行（交替进行）
- 利用I/O等待时间，提高吞吐量
- 即使在单核上也有效

### 示例2：CPU密集型任务（需要并行）

```java
// CPU密集型：需要真正的并行
public class CpuIntensiveTask {
    // 计算斐波那契数列（CPU密集）
    public long fibonacci(int n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
    
    public void computeMultipleFibonacci() {
        List<Integer> inputs = Arrays.asList(40, 41, 42, 43);
        
        // ❌ 单线程：慢
        inputs.forEach(n -> {
            long result = fibonacci(n);
            System.out.println("fib(" + n + ") = " + result);
        });
        
        // ✅ 并行：快（需要多核CPU）
        inputs.parallelStream().forEach(n -> {
            long result = fibonacci(n);
            System.out.println("fib(" + n + ") = " + result);
        });
    }
}
```

**特点**：
- CPU密集型任务，并发（单核）效果有限
- 需要真正的并行（多核）才能加速

---

## Java中的并发与并行工具

### 并发工具

```java
// 1. synchronized
public synchronized void method() { }

// 2. Lock
private final Lock lock = new ReentrantLock();

// 3. 线程池
ExecutorService executor = Executors.newFixedThreadPool(10);

// 4. 并发集合
ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>();

// 5. 原子类
AtomicInteger counter = new AtomicInteger(0);
```

### 并行工具

```java
// 1. 并行流
list.parallelStream().map(...).collect(...);

// 2. ForkJoinPool
ForkJoinPool pool = new ForkJoinPool();
pool.invoke(new RecursiveTask<>() { ... });

// 3. CompletableFuture并行组合
CompletableFuture.allOf(cf1, cf2, cf3).join();

// 4. Parallel Collector（JDK 12+）
Collectors.teeing(...);
```

---

## 面试总结

### 核心要点

1. **并发**：任务交替执行，关注调度和资源竞争
2. **并行**：任务同时执行，关注计算加速
3. **区别**：并发是逻辑概念，并行是物理概念
4. **联系**：并行是并发的子集，并行一定并发，并发不一定并行

### 答题模板

**简明版**：
- 并发是多个任务交替执行，可以在单核上实现
- 并行是多个任务同时执行，需要多核CPU
- 并发关注任务调度，并行关注计算加速

**完整版**：
1. **定义对比**：
   - 并发：同一时间段内，多个任务交替执行
   - 并行：同一时刻，多个任务真正同时执行

2. **硬件要求**：
   - 并发：单核或多核
   - 并行：必须多核

3. **应用场景**：
   - 并发：Web服务器、消息队列（I/O密集）
   - 并行：大数据处理、图形渲染（CPU密集）

4. **编程关注点**：
   - 并发：线程安全、死锁、资源竞争
   - 并行：任务分解、负载均衡、结果合并

5. **Java工具**：
   - 并发：synchronized、Lock、线程池
   - 并行：parallelStream、ForkJoinPool

### 经典比喻

```
【并发】
一个厨师（单核CPU）在三个灶台之间快速切换
→ 看起来同时在做三道菜
→ 实际上是快速交替

【并行】
三个厨师（多核CPU）各自在自己的灶台上做菜
→ 真正同时在做三道菜
→ 实际上是同时进行
```

### 记忆口诀

```
并发关调度，并行求速度
单核能并发，多核才并行
I/O用并发，CPU用并行
并发是概念，并行是实现
```

