---
title: "线程同步的方式有哪些？"
date: 2025-11-02
categories: [并发编程, 线程基础]
tags: [Java, 多线程, 线程同步, synchronized, Lock, volatile]
description: "全面梳理Java线程同步的8种方式，包括synchronized、Lock、volatile、原子类、ThreadLocal、信号量等，深入理解各自的适用场景和性能特点。"
nav_order: 180
parent: 并发编程
---
## 核心概念

**线程同步**是指协调多个线程，确保共享资源访问的安全性和有序性。Java提供了多种同步机制，从底层到高层、从重量级到轻量级。

## Java线程同步的8种方式

### 对比速览

| 方式 | 类型 | 粒度 | 性能 | 适用场景 |
|------|------|------|------|---------|
| synchronized | 内置锁 | 粗粒度 | 中 | 通用同步 |
| Lock | 显式锁 | 细粒度 | 高 | 复杂同步逻辑 |
| volatile | 内存可见性 | 轻量级 | 最高 | 状态标志 |
| 原子类 | CAS操作 | 轻量级 | 高 | 计数器、累加器 |
| ThreadLocal | 线程隔离 | 无竞争 | 高 | 线程私有数据 |
| 信号量 | 许可证机制 | 灵活 | 中 | 资源池限流 |
| CountDownLatch | 一次性同步 | 计数器 | 中 | 等待多线程完成 |
| CyclicBarrier | 循环同步 | 栅栏 | 中 | 分阶段任务 |

## 1. synchronized（内置锁）

### 基本用法

```java
public class SynchronizedDemo {
    private int count = 0;

    // 1. 同步方法
    public synchronized void incrementMethod() {
        count++;
    }

    // 2. 同步代码块
    public void incrementBlock() {
        synchronized (this) {
            count++;
        }
    }

    // 3. 同步静态方法（类锁）
    public static synchronized void staticMethod() {
        // 锁的是类对象
    }

    // 4. 同步静态代码块
    public void staticBlock() {
        synchronized (SynchronizedDemo.class) {
            // 锁的是类对象
        }
    }
}
```

### 原理

```java
// 字节码层面
public synchronized void increment();
  flags: ACC_PUBLIC, ACC_SYNCHRONIZED  // 方法标志
  Code:
    // ...

public void incrementBlock();
  Code:
    monitorenter  // 进入监视器（获取锁）
    // ... 业务代码
    monitorexit   // 退出监视器（释放锁）
```

**特点**：
- 可重入锁（同一线程可多次获取）
- 自动释放（异常时也会释放）
- 对象头Mark Word存储锁信息
- JDK 6+引入锁优化（偏向锁、轻量级锁、自旋锁）

### 适用场景

```java
// ✅ 简单的同步场景
public class Counter {
    private int count = 0;

    public synchronized int incrementAndGet() {
        return ++count;
    }
}
```

## 2. Lock（显式锁）

### ReentrantLock

```java
public class LockDemo {
    private final Lock lock = new ReentrantLock();
    private int count = 0;

    public void increment() {
        lock.lock(); // 显式加锁
        try {
            count++;
        } finally {
            lock.unlock(); // 必须在finally中释放
        }
    }

    // 尝试加锁（非阻塞）
    public boolean tryIncrement() {
        if (lock.tryLock()) {
            try {
                count++;
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;
    }

    // 超时加锁
    public boolean tryIncrementWithTimeout(long timeout, TimeUnit unit) 
            throws InterruptedException {
        if (lock.tryLock(timeout, unit)) {
            try {
                count++;
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;
    }

    // 可中断加锁
    public void interruptibleIncrement() throws InterruptedException {
        lock.lockInterruptibly();
        try {
            count++;
        } finally {
            lock.unlock();
        }
    }
}
```

### ReadWriteLock（读写锁）

```java
public class ReadWriteLockDemo {
    private final ReadWriteLock rwLock = new ReentrantReadWriteLock();
    private final Lock readLock = rwLock.readLock();
    private final Lock writeLock = rwLock.writeLock();
    private int count = 0;

    // 读操作（多个线程可同时读）
    public int getCount() {
        readLock.lock();
        try {
            return count;
        } finally {
            readLock.unlock();
        }
    }

    // 写操作（独占）
    public void increment() {
        writeLock.lock();
        try {
            count++;
        } finally {
            writeLock.unlock();
        }
    }
}
```

