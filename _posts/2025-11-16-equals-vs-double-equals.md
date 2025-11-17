---
layout: post
title: "equals 与 == 有何区别？"
date: 2025-11-16
description: "深入理解 Java 中 equals 方法与 == 运算符的本质区别，包括值比较与引用比较的差异"
author: "wuxl"
categories: [Java基础]
tags: [equals, ==, 对象比较, 引用类型]
---

## 问题

equals 与 == 有何区别？

## 答案

### 核心概念

- **`==`**：比较运算符，用于比较两个变量的**值**是否相等
  - 对于**基本数据类型**：比较的是**值**本身
  - 对于**引用类型**：比较的是**内存地址**（引用是否指向同一个对象）

- **`equals()`**：Object 类的方法，用于比较两个对象的**内容**是否相等
  - 默认实现（Object 类）：等同于 `==`，比较引用地址
  - 重写后（如 String、Integer 等）：比较对象的**实际内容**

### 原理与关键点

#### 1. `==` 的行为

```java
// 基本类型：比较值
int a = 100;
int b = 100;
System.out.println(a == b);  // true

// 引用类型：比较内存地址
String s1 = new String("hello");
String s2 = new String("hello");
System.out.println(s1 == s2);  // false（不同对象，地址不同）

String s3 = "hello";
String s4 = "hello";
System.out.println(s3 == s4);  // true（字符串常量池，同一对象）
```

#### 2. `equals()` 的默认实现

Object 类的 equals 方法源码：

```java
public boolean equals(Object obj) {
    return (this == obj);  // 默认比较引用地址
}
```

#### 3. 重写 equals 的典型实现

以 String 类为例：

```java
public boolean equals(Object anObject) {
    if (this == anObject) {
        return true;  // 同一对象，直接返回 true
    }
    if (anObject instanceof String) {
        String anotherString = (String)anObject;
        int n = value.length;
        if (n == anotherString.value.length) {
            char v1[] = value;
            char v2[] = anotherString.value;
            int i = 0;
            while (n-- != 0) {
                if (v1[i] != v2[i])  // 逐字符比较内容
                    return false;
                i++;
            }
            return true;
        }
    }
    return false;
}
```

### 重写 equals 的注意事项

重写 equals 方法时，必须遵守以下约定：

1. **自反性**：`x.equals(x)` 必须返回 true
2. **对称性**：`x.equals(y)` 为 true，则 `y.equals(x)` 也为 true
3. **传递性**：`x.equals(y)` 和 `y.equals(z)` 为 true，则 `x.equals(z)` 也为 true
4. **一致性**：多次调用结果一致（对象未修改的情况下）
5. **非空性**：`x.equals(null)` 必须返回 false

**重要规则**：重写 equals 时，必须同时重写 hashCode 方法，以保证：
```
如果 a.equals(b) 为 true，则 a.hashCode() == b.hashCode()
```

### 实际应用示例

```java
public class User {
    private String name;
    private int age;

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;

        User user = (User) obj;
        return age == user.age &&
               Objects.equals(name, user.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(name, age);
    }
}

// 使用示例
User u1 = new User("张三", 25);
User u2 = new User("张三", 25);

System.out.println(u1 == u2);       // false（不同对象）
System.out.println(u1.equals(u2));  // true（内容相同）
```

### 答题总结

| 比较方式 | 基本类型 | 引用类型（未重写equals） | 引用类型（已重写equals） |
|---------|---------|----------------------|---------------------|
| `==`    | 比较值   | 比较内存地址           | 比较内存地址          |
| `equals()` | 不适用 | 比较内存地址（默认行为） | 比较对象内容          |

**面试要点**：
- `==` 是运算符，equals 是方法
- 基本类型只能用 `==`，引用类型推荐用 equals 比较内容
- String、Integer 等包装类已重写 equals，比较的是值
- 自定义类需要重写 equals 和 hashCode 以支持内容比较
- 重写 equals 必须遵守自反性、对称性、传递性、一致性、非空性五大原则
