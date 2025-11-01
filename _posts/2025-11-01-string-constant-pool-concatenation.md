---
layout: post
title: "String a = \"ab\"; String b = \"a\" + \"b\"; a==b吗？"
date: 2025-11-01
description: "深入分析Java字符串常量池、编译期优化、字符串拼接的底层机制及==与equals的区别"
author: "wuxl"
categories: [Java基础]
tags: [String, 字符串常量池, 编译器优化, 字节码, equals]
---

## 问题

String a = "ab"; String b = "a" + "b"; a==b吗？

## 答案

### 1. 直接答案

**答案：true**

```java
String a = "ab";
String b = "a" + "b";
System.out.println(a == b);  // true
```

### 2. 原理分析

#### 编译期常量折叠优化

Java编译器会对**字面量的字符串拼接**进行**编译期优化**（常量折叠）：

```java
// 源代码
String b = "a" + "b";

// 编译后的字节码等价于
String b = "ab";
```

**验证方式：查看字节码**
```bash
javac StringTest.java
javap -c StringTest.class
```

**字节码输出：**
```java
0: ldc           #2  // String ab
2: astore_1
3: ldc           #2  // String ab  <- 注意：同一个常量池索引#2
5: astore_2
```

**关键点：**
- `"a" + "b"`在编译期被优化为`"ab"`
- 两个变量都指向常量池中**同一个**String对象（索引#2）
- 因此`a == b`返回`true`

#### 字符串常量池机制

```java
String a = "ab";  // ① 在常量池中创建"ab"（如果不存在）
String b = "ab";  // ② 直接从常量池获取引用

System.out.println(a == b);  // true - 指向同一对象
```

**内存结构：**
```
字符串常量池（堆中，JDK 7+）：
  +-----------+
  | "ab"      | <--- a
  +-----------+      b
```

### 3. 对比：不同场景的拼接

#### 场景1：字面量 + 字面量（编译期优化）

```java
String s1 = "a" + "b";
String s2 = "ab";
System.out.println(s1 == s2);  // true
```

**原因：**编译期常量折叠，等价于`String s1 = "ab";`

#### 场景2：变量 + 字面量（运行期拼接）

```java
String a = "a";
String s1 = a + "b";  // 运行期拼接
String s2 = "ab";
System.out.println(s1 == s2);  // false
```

**原因：**涉及变量，无法编译期优化，运行时创建新对象

**字节码：**
```java
// JDK 8及之前：使用StringBuilder
new StringBuilder().append(a).append("b").toString()

// JDK 9+：使用invokedynamic + StringConcatFactory
invokedynamic makeConcatWithConstants
```

#### 场景3：final变量 + 字面量（编译期优化）

```java
final String a = "a";  // final关键字
String s1 = a + "b";
String s2 = "ab";
System.out.println(s1 == s2);  // true
```

**原因：**`final`修饰的变量是常量，编译器能确定其值，进行常量折叠

#### 场景4：方法返回值 + 字面量（运行期拼接）

```java
String s1 = getA() + "b";  // 运行期拼接
String s2 = "ab";
System.out.println(s1 == s2);  // false

private static String getA() {
    return "a";
}
```

**原因：**方法返回值在编译期不确定，无法优化

### 4. 编译期 vs 运行期拼接对比

| 拼接方式 | 编译期优化 | 结果 | 示例 |
|---------|----------|------|------|
| 字面量 + 字面量 | ✅ 是 | 常量池 | `"a" + "b"` |
| final常量 + 字面量 | ✅ 是 | 常量池 | `final String a="a"; a+"b"` |
| 变量 + 字面量 | ❌ 否 | 堆中新对象 | `String a="a"; a+"b"` |
| 方法返回值 + 字面量 | ❌ 否 | 堆中新对象 | `getA() + "b"` |

### 5. `==` vs `equals`

```java
String s1 = "ab";
String s2 = "a" + "b";
String s3 = new String("a") + new String("b");

// == 比较引用地址
System.out.println(s1 == s2);  // true  - 同一对象
System.out.println(s1 == s3);  // false - 不同对象

// equals比较内容
System.out.println(s1.equals(s2));  // true
System.out.println(s1.equals(s3));  // true
```

**关键区别：**
- `==`：比较对象引用（内存地址）
- `equals()`：比较对象内容（String重写了equals方法）

### 6. 字节码详细分析

#### 源代码

```java
public class StringTest {
    public static void main(String[] args) {
        String a = "ab";
        String b = "a" + "b";
        System.out.println(a == b);
    }
}
```

#### 编译后的字节码

```bash
javap -v StringTest.class
```

**Constant Pool（常量池）：**
```
#2 = String             #16  // ab
#16 = Utf8              ab
```

