---
layout: default
title: "线程是如何被调度的？"
parent: 并发编程
nav_order: 179
description: "深入理解Java线程调度机制，包括操作系统调度算法、JVM线程映射、优先级策略，以及抢占式调度与协作式调度的区别。"
date: 2025-11-02
---
## 核心概念

**线程调度**是指操作系统决定哪个线程获得CPU执行权的过程。Java线程调度采用**抢占式调度（Preemptive Scheduling）**，由操作系统内核负责。

```
就绪队列: [线程A, 线程B, 线程C]
            ↓
       调度器选择
            ↓
         线程A → CPU执行
```

**关键特点**：
- **抢占式**：高优先级线程可以抢占低优先级线程
- **时间片轮转**：相同优先级线程轮流执行
- **操作系统控制**：JVM无法直接控制调度顺序

## 线程调度模型

### 1. 抢占式调度 vs 协作式调度

| 特性 | 抢占式调度 | 协作式调度 |
|------|-----------|-----------|
| **控制权** | 操作系统 | 线程自己 |
| **切换时机** | 随时可能被抢占 | 主动让出CPU |
| **公平性** | 较好 | 依赖线程配合 |
| **实现难度** | 内核级支持 | 应用级实现 |
| **现代系统** | ✅ 主流 | ❌ 已淘汰 |

#### 抢占式调度示例

```java
public class PreemptiveDemo {
    public static void main(String[] args) {
        Thread lowPriority = new Thread(() -> {
            while (true) {
                System.out.println("低优先级线程执行");
            }
        });
        lowPriority.setPriority(Thread.MIN_PRIORITY); // 优先级1

        Thread highPriority = new Thread(() -> {
            while (true) {
                System.out.println("高优先级线程执行");
            }
        });
        highPriority.setPriority(Thread.MAX_PRIORITY); // 优先级10

        lowPriority.start();
        highPriority.start();
        
        // 高优先级线程会抢占低优先级线程的CPU时间
    }
}
```

#### 协作式调度示例（模拟）

```java
public class CooperativeDemo {
    public static void main(String[] args) {
        Thread thread1 = new Thread(() -> {
            for (int i = 0; i < 5; i++) {
                System.out.println("线程1执行: " + i);
                Thread.yield(); // 主动让出CPU
            }
        });

        Thread thread2 = new Thread(() -> {
            for (int i = 0; i < 5; i++) {
                System.out.println("线程2执行: " + i);
                Thread.yield(); // 主动让出CPU
            }
        });

        thread1.start();
        thread2.start();
    }
}
```

### 2. Java线程与操作系统线程的映射

```
┌─────────────────────┐
│   Java Thread       │ 
│  (用户态)            │
└──────────┬──────────┘
           │ 1:1映射
           ▼
┌─────────────────────┐
│   Native Thread     │
│  (内核态)            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   CPU Core          │
└─────────────────────┘
```

**HotSpot JVM**：
- **1:1映射**：一个Java线程对应一个操作系统线程
- **内核级线程**：由操作系统调度，JVM无法直接控制
- **平台依赖**：调度行为依赖具体操作系统

**注意**：Java 19+引入的虚拟线程（Virtual Thread）采用M:N映射，多个虚拟线程映射到少量平台线程。

## 操作系统调度算法

### 1. 时间片轮转（Round-Robin）

```
时间: 0ms    10ms   20ms   30ms   40ms   50ms
     [线程A] [线程B] [线程C] [线程A] [线程B] [线程C]
       ↑________________|  每10ms切换一次
```

**特点**：
- 相同优先级线程轮流执行
- 时间片典型值：10-100ms（Linux默认约6ms）
- 保证公平性

**Java代码验证**：

```java
public class RoundRobinDemo {
    public static void main(String[] args) {
        for (int i = 0; i < 3; i++) {
            int threadNum = i;
            new Thread(() -> {
                long startTime = System.currentTimeMillis();
                int count = 0;
                
                // 持续执行1秒
                while (System.currentTimeMillis() - startTime < 1000) {
                    count++;
                }
                
                System.out.printf("线程%d 执行次数: %d%n", threadNum, count);
            }).start();
        }
    }
}
```

**输出示例**：
```
线程0 执行次数: 150000000
线程1 执行次数: 149000000  // 相近的值，说明轮转调度
线程2 执行次数: 151000000
```

