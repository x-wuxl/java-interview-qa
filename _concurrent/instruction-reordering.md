---
title: "指令重排序"
date: 2025-11-02
categories: [Java并发编程]
tags: [指令重排序, JMM, 内存屏障, happens-before]
description: 全面解析Java中的指令重排序现象，包括产生原因、类型、影响及如何通过内存屏障和volatile禁止重排序。
nav_order: 189
parent: 并发编程
---
## 什么是指令重排序

**指令重排序（Instruction Reordering）**是指编译器和处理器为了优化程序性能，在不改变单线程程序执行结果的前提下，对指令的执行顺序进行调整。

### 核心特点

- **单线程语义保证**：重排序不会改变单线程的执行结果
- **多线程问题**：重排序可能导致多线程程序出现意外行为
- **透明性**：重排序对程序员是透明的（单线程下）

## 为什么会发生重排序

### 1. 性能优化的需求

现代CPU为了提高执行效率，采用了多种优化技术：

```
指令执行流水线：
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ 取指令  │  译码   │  执行   │  访存   │  写回   │
└─────────┴─────────┴─────────┴─────────┴─────────┘

优化目标：
1. 充分利用流水线（避免流水线停顿）
2. 减少缓存未命中
3. 提高指令并行度
```

### 2. 重排序示例

```java
public class ReorderingExample {
    int a = 0;
    boolean flag = false;
    
    // 线程1
    public void writer() {
        a = 1;          // 1. 写a
        flag = true;    // 2. 写flag
    }
    
    // 线程2
    public void reader() {
        if (flag) {     // 3. 读flag
            int i = a;  // 4. 读a
            // 可能读到a=0！
        }
    }
}
```

**可能的执行顺序**（重排序后）：
```
原始顺序：1 → 2 → 3 → 4
重排序后：2 → 1 → 3 → 4
结果：flag=true时，a可能还是0
```

## 重排序的三个层次

### 1. 编译器重排序

**编译器优化**：在编译阶段调整指令顺序

```java
// 原始代码
int a = 1;
int b = 2;
int c = a + b;

// 编译器可能重排为
int b = 2;  // 先计算b
int a = 1;  // 再计算a
int c = a + b;
```

**Java字节码层面**：

```java
public void method() {
    int x = 1;
    int y = 2;
    int z = x + y;
}

// 字节码可能重排序
0: iconst_2      // 先加载2
1: istore_2      // 存储y
2: iconst_1      // 再加载1
3: istore_1      // 存储x
4: iload_1       
5: iload_2
6: iadd
7: istore_3      // 存储z
```

### 2. 处理器重排序

#### 指令级并行（ILP）

```java
// CPU可能并行执行的指令
public void execute() {
    int a = 1;  // 指令1
    int b = 2;  // 指令2（不依赖指令1，可并行）
    int c = 3;  // 指令3（不依赖指令1、2，可并行）
    int d = a + b;  // 指令4（依赖1、2，必须等待）
}
```

#### 乱序执行（Out-of-Order Execution）

```
指令流水线：
时刻T1: [指令1取指] [指令2译码] [指令3执行] [指令4访存] [指令5写回]

如果指令2需要等待内存数据，CPU会先执行指令3、4
```

### 3. 内存系统重排序

#### 写缓冲区（Store Buffer）

```
CPU核心：
  ↓ 写入
Store Buffer（写缓冲区）
  ↓ 延迟刷新
L1 Cache
  ↓
L2 Cache
  ↓
主内存

问题：写入Store Buffer后，CPU认为写入完成，但实际未刷新到主内存
```

```java
public class StoreBufferReordering {
    int a = 0;
    int b = 0;
    
    // CPU1
    public void cpu1() {
        a = 1;  // 写入Store Buffer，未刷新到内存
        int r1 = b;  // 读取b（可能还是0）
    }
    
    // CPU2
    public void cpu2() {
        b = 1;  // 写入Store Buffer，未刷新到内存
        int r2 = a;  // 读取a（可能还是0）
    }
    
    // 可能结果：r1=0, r2=0（两个CPU看到的写入顺序不同）
}
```

## 重排序的类型

### 1. LoadLoad重排序

```java
int a = x;  // Load1
int b = y;  // Load2

// 可能重排为
int b = y;  // Load2先执行
int a = x;  // Load1后执行
```

### 2. StoreStore重排序

```java
x = 1;  // Store1
y = 2;  // Store2

// 可能重排为
y = 2;  // Store2先执行
x = 1;  // Store1后执行
```

### 3. LoadStore重排序

```java
int a = x;  // Load
y = 1;      // Store

// 可能重排为
y = 1;      // Store先执行
int a = x;  // Load后执行
```

### 4. StoreLoad重排序

