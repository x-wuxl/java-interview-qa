---
title: "可重入锁的底层实现"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [可重入锁, AQS, synchronized, ReentrantLock, 源码分析]
description: "深入剖析可重入锁的底层实现原理，包括synchronized的Monitor机制和ReentrantLock的AQS实现"
nav_order: 231
parent: 并发编程
---
# 可重入锁的底层实现

## 核心原理

可重入锁的底层实现依赖两个关键数据：
1. **持有线程标识**（Owner Thread）：记录当前持有锁的线程
2. **重入计数器**（Recursion Counter）：记录同一线程获取锁的次数

Java 中有两种主要实现方式：
- **synchronized**：基于 JVM 的 ObjectMonitor
- **ReentrantLock**：基于 AQS（AbstractQueuedSynchronizer）

---

## 一、synchronized 的底层实现

### 1. ObjectMonitor 数据结构

```cpp
// HotSpot 源码：src/hotspot/share/runtime/objectMonitor.hpp

ObjectMonitor {
    void *    _owner;         // ✅ 持有锁的线程指针
    int       _recursions;    // ✅ 重入计数器
    ObjectWaiter * _EntryList;  // 等待获取锁的线程队列
    ObjectWaiter * _WaitSet;    // 调用 wait() 的线程队列
    int       _count;           // 计数器
    // ...
}
```

### 2. 加锁流程（monitorenter）

#### 源码分析

```cpp
// src/hotspot/share/runtime/objectMonitor.cpp

void ObjectMonitor::enter(TRAPS) {
    Thread * const Self = THREAD;
    
    // 步骤1：快速尝试获取锁（CAS）
    void * cur = Atomic::cmpxchg(Self, &_owner, (void*)NULL);
    if (cur == NULL) {
        // 成功获取锁
        assert(_recursions == 0, "invariant");
        return;
    }
    
    // 步骤2：检查是否为当前线程（可重入判断）
    if (cur == Self) {
        // ✅ 可重入：计数器加1
        _recursions++;
        return;
    }
    
    // 步骤3：检查当前线程是否已持有轻量级锁
    if (Self->is_lock_owned((address)cur)) {
        assert(_recursions == 0, "internal state error");
        _recursions = 1;  // 轻量级锁膨胀为重量级锁
        _owner = Self;
        return;
    }
    
    // 步骤4：其他线程持有锁，进入阻塞队列
    EnterI(THREAD);
}

void ObjectMonitor::EnterI(TRAPS) {
    Thread * const Self = THREAD;
    
    // 自旋尝试
    if (TrySpin(Self) > 0) {
        return;  // 自旋成功
    }
    
    // 自旋失败，加入 _EntryList 阻塞
    ObjectWaiter node(Self);
    node.TState = ObjectWaiter::TS_CXQ;
    
    // 加入队列
    ParkEvent * _event = node._event;
    for (;;) {
        _event->park();  // 阻塞当前线程
        
        // 被唤醒后重新尝试获取锁
        if (TryLock(Self) > 0) {
            break;  // 获取成功
        }
    }
}
```

#### 流程图

```
monitorenter:
    ┌─────────────────────┐
    │ CAS 尝试获取锁       │
    └─────────┬───────────┘
              │
         成功 │ 失败
              ▼
    ┌─────────────────────┐
    │ _owner == NULL?     │
    └─────────┬───────────┘
              │
         是   │ 否
              ▼
    ┌─────────────────────┐
    │ _owner == 当前线程?  │ ◄─ 可重入判断
    └─────────┬───────────┘
              │
         是   │ 否
              ▼
    ┌─────────────────────┐
    │ _recursions++       │ ◄─ 计数器加1
    └─────────────────────┘
              │
         否   │
              ▼
    ┌─────────────────────┐
    │ 进入 _EntryList 阻塞 │
    └─────────────────────┘
```

### 3. 解锁流程（monitorexit）

#### 源码分析

