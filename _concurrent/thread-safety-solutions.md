---
title: "有哪些实现线程安全的方案"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [线程安全, 同步机制, 并发编程, JUC]
description: "全面梳理Java中实现线程安全的各种方案，包括同步机制、无锁方案及最佳实践"
nav_order: 187
parent: 并发编程
---
## 核心概念

线程安全的实现方案可以分为三大类：
1. **互斥同步（阻塞同步）**：通过锁机制保证互斥访问
2. **非阻塞同步（乐观锁）**：通过CAS等机制实现无锁并发
3. **无同步方案**：避免共享，从根本上消除线程安全问题

---

## 一、互斥同步方案

### 1. synchronized关键字

**最基本的同步机制**，JVM内置支持，自动加锁和释放。

#### 同步方法

```java
public class SynchronizedMethod {
    private int count = 0;
    
    // 实例方法同步：锁是this
    public synchronized void increment() {
        count++;
    }
    
    // 静态方法同步：锁是Class对象
    public static synchronized void staticMethod() {
        // ...
    }
}
```

#### 同步代码块

```java
public class SynchronizedBlock {
    private final Object lock = new Object();
    private int count = 0;
    
    public void increment() {
        synchronized (lock) {  // 显式指定锁对象
            count++;
        }
    }
    
    // 细粒度锁：只锁必要的部分
    public void finegrainedLock() {
        // 无需同步的代码
        int temp = someComputation();
        
        // 需要同步的代码
        synchronized (lock) {
            count += temp;
        }
    }
}
```

#### 优缺点

**优点**：
- 简单易用，自动管理锁
- JVM优化良好（偏向锁、轻量级锁）
- 异常自动释放锁

**缺点**：
- 不够灵活（无法中断等待）
- 性能相对较低（相比CAS）
- 无法实现公平锁

### 2. ReentrantLock（可重入锁）

**更灵活的锁机制**，提供了synchronized不具备的功能。

```java
public class ReentrantLockExample {
    private final ReentrantLock lock = new ReentrantLock();
    private int count = 0;
    
    // 基本使用
    public void increment() {
        lock.lock();
        try {
            count++;
        } finally {
            lock.unlock();  // 必须在finally中释放
        }
    }
    
    // 可中断的锁获取
    public void interruptibleLock() throws InterruptedException {
        lock.lockInterruptibly();  // 可以被中断
        try {
            // 临界区代码
        } finally {
            lock.unlock();
        }
    }
    
    // 尝试获取锁（非阻塞）
    public boolean tryIncrement() {
        if (lock.tryLock()) {
            try {
                count++;
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;  // 获取锁失败
    }
    
    // 超时获取锁
    public boolean tryIncrementWithTimeout() throws InterruptedException {
        if (lock.tryLock(1, TimeUnit.SECONDS)) {
            try {
                count++;
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;
    }
}
```

#### 公平锁 vs 非公平锁

```java
// 非公平锁（默认，性能更好）
ReentrantLock unfairLock = new ReentrantLock(false);

// 公平锁（按照请求顺序获取锁）
ReentrantLock fairLock = new ReentrantLock(true);
```

### 3. ReadWriteLock（读写锁）

**适用于读多写少的场景**，允许多个读操作并发执行。

```java
public class ReadWriteLockExample {
    private final ReadWriteLock rwLock = new ReentrantReadWriteLock();
    private final Lock readLock = rwLock.readLock();
    private final Lock writeLock = rwLock.writeLock();
    private final Map<String, String> cache = new HashMap<>();
    
    // 读操作：多个线程可以同时读
    public String get(String key) {
        readLock.lock();
        try {
            return cache.get(key);
        } finally {
            readLock.unlock();
        }
    }
    
    // 写操作：独占访问
    public void put(String key, String value) {
        writeLock.lock();
        try {
            cache.put(key, value);
        } finally {
            writeLock.unlock();
        }
    }
    
    // 锁降级：写锁 → 读锁
    public String updateAndRead(String key, String value) {
        writeLock.lock();
        try {
            cache.put(key, value);
            
            // 获取读锁（在释放写锁之前）
            readLock.lock();
        } finally {
            writeLock.unlock();  // 释放写锁
        }
        
        try {
            return cache.get(key);  // 使用读锁读取
        } finally {
            readLock.unlock();
        }
    }
}
```

