---
layout: post
title: "CAS操作类"
date: 2025-11-02
categories: [Java并发编程]
tags: [CAS, Atomic, 原子类, JUC]
description: 全面介绍Java中基于CAS实现的原子操作类，包括基本类型、引用类型、数组类型和字段更新器。
---

## JUC原子类概览

Java在`java.util.concurrent.atomic`包下提供了丰富的原子操作类，所有这些类都基于**CAS（Compare-And-Swap）**机制实现。

### 四大类型

```
java.util.concurrent.atomic
├── 基本类型原子类
│   ├── AtomicInteger      - 整型原子类
│   ├── AtomicLong         - 长整型原子类
│   └── AtomicBoolean      - 布尔型原子类
│
├── 引用类型原子类
│   ├── AtomicReference<V>          - 对象引用原子类
│   ├── AtomicStampedReference<V>   - 带版本号的引用（解决ABA）
│   └── AtomicMarkableReference<V>  - 带标记位的引用
│
├── 数组类型原子类
│   ├── AtomicIntegerArray  - 整型数组原子类
│   ├── AtomicLongArray     - 长整型数组原子类
│   └── AtomicReferenceArray<E> - 引用类型数组原子类
│
├── 字段更新器
│   ├── AtomicIntegerFieldUpdater<T>   - 整型字段更新器
│   ├── AtomicLongFieldUpdater<T>      - 长整型字段更新器
│   └── AtomicReferenceFieldUpdater<T,V> - 引用字段更新器
│
└── 高性能累加器（JDK 8+）
    ├── LongAdder      - 长整型累加器
    ├── LongAccumulator - 长整型累加器（自定义函数）
    ├── DoubleAdder    - 双精度累加器
    └── DoubleAccumulator - 双精度累加器（自定义函数）
```

## 一、基本类型原子类

### 1. AtomicInteger

```java
public class AtomicIntegerExample {
    private AtomicInteger count = new AtomicInteger(0);
    
    /**
     * 主要API演示
     */
    public void demonstrateAPI() {
        // 1. 基本操作
        int current = count.get();                    // 获取当前值
        count.set(10);                                // 设置新值
        count.lazySet(10);                            // 延迟设置（性能优化）
        
        // 2. 自增/自减
        int result1 = count.incrementAndGet();        // 先加1再返回：++i
        int result2 = count.getAndIncrement();        // 先返回再加1：i++
        int result3 = count.decrementAndGet();        // 先减1再返回：--i
        int result4 = count.getAndDecrement();        // 先返回再减1：i--
        
        // 3. 加减操作
        int result5 = count.addAndGet(5);             // 加5后返回新值
        int result6 = count.getAndAdd(5);             // 返回旧值后加5
        
        // 4. CAS操作
        boolean success = count.compareAndSet(10, 20); // 期望10，更新为20
        
        // 5. JDK 8新增：函数式API
        int result7 = count.updateAndGet(x -> x * 2); // 更新并返回新值
        int result8 = count.getAndUpdate(x -> x * 2); // 返回旧值并更新
        int result9 = count.accumulateAndGet(10, (x, y) -> x + y); // 累加
        int result10 = count.getAndAccumulate(10, (x, y) -> x + y); // 累加
    }
    
    /**
     * 实战：线程安全计数器
     */
    public static void main(String[] args) throws InterruptedException {
        AtomicInteger counter = new AtomicInteger(0);
        
        // 10个线程并发自增
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 1000; j++) {
                    counter.incrementAndGet();
                }
            });
            threads[i].start();
        }
        
        for (Thread t : threads) {
            t.join();
        }
        
        System.out.println("最终值：" + counter.get());  // 输出：10000
    }
}
```

### 2. AtomicLong

```java
public class AtomicLongExample {
    private AtomicLong sequenceId = new AtomicLong(0);
    
    /**
     * ID生成器
     */
    public long nextId() {
        return sequenceId.incrementAndGet();
    }
    
    /**
     * 批量生成ID（性能优化）
     */
    public long[] nextIds(int count) {
        long[] ids = new long[count];
        long start = sequenceId.getAndAdd(count);  // 一次性获取count个ID
        for (int i = 0; i < count; i++) {
            ids[i] = start + i + 1;
        }
        return ids;
    }
}
```