```cpp
void ObjectMonitor::exit(bool not_suspended, TRAPS) {
    Thread * const Self = THREAD;
    
    // 步骤1：检查当前线程是否持有锁
    if (_owner != Self) {
        throw IllegalMonitorStateException();
    }
    
    // 步骤2：处理重入情况
    if (_recursions != 0) {
        // ✅ 重入计数器减1，但不释放锁
        _recursions--;
        return;
    }
    
    // 步骤3：计数器为0，真正释放锁
    OrderAccess::release_store(&_owner, (void*)NULL);
    OrderAccess::fence();  // 内存屏障
    
    // 步骤4：唤醒 _EntryList 中的线程
    ObjectWaiter * w = NULL;
    
    // 不同的唤醒策略（QMode）
    if (QMode == 2 && _cxq != NULL) {
        // 从 _cxq 队列中唤醒
        w = _cxq;
        ExitEpilog(Self, w);
    } else if (QMode == 0 && _EntryList != NULL) {
        // 从 _EntryList 队列中唤醒
        w = _EntryList;
        _EntryList = w->_next;
        ExitEpilog(Self, w);
    }
}

void ObjectMonitor::ExitEpilog(Thread * Self, ObjectWaiter * Wakee) {
    // 唤醒线程
    ParkEvent * _event = Wakee->_event;
    _event->unpark();  // 唤醒被阻塞的线程
}
```

#### 关键点

```java
synchronized(obj) {        // ← monitorenter
                           //   _owner = 当前线程
                           //   _recursions = 1
    
    synchronized(obj) {    // ← monitorenter（重入）
                           //   _owner 不变
                           //   _recursions = 2
        
        // ...
        
    }                      // ← monitorexit
                           //   _recursions = 1
                           //   锁未释放
    
}                          // ← monitorexit
                           //   _recursions = 0
                           //   _owner = null
                           //   唤醒 _EntryList
```

---

## 二、ReentrantLock 的底层实现

### 1. AQS 核心数据结构

```java
// java.util.concurrent.locks.AbstractQueuedSynchronizer

public abstract class AbstractQueuedSynchronizer {
    /**
     * ✅ 状态变量：表示锁的状态
     * - 0: 未锁定
     * - n: 被锁定，且重入了 n 次
     */
    private volatile int state;
    
    /**
     * ✅ 持有锁的线程
     */
    private transient Thread exclusiveOwnerThread;
    
    /**
     * 等待队列（双向链表）
     */
    static final class Node {
        volatile Node prev;
        volatile Node next;
        volatile Thread thread;
        // ...
    }
    
    private transient volatile Node head;  // 队列头
    private transient volatile Node tail;  // 队列尾
}
```

### 2. ReentrantLock 的加锁实现

#### Sync 内部类（核心逻辑）

```java
// java.util.concurrent.locks.ReentrantLock.Sync

abstract static class Sync extends AbstractQueuedSynchronizer {
    
    /**
     * 非公平锁的快速尝试
     */
    final boolean nonfairTryAcquire(int acquires) {
        final Thread current = Thread.currentThread();
        int c = getState();
        
        // 情况1：锁未被持有
        if (c == 0) {
            // CAS 尝试获取锁
            if (compareAndSetState(0, acquires)) {
                setExclusiveOwnerThread(current);
                return true;
            }
        }
        // 情况2：当前线程已持有锁（可重入判断）
        else if (current == getExclusiveOwnerThread()) {
            // ✅ 重入：state 加上 acquires（通常为1）
            int nextc = c + acquires;
            if (nextc < 0) {  // 溢出检查
                throw new Error("Maximum lock count exceeded");
            }
            setState(nextc);  // 更新 state
            return true;
        }
        
        // 情况3：其他线程持有锁
        return false;
    }
    
    /**
     * 释放锁
     */
    protected final boolean tryRelease(int releases) {
        // ✅ state 减去 releases（通常为1）
        int c = getState() - releases;
        
        // 检查当前线程是否持有锁
        if (Thread.currentThread() != getExclusiveOwnerThread()) {
            throw new IllegalMonitorStateException();
        }
        
        boolean free = false;
        // 只有 state 为 0 时才真正释放锁
        if (c == 0) {
            free = true;
            setExclusiveOwnerThread(null);  // 清空持有线程
        }
        setState(c);
        return free;
    }
}
```

