---
layout: default
title: "synchronized和ReentrantLock的区别"
parent: 并发编程
nav_order: 220
description: "全面对比synchronized和ReentrantLock在实现机制、功能特性、性能表现等方面的差异"
author: "wuxl"
date: 2025-11-02
---
## 问题

synchronized和ReentrantLock区别？

## 答案

### 1. 核心概念

**synchronized**：
- Java 内置的关键字，由 JVM 实现
- 基于 Monitor（监视器锁）机制
- 自动获取和释放锁

**ReentrantLock**：
- JUC 包中的类，由 JDK 实现
- 基于 AQS（AbstractQueuedSynchronizer）框架
- 需要显式调用 `lock()` 和 `unlock()`

### 2. 详细对比

#### 2.1 实现层面

| 特性 | synchronized | ReentrantLock |
|------|-------------|---------------|
| **实现方式** | JVM 层面的关键字 | JDK 层面的 API（java.util.concurrent.locks） |
| **底层机制** | Monitor 对象（依赖 JVM 的 monitorenter/monitorexit 指令） | AQS + CAS + LockSupport |
| **字节码** | 生成 `monitorenter` 和 `monitorexit` 指令 | 普通方法调用 |
| **锁存储** | 对象头的 Mark Word | AQS 的 state 变量 |

**synchronized 字节码示例**：
```java
public void syncMethod() {
    synchronized (this) {
        // 临界区代码
    }
}

// 字节码：
// monitorenter    // 获取锁
// ... 业务代码 ...
// monitorexit     // 释放锁
// monitorexit     // 异常情况下的释放
```

**ReentrantLock 代码示例**：
```java
private final ReentrantLock lock = new ReentrantLock();

public void lockMethod() {
    lock.lock();  // 显式获取锁
    try {
        // 临界区代码
    } finally {
        lock.unlock();  // 显式释放锁（必须在 finally 中）
    }
}
```

#### 2.2 功能特性

| 特性 | synchronized | ReentrantLock |
|------|-------------|---------------|
| **可重入性** | ✅ 支持 | ✅ 支持 |
| **公平性** | ❌ 非公平 | ✅ 可选公平/非公平 |
| **可中断性** | ❌ 不可中断（等待锁时无法响应中断） | ✅ 支持可中断（`lockInterruptibly()`） |
| **超时机制** | ❌ 不支持 | ✅ 支持超时获取锁（`tryLock(timeout, unit)`） |
| **尝试获取** | ❌ 阻塞或立即获取 | ✅ 非阻塞尝试（`tryLock()`） |
| **条件变量** | ❌ 只有一个条件队列（wait/notify） | ✅ 支持多个条件队列（`newCondition()`） |
| **锁的释放** | ✅ 自动释放（即使异常也会释放） | ❌ 必须手动释放（需要 finally 块） |

**功能示例对比**：

```java
// 1. 公平锁
// synchronized：不支持公平锁
synchronized (lock) {
    // 总是非公平
}

// ReentrantLock：可选
ReentrantLock fairLock = new ReentrantLock(true);  // 公平锁
ReentrantLock unfairLock = new ReentrantLock(false);  // 非公平锁

// 2. 可中断
// synchronized：不支持
synchronized (lock) {
    // 无法响应中断
}

// ReentrantLock：支持
lock.lockInterruptibly();  // 可响应中断
try {
    // 业务代码
} finally {
    lock.unlock();
}

// 3. 超时获取
// synchronized：不支持
synchronized (lock) {
    // 无法设置超时
}

// ReentrantLock：支持
if (lock.tryLock(3, TimeUnit.SECONDS)) {  // 最多等待 3 秒
    try {
        // 业务代码
    } finally {
        lock.unlock();
    }
} else {
    // 获取锁失败的处理
}

// 4. 非阻塞尝试
// synchronized：不支持
synchronized (lock) {
    // 必须阻塞等待
}

// ReentrantLock：支持
if (lock.tryLock()) {  // 立即返回，不阻塞
    try {
        // 业务代码
    } finally {
        lock.unlock();
    }
} else {
    // 获取锁失败，执行其他逻辑
}

// 5. 多个条件变量
// synchronized：只有一个
synchronized (lock) {
    lock.wait();   // 只有一个等待队列
    lock.notify();
}

// ReentrantLock：支持多个
Condition notFull = lock.newCondition();
Condition notEmpty = lock.newCondition();

lock.lock();
try {
    while (queue.isFull()) {
        notFull.await();  // 等待"不满"条件
    }
    queue.add(item);
    notEmpty.signal();    // 通知"不空"条件
} finally {
    lock.unlock();
}
```

#### 2.3 性能表现

**JDK 1.5 时代**：
- synchronized 是重量级锁，性能较差
- ReentrantLock 性能明显优于 synchronized

**JDK 1.6+ 优化后**：
- synchronized 引入了**偏向锁、轻量级锁、自旋锁、锁消除、锁粗化**等优化
- 在低竞争场景下，synchronized 性能已经与 ReentrantLock 相当
- 在高竞争场景下，两者性能接近

**性能对比**：
- **低竞争**：synchronized（有偏向锁优化）≈ ReentrantLock
- **高竞争**：synchronized ≈ ReentrantLock
- **极高竞争**：ReentrantLock 略优（可选公平锁，减少饥饿）

#### 2.4 使用便捷性

**synchronized**：
```java
// 优点：简洁，自动释放锁
public synchronized void method() {
    // 业务代码
}

// 或
synchronized (lock) {
    // 业务代码
}  // 自动释放，即使有异常
```

**ReentrantLock**：
```java
// 缺点：需要手动管理锁，容易忘记释放
lock.lock();
try {
    // 业务代码
} finally {
    lock.unlock();  // 必须在 finally 中释放
}

// 如果忘记 unlock()，会导致死锁！
```

