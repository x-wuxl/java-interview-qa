---
title: "有了CAS为啥还需要volatile"
date: 2025-11-02
categories: [Java并发编程]
tags: [CAS, volatile, 内存可见性, 无锁编程]
description: 深入分析CAS和volatile的关系，理解为何CAS操作仍然需要volatile保证可见性。
nav_order: 207
parent: 并发编程
---
## 核心结论

**CAS只保证单次操作的原子性，不保证变量的可见性和有序性**，因此需要`volatile`配合使用来保证内存可见性和禁止指令重排序。

## CAS与volatile的区别

| 特性 | CAS | volatile | CAS + volatile |
|-----|-----|----------|----------------|
| **原子性** | ✅ 单次操作 | ❌ 不保证 | ✅ 单次操作 |
| **可见性** | ❌ 不保证 | ✅ 保证 | ✅ 保证 |
| **有序性** | ❌ 不保证 | ✅ 禁止重排序 | ✅ 保证 |
| **适用场景** | 原子更新 | 状态标志 | 无锁数据结构 |

## 为什么CAS需要volatile

### 1. CAS不保证可见性

#### 问题示例

```java
public class CASWithoutVolatile {
    // 错误：没有volatile
    private int value = 0;
    private static final Unsafe unsafe = getUnsafe();
    private static final long valueOffset;
    
    static {
        try {
            valueOffset = unsafe.objectFieldOffset(
                CASWithoutVolatile.class.getDeclaredField("value"));
        } catch (Exception e) {
            throw new Error(e);
        }
    }
    
    public boolean compareAndSet(int expect, int update) {
        return unsafe.compareAndSwapInt(this, valueOffset, expect, update);
    }
    
    public int get() {
        return value;  // 可能读到旧值！
    }
}
```

**问题**：
```java
// 线程A
obj.compareAndSet(0, 1);  // CAS成功

// 线程B（在不同CPU核心）
int v = obj.get();  // 可能读到旧值0，而不是1
```

**原因**：
- CAS虽然保证了写入主内存的原子性
- 但不保证其他线程能立即看到修改（没有内存屏障）
- 线程B可能从自己的CPU缓存读取旧值

#### 正确示例

```java
public class CASWithVolatile {
    // 正确：使用volatile
    private volatile int value = 0;
    private static final Unsafe unsafe = getUnsafe();
    private static final long valueOffset;
    
    static {
        try {
            valueOffset = unsafe.objectFieldOffset(
                CASWithVolatile.class.getDeclaredField("value"));
        } catch (Exception e) {
            throw new Error(e);
        }
    }
    
    public boolean compareAndSet(int expect, int update) {
        return unsafe.compareAndSwapInt(this, valueOffset, expect, update);
    }
    
    public int get() {
        return value;  // volatile读，保证可见性
    }
}
```

**volatile的作用**：
- 每次读取都从主内存获取最新值
- 每次写入都立即刷新到主内存
- 配合CAS的原子性，实现完整的线程安全

### 2. CAS不保证有序性

#### 指令重排序问题

```java
public class ReorderingProblem {
    private int data = 0;
    private int flag = 0;  // 没有volatile
    private static final Unsafe unsafe = getUnsafe();
    private static final long flagOffset;
    
    static {
        // 初始化offset...
    }
    
    // 线程A：发布数据
    public void publish() {
        data = 42;                                    // 1. 写data
        unsafe.compareAndSwapInt(this, flagOffset, 0, 1);  // 2. CAS设置flag
        
        // 问题：指令可能重排序为 2 -> 1
        // 导致flag=1时，data还未被写入
    }
    
    // 线程B：读取数据
    public void consume() {
        if (flag == 1) {                              // 3. 读flag
            System.out.println(data);                 // 4. 读data
            // 可能输出0，而不是42
        }
    }
}
```

**问题根源**：
- CAS操作本身有内存屏障（LOCK指令）
- 但不保证CAS前后的普通读写不被重排序
- `data = 42` 可能在CAS之后执行

#### 使用volatile解决