#### 公平锁 vs 非公平锁

```java
// 非公平锁（默认）
static final class NonfairSync extends Sync {
    final void lock() {
        // 直接尝试 CAS（可能插队）
        if (compareAndSetState(0, 1)) {
            setExclusiveOwnerThread(Thread.currentThread());
        } else {
            acquire(1);  // 进入队列
        }
    }
}

// 公平锁
static final class FairSync extends Sync {
    final void lock() {
        acquire(1);  // 直接进入队列，不插队
    }
    
    protected final boolean tryAcquire(int acquires) {
        final Thread current = Thread.currentThread();
        int c = getState();
        
        if (c == 0) {
            // ✅ 公平锁：检查是否有前驱节点
            if (!hasQueuedPredecessors() &&
                compareAndSetState(0, acquires)) {
                setExclusiveOwnerThread(current);
                return true;
            }
        }
        // 可重入逻辑相同
        else if (current == getExclusiveOwnerThread()) {
            int nextc = c + acquires;
            setState(nextc);
            return true;
        }
        return false;
    }
}
```

### 3. 完整加锁流程

```java
// 1. 用户调用
ReentrantLock lock = new ReentrantLock();
lock.lock();

// 2. lock() 方法
public void lock() {
    sync.lock();  // 调用内部 Sync 的 lock
}

// 3. acquire() 方法（AQS）
public final void acquire(int arg) {
    // 尝试获取锁
    if (!tryAcquire(arg) &&
        // 获取失败，加入队列并阻塞
        acquireQueued(addWaiter(Node.EXCLUSIVE), arg)) {
        selfInterrupt();
    }
}

// 4. tryAcquire() 方法（上面已分析）
//    - 检查 state == 0（无人持有）
//    - 检查 exclusiveOwnerThread == current（可重入）
//    - 否则返回 false

// 5. addWaiter() 加入队列
private Node addWaiter(Node mode) {
    Node node = new Node(Thread.currentThread(), mode);
    // 尝试快速入队
    Node pred = tail;
    if (pred != null) {
        node.prev = pred;
        if (compareAndSetTail(pred, node)) {
            pred.next = node;
            return node;
        }
    }
    // 完整入队逻辑
    enq(node);
    return node;
}

// 6. acquireQueued() 阻塞等待
final boolean acquireQueued(final Node node, int arg) {
    boolean failed = true;
    try {
        boolean interrupted = false;
        for (;;) {
            final Node p = node.predecessor();
            // 只有前驱是 head 才尝试获取锁（公平性）
            if (p == head && tryAcquire(arg)) {
                setHead(node);
                p.next = null;  // help GC
                failed = false;
                return interrupted;
            }
            // 阻塞当前线程
            if (shouldParkAfterFailedAcquire(p, node) &&
                parkAndCheckInterrupt()) {
                interrupted = true;
            }
        }
    } finally {
        if (failed) {
            cancelAcquire(node);
        }
    }
}
```

---

## 三、两种实现的对比

### 1. 数据结构对比

| 对比项       | synchronized (Monitor)    | ReentrantLock (AQS)        |
|-------------|---------------------------|----------------------------|
| 持有线程     | `_owner` (void*)          | `exclusiveOwnerThread`      |
| 重入计数器   | `_recursions` (int)       | `state` (int)              |
| 等待队列     | `_EntryList` (单链表)      | `Node` (双向链表)           |
| 实现层级     | JVM C++ 代码              | Java 代码                   |
| 条件队列     | `_WaitSet` (单个)          | `ConditionObject` (多个)    |

### 2. 重入机制对比

#### synchronized

```cpp
// 加锁
if (_owner == Self) {
    _recursions++;  // 直接递增
    return;
}

// 解锁
if (_recursions != 0) {
    _recursions--;  // 直接递减
    return;
}
```

