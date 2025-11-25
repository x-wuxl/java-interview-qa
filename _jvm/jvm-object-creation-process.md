---
title: "JVM是如何创建对象的？"
date: 2025-11-01
description: "深入解析JVM对象创建的完整过程，包括类加载检查、内存分配、初始化等关键步骤"
author: "wuxl"
categories: [JVM]
tags: [JVM, 对象创建, 内存分配, 类加载]
nav_order: 119
parent: JVM
---
## 问题

JVM是如何创建对象的？

## 答案

### 核心概念

JVM创建对象是一个复杂的过程，涉及类加载检查、内存分配、初始化等多个步骤。当遇到`new`指令时，JVM会执行一系列操作来创建新对象。

### 对象创建过程

#### 1. 类加载检查

```java
Person person = new Person(); // 触发对象创建
```

JVM首先检查这个类的符号引用是否已被加载、解析、初始化：

- **未加载**：执行类加载过程（加载、验证、准备、解析、初始化）
- **已加载**：直接进行下一步
- **加载失败**：抛出`NoClassDefFoundError`

#### 2. 内存分配

对象所需内存在类加载完成后就可确定，JVM在堆中分配内存：

**分配方式**：
- **指针碰撞**（Serial、ParNew等收集器）：内存规整，指针向空闲区域移动
- **空闲列表**（CMS等收集器）：内存不规整，维护空闲区域列表

#### 3. 内存空间初始化

将分配到的内存空间（不包括对象头）初始化为零值：

```java
// JVM内部操作，对应用户代码
// 将实例字段设置为默认值
// int -> 0, boolean -> false, reference -> null
```

这保证了对象的实例字段在不赋初值时也���直接使用。

#### 4. 设置对象头

设置对象的必要信息：
- **Mark Word**：哈希码、GC分代年龄、锁状态标志等
- **类型指针**：指向对象所属类的元数据
- **数组长度**（如果是数组）：数组长度

#### 5. 执行`<init>`方法

按照程序员的意图初始化对象：
- **实例初始化块**
- **构造函数**
- **字段赋值语句**

```java
public class Person {
    private String name = "Unknown"; // 字段赋值

    { // 实例初始化块
        System.out.println("Initializing Person");
    }

    public Person() { // 构造函数
        this.name = "Default";
    }
}
```

### 性能优化考虑

#### 1. TLAB（Thread Local Allocation Buffer）

为了避免内存分配的线程竞争，JVM为每个线程在Eden区分配了一块私有内存区域：

```java
// JVM内部优化
// 大多数对象在TLAB中分配，无需同步
// TLAB空间不足时，再尝试Eden区CAS分配
```

#### 2. 对象创建优化

- **栈上分配**：通过逃逸分析，未逃逸对象可在栈上分配
- **标量替换**：将对象分解为基本类型，消除对象创建
- **锁消除**：消除同步块中的不必要锁

### 源码关键点

在HotSpot中，对象创建的核心逻辑在`instanceKlass.cpp`中：

```cpp
// 简化的对象创建流程
oop instanceKlass::allocate_instance(TRAPS) {
  // 1. 检查类是否已初始化
  if (!is_initialized()) {
    // 执行类初始化
  }

  // 2. 分配内存
  oop obj = CollectedHeap::obj_allocate(this, size, CHECK_NULL);

  // 3. 设置对象头
  obj->set_mark(markWord::prototype());

  // 4. 执行构造函数
  call_constructor(obj, CHECK_NULL);

  return obj;
}
```

### 面试要点总结

1. **五步创建流程**：类加载检查 → 内存分配 → 空间初始化 → 对象头设置 → `<init>`执行
2. **内存分配方式**：指针碰撞 vs 空闲列表
3. **线程安全保证**：CAS + TLAB机制
4. **性能优化**：逃逸分析、栈上分配、标量替换
5. **异常情况**：类加载失败、内存不足时的处理

记住这个完整流程，能够清晰阐述每个步骤的作用和实现原理，就是优秀的面试答案。