**Lock vs synchronized**：

| 特性 | synchronized | Lock |
|------|-------------|------|
| 锁获取 | 自动 | 手动 |
| 锁释放 | 自动 | 手动（finally） |
| 尝试加锁 | ❌ | ✅ tryLock() |
| 超时加锁 | ❌ | ✅ tryLock(timeout) |
| 可中断 | ❌ | ✅ lockInterruptibly() |
| 公平性 | ❌ | ✅ 可选 |
| 条件变量 | 1个（wait/notify） | 多个（Condition） |

### 适用场景

```java
// ✅ 需要高级功能
public class AdvancedLocking {
    private final ReentrantLock lock = new ReentrantLock(true); // 公平锁
    private final Condition notEmpty = lock.newCondition();
    private final Condition notFull = lock.newCondition();
    private final Object[] items = new Object[100];
    private int count, putIndex, takeIndex;

    public void put(Object x) throws InterruptedException {
        lock.lock();
        try {
            while (count == items.length)
                notFull.await(); // 等待notFull条件
            items[putIndex] = x;
            if (++putIndex == items.length) putIndex = 0;
            ++count;
            notEmpty.signal(); // 通知notEmpty条件
        } finally {
            lock.unlock();
        }
    }

    public Object take() throws InterruptedException {
        lock.lock();
        try {
            while (count == 0)
                notEmpty.await(); // 等待notEmpty条件
            Object x = items[takeIndex];
            if (++takeIndex == items.length) takeIndex = 0;
            --count;
            notFull.signal(); // 通知notFull条件
            return x;
        } finally {
            lock.unlock();
        }
    }
}
```

## 3. volatile（内存可见性）

### 基本用法

```java
public class VolatileDemo {
    private volatile boolean running = true; // 保证可见性

    public void start() {
        new Thread(() -> {
            while (running) {
                // 执行任务
            }
            System.out.println("线程停止");
        }).start();
    }

    public void stop() {
        running = false; // 修改立即对其他线程可见
    }
}
```

### 原理

```java
// volatile的两个作用：
1. 保证可见性：修改立即刷新到主内存，读取从主内存读取
2. 禁止指令重排序：使用内存屏障

// 底层实现（x86）：
// 写操作：在写后插入StoreLoad屏障（lock指令前缀）
movl $1, running      // 写入volatile变量
lock addl $0, (%esp)  // 内存屏障（强制刷新）
```

**特点**：
- 轻量级同步
- 不保证原子性（除赋值外）
- 适合单线程写、多线程读

### volatile的局限性

```java
// ❌ volatile不保证复合操作的原子性
public class VolatileCounter {
    private volatile int count = 0;

    public void increment() {
        count++; // 非原子操作：读取 → 计算 → 写入
    }
}

// ✅ 使用原子类
public class AtomicCounter {
    private AtomicInteger count = new AtomicInteger(0);

    public void increment() {
        count.incrementAndGet(); // 原子操作
    }
}
```

### 适用场景

```java
// ✅ 状态标志
private volatile boolean shutdown = false;

// ✅ 双重检查锁定（DCL）
public class Singleton {
    private static volatile Singleton instance;

    public static Singleton getInstance() {
        if (instance == null) { // 第一次检查
            synchronized (Singleton.class) {
                if (instance == null) { // 第二次检查
                    instance = new Singleton(); // volatile防止重排序
                }
            }
        }
        return instance;
    }
}

// ✅ 一次性安全发布
private volatile Map<String, String> config;

public void updateConfig() {
    Map<String, String> newConfig = loadConfig();
    config = newConfig; // 安全发布
}
```

## 4. 原子类（Atomic）

### 基本类型原子类

```java
public class AtomicDemo {
    // 原子整数
    private AtomicInteger atomicInt = new AtomicInteger(0);
    // 原子长整数
    private AtomicLong atomicLong = new AtomicLong(0L);
    // 原子布尔
    private AtomicBoolean atomicBoolean = new AtomicBoolean(false);

    public void demonstrate() {
        // CAS操作
        atomicInt.incrementAndGet();        // ++i
        atomicInt.getAndIncrement();        // i++
        atomicInt.addAndGet(5);             // i += 5
        atomicInt.compareAndSet(0, 1);      // if (i == 0) i = 1;

        // 函数式更新
        atomicInt.updateAndGet(x -> x * 2); // i = i * 2
        atomicInt.accumulateAndGet(5, (x, y) -> x + y); // i = i + 5
    }
}
```

