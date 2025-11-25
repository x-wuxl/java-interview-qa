---
layout: default
title: "有三个线程T1,T2,T3如何保证顺序执行？"
parent: 并发编程
nav_order: 268
description: "深入讲解多线程顺序执行的多种实现方案，包括join、wait/notify、CountDownLatch、Semaphore等方式的原理与应用"
author: "wuxl"
date: 2025-11-02
---
## 问题

有三个线程T1,T2,T3如何保证顺序执行？

## 答案

### 1. 核心概念

**线程顺序执行**是指在多线程环境下，确保多个线程按照指定的顺序完成任务。这是一个典型的**线程协调问题**，需要借助同步机制来实现线程之间的依赖关系。

常见的实现方式有：
- **Thread.join()**：最简单直接的方式
- **wait/notify**：基于对象监视器的经典方式
- **CountDownLatch**：JUC 包提供的倒计数门闩
- **Semaphore**：信号量控制执行顺序
- **ReentrantLock + Condition**：显式锁的条件变量

### 2. 多种实现方案

#### 2.1 方案一：Thread.join()

**原理**：`join()` 方法会让当前线程等待目标线程执行完毕后再继续执行。

```java
public class ThreadSequenceByJoin {
    public static void main(String[] args) {
        Thread t1 = new Thread(() -> {
            System.out.println("T1 执行");
        }, "T1");

        Thread t2 = new Thread(() -> {
            try {
                t1.join();  // 等待 T1 执行完毕
                System.out.println("T2 执行");
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }, "T2");

        Thread t3 = new Thread(() -> {
            try {
                t2.join();  // 等待 T2 执行完毕
                System.out.println("T3 执行");
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }, "T3");

        // 启动顺序无关紧要
        t3.start();
        t2.start();
        t1.start();
    }
}
```

**优点**：
- 代码简单，逻辑清晰
- 不需要额外的同步工具

**缺点**：
- 线程之间存在强依赖关系（T2 必须知道 T1，T3 必须知道 T2）
- 灵活性差，不适合复杂的协调场景

#### 2.2 方案二：wait/notify

**原理**：使用对象的 `wait()` 和 `notify()` 方法进行线程间通信。

```java
public class ThreadSequenceByWaitNotify {
    private static final Object lock = new Object();
    private static int currentThread = 1;  // 当前应该执行的线程

    public static void main(String[] args) {
        Thread t1 = new Thread(new Task(1, 2), "T1");
        Thread t2 = new Thread(new Task(2, 3), "T2");
        Thread t3 = new Thread(new Task(3, 1), "T3");

        t1.start();
        t2.start();
        t3.start();
    }

    static class Task implements Runnable {
        private int threadNum;
        private int nextThreadNum;

        public Task(int threadNum, int nextThreadNum) {
            this.threadNum = threadNum;
            this.nextThreadNum = nextThreadNum;
        }

        @Override
        public void run() {
            synchronized (lock) {
                while (currentThread != threadNum) {
                    try {
                        lock.wait();  // 不是自己的执行顺序，等待
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                }

                // 执行任务
                System.out.println("T" + threadNum + " 执行");

                // 通知下一个线程
                currentThread = nextThreadNum;
                lock.notifyAll();
            }
        }
    }
}
```

**优点**：
- 可以实现复杂的线程协调逻辑
- 线程之间解耦，无需相互引用

**缺点**：
- 代码较复杂，容易出错
- 必须在 synchronized 块中使用

#### 2.3 方案三：CountDownLatch

**原理**：CountDownLatch 是一个倒计数门闩，当计数器减到 0 时，所有等待的线程会被释放。

