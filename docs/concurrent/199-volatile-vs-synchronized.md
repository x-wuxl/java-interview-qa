---
layout: default
title: "有了synchronized为什么还需要volatile"
parent: 并发编程
nav_order: 199
description: 对比分析volatile和synchronized的区别，理解为何需要两种同步机制并存。
date: 2025-11-02
---
## 核心区别

`volatile` 和 `synchronized` 是两种不同层次的同步机制，各有适用场景，不能互相替代。

| 特性 | volatile | synchronized |
|-----|----------|--------------|
| **原子性** | ❌ 不保证 | ✅ 保证 |
| **可见性** | ✅ 保证 | ✅ 保证 |
| **有序性** | ✅ 禁止重排序 | ✅ 保证有序 |
| **锁机制** | 无锁 | 互斥锁 |
| **性能开销** | 极低 | 较高（线程上下文切换）|
| **作用范围** | 变量 | 方法/代码块 |
| **阻塞** | 不阻塞 | 可能阻塞 |
| **可重入** | N/A | 支持 |

## 为什么需要volatile

### 1. 性能优势

```java
public class PerformanceComparison {
    // 场景1：状态标志位 - volatile最优
    private volatile boolean running = true;
    
    public void stopWithVolatile() {
        running = false;  // 轻量级，无锁开销
    }
    
    // 场景2：如果用synchronized - 性能浪费
    private boolean running2 = true;
    
    public synchronized void stopWithSync() {
        running2 = false;  // 重量级，涉及锁的获取和释放
    }
}
```

**性能对比**：
- volatile写操作：约10-20 CPU周期
- synchronized：约100+ CPU周期（包括锁竞争、上下文切换）

### 2. 适用不同场景

```java
public class UseCases {
    
    // ✅ volatile适用：状态标志
    private volatile boolean initialized = false;
    
    public void init() {
        // 初始化逻辑
        initialized = true;  // 单次写，无需synchronized
    }
    
    public void waitForInit() {
        while (!initialized) {  // 多次读，volatile保证可见性
            // 等待
        }
    }
    
    // ✅ synchronized适用：复合操作
    private int count = 0;
    
    public synchronized void increment() {
        count++;  // 读-改-写，必须用锁
    }
    
    // ✅ volatile适用：单次安全发布
    private volatile Singleton instance;
    
    public Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;  // volatile保证对象完全初始化
    }
}
```

### 3. 语义更清晰

```java
public class ClearSemantics {
    // volatile明确表达：这是一个共享状态，会被多线程读写
    private volatile boolean flag;
    
    // synchronized表达：这是一个需要互斥访问的临界区
    private final Object lock = new Object();
    
    public void criticalSection() {
        synchronized (lock) {
            // 复杂的复合操作
        }
    }
}
```

## synchronized无法替代volatile的场景

### 场景1：双重检查锁（DCL）

```java
public class Singleton {
    // 这里必须用volatile，synchronized无法替代
    private static volatile Singleton instance;
    
    public static Singleton getInstance() {
        if (instance == null) {              // 第一次检查：无锁
            synchronized (Singleton.class) { // 加锁
                if (instance == null) {
                    // 指令重排序问题：
                    // 1. 分配内存
                    // 2. 初始化对象
                    // 3. 指向内存地址
                    // 可能重排为 1->3->2，导致其他线程拿到半初始化对象
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}

// 如果不用volatile，只用synchronized：
public class SingletonWrong {
    private static Singleton instance;  // 没有volatile
    
    public static Singleton getInstance() {
        if (instance == null) {  
            // 问题：这里的读取可能看到未完全初始化的对象
            // synchronized只保证锁内的可见性
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;  // 可能返回半初始化对象
    }
}
```

### 场景2：轻量级通知机制

```java
public class Notification {
    private volatile boolean ready = false;
    private String data;
    
    // 生产者线程
    public void produce() {
        data = "some data";
        ready = true;  // volatile写，立即可见
    }
    
    // 消费者线程
    public void consume() {
        while (!ready) {  // 无锁轮询，性能高
            // 等待
        }
        System.out.println(data);  // 由于volatile的happens-before，能看到data
    }
}

// 如果用synchronized - 过度同步
public class NotificationWithSync {
    private boolean ready = false;
    private String data;
    
    public synchronized void produce() {
        data = "some data";
        ready = true;
    }
    
    public void consume() {
        while (true) {
            synchronized (this) {  // 每次循环都要获取锁！性能差
                if (ready) {
                    System.out.println(data);
                    break;
                }
            }
        }
    }
}
```