```java
x = 1;      // Store
int a = y;  // Load

// 可能重排为
int a = y;  // Load先执行
x = 1;      // Store后执行

// 这是开销最大的重排序，需要完整的内存屏障
```

## 重排序带来的问题

### 问题1：双重检查锁的重排序

```java
public class Singleton {
    private static Singleton instance;  // 没有volatile
    
    public static Singleton getInstance() {
        if (instance == null) {  // 第一次检查
            synchronized (Singleton.class) {
                if (instance == null) {  // 第二次检查
                    instance = new Singleton();  // 问题在这里！
                }
            }
        }
        return instance;
    }
}
```

**问题分析**：

```java
instance = new Singleton();

// 这行代码实际包含3个步骤：
1. memory = allocate();   // 分配内存空间
2. ctorInstance(memory);  // 初始化对象
3. instance = memory;     // 设置instance指向内存地址

// 可能被重排序为：
1. memory = allocate();   // 分配内存
3. instance = memory;     // 指向内存（对象还未初始化）
2. ctorInstance(memory);  // 初始化对象

// 线程A执行到步骤3时，线程B进入getInstance()
// 线程B发现instance != null，直接返回instance
// 但此时对象还未初始化完成！→ 使用半初始化对象 → 出错
```

**解决方案**：

```java
public class Singleton {
    private static volatile Singleton instance;  // 使用volatile
    
    public static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();  // volatile禁止重排序
                }
            }
        }
        return instance;
    }
}
```

### 问题2：无锁发布对象

```java
public class UnsafePublication {
    private Object resource;
    private boolean initialized = false;
    
    // 线程1：初始化
    public void init() {
        resource = new Object();  // 1. 创建对象
        initialized = true;        // 2. 设置标志
        
        // 可能重排序为：
        // 2 → 1，导致initialized=true时，resource还是null
    }
    
    // 线程2：使用
    public void use() {
        if (initialized) {
            resource.doSomething();  // NullPointerException!
        }
    }
}
```

**解决方案**：

```java
public class SafePublication {
    private Object resource;
    private volatile boolean initialized = false;  // volatile
    
    public void init() {
        resource = new Object();
        initialized = true;  // volatile写，禁止之前的操作重排序到之后
    }
    
    public void use() {
        if (initialized) {  // volatile读，禁止之后的操作重排序到之前
            resource.doSomething();  // 保证能看到完全初始化的resource
        }
    }
}
```

## 禁止重排序的机制

### 1. 内存屏障（Memory Barrier）

内存屏障是CPU提供的指令，用于禁止特定类型的重排序。

| 屏障类型 | 指令 | 说明 |
|---------|-----|------|
| **LoadLoad** | Load1; LoadLoad; Load2 | 禁止Load1与Load2重排序 |
| **StoreStore** | Store1; StoreStore; Store2 | 禁止Store1与Store2重排序 |
| **LoadStore** | Load1; LoadStore; Store2 | 禁止Load1与Store2重排序 |
| **StoreLoad** | Store1; StoreLoad; Load2 | 禁止Store1与Load2重排序（最强） |

### 2. volatile的内存屏障

```java
class VolatileExample {
    int a = 0;
    volatile boolean flag = false;
    
    // 写线程
    public void writer() {
        a = 1;                  // 普通写
        // ↓ StoreStore屏障
        flag = true;            // volatile写
        // ↓ StoreLoad屏障
    }
    
    // 读线程
    public void reader() {
        // ↓ LoadLoad屏障
        if (flag) {             // volatile读
            // ↓ LoadStore屏障
            int i = a;          // 普通读
        }
    }
}
```

**JMM的插入策略**：

```
在volatile写之前：
  - 插入StoreStore屏障：禁止之前的普通写与volatile写重排序

在volatile写之后：
  - 插入StoreLoad屏障：禁止volatile写与之后的读写重排序

在volatile读之后：
  - 插入LoadLoad屏障：禁止volatile读与之后的读重排序
  - 插入LoadStore屏障：禁止volatile读与之后的写重排序
```

### 3. happens-before规则

JMM通过happens-before规则定义操作之间的偏序关系：

```java
// 规则1：程序顺序规则
a = 1;
b = 2;
// a = 1 happens-before b = 2（单线程内）

// 规则2：volatile变量规则
volatile boolean flag;
// flag的写 happens-before flag的读

// 规则3：传递性
a = 1;
flag = true;  // volatile写
if (flag) {   // volatile读
    int i = a;
}
// a = 1 happens-before flag写
// flag写 happens-before flag读
// flag读 happens-before a的读
// 传递：a = 1 happens-before a的读

// 规则4：锁规则
synchronized (lock) {
    a = 1;
}  // 解锁 happens-before 下一次加锁

// 规则5：线程启动规则
Thread t = new Thread(() -> {
    int a = x;  // 能看到主线程在start前的所有操作
});
t.start();  // start() happens-before 线程内任何操作

// 规则6：线程终止规则
t.join();   // join返回 happens-before 线程内的所有操作

// 规则7：线程中断规则
t.interrupt();  // interrupt() happens-before 检测到中断
```