### 3. AtomicBoolean

```java
public class AtomicBooleanExample {
    private AtomicBoolean initialized = new AtomicBoolean(false);
    
    /**
     * 单次初始化（保证只执行一次）
     */
    public void initialize() {
        if (initialized.compareAndSet(false, true)) {
            // 初始化逻辑
            System.out.println("执行初始化...");
            // 只有第一个线程会执行到这里
        } else {
            System.out.println("已经初始化过了");
        }
    }
    
    /**
     * 简单锁实现
     */
    public class SimpleLock {
        private AtomicBoolean locked = new AtomicBoolean(false);
        
        public boolean tryLock() {
            return locked.compareAndSet(false, true);
        }
        
        public void unlock() {
            locked.set(false);
        }
        
        public void doWork() {
            if (tryLock()) {
                try {
                    // 临界区代码
                    System.out.println(Thread.currentThread().getName() + " 获取锁成功");
                } finally {
                    unlock();
                }
            } else {
                System.out.println(Thread.currentThread().getName() + " 获取锁失败");
            }
        }
    }
}
```

## 二、引用类型原子类

### 1. AtomicReference

```java
public class AtomicReferenceExample {
    
    /**
     * 基本用法
     */
    static class User {
        String name;
        int age;
        
        User(String name, int age) {
            this.name = name;
            this.age = age;
        }
        
        @Override
        public String toString() {
            return "User{name='" + name + "', age=" + age + "}";
        }
    }
    
    public static void main(String[] args) {
        AtomicReference<User> userRef = new AtomicReference<>();
        
        User user1 = new User("Alice", 25);
        User user2 = new User("Bob", 30);
        
        userRef.set(user1);
        System.out.println("初始值：" + userRef.get());
        
        // CAS更新
        boolean success = userRef.compareAndSet(user1, user2);
        System.out.println("CAS成功：" + success);
        System.out.println("当前值：" + userRef.get());
    }
    
    /**
     * 实战：无锁栈
     */
    static class ConcurrentStack<E> {
        private static class Node<E> {
            final E item;
            Node<E> next;
            Node(E item) { this.item = item; }
        }
        
        private final AtomicReference<Node<E>> top = new AtomicReference<>();
        
        public void push(E item) {
            Node<E> newHead = new Node<>(item);
            Node<E> oldHead;
            do {
                oldHead = top.get();
                newHead.next = oldHead;
            } while (!top.compareAndSet(oldHead, newHead));
        }
        
        public E pop() {
            Node<E> oldHead, newHead;
            do {
                oldHead = top.get();
                if (oldHead == null) return null;
                newHead = oldHead.next;
            } while (!top.compareAndSet(oldHead, newHead));
            return oldHead.item;
        }
    }
}
```

### 2. AtomicStampedReference（解决ABA问题）

```java
public class AtomicStampedReferenceExample {
    
    /**
     * 演示ABA问题
     */
    public static void demonstrateABA() throws InterruptedException {
        AtomicReference<Integer> ref = new AtomicReference<>(100);
        
        // 线程1
        Thread t1 = new Thread(() -> {
            int value = ref.get();
            System.out.println("线程1读取：" + value);
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            // CAS成功，但不知道中间被改过
            if (ref.compareAndSet(value, 101)) {
                System.out.println("线程1 CAS成功");
            }
        });
        
        // 线程2：制造ABA
        Thread t2 = new Thread(() -> {
            ref.compareAndSet(100, 200);  // A -> B
            System.out.println("线程2改为200");
            ref.compareAndSet(200, 100);  // B -> A
            System.out.println("线程2改回100");
        });
        
        t1.start();
        Thread.sleep(100);
        t2.start();
        
        t1.join();
        t2.join();
    }
    
    /**
     * 使用版本号解决ABA
     */
    public static void solveABA() throws InterruptedException {
        // 初始值100，版本号0
        AtomicStampedReference<Integer> stampedRef = 
            new AtomicStampedReference<>(100, 0);
        
        // 线程1
        Thread t1 = new Thread(() -> {
            int[] stampHolder = new int[1];
            int value = stampedRef.get(stampHolder);
            int stamp = stampHolder[0];
            System.out.println("线程1读取：value=" + value + ", stamp=" + stamp);
            
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            
            // CAS：期望值100，版本号0，新值101，新版本号1
            if (stampedRef.compareAndSet(value, 101, stamp, stamp + 1)) {
                System.out.println("线程1 CAS成功");
            } else {
                System.out.println("线程1 CAS失败（检测到ABA）");
            }
        });
        
        // 线程2：制造ABA
        Thread t2 = new Thread(() -> {
            int[] stampHolder = new int[1];
            int value = stampedRef.get(stampHolder);
            int stamp = stampHolder[0];
            
            stampedRef.compareAndSet(value, 200, stamp, stamp + 1);
            System.out.println("线程2改为200，版本号：" + stampedRef.getStamp());
            
            value = stampedRef.getReference();
            stamp = stampedRef.getStamp();
            stampedRef.compareAndSet(value, 100, stamp, stamp + 1);
            System.out.println("线程2改回100，版本号：" + stampedRef.getStamp());
        });
        
        t1.start();
        Thread.sleep(100);
        t2.start();
        
        t1.join();
        t2.join();
    }
}
```

