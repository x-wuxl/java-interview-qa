---
layout: default
title: "ReentrantLock增加了哪些高级功能？"
parent: 并发编程
nav_order: 234
description: "详解ReentrantLock相比synchronized提供的轮询、超时、中断、公平锁和非公平锁等高级功能"
author: "wuxl"
date: 2025-11-02
---
## 问题

ReentrantLock增加了轮询、超时、中断、公平锁和非公平锁等高级功能。

## 答案

### 1. 核心概念

相比 `synchronized`，**ReentrantLock** 提供了以下高级功能：

1. **轮询（tryLock）**：非阻塞尝试获取锁
2. **超时（tryLock with timeout）**：在指定时间内尝试获取锁
3. **可中断（lockInterruptibly）**：等待锁时可响应中断
4. **公平锁（Fair Lock）**：按照线程请求顺序分配锁
5. **非公平锁（Unfair Lock）**：允许"插队"，性能更好
6. **多条件变量（Condition）**：支持多个等待队列

这些高级功能使 ReentrantLock 在复杂并发场景下比 synchronized 更灵活强大。

### 2. 轮询功能（tryLock）

#### 2.1 基本概念

**tryLock()**：非阻塞地尝试获取锁，立即返回成功或失败。

**特点**：
- 不会阻塞线程
- 立即返回 `true`（成功）或 `false`（失败）
- 可以避免死锁

#### 2.2 使用示例

```java
ReentrantLock lock = new ReentrantLock();

// 非阻塞尝试获取锁
if (lock.tryLock()) {
    try {
        // 成功获取锁，执行业务逻辑
        System.out.println("获取锁成功");
    } finally {
        lock.unlock();
    }
} else {
    // 获取锁失败，执行其他逻辑
    System.out.println("获取锁失败，执行其他任务");
}
```

#### 2.3 避免死锁

```java
public class DeadlockAvoidance {
    private final ReentrantLock lock1 = new ReentrantLock();
    private final ReentrantLock lock2 = new ReentrantLock();

    public void transferMoney() {
        while (true) {
            if (lock1.tryLock()) {  // 尝试获取 lock1
                try {
                    if (lock2.tryLock()) {  // 尝试获取 lock2
                        try {
                            // 两个锁都获取成功，执行转账
                            System.out.println("转账成功");
                            return;
                        } finally {
                            lock2.unlock();
                        }
                    }
                } finally {
                    lock1.unlock();
                }
            }

            // 如果获取失败，稍后重试
            try {
                Thread.sleep(10);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }
}
```

### 3. 超时功能（tryLock with timeout）

#### 3.1 基本概念

**tryLock(long timeout, TimeUnit unit)**：在指定时间内尝试获取锁，超时返回失败。

**特点**：
- 限制等待时间，避免无限阻塞
- 可以设置超时策略
- 超时后可执行补偿逻辑

#### 3.2 使用示例

```java
ReentrantLock lock = new ReentrantLock();

// 在 3 秒内尝试获取锁
try {
    if (lock.tryLock(3, TimeUnit.SECONDS)) {
        try {
            // 成功获取锁
            System.out.println("获取锁成功");
        } finally {
            lock.unlock();
        }
    } else {
        // 超时未获取到锁
        System.out.println("获取锁超时");
    }
} catch (InterruptedException e) {
    System.out.println("等待锁时被中断");
}
```

#### 3.3 实际应用：防止饥饿

```java
public class OrderService {
    private final ReentrantLock lock = new ReentrantLock();

    public boolean processOrder(Order order) {
        try {
            // 最多等待 5 秒
            if (lock.tryLock(5, TimeUnit.SECONDS)) {
                try {
                    // 处理订单
                    return true;
                } finally {
                    lock.unlock();
                }
            } else {
                // 超时，订单处理失败
                System.err.println("订单处理超时，订单号：" + order.getId());
                return false;
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return false;
        }
    }
}
```

### 4. 可中断功能（lockInterruptibly）

#### 4.1 基本概念

**lockInterruptibly()**：在等待锁的过程中，可以响应中断信号。

