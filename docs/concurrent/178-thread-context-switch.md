---
layout: default
title: "什么是多线程中的上下文切换？"
parent: 并发编程
nav_order: 178
description: "深入理解线程上下文切换的本质、开销和触发条件，掌握减少上下文切换的优化技巧，提升多线程程序性能。"
date: 2025-11-02
---
## 核心概念

**上下文切换（Context Switch）**是指CPU从一个线程切换到另一个线程时，保存当前线程状态并恢复目标线程状态的过程。

```
线程A执行 → 保存A的上下文 → 加载B的上下文 → 线程B执行
   ↑_______________________________________________|
                     上下文切换
```

**线程上下文**包括：
- **程序计数器（PC）**：下一条指令的地址
- **寄存器状态**：通用寄存器、栈指针等
- **线程栈**：局部变量、方法调用栈
- **线程状态**：RUNNABLE、BLOCKED等

## 上下文切换的过程

### 1. 完整流程

```
┌─────────────────┐
│  线程A正在运行   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 触发切换条件     │ ← 时间片用完/阻塞/sleep/wait
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 保存线程A上下文  │
│ - PC寄存器      │
│ - 寄存器状态    │
│ - 栈指针        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 线程调度        │ ← 选择下一个线程B
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 加载线程B上下文  │
│ - 恢复PC寄存器  │
│ - 恢复寄存器    │
│ - 恢复栈指针    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  线程B开始运行   │
└─────────────────┘
```

### 2. 底层实现（Linux内核）

```c
// Linux内核：进程切换（简化）
void context_switch(struct task_struct *prev, struct task_struct *next) {
    // 1. 保存当前线程的寄存器状态
    save_context(prev);
    
    // 2. 切换内存映射（如果是进程切换）
    switch_mm(prev->mm, next->mm);
    
    // 3. 切换CPU上下文（寄存器、栈指针等）
    switch_to(prev, next);
    
    // 4. 恢复新线程的寄存器状态
    restore_context(next);
}
```

## 触发上下文切换的条件

### 1. 时间片用完

```java
// CPU时间片轮转（Round-Robin）
public class TimeSliceDemo {
    public static void main(String[] args) {
        // 创建10个线程竞争CPU
        for (int i = 0; i < 10; i++) {
            new Thread(() -> {
                while (true) {
                    // 持续计算，时间片用完后会被切换
                }
            }, "Thread-" + i).start();
        }
    }
}
```

**特点**：
- 现代操作系统时间片通常为**10-100ms**
- 时间片到期后，线程被强制切换

### 2. 线程主动让出CPU

```java
public class YieldDemo {
    public static void main(String[] args) {
        Thread thread1 = new Thread(() -> {
            for (int i = 0; i < 5; i++) {
                System.out.println("Thread-1: " + i);
                Thread.yield(); // 主动让出CPU
            }
        });

        Thread thread2 = new Thread(() -> {
            for (int i = 0; i < 5; i++) {
                System.out.println("Thread-2: " + i);
                Thread.yield();
            }
        });

        thread1.start();
        thread2.start();
    }
}
```

**触发方式**：
- `Thread.yield()`
- `Thread.sleep(0)`
- `LockSupport.parkNanos(1)`

### 3. 等待锁或I/O

```java
public class BlockDemo {
    private static final Object lock = new Object();

    public static void main(String[] args) {
        // 线程1持有锁
        new Thread(() -> {
            synchronized (lock) {
                try {
                    Thread.sleep(5000); // 持有锁5秒
                } catch (InterruptedException e) {
                }
            }
        }).start();

        // 线程2等待锁，触发上下文切换
        new Thread(() -> {
            synchronized (lock) { // BLOCKED状态，上下文切换
                System.out.println("获取到锁");
            }
        }).start();
    }
}
```

**触发场景**：
- `synchronized`锁竞争
- `Lock.lock()`阻塞
- I/O操作（磁盘读写、网络请求）

### 4. wait/sleep/join