### 4. StampedLock（JDK 8+）

**性能更高的读写锁**，支持乐观读。

```java
public class StampedLockExample {
    private final StampedLock lock = new StampedLock();
    private double x, y;
    
    // 写操作
    public void move(double deltaX, double deltaY) {
        long stamp = lock.writeLock();
        try {
            x += deltaX;
            y += deltaY;
        } finally {
            lock.unlockWrite(stamp);
        }
    }
    
    // 乐观读
    public double distanceFromOrigin() {
        long stamp = lock.tryOptimisticRead();  // 乐观读
        double currentX = x;
        double currentY = y;
        
        if (!lock.validate(stamp)) {  // 检查是否有写操作
            stamp = lock.readLock();  // 升级为悲观读锁
            try {
                currentX = x;
                currentY = y;
            } finally {
                lock.unlockRead(stamp);
            }
        }
        
        return Math.sqrt(currentX * currentX + currentY * currentY);
    }
}
```

---

## 二、非阻塞同步方案

### 1. 原子类（Atomic）

**基于CAS（Compare-And-Swap）实现**，无需加锁。

#### 基本原子类

```java
public class AtomicExample {
    // 原子整数
    private AtomicInteger count = new AtomicInteger(0);
    
    public void increment() {
        count.incrementAndGet();  // 原子操作
    }
    
    public void add(int delta) {
        count.addAndGet(delta);
    }
    
    // CAS操作
    public boolean compareAndSet(int expect, int update) {
        return count.compareAndSet(expect, update);
    }
    
    // 其他原子类
    private AtomicLong longValue = new AtomicLong(0);
    private AtomicBoolean flag = new AtomicBoolean(false);
}
```

#### 原子引用类

```java
public class AtomicReferenceExample {
    static class User {
        String name;
        int age;
        
        User(String name, int age) {
            this.name = name;
            this.age = age;
        }
    }
    
    private AtomicReference<User> userRef = 
        new AtomicReference<>(new User("Alice", 20));
    
    public void updateUser(String name, int age) {
        User oldUser, newUser;
        do {
            oldUser = userRef.get();
            newUser = new User(name, age);
        } while (!userRef.compareAndSet(oldUser, newUser));
    }
}
```

#### 原子数组

```java
public class AtomicArrayExample {
    private AtomicIntegerArray array = new AtomicIntegerArray(10);
    
    public void incrementAt(int index) {
        array.incrementAndGet(index);
    }
    
    public int getAt(int index) {
        return array.get(index);
    }
}
```

#### 字段更新器

```java
public class AtomicFieldUpdaterExample {
    // 被更新的字段必须是volatile
    private volatile int count = 0;
    
    private static final AtomicIntegerFieldUpdater<AtomicFieldUpdaterExample> updater =
        AtomicIntegerFieldUpdater.newUpdater(
            AtomicFieldUpdaterExample.class, "count");
    
    public void increment() {
        updater.incrementAndGet(this);
    }
}
```

### 2. LongAdder / LongAccumulator

**高并发下性能更好的计数器**，通过分段减少竞争。

```java
public class LongAdderExample {
    // LongAdder：专门用于累加
    private LongAdder counter = new LongAdder();
    
    public void increment() {
        counter.increment();  // 内部使用Cell数组分散竞争
    }
    
    public long sum() {
        return counter.sum();  // 汇总所有Cell的值
    }
    
    // LongAccumulator：更通用的累加器
    private LongAccumulator accumulator = 
        new LongAccumulator((x, y) -> x + y, 0);
    
    public void add(long value) {
        accumulator.accumulate(value);
    }
    
    public long get() {
        return accumulator.get();
    }
}
```

