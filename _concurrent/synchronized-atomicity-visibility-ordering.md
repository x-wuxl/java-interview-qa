---
title: "synchronized是如何保证原子性、可见性、有序性的？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [synchronized, JMM, 内存模型, 线程安全]
description: "深入分析synchronized如何通过JMM内存模型保证并发三大特性：原子性、可见性和有序性"
nav_order: 212
parent: 并发编程
---
# synchronized是如何保证原子性、可见性、有序性的？

## 核心概念

并发编程的三大特性是保证线程安全的基础，`synchronized` 通过 **Java 内存模型（JMM）** 和 **Monitor 机制** 同时保证了这三个特性，是 Java 中最强的同步原语。

## 1. 原子性（Atomicity）

### 保证机制

通过 **互斥锁** 保证同一时刻只有一个线程执行临界区代码。

### 实现原理

- **monitorenter/monitorexit**：底层依赖操作系统的互斥量
- **Monitor 所有权**：同一时刻只有一个线程持有 Monitor
- **阻塞机制**：未获取锁的线程进入 `_EntryList` 阻塞等待

### 示例

```java
public class AtomicityDemo {
    private int count = 0;

    // 整个方法作为原子操作
    public synchronized void increment() {
        count++;  // 复合操作：读取 -> 加1 -> 写入
    }
}
```

**关键点**：虽然 `count++` 本身不是原子操作（包含读、改、写三步），但被 `synchronized` 保护后，整个方法成为原子操作，不会被其他线程打断。

## 2. 可见性（Visibility）

### 保证机制

通过 **内存屏障** 和 **JMM 的 happens-before 规则** 保证变量修改对其他线程立即可见。

### JMM 规定

根据 **Java 内存模型**：

1. **加锁时**（monitorenter）：
   - 清空工作内存中的共享变量副本
   - 从主内存重新读取最新值

2. **解锁时**（monitorexit）：
   - 将工作内存中的修改刷新回主内存
   - 保证其他线程能看到最新值

3. **happens-before 规则**：
   - 对一个锁的解锁 happens-before 后续对这个锁的加锁
   - 前一个线程的修改对后一个线程可见

### 示例

```java
public class VisibilityDemo {
    private boolean flag = false;
    private int number = 0;

    // 线程A
    public synchronized void writer() {
        number = 42;
        flag = true;  // 解锁时刷新到主内存
    }

    // 线程B
    public synchronized void reader() {
        if (flag) {  // 加锁时从主内存读取
            System.out.println(number);  // 一定能看到42
        }
    }
}
```

**关键点**：synchronized 解锁前的所有写操作，对后续获取同一个锁的线程可见。

## 3. 有序性（Ordering）

### 保证机制

通过 **内存屏障** 和 **as-if-serial 语义** 防止指令重排序导致的问题。

### 实现原理

1. **临界区内部**：
   - 允许重排序，但遵循 as-if-serial 语义
   - 单线程视角下执行结果不变

2. **临界区边界**：
   - 禁止临界区内的代码重排到临界区外
   - 禁止临界区外的代码重排到临界区内

3. **内存屏障**：
   - **LoadLoad 屏障**（加锁后）：禁止后续读操作重排到加锁前
   - **StoreStore 屏障**（解锁前）：禁止前面写操作重排到解锁后

### 示例

```java
public class OrderingDemo {
    private int a = 0;
    private int b = 0;
    private final Object lock = new Object();

    public void method1() {
        a = 1;  // ①
        b = 2;  // ②
        synchronized(lock) {  // ③ monitorenter
            int c = a + b;    // ④ 
        }  // ⑤ monitorexit
    }
}
```

**重排序约束**：
- ① 和 ② 可能重排（临界区外）
- ④ 不能重排到 ③ 之前（临界区内代码不能重排到加锁前）
- ③ 之后读取的 a、b 一定是最新值（内存屏障保证）

## 底层实现总结

### 字节码 + 内存屏障

```
monitorenter    // 加锁
LoadLoad屏障    // 禁止后续读操作重排到加锁前
临界区代码
StoreStore屏障  // 禁止前面写操作重排到解锁后
monitorexit     // 解锁（刷新主内存）
```

### Happens-Before 规则

```
线程A：
  write(x) → unlock(m)
            ↓ happens-before
线程B：
  lock(m) → read(x)
```

## 对比 volatile

| 特性     | synchronized           | volatile          |
|----------|------------------------|-------------------|
| 原子性   | ✅ 保证复合操作原子性   | ❌ 仅保证单次读写  |
| 可见性   | ✅ 保证                | ✅ 保证           |
| 有序性   | ✅ 保证（禁止重排）     | ✅ 保证（禁止重排）|
| 性能     | 较重（涉及上下文切换）  | 较轻（内存屏障）   |
| 阻塞     | 阻塞等待               | 不阻塞            |

## 答题总结

1. **原子性**：通过 Monitor 互斥锁，同一时刻只有一个线程执行临界区代码
2. **可见性**：
   - 加锁时清空本地缓存，从主内存读取最新值
   - 解锁时刷新修改到主内存
   - 遵循 happens-before 规则
3. **有序性**：
   - 插入内存屏障禁止指令重排序
   - 临界区内外代码不能互相重排
   - 内部遵循 as-if-serial 语义

synchronized 是 Java 中最强的同步手段，一次性保证三大特性，但性能开销相对较大，JVM 通过锁优化（偏向锁、轻量级锁）来降低成本。

