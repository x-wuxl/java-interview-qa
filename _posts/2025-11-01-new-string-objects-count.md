---
layout: post
title: "String str = new String(\"hollis\")创建了几个对象？"
date: 2025-11-01
description: "深入剖析new String创建对象的底层机制、字符串常量池与堆内存的分配、类加载时机及字节码验证"
author: "wuxl"
categories: [Java基础]
tags: [String, new, 字符串常量池, 对象创建, 字节码]
---

## 问题

String str = new String("hollis")创建了几个对象？

## 答案

### 1. 直接答案

**标准回答：1个或2个对象**

- **常见情况（首次遇到"hollis"）**：创建**2个对象**
  - 1个在**字符串常量池**（存储字面量"hollis"）
  - 1个在**堆内存**（new String()创建的对象）

- **特殊情况（常量池已存在"hollis"）**：创建**1个对象**
  - 常量池中已有"hollis"，不再创建
  - 仅在堆中创建1个新对象

### 2. 详细分析

#### 对象创建过程

```java
String str = new String("hollis");
```

**执行步骤：**

1. **检查字符串常量池**
   - JVM检查常量池中是否已存在"hollis"
   - 如果不存在，在常量池中创建"hollis"对象（**第1个对象**）

2. **堆中创建对象**
   - 执行`new String()`，在堆中创建新对象（**第2个对象**）
   - 将常量池中的"hollis"内容复制到堆对象中

3. **引用赋值**
   - 将堆中对象的引用赋值给变量`str`

#### 内存结构图

```
字符串常量池（堆中，JDK 7+）：
  +-------------+
  | "hollis"    |  <--- 对象1（字面量）
  +-------------+

Java堆内存：
  +-------------+
  | String对象  |  <--- 对象2（new创建）
  | value → "hollis"
  +-------------+
       ↑
       |
     str（变量引用）
```

### 3. 字节码验证

#### 源代码

```java
public class StringTest {
    public static void main(String[] args) {
        String str = new String("hollis");
    }
}
```

#### 编译并查看字节码

```bash
javac StringTest.java
javap -v StringTest.class
```

#### 字节码分析

**Constant Pool（常量池）：**
```
Constant pool:
   #1 = Methodref          #6.#15  // java/lang/Object."<init>":()V
   #2 = Class              #16     // java/lang/String
   #3 = String             #17     // hollis  <- 字符串字面量在常量池
   #4 = Methodref          #2.#18  // java/lang/String."<init>":(Ljava/lang/String;)V
   ...
  #17 = Utf8               hollis   <- 实际字符串内容
```

**main方法字节码：**
```
 0: new           #2   // class java/lang/String  <- 创建String对象
 3: dup                 // 复制栈顶引用
 4: ldc           #3   // String hollis  <- 从常量池加载"hollis"
 6: invokespecial #4   // Method java/lang/String."<init>":(Ljava/lang/String;)V
 9: astore_1            // 存入变量str
10: return
```

**关键指令解析：**
- `new #2`：在堆中分配String对象空间（**对象2**）
- `ldc #3`：从常量池加载"hollis"字面量（**对象1**，如果常量池中不存在则创建）
- `invokespecial #4`：调用String构造方法，传入常量池中的"hollis"

### 4. 不同场景的对比

#### 场景1：首次使用"hollis"

```java
// 常量池中不存在"hollis"
String str = new String("hollis");
// 创建2个对象：
// 1. 常量池中的"hollis"
// 2. 堆中的String对象
```

#### 场景2：常量池已存在"hollis"

```java
String s1 = "hollis";  // 常量池中创建"hollis"
String str = new String("hollis");  // 仅在堆中创建1个对象
// 此时只创建1个对象：堆中的String对象
```

#### 场景3：仅使用字面量

```java
String s1 = "hollis";  // 创建1个对象（常量池）
String s2 = "hollis";  // 不创建对象，复用s1
System.out.println(s1 == s2);  // true
```

#### 场景4：多次new String

```java
String s1 = new String("hollis");  // 2个对象（常量池1个 + 堆1个）
String s2 = new String("hollis");  // 1个对象（仅堆中）
String s3 = new String("hollis");  // 1个对象（仅堆中）

System.out.println(s1 == s2);  // false - 不同堆对象
System.out.println(s1 == s3);  // false - 不同堆对象
System.out.println(s1.equals(s2));  // true - 内容相同
```

### 5. 引用关系验证

```java
String str = new String("hollis");
String literal = "hollis";

System.out.println(str == literal);  // false - 不同对象
System.out.println(str.equals(literal));  // true - 内容相同
System.out.println(str.intern() == literal);  // true - intern返回常量池引用
```

**说明：**
- `str`指向堆中对象
- `literal`指向常量池对象
- `str.intern()`返回常量池中的"hollis"，与`literal`是同一对象