**性能对比**：

```java
// 高竞争场景
AtomicLong atomicLong = new AtomicLong(0);
LongAdder longAdder = new LongAdder();

// 1000个线程各自执行10000次
// AtomicLong: 约3000ms（大量CAS失败重试）
// LongAdder: 约300ms（分段避免竞争）
```

---

## 三、无同步方案

### 1. ThreadLocal

**线程本地存储**，每个线程有独立的副本。

```java
public class ThreadLocalExample {
    // 每个线程有自己的SimpleDateFormat实例
    private static ThreadLocal<SimpleDateFormat> dateFormat = 
        ThreadLocal.withInitial(() -> new SimpleDateFormat("yyyy-MM-dd"));
    
    public String formatDate(Date date) {
        return dateFormat.get().format(date);  // 线程安全
    }
    
    // 使用示例：数据库连接管理
    private static ThreadLocal<Connection> connectionHolder = 
        new ThreadLocal<>();
    
    public static void setConnection(Connection conn) {
        connectionHolder.set(conn);
    }
    
    public static Connection getConnection() {
        return connectionHolder.get();
    }
    
    public static void closeConnection() {
        Connection conn = connectionHolder.get();
        if (conn != null) {
            try {
                conn.close();
            } catch (SQLException e) {
                e.printStackTrace();
            } finally {
                connectionHolder.remove();  // 避免内存泄漏
            }
        }
    }
}
```

**注意事项**：
- 使用后及时`remove()`，避免内存泄漏
- 线程池环境下要特别注意清理

### 2. 不可变对象

**最佳的线程安全方案**，对象创建后不可修改。

```java
// 不可变类的设计
public final class ImmutablePerson {
    private final String name;
    private final int age;
    private final List<String> hobbies;
    
    public ImmutablePerson(String name, int age, List<String> hobbies) {
        this.name = name;
        this.age = age;
        // 防御性拷贝
        this.hobbies = Collections.unmodifiableList(
            new ArrayList<>(hobbies));
    }
    
    public String getName() { return name; }
    public int getAge() { return age; }
    public List<String> getHobbies() { return hobbies; }
    
    // "修改"操作返回新对象
    public ImmutablePerson withAge(int newAge) {
        return new ImmutablePerson(this.name, newAge, this.hobbies);
    }
}
```

**不可变类的要求**：
1. 类声明为`final`，防止子类破坏不可变性
2. 所有字段声明为`private final`
3. 不提供修改字段的方法
4. 对可变字段进行防御性拷贝
5. 不共享可变对象的引用

### 3. 栈封闭

**局部变量天然线程安全**，存储在线程栈上。

```java
public class StackConfinement {
    public int calculate(int a, int b) {
        // 局部变量，线程独享
        int result = a + b;
        int temp = result * 2;
        return temp;
    }
    
    public List<String> processList(List<String> input) {
        // 局部变量，每个线程有自己的副本
        List<String> result = new ArrayList<>();
        for (String s : input) {
            result.add(s.toUpperCase());
        }
        return result;
    }
}
```

---

## 四、并发容器

### 1. ConcurrentHashMap

**高性能的并发Map**，JDK 7使用分段锁，JDK 8使用CAS+synchronized。

