---
layout: post
title: "字符串常量是什么时候进入到字符串常量池的？"
date: 2025-11-01
description: "深入剖析字符串常量池的加载时机：类加载过程、ldc指令执行、运行时字符串入池机制及JDK版本差异"
author: "wuxl"
categories: [Java基础]
tags: [String, 字符串常量池, 类加载, ldc指令, JVM]
---

## 问题

字符串常量是什么时候进入到字符串常量池的？

## 答案

### 1. 核心答案

字符串常量进入常量池的时机**取决于字符串的类型和使用方式**：

1. **字面量常量（编译期确定）**：在**类加载的解析阶段**或**首次执行ldc指令时**
2. **运行期字符串**：通过`String.intern()`手动放入
3. **new String()创建的字符串**：字面量部分在类加载时，堆对象不入池（除非调用intern）

**关键时机：**
- **类加载时**：字符串字面量准备好，但可能**延迟解析**（Lazy Resolution）
- **ldc指令执行时**：确保字符串已在常量池中（如果未解析，此时解析）
- **运行时intern调用**：手动将字符串加入常量池

### 2. 类加载过程与字符串常量池

#### 类加载的七个阶段

```
1. 加载（Loading）
2. 验证（Verification）
3. 准备（Preparation）
4. 解析（Resolution）  <- 字符串常量可能在此阶段入池
5. 初始化（Initialization）
6. 使用（Using）
7. 卸载（Unloading）
```

#### 解析阶段（Resolution）

在**解析阶段**，JVM将class文件常量池中的**符号引用**转换为**直接引用**：

```java
// 源代码
public class StringTest {
    public static void main(String[] args) {
        String s = "hello";
    }
}
```

**class文件常量池（编译期）：**
```
Constant pool:
   #1 = Methodref          #6.#20
   #2 = String             #21  // 符号引用：指向#21
   #3 = Fieldref           #22.#23
   ...
  #21 = Utf8               hello  // 字符串内容
```

**运行时常量池（解析后）：**
```
#2 指向字符串常量池中的"hello"对象（直接引用）
```

**解析时机：**
- **急切解析（Eager Resolution）**：类加载时立即解析所有符号
- **延迟解析（Lazy Resolution）**：首次使用时才解析（HotSpot默认）

### 3. ldc指令与字符串入池

#### ldc指令的作用

`ldc`（Load Constant）指令用于从常量池加载常量到操作数栈：

```java
String s = "hello";
```

**字节码：**
```
0: ldc           #2  // String hello  <- ldc指令
2: astore_1
```

#### ldc指令执行流程

```
1. ldc指令执行
    ↓
2. 检查常量池索引#2是否已解析
    ↓
3. 如果未解析：
   - 从class文件常量池获取字符串内容"hello"
   - 在字符串常量池中查找"hello"
   - 如果不存在，创建String对象并放入常量池
   - 将#2解析为指向常量池"hello"的直接引用
    ↓
4. 如果已解析：
   - 直接获取常量池中的"hello"引用
    ↓
5. 将引用压入操作数栈
```

**关键点：**字符串常量在**首次执行ldc指令时**确保已在常量池中。

### 4. 不同场景的入池时机

#### 场景1：简单字面量

```java
public class Test {
    public static void main(String[] args) {
        String s = "hello";
    }
}
```

**入池时机：**
- **类加载时**（如果JVM使用急切解析）
- **或首次执行ldc指令时**（如果JVM使用延迟解析，HotSpot默认）

#### 场景2：编译期常量拼接

```java
String s = "hel" + "lo";
```

**编译器优化：**
```java
// 编译后等价于
String s = "hello";
```

**入池时机：**
- 编译期合并为"hello"
- 类加载时或ldc指令执行时入池

#### 场景3：运行期拼接

```java
String s1 = "hel";
String s2 = s1 + "lo";  // 运行期拼接
```

**分析：**
- `"hel"`：类加载时入池
- `"lo"`：类加载时入池（如果代码中有此字面量）
- `s1 + "lo"`的结果：**不会自动入池**，在堆中创建新对象

