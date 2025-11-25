---
layout: default
title: "什么是死锁，如何解决？"
parent: 并发编程
nav_order: 181
description: "深入理解死锁的概念、产生条件、检测方法和解决方案，掌握预防死锁的最佳实践，提升并发程序的稳定性。"
date: 2025-11-02
---
## 核心概念

**死锁（Deadlock）**是指两个或多个线程互相持有对方需要的资源，导致所有线程都无法继续执行的状态。

```
线程A持有资源1，等待资源2
      ↓
   [死锁]
      ↑
线程B持有资源2，等待资源1
```

## 死锁示例

### 经典死锁场景

```java
public class DeadlockDemo {
    private static final Object lock1 = new Object();
    private static final Object lock2 = new Object();

    public static void main(String[] args) {
        // 线程1：先获取lock1，再获取lock2
        Thread thread1 = new Thread(() -> {
            synchronized (lock1) {
                System.out.println("线程1获取lock1");
                try {
                    Thread.sleep(100); // 增加死锁概率
                } catch (InterruptedException e) {
                }
                System.out.println("线程1等待lock2...");
                synchronized (lock2) {
                    System.out.println("线程1获取lock2");
                }
            }
        }, "Thread-1");

        // 线程2：先获取lock2，再获取lock1
        Thread thread2 = new Thread(() -> {
            synchronized (lock2) {
                System.out.println("线程2获取lock2");
                try {
                    Thread.sleep(100);
                } catch (InterruptedException e) {
                }
                System.out.println("线程2等待lock1...");
                synchronized (lock1) {
                    System.out.println("线程2获取lock1");
                }
            }
        }, "Thread-2");

        thread1.start();
        thread2.start();
    }
}
```

**输出**：
```
线程1获取lock1
线程2获取lock2
线程1等待lock2...
线程2等待lock1...
// 程序卡死，死锁发生
```

## 死锁产生的四个必要条件

### 1. 互斥条件（Mutual Exclusion）

**定义**：资源只能被一个线程占用，其他线程必须等待。

```java
synchronized (lock) {
    // 同一时刻只有一个线程能进入
}
```

### 2. 请求与保持条件（Hold and Wait）

**定义**：线程已持有至少一个资源，同时又请求其他资源。

```java
synchronized (lock1) {       // 持有lock1
    synchronized (lock2) {    // 请求lock2
        // ...
    }
}
```

### 3. 不可剥夺条件（No Preemption）

**定义**：线程持有的资源不能被强制剥夺，只能主动释放。

```java
// synchronized锁无法被外部中断
// 线程只能等待或自己释放
```

### 4. 循环等待条件（Circular Wait）

**定义**：存在线程资源的循环等待链。

```
线程A → 资源1 → 线程B → 资源2 → 线程A
   ↑___________________________________|
                循环等待
```

**破坏任意一个条件即可避免死锁。**

## 死锁检测

### 1. jstack命令行工具

```bash
# 1. 找到Java进程PID
jps -l

# 2. 打印线程堆栈
jstack <pid>

# 输出示例：
Found one Java-level deadlock:
=============================
"Thread-2":
  waiting to lock monitor 0x00007f8b8c004e00 (object 0x000000076ab48d98, a java.lang.Object),
  which is held by "Thread-1"
"Thread-1":
  waiting to lock monitor 0x00007f8b8c007350 (object 0x000000076ab48da8, a java.lang.Object),
  which is held by "Thread-2"

Java stack information for the threads listed above:
===================================================
"Thread-2":
	at DeadlockDemo.lambda$main$1(DeadlockDemo.java:30)
	- waiting to lock <0x000000076ab48d98> (a java.lang.Object)
	- locked <0x000000076ab48da8> (a java.lang.Object)
```

### 2. JConsole图形化工具

```java
// 启动JConsole
// 1. 运行：jconsole
// 2. 连接到目标进程
// 3. 切换到"线程"标签
// 4. 点击"检测死锁"按钮
```

### 3. ThreadMXBean编程检测

```java
public class DeadlockDetector {
    public static void detectDeadlock() {
        ThreadMXBean threadMXBean = ManagementFactory.getThreadMXBean();
        
        // 检测死锁
        long[] deadlockedThreads = threadMXBean.findDeadlockedThreads();
        
        if (deadlockedThreads != null) {
            System.out.println("检测到死锁！");
            ThreadInfo[] threadInfos = threadMXBean.getThreadInfo(deadlockedThreads);
            for (ThreadInfo threadInfo : threadInfos) {
                System.out.println("线程名: " + threadInfo.getThreadName());
                System.out.println("线程状态: " + threadInfo.getThreadState());
                System.out.println("锁名: " + threadInfo.getLockName());
                System.out.println("锁持有者: " + threadInfo.getLockOwnerName());
                System.out.println("---");
            }
        } else {
            System.out.println("未检测到死锁");
        }
    }

    public static void main(String[] args) throws InterruptedException {
        // 启动死锁场景
        DeadlockDemo.main(args);
        
        // 等待死锁发生
        Thread.sleep(1000);
        
        // 检测死锁
        detectDeadlock();
    }
}
```