### 3. AtomicMarkableReference（带标记位）

```java
public class AtomicMarkableReferenceExample {
    
    /**
     * 用于标记对象状态（如：是否被删除）
     */
    static class Node {
        int value;
        Node(int value) { this.value = value; }
        
        @Override
        public String toString() {
            return "Node{" + value + "}";
        }
    }
    
    public static void main(String[] args) {
        Node node = new Node(100);
        
        // 初始值node，标记为false（未删除）
        AtomicMarkableReference<Node> markableRef = 
            new AtomicMarkableReference<>(node, false);
        
        // 检查标记
        boolean[] markHolder = new boolean[1];
        Node current = markableRef.get(markHolder);
        System.out.println("当前值：" + current + ", 已删除：" + markHolder[0]);
        
        // 标记为已删除
        markableRef.attemptMark(node, true);
        current = markableRef.get(markHolder);
        System.out.println("标记后：" + current + ", 已删除：" + markHolder[0]);
        
        // CAS：期望node且未删除，更新为null且已删除
        Node newNode = new Node(200);
        boolean success = markableRef.compareAndSet(node, newNode, true, false);
        System.out.println("CAS成功：" + success);
    }
}
```

## 三、数组类型原子类

### 1. AtomicIntegerArray

```java
public class AtomicIntegerArrayExample {
    private AtomicIntegerArray array = new AtomicIntegerArray(10);
    
    /**
     * 主要API
     */
    public void demonstrateAPI() {
        // 基本操作
        array.set(0, 100);                              // 设置索引0的值为100
        int value = array.get(0);                       // 获取索引0的值
        
        // 自增/自减
        int result1 = array.incrementAndGet(0);         // ++array[0]
        int result2 = array.getAndIncrement(0);         // array[0]++
        
        // 加减操作
        int result3 = array.addAndGet(0, 10);           // array[0] += 10
        int result4 = array.getAndAdd(0, 10);           // array[0] += 10
        
        // CAS操作
        boolean success = array.compareAndSet(0, 100, 200);
    }
    
    /**
     * 实战：并发统计每个桶的计数
     */
    public static void main(String[] args) throws InterruptedException {
        int buckets = 10;
        AtomicIntegerArray counters = new AtomicIntegerArray(buckets);
        
        // 100个线程并发更新
        Thread[] threads = new Thread[100];
        for (int i = 0; i < 100; i++) {
            final int threadId = i;
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 1000; j++) {
                    int bucket = threadId % buckets;  // 选择桶
                    counters.incrementAndGet(bucket);  // 原子自增
                }
            });
            threads[i].start();
        }
        
        for (Thread t : threads) {
            t.join();
        }
        
        // 输出统计结果
        for (int i = 0; i < buckets; i++) {
            System.out.println("桶" + i + "：" + counters.get(i));
        }
        // 每个桶应该是10000（10个线程 × 1000次）
    }
}
```

### 2. AtomicReferenceArray