```java
public class ReorderingSolution {
    private int data = 0;
    private volatile int flag = 0;  // 使用volatile
    private static final Unsafe unsafe = getUnsafe();
    private static final long flagOffset;
    
    static {
        // 初始化offset...
    }
    
    public void publish() {
        data = 42;                                    // 1. 写data
        unsafe.compareAndSwapInt(this, flagOffset, 0, 1);  // 2. CAS设置flag
        
        // volatile的happens-before规则：
        // data的写入 happens-before flag的CAS写入
    }
    
    public void consume() {
        if (flag == 1) {                              // 3. volatile读flag
            System.out.println(data);                 // 4. 读data，保证能看到42
            // happens-before规则保证能看到正确的data
        }
    }
}
```

## AtomicInteger源码分析

### 源码实现

```java
public class AtomicInteger extends Number implements java.io.Serializable {
    private static final Unsafe unsafe = Unsafe.getUnsafe();
    private static final long valueOffset;
    
    static {
        try {
            valueOffset = unsafe.objectFieldOffset
                (AtomicInteger.class.getDeclaredField("value"));
        } catch (Exception ex) { throw new Error(ex); }
    }
    
    // 关键：value字段使用volatile
    private volatile int value;
    
    /**
     * 获取当前值
     */
    public final int get() {
        return value;  // volatile读，保证可见性
    }
    
    /**
     * 设置新值
     */
    public final void set(int newValue) {
        value = newValue;  // volatile写，保证可见性
    }
    
    /**
     * CAS操作
     */
    public final boolean compareAndSet(int expect, int update) {
        return unsafe.compareAndSwapInt(this, valueOffset, expect, update);
    }
    
    /**
     * 自增操作（CAS + 自旋）
     */
    public final int getAndIncrement() {
        return unsafe.getAndAddInt(this, valueOffset, 1);
    }
}

// Unsafe.getAndAddInt的实现
public final int getAndAddInt(Object o, long offset, int delta) {
    int v;
    do {
        v = getIntVolatile(o, offset);  // volatile读，保证每次都读到最新值
    } while (!compareAndSwapInt(o, offset, v, v + delta));
    return v;
}
```

### 为何必须使用volatile

```java
// 如果不用volatile，会出现问题：
public final int getAndIncrement() {
    int v;
    do {
        v = getIntVolatile(o, offset);  // 读取
        // 假设这里v=5
        
        // 其他线程已经把value改成了10
        // 但当前线程的CPU缓存可能还是5
        
    } while (!compareAndSwapInt(o, offset, v, v + 1));
    // CAS会失败，因为内存中的值已经不是5了
    // 但如果没有volatile，getIntVolatile可能一直读到旧值5
    // 导致无限循环
    return v;
}
```

**volatile的三个作用**：
1. **CAS前**：保证读到最新的expect值
2. **CAS后**：保证新值对其他线程立即可见
3. **整体**：禁止指令重排序，保证happens-before

## 实战案例

### 案例1：非阻塞栈（Treiber Stack）

```java
public class TreiberStack<E> {
    // 必须用volatile
    private volatile Node<E> top = null;
    
    private static class Node<E> {
        final E item;
        Node<E> next;
        
        Node(E item, Node<E> next) {
            this.item = item;
            this.next = next;
        }
    }
    
    private static final Unsafe unsafe = getUnsafe();
    private static final long topOffset;
    
    static {
        try {
            topOffset = unsafe.objectFieldOffset(
                TreiberStack.class.getDeclaredField("top"));
        } catch (Exception e) {
            throw new Error(e);
        }
    }
    
    /**
     * 入栈
     */
    public void push(E item) {
        Node<E> newHead = new Node<>(item, null);
        Node<E> oldHead;
        do {
            oldHead = top;  // volatile读，保证看到最新的栈顶
            newHead.next = oldHead;
        } while (!unsafe.compareAndSwapObject(this, topOffset, oldHead, newHead));
        // CAS成功后，volatile保证新栈顶立即对其他线程可见
    }
    
    /**
     * 出栈
     */
    public E pop() {
        Node<E> oldHead, newHead;
        do {
            oldHead = top;  // volatile读
            if (oldHead == null) {
                return null;
            }
            newHead = oldHead.next;
        } while (!unsafe.compareAndSwapObject(this, topOffset, oldHead, newHead));
        return oldHead.item;
    }
}
```

**如果去掉volatile会怎样？**