### 2. 优先级调度（Priority Scheduling）

```java
public class PrioritySchedulingDemo {
    public static void main(String[] args) throws InterruptedException {
        Thread low = new Thread(() -> {
            int count = 0;
            while (!Thread.currentThread().isInterrupted()) {
                count++;
            }
            System.out.println("低优先级执行次数: " + count);
        });
        low.setPriority(Thread.MIN_PRIORITY); // 1

        Thread high = new Thread(() -> {
            int count = 0;
            while (!Thread.currentThread().isInterrupted()) {
                count++;
            }
            System.out.println("高优先级执行次数: " + count);
        });
        high.setPriority(Thread.MAX_PRIORITY); // 10

        low.start();
        high.start();

        Thread.sleep(1000);
        low.interrupt();
        high.interrupt();
    }
}
```

**典型输出**（Linux）：
```
低优先级执行次数: 50000000
高优先级执行次数: 150000000  // 高优先级获得更多CPU时间
```

**注意**：
- Windows基本忽略Java线程优先级
- Linux会参考优先级，但不保证严格执行
- **不要依赖优先级做核心业务逻辑**

### 3. 多级反馈队列（Multilevel Feedback Queue）

```
高优先级队列（时间片10ms）
    ↓ 未完成
中优先级队列（时间片20ms）
    ↓ 未完成
低优先级队列（时间片40ms）
    ↓ 未完成
   继续轮转
```

**特点**：
- 新线程从高优先级队列开始
- CPU密集型线程逐渐降级
- I/O密集型线程保持高优先级

## Java线程优先级

### 1. 优先级定义

```java
public class Thread {
    public final static int MIN_PRIORITY = 1;   // 最低优先级
    public final static int NORM_PRIORITY = 5;  // 默认优先级
    public final static int MAX_PRIORITY = 10;  // 最高优先级
}
```

### 2. 设置与获取优先级

```java
public class ThreadPriorityDemo {
    public static void main(String[] args) {
        Thread thread = new Thread(() -> {
            System.out.println("线程执行");
        });
        
        // 设置优先级（必须在start()前）
        thread.setPriority(Thread.MAX_PRIORITY);
        
        // 获取优先级
        int priority = thread.getPriority();
        System.out.println("线程优先级: " + priority);
        
        thread.start();
    }
}
```

### 3. 优先级继承

```java
public class PriorityInheritanceDemo {
    public static void main(String[] args) {
        Thread parent = Thread.currentThread();
        parent.setPriority(8);
        
        Thread child = new Thread(() -> {
            // 子线程继承父线程的优先级
            System.out.println("子线程优先级: " + Thread.currentThread().getPriority());
        });
        
        child.start(); // 输出: 子线程优先级: 8
    }
}
```

### 4. 优先级陷阱

```java
// ❌ 依赖优先级控制执行顺序（不可靠）
public class UnreliablePriority {
    private static int count = 0;

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new Thread(() -> {
            for (int i = 0; i < 100; i++) {
                count++;
            }
        });
        t1.setPriority(Thread.MAX_PRIORITY);

        Thread t2 = new Thread(() -> {
            for (int i = 0; i < 100; i++) {
                count++;
            }
        });
        t2.setPriority(Thread.MIN_PRIORITY);

        t1.start();
        t2.start();
        t1.join();
        t2.join();

        // ❌ 不能保证t1一定先执行完
        System.out.println("count: " + count);
    }
}

// ✅ 使用同步机制控制顺序
public class ReliableOrdering {
    private static int count = 0;
    private static final Object lock = new Object();

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new Thread(() -> {
            synchronized (lock) {
                for (int i = 0; i < 100; i++) {
                    count++;
                }
            }
        });

        Thread t2 = new Thread(() -> {
            synchronized (lock) {
                for (int i = 0; i < 100; i++) {
                    count++;
                }
            }
        });

        t1.start();
        t2.start();
        t1.join();
        t2.join();

        // ✅ 保证线程安全
        System.out.println("count: " + count);
    }
}
```

## 不同平台的调度差异

### 1. Linux（CFS调度器）

```
完全公平调度器（Completely Fair Scheduler）
- 基于虚拟运行时间（vruntime）
- 优先级转换为权重（weight）
- 使用红黑树管理就绪队列
```

