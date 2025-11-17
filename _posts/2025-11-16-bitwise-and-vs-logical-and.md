---
layout: post
title: "& 与 && 有何区别？"
date: 2025-11-16
description: "详解 Java 中位运算符 & 与逻辑运算符 && 的区别，包括短路特性和使用场景"
author: "wuxl"
categories: [Java基础]
tags: [运算符, 位运算, 逻辑运算, 短路]
---

## 问题

& 与 && 有何区别？

## 答案

### 一、核心区别

`&` 和 `&&` 在 Java 中有两种不同的用途：

| 运算符 | 类型 | 名称 | 短路特性 | 适用场景 |
|--------|------|------|----------|----------|
| `&` | 位运算符 / 逻辑运算符 | 按位与 / 逻辑与 | **无短路** | 位操作、必须执行所有条件 |
| `&&` | 逻辑运算符 | 短路与 | **有短路** | 布尔逻辑判断 |

---

### 二、作为逻辑运算符的区别

#### 1. 短路特性

**`&&`（短路与）**：
- 如果左侧表达式为 `false`，**不再计算右侧表达式**，直接返回 `false`
- 性能更优，避免不必要的计算

**`&`（非短路与）**：
- **无论左侧结果如何，都会计算右侧表达式**
- 两侧都执行后再返回结果

#### 2. 示例对比

```java
public class LogicalOperatorDemo {
    public static void main(String[] args) {
        int a = 5;
        int b = 0;

        // 使用 && (短路与)
        if (b != 0 && a / b > 2) {  // b != 0 为 false，不执行 a / b
            System.out.println("条件成立");
        }
        System.out.println("&& 执行完毕，未抛出异常");

        // 使用 & (非短路与)
        if (b != 0 & a / b > 2) {  // 即使 b != 0 为 false，仍执行 a / b
            System.out.println("条件成立");
        }
        // 上面会抛出 ArithmeticException: / by zero
    }
}
```

**输出结果**：
```
&& 执行完毕，未抛出异常
Exception in thread "main" java.lang.ArithmeticException: / by zero
```

#### 3. 方法调用的差异

```java
public class ShortCircuitDemo {
    static boolean checkA() {
        System.out.println("checkA() 被调用");
        return false;
    }

    static boolean checkB() {
        System.out.println("checkB() 被调用");
        return true;
    }

    public static void main(String[] args) {
        System.out.println("=== 使用 && ===");
        if (checkA() && checkB()) {
            System.out.println("条件成立");
        }

        System.out.println("\n=== 使用 & ===");
        if (checkA() & checkB()) {
            System.out.println("条件成立");
        }
    }
}
```

**输出结果**：
```
=== 使用 && ===
checkA() 被调用

=== 使用 & ===
checkA() 被调用
checkB() 被调用
```

**分析**：
- `&&`：`checkA()` 返回 `false` 后，`checkB()` 不会被调用
- `&`：两个方法都会被调用

---

### 三、作为位运算符的用法

#### 1. 按位与（&）

对两个整数的每一位进行 **与运算**：
- `1 & 1 = 1`
- `1 & 0 = 0`
- `0 & 0 = 0`

```java
int x = 12;  // 二进制：1100
int y = 10;  // 二进制：1010
int result = x & y;  // 结果：1000 (十进制 8)

System.out.println(result);  // 输出：8
```

**计算过程**：
```
  1100  (12)
& 1010  (10)
-------
  1000  (8)
```

#### 2. 常见应用场景

**（1）判断奇偶性**

```java
// 判断一个数是否为偶数
public static boolean isEven(int num) {
    return (num & 1) == 0;  // 最低位为 0 则为偶数
}
```

**（2）权限控制（位掩码）**

```java
// 定义权限常量
public static final int READ = 1;    // 0001
public static final int WRITE = 2;   // 0010
public static final int EXECUTE = 4; // 0100

// 授予读写权限
int permission = READ | WRITE;  // 0011

// 检查是否有写权限
boolean hasWrite = (permission & WRITE) != 0;  // true

// 检查是否有执行权限
boolean hasExecute = (permission & EXECUTE) != 0;  // false
```

**（3）提取特定位**

```java
// 提取一个整数的低 8 位
int value = 0x12345678;
int lowByte = value & 0xFF;  // 结果：0x78 (120)
```

---

### 四、使用建议

#### 1. 逻辑判断场景

```java
// ✅ 推荐：使用 && (性能更好，避免空指针)
if (obj != null && obj.getValue() > 10) {
    // ...
}

// ❌ 不推荐：使用 & (可能抛出 NullPointerException)
if (obj != null & obj.getValue() > 10) {
    // 如果 obj 为 null，仍会执行 obj.getValue()
}
```

#### 2. 必须执行所有条件的场景

```java
// 需要执行所有验证方法（即使前面失败）
if (validateInput() & checkPermission() & logAccess()) {
    // 三个方法都会被调用，即使第一个返回 false
}
```

#### 3. 位运算场景

```java
// 位操作只能使用 &
int flags = 0b1010;
int mask = 0b0011;
int result = flags & mask;  // 按位与
```

---

### 五、性能对比

| 场景 | `&` | `&&` |
|------|-----|------|
| 简单布尔判断 | 两侧都计算 | 可能只计算左侧 |
| 包含方法调用 | 所有方法都执行 | 可能跳过部分方法 |
| 位运算 | 正常执行 | 不适用 |

**结论**：在逻辑判断中，`&&` 通常性能更优且更安全。

---

### 六、相关运算符

| 运算符 | 名称 | 短路特性 |
|--------|------|----------|
| `&` | 按位与 / 逻辑与 | 无 |
| `&&` | 短路与 | 有 |
| `|` | 按位或 / 逻辑或 | 无 |
| `||` | 短路或 | 有 |
| `^` | 按位异或 / 逻辑异或 | 无 |
| `~` | 按位取反 | - |

**短路或示例**：
```java
// || 短路：左侧为 true 时，不计算右侧
if (user.isAdmin() || user.hasPermission("write")) {
    // 如果是管理员，不再检查权限
}

// | 非短路：两侧都会计算
if (user.isAdmin() | user.hasPermission("write")) {
    // 两个方法都会被调用
}
```

---

### 七、面试要点总结

1. **逻辑运算**：
   - `&&` 有短路特性，左侧为 `false` 时不计算右侧
   - `&` 无短路特性，两侧都会计算

2. **位运算**：
   - `&` 可用于按位与操作
   - `&&` 不能用于位运算

3. **使用场景**：
   - 逻辑判断优先使用 `&&`（性能好、避免空指针）
   - 需要执行所有条件时使用 `&`
   - 位操作只能使用 `&`

4. **典型陷阱**：
   ```java
   // 错误示例：可能导致空指针异常
   if (str != null & str.length() > 0) { }

   // 正确示例：使用短路与
   if (str != null && str.length() > 0) { }
   ```

**记忆口诀**：双 `&` 短路快，单 `&` 全执行；逻辑用双 `&`，位运算单 `&`。