**验证：**
```java
String s1 = "hel";
String s2 = s1 + "lo";
String s3 = "hello";
System.out.println(s2 == s3);  // false - s2在堆，s3在常量池
```

#### 场景4：new String()

```java
String s = new String("hello");
```

**分析：**
- `"hello"`字面量：类加载时入池
- `new String()`对象：在堆中创建，**不入池**

**内存结构：**
```
字符串常量池：
  "hello"  <- 类加载时创建

堆内存：
  String对象（value指向"hello"的char[]/byte[]）  <- new创建
```

#### 场景5：手动intern()

```java
String s1 = new String("hello");
String s2 = s1.intern();
```

**分析：**
- `"hello"`字面量：类加载时已入池
- `s1.intern()`：发现常量池已有"hello"，返回常量池引用
- `s2`指向常量池中的"hello"

**验证：**
```java
String s1 = new String("hello");
String s2 = s1.intern();
String s3 = "hello";
System.out.println(s1 == s2);  // false
System.out.println(s2 == s3);  // true
```

#### 场景6：动态字符串intern()

```java
String s1 = new String("hel") + new String("lo");  // 运行期拼接
String s2 = s1.intern();
String s3 = "hello";
```

**分析（JDK 7+）：**
- `"hel"`和`"lo"`：类加载时入池
- `s1`：运行期拼接结果在堆中，常量池**没有"hello"**
- `s1.intern()`：常量池中不存在"hello"，将`s1`的引用存入常量池
- `s3 = "hello"`：从常量池获取，指向`s1`

**验证：**
```java
String s1 = new String("hel") + new String("lo");
String s2 = s1.intern();
String s3 = "hello";
System.out.println(s1 == s2);  // true（JDK 7+）
System.out.println(s2 == s3);  // true（JDK 7+）
```

### 5. JDK版本差异

#### JDK 6：常量池在PermGen

```java
String s1 = new String("hel") + new String("lo");
s1.intern();
String s2 = "hello";
System.out.println(s1 == s2);  // false
```

**原因：**
- 常量池在永久代
- `intern()`会**复制字符串**到永久代
- `s1`在堆，`s2`在永久代，不同对象

#### JDK 7+：常量池在堆

```java
String s1 = new String("hel") + new String("lo");
s1.intern();
String s2 = "hello";
System.out.println(s1 == s2);  // true
```

**原因：**
- 常量池在堆中
- `intern()`存储`s1`的**引用**，而非复制
- `s1`和`s2`指向同一对象

### 6. 字节码验证

#### 示例代码

```java
public class StringPoolTest {
    public static void main(String[] args) {
        String s1 = "hello";
        String s2 = "world";
        String s3 = "hello";
    }
}
```

#### 编译并查看字节码

```bash
javac StringPoolTest.java
javap -v StringPoolTest.class
```

#### Constant Pool

```
Constant pool:
   #1 = Methodref          #6.#20
   #2 = String             #21  // hello
   #3 = String             #22  // world
   #4 = Fieldref           #23.#24
   ...
  #21 = Utf8               hello
  #22 = Utf8               world
```

#### main方法字节码

```
 0: ldc           #2   // String hello  <- 首次加载"hello"
 2: astore_1
 3: ldc           #3   // String world  <- 首次加载"world"
 5: astore_2
 6: ldc           #2   // String hello  <- 复用#2，不再创建
 8: astore_3
 9: return
```

**关键点：**
- 偏移量0和6都使用`ldc #2`，加载同一个常量池引用
- 首次ldc执行时，"hello"入池
- 后续ldc直接复用

### 7. 类加载时机影响

#### 延迟加载的例子

```java
public class LazyLoadTest {
    public static void main(String[] args) {
        System.out.println("Main started");
        // 此时InnerClass尚未加载，其字符串常量也未入池

        if (false) {
            InnerClass.test();  // 永不执行，InnerClass不会加载
        }

        System.out.println("Main finished");
    }

    static class InnerClass {
        static String s = "inner";  // 不会入池，因为InnerClass未被加载

        static void test() {
            System.out.println(s);
        }
    }
}
```

