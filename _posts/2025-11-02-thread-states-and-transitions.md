---
layout: post
title: "线程有几种状态，状态之间的流转是怎样的？"
date: 2025-11-02
categories: [并发编程, 线程基础]
tags: [Java, 多线程, 线程状态, Thread.State]
description: "详解Java线程的6种状态及其转换关系，结合源码分析线程生命周期，理解NEW、RUNNABLE、BLOCKED、WAITING、TIMED_WAITING、TERMINATED的本质。"
---

## 核心概念

Java线程有**6种状态**，定义在`Thread.State`枚举中：

1. **NEW**（新建）
2. **RUNNABLE**（可运行）
3. **BLOCKED**（阻塞）
4. **WAITING**（等待）
5. **TIMED_WAITING**（超时等待）
6. **TERMINATED**（终止）

## 状态详解与转换

### 状态转换图

```
         NEW
          |
        start()
          ↓
      RUNNABLE ←─────────────┐
       ↙  ↓  ↘               │
   BLOCKED WAITING TIMED_WAITING
       ↘  ↓  ↙               │
      RUNNABLE                │
          ↓                   │
      TERMINATED ──────────────┘
```

### 1. NEW（新建）

```java
Thread thread = new Thread(() -> {});
// 此时状态为 NEW
System.out.println(thread.getState()); // NEW
```

**特点**：线程对象已创建，但尚未调用`start()`方法。

### 2. RUNNABLE（可运行）

```java
thread.start();
// 此时状态为 RUNNABLE
System.out.println(thread.getState()); // RUNNABLE
```

**特点**：
- 包含操作系统层面的**Running**和**Ready**两种状态
- 线程可能正在执行，也可能在等待CPU时间片
- Java不区分这两种状态，统一为RUNNABLE

**进入方式**：
- `NEW` → 调用`start()` → `RUNNABLE`
- `BLOCKED/WAITING/TIMED_WAITING` → 条件满足 → `RUNNABLE`

### 3. BLOCKED（阻塞）

```java
synchronized(lock) {
    // 如果锁被占用，当前线程进入BLOCKED状态
}
```

**特点**：等待获取`synchronized`锁（Monitor）

**进入方式**：
- 尝试进入`synchronized`代码块/方法，但锁被其他线程持有

**退出方式**：
- 获取到锁 → `RUNNABLE`

### 4. WAITING（无限等待）

```java
// 方式1：Object.wait()
synchronized(lock) {
    lock.wait(); // 进入WAITING，释放锁
}

// 方式2：Thread.join()
thread.join(); // 等待thread线程结束

// 方式3：LockSupport.park()
LockSupport.park(); // 进入WAITING
```

**特点**：
- 无限期等待，直到被显式唤醒
- `wait()`会释放锁，`park()`不涉及锁

**进入方式**：
- `Object.wait()`（无超时参数）
- `Thread.join()`（无超时参数）
- `LockSupport.park()`

**退出方式**：
- `Object.notify()/notifyAll()`
- 被等待的线程执行完毕
- `LockSupport.unpark()`

### 5. TIMED_WAITING（超时等待）

```java
// 方式1：Thread.sleep()
Thread.sleep(1000); // 进入TIMED_WAITING，不释放锁

// 方式2：Object.wait(timeout)
synchronized(lock) {
    lock.wait(1000); // 进入TIMED_WAITING，释放锁
}

// 方式3：Thread.join(timeout)
thread.join(1000);

// 方式4：LockSupport.parkNanos()/parkUntil()
LockSupport.parkNanos(1000000000L); // 1秒
```

**特点**：
- 有超时时间，到期自动唤醒
- `sleep()`不释放锁，`wait(timeout)`释放锁

**退出方式**：
- 超时时间到期
- 被提前唤醒（`notify()`/`unpark()`）

### 6. TERMINATED（终止）

```java
// 线程执行完run()方法，或抛出未捕获异常
```

**特点**：
- 线程执行结束，生命周期终结
- 不可重新启动（再次调用`start()`会抛`IllegalThreadStateException`）

## 源码关键点

### Thread.State源码

```java
public enum State {
    NEW,           // 初始状态
    RUNNABLE,      // 运行状态
    BLOCKED,       // 阻塞状态（等待锁）
    WAITING,       // 等待状态（无限期）
    TIMED_WAITING, // 超时等待
    TERMINATED;    // 终止状态
}
```

### 状态检查

```java
public State getState() {
    // 由JVM实现，返回线程当前状态
    return jdk.internal.misc.VM.toThreadState(threadStatus);
}
```

## 面试常见陷阱

### 1. BLOCKED vs WAITING

| 状态 | 触发场景 | 是否释放锁 |
|------|---------|----------|
| BLOCKED | 等待`synchronized`锁 | 未持有锁 |
| WAITING | `wait()`/`join()`/`park()` | `wait()`释放锁 |

### 2. sleep() vs wait()

```java
// sleep：TIMED_WAITING，不释放锁
synchronized(lock) {
    Thread.sleep(1000); // 仍持有lock
}

// wait：WAITING，释放锁
synchronized(lock) {
    lock.wait(); // 释放lock，其他线程可进入
}
```

### 3. RUNNABLE的双重含义

```java
// RUNNABLE包含两种操作系统状态：
// 1. Ready：在就绪队列，等待CPU调度
// 2. Running：正在CPU上执行
// Java层面无法区分，统一为RUNNABLE
```

## 答题总结

**面试标准答案**：

Java线程有**6种状态**：
1. **NEW**：创建未启动
2. **RUNNABLE**：可运行（含Running和Ready）
3. **BLOCKED**：等待synchronized锁
4. **WAITING**：无限期等待（wait/join/park）
5. **TIMED_WAITING**：超时等待（sleep/wait(timeout)）
6. **TERMINATED**：执行结束

**关键流转**：
- `NEW` → `start()` → `RUNNABLE`
- `RUNNABLE` → 等待锁 → `BLOCKED` → 获取锁 → `RUNNABLE`
- `RUNNABLE` → `wait()/park()` → `WAITING` → `notify()/unpark()` → `RUNNABLE`
- `RUNNABLE` → `sleep()/wait(timeout)` → `TIMED_WAITING` → 超时/唤醒 → `RUNNABLE`
- `RUNNABLE` → 执行完毕 → `TERMINATED`

**核心区别**：
- **BLOCKED**是被动等锁，**WAITING**是主动等待
- **sleep()**不释放锁，**wait()**释放锁
- **RUNNABLE**包含操作系统的就绪和运行两种状态

