---
title: "介绍下CAS"
date: 2025-11-02
categories: [Java并发编程]
tags: [CAS, 无锁编程, 原子操作, 并发]
description: 全面介绍CAS（Compare-And-Swap）机制，包括概念、原理、应用场景及优缺点。
nav_order: 203
parent: 并发编程
---
## 什么是CAS

**CAS（Compare-And-Swap，比较并交换）**是一种无锁的原子操作，是实现并发算法的重要技术，也是Java并发包（JUC）的核心基础。

### 基本定义

CAS操作包含三个操作数：
- **V（Variable）**：要更新的变量（内存地址）
- **E（Expected）**：预期值（旧值）
- **N（New）**：新值

**执行逻辑**：
```java
boolean CAS(V, E, N) {
    if (V == E) {
        V = N;
        return true;  // 更新成功
    } else {
        return false; // 更新失败
    }
}
```

**关键特性**：整个"比较+交换"过程是**原子性**的，由CPU硬件指令保证。

## 工作原理

### 概念示意

```java
// 场景：多线程同时对count进行自增操作
int count = 0;

// 线程A执行CAS(count, 0, 1)：
// 1. 读取count的值：0
// 2. 比较count是否等于预期值0：相等
// 3. 将count更新为1：成功
// 返回true

// 线程B同时执行CAS(count, 0, 1)：
// 1. 读取count的值：已经是1了
// 2. 比较count是否等于预期值0：不相等
// 3. 不做任何修改
// 返回false
```

### Java层面实现

```java
// Unsafe类提供的CAS操作
public final class Unsafe {
    /**
     * CAS操作：原子地比较并交换int值
     */
    public native boolean compareAndSwapInt(
        Object o,        // 目标对象
        long offset,     // 字段在对象中的内存偏移量
        int expected,    // 期望值
        int x            // 新值
    );
    
    public native boolean compareAndSwapLong(
        Object o, long offset, long expected, long x);
    
    public native boolean compareAndSwapObject(
        Object o, long offset, Object expected, Object x);
}
```

### 硬件层面实现

#### x86架构的CMPXCHG指令

```assembly
; 汇编伪代码
LOCK CMPXCHG [memory], register

; 执行过程：
; 1. LOCK前缀锁定缓存行或总线
; 2. 比较EAX寄存器与[memory]的值
; 3. 相等则将register写入[memory]，并设置ZF标志位
; 4. 不相等则将[memory]的值读入EAX
```

**LOCK前缀的作用**：
- 早期CPU：锁总线（Bus Lock），阻止其他CPU访问内存
- 现代CPU：锁缓存行（Cache Line Lock），利用MESI协议保证原子性

## CAS的典型应用

### 1. AtomicInteger（基础应用）

```java
public class AtomicInteger {
    private static final Unsafe unsafe = Unsafe.getUnsafe();
    private static final long valueOffset;
    
    static {
        try {
            valueOffset = unsafe.objectFieldOffset(
                AtomicInteger.class.getDeclaredField("value"));
        } catch (Exception ex) { throw new Error(ex); }
    }
    
    private volatile int value;  // volatile保证可见性
    
    /**
     * 自增操作（CAS + 自旋）
     */
    public final int incrementAndGet() {
        return unsafe.getAndAddInt(this, valueOffset, 1) + 1;
    }
    
    /**
     * getAndAddInt的实现
     */
    public final int getAndAddInt(Object o, long offset, int delta) {
        int v;
        do {
            v = getIntVolatile(o, offset);  // 读取当前值
        } while (!compareAndSwapInt(o, offset, v, v + delta));  // CAS自旋
        return v;
    }
    
    /**
     * CAS操作
     */
    public final boolean compareAndSet(int expect, int update) {
        return unsafe.compareAndSwapInt(this, valueOffset, expect, update);
    }
}
```

### 2. 非阻塞栈（Treiber Stack）

```java
public class ConcurrentStack<E> {
    private static class Node<E> {
        final E item;
        Node<E> next;
        
        Node(E item) {
            this.item = item;
        }
    }
    
    private final AtomicReference<Node<E>> top = new AtomicReference<>();
    
    /**
     * 入栈操作（无锁）
     */
    public void push(E item) {
        Node<E> newHead = new Node<>(item);
        Node<E> oldHead;
        do {
            oldHead = top.get();
            newHead.next = oldHead;
        } while (!top.compareAndSet(oldHead, newHead));  // CAS自旋
    }
    
    /**
     * 出栈操作（无锁）
     */
    public E pop() {
        Node<E> oldHead, newHead;
        do {
            oldHead = top.get();
            if (oldHead == null) {
                return null;  // 栈为空
            }
            newHead = oldHead.next;
        } while (!top.compareAndSet(oldHead, newHead));  // CAS自旋
        return oldHead.item;
    }
}
```

