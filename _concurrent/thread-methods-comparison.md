---
title: "run、start、wait、sleep、notify、notifyAll区别"
date: 2025-11-02
categories: [并发编程, 线程基础]
tags: [Java, 多线程, wait, sleep, notify, 线程方法]
description: "全面对比Java线程核心方法：run与start的区别、wait与sleep的差异、notify与notifyAll的选择，深入理解线程协作机制的底层原理。"
nav_order: 182
parent: 并发编程
---
## 核心概念速览

| 方法 | 所属类 | 是否释放锁 | 线程状态 | 用途 |
|------|--------|-----------|---------|------|
| `run()` | Thread | N/A | RUNNABLE | 线程执行体 |
| `start()` | Thread | N/A | NEW→RUNNABLE | 启动线程 |
| `wait()` | Object | ✅ 释放 | WAITING | 等待通知 |
| `sleep()` | Thread | ❌ 不释放 | TIMED_WAITING | 暂停执行 |
| `notify()` | Object | ❌ 不释放 | WAITING→RUNNABLE | 唤醒单个 |
| `notifyAll()` | Object | ❌ 不释放 | WAITING→RUNNABLE | 唤醒全部 |

## 详细对比分析

### 1. run() vs start()

#### run()方法
```java
public class ThreadDemo {
    public static void main(String[] args) {
        Thread thread = new Thread(() -> {
            System.out.println("当前线程：" + Thread.currentThread().getName());
        });
        
        // 直接调用run()：在main线程中执行
        thread.run(); // 输出：当前线程：main
    }
}
```

**特点**：
- 普通方法调用，不启动新线程
- 在**当前线程**中同步执行
- 可以重复调用

#### start()方法
```java
public class ThreadDemo {
    public static void main(String[] args) {
        Thread thread = new Thread(() -> {
            System.out.println("当前线程：" + Thread.currentThread().getName());
        });
        
        // 调用start()：创建新线程执行
        thread.start(); // 输出：当前线程：Thread-0
    }
}
```

**特点**：
- 启动新线程，由JVM调用`run()`
- 异步执行，立即返回
- 只能调用一次（重复调用抛`IllegalThreadStateException`）

#### start()源码分析
```java
public synchronized void start() {
    // 检查线程状态
    if (threadStatus != 0)
        throw new IllegalThreadStateException();

    // 加入线程组
    group.add(this);

    boolean started = false;
    try {
        start0(); // native方法，创建新线程
        started = true;
    } finally {
        try {
            if (!started) {
                group.threadStartFailed(this);
            }
        } catch (Throwable ignore) {
        }
    }
}

private native void start0(); // JVM调用run()
```

### 2. wait() vs sleep()

#### wait()方法

```java
public class WaitDemo {
    private static final Object lock = new Object();

    public static void main(String[] args) {
        new Thread(() -> {
            synchronized (lock) {
                System.out.println("线程1获取锁");
                try {
                    System.out.println("线程1释放锁，进入等待");
                    lock.wait(); // 释放锁，进入WAITING
                    System.out.println("线程1被唤醒，重新获取锁");
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }).start();

        new Thread(() -> {
            synchronized (lock) {
                System.out.println("线程2获取锁");
                lock.notify(); // 唤醒线程1
                System.out.println("线程2释放锁");
            }
        }).start();
    }
}
```

**特点**：
- **属于Object类**，必须在`synchronized`块中调用
- **释放锁**，让其他线程可以进入同步块
- 进入`WAITING`或`TIMED_WAITING`状态
- 被唤醒后需要**重新竞争锁**

#### sleep()方法

```java
public class SleepDemo {
    private static final Object lock = new Object();

    public static void main(String[] args) {
        new Thread(() -> {
            synchronized (lock) {
                System.out.println("线程1获取锁");
                try {
                    System.out.println("线程1休眠，但不释放锁");
                    Thread.sleep(2000); // 不释放锁，进入TIMED_WAITING
                    System.out.println("线程1醒来，仍持有锁");
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }).start();

        new Thread(() -> {
            synchronized (lock) {
                System.out.println("线程2获取锁"); // 需要等待线程1 sleep结束
            }
        }).start();
    }
}
```

**特点**：
- **属于Thread类**，可在任何地方调用
- **不释放锁**，继续持有
- 进入`TIMED_WAITING`状态
- 时间到期自动唤醒，无需其他线程通知

#### 核心区别

| 特性 | wait() | sleep() |
|------|--------|---------|
| 所属类 | Object | Thread |
| 锁处理 | 释放锁 | 不释放锁 |
| 使用场景 | synchronized块内 | 任何地方 |
| 唤醒方式 | notify/notifyAll | 超时自动 |
| 异常 | InterruptedException | InterruptedException |

### 3. notify() vs notifyAll()

#### notify()方法