### 4. 定时监控

```java
public class DeadlockMonitor {
    private final ScheduledExecutorService scheduler = 
        Executors.newScheduledThreadPool(1);
    private final ThreadMXBean threadMXBean = 
        ManagementFactory.getThreadMXBean();

    public void startMonitoring() {
        scheduler.scheduleAtFixedRate(() -> {
            long[] deadlockedThreads = threadMXBean.findDeadlockedThreads();
            if (deadlockedThreads != null) {
                System.err.println("【告警】检测到死锁，涉及线程数: " + 
                    deadlockedThreads.length);
                // 发送告警、记录日志等
                handleDeadlock(deadlockedThreads);
            }
        }, 0, 10, TimeUnit.SECONDS); // 每10秒检测一次
    }

    private void handleDeadlock(long[] threadIds) {
        ThreadInfo[] threadInfos = threadMXBean.getThreadInfo(threadIds, true, true);
        for (ThreadInfo info : threadInfos) {
            System.err.println("死锁线程: " + info.getThreadName());
            System.err.println("堆栈信息:");
            for (StackTraceElement element : info.getStackTrace()) {
                System.err.println("  " + element);
            }
        }
    }
}
```

## 死锁解决方案

### 方案1：破坏请求与保持条件（一次性申请所有资源）

```java
// ❌ 原始代码（可能死锁）
public class BankTransfer {
    public void transfer(Account from, Account to, int amount) {
        synchronized (from) {           // 持有from
            synchronized (to) {          // 请求to
                from.debit(amount);
                to.credit(amount);
            }
        }
    }
}

// ✅ 方案1：一次性申请所有资源
public class BankTransferFixed1 {
    private static final Object tieLock = new Object();

    public void transfer(Account from, Account to, int amount) {
        synchronized (tieLock) {         // 先获取全局锁
            synchronized (from) {
                synchronized (to) {
                    from.debit(amount);
                    to.credit(amount);
                }
            }
        }
    }
}
```

**缺点**：降低并发度。

### 方案2：破坏不可剥夺条件（超时释放）

```java
// ✅ 使用tryLock超时机制
public class BankTransferFixed2 {
    public boolean transfer(Account from, Account to, int amount) 
            throws InterruptedException {
        boolean fromLocked = false;
        boolean toLocked = false;

        try {
            // 尝试获取from锁，超时1秒
            fromLocked = from.getLock().tryLock(1, TimeUnit.SECONDS);
            if (!fromLocked) {
                return false; // 获取失败，返回
            }

            // 尝试获取to锁，超时1秒
            toLocked = to.getLock().tryLock(1, TimeUnit.SECONDS);
            if (!toLocked) {
                return false; // 获取失败，返回
            }

            // 执行转账
            from.debit(amount);
            to.credit(amount);
            return true;

        } finally {
            if (fromLocked) from.getLock().unlock();
            if (toLocked) to.getLock().unlock();
        }
    }
}
```

### 方案3：破坏循环等待条件（资源排序）

```java
// ✅ 按照统一顺序获取锁
public class BankTransferFixed3 {
    public void transfer(Account from, Account to, int amount) {
        // 按照账户ID排序
        Account first = from.getId() < to.getId() ? from : to;
        Account second = from.getId() < to.getId() ? to : from;

        synchronized (first) {      // 先获取ID小的锁
            synchronized (second) {  // 再获取ID大的锁
                from.debit(amount);
                to.credit(amount);
            }
        }
    }
}

class Account {
    private final int id;
    private int balance;

    public Account(int id, int balance) {
        this.id = id;
        this.balance = balance;
    }

    public int getId() {
        return id;
    }

    public synchronized void debit(int amount) {
        balance -= amount;
    }

    public synchronized void credit(int amount) {
        balance += amount;
    }
}
```

**推荐**：这是最常用的死锁预防方案。

### 方案4：使用并发工具类

```java
// ✅ 使用Semaphore
public class BankTransferFixed4 {
    private final Semaphore semaphore = new Semaphore(1);

    public void transfer(Account from, Account to, int amount) 
            throws InterruptedException {
        semaphore.acquire(); // 同一时刻只允许一个转账
        try {
            from.debit(amount);
            to.credit(amount);
        } finally {
            semaphore.release();
        }
    }
}

// ✅ 使用ReadWriteLock
public class DataManager {
    private final ReadWriteLock lock = new ReentrantReadWriteLock();
    private Map<String, String> data = new HashMap<>();

    public String read(String key) {
        lock.readLock().lock(); // 读锁不会死锁
        try {
            return data.get(key);
        } finally {
            lock.readLock().unlock();
        }
    }

    public void write(String key, String value) {
        lock.writeLock().lock();
        try {
            data.put(key, value);
        } finally {
            lock.writeLock().unlock();
        }
    }
}
```

## 避免死锁的最佳实践

### 1. 锁顺序一致

