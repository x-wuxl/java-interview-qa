---
title: "什么是CAS？存在什么问题？"
date: 2025-11-02
categories: [Java并发编程]
tags: [CAS, 原子操作, 无锁编程, ABA问题]
description: 深入讲解CAS（Compare-And-Swap）的原理、实现机制及其存在的ABA、自旋开销等问题。
nav_order: 202
parent: 并发编程
---
## 核心概念

**CAS（Compare-And-Swap，比较并交换）**是一种无锁的原子操作，用于实现多线程环境下的同步。

### 基本原理

CAS包含三个操作数：
- **V**：内存位置（变量的内存地址）
- **A**：预期原值（Expected）
- **B**：新值（New Value）

**执行逻辑**：
```
if (V == A) {
    V = B;  // 更新成功
    return true;
} else {
    return false;  // 更新失败
}
```

**关键特性**：整个"比较+交换"操作是原子性的，由CPU指令保证。

## 底层实现原理

### Java层面实现

```java
// Unsafe类提供的CAS操作
public final class Unsafe {
    /**
     * CAS操作
     * @param o 对象
     * @param offset 字段的内存偏移量
     * @param expected 期望值
     * @param x 新值
     */
    public native boolean compareAndSwapInt(
        Object o, long offset, int expected, int x);
    
    public native boolean compareAndSwapLong(
        Object o, long offset, long expected, long x);
    
    public native boolean compareAndSwapObject(
        Object o, long offset, Object expected, Object x);
}
```

### AtomicInteger使用CAS示例

```java
public class AtomicInteger {
    private static final Unsafe unsafe = Unsafe.getUnsafe();
    private static final long valueOffset;  // value字段的内存偏移量
    
    static {
        try {
            // 获取value字段的内存偏移地址
            valueOffset = unsafe.objectFieldOffset
                (AtomicInteger.class.getDeclaredField("value"));
        } catch (Exception ex) { throw new Error(ex); }
    }
    
    private volatile int value;  // 使用volatile保证可见性
    
    /**
     * 自增操作
     */
    public final int incrementAndGet() {
        return unsafe.getAndAddInt(this, valueOffset, 1) + 1;
    }
    
    /**
     * getAndAddInt的实现（JDK 8+）
     */
    public final int getAndAddInt(Object o, long offset, int delta) {
        int v;
        do {
            v = getIntVolatile(o, offset);  // 获取当前值
        } while (!compareAndSwapInt(o, offset, v, v + delta));  // CAS自旋
        return v;
    }
}
```

### CPU指令层面

不同架构的CPU指令：
- **X86/X64**：`CMPXCHG` 指令 + `LOCK` 前缀
- **ARM**：`LDREX` / `STREX` 指令
- **MIPS**：`LL` / `SC` 指令

```assembly
; X86汇编伪代码
LOCK CMPXCHG [地址], 新值
; LOCK前缀保证多核CPU下的原子性
```

## CAS存在的问题

### 1. ABA问题

#### 问题描述

```java
// 初始值：A
线程1：读取A，准备改为C
线程2：将A改为B
线程2：又将B改为A
线程1：CAS成功（但中间状态被忽略了）
```

#### 实际案例

```java
public class ABADemo {
    static AtomicInteger atomicInt = new AtomicInteger(100);
    
    public static void main(String[] args) throws InterruptedException {
        // 线程1
        Thread t1 = new Thread(() -> {
            int value = atomicInt.get();  // 读取100
            System.out.println("线程1读取值：" + value);
            try {
                Thread.sleep(1000);  // 模拟耗时操作
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            // CAS成功，但不知道中间被改过
            if (atomicInt.compareAndSet(value, 101)) {
                System.out.println("线程1 CAS成功");
            }
        });
        
        // 线程2
        Thread t2 = new Thread(() -> {
            atomicInt.compareAndSet(100, 200);  // A -> B
            System.out.println("线程2改为200");
            atomicInt.compareAndSet(200, 100);  // B -> A
            System.out.println("线程2又改回100");
        });
        
        t1.start();
        Thread.sleep(100);  // 确保t1先读取
        t2.start();
        
        t1.join();
        t2.join();
        
        System.out.println("最终值：" + atomicInt.get());
    }
}
```

**输出结果**：
```
线程1读取值：100
线程2改为200
线程2又改回100
线程1 CAS成功
最终值：101
```

#### 解决方案：AtomicStampedReference

```java
public class ABASolution {
    // 带版本号的原子引用
    static AtomicStampedReference<Integer> atomicRef = 
        new AtomicStampedReference<>(100, 0);  // 初始值100，版本号0
    
    public static void main(String[] args) throws InterruptedException {
        // 线程1
        Thread t1 = new Thread(() -> {
            int stamp = atomicRef.getStamp();  // 获取版本号
            int value = atomicRef.getReference();
            System.out.println("线程1读取：value=" + value + ", stamp=" + stamp);
            
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            
            // CAS：期望值100，版本号0，新值101，新版本号1
            if (atomicRef.compareAndSet(value, 101, stamp, stamp + 1)) {
                System.out.println("线程1 CAS成功");
            } else {
                System.out.println("线程1 CAS失败（检测到ABA）");
            }
        });
        
        // 线程2
        Thread t2 = new Thread(() -> {
            int stamp = atomicRef.getStamp();
            int value = atomicRef.getReference();
            
            atomicRef.compareAndSet(value, 200, stamp, stamp + 1);
            System.out.println("线程2改为200，版本号：" + atomicRef.getStamp());
            
            stamp = atomicRef.getStamp();
            value = atomicRef.getReference();
            atomicRef.compareAndSet(value, 100, stamp, stamp + 1);
            System.out.println("线程2改回100，版本号：" + atomicRef.getStamp());
        });
        
        t1.start();
        Thread.sleep(100);
        t2.start();
        
        t1.join();
        t2.join();
        
        System.out.println("最终：value=" + atomicRef.getReference() + 
                           ", stamp=" + atomicRef.getStamp());
    }
}
```

