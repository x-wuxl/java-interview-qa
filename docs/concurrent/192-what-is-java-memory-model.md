---
layout: default
title: "什么是Java内存模型（JMM）？"
parent: 并发编程
nav_order: 192
description: "深入理解Java内存模型（JMM）的核心概念、作用及其在并发编程中的重要性"
date: 2025-11-02
---
## 核心概念

**Java内存模型（Java Memory Model，JMM）** 是一种抽象的规范，定义了多线程环境下共享变量的访问规则，以及如何在并发场景中保证**可见性**、**有序性**和**原子性**。

JMM并不是真实存在的物理模型，而是一套规则，用于屏蔽不同硬件和操作系统内存访问差异，为开发者提供统一的并发编程语义。

---

## 核心原理

### 1. 内存结构抽象

JMM将内存分为两部分：

- **主内存（Main Memory）**：所有线程共享的内存区域，存储共享变量的主副本
- **工作内存（Working Memory）**：每个线程私有的内存区域，存储该线程使用的共享变量的副本

线程对共享变量的操作流程：
1. 线程从主内存读取变量到工作内存
2. 在工作内存中进行修改
3. 将修改后的值写回主内存

### 2. 三大特性

#### 可见性
一个线程修改了共享变量，其他线程能立即看到修改后的值。

```java
// 使用 volatile 保证可见性
public class VisibilityExample {
    private volatile boolean flag = false;
    
    public void writer() {
        flag = true; // 修改立即对其他线程可见
    }
    
    public void reader() {
        while (!flag) {
            // 能及时看到 flag 的变化
        }
        System.out.println("Flag is true");
    }
}
```

#### 有序性
程序执行的顺序按照代码的先后顺序执行，但JVM可能会进行指令重排序优化。JMM通过happens-before规则保证必要的有序性。

```java
// 可能发生指令重排序
int a = 1;  // 操作1
int b = 2;  // 操作2
// 在某些情况下，操作2可能先于操作1执行
```

#### 原子性
一个操作或多个操作要么全部执行完成且不被中断，要么全部不执行。

```java
// 非原子操作
int count = 0;
count++; // 分为三步：读取、加1、写回

// 使用 synchronized 保证原子性
public synchronized void increment() {
    count++;
}
```

### 3. 八大原子操作

JMM定义了8种原子操作，用于描述主内存与工作内存之间的交互：

- **lock（锁定）**：作用于主内存变量，标识为线程独占
- **unlock（解锁）**：作用于主内存变量，释放独占状态
- **read（读取）**：从主内存读取变量到工作内存
- **load（载入）**：将read的值放入工作内存副本
- **use（使用）**：将工作内存变量传递给执行引擎
- **assign（赋值）**：将执行引擎的值赋给工作内存变量
- **store（存储）**：将工作内存变量传送到主内存
- **write（写入）**：将store的值放入主内存变量

---

## 并发场景考量

### 1. 缓存一致性问题

在多核CPU环境下，每个核心都有自己的缓存，JMM需要保证多个线程看到的共享变量值是一致的。

### 2. 指令重排序问题

编译器和处理器为了优化性能，可能会对指令进行重排序。JMM通过内存屏障和happens-before规则来限制重排序，保证程序的正确性。

### 3. 分布式场景的延伸

虽然JMM主要解决单JVM内的并发问题，但在分布式系统中：
- 需要使用分布式锁（如Redis、Zookeeper）
- 需要考虑网络延迟导致的可见性问题
- 需要引入分布式缓存一致性协议

---

## 实践总结

### 面试要点

1. **JMM是什么**：一套规范，定义共享变量访问规则，保证可见性、有序性、原子性
2. **为什么需要JMM**：屏蔽硬件和OS差异，提供统一的并发编程模型
3. **如何使用**：通过volatile、synchronized、Lock等关键字/工具实现JMM规范
4. **三大特性**：可见性、有序性、原子性

### 关键工具

```java
// 1. volatile - 保证可见性和有序性
private volatile int status;

// 2. synchronized - 保证三大特性
public synchronized void method() {
    // 原子操作
}

// 3. Lock接口 - 更灵活的锁机制
private final Lock lock = new ReentrantLock();
public void method() {
    lock.lock();
    try {
        // 原子操作
    } finally {
        lock.unlock();
    }
}

// 4. Atomic类 - 利用CAS实现原子操作
private AtomicInteger count = new AtomicInteger(0);
count.incrementAndGet();
```

### 答题建议

面试时可以从"**是什么 → 为什么 → 怎么用**"的思路回答：
1. JMM是Java并发编程的理论基础
2. 解决了多线程环境下的可见性、有序性、原子性问题
3. 通过volatile、synchronized等机制实现
4. 在实际项目中需要根据场景选择合适的并发控制手段