### 3. 非阻塞队列（Michael-Scott Queue）

```java
public class ConcurrentQueue<E> {
    private static class Node<E> {
        final E item;
        final AtomicReference<Node<E>> next;
        
        Node(E item) {
            this.item = item;
            this.next = new AtomicReference<>(null);
        }
    }
    
    private final AtomicReference<Node<E>> head;
    private final AtomicReference<Node<E>> tail;
    
    public ConcurrentQueue() {
        Node<E> dummy = new Node<>(null);
        head = new AtomicReference<>(dummy);
        tail = new AtomicReference<>(dummy);
    }
    
    /**
     * 入队操作
     */
    public void enqueue(E item) {
        Node<E> newNode = new Node<>(item);
        while (true) {
            Node<E> curTail = tail.get();
            Node<E> tailNext = curTail.next.get();
            
            if (curTail == tail.get()) {  // 一致性检查
                if (tailNext == null) {
                    // tail的next为空，尝试插入新节点
                    if (curTail.next.compareAndSet(null, newNode)) {
                        // CAS成功，移动tail指针
                        tail.compareAndSet(curTail, newNode);
                        return;
                    }
                } else {
                    // tail落后，帮助推进
                    tail.compareAndSet(curTail, tailNext);
                }
            }
        }
    }
    
    /**
     * 出队操作
     */
    public E dequeue() {
        while (true) {
            Node<E> curHead = head.get();
            Node<E> curTail = tail.get();
            Node<E> headNext = curHead.next.get();
            
            if (curHead == head.get()) {  // 一致性检查
                if (curHead == curTail) {
                    if (headNext == null) {
                        return null;  // 队列为空
                    }
                    // tail落后，帮助推进
                    tail.compareAndSet(curTail, headNext);
                } else {
                    E item = headNext.item;
                    if (head.compareAndSet(curHead, headNext)) {
                        return item;
                    }
                }
            }
        }
    }
}
```

### 4. 乐观锁（版本号机制）

```java
public class OptimisticLockExample {
    private AtomicStampedReference<Integer> atomicRef = 
        new AtomicStampedReference<>(0, 0);
    
    /**
     * 更新数据（乐观锁）
     */
    public boolean updateData(int newValue) {
        int[] stampHolder = new int[1];
        Integer currentValue;
        
        do {
            currentValue = atomicRef.get(stampHolder);
            int currentStamp = stampHolder[0];
            int newStamp = currentStamp + 1;
            
            // 执行业务逻辑...
            
            // CAS更新，失败则重试
            if (atomicRef.compareAndSet(currentValue, newValue, 
                                        currentStamp, newStamp)) {
                return true;
            }
        } while (true);
    }
}
```

## CAS的优势

### 1. 性能优越

```java
// 性能对比测试
public class CASPerformance {
    private int syncCounter = 0;
    private AtomicInteger casCounter = new AtomicInteger(0);
    
    // synchronized方案
    public synchronized void incrementSync() {
        syncCounter++;
    }
    
    // CAS方案
    public void incrementCAS() {
        casCounter.incrementAndGet();
    }
    
    public static void main(String[] args) throws InterruptedException {
        CASPerformance test = new CASPerformance();
        int threadCount = 10;
        int iterations = 100000;
        
        // 测试synchronized
        long start1 = System.currentTimeMillis();
        Thread[] threads1 = new Thread[threadCount];
        for (int i = 0; i < threadCount; i++) {
            threads1[i] = new Thread(() -> {
                for (int j = 0; j < iterations; j++) {
                    test.incrementSync();
                }
            });
            threads1[i].start();
        }
        for (Thread t : threads1) t.join();
        long end1 = System.currentTimeMillis();
        System.out.println("synchronized: " + (end1 - start1) + "ms");
        
        // 测试CAS
        long start2 = System.currentTimeMillis();
        Thread[] threads2 = new Thread[threadCount];
        for (int i = 0; i < threadCount; i++) {
            threads2[i] = new Thread(() -> {
                for (int j = 0; j < iterations; j++) {
                    test.incrementCAS();
                }
            });
            threads2[i].start();
        }
        for (Thread t : threads2) t.join();
        long end2 = System.currentTimeMillis();
        System.out.println("CAS: " + (end2 - start2) + "ms");
    }
}
```

**典型结果**：
```
synchronized: 450ms
CAS: 180ms
性能提升：2.5倍
```

### 2. 无阻塞特性

- **synchronized/Lock**：线程获取不到锁会阻塞，涉及上下文切换
- **CAS**：失败后立即重试或返回，不会阻塞线程

