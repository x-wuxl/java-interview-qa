---
layout: default
title: "synchronized和lock区别"
parent: 并发编程
nav_order: 221
description: "全面对比synchronized和Lock接口的区别，包括使用方式、功能特性、性能表现和适用场景"
date: 2025-11-02
---
# synchronized和lock区别

## 核心对比

`synchronized` 是 Java 内置关键字，`Lock` 是 JUC 包提供的接口，两者都用于实现互斥锁，但在实现机制、功能特性和使用方式上有显著差异。

---

## 详细对比表

| 对比维度         | synchronized              | Lock (ReentrantLock)        |
|-----------------|---------------------------|-----------------------------|
| **层级**        | JVM 层面（字节码指令）       | Java API 层面（java.util.concurrent）|
| **使用方式**    | 关键字，自动加锁/解锁         | 接口，手动 lock()/unlock()   |
| **锁释放**      | 自动释放（JVM 保证）         | 手动释放（需 finally）        |
| **可中断**      | ❌ 不可中断                 | ✅ lockInterruptibly()       |
| **超时**        | ❌ 不支持                   | ✅ tryLock(timeout)          |
| **公平性**      | ❌ 非公平锁                 | ✅ 可选公平/非公平            |
| **条件变量**    | 单一条件（wait/notify）     | ✅ 多个 Condition            |
| **可重入**      | ✅ 支持                     | ✅ 支持                      |
| **性能**        | JDK 6 后接近 Lock           | 低竞争时稍快，高竞争时相似     |
| **死锁检测**    | ❌ 无                       | ❌ 无（但可通过 tryLock 避免）|
| **适用场景**    | 简单同步、代码块保护          | 复杂场景、需要高级特性        |

---

## 1. 使用方式

### synchronized

```java
// 方式1：同步方法
public synchronized void method() {
    // 自动加锁
} // 自动解锁

// 方式2：同步代码块
public void method() {
    synchronized(lock) {
        // 自动加锁
    } // 自动解锁，即使抛异常也会释放
}
```

**特点**：
- 无需手动释放锁
- 异常时 JVM 保证锁释放
- 代码简洁，不易出错

### Lock

```java
Lock lock = new ReentrantLock();

public void method() {
    lock.lock();  // 手动加锁
    try {
        // 临界区代码
    } finally {
        lock.unlock();  // ⚠️ 必须在 finally 中释放
    }
}
```

**特点**：
- 需要手动释放锁
- 必须在 `finally` 中 unlock，否则可能永久锁死
- 代码较繁琐，但更灵活

---

## 2. 可中断性

### synchronized：不可中断

```java
// 线程1：持有锁
synchronized(lock) {
    Thread.sleep(60000);  // 长时间持有
}

// 线程2：等待锁
new Thread(() -> {
    synchronized(lock) {  // ❌ 阻塞，无法被中断
        // ...
    }
}).start();

thread2.interrupt();  // ❌ 无效！线程仍在等待锁
```

**问题**：无法响应中断，可能导致线程无法终止。

### Lock：可中断

```java
Lock lock = new ReentrantLock();

// 线程2：可中断等待
new Thread(() -> {
    try {
        lock.lockInterruptibly();  // ✅ 可中断
        try {
            // ...
        } finally {
            lock.unlock();
        }
    } catch (InterruptedException e) {
        System.out.println("线程被中断，放弃获取锁");
    }
}).start();

thread2.interrupt();  // ✅ 有效！线程响应中断
```

**优势**：可以及时响应中断，避免死锁或无限等待。

---

## 3. 超时机制

### synchronized：不支持超时

```java
synchronized(lock) {
    // ❌ 无法设置等待超时
    // 可能永久阻塞
}
```

### Lock：支持超时

```java
Lock lock = new ReentrantLock();

if (lock.tryLock(3, TimeUnit.SECONDS)) {  // ✅ 等待3秒
    try {
        // 获取锁成功
    } finally {
        lock.unlock();
    }
} else {
    System.out.println("获取锁超时，执行备用逻辑");
}
```

