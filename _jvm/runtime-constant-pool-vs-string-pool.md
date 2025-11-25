---
title: "运行时常量池和字符串常量池的关系是什么？"
date: 2025-11-01
description: "深入理解运行时常量池与字符串常量池的区别、联系和在不同JDK版本中的位置变化"
author: "wuxl"
categories: [JVM]
tags: [常量池, 字符串常量池, 运行时常量池, JVM, 面试]
nav_order: 158
parent: JVM
---
## 问题

运行时常量池和字符串常量池的关系是什么？

## 答案

### 核心概念

- **运行时常量池（Runtime Constant Pool）**：每个类加载后在方法区创建的常量池,存储该类的常量信息
- **字符串常量池（String Pool/String Table）**：JVM全局唯一的字符串缓存池，用于存储字符串字面量的引用

**关系**：字符串常量池是**独立于**运行时常量池的全局结构，运行时常量池中的字符串字面量会在字符串常量池中维护引用。

### 关键区别

| 对比项 | 运行时常量池 | 字符串常量池 |
|-------|-------------|-------------|
| **作用域** | 每个类独立 | **全局唯一**（所有类共享） |
| **存储位置（JDK 8+）** | 元空间（Metaspace） | **堆（Heap）** |
| **存储内容** | 字面量、符号引用、直接引用 | **字符串对象的引用** |
| **数据结构** | 数组/表结构 | **HashTable** |
| **生命周期** | 跟随类的生命周期 | 跟随JVM生命周期 |
| **可见性** | 类级别 | JVM全局 |

### 存储位置的演变

#### **JDK 7之前**

```
永久代（PermGen）
├── 运行时常量池（每个类一个）
└── 字符串常量池
```

#### **JDK 7**

```
元空间（Metaspace）
└── 运行时常量池

堆（Heap）
└── 字符串常量池 ← 移至堆
```

#### **JDK 8及之后**

```
元空间（Metaspace）
└── 运行时常量池

堆（Heap）
└── 字符串常量池
```

**关键变化**：JDK 7将字符串常量池从永久代移到堆，避免永久代OOM问题。

### 字符串常量池的特殊性

#### **1. 全局唯一性**

```java
public class StringPoolDemo {
    public static void main(String[] args) {
        // 两个不同类中的相同字符串字面量
        String s1 = "hello"; // ClassA的运行时常量池
        String s2 = "hello"; // ClassB的运行时常量池

        // 实际上都指向字符串常量池中的同一个对象
        System.out.println(s1 == s2); // true
    }
}
```

**原理**：
```
ClassA运行时常量池 → "hello"引用 ↘
                                  字符串常量池中的"hello"对象
ClassB运行时常量池 → "hello"引用 ↗
```

#### **2. intern()方法的作用**

```java
public class InternDemo {
    public static void main(String[] args) {
        // 堆中创建新对象
        String s1 = new String("hello");

        // intern()尝试将字符串加入字符串常量池
        String s2 = s1.intern();

        // 字符串字面量直接来自常量池
        String s3 = "hello";

        System.out.println(s1 == s2); // false（s1在堆，s2在常量池）
        System.out.println(s2 == s3); // true（都来自字符串常量池）
    }
}
```

### 运行时常量池与字符串常量池的交互

#### **示例1：字符串字面量的加载**

```java
public class StringLoadingDemo {
    public static void main(String[] args) {
        String s1 = "hello"; // 触发字符串加载
    }
}
```

**加载流程**：
```
1. 编译期：
   "hello"存入Class文件的Class常量池

2. 类加载期：
   ├─ Class常量池 → ClassA的运行时常量池
   └─ 检查字符串常量池是否有"hello"
      ├─ 没有：在堆中创建"hello"对象，将引用存入字符串常量池
      └─ 有：直接使用已有引用

3. 执行期：
   s1 = 字符串常量池中"hello"的引用
```

#### **示例2：跨类字符串共享**

```java
// ClassA.java
public class ClassA {
    public static String getGreeting() {
        return "hello"; // 来自ClassA的运行时常量池
    }
}

// ClassB.java
public class ClassB {
    public static String getGreeting() {
        return "hello"; // 来自ClassB的运行时常量池
    }
}

// Main.java
public class Main {
    public static void main(String[] args) {
        String s1 = ClassA.getGreeting();
        String s2 = ClassB.getGreeting();
        String s3 = "hello";

        // 都指向字符串常量池的同一个对象
        System.out.println(s1 == s2); // true
        System.out.println(s1 == s3); // true
    }
}
```

### JDK 7的关键变化详解

#### **变化1：字符串常量池位置迁移**