```java
public class WaitSleepDemo {
    private static final Object lock = new Object();

    public static void main(String[] args) {
        // sleep触发切换
        new Thread(() -> {
            try {
                Thread.sleep(1000); // TIMED_WAITING，上下文切换
            } catch (InterruptedException e) {
            }
        }).start();

        // wait触发切换
        new Thread(() -> {
            synchronized (lock) {
                try {
                    lock.wait(); // WAITING，上下文切换
                } catch (InterruptedException e) {
                }
            }
        }).start();
    }
}
```

### 5. 线程优先级调度

```java
public class PriorityDemo {
    public static void main(String[] args) {
        Thread lowPriority = new Thread(() -> {
            while (true) {
                // 低优先级任务
            }
        });
        lowPriority.setPriority(Thread.MIN_PRIORITY);

        Thread highPriority = new Thread(() -> {
            while (true) {
                // 高优先级任务，可能抢占低优先级线程
            }
        });
        highPriority.setPriority(Thread.MAX_PRIORITY);

        lowPriority.start();
        highPriority.start();
    }
}
```

## 上下文切换的开销

### 1. 时间开销

| 操作 | 时间开销 |
|------|---------|
| 单次上下文切换 | **1-10微秒** |
| 函数调用 | 几纳秒 |
| 缓存失效 | 数十纳秒到数微秒 |

**示例测试**：

```java
public class ContextSwitchCostDemo {
    private static final int COUNT = 1000000;

    public static void main(String[] args) throws InterruptedException {
        // 测试1：单线程执行
        long start1 = System.nanoTime();
        for (int i = 0; i < COUNT; i++) {
            doWork();
        }
        long time1 = System.nanoTime() - start1;
        System.out.println("单线程: " + time1 / 1_000_000 + "ms");

        // 测试2：多线程执行（频繁切换）
        Thread[] threads = new Thread[10];
        long start2 = System.nanoTime();
        for (int i = 0; i < 10; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < COUNT / 10; j++) {
                    doWork();
                    Thread.yield(); // 触发切换
                }
            });
            threads[i].start();
        }
        for (Thread t : threads) {
            t.join();
        }
        long time2 = System.nanoTime() - start2;
        System.out.println("多线程(频繁切换): " + time2 / 1_000_000 + "ms");
    }

    private static void doWork() {
        // 简单计算
        int sum = 0;
        for (int i = 0; i < 100; i++) {
            sum += i;
        }
    }
}
```

**典型输出**：
```
单线程: 50ms
多线程(频繁切换): 1500ms  // 30倍慢！
```

### 2. 性能影响

```java
// 直接开销
1. 保存/恢复寄存器状态：1-2微秒
2. 内核调度决策：1-2微秒
3. TLB刷新：1-2微秒

// 间接开销
4. CPU缓存失效（Cache Miss）
5. 分支预测失败
6. 内存访问延迟增加
```

### 3. 可视化监控

```java
// 使用JMX监控上下文切换
public class ContextSwitchMonitor {
    public static void main(String[] args) {
        ThreadMXBean threadMXBean = ManagementFactory.getThreadMXBean();
        
        long[] threadIds = threadMXBean.getAllThreadIds();
        for (long threadId : threadIds) {
            ThreadInfo info = threadMXBean.getThreadInfo(threadId);
            if (info != null) {
                System.out.printf("Thread: %s, State: %s, Blocked: %d, Waited: %d%n",
                    info.getThreadName(),
                    info.getThreadState(),
                    info.getBlockedCount(),   // 阻塞次数
                    info.getWaitedCount());   // 等待次数（近似切换次数）
            }
        }
    }
}
```

## 减少上下文切换的优化策略

### 1. 无锁并发编程

```java
// ❌ 锁竞争导致频繁切换
public class SynchronizedCounter {
    private int count = 0;
    
    public synchronized void increment() {
        count++; // 多线程竞争，频繁阻塞
    }
}

// ✅ CAS无锁，减少切换
public class AtomicCounter {
    private AtomicInteger count = new AtomicInteger(0);
    
    public void increment() {
        count.incrementAndGet(); // 无锁，自旋重试
    }
}
```

**效果**：
- 减少`BLOCKED`状态
- 降低上下文切换频率

### 2. 减少线程数量

```java
// ❌ 过多线程导致频繁切换
ExecutorService executor = Executors.newFixedThreadPool(1000); // 过多

// ✅ 合理线程数
int processors = Runtime.getRuntime().availableProcessors();
ExecutorService executor = new ThreadPoolExecutor(
    processors,           // 核心线程数 = CPU核心数
    processors * 2,       // 最大线程数
    60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(100)
);
```

