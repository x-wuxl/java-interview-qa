---
title: "synchronized是非公平锁吗，那么是如何体现的？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [synchronized, 非公平锁, 锁竞争, Monitor]
description: "深入分析synchronized的非公平性特征，包括轻量级锁的CAS竞争和重量级锁的线程唤醒机制"
nav_order: 219
parent: 并发编程
---
# synchronized是非公平锁吗，那么是如何体现的？

## 核心答案

**是的，synchronized 是非公平锁**。这意味着后来的线程可能比等待时间长的线程更早获取锁，无法保证"先来先得"的公平性。

---

## 非公平性的体现

### 1. 轻量级锁阶段：CAS 竞争无序

#### 机制

多个线程通过 **CAS 操作**竞争轻量级锁，成功的线程立即获取锁，**没有排队机制**。

#### 示例

```java
Object lock = new Object();

// 线程1：持有轻量级锁
new Thread(() -> {
    synchronized(lock) {
        sleep(10);
    }
}, "Thread-1").start();

Thread.sleep(1);  // 确保线程1先获取锁

// 线程2：等待中（自旋）
new Thread(() -> {
    synchronized(lock) {
        System.out.println("Thread-2 acquired");
    }
}, "Thread-2").start();

Thread.sleep(1);  // 确保线程2先开始等待

// 线程3：后到
new Thread(() -> {
    synchronized(lock) {
        System.out.println("Thread-3 acquired");
    }
}, "Thread-3").start();
```

**可能的输出**：
```
Thread-3 acquired  // 线程3后到但先获取！
Thread-2 acquired
```

**原因**：
- 线程1 释放锁时，线程2 和线程3 同时执行 CAS
- CAS 是原子操作，但**没有队列顺序**
- 线程3 的 CAS 可能恰好成功（取决于 CPU 调度）

---

### 2. 重量级锁阶段：唤醒无序

#### Monitor 结构

```cpp
ObjectMonitor {
    _owner       = null;          // 持有锁的线程
    _EntryList   = [Thread-2, Thread-3, Thread-4];  // 等待队列
    _WaitSet     = [];            // wait() 的线程
    _recursions  = 0;
}
```

#### 非公平唤醒机制

```java
// 线程1 释放锁
synchronized(lock) {
    // ...
}  // monitorexit

// JVM 的唤醒策略（非公平）
void monitorexit() {
    monitor._owner = null;
    
    // 唤醒策略1：唤醒 _EntryList 第一个线程（看似公平）
    Thread t = _EntryList.removeFirst();
    unpark(t);  // 唤醒线程2
    
    // ⚠️ 但此时有新线程Thread-5到达
    // Thread-5 直接尝试 CAS 获取锁
    if (CAS(_owner, null, Thread-5)) {
        // Thread-5 插队成功！
        return;
    }
    
    // Thread-2 被唤醒，尝试获取锁
    if (CAS(_owner, null, Thread-2)) {
        // Thread-2 获取成功
    } else {
        // 失败，重新进入 _EntryList 阻塞
    }
}
```

#### 关键点

1. **新线程可以插队**：
   - 新到达的线程会直接尝试获取锁（tryLock）
   - 不需要先进入 `_EntryList`
   - 如果 CAS 成功，直接获取锁

2. **唤醒的线程可能再次失败**：
   - 从 `_EntryList` 唤醒的线程需要重新竞争
   - 如果此时有新线程插队，被唤醒的线程会再次阻塞

3. **唤醒顺序不确定**（某些 JVM 实现）：
   - 不同 JVM 实现的 `_EntryList` 数据结构不同
   - HotSpot 早期使用无序链表，唤醒顺序不确定

---

### 3. 源码层面的非公平性

#### HotSpot 源码分析

```cpp
// src/hotspot/share/runtime/objectMonitor.cpp

void ObjectMonitor::enter(TRAPS) {
    Thread * const Self = THREAD;
    
    // ⚠️ 第一次尝试：直接 CAS（非公平入口）
    void * cur = Atomic::cmpxchg(Self, &_owner, (void*)NULL);
    if (cur == NULL) {
        return;  // 插队成功，直接获取
    }
    
    // 当前线程已持有锁（重入）
    if (cur == Self) {
        _recursions++;
        return;
    }
    
    // ⚠️ 第二次尝试：自旋 CAS（非公平自旋）
    if (TrySpin(Self) > 0) {
        return;  // 自旋成功，又一次插队
    }
    
    // 进入等待队列
    EnterI(THREAD);
}

void ObjectMonitor::exit(bool not_suspended, TRAPS) {
    // 释放锁
    OrderAccess::release_store(&_owner, (void*)NULL);
    
    // ⚠️ 唤醒策略：QMode 参数控制
    // QMode = 0: 直接唤醒 _EntryList 头部（默认）
    // QMode = 2: 唤醒后线程仍需竞争（非公平）
    // QMode = 3: 移到 _cxq 队列再竞争（非公平）
    
    ObjectWaiter * w = _EntryList;
    if (w != NULL) {
        ExitEpilog(Self, w);  // 唤醒，但不保证获取锁
    }
}
```