```java
public class ThreadSequenceByCountDownLatch {
    public static void main(String[] args) {
        CountDownLatch latch1 = new CountDownLatch(1);
        CountDownLatch latch2 = new CountDownLatch(1);

        Thread t1 = new Thread(() -> {
            System.out.println("T1 执行");
            latch1.countDown();  // T1 完成，释放 latch1
        }, "T1");

        Thread t2 = new Thread(() -> {
            try {
                latch1.await();  // 等待 T1 完成
                System.out.println("T2 执行");
                latch2.countDown();  // T2 完成，释放 latch2
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }, "T2");

        Thread t3 = new Thread(() -> {
            try {
                latch2.await();  // 等待 T2 完成
                System.out.println("T3 执行");
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }, "T3");

        // 启动顺序无关紧要
        t3.start();
        t2.start();
        t1.start();
    }
}
```

**优点**：
- 代码清晰，语义明确
- JUC 包的标准工具，性能好
- 支持超时等待

**缺点**：
- CountDownLatch 不可重用（一次性使用）
- 需要创建多个 Latch 对象

#### 2.4 方案四：Semaphore

**原理**：Semaphore 信号量可以控制同时访问资源的线程数量，初始许可设为 0 可实现顺序执行。

```java
public class ThreadSequenceBySemaphore {
    public static void main(String[] args) {
        Semaphore semaphore1 = new Semaphore(1);  // T1 初始可执行
        Semaphore semaphore2 = new Semaphore(0);  // T2 初始阻塞
        Semaphore semaphore3 = new Semaphore(0);  // T3 初始阻塞

        Thread t1 = new Thread(() -> {
            try {
                semaphore1.acquire();  // 获取许可
                System.out.println("T1 执行");
                semaphore2.release();  // 释放许可给 T2
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }, "T1");

        Thread t2 = new Thread(() -> {
            try {
                semaphore2.acquire();  // 等待 T1 释放许可
                System.out.println("T2 执行");
                semaphore3.release();  // 释放许可给 T3
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }, "T2");

        Thread t3 = new Thread(() -> {
            try {
                semaphore3.acquire();  // 等待 T2 释放许可
                System.out.println("T3 执行");
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }, "T3");

        // 启动顺序无关紧要
        t3.start();
        t2.start();
        t1.start();
    }
}
```

**优点**：
- 语义清晰，表达"许可传递"的概念
- 可以控制并发度
- 可以多次使用

**缺点**：
- 相对复杂，需要理解信号量的语义

#### 2.5 方案五：ReentrantLock + Condition

**原理**：使用显式锁和条件变量实现更灵活的线程协调。

```java
public class ThreadSequenceByLockCondition {
    private static ReentrantLock lock = new ReentrantLock();
    private static Condition condition1 = lock.newCondition();
    private static Condition condition2 = lock.newCondition();
    private static Condition condition3 = lock.newCondition();
    private static int currentThread = 1;

    public static void main(String[] args) {
        Thread t1 = new Thread(() -> {
            lock.lock();
            try {
                while (currentThread != 1) {
                    condition1.await();
                }
                System.out.println("T1 执行");
                currentThread = 2;
                condition2.signal();  // 唤醒 T2
            } catch (InterruptedException e) {
                e.printStackTrace();
            } finally {
                lock.unlock();
            }
        }, "T1");

        Thread t2 = new Thread(() -> {
            lock.lock();
            try {
                while (currentThread != 2) {
                    condition2.await();
                }
                System.out.println("T2 执行");
                currentThread = 3;
                condition3.signal();  // 唤醒 T3
            } catch (InterruptedException e) {
                e.printStackTrace();
            } finally {
                lock.unlock();
            }
        }, "T2");

        Thread t3 = new Thread(() -> {
            lock.lock();
            try {
                while (currentThread != 3) {
                    condition3.await();
                }
                System.out.println("T3 执行");
            } catch (InterruptedException e) {
                e.printStackTrace();
            } finally {
                lock.unlock();
            }
        }, "T3");

        t1.start();
        t2.start();
        t3.start();
    }
}
```

**优点**：
- 非常灵活，可以实现复杂的协调逻辑
- 支持多个条件变量，精准唤醒
- 可以避免虚假唤醒

