---
layout: post
title: "所有异常的共同祖先是什么？常见的运行时异常有哪些？"
date: 2025-11-17
description: "深入理解 Java 异常体系结构及常见运行时异常类型"
author: "wuxl"
categories: [Java基础]
tags: [异常处理, Exception, RuntimeException]
---

## 问题

所有异常的共同祖先是什么？常见的运行时异常有哪些？

## 答案

### 核心结论

1. **所有异常的共同祖先是 `Throwable` 类**
2. **常见的运行时异常**包括：`NullPointerException`、`ArrayIndexOutOfBoundsException`、`ClassCastException`、`IllegalArgumentException`、`NumberFormatException` 等

### Java 异常体系结构

```
Throwable (所有异常的根类)
├── Error (错误，程序无法处理)
│   ├── OutOfMemoryError
│   ├── StackOverflowError
│   ├── NoClassDefFoundError
│   └── ...
└── Exception (异常，程序可以处理)
    ├── IOException (受检异常)
    ├── SQLException (受检异常)
    ├── ClassNotFoundException (受检异常)
    └── RuntimeException (运行时异常/非受检异常)
        ├── NullPointerException
        ├── ArrayIndexOutOfBoundsException
        ├── ClassCastException
        ├── IllegalArgumentException
        │   └── NumberFormatException
        ├── ArithmeticException
        ├── IllegalStateException
        └── ...
```

### Throwable 类的关键方法

```java
public class Throwable {
    // 获取异常消息
    public String getMessage();

    // 获取详细消息（包含异常类型）
    public String toString();

    // 打印堆栈跟踪信息
    public void printStackTrace();

    // 获取堆栈跟踪元素数组
    public StackTraceElement[] getStackTrace();

    // 获取异常原因
    public Throwable getCause();
}
```

### 常见运行时异常详解

#### 1. NullPointerException（空指针异常）

**触发场景**：对 null 对象调用方法或访问属性

```java
String str = null;
int length = str.length();  // NullPointerException

List<String> list = null;
list.add("item");  // NullPointerException
```

#### 2. ArrayIndexOutOfBoundsException（数组越界异常）

**触发场景**：访问数组时索引超出范围

```java
int[] arr = {1, 2, 3};
int value = arr[5];  // ArrayIndexOutOfBoundsException

// 负数索引也会抛出
int value2 = arr[-1];  // ArrayIndexOutOfBoundsException
```

#### 3. ClassCastException（类型转换异常）

**触发场景**：强制类型转换失败

```java
Object obj = "Hello";
Integer num = (Integer) obj;  // ClassCastException

List<String> list = new ArrayList<>();
List<Integer> intList = (List<Integer>) (Object) list;  // 运行时可能出错
```

#### 4. IllegalArgumentException（非法参数异常）

**触发场景**：方法接收到不合法的参数

```java
Thread thread = new Thread();
thread.setPriority(100);  // IllegalArgumentException (优先级范围 1-10)

// 自定义方法中主动抛出
public void setAge(int age) {
    if (age < 0 || age > 150) {
        throw new IllegalArgumentException("年龄必须在 0-150 之间");
    }
}
```

#### 5. NumberFormatException（数字格式异常）

**触发场景**：字符串转数字时格式不正确（继承自 `IllegalArgumentException`）

```java
int num1 = Integer.parseInt("abc");  // NumberFormatException
int num2 = Integer.parseInt("12.5");  // NumberFormatException
double d = Double.parseDouble("3.14.15");  // NumberFormatException
```

#### 6. ArithmeticException（算术异常）

**触发场景**：算术运算错误，如除零

```java
int result = 10 / 0;  // ArithmeticException: / by zero

// 注意：浮点数除零不会抛异常
double d = 10.0 / 0;  // 结果是 Infinity，不抛异常
```

#### 7. IllegalStateException（非法状态异常）

**触发场景**：对象状态不正确时调用方法

```java
Iterator<String> iterator = list.iterator();
iterator.remove();  // IllegalStateException (必须先调用 next())

// 线程状态错误
Thread thread = new Thread();
thread.start();
thread.start();  // IllegalThreadStateException (线程已启动)
```

#### 8. IndexOutOfBoundsException（索引越界异常）

**触发场景**：集合索引超出范围