#### QMode 参数（JVM 内部）

```bash
# 控制唤醒策略（JVM 内部参数，无法直接设置）
QMode = 0   # 唤醒 _EntryList 头部（看似公平，但新线程可插队）
QMode = 2   # 被唤醒线程与新到达线程竞争（明显非公平）
QMode = 3   # 移到 _cxq 队列后竞争（非公平）
```

---

## 非公平的优势

### 1. 减少线程切换

```java
// 公平锁的开销
synchronized(lock) {  // 假设公平
    // 线程1 释放锁
}  
// → 唤醒线程2（上下文切换：10μs）
// → 线程2 执行（可能很快：1μs）
// → 线程2 释放锁
// → 唤醒线程3（上下文切换：10μs）

// 非公平锁的优化
synchronized(lock) {
    // 线程1 释放锁
}
// → 线程4 正在运行，直接插队获取（0μs）
// → 线程4 执行完释放
// → 此时才唤醒线程2
```

**收益**：减少不必要的上下文切换。

### 2. 提高吞吐量

```
公平锁：保证顺序，但吞吐量低
非公平锁：可能"饿死"，但吞吐量高
```

**场景**：
- 高并发服务器（Tomcat、Netty）
- 短时间临界区（几微秒）
- 追求总吞吐量而非单个请求延迟

---

## 非公平的问题：线程饥饿

### 饥饿示例

```java
public class StarvationDemo {
    private final Object lock = new Object();
    
    public static void main(String[] args) {
        StarvationDemo demo = new StarvationDemo();
        
        // 一个低优先级线程
        Thread t1 = new Thread(() -> {
            while (true) {
                synchronized(demo.lock) {
                    System.out.println("Thread-1 acquired");
                }
            }
        });
        t1.setPriority(Thread.MIN_PRIORITY);
        t1.start();
        
        // 10个高优先级线程
        for (int i = 0; i < 10; i++) {
            Thread t = new Thread(() -> {
                while (true) {
                    synchronized(demo.lock) {
                        // 高优先级线程可能一直插队
                    }
                }
            });
            t.setPriority(Thread.MAX_PRIORITY);
            t.start();
        }
    }
}
```

**可能结果**：线程1 长时间无法获取锁（饿死）。

---

## 对比：ReentrantLock 的公平与非公平

### ReentrantLock 支持选择

```java
// 非公平锁（默认）
ReentrantLock lock = new ReentrantLock(false);

// 公平锁
ReentrantLock fairLock = new ReentrantLock(true);
```

### 公平锁实现

```java
// AQS 队列（FIFO）
protected final boolean tryAcquire(int acquires) {
    if (hasQueuedPredecessors()) {  // ✅ 检查是否有前驱节点
        return false;  // 有等待线程，拒绝插队
    }
    // CAS 获取锁
}
```

### 性能对比

| 类型            | 吞吐量 | 延迟     | 公平性 |
|----------------|--------|---------|--------|
| synchronized   | 高     | 低（平均）| ❌     |
| ReentrantLock(false) | 高 | 低（平均）| ❌     |
| ReentrantLock(true)  | 低 | 高（最坏）| ✅     |

---

## 实战建议

### 何时接受非公平性

```java
// ✅ 适合场景：短时间临界区
@RestController
public class UserController {
    private final Object lock = new Object();
    
    @GetMapping("/counter")
    public int increment() {
        synchronized(lock) {
            return counter++;  // 几纳秒，非公平无影响
        }
    }
}
```

### 何时需要公平锁

```java
// ❌ 不适合场景：任务调度
public class TaskScheduler {
    private final ReentrantLock lock = new ReentrantLock(true);  // 公平
    
    public void scheduleTask(Task task) {
        lock.lock();
        try {
            queue.offer(task);  // 保证任务按提交顺序执行
        } finally {
            lock.unlock();
        }
    }
}
```

---

## 答题总结

**问题**：synchronized 是非公平锁吗，如何体现？

**回答**：

是的，synchronized 是**非公平锁**，主要体现在以下方面：

1. **轻量级锁阶段**：
   - 多个线程通过 CAS 竞争，无排队机制
   - 后到的线程可能比先等待的线程更早获取锁

2. **重量级锁阶段**：
   - 新到达的线程可以直接尝试获取锁（插队）
   - 从 `_EntryList` 唤醒的线程需要重新竞争，可能再次失败
   - 唤醒顺序在某些 JVM 实现中也不保证 FIFO

3. **源码层面**：
   - `ObjectMonitor::enter()` 有两次非公平尝试（直接 CAS + 自旋）
   - `ObjectMonitor::exit()` 的唤醒策略允许新线程插队

**非公平的优势**：
- 减少线程上下文切换
- 提高整体吞吐量
- 适合短时间临界区

**缺点**：可能导致线程饥饿（某些线程长时间得不到执行）。

如果需要公平性，建议使用 `ReentrantLock(true)` 公平锁。

