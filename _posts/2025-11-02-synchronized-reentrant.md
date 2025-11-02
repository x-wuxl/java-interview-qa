---
layout: post
title: "synchronized是否可重入"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [synchronized, 可重入锁, 递归, 并发安全]
description: "详解synchronized的可重入特性，包括原理、应用场景和重入计数器机制"
---

# synchronized是否可重入

## 核心答案

**是的，synchronized 是可重入锁**（Reentrant Lock）。同一个线程可以多次获取同一把锁，而不会造成死锁。

---

## 什么是可重入？

### 定义

**可重入锁**：同一线程在持有锁的情况下，可以再次获取该锁，而不会被自己阻塞。

### 为什么需要可重入？

```java
public class Counter {
    private int count = 0;
    
    // 方法A：持有锁
    public synchronized void increment() {
        count++;
        print();  // ⚠️ 调用另一个 synchronized 方法
    }
    
    // 方法B：需要同一把锁
    public synchronized void print() {
        System.out.println(count);
    }
}
```

**如果不可重入**：
```
线程1 调用 increment()
→ 获取 this 锁
→ 调用 print()
→ 尝试获取 this 锁（已被自己持有）
→ ❌ 死锁！（自己阻塞自己）
```

**可重入的好处**：
```
线程1 调用 increment()
→ 获取 this 锁（计数器 = 1）
→ 调用 print()
→ 再次获取 this 锁（计数器 = 2）
→ print() 执行完，释放锁（计数器 = 1）
→ increment() 执行完，释放锁（计数器 = 0）
→ ✅ 正常执行
```

---

## 可重入的实现原理

### 1. 重入计数器

每个锁都关联一个**重入计数器**（Recursion Counter）和**持有线程**（Owner Thread）。

#### 数据结构

```cpp
// HotSpot ObjectMonitor 结构
ObjectMonitor {
    _owner       = Thread-1;    // 持有锁的线程
    _recursions  = 2;           // 重入次数
    _EntryList   = [];          // 等待队列
    _count       = 1;           // 计数器
}
```

#### 加锁流程

```java
monitorenter(obj) {
    Thread current = Thread.currentThread();
    
    // 情况1：无人持有锁
    if (obj.monitor._owner == null) {
        obj.monitor._owner = current;
        obj.monitor._recursions = 1;  // ✅ 初始化计数器
        return;
    }
    
    // 情况2：当前线程已持有锁（可重入）
    if (obj.monitor._owner == current) {
        obj.monitor._recursions++;  // ✅ 计数器加1
        return;
    }
    
    // 情况3：其他线程持有锁
    // 进入 _EntryList 阻塞等待
}
```

#### 解锁流程

```java
monitorexit(obj) {
    Thread current = Thread.currentThread();
    
    // 计数器减1
    obj.monitor._recursions--;
    
    // 只有计数器为0时才真正释放锁
    if (obj.monitor._recursions == 0) {
        obj.monitor._owner = null;  // ✅ 释放锁
        // 唤醒 _EntryList 中的线程
    }
}
```

---

## 可重入的典型场景

### 场景1：同步方法调用同步方法

```java
public class Account {
    private int balance = 1000;
    
    // 同步方法1
    public synchronized void withdraw(int amount) {
        if (checkBalance(amount)) {  // ✅ 可重入
            balance -= amount;
        }
    }
    
    // 同步方法2
    public synchronized boolean checkBalance(int amount) {
        return balance >= amount;
    }
}

// 执行流程
account.withdraw(100);
// → 获取 account 锁（计数器 = 1）
// → 调用 checkBalance()
// → 再次获取 account 锁（计数器 = 2）✅
// → checkBalance() 返回（计数器 = 1）
// → withdraw() 返回（计数器 = 0，释放锁）
```

### 场景2：递归调用

```java
public class RecursiveCounter {
    private int count = 0;
    
    public synchronized void countDown(int n) {
        if (n <= 0) return;
        
        count++;
        System.out.println("Count: " + count);
        
        countDown(n - 1);  // ✅ 递归调用，可重入
    }
}

// 执行流程
counter.countDown(3);
// → 第1次：获取锁（计数器 = 1）
// → 第2次：递归获取锁（计数器 = 2）
// → 第3次：递归获取锁（计数器 = 3）
// → 第3次返回：释放锁（计数器 = 2）
// → 第2次返回：释放锁（计数器 = 1）
// → 第1次返回：释放锁（计数器 = 0）
```