**应用场景**：
- 防止无限等待
- 避免死锁（设置超时后放弃）
- 实现降级策略

---

## 4. 公平性

### synchronized：只支持非公平锁

```java
synchronized(lock) {
    // ❌ 后到的线程可能先获取锁
}
```

### Lock：支持公平/非公平选择

```java
// 非公平锁（默认，性能更好）
Lock lock = new ReentrantLock(false);

// 公平锁（保证 FIFO）
Lock fairLock = new ReentrantLock(true);
```

**对比**：

```java
// 非公平锁
ReentrantLock lock = new ReentrantLock(false);
// 后到的线程可能插队
// 吞吐量高

// 公平锁
ReentrantLock lock = new ReentrantLock(true);
// 严格按排队顺序
// 避免饥饿，但性能较低（约慢 2-3 倍）
```

---

## 5. 条件变量

### synchronized：单一条件队列

```java
synchronized(lock) {
    while (!condition) {
        lock.wait();  // ❌ 只有一个等待队列
    }
    // ...
    lock.notifyAll();  // 唤醒所有等待线程（可能不必要）
}
```

**局限**：
- 只有一个等待队列
- `notifyAll()` 可能唤醒不相关的线程
- 无法实现精确唤醒

### Lock：多个 Condition

```java
Lock lock = new ReentrantLock();
Condition notEmpty = lock.newCondition();  // 条件1
Condition notFull = lock.newCondition();   // 条件2

// 生产者
lock.lock();
try {
    while (queue.isFull()) {
        notFull.await();  // ✅ 等待 notFull 条件
    }
    queue.add(item);
    notEmpty.signal();  // ✅ 精确唤醒等待 notEmpty 的线程
} finally {
    lock.unlock();
}

// 消费者
lock.lock();
try {
    while (queue.isEmpty()) {
        notEmpty.await();  // ✅ 等待 notEmpty 条件
    }
    queue.remove();
    notFull.signal();  // ✅ 精确唤醒等待 notFull 的线程
} finally {
    lock.unlock();
}
```

**优势**：
- 多个条件队列，逻辑清晰
- 精确唤醒，避免惊群效应
- 更高效的线程协调

---

## 6. 性能对比

### 历史演变

**JDK 5 时代**：
- synchronized 性能较差（重量级锁）
- Lock 明显更快

**JDK 6 后**（锁优化）：
- synchronized 引入偏向锁、轻量级锁、自适应自旋
- 性能接近甚至超过 Lock

### 现代性能（JDK 17+）

| 场景              | synchronized | ReentrantLock |
|-------------------|-------------|---------------|
| 无竞争            | ~10 ns      | ~20 ns        |
| 低竞争（2线程）   | ~50 ns      | ~50 ns        |
| 高竞争（10线程）  | ~200 ns     | ~180 ns       |

**结论**：
- **低竞争场景**：synchronized 稍快（JVM 内联优化）
- **高竞争场景**：Lock 稍快（避免锁升级开销）
- **实际应用**：差异不大（微秒级），优先考虑功能需求

---

## 7. 其他特性对比

### 锁状态查询

```java
// synchronized：无法查询
synchronized(lock) {
    // ❌ 无法知道有多少线程在等待
}

// Lock：丰富的查询 API
ReentrantLock lock = new ReentrantLock();
lock.isLocked();              // 是否被锁定
lock.getHoldCount();          // 当前线程持有锁的次数
lock.getQueueLength();        // 等待线程数
lock.hasQueuedThreads();      // 是否有线程等待
```

### 锁绑定多个条件

```java
// 读写锁（Lock 的扩展）
ReadWriteLock rwLock = new ReentrantReadWriteLock();
Lock readLock = rwLock.readLock();   // 读锁
Lock writeLock = rwLock.writeLock(); // 写锁

// synchronized 无法实现读写分离
```

---

## 8. 适用场景

### 使用 synchronized 的场景