```java
public class NotifyDemo {
    private static final Object lock = new Object();

    public static void main(String[] args) throws InterruptedException {
        // 启动3个等待线程
        for (int i = 1; i <= 3; i++) {
            int finalI = i;
            new Thread(() -> {
                synchronized (lock) {
                    System.out.println("线程" + finalI + "开始等待");
                    try {
                        lock.wait();
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                    System.out.println("线程" + finalI + "被唤醒");
                }
            }).start();
        }

        Thread.sleep(1000);

        // 只唤醒一个线程
        synchronized (lock) {
            lock.notify(); // 随机唤醒1个线程
        }
    }
}
```

**输出示例**：
```
线程1开始等待
线程2开始等待
线程3开始等待
线程2被唤醒  // 只有1个线程被唤醒
```

**特点**：
- 随机唤醒**一个**等待的线程
- 其他线程继续等待
- 性能更好，但可能导致**线程饥饿**

#### notifyAll()方法

```java
public class NotifyAllDemo {
    private static final Object lock = new Object();

    public static void main(String[] args) throws InterruptedException {
        // 启动3个等待线程
        for (int i = 1; i <= 3; i++) {
            int finalI = i;
            new Thread(() -> {
                synchronized (lock) {
                    System.out.println("线程" + finalI + "开始等待");
                    try {
                        lock.wait();
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                    System.out.println("线程" + finalI + "被唤醒");
                }
            }).start();
        }

        Thread.sleep(1000);

        // 唤醒所有线程
        synchronized (lock) {
            lock.notifyAll(); // 唤醒所有等待的线程
        }
    }
}
```

**输出示例**：
```
线程1开始等待
线程2开始等待
线程3开始等待
线程1被唤醒  // 所有线程都被唤醒
线程2被唤醒
线程3被唤醒
```

**特点**：
- 唤醒**所有**等待的线程
- 线程需要重新竞争锁
- 避免线程饥饿，但性能开销更大

#### 选择建议

```java
// 场景1：单一条件，使用notify()
class SingleCondition {
    private boolean ready = false;
    private final Object lock = new Object();

    public void waitForReady() throws InterruptedException {
        synchronized (lock) {
            while (!ready) {
                lock.wait();
            }
        }
    }

    public void setReady() {
        synchronized (lock) {
            ready = true;
            lock.notify(); // 只需唤醒一个
        }
    }
}

// 场景2：多个条件，使用notifyAll()
class MultiCondition {
    private int count = 0;
    private final Object lock = new Object();

    public void waitForCondition(int target) throws InterruptedException {
        synchronized (lock) {
            while (count < target) {
                lock.wait();
            }
        }
    }

    public void increment() {
        synchronized (lock) {
            count++;
            lock.notifyAll(); // 需要唤醒所有，让它们重新检查条件
        }
    }
}
```

**推荐**：
- **默认使用notifyAll()**，避免死锁和饥饿
- **性能敏感**且确保只有一个等待者时用`notify()`

## 线程安全与最佳实践

### 1. wait()必须在循环中使用

```java
// ❌ 错误用法
synchronized (lock) {
    if (!condition) {
        lock.wait(); // 可能虚假唤醒
    }
}

// ✅ 正确用法
synchronized (lock) {
    while (!condition) {
        lock.wait(); // 防止虚假唤醒
    }
}
```

**原因**：防止虚假唤醒（Spurious Wakeup）

### 2. 避免使用wait/notify，推荐Lock + Condition

```java
// 现代写法
class ModernWaitNotify {
    private final Lock lock = new ReentrantLock();
    private final Condition condition = lock.newCondition();

    public void await() throws InterruptedException {
        lock.lock();
        try {
            condition.await(); // 替代wait()
        } finally {
            lock.unlock();
        }
    }

    public void signal() {
        lock.lock();
        try {
            condition.signal(); // 替代notify()
        } finally {
            lock.unlock();
        }
    }
}
```

**优势**：
- 支持多个Condition，更灵活
- 可中断、可超时
- 更清晰的语义

## 答题总结

**面试标准答案**：

### run() vs start()
- **run()**：普通方法，当前线程同步执行
- **start()**：启动新线程，JVM异步调用run()

### wait() vs sleep()
- **wait()**：Object方法，释放锁，等待notify唤醒
- **sleep()**：Thread方法，不释放锁，超时自动唤醒

### notify() vs notifyAll()
- **notify()**：随机唤醒一个，可能饥饿
- **notifyAll()**：唤醒全部，安全但性能略差

**关键记忆点**：
1. **wait/notify/notifyAll**属于Object，必须在synchronized块中
2. **sleep**属于Thread，可在任何地方调用
3. **wait释放锁**，**sleep不释放锁**
4. **wait需要notify唤醒**，**sleep自动唤醒**
5. **生产环境推荐Lock + Condition**，替代wait/notify

