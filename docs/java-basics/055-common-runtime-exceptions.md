---
layout: default
title: "请列出 5 个常见的运行时异常"
parent: Java基础
nav_order: 55
description: "详解 Java 中最常见的 5 个运行时异常及其产生原因和避免方法"
author: "wuxl"
date: 2025-11-16
---
## 问题

请列出 5 个常见的运行时异常。

## 答案

### 核心概念

**运行时异常（RuntimeException）** 是 `Unchecked Exception`（非受检异常），编译器不强制要求捕获或声明。通常由程序逻辑错误引起，可以通过代码优化避免。

### 5 个最常见的运行时异常

#### 1. NullPointerException（空指针异常）

**产生原因**：对 `null` 对象调用方法或访问属性

```java
String str = null;
int length = str.length();  // 抛出 NullPointerException
```

**避免方法**：
- 使用前进行 `null` 检查
- 使用 `Optional` 类（Java 8+）
- 使用 `Objects.requireNonNull()`

```java
// 方法 1：null 检查
if (str != null) {
    int length = str.length();
}

// 方法 2：Optional
Optional.ofNullable(str).ifPresent(s -> System.out.println(s.length()));

// 方法 3：Objects 工具类
Objects.requireNonNull(str, "str 不能为 null");
```

#### 2. ArrayIndexOutOfBoundsException（数组越界异常）

**产生原因**：访问数组时索引超出范围（`index < 0` 或 `index >= length`）

```java
int[] arr = {1, 2, 3};
int value = arr[5];  // 抛出 ArrayIndexOutOfBoundsException
```

**避免方法**：
- 访问前检查索引范围
- 使用增强 for 循环（for-each）
- 使用集合类（如 `ArrayList`）并调用 `get()` 前检查 `size()`

```java
// 方法 1：范围检查
if (index >= 0 && index < arr.length) {
    int value = arr[index];
}

// 方法 2：for-each
for (int num : arr) {
    System.out.println(num);
}
```

#### 3. ClassCastException（类型转换异常）

**产生原因**：将对象强制转换为不兼容的类型

```java
Object obj = "Hello";
Integer num = (Integer) obj;  // 抛出 ClassCastException
```

**避免方法**：
- 使用 `instanceof` 检查类型
- 使用泛型避免类型转换
- 使用多态设计

```java
// 方法 1：instanceof 检查
if (obj instanceof Integer) {
    Integer num = (Integer) obj;
}

// 方法 2：泛型
List<String> list = new ArrayList<>();  // 编译时类型安全
```

#### 4. NumberFormatException（数字格式异常）

**产生原因**：将字符串转换为数字时，字符串格式不正确

```java
String str = "abc";
int num = Integer.parseInt(str);  // 抛出 NumberFormatException
```

**避免方法**：
- 使用 `try-catch` 捕获异常
- 使用正则表达式预先验证
- 使用 Apache Commons Lang 的 `NumberUtils.isCreatable()`

```java
// 方法 1：try-catch
try {
    int num = Integer.parseInt(str);
} catch (NumberFormatException e) {
    System.out.println("无效的数字格式");
}

// 方法 2：正则验证
if (str.matches("-?\\d+")) {
    int num = Integer.parseInt(str);
}

// 方法 3：Apache Commons Lang
if (NumberUtils.isCreatable(str)) {
    int num = Integer.parseInt(str);
}
```

#### 5. IllegalArgumentException（非法参数异常）

**产生原因**：方法接收到不合法的参数

```java
public void setAge(int age) {
    if (age < 0 || age > 150) {
        throw new IllegalArgumentException("年龄必须在 0-150 之间");
    }
    this.age = age;
}

setAge(-5);  // 抛出 IllegalArgumentException
```

**避免方法**：
- 在方法入口进行参数校验
- 使用 `Objects.requireNonNull()` 检查 null
- 使用 Bean Validation（JSR-303）注解

```java
// 方法 1：手动校验
public void setAge(int age) {
    if (age < 0 || age > 150) {
        throw new IllegalArgumentException("年龄必须在 0-150 之间");
    }
    this.age = age;
}

// 方法 2：Bean Validation
public class Person {
    @Min(0)
    @Max(150)
    private int age;
}
```

### 其他常见运行时异常

| 异常 | 产生原因 | 示例 |
|------|---------|------|
| **ArithmeticException** | 算术运算异常（如除零） | `int result = 10 / 0;` |
| **IndexOutOfBoundsException** | 索引越界（集合） | `list.get(100);` |
| **ConcurrentModificationException** | 并发修改异常 | 遍历集合时删除元素 |
| **UnsupportedOperationException** | 不支持的操作 | 对不可修改集合调用 `add()` |
| **IllegalStateException** | 非法状态异常 | 在错误的时机调用方法 |

### 运行时异常 vs 受检异常

| 特性 | 运行时异常（RuntimeException） | 受检异常（Checked Exception） |
|------|------------------------------|------------------------------|
| **继承关系** | 继承自 `RuntimeException` | 继承自 `Exception`（但不是 `RuntimeException`） |
| **编译器检查** | 不强制捕获或声明 | 必须捕获或声明（`throws`） |
| **产生原因** | 程序逻辑错误 | 外部因素（如 IO、网络） |
| **典型示例** | `NullPointerException`、`ArrayIndexOutOfBoundsException` | `IOException`、`SQLException` |
| **处理建议** | 通过代码优化避免 | 必须显式处理 |

### 最佳实践

1. **预防优于捕获**：通过参数校验、null 检查等避免异常发生
2. **不要滥用异常**：异常处理有性能开销，不应用于正常流程控制
3. **提供有意义的异常信息**：抛出异常时附带详细的错误描述
4. **日志记录**：捕获异常后记录日志，便于排查问题

```java
// 良好的异常处理示例
public User getUserById(Long id) {
    if (id == null || id <= 0) {
        throw new IllegalArgumentException("用户 ID 必须为正整数");
    }

    User user = userRepository.findById(id);
    if (user == null) {
        throw new IllegalArgumentException("用户不存在：" + id);
    }

    return user;
}
```

### 面试总结

**5 个最常见的运行时异常**：
1. **NullPointerException**：空指针异常
2. **ArrayIndexOutOfBoundsException**：数组越界异常
3. **ClassCastException**：类型转换异常
4. **NumberFormatException**：数字格式异常
5. **IllegalArgumentException**：非法参数异常

**关键点**：
- 运行时异常是 `Unchecked Exception`，编译器不强制处理
- 通常由程序逻辑错误引起，应通过代码优化避免
- 预防优于捕获，做好参数校验和边界检查
