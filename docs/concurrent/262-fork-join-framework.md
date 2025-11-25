---
layout: default
title: "如何理解 Fork/Join 框架？"
parent: 并发编程
nav_order: 262
description: "详解Java 7引入的Fork/Join框架，剖析其分治思想与工作窃取（Work-Stealing）算法的核心原理，以及在Parallel Stream中的应用。"
date: 2025-11-19
---
### 1. 核心概念简述

**Fork/Join 框架**是 Java 7 引入的一个用于并行执行任务的框架，其核心思想是**分治法（Divide and Conquer）**：

*   **Fork（分解）**：将一个大任务拆分成若干个互不依赖的小任务。如果小任务还不够小，就继续拆分，直到达到阈值。
*   **Join（合并）**：执行这些小任务，并将它们的结果递归合并，最终得到大任务的结果。

它主要用于加速**CPU 密集型**任务的计算，充分利用多核处理器的优势。

### 2. 原理与源码关键点

Fork/Join 框架主要包含两个核心组件：`ForkJoinPool`（线程池）和 `ForkJoinTask`（任务）。

#### 工作窃取算法 (Work-Stealing Algorithm) —— 核心考点
这是 Fork/Join 框架性能高效的关键。
*   **双端队列**：池中的每个工作线程（Worker Thread）都有自己的双端队列（Deque）。
*   **LIFO（后进先出）**：线程自己产生的任务放在队头，自己取任务也从队头取（类似栈，利用 CPU 缓存局部性）。
*   **Stealing（窃取）**：当一个线程完成了自己队列中的所有任务，它不会闲着，而是随机从其他繁忙线程的队列**队尾**（Tail）“窃取”一个任务来执行。
*   **优势**：充分利用了所有线程的算力，减少了线程间的竞争（自己取队头，别人偷队尾）。

#### 核心类
*   `RecursiveTask<V>`：有返回值的任务。
*   `RecursiveAction`：无返回值的任务。

### 3. 性能与场景考量

1.  **适用场景**：
    *   **CPU 密集型**：如大规模数组排序（Arrays.parallelSort）、图像处理、复杂数据计算。
    *   **不适合 I/O 密集型**：因为工作线程数通常默认为 CPU 核心数，一旦阻塞，整个池的效率会大打折扣。

2.  **Parallel Stream**：
    *   Java 8 的 `parallelStream()` 底层默认使用的就是 `ForkJoinPool.commonPool()`。
    *   **注意**：千万不要在并行流中执行阻塞 I/O 操作，否则会拖垮整个系统的公共线程池，影响其他业务。

### 4. 总结与示例

**回答总结：**
“Fork/Join 是基于分治思想的并行计算框架，核心在于**工作窃取算法**。每个线程维护私有双端队列，空闲线程会从其他线程队列的尾部窃取任务，从而实现负载均衡。它非常适合处理大规模的 CPU 密集型任务，也是 Java 8 并行流的底层实现。”

**代码示例（求和）：**

```java
public class SumTask extends RecursiveTask<Long> {
    private static final int THRESHOLD = 1000; // 拆分阈值
    private long start, end;

    public SumTask(long start, long end) {
        this.start = start;
        this.end = end;
    }

    @Override
    protected Long compute() {
        // 1. 任务足够小，直接计算
        if (end - start <= THRESHOLD) {
            long sum = 0;
            for (long i = start; i <= end; i++) sum += i;
            return sum;
        }
        
        // 2. 任务太大，Fork 拆分
        long mid = (start + end) / 2;
        SumTask leftTask = new SumTask(start, mid);
        SumTask rightTask = new SumTask(mid + 1, end);
        
        // 异步执行子任务
        leftTask.fork();
        rightTask.fork();
        
        // 3. Join 合并结果
        return leftTask.join() + rightTask.join();
    }
}

// 调用
ForkJoinPool pool = new ForkJoinPool();
Long result = pool.invoke(new SumTask(1, 100000));
```