```java
public class AtomicReferenceArrayExample {
    
    static class Task {
        String name;
        boolean completed;
        
        Task(String name) {
            this.name = name;
            this.completed = false;
        }
        
        @Override
        public String toString() {
            return "Task{" + name + ", completed=" + completed + "}";
        }
    }
    
    /**
     * 任务队列
     */
    public static void main(String[] args) {
        int size = 5;
        AtomicReferenceArray<Task> tasks = new AtomicReferenceArray<>(size);
        
        // 初始化任务
        for (int i = 0; i < size; i++) {
            tasks.set(i, new Task("Task-" + i));
        }
        
        // 并发标记任务完成
        Thread[] threads = new Thread[size];
        for (int i = 0; i < size; i++) {
            final int index = i;
            threads[i] = new Thread(() -> {
                Task oldTask = tasks.get(index);
                Task newTask = new Task(oldTask.name);
                newTask.completed = true;
                
                // CAS更新
                if (tasks.compareAndSet(index, oldTask, newTask)) {
                    System.out.println(Thread.currentThread().getName() + 
                                       " 完成了 " + newTask.name);
                }
            });
            threads[i].start();
        }
        
        for (Thread t : threads) {
            try {
                t.join();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        
        // 输出最终状态
        for (int i = 0; i < size; i++) {
            System.out.println(tasks.get(i));
        }
    }
}
```

## 四、字段更新器

### 1. AtomicIntegerFieldUpdater

```java
public class AtomicIntegerFieldUpdaterExample {
    
    /**
     * 需要更新的类
     */
    static class Counter {
        // 必须是volatile
        volatile int count = 0;
        volatile int visitors = 0;
    }
    
    public static void main(String[] args) throws InterruptedException {
        Counter counter = new Counter();
        
        // 创建字段更新器
        AtomicIntegerFieldUpdater<Counter> countUpdater = 
            AtomicIntegerFieldUpdater.newUpdater(Counter.class, "count");
        
        AtomicIntegerFieldUpdater<Counter> visitorsUpdater = 
            AtomicIntegerFieldUpdater.newUpdater(Counter.class, "visitors");
        
        // 10个线程并发更新
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 1000; j++) {
                    countUpdater.incrementAndGet(counter);
                    visitorsUpdater.addAndGet(counter, 2);
                }
            });
            threads[i].start();
        }
        
        for (Thread t : threads) {
            t.join();
        }
        
        System.out.println("count: " + counter.count);       // 10000
        System.out.println("visitors: " + counter.visitors); // 20000
    }
    
    /**
     * 优势：节省内存
     * 
     * 如果有10000个Counter对象：
     * - 使用AtomicInteger：每个对象额外16字节 × 10000 = 160KB
     * - 使用FieldUpdater：共享1个更新器对象 ≈ 几十字节
     */
}
```

### 2. AtomicReferenceFieldUpdater

```java
public class AtomicReferenceFieldUpdaterExample {
    
    static class Node {
        volatile Node next;  // 必须是volatile
        String value;
        
        Node(String value) {
            this.value = value;
        }
    }
    
    // 创建字段更新器
    private static final AtomicReferenceFieldUpdater<Node, Node> NEXT_UPDATER = 
        AtomicReferenceFieldUpdater.newUpdater(Node.class, Node.class, "next");
    
    /**
     * 无锁链表插入
     */
    public static void insert(Node head, Node newNode) {
        Node oldNext;
        do {
            oldNext = head.next;
            newNode.next = oldNext;
        } while (!NEXT_UPDATER.compareAndSet(head, oldNext, newNode));
    }
    
    public static void main(String[] args) {
        Node head = new Node("head");
        
        // 并发插入
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            final int index = i;
            threads[i] = new Thread(() -> {
                Node node = new Node("Node-" + index);
                insert(head, node);
            });
            threads[i].start();
        }
        
        for (Thread t : threads) {
            try {
                t.join();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        
        // 输出链表
        Node current = head;
        while (current != null) {
            System.out.println(current.value);
            current = current.next;
        }
    }
}
```

## 五、高性能累加器（JDK 8+）

### 1. LongAdder