**说明：**
- `InnerClass`未被使用，不会加载
- 其字符串常量`"inner"`不会进入常量池

### 8. 常见误区

#### 误区1：认为所有字符串常量在程序启动时就入池

```java
public class Test {
    static String s1 = "hello";  // ✅ 类加载时入池

    void method() {
        String s2 = "world";  // ⚠️ 类加载时或首次执行ldc时入池（取决于JVM）
    }
}
```

**实际情况：**
- HotSpot使用延迟解析，字符串常量在**首次使用时**才确保入池
- 并非所有常量在类加载时立即解析

#### 误区2：认为运行期拼接的字符串会自动入池

```java
String s = "hel" + "lo";  // ✅ 编译期优化，"hello"入池
String s = str1 + str2;   // ❌ 运行期拼接，结果在堆中，不入池
```

#### 误区3：认为new String()会在常量池创建对象

```java
String s = new String("hello");
// "hello"字面量入池
// new String()对象在堆中，不入池
```

### 9. 调试验证

#### 使用JVM参数打印字符串表

```bash
# JDK 8
-XX:+PrintStringTableStatistics

# JDK 11+
-Xlog:stringtable=trace
```

#### 使用jmap查看

```bash
# 查看堆内存详情
jmap -heap <pid>

# 导出堆转储
jmap -dump:format=b,file=heap.bin <pid>

# 使用MAT/JVisualVM分析字符串常量池
```

### 10. 最佳实践

#### 推荐做法

```java
// ✅ 直接使用字面量
String s = "hello";

// ✅ 编译期常量拼接
String s = "hel" + "lo";

// ✅ 高重复字符串使用intern
String status = dbResult.getString("status").intern();
```

#### 避免做法

```java
// ❌ 不必要的new String
String s = new String("hello");  // 多创建一个对象

// ❌ 对唯一值使用intern
String uuid = UUID.randomUUID().toString().intern();  // 浪费常量池空间

// ❌ 循环中拼接字符串
String s = "";
for (int i = 0; i < 100; i++) {
    s += i;  // 每次循环创建新对象
}
```

### 11. 面试答题要点

**标准回答结构：**

1. **分场景回答**：
   - 字面量：类加载时或首次ldc指令执行时
   - 运行期拼接：不自动入池，需要调用intern()
   - new String()：字面量入池，堆对象不入池

2. **关键时机**：
   - 类加载的解析阶段（延迟解析或急切解析）
   - ldc指令首次执行时
   - 调用String.intern()时

3. **JDK差异**：
   - JDK 6：常量池在PermGen，intern会复制
   - JDK 7+：常量池在堆，intern存引用

4. **字节码层面**：ldc指令触发字符串常量解析和入池

5. **延迟加载**：HotSpot默认延迟解析，首次使用时才入池

**加分点：**
- 了解类加载的七个阶段
- 知道ldc指令的执行流程
- 能说明急切解析vs延迟解析
- 对比JDK 6和JDK 7+的常量池差异
- 能用字节码验证入池时机

### 12. 总结

**字符串常量入池时机总结：**

| 字符串类型 | 入池时机 | 示例 |
|-----------|---------|------|
| **字面量** | 类加载时或ldc执行时 | `String s = "hello";` |
| **编译期常量** | 同字面量 | `String s = "hel" + "lo";` |
| **final变量** | 同字面量 | `final String a="a"; String s=a+"b";` |
| **运行期拼接** | 不入池（除非intern） | `String s = s1 + s2;` |
| **new String()** | 字面量入池，对象不入池 | `new String("hello")` |
| **手动intern** | intern调用时 | `s.intern();` |

**核心要点：**
1. **编译期确定的字符串**：类加载时入池（或延迟到首次使用）
2. **运行期动态生成的字符串**：默认不入池，需手动intern
3. **ldc指令**：确保字符串在常量池中的关键时机
4. **JDK版本**：JDK 7+的常量池在堆中，intern行为有变化

理解字符串入池时机，有助于深入掌握JVM类加载、内存模型和性能优化。
