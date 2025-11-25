---
title: "synchronized锁的是什么？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [synchronized, 锁对象, Monitor]
description: "详解synchronized关键字锁定的对象类型，包括实例对象、Class对象和this引用"
nav_order: 211
parent: 并发编程
---
# synchronized锁的是什么？

## 核心概念

`synchronized` 本质上**锁的是对象**，准确地说是锁定对象的 **Monitor（监视器）**。不同的使用方式锁定不同的对象，决定了同步的范围和粒度。

## 三种锁定目标

### 1. 锁定实例对象（this）

**实例方法**：
```java
public synchronized void instanceMethod() {
    // 锁的是当前实例对象 this
}
```

等价于：
```java
public void instanceMethod() {
    synchronized(this) {
        // 同步代码块
    }
}
```

- **锁对象**：当前实例对象
- **作用范围**：同一实例的所有 synchronized 实例方法
- **线程安全**：不同实例对象之间不互斥

### 2. 锁定任意对象

**同步代码块**：
```java
private final Object lock = new Object();

public void method() {
    synchronized(lock) {
        // 锁的是 lock 对象
    }
}
```

- **锁对象**：指定的对象引用
- **作用范围**：所有以该对象为锁的代码块
- **优势**：更细粒度的锁控制，减少锁竞争

### 3. 锁定 Class 对象

**静态方法**：
```java
public static synchronized void staticMethod() {
    // 锁的是 MyClass.class 对象
}
```

等价于：
```java
public static void staticMethod() {
    synchronized(MyClass.class) {
        // 同步代码块
    }
}
```

- **锁对象**：类的 Class 对象（全局唯一）
- **作用范围**：所有该类的 synchronized 静态方法
- **线程安全**：所有实例共享同一把锁

## 示例对比

```java
public class SyncDemo {
    private static int staticCounter = 0;
    private int instanceCounter = 0;
    private final Object lock = new Object();

    // 锁的是当前实例对象
    public synchronized void method1() {
        instanceCounter++;
    }

    // 锁的是 lock 对象
    public void method2() {
        synchronized(lock) {
            instanceCounter++;
        }
    }

    // 锁的是 SyncDemo.class 对象
    public static synchronized void method3() {
        staticCounter++;
    }
}
```

**互斥关系**：
- `method1` 与自身互斥（同一实例）
- `method2` 与自身互斥（同一 lock 对象）
- `method3` 与自身互斥（所有实例共享）
- `method1` 和 `method2` **不互斥**（锁对象不同）
- `method1` 和 `method3` **不互斥**（实例锁 vs 类锁）

## 常见误区

### 误区1：锁定基本类型包装类

```java
// ❌ 错误示例
private Integer count = 0;

public void increment() {
    synchronized(count) {  // count 对象会改变！
        count++;  // 自动装箱产生新对象
    }
}
```

**问题**：`count++` 产生新对象，导致锁对象改变。

**正确做法**：
```java
private final Object lock = new Object();
private Integer count = 0;

public void increment() {
    synchronized(lock) {
        count++;
    }
}
```

### 误区2：锁定 String 字面量

```java
// ❌ 避免使用
synchronized("lock") {  // 字符串常量池可能导致意外共享
    // ...
}
```

**问题**：字符串字面量会被放入常量池，可能被其他代码意外共享。

## 答题总结

1. **实例方法**：锁的是 `this`（当前实例对象）
2. **静态方法**：锁的是 `Class` 对象（类锁）
3. **同步代码块**：锁的是括号内指定的对象
4. **关键原则**：
   - 锁对象必须是引用类型
   - 锁对象不应该改变（建议用 `final`）
   - 避免使用 String 字面量或包装类作为锁对象
   - 不同锁对象之间不互斥

synchronized 锁的是对象的 Monitor，选择合适的锁对象是控制并发粒度的关键。

