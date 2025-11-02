---
layout: post
title: "什么是Unsafe？"
date: 2025-11-02
categories: [Java并发编程]
tags: [Unsafe, 底层API, CAS, 内存操作]
description: 深入解析Java中的Unsafe类，了解其强大功能、使用方式及在并发编程中的核心作用。
---

## 核心概念

**Unsafe**是Java底层的"万能钥匙"，位于`sun.misc`包下，提供了直接操作内存、CAS原子操作、线程调度等底层能力，是Java并发包（JUC）的基石。

```java
package sun.misc;

public final class Unsafe {
    // 单例模式
    private static final Unsafe theUnsafe = new Unsafe();
    
    // 私有构造函数，防止外部实例化
    private Unsafe() {}
    
    // 只能通过getUnsafe获取实例（有权限检查）
    @CallerSensitive
    public static Unsafe getUnsafe() {
        Class<?> caller = Reflection.getCallerClass();
        if (!VM.isSystemDomainLoader(caller.getClassLoader())) {
            throw new SecurityException("Unsafe");
        }
        return theUnsafe;
    }
}
```

## 核心功能

### 1. CAS操作（原子操作）

```java
public final class Unsafe {
    /**
     * CAS操作：比较并交换int值
     * @param o 对象
     * @param offset 字段的内存偏移量
     * @param expected 期望值
     * @param x 新值
     * @return 是否成功
     */
    public native boolean compareAndSwapInt(
        Object o, long offset, int expected, int x);
    
    public native boolean compareAndSwapLong(
        Object o, long offset, long expected, long x);
    
    public native boolean compareAndSwapObject(
        Object o, long offset, Object expected, Object x);
}
```

**应用示例**：

```java
public class UnsafeCASExample {
    private volatile int value = 0;
    private static final Unsafe unsafe = getUnsafeInstance();
    private static final long valueOffset;
    
    static {
        try {
            valueOffset = unsafe.objectFieldOffset(
                UnsafeCASExample.class.getDeclaredField("value"));
        } catch (Exception e) {
            throw new Error(e);
        }
    }
    
    public boolean compareAndSet(int expect, int update) {
        return unsafe.compareAndSwapInt(this, valueOffset, expect, update);
    }
    
    public int incrementAndGet() {
        int current;
        do {
            current = value;
        } while (!unsafe.compareAndSwapInt(this, valueOffset, current, current + 1));
        return current + 1;
    }
}
```

### 2. 内存操作

#### 直接内存分配

```java
public class DirectMemoryExample {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    public static void main(String[] args) {
        // 分配1KB内存
        long address = unsafe.allocateMemory(1024);
        
        try {
            // 写入数据
            unsafe.putInt(address, 42);
            unsafe.putLong(address + 4, 1234567890L);
            unsafe.putByte(address + 12, (byte) 255);
            
            // 读取数据
            int intValue = unsafe.getInt(address);
            long longValue = unsafe.getLong(address + 4);
            byte byteValue = unsafe.getByte(address + 12);
            
            System.out.println("int: " + intValue);       // 42
            System.out.println("long: " + longValue);     // 1234567890
            System.out.println("byte: " + byteValue);     // -1 (255的有符号表示)
            
            // 设置内存（类似memset）
            unsafe.setMemory(address, 1024, (byte) 0);  // 全部置0
            
        } finally {
            // 释放内存（必须手动释放，否则内存泄漏）
            unsafe.freeMemory(address);
        }
    }
}
```

#### 对象字段访问

```java
public class FieldAccessExample {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    static class User {
        private String name;
        private int age;
        
        public User(String name, int age) {
            this.name = name;
            this.age = age;
        }
    }
    
    public static void main(String[] args) throws Exception {
        User user = new User("Alice", 25);
        
        // 获取字段偏移量
        long nameOffset = unsafe.objectFieldOffset(
            User.class.getDeclaredField("name"));
        long ageOffset = unsafe.objectFieldOffset(
            User.class.getDeclaredField("age"));
        
        // 直接读取字段（绕过访问控制）
        String name = (String) unsafe.getObject(user, nameOffset);
        int age = unsafe.getInt(user, ageOffset);
        System.out.println("name: " + name + ", age: " + age);
        
        // 直接修改字段（即使是private final）
        unsafe.putObject(user, nameOffset, "Bob");
        unsafe.putInt(user, ageOffset, 30);
        
        System.out.println("修改后：name=" + user.name + ", age=" + user.age);
    }
}
```

### 3. 对象操作

#### 绕过构造函数创建对象