```java
// ✅ 简单的同步需求
public synchronized void increment() {
    count++;
}

// ✅ 方法级别的同步
@Service
public class UserService {
    public synchronized void updateUser(User user) {
        // 简单业务逻辑
    }
}

// ✅ 不需要高级特性
public void transfer(Account from, Account to, int amount) {
    synchronized(from) {
        synchronized(to) {
            from.balance -= amount;
            to.balance += amount;
        }
    }
}
```

### 使用 Lock 的场景

```java
// ✅ 需要超时机制
public boolean tryTransfer(Account from, Account to, int amount) {
    if (from.lock.tryLock(1, TimeUnit.SECONDS)) {
        try {
            if (to.lock.tryLock(1, TimeUnit.SECONDS)) {
                try {
                    // 转账逻辑
                    return true;
                } finally {
                    to.lock.unlock();
                }
            }
        } finally {
            from.lock.unlock();
        }
    }
    return false;  // 超时，避免死锁
}

// ✅ 需要公平锁
Lock fairLock = new ReentrantLock(true);  // 任务调度

// ✅ 需要多个条件变量
Lock lock = new ReentrantLock();
Condition condition1 = lock.newCondition();
Condition condition2 = lock.newCondition();

// ✅ 需要可中断
lock.lockInterruptibly();  // 响应中断
```

---

## 9. 死锁对比

### synchronized 死锁示例

```java
// ❌ 死锁，且无法解除
Object lock1 = new Object();
Object lock2 = new Object();

Thread t1 = new Thread(() -> {
    synchronized(lock1) {
        sleep(10);
        synchronized(lock2) {  // 等待 lock2
            // ...
        }
    }
});

Thread t2 = new Thread(() -> {
    synchronized(lock2) {
        sleep(10);
        synchronized(lock1) {  // 等待 lock1
            // ...
        }
    }
});
```

**问题**：一旦死锁，只能重启应用。

### Lock 避免死锁

```java
// ✅ 通过 tryLock 避免死锁
public boolean tryLockBoth(Lock lock1, Lock lock2) {
    while (true) {
        if (lock1.tryLock()) {
            try {
                if (lock2.tryLock()) {
                    try {
                        return true;  // 同时获取两把锁
                    } finally {
                        lock2.unlock();
                    }
                }
            } finally {
                lock1.unlock();  // 获取 lock2 失败，释放 lock1
            }
        }
        // 重试或放弃
        Thread.sleep(random.nextInt(10));  // 随机退避
    }
}
```

---

## 10. 选择建议

### 优先使用 synchronized（默认选择）

**理由**：
- 代码简洁，不易出错
- JVM 自动优化（逃逸分析、锁消除）
- 性能已足够好
- 大多数场景无需高级特性

**示例**：
```java
// ✅ 推荐
public synchronized void simpleOperation() {
    count++;
}
```

### 使用 Lock 的场景

**满足以下任一条件时选择 Lock**：
1. 需要 **tryLock** 超时机制
2. 需要 **可中断** 的锁等待
3. 需要 **公平锁**
4. 需要 **多个条件变量**
5. 需要 **读写锁**（ReadWriteLock）

**示例**：
```java
// ✅ 需要超时
if (lock.tryLock(3, TimeUnit.SECONDS)) {
    // ...
}

// ✅ 需要多条件
Condition c1 = lock.newCondition();
Condition c2 = lock.newCondition();
```

---

## 答题总结

**synchronized 和 Lock 的主要区别**：

1. **层级**：synchronized 是 JVM 层面关键字，Lock 是 Java API
2. **使用**：synchronized 自动释放，Lock 需手动释放（finally）
3. **功能**：
   - Lock 支持超时（tryLock）、可中断（lockInterruptibly）
   - Lock 支持公平锁、多个条件变量
   - synchronized 功能简单但不易出错
4. **性能**：JDK 6 后性能接近，synchronized 甚至稍快（低竞争）
5. **适用**：
   - synchronized：简单场景，优先选择
   - Lock：复杂需求，需要高级特性

**选择原则**：优先使用 synchronized，只有在需要高级特性时才用 Lock。