### 6. 类加载时机的影响

#### 情况1：字面量在类加载时进入常量池

```java
public class StringTest {
    public static void main(String[] args) {
        // 类加载时，常量池已准备好"hollis"
        String str = new String("hollis");  // 仅创建堆对象，1个对象
    }
}
```

**注意：**字符串字面量在**类加载的准备阶段**就会在常量池中准备好。

#### 情况2：运行时动态拼接

```java
String s = "hol";
String str = new String(s + "lis");  // 创建几个对象？

// 分析：
// 1. "hol" - 常量池1个
// 2. "lis" - 常量池1个（如果存在类似代码）
// 3. s + "lis" - 运行期拼接，堆中1个
// 4. new String() - 堆中1个
// 注意：拼接结果不会自动进入常量池
```

### 7. 常见变体题目

#### 变体1：使用char数组

```java
char[] chars = {'h', 'o', 'l', 'l', 'i', 's'};
String str = new String(chars);
// 创建几个对象？
// 答案：1个（仅堆中对象，不涉及常量池）
```

#### 变体2：双重构造

```java
String str = new String(new String("hollis"));
// 创建几个对象？
// 答案：3个
// 1. 常量池中的"hollis"
// 2. 内层new String("hollis") - 堆对象1
// 3. 外层new String(...) - 堆对象2
```

#### 变体3：拼接后构造

```java
String str = new String("hol" + "lis");
// 创建几个对象？
// 答案：2个
// 1. 编译期优化："hol" + "lis" → "hollis"，常量池1个
// 2. new String() - 堆对象1个
```

### 8. 源码分析

#### String构造方法

```java
// String(String original)构造方法源码
public String(String original) {
    this.value = original.value;  // 复制char[]/byte[]引用
    this.hash = original.hash;    // 复制hashCode缓存
}
```

**关键点：**
- 构造方法只是复制内部`value`数组的引用
- 不会深拷贝字符数组
- 由于String不可变，这种浅拷贝是安全的

### 9. 性能与最佳实践

#### ❌ 不推荐的写法

```java
// 无意义的构造，创建多余对象
String str = new String("hollis");

// 等价于
String str = "hollis";  // 推荐！
```

**浪费原因：**
- 多创建1个堆对象
- 占用额外内存
- 失去常量池复用优势

#### ✅ 推荐的写法

```java
// 直接使用字面量
String str = "hollis";

// 需要复制时
String copy = new String(originalCharArray);  // 从char[]构造

// 需要独立对象时（极少场景）
String independent = new String(sharedString);
```

#### 使用new String的合理场景

```java
// 场景1：从字节数组构造
byte[] bytes = {104, 111, 108, 108, 105, 115};
String str = new String(bytes, StandardCharsets.UTF_8);

// 场景2：子字符串，避免内存泄漏（JDK 6）
String large = loadLargeString();  // 假设100MB
String small = new String(large.substring(0, 10));  // 复制10字符，释放100MB
large = null;

// 注意：JDK 7+的substring已优化，不再需要这种做法
```

### 10. 面试答题要点

**标准回答模板：**

1. **精确答案**：创建1个或2个对象，取决于常量池中是否已存在该字符串
2. **详细说明**：
   - 如果常量池没有"hollis"：创建2个对象（常量池1个 + 堆1个）
   - 如果常量池已有"hollis"：创建1个对象（仅堆中）
3. **内存位置**：
   - 字面量"hollis"在字符串常量池（JDK 7+位于堆中）
   - new String()创建的对象在Java堆
4. **引用关系**：变量str指向堆中对象，不是常量池对象
5. **最佳实践**：直接用字面量`String str = "hollis"`，避免不必要的堆对象

**加分点：**
- 能说明字节码层面的创建过程（new、ldc、invokespecial）
- 了解类加载时机对常量池的影响
- 知道JDK 6和JDK 7+常量池位置的变化
- 能对比字面量和new String的区别
- 提到`intern()`方法的作用

### 11. 总结

**核心知识点对比：**

| 创建方式 | 对象数量 | 内存位置 | 引用复用 |
|---------|---------|---------|---------|
| `String s = "hollis"` | 1个 | 常量池 | ✅ 是 |
| `new String("hollis")` | 1-2个 | 堆 + 常量池 | ❌ 否 |
| `new String(charArray)` | 1个 | 堆 | ❌ 否 |

**记忆要点：**
1. **字面量 → 常量池**，可复用
2. **new → 堆**，总创建新对象
3. **new String("字面量")** → 可能2个对象
4. **常量池位置**：JDK 7+在堆中，JDK 6在PermGen

这道题考察的是对**String对象创建机制、常量池、堆内存、字节码**的深入理解，是String相关的高频面试题。