### 数组原子类

```java
public class AtomicArrayDemo {
    private AtomicIntegerArray array = new AtomicIntegerArray(10);

    public void increment(int index) {
        array.incrementAndGet(index); // 原子递增指定位置
    }

    public int get(int index) {
        return array.get(index);
    }
}
```

### 引用原子类

```java
public class AtomicReferenceDemo {
    static class User {
        String name;
        int age;

        User(String name, int age) {
            this.name = name;
            this.age = age;
        }
    }

    private AtomicReference<User> atomicUser = 
        new AtomicReference<>(new User("Tom", 20));

    public void updateUser() {
        User oldUser = atomicUser.get();
        User newUser = new User("Jerry", 21);
        atomicUser.compareAndSet(oldUser, newUser); // CAS更新
    }
}
```

### 字段原子更新器

```java
public class AtomicFieldDemo {
    // 原子更新int字段
    private static final AtomicIntegerFieldUpdater<User> ageUpdater =
        AtomicIntegerFieldUpdater.newUpdater(User.class, "age");

    static class User {
        String name;
        volatile int age; // 必须是volatile

        User(String name, int age) {
            this.name = name;
            this.age = age;
        }
    }

    public void updateAge(User user, int newAge) {
        ageUpdater.compareAndSet(user, user.age, newAge);
    }
}
```

### 累加器（JDK 8+）

```java
public class AccumulatorDemo {
    // 高性能计数器（分段CAS）
    private LongAdder counter = new LongAdder();

    public void increment() {
        counter.increment(); // 比AtomicLong更快
    }

    public long getCount() {
        return counter.sum();
    }
}
```

**LongAdder vs AtomicLong**：
- `AtomicLong`：单个变量CAS，高竞争下性能差
- `LongAdder`：分段累加，高竞争下性能好

## 5. ThreadLocal（线程隔离）

### 基本用法

```java
public class ThreadLocalDemo {
    private static ThreadLocal<Integer> threadLocal = 
        ThreadLocal.withInitial(() -> 0);

    public void increment() {
        int value = threadLocal.get();
        threadLocal.set(value + 1);
    }

    public int getValue() {
        return threadLocal.get();
    }

    public static void main(String[] args) throws InterruptedException {
        ThreadLocalDemo demo = new ThreadLocalDemo();

        Thread t1 = new Thread(() -> {
            demo.increment();
            demo.increment();
            System.out.println("线程1: " + demo.getValue()); // 2
        });

        Thread t2 = new Thread(() -> {
            demo.increment();
            System.out.println("线程2: " + demo.getValue()); // 1
        });

        t1.start();
        t2.start();
        t1.join();
        t2.join();
    }
}
```

### 典型应用

```java
// 1. 数据库连接管理
public class ConnectionManager {
    private static ThreadLocal<Connection> connectionHolder = 
        ThreadLocal.withInitial(() -> {
            try {
                return DriverManager.getConnection("jdbc:mysql://...");
            } catch (SQLException e) {
                throw new RuntimeException(e);
            }
        });

    public static Connection getConnection() {
        return connectionHolder.get();
    }

    public static void closeConnection() {
        Connection conn = connectionHolder.get();
        if (conn != null) {
            try {
                conn.close();
            } catch (SQLException e) {
                e.printStackTrace();
            } finally {
                connectionHolder.remove(); // 防止内存泄漏
            }
        }
    }
}

// 2. 用户上下文
public class UserContext {
    private static ThreadLocal<User> currentUser = new ThreadLocal<>();

    public static void setUser(User user) {
        currentUser.set(user);
    }

    public static User getUser() {
        return currentUser.get();
    }

    public static void clear() {
        currentUser.remove();
    }
}

// 3. SimpleDateFormat线程安全
public class DateUtil {
    private static ThreadLocal<SimpleDateFormat> formatter = 
        ThreadLocal.withInitial(() -> new SimpleDateFormat("yyyy-MM-dd"));

    public static String format(Date date) {
        return formatter.get().format(date);
    }
}
```