### 场景3：读多写少的状态共享

```java
public class Configuration {
    // 配置项：写一次，读百万次
    private volatile boolean featureEnabled = false;
    
    // 读操作：高频调用
    public boolean isFeatureEnabled() {
        return featureEnabled;  // volatile读，无锁，极快
    }
    
    // 写操作：低频调用
    public void setFeatureEnabled(boolean enabled) {
        featureEnabled = enabled;  // volatile写，保证可见性
    }
}

// 如果用synchronized：每次读都要加锁，性能损失巨大
public class ConfigurationWithSync {
    private boolean featureEnabled = false;
    
    public synchronized boolean isFeatureEnabled() {
        return featureEnabled;  // 每次读都加锁！
    }
    
    public synchronized void setFeatureEnabled(boolean enabled) {
        featureEnabled = enabled;
    }
}
```

## volatile无法替代synchronized的场景

### 场景1：复合操作

```java
// 错误：volatile无法保证原子性
private volatile int count = 0;
public void increment() {
    count++;  // 非原子操作，会出错
}

// 正确：使用synchronized
private int count = 0;
public synchronized void increment() {
    count++;  // 保证原子性
}
```

### 场景2：多个变量的一致性

```java
public class Transfer {
    // 错误：volatile无法保证多个变量的一致性
    private volatile int accountA = 1000;
    private volatile int accountB = 1000;
    
    public void transfer(int amount) {
        accountA -= amount;  // ❌ 可能在这里被中断
        accountB += amount;  // 导致不一致
    }
    
    // 正确：使用synchronized保证事务性
    public synchronized void transferCorrect(int amount) {
        accountA -= amount;
        accountB += amount;  // 作为整体执行
    }
}
```

## 组合使用的场景

```java
public class CombinedUsage {
    private volatile boolean stopped = false;  // 状态标志
    private final Object lock = new Object();
    private Queue<Task> tasks = new LinkedList<>();
    
    public void worker() {
        while (!stopped) {  // volatile读，快速检查
            Task task = null;
            synchronized (lock) {  // 只在必要时加锁
                if (!tasks.isEmpty()) {
                    task = tasks.poll();
                }
            }
            if (task != null) {
                task.execute();
            }
        }
    }
    
    public void stop() {
        stopped = true;  // volatile写，立即通知所有线程
    }
    
    public void addTask(Task task) {
        synchronized (lock) {  // 修改共享集合必须加锁
            tasks.offer(task);
        }
    }
}
```

## 性能实测

```java
public class BenchmarkTest {
    private volatile boolean volatileFlag = false;
    private boolean syncFlag = false;
    
    @Test
    public void testVolatile() {
        long start = System.nanoTime();
        for (int i = 0; i < 10_000_000; i++) {
            volatileFlag = !volatileFlag;
        }
        long end = System.nanoTime();
        System.out.println("Volatile: " + (end - start) / 1_000_000 + "ms");
        // 结果：约50ms
    }
    
    @Test
    public void testSynchronized() {
        long start = System.nanoTime();
        for (int i = 0; i < 10_000_000; i++) {
            synchronized (this) {
                syncFlag = !syncFlag;
            }
        }
        long end = System.nanoTime();
        System.out.println("Synchronized: " + (end - start) / 1_000_000 + "ms");
        // 结果：约200-300ms
    }
}
```

## 答题总结

### 三个关键点

1. **功能差异**：
   - volatile：轻量级，只保证可见性和有序性，不保证原子性
   - synchronized：重量级，保证原子性、可见性、有序性

2. **性能差异**：
   - volatile：无锁，性能开销极小，适合高频读写的状态变量
   - synchronized：有锁，有上下文切换开销，适合临界区保护

3. **互补关系**：
   - **volatile无法替代synchronized**：复合操作、多变量一致性
   - **synchronized无法替代volatile**：DCL模式、轻量级通知、读多写少场景

### 面试答题模板

> "synchronized和volatile解决的问题不同：
>
> **synchronized**是互斥锁，保证原子性、可见性、有序性，适合保护临界区，但有锁竞争和上下文切换开销。
>
> **volatile**是轻量级同步，只保证可见性和有序性，不保证原子性，性能开销极小，适合状态标志、DCL单例模式等场景。
>
> 典型例子是双重检查锁的单例模式，必须用volatile防止指令重排序，而synchronized只负责保证实例创建的原子性。如果只用synchronized而不用volatile，可能导致其他线程拿到未完全初始化的对象。
>
> 所以两者是互补关系，根据具体场景选择或组合使用。"