```java
private Node<E> top = null;  // 去掉volatile

// 问题1：可见性
线程A：push(1)，top指向Node1
线程B：读取top，可能仍然是null（未及时看到线程A的修改）

// 问题2：指令重排序
public void push(E item) {
    Node<E> newHead = new Node<>(item, null);  // 1
    newHead.next = top;                         // 2
    top = newHead;                              // 3
    
    // 可能重排为：3 -> 2 -> 1
    // 其他线程看到top=newHead时，newHead可能还未完全初始化
}
```

### 案例2：并发计数器

```java
public class ConcurrentCounter {
    // 必须使用volatile
    private volatile int count = 0;
    private static final Unsafe unsafe = getUnsafe();
    private static final long countOffset;
    
    static {
        // 初始化offset...
    }
    
    /**
     * 自增
     */
    public void increment() {
        int oldValue, newValue;
        do {
            oldValue = count;  // volatile读，保证每次都读到最新值
            newValue = oldValue + 1;
        } while (!unsafe.compareAndSwapInt(this, countOffset, oldValue, newValue));
        // CAS后，volatile保证新值立即可见
    }
    
    /**
     * 获取当前值
     */
    public int get() {
        return count;  // volatile读，保证可见性
    }
}
```

## 性能对比测试

```java
public class PerformanceTest {
    // 方案1：CAS + volatile（正确）
    private volatile int volatileCounter = 0;
    
    // 方案2：只用synchronized（对比）
    private int syncCounter = 0;
    
    @Benchmark
    public void testVolatileCAS() {
        // AtomicInteger内部实现
        // volatile读 + CAS + volatile写
        // 约20-50ns
    }
    
    @Benchmark
    public void testSynchronized() {
        synchronized (this) {
            syncCounter++;
        }
        // 约100-200ns（包含锁获取/释放）
    }
}
```

**结论**：
- CAS + volatile：20-50ns
- synchronized：100-200ns
- **性能提升2-4倍**

## 内存语义对比

### CAS的内存语义

```
CAS操作（LOCK CMPXCHG）：
  - 带有完整的内存屏障（StoreLoad）
  - 保证CAS本身的原子性
  - 但不保证CAS前后的普通读写顺序
```

### volatile的内存语义

```
volatile写之前：
  - StoreStore屏障：禁止之前的写操作与volatile写重排序

volatile写之后：
  - StoreLoad屏障：禁止volatile写与之后的读操作重排序

volatile读之后：
  - LoadLoad + LoadStore屏障：禁止volatile读与后续操作重排序
```

### 组合效果

```java
private int data = 0;
private volatile int flag = 0;

// 写线程
data = 42;                    // 1. 普通写
unsafe.compareAndSwapInt(...); // 2. CAS写flag（volatile）

// 保证：1 happens-before 2（StoreStore屏障）

// 读线程
if (flag == 1) {              // 3. volatile读flag
    int value = data;         // 4. 普通读
}

// 保证：3 happens-before 4（LoadLoad屏障）
// 整体：1 happens-before 2 happens-before 3 happens-before 4
```

## 答题总结

### 三个关键点

1. **CAS只保证单次操作的原子性**，不保证可见性和有序性：
   - CAS成功后，不保证其他线程能立即看到修改
   - CAS前后的普通操作可能被重排序

2. **volatile提供可见性和有序性保证**：
   - volatile读：保证读到最新值（CAS前需要）
   - volatile写：保证修改立即可见（CAS后需要）
   - 内存屏障：禁止关键操作的重排序

3. **JDK中所有原子类都是CAS + volatile**：
   - `AtomicInteger.value`是volatile
   - `AtomicReference.value`是volatile
   - 保证了完整的线程安全性

### 面试答题模板

> "CAS只保证单次比较并交换操作的原子性，不保证内存可见性和有序性，因此需要volatile配合。
>
> 具体来说有三个原因：
>
> **第一，可见性**：CAS虽然保证了写入的原子性，但不保证其他线程能立即看到修改。volatile保证每次读取都从主内存获取最新值，每次写入都立即刷新到主内存。
>
> **第二，读取最新值**：CAS操作前需要读取expect值，如果没有volatile，可能读到CPU缓存中的旧值，导致CAS逻辑错误或无限循环。
>
> **第三，禁止重排序**：volatile的内存屏障保证CAS前后的操作不会被重排序，这在发布对象等场景下非常重要。
>
> 所以JDK中的AtomicInteger、AtomicReference等所有原子类，内部的value字段都声明为volatile，就是为了配合CAS实现完整的线程安全。"