```java
public class ConcurrentHashMapExample {
    private ConcurrentHashMap<String, Integer> map = 
        new ConcurrentHashMap<>();
    
    // 基本操作（线程安全）
    public void put(String key, Integer value) {
        map.put(key, value);
    }
    
    // 原子操作
    public Integer putIfAbsent(String key, Integer value) {
        return map.putIfAbsent(key, value);
    }
    
    public boolean remove(String key, Integer value) {
        return map.remove(key, value);
    }
    
    public boolean replace(String key, Integer oldValue, Integer newValue) {
        return map.replace(key, oldValue, newValue);
    }
    
    // JDK 8+ 函数式操作
    public void computeIfAbsent(String key) {
        map.computeIfAbsent(key, k -> expensiveComputation(k));
    }
    
    public void merge(String key, Integer value) {
        map.merge(key, value, (oldVal, newVal) -> oldVal + newVal);
    }
    
    private Integer expensiveComputation(String key) {
        return key.length();
    }
}
```

### 2. CopyOnWriteArrayList

**写时复制的List**，适用于读多写少的场景。

```java
public class CopyOnWriteArrayListExample {
    private CopyOnWriteArrayList<String> list = 
        new CopyOnWriteArrayList<>();
    
    // 写操作：复制整个数组
    public void add(String element) {
        list.add(element);  // 内部会复制数组
    }
    
    // 读操作：不加锁
    public String get(int index) {
        return list.get(index);
    }
    
    // 遍历：不会抛出ConcurrentModificationException
    public void iterate() {
        for (String s : list) {
            System.out.println(s);  // 即使其他线程在写，也不会出错
        }
    }
}
```

**适用场景**：
- 读操作远多于写操作
- 事件监听器列表
- 配置信息列表

### 3. BlockingQueue

**阻塞队列**，适用于生产者-消费者模式。

```java
public class BlockingQueueExample {
    // ArrayBlockingQueue：有界队列
    private BlockingQueue<Task> queue = 
        new ArrayBlockingQueue<>(100);
    
    // 生产者
    public void produce(Task task) throws InterruptedException {
        queue.put(task);  // 队列满时阻塞
    }
    
    // 消费者
    public Task consume() throws InterruptedException {
        return queue.take();  // 队列空时阻塞
    }
    
    // 其他常用方法
    public boolean offer(Task task) {
        return queue.offer(task);  // 非阻塞，返回false表示失败
    }
    
    public Task poll() {
        return queue.poll();  // 非阻塞，返回null表示队列空
    }
}

// 其他BlockingQueue实现
// LinkedBlockingQueue：无界队列（或有界）
// PriorityBlockingQueue：优先级队列
// DelayQueue：延迟队列
// SynchronousQueue：容量为0的队列
```

---

## 五、综合实践案例

### 案例1：线程安全的单例

```java
// 方案1：饿汉式（类加载时初始化）
public class EagerSingleton {
    private static final EagerSingleton INSTANCE = new EagerSingleton();
    private EagerSingleton() {}
    public static EagerSingleton getInstance() {
        return INSTANCE;
    }
}

// 方案2：静态内部类（推荐）
public class StaticInnerSingleton {
    private StaticInnerSingleton() {}
    
    private static class Holder {
        private static final StaticInnerSingleton INSTANCE = 
            new StaticInnerSingleton();
    }
    
    public static StaticInnerSingleton getInstance() {
        return Holder.INSTANCE;
    }
}

// 方案3：DCL（双重检查锁定）
public class DclSingleton {
    private static volatile DclSingleton instance;
    private DclSingleton() {}
    
    public static DclSingleton getInstance() {
        if (instance == null) {
            synchronized (DclSingleton.class) {
                if (instance == null) {
                    instance = new DclSingleton();
                }
            }
        }
        return instance;
    }
}
```

### 案例2：线程安全的缓存