### 注意事项

```java
// ❌ 内存泄漏风险
public class ThreadLocalLeak {
    private static ThreadLocal<byte[]> local = new ThreadLocal<>();

    public void allocate() {
        local.set(new byte[1024 * 1024 * 10]); // 10MB
        // 未调用remove()，线程池中线程不销毁，导致内存泄漏
    }
}

// ✅ 正确使用
public class ThreadLocalCorrect {
    private static ThreadLocal<Resource> local = new ThreadLocal<>();

    public void process() {
        try {
            local.set(new Resource());
            // ... 使用资源
        } finally {
            local.remove(); // 及时清理
        }
    }
}
```

## 6. Semaphore（信号量）

```java
public class SemaphoreDemo {
    // 限制同时访问的线程数为3
    private final Semaphore semaphore = new Semaphore(3);

    public void访问资源() throws InterruptedException {
        semaphore.acquire(); // 获取许可证
        try {
            System.out.println(Thread.currentThread().getName() + " 访问资源");
            Thread.sleep(1000);
        } finally {
            semaphore.release(); // 释放许可证
        }
    }

    public static void main(String[] args) {
        SemaphoreDemo demo = new SemaphoreDemo();
        for (int i = 0; i < 10; i++) {
            new Thread(() -> {
                try {
                    demo.访问资源();
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }, "Thread-" + i).start();
        }
    }
}
```

**适用场景**：
- 连接池限流
- 资源访问控制
- 限流器实现

## 7. CountDownLatch（倒计数门闩）

```java
public class CountDownLatchDemo {
    public static void main(String[] args) throws InterruptedException {
        int workerCount = 5;
        CountDownLatch latch = new CountDownLatch(workerCount);

        // 启动5个工作线程
        for (int i = 0; i < workerCount; i++) {
            int workerId = i;
            new Thread(() -> {
                System.out.println("Worker " + workerId + " 开始工作");
                try {
                    Thread.sleep(1000);
                } catch (InterruptedException e) {
                }
                System.out.println("Worker " + workerId + " 完成工作");
                latch.countDown(); // 计数减1
            }).start();
        }

        System.out.println("主线程等待所有Worker完成...");
        latch.await(); // 阻塞直到计数为0
        System.out.println("所有Worker已完成，主线程继续");
    }
}
```

## 8. CyclicBarrier（循环栅栏）

```java
public class CyclicBarrierDemo {
    public static void main(String[] args) {
        int threadCount = 3;
        CyclicBarrier barrier = new CyclicBarrier(threadCount, () -> {
            System.out.println("所有线程已到达屏障，开始下一阶段");
        });

        for (int i = 0; i < threadCount; i++) {
            int threadId = i;
            new Thread(() -> {
                try {
                    System.out.println("线程" + threadId + " 阶段1完成");
                    barrier.await(); // 等待其他线程

                    System.out.println("线程" + threadId + " 阶段2完成");
                    barrier.await(); // 可重复使用

                } catch (Exception e) {
                    e.printStackTrace();
                }
            }).start();
        }
    }
}
```

## 答题总结

**面试标准答案**：

Java线程同步主要有**8种方式**：

### 1. synchronized（内置锁）
- 简单易用，自动释放
- 适合简单同步场景

### 2. Lock（显式锁）
- 功能丰富：tryLock、超时、可中断
- 适合复杂同步逻辑

### 3. volatile（可见性）
- 轻量级，保证可见性和有序性
- 适合状态标志、单写多读

### 4. 原子类（Atomic）
- CAS无锁，高性能
- 适合计数器、累加器

### 5. ThreadLocal（线程隔离）
- 无竞争，线程私有
- 适合连接管理、上下文传递

### 6. Semaphore（信号量）
- 许可证机制
- 适合资源池、限流

### 7. CountDownLatch（倒计数）
- 一次性同步
- 适合等待多线程完成

### 8. CyclicBarrier（循环栅栏）
- 可重复使用
- 适合分阶段任务

**选择建议**：
- **简单场景**：synchronized
- **复杂逻辑**：Lock + Condition
- **高性能计数**：LongAdder
- **状态标志**：volatile
- **线程私有**：ThreadLocal