#### 2.5 锁的升级

**synchronized**：
- JDK 1.6+ 支持锁升级：无锁 → 偏向锁 → 轻量级锁 → 重量级锁
- 自动根据竞争情况升级，无需手动干预

**ReentrantLock**：
- 没有锁升级机制
- 始终是基于 AQS 的锁实现

### 3. 底层原理对比

#### 3.1 synchronized 原理

```java
// 对象头结构（Mark Word）
| 锁状态   | 25 bit        | 4 bit   | 1 bit (是否偏向) | 2 bit (锁标志) |
|---------|--------------|---------|-----------------|---------------|
| 无锁    | hashCode     | 分代年龄 | 0               | 01            |
| 偏向锁  | 线程 ID       | 分代年龄 | 1               | 01            |
| 轻量级锁 | 栈中锁记录指针 |         |                 | 00            |
| 重量级锁 | Monitor 指针  |         |                 | 10            |
```

**加锁过程**：
1. **偏向锁**：线程 ID 存储在对象头，无需 CAS，性能最优
2. **轻量级锁**：通过 CAS 在栈中创建锁记录，适用于线程交替执行
3. **重量级锁**：依赖操作系统的 Mutex（互斥量），涉及用户态和内核态切换

#### 3.2 ReentrantLock 原理

```java
// 基于 AQS 的 state 变量
private volatile int state;  // 0: 未锁定, >0: 锁定次数（重入）

// 获取锁（非公平）
final boolean nonfairTryAcquire(int acquires) {
    final Thread current = Thread.currentThread();
    int c = getState();
    if (c == 0) {  // 未锁定
        if (compareAndSetState(0, acquires)) {  // CAS 获取锁
            setExclusiveOwnerThread(current);
            return true;
        }
    } else if (current == getExclusiveOwnerThread()) {  // 重入
        int nextc = c + acquires;
        setState(nextc);
        return true;
    }
    return false;
}
```

### 4. 使用场景

**推荐使用 synchronized**：
- 代码简洁性要求高
- 不需要高级特性（公平锁、超时、中断）
- JVM 内置优化已足够
- 方法级别或简单代码块的同步

**推荐使用 ReentrantLock**：
- 需要公平锁
- 需要可中断的锁获取（`lockInterruptibly()`）
- 需要超时获取锁（`tryLock(timeout, unit)`）
- 需要非阻塞尝试获取锁（`tryLock()`）
- 需要多个条件变量（`Condition`）
- 需要更细粒度的锁控制

### 5. 实际案例

#### 5.1 生产者-消费者模型

**使用 synchronized**：
```java
class BoundedBuffer {
    private final Object lock = new Object();
    private final Queue<Integer> queue = new LinkedList<>();
    private final int capacity = 10;

    public void produce(int item) throws InterruptedException {
        synchronized (lock) {
            while (queue.size() == capacity) {
                lock.wait();  // 只有一个条件队列
            }
            queue.add(item);
            lock.notifyAll();  // 唤醒所有线程（包括生产者和消费者）
        }
    }

    public int consume() throws InterruptedException {
        synchronized (lock) {
            while (queue.isEmpty()) {
                lock.wait();  // 只有一个条件队列
            }
            int item = queue.remove();
            lock.notifyAll();  // 唤醒所有线程（效率低）
            return item;
        }
    }
}
```

**使用 ReentrantLock + Condition**：
```java
class BoundedBuffer {
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();   // 独立条件队列
    private final Condition notEmpty = lock.newCondition();  // 独立条件队列
    private final Queue<Integer> queue = new LinkedList<>();
    private final int capacity = 10;

    public void produce(int item) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == capacity) {
                notFull.await();  // 等待"不满"条件
            }
            queue.add(item);
            notEmpty.signal();    // 精准唤醒消费者（效率高）
        } finally {
            lock.unlock();
        }
    }

    public int consume() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) {
                notEmpty.await();  // 等待"不空"条件
            }
            int item = queue.remove();
            notFull.signal();      // 精准唤醒生产者（效率高）
            return item;
        } finally {
            lock.unlock();
        }
    }
}
```

### 6. 性能优化考量

**synchronized 优化**：
- 减少同步代码块的范围
- 避免在循环中使用 synchronized
- 利用 JVM 的锁消除和锁粗化优化

**ReentrantLock 优化**：
- 合理选择公平/非公平锁（非公平锁性能更好）
- 使用 `tryLock()` 避免无限等待
- 使用多个 Condition 减少不必要的唤醒

### 7. 总结

| 维度 | synchronized | ReentrantLock |
|------|-------------|---------------|
| **实现** | JVM 内置关键字 | JDK API 类 |
| **使用** | 简单，自动释放 | 复杂，手动管理 |
| **功能** | 基础功能 | 高级功能（公平锁、超时、中断、多条件） |
| **性能** | JDK 1.6+ 已优化，性能接近 | 略优于早期 synchronized |
| **推荐** | 优先选择，简洁安全 | 需要高级特性时选择 |

**面试要点**：
1. **实现层面**：synchronized 是 JVM 实现，ReentrantLock 是 AQS 实现
2. **功能对比**：ReentrantLock 提供更多高级特性（公平锁、超时、中断、多条件）
3. **性能**：JDK 1.6+ 后，synchronized 性能已大幅提升，两者接近
4. **使用建议**：优先使用 synchronized（简洁安全），需要高级功能时用 ReentrantLock
5. **注意事项**：ReentrantLock 必须在 finally 中释放锁，否则容易死锁

**记忆口诀**：
- synchronized：简单自动，JVM优化好
- ReentrantLock：功能强大，手动要记牢