```java
List<String> list = new ArrayList<>();
list.add("A");
String item = list.get(5);  // IndexOutOfBoundsException

String str = "Hello";
char ch = str.charAt(10);  // StringIndexOutOfBoundsException
```

#### 9. UnsupportedOperationException（不支持的操作异常）

**触发场景**：调用对象不支持的方法

```java
List<String> list = Arrays.asList("A", "B", "C");
list.add("D");  // UnsupportedOperationException (Arrays.asList 返回的是不可变列表)

List<String> unmodifiableList = Collections.unmodifiableList(new ArrayList<>());
unmodifiableList.add("item");  // UnsupportedOperationException
```

#### 10. ConcurrentModificationException（并发修改异常）

**触发场景**：迭代集合时直接修改集合结构

```java
List<String> list = new ArrayList<>(Arrays.asList("A", "B", "C"));
for (String item : list) {
    if ("B".equals(item)) {
        list.remove(item);  // ConcurrentModificationException
    }
}

// 正确做法：使用迭代器的 remove 方法
Iterator<String> iterator = list.iterator();
while (iterator.hasNext()) {
    String item = iterator.next();
    if ("B".equals(item)) {
        iterator.remove();  // 正确
    }
}
```

### 完整示例代码

```java
public class CommonRuntimeExceptions {
    public static void main(String[] args) {
        // 1. NullPointerException
        try {
            String str = null;
            str.length();
        } catch (NullPointerException e) {
            System.out.println("捕获到空指针异常: " + e.getMessage());
        }

        // 2. ArrayIndexOutOfBoundsException
        try {
            int[] arr = {1, 2, 3};
            int value = arr[5];
        } catch (ArrayIndexOutOfBoundsException e) {
            System.out.println("捕获到数组越界异常: " + e.getMessage());
        }

        // 3. ClassCastException
        try {
            Object obj = "Hello";
            Integer num = (Integer) obj;
        } catch (ClassCastException e) {
            System.out.println("捕获到类型转换异常: " + e.getMessage());
        }

        // 4. NumberFormatException
        try {
            int num = Integer.parseInt("abc");
        } catch (NumberFormatException e) {
            System.out.println("捕获到数字格式异常: " + e.getMessage());
        }

        // 5. ArithmeticException
        try {
            int result = 10 / 0;
        } catch (ArithmeticException e) {
            System.out.println("捕获到算术异常: " + e.getMessage());
        }
    }
}
```

### Error vs Exception vs RuntimeException

| 类型 | 是否需要捕获 | 是否可恢复 | 典型场景 |
|------|------------|-----------|---------|
| **Error** | 否 | 否 | JVM 错误、内存溢出、栈溢出 |
| **受检异常** (Exception) | **是** | 是 | IO 异常、SQL 异常、网络异常 |
| **运行时异常** (RuntimeException) | 否 | 是 | 空指针、数组越界、类型转换 |

### 面试要点总结

1. **异常体系根类**：
   - `Throwable` 是所有异常和错误的父类
   - 有两个直接子类：`Error` 和 `Exception`

2. **运行时异常特点**：
   - 继承自 `RuntimeException`
   - **不需要强制捕获**（非受检异常）
   - 通常是编程错误导致，应该通过���码逻辑避免

3. **常见运行时异常记忆口诀**：
   - **空指针**（NullPointerException）
   - **越界**（IndexOutOfBoundsException、ArrayIndexOutOfBoundsException）
   - **类型转换**（ClassCastException）
   - **非法参数**（IllegalArgumentException、NumberFormatException）
   - **算术错误**（ArithmeticException）
   - **非法状态**（IllegalStateException）

4. **最佳实践**：
   - 运行时异常应该通过**预防性编程**避免（如空值检查）
   - 不要过度使用 `try-catch` 捕获运行时异常
   - 使用 `Objects.requireNonNull()` 等工具类进行参数校验

```java
// 推荐的防御性编程
public void process(String input) {
    Objects.requireNonNull(input, "输入不能为 null");
    if (input.isEmpty()) {
        throw new IllegalArgumentException("输入不能为空");
    }
    // 业务逻辑
}
```

这道题考察的是对 Java 异常体系的整体理解和常见异常的识别能力，是面试中的高频基础题。