**缺点**：
- 代码相对复杂
- 需要显式加锁和解锁

### 3. 方案对比与选型

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **Thread.join()** | 简单顺序执行 | 简单直观 | 线程强依赖，不灵活 |
| **wait/notify** | 复杂协调逻辑 | 灵活，经典方式 | 容易出错，必须在 synchronized 中 |
| **CountDownLatch** | 一次性顺序执行 | 语义清晰，性能好 | 不可重用 |
| **Semaphore** | 需要重复执行 | 可重用，控制并发度 | 需要理解信号量语义 |
| **Lock + Condition** | 复杂协调，精准唤醒 | 最灵活，支持多条件 | 代码复杂，需要显式管理锁 |

### 4. 性能与实战考量

#### 4.1 性能对比

- **join()**：最简单，性能开销最小
- **CountDownLatch/Semaphore**：基于 AQS，性能优秀
- **wait/notify**：涉及重量级锁（synchronized），性能较低
- **Lock + Condition**：基于 AQS，性能好，但代码复杂

#### 4.2 生产环境建议

**推荐方案**：
1. **简单场景**：使用 `Thread.join()` 或 `CountDownLatch`
2. **需要重复执行**：使用 `Semaphore` 或 `CyclicBarrier`
3. **复杂协调逻辑**：使用 `Lock + Condition`

**注意事项**：
- 避免死锁：确保锁的获取和释放顺序一致
- 异常处理：确保在 finally 块中释放资源
- 超时机制：考虑使用带超时的 `await/tryAcquire` 方法，避免永久阻塞

#### 4.3 扩展场景：循环顺序执行

如果需要 T1 → T2 → T3 → T1 → T2 → T3 ... 循环执行，推荐使用 **Semaphore** 或 **CyclicBarrier**。

```java
public class ThreadSequenceCyclic {
    private static Semaphore semaphore1 = new Semaphore(1);
    private static Semaphore semaphore2 = new Semaphore(0);
    private static Semaphore semaphore3 = new Semaphore(0);

    public static void main(String[] args) {
        new Thread(new Task(semaphore1, semaphore2, "T1")).start();
        new Thread(new Task(semaphore2, semaphore3, "T2")).start();
        new Thread(new Task(semaphore3, semaphore1, "T3")).start();
    }

    static class Task implements Runnable {
        private Semaphore current;
        private Semaphore next;
        private String name;

        public Task(Semaphore current, Semaphore next, String name) {
            this.current = current;
            this.next = next;
            this.name = name;
        }

        @Override
        public void run() {
            for (int i = 0; i < 10; i++) {  // 循环 10 次
                try {
                    current.acquire();
                    System.out.println(name + " 执行第 " + (i + 1) + " 次");
                    Thread.sleep(100);
                    next.release();
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }
    }
}
```

### 5. 总结

实现三个线程顺序执行的核心是**线程间协调与同步**，常见方案有：

1. **Thread.join()**：
   - 最简单的方式，适合一次性顺序执行
   - 线程之间存在强依赖

2. **wait/notify**：
   - 经典的线程通信方式
   - 适合复杂协调逻辑，但容易出错

3. **CountDownLatch**（推荐）：
   - JUC 包的标准工具，语义清晰
   - 适合一次性顺序执行，性能好

4. **Semaphore**：
   - 可重用，适合循环顺序执行
   - 语义清晰，表达"许可传递"

5. **Lock + Condition**：
   - 最灵活的方式，支持复杂协调逻辑
   - 代码复杂，适合高级场景

**面试要点**：
- 能说出至少 3 种实现方式
- 理解各方案的原理与适用场景
- 推荐使用 JUC 包的工具（CountDownLatch/Semaphore）
- 能扩展到循环顺序执行的场景

**实战建议**：
- 简单场景优先使用 CountDownLatch
- 需要重复执行使用 Semaphore
- 复杂场景使用 Lock + Condition
- 注意异常处理和超时机制，避免死锁

