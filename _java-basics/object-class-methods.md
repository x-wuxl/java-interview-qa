---
title: "Object 中定义了哪些方法？"
date: 2025-11-16
description: "全面解析 Java Object 类的 11 个核心方法及其作用"
author: "wuxl"
categories: [Java基础]
tags: [Object, equals, hashCode, toString, clone, finalize]
nav_order: 20
parent: Java基础
---
## 问题

Object 中定义了哪些方法？

## 答案

### 核心概念

`Object` 是 Java 中所有类的根父类，定义了 **11 个方法**，分为以下几类：
- **对象比较**：`equals()`、`hashCode()`
- **对象表示**：`toString()`、`getClass()`
- **对象克隆**：`clone()`
- **线程通信**：`wait()`、`notify()`、`notifyAll()`
- **对象生命周期**：`finalize()`
- **其他**：`registerNatives()`

### 方法详解

#### 1. equals(Object obj)
```java
public boolean equals(Object obj)
```
- **作用**：判断两个对象是否"相等"
- **默认实现**：比较对象引用（`this == obj`）
- **重写规则**：需满足自反性、对称性、传递性、一致性、非空性
- **注意**：重写 `equals()` 必须同时重写 `hashCode()`

#### 2. hashCode()
```java
public native int hashCode()
```
- **作用**：返回对象的哈希码（整数）
- **默认实现**：基于对象内存地址计算（native 方法）
- **约定**：相等的对象必须有相同的哈希码
- **用途**：用于 `HashMap`、`HashSet` 等哈希表结构

#### 3. toString()
```java
public String toString()
```
- **作用**：返回对象的字符串表示
- **默认实现**：`类名@哈希码的十六进制`（如 `Person@1a2b3c4d`）
- **建议**：重写以提供有意义的信息，便于调试和日志

#### 4. getClass()
```java
public final native Class<?> getClass()
```
- **作用**：返回对象的运行时类对象（`Class` 实例）
- **特点**：`final` 方法，不可重写
- **用途**：反射、类型判断

```java
Person p = new Person();
Class<?> clazz = p.getClass();  // 获取 Person.class
```

#### 5. clone()
```java
protected native Object clone() throws CloneNotSupportedException
```
- **作用**：创建并返回对象的副本（浅克隆）
- **前提**：类必须实现 `Cloneable` 接口
- **访问权限**：`protected`，需要重写为 `public`

#### 6. wait() / wait(long timeout) / wait(long timeout, int nanos)
```java
public final void wait() throws InterruptedException
public final native void wait(long timeout) throws InterruptedException
public final void wait(long timeout, int nanos) throws InterruptedException
```
- **作用**：使当前线程进入等待状态，释放对象锁
- **前提**：必须在同步代码块或同步方法中调用
- **唤醒**：通过 `notify()` 或 `notifyAll()` 唤醒

#### 7. notify()
```java
public final native void notify()
```
- **作用**：唤醒在此对象监视器上等待的单个线程（随机选择）
- **前提**：必须在同步代码块或同步方法中调用

#### 8. notifyAll()
```java
public final native void notifyAll()
```
- **作用**：唤醒在此对象监视器上等待的所有线程
- **前提**：必须在同步代码块或同步方法中调用

#### 9. finalize()
```java
protected void finalize() throws Throwable
```
- **作用**：对象被垃圾回收前调用（已废弃）
- **问题**：执行时机不确定，性能差，容易导致内存泄漏
- **替代**：使用 `try-with-resources` 或 `Cleaner` API（Java 9+）

#### 10. registerNatives()
```java
private static native void registerNatives()
```
- **作用**：注册本地方法（JVM 内部使用）
- **特点**：私有方法，开发者无需关注

### 方法分类总结

| 类别 | 方法 | 是否可重写 | 常见用途 |
|------|------|-----------|---------|
| **对象比较** | `equals()` | 是 | 逻辑相等判断 |
|  | `hashCode()` | 是 | 哈希表存储 |
| **对象表示** | `toString()` | 是 | 调试、日志 |
|  | `getClass()` | 否（final） | 反射、类型判断 |
| **对象克隆** | `clone()` | 是 | 对象复制 |
| **线程通信** | `wait()` | 否（final） | 线程等待 |
|  | `notify()` | 否（final） | 唤醒单个线程 |
|  | `notifyAll()` | 否（final） | 唤醒所有线程 |
| **生命周期** | `finalize()` | 是（已废弃） | 资源清理（不推荐） |
| **内部方法** | `registerNatives()` | 否 | JVM 内部使用 |

### 重点方法使用示例

```java
public class Person {
    private String name;
    private int age;

    // 重写 equals
    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;
        Person person = (Person) obj;
        return age == person.age && Objects.equals(name, person.name);
    }

    // 重写 hashCode
    @Override
    public int hashCode() {
        return Objects.hash(name, age);
    }

    // 重写 toString
    @Override
    public String toString() {
        return "Person{name='" + name + "', age=" + age + "}";
    }
}
```

### 面试总结

- **11 个方法**：`equals`、`hashCode`、`toString`、`getClass`、`clone`、`wait`（3 个重载）、`notify`、`notifyAll`、`finalize`、`registerNatives`
- **常重写的方法**：`equals`、`hashCode`、`toString`、`clone`
- **线程相关**：`wait`、`notify`、`notifyAll` 必须在同步块中使用
- **已废弃**：`finalize()` 不推荐使用，用 `try-with-resources` 替代