**公式**：
- **CPU密集型**：线程数 = CPU核心数 + 1
- **I/O密集型**：线程数 = CPU核心数 × (1 + I/O时间 / CPU时间)

### 3. 协程（轻量级线程）

```java
// Java 19+ 虚拟线程（Project Loom）
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    for (int i = 0; i < 100000; i++) {
        executor.submit(() -> {
            // 虚拟线程，由JVM调度，减少内核上下文切换
            Thread.sleep(1000);
            return "result";
        });
    }
}
```

**优势**：
- 虚拟线程由JVM调度，不触发内核级上下文切换
- 支持海量并发（百万级）

### 4. 合并锁粒度

```java
// ❌ 细粒度锁，频繁切换
public class FineGrainedLock {
    private final Object lock1 = new Object();
    private final Object lock2 = new Object();
    
    public void method1() {
        synchronized (lock1) { /* ... */ }
    }
    
    public void method2() {
        synchronized (lock2) { /* ... */ }
    }
}

// ✅ 粗粒度锁，减少切换（适用于短临界区）
public class CoarseGrainedLock {
    private final Object lock = new Object();
    
    public void method1() {
        synchronized (lock) { /* ... */ }
    }
    
    public void method2() {
        synchronized (lock) { /* ... */ }
    }
}
```

### 5. 使用ThreadLocal

```java
// ❌ 共享变量，需要同步
public class SharedVariable {
    private static int count = 0;
    
    public static synchronized int getNext() {
        return count++; // 频繁同步，上下文切换
    }
}

// ✅ ThreadLocal，无需同步
public class ThreadLocalVariable {
    private static ThreadLocal<Integer> count = ThreadLocal.withInitial(() -> 0);
    
    public static int getNext() {
        int value = count.get();
        count.set(value + 1);
        return value; // 无同步，无切换
    }
}
```

## 监控与诊断

### 1. Linux系统监控

```bash
# 查看上下文切换次数
vmstat 1

# 查看每个进程的上下文切换
pidstat -w 1 -p <pid>

# 查看线程级别的上下文切换
perf stat -e context-switches -p <pid>
```

### 2. Java代码监控

```java
public class ContextSwitchStats {
    public static void main(String[] args) throws Exception {
        ThreadMXBean threadMXBean = ManagementFactory.getThreadMXBean();
        
        long totalSwitches = 0;
        for (long id : threadMXBean.getAllThreadIds()) {
            ThreadInfo info = threadMXBean.getThreadInfo(id);
            if (info != null) {
                // 近似统计
                totalSwitches += info.getBlockedCount() + info.getWaitedCount();
            }
        }
        
        System.out.println("总上下文切换次数（近似）: " + totalSwitches);
    }
}
```

## 答题总结

**面试标准答案**：

**上下文切换**是CPU从一个线程切换到另一个线程时，保存当前线程状态并恢复目标线程状态的过程。

### 核心内容
- **线程上下文**：程序计数器、寄存器、栈指针、线程状态
- **切换流程**：保存当前上下文 → 选择新线程 → 恢复新上下文
- **时间开销**：单次切换1-10微秒，但包含缓存失效等间接开销

### 触发条件
1. **时间片用完**（10-100ms）
2. **主动让出CPU**（yield/sleep(0)）
3. **阻塞操作**（锁竞争/I/O）
4. **等待通知**（wait/sleep/join）
5. **优先级抢占**

### 性能影响
- 直接开销：保存/恢复寄存器
- 间接开销：CPU缓存失效、分支预测失败
- 频繁切换可导致性能下降30倍以上

### 优化策略
1. **无锁编程**：使用CAS、原子类
2. **减少线程数**：CPU密集型 = 核心数+1
3. **虚拟线程**：JVM级调度，减少内核切换
4. **合并锁粒度**：权衡锁冲突和切换开销
5. **ThreadLocal**：避免共享状态

**核心记忆**：上下文切换 = 线程间的"接力赛"，交接棒（保存/恢复状态）需要时间，频繁交接会严重影响性能。