### 4. final字段的重排序规则

```java
public class FinalFieldExample {
    final int x;
    int y;
    static FinalFieldExample obj;
    
    public FinalFieldExample() {
        x = 1;  // final字段的写
        y = 2;  // 普通字段的写
    }
    
    // 线程1
    public static void writer() {
        obj = new FinalFieldExample();
    }
    
    // 线程2
    public static void reader() {
        FinalFieldExample o = obj;
        if (o != null) {
            int a = o.x;  // 保证能看到x=1
            int b = o.y;  // 不保证能看到y=2
        }
    }
}
```

**final的重排序规则**：

1. **写final字段**：禁止"final字段写"与"构造函数返回"重排序
   ```java
   x = 1;  // final写
   // ↓ StoreStore屏障
   return this;  // 构造函数返回
   ```

2. **读final字段**：禁止"读对象引用"与"读final字段"重排序
   ```java
   obj = new FinalFieldExample();  // 读引用
   // ↓ LoadLoad屏障
   int a = obj.x;  // 读final字段
   ```

## 实战案例

### 案例1：无锁单例模式（Holder模式）

```java
public class Singleton {
    private Singleton() {}
    
    // 静态内部类
    private static class Holder {
        // final保证完全初始化
        static final Singleton INSTANCE = new Singleton();
    }
    
    public static Singleton getInstance() {
        return Holder.INSTANCE;  // 类加载机制保证线程安全
    }
}
```

**原理**：
- 类加载时，JVM保证初始化的线程安全性
- `final`保证`INSTANCE`完全初始化后才对其他线程可见

### 案例2：无锁发布对象

```java
public class SafePublication {
    private final Object resource;
    
    public SafePublication() {
        this.resource = new Object();  // final字段
    }
    
    // 不需要volatile或synchronized
    public Object getResource() {
        return resource;  // final保证可见性
    }
}
```

### 案例3：Disruptor的序列号屏障

```java
public class Sequence {
    private volatile long value = -1;  // volatile保证可见性和有序性
    
    public void set(long value) {
        this.value = value;
    }
    
    public long get() {
        return value;
    }
    
    // Disruptor使用volatile + CAS实现高性能队列
}
```

## 性能影响

### 内存屏障的开销

```java
// 性能测试
public class BarrierOverhead {
    int normalVar = 0;
    volatile int volatileVar = 0;
    
    @Benchmark
    public void testNormal() {
        normalVar++;  // 约1ns
    }
    
    @Benchmark
    public void testVolatile() {
        volatileVar++;  // 约10-20ns（有内存屏障开销）
    }
}
```

**开销排序**：
```
StoreLoad（最大） > StoreStore ≈ LoadStore ≈ LoadLoad
```

## 答题总结

### 核心要点

1. **定义**：指令重排序是编译器和处理器为优化性能，在不改变单线程结果的前提下调整指令执行顺序

2. **三个层次**：
   - 编译器重排序（编译时）
   - 处理器重排序（运行时，指令级并行）
   - 内存系统重排序（缓存、写缓冲区）

3. **四种类型**：LoadLoad、StoreStore、LoadStore、StoreLoad

4. **禁止重排序**：
   - volatile（内存屏障）
   - synchronized/Lock（锁规则）
   - final（初始化安全）
   - happens-before规则

5. **典型问题**：双重检查锁的半初始化对象

### 面试答题模板

> "指令重排序是编译器和处理器为了提高程序性能，在保证单线程语义不变的前提下，对指令的执行顺序进行调整。
>
> 重排序有三个层次：一是编译器重排序，在编译阶段调整指令顺序；二是处理器重排序，CPU通过乱序执行和流水线优化提高并行度；三是内存系统重排序，由于写缓冲区和缓存导致的内存访问顺序变化。
>
> 重排序在单线程下没问题，但多线程下可能导致意外行为。典型例子是双重检查锁的单例模式，对象创建包括分配内存、初始化对象、赋值引用三步，可能被重排序为分配内存、赋值引用、初始化对象，导致其他线程拿到未完全初始化的对象。
>
> 解决方案是使用volatile关键字。volatile通过插入内存屏障，禁止特定类型的重排序。volatile写之前插入StoreStore屏障，写之后插入StoreLoad屏障；volatile读之后插入LoadLoad和LoadStore屏障。这样保证了volatile变量前后的操作不会被重排序。
>
> 此外，synchronized、final字段、happens-before规则也都能禁止重排序，保证多线程的正确性。"