```java
public class ObjectCreationExample {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    static class Person {
        private String name = "Default";
        private int age = 0;
        
        // 构造函数
        public Person() {
            System.out.println("构造函数被调用");
            this.name = "Constructed";
            this.age = 18;
        }
        
        @Override
        public String toString() {
            return "Person{name='" + name + "', age=" + age + "}";
        }
    }
    
    public static void main(String[] args) throws Exception {
        // 正常创建对象
        Person p1 = new Person();
        System.out.println("正常创建：" + p1);
        
        // 使用Unsafe创建对象（不调用构造函数）
        Person p2 = (Person) unsafe.allocateInstance(Person.class);
        System.out.println("Unsafe创建：" + p2);  // 字段保持默认值
    }
}
```

**输出**：
```
构造函数被调用
正常创建：Person{name='Constructed', age=18}
Unsafe创建：Person{name='Default', age=0}
```

**应用场景**：
- 序列化/反序列化（如Kryo、Gson）
- 单例模式的破坏与防御

### 4. 数组操作

```java
public class ArrayOperationExample {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    public static void main(String[] args) {
        int[] array = new int[10];
        
        // 获取数组元素的基础偏移量
        int baseOffset = unsafe.arrayBaseOffset(int[].class);
        
        // 获取数组元素的缩放因子（每个元素占用的字节数）
        int indexScale = unsafe.arrayIndexScale(int[].class);
        
        System.out.println("baseOffset: " + baseOffset);    // 通常是16
        System.out.println("indexScale: " + indexScale);    // int是4字节
        
        // 直接操作数组元素
        for (int i = 0; i < array.length; i++) {
            long offset = baseOffset + (long) i * indexScale;
            unsafe.putInt(array, offset, i * 10);
        }
        
        // 读取数组元素
        for (int i = 0; i < array.length; i++) {
            long offset = baseOffset + (long) i * indexScale;
            System.out.print(unsafe.getInt(array, offset) + " ");
        }
        // 输出：0 10 20 30 40 50 60 70 80 90
    }
}
```

### 5. 线程调度

```java
public class ThreadParkExample {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    public static void main(String[] args) throws InterruptedException {
        Thread t = new Thread(() -> {
            System.out.println("线程开始执行");
            
            // 阻塞当前线程（类似LockSupport.park()）
            unsafe.park(false, 0);  // 参数：是否绝对时间，纳秒数（0表示无限等待）
            
            System.out.println("线程被唤醒");
        });
        
        t.start();
        Thread.sleep(2000);  // 主线程等待2秒
        
        System.out.println("唤醒线程");
        unsafe.unpark(t);  // 唤醒线程
        
        t.join();
    }
}
```

**输出**：
```
线程开始执行
（等待2秒）
唤醒线程
线程被唤醒
```

### 6. 内存屏障

```java
public class MemoryBarrierExample {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    private int a = 0;
    private int b = 0;
    
    public void writer() {
        a = 1;
        unsafe.storeFence();  // 写屏障：确保a的写入完成后再执行后续写入
        b = 2;
    }
    
    public void reader() {
        int r1 = b;
        unsafe.loadFence();   // 读屏障：确保b的读取完成后再执行后续读取
        int r2 = a;
        
        // 保证：如果r1==2，则r2一定==1
    }
    
    public void fullBarrier() {
        unsafe.fullFence();   // 全屏障：禁止所有重排序
    }
}
```

## JUC中的Unsafe应用

### 1. AtomicInteger

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
    
    private volatile int value;
    
    public final boolean compareAndSet(int expect, int update) {
        return unsafe.compareAndSwapInt(this, valueOffset, expect, update);
    }
}
```

### 2. LockSupport

```java
public class LockSupport {
    private static final Unsafe unsafe = Unsafe.getUnsafe();
    
    public static void park() {
        unsafe.park(false, 0L);  // 阻塞当前线程
    }
    
    public static void unpark(Thread thread) {
        if (thread != null) {
            unsafe.unpark(thread);  // 唤醒线程
        }
    }
}
```

### 3. AQS（AbstractQueuedSynchronizer）

```java
public abstract class AbstractQueuedSynchronizer {
    private static final Unsafe unsafe = Unsafe.getUnsafe();
    private static final long stateOffset;
    private static final long headOffset;
    private static final long tailOffset;
    
    static {
        try {
            stateOffset = unsafe.objectFieldOffset(
                AbstractQueuedSynchronizer.class.getDeclaredField("state"));
            headOffset = unsafe.objectFieldOffset(
                AbstractQueuedSynchronizer.class.getDeclaredField("head"));
            tailOffset = unsafe.objectFieldOffset(
                AbstractQueuedSynchronizer.class.getDeclaredField("tail"));
        } catch (Exception ex) { throw new Error(ex); }
    }
    