**特点**：
- 可以取消正在等待的线程
- 抛出 `InterruptedException`
- 比 synchronized 更灵活

**对比 synchronized**：
- `synchronized`：等待锁时不可中断
- `ReentrantLock`：通过 `lockInterruptibly()` 可中断

#### 4.2 使用示例

```java
ReentrantLock lock = new ReentrantLock();

Thread t = new Thread(() -> {
    try {
        System.out.println("尝试获取锁");
        lock.lockInterruptibly();  // 可中断等待
        try {
            System.out.println("获取锁成功");
            Thread.sleep(10000);  // 模拟长时间持有锁
        } finally {
            lock.unlock();
        }
    } catch (InterruptedException e) {
        System.out.println("等待锁时被中断");
    }
});

t.start();
Thread.sleep(1000);

// 中断线程
t.interrupt();
System.out.println("发送中断信号");

// 输出：
// 尝试获取锁
// 发送中断信号
// 等待锁时被中断
```

#### 4.3 实际应用：任务取消

```java
public class CancelableTask {
    private final ReentrantLock lock = new ReentrantLock();

    public void executeTask() {
        try {
            lock.lockInterruptibly();  // 可中断
            try {
                // 执行长时间任务
                while (!Thread.currentThread().isInterrupted()) {
                    // 业务逻辑
                }
            } finally {
                lock.unlock();
            }
        } catch (InterruptedException e) {
            System.out.println("任务被取消");
            Thread.currentThread().interrupt();  // 恢复中断状态
        }
    }

    public void cancelTask(Thread taskThread) {
        taskThread.interrupt();  // 中断任务线程
    }
}
```

### 5. 公平锁功能

#### 5.1 基本概念

**公平锁（Fair Lock）**：按照线程请求锁的顺序（FIFO）分配锁。

**特点**：
- 保证先来先得
- 避免线程饥饿
- 性能略低于非公平锁

#### 5.2 使用示例

```java
// 创建公平锁
ReentrantLock fairLock = new ReentrantLock(true);

for (int i = 0; i < 5; i++) {
    new Thread(() -> {
        fairLock.lock();
        try {
            System.out.println(Thread.currentThread().getName() + " 获得锁");
        } finally {
            fairLock.unlock();
        }
    }, "Thread-" + i).start();
}

// 输出（按顺序）：
// Thread-0 获得锁
// Thread-1 获得锁
// Thread-2 获得锁
// Thread-3 获得锁
// Thread-4 获得锁
```

#### 5.3 实际应用：订单处理系统

```java
public class OrderProcessor {
    // 公平锁保证订单按时间顺序处理
    private final ReentrantLock lock = new ReentrantLock(true);

    public void processOrder(Order order) {
        lock.lock();
        try {
            System.out.println("处理订单：" + order.getId() + "，时间：" + order.getTimestamp());
            // 处理订单逻辑
        } finally {
            lock.unlock();
        }
    }
}
```

### 6. 非公平锁功能

#### 6.1 基本概念

**非公平锁（Unfair Lock）**：线程获取锁时不考虑等待队列，直接尝试获取。

**特点**：
- 允许"插队"
- 性能更好（减少上下文切换）
- 可能导致线程饥饿

#### 6.2 使用示例

```java
// 创建非公平锁（默认）
ReentrantLock unfairLock = new ReentrantLock();
// 或显式指定
ReentrantLock unfairLock = new ReentrantLock(false);

unfairLock.lock();
try {
    // 业务逻辑
} finally {
    unfairLock.unlock();
}
```

### 7. 多条件变量（Condition）

#### 7.1 基本概念

**Condition**：类似于 `Object.wait()/notify()`，但更强大。

**特点**：
- 一个锁可以创建多个 Condition
- 精准控制线程的等待和唤醒
- 支持 `await()`、`signal()`、`signalAll()`

#### 7.2 使用示例