**main方法字节码：**
```
 0: ldc           #2   // String ab  <- 加载"ab"常量
 2: astore_1           // 存入变量a
 3: ldc           #2   // String ab  <- 再次加载同一个"ab"常量
 5: astore_2           // 存入变量b
 6: getstatic     #3   // Field java/lang/System.out
 9: aload_1            // 加载a
10: aload_2            // 加载b
11: if_acmpne     18   // 比较引用，相同跳到18
14: iconst_1           // 压入true
15: goto          19
18: iconst_0           // 压入false
19: invokevirtual #4   // 调用println
```

**关键点：**
- 偏移量0和3处都使用`ldc #2`，加载的是**同一个常量池索引**
- 证明了编译器优化的存在

### 7. 进阶题目

#### 题目1：多级拼接

```java
String s1 = "a" + "b" + "c";
String s2 = "abc";
System.out.println(s1 == s2);  // true
```

**原因：**编译器优化为`"abc"`

#### 题目2：混合拼接

```java
String a = "a";
String s1 = a + "b" + "c";  // 运行期拼接
String s2 = "abc";
System.out.println(s1 == s2);  // false
```

**原因：**包含变量，无法编译期优化

#### 题目3：intern方法

```java
String a = "a";
String s1 = (a + "b").intern();  // 手动放入常量池
String s2 = "ab";
System.out.println(s1 == s2);  // true
```

**原因：**`intern()`将拼接结果放入常量池

#### 题目4：三元表达式

```java
String s1 = "a" + (true ? "b" : "c");
String s2 = "ab";
System.out.println(s1 == s2);  // true（某些编译器优化）
```

**注意：**依赖编译器优化能力，不保证所有版本都优化

### 8. 常见误区

#### 误区1：以为所有拼接都创建新对象

```java
String s = "a" + "b" + "c";  // 误以为创建多个中间对象
// 实际：编译期优化为 String s = "abc";
```

#### 误区2：以为final只影响可修改性

```java
final String a = "a";
String s = a + "b";  // final使变量成为编译期常量
// 实际：编译器能识别final，进行常量折叠
```

#### 误区3：以为`==`总是不可靠

```java
// 对于字符串字面量，==是可靠的
String s1 = "hello";
String s2 = "hello";
System.out.println(s1 == s2);  // true，且推荐用于性能敏感场景
```

### 9. 最佳实践

#### 字符串比较推荐方式

```java
// ✅ 推荐：使用equals比较内容
String s1 = "hello";
String s2 = getStringFromSomewhere();
if (s1.equals(s2)) {
    // ...
}

// ✅ 防御性编程：常量在前，防止NullPointerException
if ("SUCCESS".equals(status)) {
    // ...
}

// ⚠️ 特殊场景：常量池引用比较（性能优化）
String status = statusFromDB.intern();
if (status == STATUS_SUCCESS) {  // STATUS_SUCCESS是常量
    // 直接比较引用，性能更高
}
```

#### 字符串拼接推荐方式

```java
// ✅ 字面量拼接：直接用+
String welcome = "Hello" + " " + "World";  // 编译器优化

// ✅ 循环拼接：使用StringBuilder
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 100; i++) {
    sb.append(i);
}
String result = sb.toString();

// ❌ 避免：循环中使用+
String result = "";
for (int i = 0; i < 100; i++) {
    result += i;  // 每次循环创建新StringBuilder
}
```

### 10. 面试答题要点

**标准回答结构：**

1. **直接答案**：`a == b`结果为`true`
2. **核心原因**：编译器对字面量拼接进行**常量折叠优化**，`"a" + "b"`被优化为`"ab"`
3. **字节码证明**：两个变量都引用常量池中同一个对象（相同索引）
4. **对比说明**：如果涉及变量（非final），则无法编译期优化，会创建新对象
5. **最佳实践**：字符串比较应使用`equals()`，`==`仅用于引用比较

**加分点：**
- 能画出内存结构图（常量池 vs 堆）
- 说明编译期优化和运行期拼接的区别
- 了解`final`关键字对常量折叠的影响
- 知道JDK 9+的字符串拼接优化（invokedynamic）
- 能举一反三，对比不同场景的拼接行为

### 11. 总结

**核心知识点：**

| 概念 | 说明 |
|------|------|
| **常量折叠** | 编译器优化，将字面量表达式在编译期计算 |
| **字符串常量池** | JVM中存储字符串字面量的特殊区域，避免重复 |
| **==比较** | 比较引用地址，常量池中的字符串引用相同 |
| **equals比较** | 比较内容，推荐使用 |
| **final常量** | 可参与编译期优化，等同于字面量 |

**记忆口诀：**
- 字面量拼字面量，编译期就优化
- 变量拼字面量，运行期新对象
- final修饰变量，当成字面量看
- 字符串比较，equals更安全

这道题考察的是对**Java编译器优化、字符串常量池、内存模型**的综合理解，是String相关的经典面试题。