    protected final boolean compareAndSetState(int expect, int update) {
        return unsafe.compareAndSwapInt(this, stateOffset, expect, update);
    }
}
```

## 如何获取Unsafe实例

### 方法1：反射（常用）

```java
public static Unsafe getUnsafeInstance() {
    try {
        Field field = Unsafe.class.getDeclaredField("theUnsafe");
        field.setAccessible(true);
        return (Unsafe) field.get(null);
    } catch (Exception e) {
        throw new RuntimeException("无法获取Unsafe实例", e);
    }
}
```

### 方法2：自定义ClassLoader

```java
public class UnsafeProvider {
    public static Unsafe getUnsafe() {
        try {
            return Unsafe.getUnsafe();  // 直接调用会抛出SecurityException
        } catch (SecurityException e) {
            try {
                // 使用自定义ClassLoader加载
                return AccessController.doPrivileged(
                    (PrivilegedExceptionAction<Unsafe>) () -> {
                        Field field = Unsafe.class.getDeclaredField("theUnsafe");
                        field.setAccessible(true);
                        return (Unsafe) field.get(null);
                    });
            } catch (Exception ex) {
                throw new RuntimeException("无法获取Unsafe", ex);
            }
        }
    }
}
```

## 危险性与注意事项

### 1. 内存泄漏

```java
// 错误示例
public class MemoryLeak {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    public void bad() {
        long address = unsafe.allocateMemory(1024 * 1024 * 1024);  // 1GB
        // 忘记调用freeMemory，导致内存泄漏！
    }
    
    // 正确示例
    public void good() {
        long address = unsafe.allocateMemory(1024);
        try {
            // 使用内存
        } finally {
            unsafe.freeMemory(address);  // 确保释放
        }
    }
}
```

### 2. JVM崩溃

```java
// 危险操作
public class CrashExample {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    public static void main(String[] args) {
        // 访问非法内存地址 → JVM崩溃
        unsafe.putInt(0, 42);  // ☠️ Segmentation fault
    }
}
```

### 3. 破坏不可变性

```java
public class ImmutableViolation {
    private static final Unsafe unsafe = getUnsafeInstance();
    
    public static void main(String[] args) throws Exception {
        String str = "Hello";
        System.out.println("原始值：" + str);
        
        // 获取String的value字段偏移量
        long offset = unsafe.objectFieldOffset(
            String.class.getDeclaredField("value"));
        
        // 修改String的内部char数组（破坏不可变性）
        char[] newValue = "World".toCharArray();
        unsafe.putObject(str, offset, newValue);
        
        System.out.println("修改后：" + str);  // 输出：World
    }
}
```

## Java 9+的替代方案

### VarHandle（推荐）

```java
public class VarHandleExample {
    private volatile int value = 0;
    private static final VarHandle VALUE;
    
    static {
        try {
            VALUE = MethodHandles.lookup()
                .findVarHandle(VarHandleExample.class, "value", int.class);
        } catch (Exception e) {
            throw new Error(e);
        }
    }
    
    public boolean compareAndSet(int expect, int update) {
        return VALUE.compareAndSet(this, expect, update);
    }
    
    public int getVolatile() {
        return (int) VALUE.getVolatile(this);
    }
    
    public void setVolatile(int newValue) {
        VALUE.setVolatile(this, newValue);
    }
}
```

**优势**：
- 官方支持，类型安全
- 性能与Unsafe相当
- 不依赖内部API

## 答题总结

### 核心要点

1. **定义**：Unsafe是Java底层API，提供直接内存操作、CAS、线程调度等能力

2. **六大功能**：
   - CAS原子操作（并发编程基石）
   - 内存操作（直接内存分配/释放）
   - 对象操作（绕过构造函数创建对象）
   - 数组操作（直接访问数组元素）
   - 线程调度（park/unpark）
   - 内存屏障（控制指令重排序）

3. **应用**：
   - JUC并发包（AtomicInteger、LockSupport、AQS）
   - NIO（DirectByteBuffer）
   - 序列化框架（Kryo、Gson）

4. **风险**：
   - 内存泄漏、JVM崩溃
   - 破坏Java安全模型
   - Java 9+推荐使用VarHandle替代

### 面试答题模板

> "Unsafe是Java提供的底层API，位于sun.misc包下，提供了直接操作内存、CAS原子操作、线程调度等能力，是整个JUC并发包的基石。
>
> 它的核心功能有六个方面：一是CAS操作，提供compareAndSwapInt等方法，这是AtomicInteger等原子类的底层实现；二是内存操作，可以直接分配和释放堆外内存；三是对象操作，可以绕过构造函数创建对象；四是数组操作，直接访问数组元素；五是线程调度，提供park和unpark方法，LockSupport就是基于此实现的；六是内存屏障，控制指令重排序。
>
> JUC中的AtomicInteger、AQS、LockSupport等核心类都依赖Unsafe实现。比如AtomicInteger的compareAndSet方法就是调用Unsafe的compareAndSwapInt实现的。
>
> 但Unsafe非常危险，使用不当可能导致内存泄漏甚至JVM崩溃，而且它属于内部API，Java 9之后推荐使用VarHandle作为替代。"