#### ReentrantLock

```java
// 加锁
if (current == getExclusiveOwnerThread()) {
    int nextc = getState() + acquires;  // state 加上 acquires
    setState(nextc);
    return true;
}

// 解锁
int c = getState() - releases;  // state 减去 releases
if (c == 0) {
    setExclusiveOwnerThread(null);
}
setState(c);
```

### 3. 性能对比

```java
// 基准测试
@Benchmark
public void synchronizedReentrant() {
    synchronized(lock) {
        synchronized(lock) {
            synchronized(lock) {
                // 三次重入
            }
        }
    }
}

@Benchmark
public void reentrantLockReentrant() {
    lock.lock();
    try {
        lock.lock();
        try {
            lock.lock();
            try {
                // 三次重入
            } finally {
                lock.unlock();
            }
        } finally {
            lock.unlock();
        }
    } finally {
        lock.unlock();
    }
}
```

**结果**（现代 JVM）：
- synchronized：~50 ns（JVM 内联优化）
- ReentrantLock：~60 ns（方法调用开销）

**结论**：性能差异很小，选择依据应是功能需求。

---

## 四、关键实现细节

### 1. 为什么用 state 而不是单独的计数器？

AQS 的 `state` 是多用途的：
- **独占锁**：state = 重入次数
- **共享锁**：state = 剩余许可数（如 Semaphore）
- **读写锁**：state 高 16 位 = 读锁，低 16 位 = 写锁

```java
// ReentrantReadWriteLock 的 state 划分
static final int SHARED_SHIFT   = 16;
static final int SHARED_UNIT    = (1 << SHARED_SHIFT);  // 读锁单位
static final int MAX_COUNT      = (1 << SHARED_SHIFT) - 1;
static final int EXCLUSIVE_MASK = (1 << SHARED_SHIFT) - 1;

// 读锁计数：state >>> 16
// 写锁计数：state & EXCLUSIVE_MASK
```

### 2. 重入计数器的溢出处理

```java
// synchronized：不检查溢出（理论上可达到 2^31-1）
_recursions++;  // 可能溢出（实际不会发生）

// ReentrantLock：检查溢出
int nextc = c + acquires;
if (nextc < 0) {  // 溢出检查
    throw new Error("Maximum lock count exceeded");
}
```

### 3. 内存可见性保证

```java
// synchronized：通过内存屏障（monitorenter/monitorexit）
monitorenter
LoadLoad 屏障
临界区代码
StoreStore 屏障
monitorexit

// ReentrantLock：通过 volatile
private volatile int state;  // volatile 保证可见性
```

---

## 五、答题总结

**问题**：可重入锁的底层实现？

**回答**：

可重入锁的底层实现依赖**持有线程标识**和**重入计数器**两个核心数据。

### synchronized 实现（ObjectMonitor）

1. **数据结构**：
   - `_owner`：持有锁的线程指针
   - `_recursions`：重入计数器

2. **加锁流程**：
   - 检查 `_owner == NULL`：CAS 获取锁
   - 检查 `_owner == 当前线程`：计数器 + 1（可重入）
   - 否则进入 `_EntryList` 阻塞

3. **解锁流程**：
   - 计数器 - 1
   - 只有计数器为 0 时才释放锁，唤醒等待线程

### ReentrantLock 实现（AQS）

1. **数据结构**：
   - `state`：锁状态（0 = 未锁定，n = 重入 n 次）
   - `exclusiveOwnerThread`：持有锁的线程

2. **加锁流程**：
   - 检查 `state == 0`：CAS 设置 state = 1
   - 检查 `exclusiveOwnerThread == 当前线程`：state + 1（可重入）
   - 否则加入 AQS 队列阻塞

3. **解锁流程**：
   - state - 1
   - 只有 state == 0 时才释放锁，唤醒队列头部线程

**关键点**：两者的可重入机制本质相同，都是通过线程标识 + 计数器实现，性能接近，主要区别在于功能特性（公平锁、条件变量等）。