```java
ReentrantLock lock = new ReentrantLock();
Condition notFull = lock.newCondition();   // 条件 1：不满
Condition notEmpty = lock.newCondition();  // 条件 2：不空

// 生产者
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

// 消费者
lock.lock();
try {
    while (queue.isEmpty()) {
        notEmpty.await();  // 等待"不空"条件
    }
    Item item = queue.remove();
    notFull.signal();      // 通知"不满"条件
} finally {
    lock.unlock();
}
```

#### 7.3 实际应用：阻塞队列

```java
public class BoundedQueue<T> {
    private final Queue<T> queue = new LinkedList<>();
    private final int capacity;
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();

    public BoundedQueue(int capacity) {
        this.capacity = capacity;
    }

    public void put(T item) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == capacity) {
                notFull.await();  // 队列满，等待
            }
            queue.add(item);
            notEmpty.signal();    // 通知消费者
        } finally {
            lock.unlock();
        }
    }

    public T take() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) {
                notEmpty.await();  // 队列空，等待
            }
            T item = queue.remove();
            notFull.signal();      // 通知生产者
            return item;
        } finally {
            lock.unlock();
        }
    }
}
```

### 8. 功能对比总结

| 功能 | synchronized | ReentrantLock |
|------|-------------|---------------|
| **轮询** | ❌ 不支持 | ✅ `tryLock()` |
| **超时** | ❌ 不支持 | ✅ `tryLock(timeout, unit)` |
| **可中断** | ❌ 不可中断 | ✅ `lockInterruptibly()` |
| **公平锁** | ❌ 非公平 | ✅ `new ReentrantLock(true)` |
| **非公平锁** | ✅ 默认非公平 | ✅ `new ReentrantLock(false)` |
| **多条件变量** | ❌ 只有一个 | ✅ `newCondition()` |

### 9. 选择建议

**使用 synchronized**：
- 简单场景
- 不需要高级功能
- JVM 内置优化已足够

**使用 ReentrantLock**：
- 需要轮询或超时获取锁
- 需要可中断的锁等待
- 需要公平锁
- 需要多个条件变量
- 需要获取锁的状态信息（`isLocked()`、`getHoldCount()` 等）

### 10. 实际案例：数据库连接池

```java
public class ConnectionPool {
    private final Queue<Connection> connections = new LinkedList<>();
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notEmpty = lock.newCondition();

    // 获取连接（超时）
    public Connection getConnection(long timeout, TimeUnit unit) throws InterruptedException {
        lock.lock();
        try {
            long nanos = unit.toNanos(timeout);
            while (connections.isEmpty()) {
                if (nanos <= 0) {
                    return null;  // 超时
                }
                nanos = notEmpty.awaitNanos(nanos);  // 等待指定时间
            }
            return connections.remove();
        } finally {
            lock.unlock();
        }
    }

    // 释放连接
    public void releaseConnection(Connection conn) {
        lock.lock();
        try {
            connections.add(conn);
            notEmpty.signal();  // 通知等待的线程
        } finally {
            lock.unlock();
        }
    }
}
```

### 11. 性能考量

**非公平锁 vs 公平锁**：
- 非公平锁性能通常是公平锁的 **10-100 倍**
- 默认使用非公平锁

**可中断 vs 不可中断**：
- `lockInterruptibly()` 比 `lock()` 略慢，但更灵活
- 根据需求选择

### 12. 总结

ReentrantLock 提供的高级功能：

1. **轮询（tryLock）**：非阻塞尝试获取锁，避免死锁
2. **超时（tryLock with timeout）**：限制等待时间，防止无限阻塞
3. **可中断（lockInterruptibly）**：等待锁时可响应中断，支持任务取消
4. **公平锁**：按顺序分配锁，保证公平性，避免饥饿
5. **非公平锁**：允许插队，性能更好（默认）
6. **多条件变量（Condition）**：支持多个等待队列，精准控制

**面试要点**：
- 列举 ReentrantLock 的高级功能
- 说明每个功能的应用场景（轮询避免死锁、超时防止饥饿、可中断支持取消）
- 对比 synchronized 和 ReentrantLock 的差异
- 理解公平锁和非公平锁的性能权衡

**记忆口诀**：
- 轮询超时可中断，公平非公平可选
- 多个条件精准控，灵活强大比 sync 全
