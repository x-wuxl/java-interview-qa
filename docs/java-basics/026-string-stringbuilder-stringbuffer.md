---
layout: default
title: "String、StringBuilder和StringBuffer的区别？"
parent: Java基础
nav_order: 26
description: "深入对比String、StringBuilder和StringBuffer的可变性、线程安全性、性能差异及适用场景"
author: "wuxl"
date: 2025-11-01
---
## 问题

String、StringBuilder和StringBuffer的区别？

## 答案

### 1. 核心概念

这三个类都用于处理字符串，但在**可变性**、**线程安全性**和**性能**上有本质区别：

- **String**：不可变（immutable）字符串，线程安全
- **StringBuilder**：可变字符串，非线程安全，JDK 1.5引入
- **StringBuffer**：可变字符串，线程安全（方法加synchronized）

### 2. 详细对比

#### 可变性差异

**String - 不可变**
```java
String str = "hello";
str = str + " world";  // 实际创建了新对象，原对象不变
```

每次修改都会创建新对象，原字符串保持不变。频繁修改会产生大量临时对象。

**StringBuilder/StringBuffer - 可变**
```java
StringBuilder sb = new StringBuilder("hello");
sb.append(" world");  // 直接在原对象上修改，无需创建新对象
```

内部维护可变字符数组，修改操作直接在原对象上进行。

#### 线程安全性

**StringBuffer - 线程安全**
```java
// StringBuffer的append方法源码
@Override
public synchronized StringBuffer append(String str) {
    toStringCache = null;
    super.append(str);
    return this;
}
```

所有公共方法都使用`synchronized`关键字修饰，保证线程安全，但性能较低。

**StringBuilder - 非线程安全**
```java
// StringBuilder的append方法源码
@Override
public StringBuilder append(String str) {
    super.append(str);
    return this;
}
```

没有同步机制，不保证线程安全，但性能更高。

#### 性能对比

**测试代码：**
```java
public class StringPerformanceTest {
    public static void main(String[] args) {
        int count = 50000;

        // String拼接 - 最慢
        long start = System.currentTimeMillis();
        String str = "";
        for (int i = 0; i < count; i++) {
            str += "a";
        }
        System.out.println("String: " + (System.currentTimeMillis() - start) + "ms");

        // StringBuffer - 较快
        start = System.currentTimeMillis();
        StringBuffer sb = new StringBuffer();
        for (int i = 0; i < count; i++) {
            sb.append("a");
        }
        System.out.println("StringBuffer: " + (System.currentTimeMillis() - start) + "ms");

        // StringBuilder - 最快
        start = System.currentTimeMillis();
        StringBuilder sbd = new StringBuilder();
        for (int i = 0; i < count; i++) {
            sbd.append("a");
        }
        System.out.println("StringBuilder: " + (System.currentTimeMillis() - start) + "ms");
    }
}
```

**性能结果（大致）：**
- String: 2000+ ms（产生大量垃圾对象）
- StringBuffer: 2-5 ms（有同步开销）
- StringBuilder: 1-3 ms（最快）

### 3. 源码实现关键点

#### 底层存储结构

```java
// String - final char[]，JDK9后改为byte[]
public final class String {
    private final byte[] value;  // 不可变数组
    // ...
}

// AbstractStringBuilder - 可变char[]，JDK9后改为byte[]
abstract class AbstractStringBuilder {
    byte[] value;  // 可变数组
    int count;     // 实际字符数

    // 扩容机制
    private void ensureCapacityInternal(int minimumCapacity) {
        if (minimumCapacity - value.length > 0) {
            expandCapacity(minimumCapacity);
        }
    }
}
```

#### 扩容策略

```java
// StringBuilder/StringBuffer扩容：新容量 = 旧容量 * 2 + 2
void expandCapacity(int minimumCapacity) {
    int newCapacity = value.length * 2 + 2;
    if (newCapacity - minimumCapacity < 0)
        newCapacity = minimumCapacity;
    if (newCapacity < 0) {
        if (minimumCapacity < 0) // overflow
            throw new OutOfMemoryError();
        newCapacity = Integer.MAX_VALUE;
    }
    value = Arrays.copyOf(value, newCapacity);
}
```

### 4. 使用场景与最佳实践

| 类 | 使用场景 | 性能 | 线程安全 |
|---|---|---|---|
| **String** | 字符串常量、少量拼接操作 | 修改慢 | 安全 |
| **StringBuilder** | 单线程环境大量拼接（推荐） | 最快 | 不安全 |
| **StringBuffer** | 多线程环境共享字符串拼接 | 较快 | 安全 |

#### 最佳实践

**✅ 推荐做法：**
```java
// 1. 单线程拼接 - 使用StringBuilder
public String buildSql(List<String> fields) {
    StringBuilder sql = new StringBuilder("SELECT ");
    for (int i = 0; i < fields.size(); i++) {
        if (i > 0) sql.append(", ");
        sql.append(fields.get(i));
    }
    sql.append(" FROM table");
    return sql.toString();
}

// 2. 预估容量，减少扩容
StringBuilder sb = new StringBuilder(100);  // 预分配容量

// 3. 常量拼接直接用+（编译器优化）
String msg = "Hello" + " " + "World";  // 编译期优化为"Hello World"
```

**❌ 避免做法：**
```java
// 循环中使用String拼接
String result = "";
for (int i = 0; i < 1000; i++) {
    result += i;  // 产生1000个临时对象！
}

// 单线程环境使用StringBuffer
StringBuilder sb = new StringBuffer();  // 不必要的同步开销
```

### 5. 编译器优化

#### JDK 8及之前
```java
String s = "a" + "b" + "c";
// 编译器优化为：
String s = "abc";

String s1 = "a";
String s2 = s1 + "b";
// 编译器优化为：
String s2 = new StringBuilder(s1).append("b").toString();
```

#### JDK 9及之后
使用`invokedynamic`指令和`StringConcatFactory`优化字符串拼接，性能进一步提升。

### 6. 面试答题要点

**标准回答结构：**

1. **可变性**：String不可变，StringBuilder/StringBuffer可变
2. **线程安全**：String和StringBuffer线程安全，StringBuilder不安全
3. **性能**：StringBuilder > StringBuffer > String（修改操作时）
4. **使用场景**：
   - String：字符串常量、传参
   - StringBuilder：单线程大量拼接（99%场景推荐）
   - StringBuffer：多线程共享拼接（实际很少用）
5. **底层原理**：String用final数组，StringBuilder用可变数组+扩容机制

**加分点：**
- 提到String的不可变性优势（安全性、缓存、常量池）
- 说明StringBuilder的扩容策略（2倍+2）
- 了解编译器对字符串拼接的优化
- 知道JDK 9的改进（byte[]存储、invokedynamic优化）

### 7. 总结

在实际开发中，**99%的场景应该使用StringBuilder**，因为：
- 现代应用很少直接在多线程间共享可变字符串对象
- 如需线程安全，通常通过方法局部变量或其他同步机制实现
- StringBuffer的synchronized开销在高并发场景下影响明显

只有在明确需要在多线程间共享并修改同一个字符串对象时，才考虑StringBuffer。