```java
// ✅ 所有地方都按相同顺序获取锁
public class LockOrdering {
    private static final Object lock1 = new Object();
    private static final Object lock2 = new Object();
    private static final Object lock3 = new Object();

    public void method1() {
        synchronized (lock1) {
            synchronized (lock2) {
                synchronized (lock3) {
                    // 业务逻辑
                }
            }
        }
    }

    public void method2() {
        // 必须保持相同顺序：lock1 → lock2 → lock3
        synchronized (lock1) {
            synchronized (lock2) {
                // 业务逻辑
            }
        }
    }
}
```

### 2. 缩小锁范围

```java
// ❌ 锁范围过大
public synchronized void largeMethod() {
    // 100行代码
    // 只有最后10行需要同步
}

// ✅ 缩小锁范围
public void optimizedMethod() {
    // 90行不需要同步的代码
    
    synchronized (this) {
        // 只同步必要的10行
    }
}
```

### 3. 使用tryLock超时

```java
// ✅ 设置超时，避免无限等待
Lock lock = new ReentrantLock();

if (lock.tryLock(1, TimeUnit.SECONDS)) {
    try {
        // 业务逻辑
    } finally {
        lock.unlock();
    }
} else {
    // 获取锁失败，执行降级逻辑
    handleLockFailure();
}
```

### 4. 避免嵌套锁

```java
// ❌ 嵌套锁容易死锁
synchronized (lock1) {
    synchronized (lock2) {
        // ...
    }
}

// ✅ 尽量单一锁
synchronized (lock) {
    // 一次性完成操作
}
```

### 5. 使用并发容器

```java
// ❌ 手动同步
Map<String, String> map = new HashMap<>();
synchronized (map) {
    map.put("key", "value");
}

// ✅ 使用并发容器
ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>();
map.put("key", "value"); // 内部已优化，避免死锁
```

### 6. 开放调用（Open Call）

```java
// ❌ 在持有锁时调用外部方法
synchronized (lock) {
    externalMethod(); // 可能导致死锁
}

// ✅ 开放调用
Object snapshot;
synchronized (lock) {
    snapshot = getState();
}
externalMethod(snapshot); // 锁外调用
```

## 死锁 vs 活锁 vs 饥饿

### 死锁（Deadlock）

```java
// 线程互相等待，都无法继续
```

### 活锁（Livelock）

```java
// 线程不断重试，但都无法成功
public class LivelockDemo {
    static class Spoon {
        private Diner owner;

        public synchronized void use() {
            System.out.printf("%s正在用勺子吃饭%n", owner.name);
        }

        public synchronized void setOwner(Diner diner) {
            owner = diner;
        }
    }

    static class Diner {
        private String name;
        private boolean isHungry;

        public void eatWith(Spoon spoon, Diner spouse) {
            while (isHungry) {
                // 如果勺子不是自己的
                if (spoon.owner != this) {
                    try {
                        Thread.sleep(1);
                    } catch (InterruptedException e) {
                    }
                    continue; // 继续等待
                }

                // 如果配偶也饿了
                if (spouse.isHungry) {
                    System.out.println(name + ": 亲爱的，你先吃吧");
                    spoon.setOwner(spouse); // 礼让
                    continue; // 活锁：两人不断礼让
                }

                // 吃饭
                spoon.use();
                isHungry = false;
            }
        }
    }
}
```

### 饥饿（Starvation）

```java
// 低优先级线程长期得不到执行
Thread lowPriority = new Thread(() -> {
    // 永远得不到CPU时间
});
lowPriority.setPriority(Thread.MIN_PRIORITY);
```

| 问题 | 特征 | 解决方案 |
|------|------|---------|
| **死锁** | 互相等待，永久阻塞 | 破坏死锁条件 |
| **活锁** | 不断重试，无法成功 | 引入随机性 |
| **饥饿** | 长期得不到资源 | 公平锁、优先级调整 |

## 答题总结

**面试标准答案**：

### 死锁定义
**死锁**是指多个线程互相持有对方需要的资源，导致所有线程都无法继续执行。

### 产生条件（四个必要条件）
1. **互斥条件**：资源只能被一个线程占用
2. **请求与保持**：持有资源的同时请求其他资源
3. **不可剥夺**：资源不能被强制释放
4. **循环等待**：存在线程-资源的循环等待链

### 检测方法
1. **jstack**：命令行工具，打印线程堆栈
2. **JConsole**：图形化工具，"检测死锁"按钮
3. **ThreadMXBean**：编程检测，`findDeadlockedThreads()`

### 解决方案
1. **破坏请求与保持**：一次性申请所有资源
2. **破坏不可剥夺**：使用`tryLock()`超时机制
3. **破坏循环等待**：资源排序，统一获取顺序（推荐）
4. **使用并发工具**：Semaphore、ReadWriteLock

### 最佳实践
1. **锁顺序一致**：全局统一的加锁顺序
2. **缩小锁范围**：只锁必要的代码
3. **避免嵌套锁**：尽量单一锁
4. **使用并发容器**：ConcurrentHashMap等
5. **超时机制**：`tryLock(timeout)`
6. **开放调用**：锁外调用外部方法

**核心记忆**：死锁 = 相互等待，解决 = 破坏四个条件之一，最常用 = 资源排序。

