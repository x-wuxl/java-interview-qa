---
layout: default
title: "能不能谈谈你对线程安全的理解？"
parent: 并发编程
nav_order: 186
description: "深入理解线程安全的概念、级别及其在Java并发编程中的实现"
date: 2025-11-02
---
## 核心概念

**线程安全（Thread Safety）** 是指当多个线程访问同一个对象或执行同一段代码时，不需要额外的同步措施或调用方进行协调，程序依然能够正确运行，不会出现数据不一致、死锁等问题。

**简单来说**：多个线程同时访问，结果依然正确。

---

## 线程安全的定义

### 经典定义

> 当多个线程访问一个对象时，如果不用考虑这些线程在运行时环境下的调度和交替执行，也不需要进行额外的同步，或者在调用方进行任何其他的协调操作，调用这个对象的行为都可以获得正确的结果，那这个对象就是线程安全的。
> —— Brian Goetz《Java Concurrency in Practice》

### 三个核心要素

1. **原子性（Atomicity）**：操作不可分割，要么全部执行，要么全部不执行
2. **可见性（Visibility）**：一个线程的修改对其他线程立即可见
3. **有序性（Ordering）**：程序执行的顺序按照代码的先后顺序执行

---

## 线程不安全的表现

### 1. 数据竞争（Data Race）

```java
// 典型的线程不安全示例
public class UnsafeCounter {
    private int count = 0;
    
    public void increment() {
        count++;  // 非原子操作：读取、加1、写回
    }
    
    public int getCount() {
        return count;
    }
}

// 测试
UnsafeCounter counter = new UnsafeCounter();
// 10个线程各自执行1000次increment
for (int i = 0; i < 10; i++) {
    new Thread(() -> {
        for (int j = 0; j < 1000; j++) {
            counter.increment();
        }
    }).start();
}
// 预期结果：10000
// 实际结果：<10000（如9856），发生了数据丢失
```

**问题分析**：
```
时间 | 线程A          | 线程B          | count值
-----|---------------|---------------|--------
T1   | 读取count=0   |               | 0
T2   |               | 读取count=0   | 0
T3   | 计算0+1=1     |               | 0
T4   |               | 计算0+1=1     | 0
T5   | 写回count=1   |               | 1
T6   |               | 写回count=1   | 1
结果：两次increment操作，count只增加了1次
```

### 2. 可见性问题

```java
// 可见性问题示例
public class VisibilityProblem {
    private boolean flag = false;
    private int value = 0;
    
    // 线程1执行
    public void writer() {
        value = 42;
        flag = true;
    }
    
    // 线程2执行
    public void reader() {
        while (!flag) {
            // 可能永远循环，因为看不到flag的修改
        }
        System.out.println(value);  // 可能输出0或42
    }
}
```

**问题原因**：
- CPU缓存：线程2的flag值在本地缓存中，看不到线程1的修改
- 编译器优化：编译器可能将`while(!flag)`优化为`if(!flag) while(true)`

### 3. 有序性问题

```java
// 有序性问题示例
public class OrderingProblem {
    private int a = 0;
    private boolean initialized = false;
    
    // 线程1
    public void init() {
        a = 42;                    // 操作1
        initialized = true;        // 操作2
        // 可能发生重排序：操作2在操作1之前执行
    }
    
    // 线程2
    public void use() {
        if (initialized) {         // 操作3
            int b = a * 2;         // 操作4：可能a还是0
        }
    }
}
```

**问题原因**：
- 指令重排序：CPU或编译器为了性能，可能调整执行顺序
- 在单线程中，重排序不影响结果
- 在多线程中，重排序可能导致错误

---

## 线程安全的级别

根据《Java Concurrency in Practice》，线程安全可以分为5个级别：

### 1. 不可变（Immutable）

**最高安全级别**，对象创建后状态不能改变，天然线程安全。

```java
// String类是不可变的
String str = "Hello";
str.concat(" World");  // 返回新对象，原对象不变

// 自定义不可变类
public final class ImmutablePoint {
    private final int x;
    private final int y;
    
    public ImmutablePoint(int x, int y) {
        this.x = x;
        this.y = y;
    }
    
    public int getX() { return x; }
    public int getY() { return y; }
    
    // 修改操作返回新对象
    public ImmutablePoint move(int dx, int dy) {
        return new ImmutablePoint(x + dx, y + dy);
    }
}
```

**优点**：
- 天然线程安全，无需同步
- 可以自由共享和缓存
- 简化并发编程

### 2. 绝对线程安全（Absolute Thread Safety）

无论运行时环境如何，调用者都不需要额外的同步措施。