```java
public class ThreadSafeCache<K, V> {
    private final ConcurrentHashMap<K, V> cache = new ConcurrentHashMap<>();
    private final Function<K, V> loader;
    
    public ThreadSafeCache(Function<K, V> loader) {
        this.loader = loader;
    }
    
    public V get(K key) {
        // 方案1：简单但可能重复计算
        V value = cache.get(key);
        if (value == null) {
            value = loader.apply(key);
            cache.put(key, value);
        }
        return value;
        
        // 方案2：使用computeIfAbsent（推荐）
        // return cache.computeIfAbsent(key, loader);
    }
    
    // 带超时的缓存
    static class CacheEntry<V> {
        final V value;
        final long expireTime;
        
        CacheEntry(V value, long ttl) {
            this.value = value;
            this.expireTime = System.currentTimeMillis() + ttl;
        }
        
        boolean isExpired() {
            return System.currentTimeMillis() > expireTime;
        }
    }
}
```

### 案例3：生产者-消费者

```java
public class ProducerConsumer {
    private final BlockingQueue<Task> queue = 
        new LinkedBlockingQueue<>(100);
    
    // 生产者线程
    class Producer implements Runnable {
        @Override
        public void run() {
            try {
                while (!Thread.interrupted()) {
                    Task task = produceTask();
                    queue.put(task);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        
        private Task produceTask() {
            return new Task();
        }
    }
    
    // 消费者线程
    class Consumer implements Runnable {
        @Override
        public void run() {
            try {
                while (!Thread.interrupted()) {
                    Task task = queue.take();
                    processTask(task);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        
        private void processTask(Task task) {
            // 处理任务
        }
    }
}
```

---

## 六、方案选择指南

### 选择原则

```
1. 优先考虑不可变对象
   ↓
2. 考虑ThreadLocal（避免共享）
   ↓
3. 考虑JUC并发容器
   ↓
4. 考虑原子类（CAS）
   ↓
5. 考虑Lock（需要高级特性）
   ↓
6. 使用synchronized（简单场景）
```

### 场景对应

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| **计数器** | `LongAdder` | 高并发性能好 |
| **缓存** | `ConcurrentHashMap` | 读写都高效 |
| **单例** | 静态内部类 | 懒加载+线程安全 |
| **读多写少** | `ReadWriteLock` | 读并发，写互斥 |
| **监听器列表** | `CopyOnWriteArrayList` | 遍历不加锁 |
| **生产者-消费者** | `BlockingQueue` | 自动阻塞唤醒 |
| **日期格式化** | `ThreadLocal` | 避免共享 |

---

## 面试总结

### 核心要点

1. **三大类方案**：互斥同步、非阻塞同步、无同步
2. **优先顺序**：不可变 > 无同步 > CAS > Lock > synchronized
3. **并发容器**：ConcurrentHashMap、CopyOnWriteArrayList、BlockingQueue
4. **根据场景选择**：读多写少、高竞争、需要阻塞等

### 答题模板

**简明版**：
- 互斥同步：synchronized、Lock
- 非阻塞：Atomic原子类、CAS
- 无同步：ThreadLocal、不可变对象
- 并发容器：ConcurrentHashMap、CopyOnWriteArrayList

**完整版**：
1. **互斥同步**：synchronized（简单）、ReentrantLock（灵活）、ReadWriteLock（读多写少）
2. **非阻塞同步**：AtomicInteger、LongAdder（高并发计数）
3. **无同步方案**：不可变对象（最佳）、ThreadLocal（线程本地）、栈封闭
4. **并发容器**：ConcurrentHashMap（缓存）、BlockingQueue（生产消费）
5. **选择依据**：并发度、读写比例、是否需要阻塞、性能要求

### 常见面试题

**Q：synchronized和ReentrantLock的区别？**
- synchronized是关键字，Lock是接口
- Lock更灵活（可中断、超时、公平锁）
- synchronized自动释放，Lock需手动释放
- synchronized是JVM实现，Lock是JDK实现

**Q：什么时候用LongAdder而不是AtomicLong？**
- 高并发写场景用LongAdder
- LongAdder通过分段减少CAS竞争
- 单线程或低竞争用AtomicLong

**Q：CopyOnWriteArrayList适用什么场景？**
- 读多写少
- 可以容忍写操作的开销（复制数组）
- 事件监听器、配置列表等

