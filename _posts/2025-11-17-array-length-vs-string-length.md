---
layout: post
title: "数组是否有 length() 方法？String 是否有 length() 方法？"
date: 2025-11-17
description: "辨析 Java 中数组的 length 属性与 String 的 length() 方法的区别"
author: "wuxl"
categories: [Java基础]
tags: [数组, String, length, 属性与方法]
---

## 问题

数组是否有 length() 方法？String 是否有 length() 方法？

## 答案

### 核心结论

- **数组**：没有 `length()` 方法，只有 `length` **属性**（public final 字段）
- **String**：有 `length()` **方法**

### 详细对比

#### 1. 数组的 length 属性

```java
int[] arr = {1, 2, 3, 4, 5};

// ✅ 正确：使用 length 属性
int size = arr.length;  // 5

// ❌ 错误：数组没有 length() 方法
int size = arr.length();  // 编译错误
```

**关键特性**：
- `length` 是数组对象的 **public final 字段**
- 在数组创建时就确定，之后不可变
- 直接访问，无需方法调用（性能更高）

```java
// 多维数组
int[][] matrix = new int[3][4];
System.out.println(matrix.length);      // 3（行数）
System.out.println(matrix[0].length);   // 4（第一行的列数）
```

#### 2. String 的 length() 方法

```java
String str = "Hello";

// ✅ 正确：使用 length() 方法
int len = str.length();  // 5

// ❌ 错误：String 没有 length 属性
int len = str.length;  // 编译错误
```

**关键特性**：
- `length()` 是 String 类的 **public 方法**
- 返回字符串中字符的个数（char 数组的长度）

```java
// String 的 length() 方法源码（简化版）
public final class String {
    private final char[] value;  // 内部字符数组

    public int length() {
        return value.length;  // 返回内部数组的 length 属性
    }
}
```

### 为什么设计不同？

#### 1. 数组使用属性的原因

- **性能考虑**：数组长度是固定的，直接访问字段比方法调用更快
- **语言设计**：数组是 Java 的内置类型，不是普通类，由 JVM 特殊处理
- **历史原因**：Java 1.0 就这样设计，保持向后兼容

```java
// 字节码层面：访问数组 length 使用 arraylength 指令
int[] arr = new int[10];
int len = arr.length;  // 编译为 arraylength 指令（非方法调用）
```

#### 2. String 使用方法的原因

- **封装性**：String 是普通类，遵循面向对象封装原则
- **灵活性**：方法可以添加额外逻辑（虽然 length() 很简单）
- **一致性**：与其他集合类保持一致（如 List.size()、Map.size()）

### 相关类型对比

| 类型 | 获取长度/大小的方式 | 类型 |
|------|-------------------|------|
| 数组 | `arr.length` | 属性 |
| String | `str.length()` | 方法 |
| StringBuilder | `sb.length()` | 方法 |
| List | `list.size()` | 方法 |
| Set | `set.size()` | 方法 |
| Map | `map.size()` | 方法 |

### 常见陷阱

#### 陷阱 1：混淆数组和 String

```java
String[] strArray = {"a", "b", "c"};

// ✅ 数组长度
int arrayLength = strArray.length;  // 3

// ✅ 数组中第一个字符串的长度
int stringLength = strArray[0].length();  // 1

// ❌ 常见错误
int wrong = strArray.length();  // 编译错误
```

#### 陷阱 2：空数组 vs 空字符串

```java
// 空数组
int[] emptyArray = new int[0];
System.out.println(emptyArray.length);  // 0（不是 null）

// 空字符串
String emptyString = "";
System.out.println(emptyString.length());  // 0（不是 null）

// null 的情况
int[] nullArray = null;
System.out.println(nullArray.length);  // NullPointerException

String nullString = null;
System.out.println(nullString.length());  // NullPointerException
```

#### 陷阱 3：字符串长度与字节长度

```java
String str = "Hello世界";

// 字符数量
System.out.println(str.length());  // 7

// 字节长度（取决于编码）
System.out.println(str.getBytes("UTF-8").length);  // 11
System.out.println(str.getBytes("GBK").length);    // 9

// Unicode 码点数量（考虑代理对）
System.out.println(str.codePointCount(0, str.length()));  // 7
```

### 实际应用示例

```java
// 遍历数组
public void printArray(int[] arr) {
    if (arr == null || arr.length == 0) {  // 使用 length 属性
        System.out.println("空数组");
        return;
    }
    for (int i = 0; i < arr.length; i++) {
        System.out.println(arr[i]);
    }
}

// 验证字符串
public boolean isValidUsername(String username) {
    if (username == null || username.length() == 0) {  // 使用 length() 方法
        return false;
    }
    return username.length() >= 3 && username.length() <= 20;
}

// 更好的空字符串判断
public boolean isEmpty(String str) {
    return str == null || str.isEmpty();  // isEmpty() 内部调用 length() == 0
}
```

### 性能对比

```java
// 数组 length：直接字段访问，极快
int[] arr = new int[1000000];
long start = System.nanoTime();
for (int i = 0; i < 1000000; i++) {
    int len = arr.length;  // 直接访问字段
}
long end = System.nanoTime();

// String length()：方法调用，但 JIT 会内联优化
String str = "x".repeat(1000000);
start = System.nanoTime();
for (int i = 0; i < 1000000; i++) {
    int len = str.length();  // 方法调用，但会被内联
}
end = System.nanoTime();

// 实际性能差异微乎其微（JIT 优化后）
```

### 面试答题要点

1. **数组**：使用 `length` **属性**（不是方法），直接访问字段
2. **String**：使用 `length()` **方法**，符合面向对象封装
3. **设计原因**：
   - 数组是内置类型，length 是 final 字段，性能优先
   - String 是普通类，遵循封装原则
4. **注意区分**：数组用属性，集合类（String、List、Map）用方法
5. **空值处理**：使用前需判空，避免 NullPointerException

### 记忆技巧

- **数组**：`length` 没有括号 → 属性
- **String/集合**：`length()` / `size()` 有括号 → 方法
- **口诀**：数组属性直接访，字符串方法加括号