```java
public class LongAdderExample {
    private LongAdder counter = new LongAdder();
    
    /**
     * 性能对比：LongAdder vs AtomicLong
     */
    public static void performanceComparison() throws InterruptedException {
        int threadCount = 100;
        int iterations = 100000;
        
        // 测试AtomicLong
        AtomicLong atomicCounter = new AtomicLong(0);
        long start1 = System.currentTimeMillis();
        
        Thread[] threads1 = new Thread[threadCount];
        for (int i = 0; i < threadCount; i++) {
            threads1[i] = new Thread(() -> {
                for (int j = 0; j < iterations; j++) {
                    atomicCounter.incrementAndGet();
                }
            });
            threads1[i].start();
        }
        for (Thread t : threads1) t.join();
        
        long end1 = System.currentTimeMillis();
        System.out.println("AtomicLong: " + (end1 - start1) + "ms, 结果：" + atomicCounter.get());
        
        // 测试LongAdder
        LongAdder adder = new LongAdder();
        long start2 = System.currentTimeMillis();
        
        Thread[] threads2 = new Thread[threadCount];
        for (int i = 0; i < threadCount; i++) {
            threads2[i] = new Thread(() -> {
                for (int j = 0; j < iterations; j++) {
                    adder.increment();
                }
            });
            threads2[i].start();
        }
        for (Thread t : threads2) t.join();
        
        long end2 = System.currentTimeMillis();
        System.out.println("LongAdder: " + (end2 - start2) + "ms, 结果：" + adder.sum());
        
        // 典型结果：
        // AtomicLong: 1500ms
        // LongAdder: 300ms（性能提升5倍）
    }
}
```

### 2. LongAccumulator

```java
public class LongAccumulatorExample {
    
    /**
     * 自定义累加函数
     */
    public static void main(String[] args) throws InterruptedException {
        // 求最大值（累加函数：Math::max，初始值：0）
        LongAccumulator maxAccumulator = new LongAccumulator(Math::max, 0);
        
        // 求和（累加函数：(x, y) -> x + y，初始值：0）
        LongAccumulator sumAccumulator = new LongAccumulator((x, y) -> x + y, 0);
        
        // 10个线程并发更新
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            final int threadId = i;
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 100; j++) {
                    int value = threadId * 100 + j;
                    maxAccumulator.accumulate(value);
                    sumAccumulator.accumulate(value);
                }
            });
            threads[i].start();
        }
        
        for (Thread t : threads) {
            t.join();
        }
        
        System.out.println("最大值：" + maxAccumulator.get());  // 999
        System.out.println("总和：" + sumAccumulator.get());    // 499500
    }
}
```

## 性能对比总结

| 原子类 | 并发度 | 性能 | 使用场景 |
|-------|-------|------|---------|
| AtomicInteger | 低-中 | ★★★☆ | 通用计数器 |
| AtomicLong | 低-中 | ★★★☆ | ID生成器 |
| LongAdder | 高 | ★★★★★ | 高并发统计 |
| FieldUpdater | 低-中 | ★★★☆ | 节省内存 |

## 答题总结

### 核心要点

1. **四大类型**：基本类型（AtomicInteger/Long/Boolean）、引用类型（AtomicReference/Stamped/Markable）、数组类型（AtomicIntegerArray等）、字段更新器

2. **解决ABA**：AtomicStampedReference（版本号）、AtomicMarkableReference（标记位）

3. **高性能**：LongAdder/LongAccumulator（分段锁思想，高并发下性能远超AtomicLong）

4. **节省内存**：FieldUpdater（多个对象共享一个更新器）

### 面试答题模板

> "Java提供了丰富的CAS原子操作类，主要分为四大类型：
>
> **第一类是基本类型原子类**，包括AtomicInteger、AtomicLong、AtomicBoolean，提供incrementAndGet、compareAndSet等方法，适合计数器、ID生成器等场景。
>
> **第二类是引用类型原子类**，AtomicReference用于原子更新对象引用，AtomicStampedReference通过版本号解决ABA问题，AtomicMarkableReference通过布尔标记位标识对象状态。
>
> **第三类是数组类型原子类**，如AtomicIntegerArray，可以原子更新数组中的元素，适合分桶统计等场景。
>
> **第四类是字段更新器**，如AtomicIntegerFieldUpdater，不需要额外对象，直接更新现有对象的volatile字段，节省内存。
>
> 此外，JDK 8还提供了LongAdder和LongAccumulator，采用分段锁思想，高并发下性能是AtomicLong的5倍以上，适合高并发统计场景。"