### 场景3：继承关系

```java
public class Parent {
    public synchronized void doSomething() {
        System.out.println("Parent");
    }
}

public class Child extends Parent {
    @Override
    public synchronized void doSomething() {
        super.doSomething();  // ✅ 可重入
        System.out.println("Child");
    }
}

// 执行流程
Child child = new Child();
child.doSomething();
// → 获取 child 对象锁（计数器 = 1）
// → 调用 super.doSomething()
// → 再次获取 child 对象锁（计数器 = 2）✅
// → 父类方法返回（计数器 = 1）
// → 子类方法返回（计数器 = 0）
```

---

## 字节码层面的体现

### 源代码

```java
public class ReentrantDemo {
    public synchronized void method1() {
        method2();
    }
    
    public synchronized void method2() {
        System.out.println("Hello");
    }
}
```

### 字节码分析

```
method1() 的字节码：
  flags: ACC_PUBLIC, ACC_SYNCHRONIZED
  Code:
    0: aload_0
    1: invokevirtual #2    // method2()
    4: return

method2() 的字节码：
  flags: ACC_PUBLIC, ACC_SYNCHRONIZED
  Code:
    0: getstatic     #3    // System.out
    3: ldc           #4    // "Hello"
    5: invokevirtual #5    // println()
    8: return
```

**关键点**：
- 两个方法都有 `ACC_SYNCHRONIZED` 标志
- JVM 在方法调用时自动处理重入逻辑
- 不需要额外的字节码指令

---

## 不可重入锁的问题示例

### 假设 synchronized 不可重入

```java
public class NonReentrantExample {
    public synchronized void outer() {
        System.out.println("Outer start");
        inner();  // ❌ 死锁！
        System.out.println("Outer end");
    }
    
    public synchronized void inner() {
        System.out.println("Inner");
    }
}

// 执行结果（如果不可重入）
outer()
// → 获取锁
// → 调用 inner()
// → 尝试获取锁（被自己持有）
// → 永久阻塞（死锁）
```

**现实中的可重入**：
```
outer()
// → 获取锁（计数器 = 1）
// → 调用 inner()
// → 重入获取锁（计数器 = 2）✅
// → inner() 返回（计数器 = 1）
// → outer() 返回（计数器 = 0）
```

---

## 源码层面的实现

### HotSpot 源码片段

```cpp
// src/hotspot/share/runtime/objectMonitor.cpp

void ObjectMonitor::enter(TRAPS) {
    Thread * const Self = THREAD;
    void * cur = Atomic::cmpxchg(Self, &_owner, (void*)NULL);
    
    if (cur == NULL) {
        // 无人持有，直接获取
        return;
    }
    
    // ✅ 检查是否为当前线程（可重入判断）
    if (cur == Self) {
        _recursions++;  // 重入计数器加1
        return;
    }
    
    // 其他线程持有，进入等待队列
    EnterI(THREAD);
}

void ObjectMonitor::exit(bool not_suspended, TRAPS) {
    Thread * const Self = THREAD;
    
    // ✅ 重入计数器减1
    if (_recursions != 0) {
        _recursions--;
        return;  // 还有重入，不释放锁
    }
    
    // 计数器为0，真正释放锁
    OrderAccess::release_store(&_owner, (void*)NULL);
    
    // 唤醒等待队列中的线程
    ExitEpilog(Self, wakee);
}
```

---

## 性能考虑

### 重入的开销

```java
// 测试代码
public class ReentrantBenchmark {
    
    @Benchmark
    public void singleEntry() {
        synchronized(this) {
            // 单次加锁：~20 ns
        }
    }
    
    @Benchmark
    public void reentrant10Times() {
        synchronized(this) {
            reentrantHelper(10);
        }
    }
    
    private void reentrantHelper(int depth) {
        if (depth <= 0) return;
        synchronized(this) {
            // 每次重入：~5 ns（只需检查线程ID + 计数器加1）
            reentrantHelper(depth - 1);
        }
    }
}
```