**特点**：
- 部分尊重Java线程优先级
- 时间片动态调整
- 优先级影响相对较小

### 2. Windows（抢占式多级调度）

```
Windows线程优先级
- 32个优先级等级（0-31）
- Java优先级映射到7个级别
- 严格的优先级抢占
```

**特点**：
- 基本忽略Java线程优先级差异
- 优先级影响极小
- 依赖时间片轮转

### 3. macOS（Mach调度）

```
Mach微内核调度
- 基于优先级的时间片轮转
- 动态优先级调整
```

**特点**：
- 部分参考Java优先级
- 调度行为介于Linux和Windows之间

## 线程状态与调度的关系

```
NEW → start() → RUNNABLE ──────┐
                 ↑             │
                 │  调度选中    │ 时间片用完/yield
                 │             ↓
              就绪队列 ← [调度器]
                 ↑
                 │ notify/unlock/超时
                 │
         BLOCKED/WAITING/TIMED_WAITING
```

**调度器只调度RUNNABLE状态的线程**：
- `BLOCKED`：等待锁，不参与调度
- `WAITING`：等待通知，不参与调度
- `TIMED_WAITING`：超时等待，不参与调度

## 调度优化策略

### 1. CPU亲和性（Affinity）

```java
// Linux：绑定线程到特定CPU核心（需要JNI）
public class CpuAffinity {
    static {
        System.loadLibrary("affinity");
    }

    // 将当前线程绑定到CPU核心0
    public native void setCpuAffinity(int cpuId);
}
```

**优势**：
- 减少线程迁移
- 提升CPU缓存命中率
- 降低上下文切换开销

### 2. NUMA感知调度

```java
// 在NUMA架构上，尽量让线程访问本地内存
// 需要操作系统和JVM支持
// JVM参数：-XX:+UseNUMA
```

### 3. 虚拟线程（Java 19+）

```java
// 虚拟线程由JVM调度，避免内核级切换
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    for (int i = 0; i < 100000; i++) {
        executor.submit(() -> {
            // 虚拟线程任务
            Thread.sleep(1000);
            return "result";
        });
    }
}
```

**优势**：
- 百万级并发
- 用户态调度，无内核开销
- 自动协作式调度

## 监控线程调度

### 1. JMX监控

```java
public class ThreadSchedulingMonitor {
    public static void main(String[] args) {
        ThreadMXBean threadMXBean = ManagementFactory.getThreadMXBean();
        
        for (long threadId : threadMXBean.getAllThreadIds()) {
            ThreadInfo info = threadMXBean.getThreadInfo(threadId);
            if (info != null) {
                System.out.printf("Thread: %s%n", info.getThreadName());
                System.out.printf("  State: %s%n", info.getThreadState());
                System.out.printf("  CPU Time: %d ns%n", 
                    threadMXBean.getThreadCpuTime(threadId));
                System.out.printf("  Blocked Count: %d%n", info.getBlockedCount());
            }
        }
    }
}
```

### 2. Linux系统监控

```bash
# 查看线程调度信息
ps -eLo pid,tid,pri,nice,comm | grep java

# 查看线程CPU使用率
top -H -p <pid>

# 查看调度策略
chrt -p <pid>
```

## 答题总结

**面试标准答案**：

Java线程调度采用**抢占式调度**，由**操作系统内核**负责。

### 核心机制
1. **调度模型**：抢占式，非协作式
2. **线程映射**：1:1映射到操作系统线程（传统JVM）
3. **调度算法**：
   - 时间片轮转（Round-Robin）
   - 优先级调度（Priority Scheduling）
   - 多级反馈队列（现代Linux）

### 优先级
- **范围**：1（最低）到10（最高），默认5
- **平台差异**：
  - Windows：基本忽略
  - Linux：部分参考，影响较小
  - 不可依赖优先级做核心逻辑

### 调度时机
1. 时间片用完（10-100ms）
2. 高优先级线程抢占
3. 线程主动让出（yield/sleep）
4. 线程阻塞（锁/I/O/wait）

### 优化策略
1. **减少线程数**：避免过度竞争
2. **无锁编程**：减少阻塞
3. **CPU亲和性**：绑定核心
4. **虚拟线程**：用户态调度（Java 19+）

**核心记忆**：Java线程调度 = 操作系统说了算，优先级只是"建议"，不要依赖优先级做业务逻辑。