**输出结果**：
```
线程1读取：value=100, stamp=0
线程2改为200，版本号：1
线程2改回100，版本号：2
线程1 CAS失败（检测到ABA）
最终：value=100, stamp=2
```

### 2. 自旋开销（循环时间长）

#### 问题描述

高并发场景下，CAS失败率高，导致长时间自旋，浪费CPU资源。

```java
public class SpinOverheadDemo {
    static AtomicInteger counter = new AtomicInteger(0);
    
    public static void main(String[] args) throws InterruptedException {
        long start = System.currentTimeMillis();
        
        // 100个线程同时竞争
        Thread[] threads = new Thread[100];
        for (int i = 0; i < 100; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 10000; j++) {
                    counter.incrementAndGet();  // 大量CAS自旋
                }
            });
            threads[i].start();
        }
        
        for (Thread thread : threads) {
            thread.join();
        }
        
        long end = System.currentTimeMillis();
        System.out.println("耗时：" + (end - start) + "ms");
        System.out.println("最终值：" + counter.get());
    }
}
```

#### 解决方案：LongAdder

```java
public class LongAdderSolution {
    static LongAdder counter = new LongAdder();
    
    public static void main(String[] args) throws InterruptedException {
        long start = System.currentTimeMillis();
        
        Thread[] threads = new Thread[100];
        for (int i = 0; i < 100; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < 10000; j++) {
                    counter.increment();  // 分段CAS，减少竞争
                }
            });
            threads[i].start();
        }
        
        for (Thread thread : threads) {
            thread.join();
        }
        
        long end = System.currentTimeMillis();
        System.out.println("耗时：" + (end - start) + "ms");
        System.out.println("最终值：" + counter.sum());
    }
}
```

**性能对比**：
- AtomicInteger（100线程）：约1000ms
- LongAdder（100线程）：约200ms
- **提升5倍性能**

### 3. 只能保证单个变量的原子性

```java
public class MultiVariableProblem {
    AtomicInteger x = new AtomicInteger(0);
    AtomicInteger y = new AtomicInteger(0);
    
    // 问题：无法保证x和y的一致性
    public void update() {
        x.incrementAndGet();  // ✅ 单个操作原子
        y.incrementAndGet();  // ✅ 单个操作原子
        // ❌ 两个操作之间可能被打断，x和y不一致
    }
    
    // 解决方案1：使用锁
    private final Object lock = new Object();
    public void updateWithLock() {
        synchronized (lock) {
            x.incrementAndGet();
            y.incrementAndGet();
        }
    }
    
    // 解决方案2：使用AtomicReference封装
    static class Point {
        final int x, y;
        Point(int x, int y) { this.x = x; this.y = y; }
    }
    
    AtomicReference<Point> point = new AtomicReference<>(new Point(0, 0));
    
    public void updatePoint() {
        Point oldPoint, newPoint;
        do {
            oldPoint = point.get();
            newPoint = new Point(oldPoint.x + 1, oldPoint.y + 1);
        } while (!point.compareAndSet(oldPoint, newPoint));
    }
}
```

## 性能与线程安全考量

### 适用场景

✅ **适合**：
- 竞争不激烈的场景
- 单个变量的原子操作
- 对性能要求极高的场景

❌ **不适合**：
- 高并发、竞争激烈（考虑LongAdder）
- 需要保证多个变量一致性（考虑锁）
- 对ABA敏感的业务（使用版本号）

### 性能对比

| 并发度 | synchronized | AtomicInteger | LongAdder |
|-------|--------------|---------------|-----------|
| 低（1-10线程）| 100ms | 50ms | 60ms |
| 中（50线程）| 500ms | 400ms | 150ms |
| 高（100线程）| 2000ms | 1500ms | 300ms |

## 答题总结

### CAS是什么？

> CAS是一种无锁的原子操作，包含三个参数：内存位置V、预期值A、新值B。操作逻辑是：如果V的值等于A，则更新为B，否则不做任何操作。整个过程由CPU指令保证原子性。

### CAS的三大问题

1. **ABA问题**：值被改了又改回来，无法察觉中间状态。
   - **解决**：使用`AtomicStampedReference`增加版本号

2. **自旋开销**：高并发下失败率高，长时间自旋浪费CPU。
   - **解决**：使用`LongAdder`的分段CAS，或限制自旋次数后升级为锁

3. **单变量限制**：只能保证单个变量的原子性，无法保证多变量一致性。
   - **解决**：使用`AtomicReference`封装多个字段，或使用锁

### 面试答题模板

> "CAS是Compare-And-Swap，比较并交换，包含内存地址、预期值、新值三个参数。原理是先比较内存值是否等于预期值，相等则更新为新值，整个操作由CPU指令保证原子性。
>
> CAS主要有三个问题：
>
> 一是**ABA问题**，值从A变成B又变回A，CAS无法察觉。解决办法是使用AtomicStampedReference加版本号。
>
> 二是**自旋开销**，高并发下失败率高导致长时间自旋。可以用LongAdder的分段思想降低竞争。
>
> 三是**只能保证单变量原子性**，多个变量需要用AtomicReference封装或者用锁。"