```java
// Java中几乎没有真正绝对线程安全的类
// 即使是Vector，也不是绝对线程安全的

Vector<Integer> vector = new Vector<>();
// 线程1
vector.add(1);

// 线程2：可能抛出ArrayIndexOutOfBoundsException
if (vector.size() > 0) {  // 假设size=1
    // 此时线程1删除了元素，size变为0
    vector.get(0);  // 抛出异常！
}

// 需要额外同步
synchronized (vector) {
    if (vector.size() > 0) {
        vector.get(0);
    }
}
```

### 3. 相对线程安全（Relative Thread Safety）

**最常见的线程安全级别**，对象的单次操作是线程安全的，但特定顺序的连续调用需要额外同步。

```java
// Vector、ConcurrentHashMap等属于这个级别

// 单次操作线程安全
ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
map.put("key", 1);  // 线程安全
Integer value = map.get("key");  // 线程安全

// 复合操作需要额外同步
// ❌ 不是线程安全的
if (!map.containsKey("key")) {
    map.put("key", 1);
}

// ✅ 使用原子方法
map.putIfAbsent("key", 1);
```

### 4. 线程兼容（Thread Compatible）

对象本身不是线程安全的，但可以通过外部同步来安全使用。

```java
// ArrayList、HashMap等属于这个级别
List<Integer> list = new ArrayList<>();

// ❌ 直接使用不安全
// 多个线程同时add会出问题

// ✅ 通过外部同步使用
synchronized (list) {
    list.add(1);
}

// ✅ 或使用包装类
List<Integer> syncList = Collections.synchronizedList(new ArrayList<>());
syncList.add(1);  // 内部自动同步
```

### 5. 线程对立（Thread Hostile）

无论是否采取同步措施，都无法在多线程环境中安全使用。

```java
// 例如：System.setIn()、System.setOut()
// 这些方法会影响全局状态，即使同步也无法保证安全

// 线程对立的代码示例（反例）
public class ThreadHostile {
    private static int id = 0;
    
    public static void setId(int newId) {
        // 直接修改静态变量，影响所有使用者
        id = newId;
        // 其他线程可能读到不一致的状态
    }
}
```

---

## 线程安全的实现方式

### 1. 互斥同步（悲观锁）

```java
// synchronized
public class SynchronizedExample {
    private int count = 0;
    
    public synchronized void increment() {
        count++;
    }
    
    // 或使用同步块
    public void decrement() {
        synchronized (this) {
            count--;
        }
    }
}

// ReentrantLock
public class LockExample {
    private int count = 0;
    private final Lock lock = new ReentrantLock();
    
    public void increment() {
        lock.lock();
        try {
            count++;
        } finally {
            lock.unlock();
        }
    }
}
```

### 2. 非阻塞同步（乐观锁）

```java
// CAS（Compare-And-Swap）
public class CasExample {
    private AtomicInteger count = new AtomicInteger(0);
    
    public void increment() {
        count.incrementAndGet();  // 使用CAS实现
    }
    
    // 手动使用CAS
    public void compareAndSet(int expect, int update) {
        count.compareAndSet(expect, update);
    }
}
```

### 3. 无同步方案

```java
// ThreadLocal
public class ThreadLocalExample {
    private static ThreadLocal<Integer> threadLocal = 
        ThreadLocal.withInitial(() -> 0);
    
    public void increment() {
        // 每个线程有自己的副本，无需同步
        threadLocal.set(threadLocal.get() + 1);
    }
    
    public int get() {
        return threadLocal.get();
    }
}

// 栈封闭（局部变量）
public class StackConfinement {
    public int calculate(int a, int b) {
        // 局部变量在栈上，线程独享
        int result = a + b;
        return result;
    }
}
```

---

## 实际场景分析

### 场景1：单例模式

```java
// ❌ 线程不安全的懒加载
public class UnsafeSingleton {
    private static UnsafeSingleton instance;
    
    public static UnsafeSingleton getInstance() {
        if (instance == null) {
            instance = new UnsafeSingleton();  // 可能创建多个实例
        }
        return instance;
    }
}

// ✅ 线程安全的DCL
public class SafeSingleton {
    private static volatile SafeSingleton instance;
    
    public static SafeSingleton getInstance() {
        if (instance == null) {
            synchronized (SafeSingleton.class) {
                if (instance == null) {
                    instance = new SafeSingleton();
                }
            }
        }
        return instance;
    }
}

// ✅ 静态内部类（推荐）
public class BestSingleton {
    private BestSingleton() {}
    
    private static class Holder {
        private static final BestSingleton INSTANCE = new BestSingleton();
    }
    
    public static BestSingleton getInstance() {
        return Holder.INSTANCE;  // 类加载时保证线程安全
    }
}
```