### 3. 避免死锁

- 无锁机制，天然避免死锁问题
- 适合实现无锁数据结构

## CAS的劣势

### 1. ABA问题

```java
// 问题场景
初始值：A
线程1读取：A，准备改为C
线程2修改：A → B
线程2再改：B → A
线程1 CAS：成功（但中间状态被忽略）

// 解决方案：AtomicStampedReference
AtomicStampedReference<Integer> ref = 
    new AtomicStampedReference<>(100, 0);  // 值 + 版本号

// 每次更新版本号递增
ref.compareAndSet(100, 200, 0, 1);
```

### 2. 自旋开销

```java
// 高并发下CAS失败率高，导致长时间自旋
public int incrementAndGet() {
    int current;
    do {
        current = value;  // 读取
        // 高并发下，可能循环很多次才能成功
    } while (!compareAndSet(current, current + 1));
    return current + 1;
}

// 解决方案：LongAdder（分段CAS）
LongAdder adder = new LongAdder();
adder.increment();  // 分散竞争，降低自旋次数
```

### 3. 单变量限制

```java
// 问题：无法保证多个变量的原子性
AtomicInteger x = new AtomicInteger(0);
AtomicInteger y = new AtomicInteger(0);

// 无法保证x和y同时更新
x.incrementAndGet();
y.incrementAndGet();  // 中间可能被其他线程打断

// 解决方案：AtomicReference封装
class Point {
    final int x, y;
    Point(int x, int y) { this.x = x; this.y = y; }
}
AtomicReference<Point> point = new AtomicReference<>(new Point(0, 0));

// 原子更新整个对象
Point oldPoint, newPoint;
do {
    oldPoint = point.get();
    newPoint = new Point(oldPoint.x + 1, oldPoint.y + 1);
} while (!point.compareAndSet(oldPoint, newPoint));
```

## CAS vs synchronized

| 维度 | CAS | synchronized |
|-----|-----|--------------|
| **锁机制** | 无锁（乐观锁） | 互斥锁（悲观锁） |
| **阻塞** | 不阻塞 | 可能阻塞 |
| **上下文切换** | 无 | 有 |
| **性能** | 低并发下更优 | 高并发下可能更优（JDK优化） |
| **适用场景** | 简单原子操作 | 复杂临界区 |
| **原子性范围** | 单个变量 | 代码块 |
| **失败处理** | 自旋重试 | 阻塞等待 |

## 使用建议

### 适用场景

✅ **推荐使用CAS**：
- 竞争不激烈的场景
- 简单的原子操作（计数、状态标志）
- 对性能要求极高的场景
- 无锁数据结构

❌ **不推荐使用CAS**：
- 高并发、长时间自旋
- 需要保护多个变量的一致性
- 包含复杂业务逻辑的临界区

### 选择决策

```
需要原子操作？
  ├─ 单个变量
  │  ├─ 低并发 → AtomicInteger
  │  └─ 高并发 → LongAdder
  └─ 多个变量
     └─ synchronized 或 Lock
```

## 答题总结

### 核心要点

1. **定义**：CAS是一种无锁的原子操作，包含三个参数：内存地址V、期望值E、新值N

2. **原理**：先比较V是否等于E，相等则更新为N，整个过程由CPU指令（如CMPXCHG）保证原子性

3. **优势**：
   - 性能优于synchronized（避免锁竞争和上下文切换）
   - 无阻塞、无死锁
   - 适合实现无锁数据结构

4. **劣势**：
   - ABA问题（用版本号解决）
   - 高并发下自旋开销大（用LongAdder解决）
   - 只能保护单个变量

5. **应用**：JUC中的AtomicInteger、AQS、ConcurrentLinkedQueue等都基于CAS实现

### 面试答题模板

> "CAS全称Compare-And-Swap，比较并交换，是一种无锁的原子操作。它包含三个参数：内存位置、期望值、新值。执行逻辑是先比较内存值是否等于期望值，如果相等就更新为新值，否则不做任何操作，整个过程由CPU指令保证原子性。
>
> CAS的优势是性能好，因为不需要加锁，避免了线程阻塞和上下文切换，在低到中等并发场景下性能远超synchronized。而且天然避免死锁，适合实现无锁数据结构。
>
> 但CAS也有三个问题：一是ABA问题，可以用AtomicStampedReference加版本号解决；二是高并发下自旋开销大，可以用LongAdder的分段思想降低竞争；三是只能保证单个变量的原子性，多个变量需要用AtomicReference封装或者加锁。
>
> Java并发包中的AtomicInteger、AQS、ConcurrentLinkedQueue等核心类都是基于CAS实现的，可以说CAS是整个JUC的基石。"

