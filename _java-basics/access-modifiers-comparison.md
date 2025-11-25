---
title: "public、private、protected 以及 default 访问修饰符有何区别？"
date: 2025-11-17
description: "全面解析 Java 四种访问修饰符的作用范围与使用场景"
author: "wuxl"
categories: [Java基础]
tags: [访问修饰符, 封装, 面向对象]
nav_order: 42
parent: Java基础
---
## 问题

public、private、protected 以及 default 访问修饰符有何区别？

## 答案

### 核心概念

Java 提供了四种访问修饰符来控制类、方法、变量的可见性，从严格到宽松依次为：

**private < default（包访问权限）< protected < public**

这是面向对象**封装特性**的重要体现，用于控制代码的访问边界。

### 四种修饰符的访问范围

| 修饰符 | 同一类内 | 同一包内 | 不同包的子类 | 不同包的非子类 |
|--------|---------|---------|-------------|---------------|
| **private** | ✅ | ❌ | ❌ | ❌ |
| **default**（无修饰符） | ✅ | ✅ | ❌ | ❌ |
| **protected** | ✅ | ✅ | ✅ | ❌ |
| **public** | ✅ | ✅ | ✅ | ✅ |

### 详细说明

#### 1. private（私有）

- **访问范围**：仅限于**当前类内部**
- **使用场景**：
  - 隐藏实现细节，保护敏感数据
  - 工具方法、内部状态变量
- **典型用法**：成员变量通常声明为 `private`，通过 getter/setter 访问

```java
public class BankAccount {
    private double balance;  // 私有字段，外部无法直接访问

    public double getBalance() {
        return balance;
    }

    public void deposit(double amount) {
        if (amount > 0) {
            balance += amount;
        }
    }

    private void internalAudit() {
        // 私有方法，仅供类内部使用
        System.out.println("执行内部审计...");
    }
}
```

#### 2. default（包访问权限）

- **访问范围**：**同一包内**的所有类可访问
- **特点**：不写任何修饰符时的默认级别
- **使用场景**：
  - 包内协作的工具类
  - 不希望对外暴露的包级实现

```java
package com.example.util;

class PackageHelper {  // 默认访问权限，仅包内可见
    void processData() {
        // 包内其他类可以调用
    }
}

public class PublicService {
    void helperMethod() {  // 默认访问权限
        // 同包内可访问，包外不可见
    }
}
```

#### 3. protected（受保护）

- **访问范围**：
  - **同一包内**的所有类
  - **不同包的子类**（通过继承访问）
- **使用场景**：
  - 父类希望子类能访问或重写的方法
  - 模板方法模式中的钩子方法

```java
package com.example.base;

public class Animal {
    protected void eat() {  // 子类可访问
        System.out.println("动物进食");
    }

    protected String species;  // 子类可访问的字段
}

// 不同包的子类
package com.example.impl;
import com.example.base.Animal;

public class Dog extends Animal {
    public void feed() {
        eat();  // 可以访问父类的 protected 方法
        species = "犬科";  // 可以访问父类的 protected 字段
    }
}
```

**注意**：`protected` 成员在子类中的访问有限制：
- 子类可以访问**继承来的** `protected` 成员
- 但不能通过父类引用访问其他对象的 `protected` 成员（除非在同一包内）

```java
public class Dog extends Animal {
    public void test() {
        this.eat();  // ✅ 访问继承的 protected 方法

        Dog otherDog = new Dog();
        otherDog.eat();  // ✅ 同类对象可以访问

        Animal animal = new Animal();
        animal.eat();  // ❌ 编译错误（不同包且非继承关系）
    }
}
```

#### 4. public（公开）

- **访问范围**：**所有类**都可以访问
- **使用场景**：
  - 对外提供的 API 接口
  - 公共服务类、工具类
- **限制**：一个 `.java` 文件中只能有一个 `public` 类，且类名必须与文件名一致

```java
public class UserService {  // 公开类，任何地方都可以访问
    public void register(String username) {
        // 公开方法，对外提供服务
    }
}
```

### 类的访问修饰符

**顶层类**（非内部类）只能使用两种修饰符：

1. **public**：对所有包可见
2. **default**（无修饰符）：仅对同一包可见

```java
// 文件：UserService.java
public class UserService {  // public 类
    // ...
}

class InternalHelper {  // default 类，仅包内可见
    // ...
}
```

**内部类**可以使用所有四种修饰符。

### 实际开发建议

1. **最小权限原则**：默认使用 `private`，根据需要逐步放宽
2. **成员变量**：通常声明为 `private`，通过 getter/setter 访问
3. **工具方法**：内部使用的方法声明为 `private`
4. **继承体系**：父类希望子类访问的方法用 `protected`
5. **API 接口**：对外提供的服务用 `public`

### 常见误区

1. **protected 不是"比 default 更严格"**：`protected` 的访问范围实际上**更宽**（包含同包 + 子类）
2. **子类访问 protected 的限制**：不能随意访问父类对象的 `protected` 成员，只能访问继承来的
3. **default 不是关键字**：包访问权限是"不写修饰符"的默认行为，不需要写 `default` 关键字

### 面试答题要点

1. **按范围排序**：private < default < protected < public
2. **用表格说明**：清晰展示四种修饰符在不同场景下的可见性
3. **举例说明**：private 用于封装，protected 用于继承，public 用于 API
4. **关联原则**：体现封装性和最小权限原则
5. **注意细节**：顶层类只能用 public 或 default，protected 在子类中的访问限制

这道题考察对 Java 访问控制机制的理解，是面向对象封装特性的基础知识。