### 场景2：缓存实现

```java
// ❌ 线程不安全的缓存
public class UnsafeCache {
    private final Map<String, Object> cache = new HashMap<>();
    
    public Object get(String key) {
        if (!cache.containsKey(key)) {
            Object value = loadFromDB(key);
            cache.put(key, value);  // 多线程可能重复加载
        }
        return cache.get(key);
    }
}

// ✅ 线程安全的缓存
public class SafeCache {
    private final ConcurrentHashMap<String, Object> cache = 
        new ConcurrentHashMap<>();
    
    public Object get(String key) {
        return cache.computeIfAbsent(key, k -> loadFromDB(k));
    }
    
    private Object loadFromDB(String key) {
        // 从数据库加载数据
        return new Object();
    }
}
```

### 场景3：观察者模式

```java
// ❌ 线程不安全的观察者
public class UnsafeObservable {
    private final List<Observer> observers = new ArrayList<>();
    
    public void addObserver(Observer o) {
        observers.add(o);  // add时可能有其他线程在遍历
    }
    
    public void notifyObservers() {
        for (Observer o : observers) {  // 遍历时可能有其他线程在add
            o.update();  // 可能抛出ConcurrentModificationException
        }
    }
}

// ✅ 线程安全的观察者
public class SafeObservable {
    private final List<Observer> observers = 
        new CopyOnWriteArrayList<>();  // 写时复制
    
    public void addObserver(Observer o) {
        observers.add(o);  // 线程安全
    }
    
    public void notifyObservers() {
        for (Observer o : observers) {  // 读不加锁
            o.update();
        }
    }
}
```

---

## 如何判断线程安全？

### 判断标准

1. **是否有共享数据**：没有共享数据，自然线程安全
2. **共享数据是否可变**：不可变数据，自然线程安全
3. **访问是否同步**：有同步措施，可能线程安全
4. **操作是否原子**：原子操作，可能线程安全

### 检查清单

```java
// 问自己这些问题：
1. 是否有多个线程访问？           // 单线程不存在问题
2. 是否有共享的可变状态？         // 不可变对象天然安全
3. 是否有竞态条件？               // 如check-then-act
4. 是否正确使用了同步？           // synchronized/Lock
5. 是否有复合操作？               // 需要原子性保证
6. 是否有内存可见性问题？         // 需要volatile
7. 是否有死锁风险？               // 锁的顺序
```

---

## 面试总结

### 核心要点

1. **定义**：多线程访问时，无需额外同步，结果依然正确
2. **三要素**：原子性、可见性、有序性
3. **五级别**：不可变、绝对安全、相对安全、线程兼容、线程对立
4. **实现方式**：互斥同步、非阻塞同步、无同步方案

### 答题模板

**简明版**：
- 线程安全是指多线程访问时，无需额外同步即可保证正确性
- 需要保证原子性、可见性、有序性
- 常见实现：synchronized、volatile、Lock、原子类、不可变对象

**完整版**：
1. **定义**：多线程环境下，无需调用方协调，对象行为依然正确
2. **三大特性**：
   - 原子性：count++需要synchronized保证
   - 可见性：共享变量需要volatile保证
   - 有序性：防止指令重排序
3. **安全级别**：从不可变到线程对立，常见是相对线程安全
4. **实现方式**：
   - 互斥同步：synchronized、Lock
   - 非阻塞：CAS、原子类
   - 无同步：ThreadLocal、不可变对象
5. **实践建议**：优先使用不可变对象、JUC工具类、避免过度同步

### 经典面试题回答

**Q：如何保证线程安全？**

A：
1. **不可变对象**：如String、Integer（推荐）
2. **同步机制**：synchronized、Lock保证互斥
3. **原子类**：AtomicInteger等CAS操作
4. **并发容器**：ConcurrentHashMap、CopyOnWriteArrayList
5. **ThreadLocal**：线程本地存储
6. **volatile**：保证可见性和有序性

**Q：Vector是线程安全的吗？**

A：Vector是相对线程安全的，单次操作安全，但复合操作不安全。例如：

```java
if (vector.size() > 0) {
    vector.get(0);  // 可能抛异常
}
// 需要额外同步
synchronized (vector) {
    if (vector.size() > 0) {
        vector.get(0);
    }
}
```

**Q：如何检测代码是否线程安全？**

A：
1. **Code Review**：检查共享变量访问
2. **压力测试**：高并发场景测试
3. **工具检测**：FindBugs、ThreadSanitizer
4. **单元测试**：并发测试框架（如JCStress）