**结论**：
- 首次加锁：~20 ns（CAS 操作）
- 重入加锁：~5 ns（仅递增计数器）
- 重入的开销很小，无需担心性能问题

---

## 对比其他锁

### ReentrantLock 的可重入

```java
ReentrantLock lock = new ReentrantLock();

public void method1() {
    lock.lock();  // 获取锁（计数器 = 1）
    try {
        method2();
    } finally {
        lock.unlock();  // 计数器 - 1
    }
}

public void method2() {
    lock.lock();  // ✅ 可重入（计数器 = 2）
    try {
        System.out.println("Hello");
    } finally {
        lock.unlock();  // 计数器 - 1
    }
}
```

**实现原理相同**：
- AQS（AbstractQueuedSynchronizer）内部维护 `state` 计数器
- 每次重入 `state++`
- 每次释放 `state--`
- `state == 0` 时真正释放锁

### 不可重入锁（非标准）

某些自定义锁可能不支持重入：

```java
// ❌ 不可重入的简单自旋锁
public class NonReentrantSpinLock {
    private AtomicBoolean locked = new AtomicBoolean(false);
    
    public void lock() {
        while (!locked.compareAndSet(false, true)) {
            // 自旋等待
        }
    }
    
    public void unlock() {
        locked.set(false);
    }
}

// 问题示例
lock.lock();
lock.lock();  // ❌ 死锁！（自己阻塞自己）
```

**改进为可重入**：

```java
// ✅ 可重入自旋锁
public class ReentrantSpinLock {
    private AtomicReference<Thread> owner = new AtomicReference<>();
    private int recursions = 0;
    
    public void lock() {
        Thread current = Thread.currentThread();
        
        // 检查是否为当前线程（可重入）
        if (owner.get() == current) {
            recursions++;
            return;
        }
        
        // CAS 获取锁
        while (!owner.compareAndSet(null, current)) {
            // 自旋等待
        }
        recursions = 1;
    }
    
    public void unlock() {
        Thread current = Thread.currentThread();
        
        if (owner.get() != current) {
            throw new IllegalMonitorStateException();
        }
        
        if (--recursions == 0) {
            owner.set(null);  // 释放锁
        }
    }
}
```

---

## 常见误区

### 误区1：不同对象的锁可以重入

```java
Object lock1 = new Object();
Object lock2 = new Object();

synchronized(lock1) {
    synchronized(lock2) {  // ❌ 这不是重入！
        // 这是获取不同的锁
    }
}
```

**正确理解**：
- 可重入指的是**同一把锁**的多次获取
- 不同对象的锁是**不同的锁**，不是重入

### 误区2：忘记释放导致计数器错误

```java
// ❌ 错误示例
public synchronized void method() {
    try {
        // ...
    } catch (Exception e) {
        return;  // 提前返回，monitorexit 仍会执行
    }
    // 正常返回，monitorexit 执行
}
```

**说明**：
- synchronized 由 JVM 保证释放，不会有计数器错误
- 但 ReentrantLock 需要手动在 finally 中释放

---

## 答题总结

**问题**：synchronized 是否可重入？

**回答**：

是的，synchronized 是**可重入锁**。

**含义**：同一线程可以多次获取同一把锁，而不会被自己阻塞。

**实现原理**：
1. 每个 Monitor 对象维护两个关键字段：
   - `_owner`：持有锁的线程
   - `_recursions`：重入计数器

2. 加锁时：
   - 如果 `_owner` 为空，设置为当前线程，计数器 = 1
   - 如果 `_owner` 为当前线程，计数器 + 1（可重入）
   - 如果 `_owner` 为其他线程，阻塞等待

3. 解锁时：
   - 计数器 - 1
   - 只有计数器为 0 时才真正释放锁

**应用场景**：
- 同步方法调用同步方法
- 递归调用同步方法
- 子类调用父类同步方法

**性能**：重入的开销很小（~5 ns），仅需递增计数器，无需担心性能问题。

可重入是 synchronized 和 ReentrantLock 等主流锁的基本特性，避免了"自己阻塞自己"的死锁问题。