```java
// JDK 6
public class JDK6StringPoolDemo {
    public static void main(String[] args) {
        String s = "hello";
        // s引用的对象在永久代的字符串常量池
    }
}

// JDK 7+
public class JDK7StringPoolDemo {
    public static void main(String[] args) {
        String s = "hello";
        // s引用的对象在堆中的字符串常量池
    }
}
```

**好处**：
- 永久代空间有限，容易OOM
- 堆空间更大，GC效率更高
- 避免`-XX:PermSize`调优困扰

#### **变化2：intern()行为变化**

```java
public class InternBehaviorDemo {
    public static void main(String[] args) {
        String s1 = new String("a") + new String("b"); // 堆中"ab"
        String s2 = s1.intern();
        String s3 = "ab";

        System.out.println(s1 == s2); // JDK 6: false, JDK 7+: true
        System.out.println(s2 == s3); // true
    }
}
```

**JDK 6行为**：
```
intern() → 在永久代字符串常量池创建"ab"副本 → 返回副本引用
s1（堆）!= s2（永久代）
```

**JDK 7+行为**：
```
intern() → 字符串常量池存储s1的引用（不复制对象）→ 返回s1引用
s1（堆）== s2（字符串常量池存的是s1的引用）
```

### 实战示例

#### **示例1：常量池膨胀问题**

```java
public class StringPoolInflationDemo {
    public static void main(String[] args) {
        // 危险：大量intern()导致字符串常量池膨胀
        List<String> list = new ArrayList<>();
        for (int i = 0; i < 10000000; i++) {
            list.add(String.valueOf(i).intern()); // 1000万个字符串进入常量池
        }
        // 可能导致性能下降或OOM
    }
}
```

**优化**：
```java
// 避免不必要的intern()
List<String> list = new ArrayList<>();
for (int i = 0; i < 10000000; i++) {
    list.add(String.valueOf(i)); // 不使用intern()
}
```

#### **示例2：查看字符串常量池大小**

```bash
# JDK 7+
java -XX:+PrintStringTableStatistics -version

# 输出
StringTable statistics:
Number of buckets       :     60013 =    480104 bytes
Number of entries       :      1765 =     42360 bytes
Number of literals      :      1765 =    156440 bytes
```

**调优参数**：
```bash
# 设置字符串常量池大小（bucket数量）
-XX:StringTableSize=1000003

# 默认值
# JDK 7: 60013
# JDK 8: 60013
# JDK 9+: 动态调整
```

### 内存泄漏风险

```java
public class StringPoolLeakDemo {
    // 危险：大量长字符串intern()
    public void processLogs(List<String> logs) {
        for (String log : logs) {
            // 每条日志都很长（几KB），且不重复
            cache.put(log.intern(), parseLog(log));
            // 字符串常量池持有这些大对象引用，无法GC
        }
    }
}
```

**正确做法**：
```java
public void processLogs(List<String> logs) {
    for (String log : logs) {
        // 不使用intern()，让字符串可以被GC
        cache.put(log, parseLog(log));
    }
}
```

### 判断字符串是否在常量池

```java
public class StringPoolCheckDemo {
    public static void main(String[] args) {
        String s1 = "hello";
        String s2 = new String("world");
        String s3 = s2.intern();

        // 方式1：比较intern()结果
        System.out.println(s1 == s1.intern()); // true（已在常量池）
        System.out.println(s2 == s2.intern()); // false（不在常量池）
        System.out.println(s3 == s3.intern()); // true（已在常量池）

        // 方式2：与字面量比较
        System.out.println(s1 == "hello");  // true
        System.out.println(s2 == "world");  // false
        System.out.println(s3 == "world");  // true
    }
}
```

### 数据结构对比

#### **运行时常量池**
```java
// 简化的结构（概念示意）
class RuntimeConstantPool {
    Object[] constants; // 数组存储
    int size;

    Object getConstant(int index) {
        return constants[index];
    }
}
```

#### **字符串常量池**
```java
// 简化的结构（概念示意）
class StringTable {
    Entry[] buckets; // HashTable结构
    int size;

    static class Entry {
        int hash;
        String value;
        Entry next; // 链表解决冲突
    }

    String intern(String str) {
        int hash = str.hashCode();
        int index = hash % buckets.length;
        // 查找或插入
    }
}
```

### 面试要点总结

1. **核心区别**：运行时常量池是类级别的，字符串常量池是JVM全局唯一的
2. **存储位置**：JDK 7+字符串常量池在堆，运行时常量池在元空间
3. **关系**：运行时常量池中的字符串字面量引用指向字符串常量池中的对象
4. **intern()行为**：JDK 7+存储引用而非复制对象（重要变化）
5. **性能考量**：避免大量intern()导致字符串常量池膨胀
6. **调优参数**：`-XX:StringTableSize`调整字符串常量池大小
7. **内存泄漏风险**：大量不重复字符串intern()会导致内存泄漏
