---
layout: default
title: "重载与重写的区别是什么？"
parent: Java基础
nav_order: 49
description: "深入理解 Java 中方法重载（Overload）与方法重写（Override）的本质区别与应用场景"
author: "wuxl"
date: 2025-11-16
---
## 问题

重载与重写的区别是什么？

## 答案

### 核心概念

- **重载（Overload）**：同一个类中，方法名相同但**参数列表不同**的多个方法
  - 发生在**编译期**（静态多态）
  - 体现了**同一操作的多种实现方式**

- **重写（Override）**：子类重新定义父类中**相同签名**的方法
  - 发生在**运行期**（动态多态）
  - 体现了**子类对父类行为的定制**

### 1. 方法重载（Overload）

#### 基本规则

```java
public class Calculator {
    // 方法名相同，参数列表不同

    // 1. 参数个数不同
    public int add(int a, int b) {
        return a + b;
    }

    public int add(int a, int b, int c) {
        return a + b + c;
    }

    // 2. 参数类型不同
    public double add(double a, double b) {
        return a + b;
    }

    // 3. 参数顺序不同
    public void print(String str, int num) {
        System.out.println(str + num);
    }

    public void print(int num, String str) {
        System.out.println(num + str);
    }
}
```

#### 重载的判定条件

| 条件 | 是否影响重载 | 说明 |
|------|------------|------|
| **方法名** | 必须相同 | 重载的前提 |
| **参数列表** | 必须不同 | 个数、类型或顺序至少一项不同 |
| **返回值类型** | 不影响 | 仅返回值不同不构成重载 |
| **访问修饰符** | 不影响 | public/private 不影响重载 |
| **异常声明** | 不影响 | throws 子句不影响重载 |

#### 错误示例

```java
public class ErrorDemo {
    // 编译错误：仅返回值不同，不构成重载
    public int getValue() { return 1; }
    public double getValue() { return 1.0; }  // 编译错误

    // 编译错误：仅访问修饰符不同，不构成重载
    public void show()
    private void show() {}  // 编译错误
}
```

#### 典型应用场景

```java
// 1. 构造方法重载
public class User {
    private String name;
    private int age;

    public User() {}

    public User(String name) {
        this.name = name;
    }

    public User(String name, int age) {
        this.name = name;
        this.age = age;
    }
}

// 2. 可变参数与重载
public class VarargsDemo {
    public void print(String... args) {
        System.out.println("可变参数");
    }

    public void print(String arg) {
        System.out.println("单个参数");  // 优先匹配精确类型
    }

    public static void main(String[] args) {
        VarargsDemo demo = new VarargsDemo();
        demo.print("test");  // 调用 print(String)
    }
}
```

### 2. 方法重写（Override）

#### 基本规则

```java
public class Animal {
    public void makeSound() {
        System.out.println("动物发出声音");
    }

    public void eat(String food) {
        System.out.println("动物吃" + food);
    }
}

public class Dog extends Animal {
    // 重写父类方法
    @Override
    public void makeSound() {
        System.out.println("汪汪汪");
    }

    @Override
    public void eat(String food) {
        System.out.println("狗狗吃" + food);
    }
}
```

#### 重写的约束条件

| 条件 | 要求 | 说明 |
|------|------|------|
| **方法名** | 必须相同 | 完全一致 |
| **参数列表** | 必须相同 | 类型、个数、顺序完全一致 |
| **返回值类型** | 相同或子类型 | 协变返回类型（Java 5+） |
| **访问修饰符** | 不能更严格 | public → public/protected，不能 public → private |
| **异常声明** | 不能更宽泛 | 只能抛出父类方法异常的子类或更少异常 |
| **static/final/private** | 不能重写 | 这些方法不参与多态 |

#### 协变返回类型

```java
public class Parent {
    public Number getValue() {
        return 1;
    }
}

public class Child extends Parent {
    // 返回值类型可以是父类返回值的子类
    @Override
    public Integer getValue() {  // Integer 是 Number 的子类
        return 100;
    }
}
```

#### 访问修饰符规则

```java
public class Base {
    protected void show() {}
}

public class Derived extends Base {
    // 正确：访问权限可以扩大
    @Override
    public void show() {}

    // 错误：访问权限不能缩小
    // @Override
    // private void show() {}  // 编译错误
}
```

#### 异常声明规则

```java
public class Parent {
    public void method() throws IOException {
        // ...
    }
}

public class Child extends Parent {
    // 正确：可以不抛异常
    @Override
    public void method() {
        // ...
    }

    // 正确：可以抛出子类异常
    @Override
    public void method() throws FileNotFoundException {  // IOException 的子类
        // ...
    }

    // 错误：不能抛出更宽泛的异常
    // @Override
    // public void method() throws Exception {  // 编译错误
    //     // ...
    // }
}
```

#### 不能重写的方法

```java
public class Parent {
    // 1. final 方法不能重写
    public final void finalMethod() {}

    // 2. static 方法不能重写（但可以隐藏）
    public static void staticMethod() {}

    // 3. private 方法不能重写（子类不可见）
    private void privateMethod() {}
}

public class Child extends Parent {
    // 这不是重写，而是定义新方法（方法隐藏）
    public static void staticMethod() {}
}
```

### 3. 重载 vs 重写对比

| 特性 | 重载（Overload） | 重写（Override） |
|------|-----------------|-----------------|
| **英文名称** | Overload | Override |
| **发生范围** | 同一个类 | 父类与子类之间 |
| **方法名** | 必须相同 | 必须相同 |
| **参数列表** | 必须不同 | 必须相同 |
| **返回值类型** | 无要求 | 相同或子类型 |
| **访问修饰符** | 无要求 | 不能更严格 |
| **异常声明** | 无要求 | 不能更宽泛 |
| **绑定时机** | 编译期（静态绑定） | 运行期（动态绑定） |
| **多态类型** | 编译时多态 | 运行时多态 |
| **@Override 注解** | 不适用 | 推荐使用 |

### 4. 多态的体现

```java
public class PolymorphismDemo {
    public static void main(String[] args) {
        // 重写体现运行时多态
        Animal animal = new Dog();
        animal.makeSound();  // 输出：汪汪汪（运行时决定调用 Dog 的方法）

        // 重载体现编译时多态
        Calculator calc = new Calculator();
        calc.add(1, 2);       // 调用 add(int, int)
        calc.add(1.0, 2.0);   // 调用 add(double, double)
    }
}
```

### 5. 实际应用场景

#### 重载的应用

```java
// 1. 提供多种调用方式
public class StringUtils {
    public static boolean isEmpty(String str) {
        return str == null || str.length() == 0;
    }

    public static boolean isEmpty(String str, boolean trim) {
        return trim ? isEmpty(str.trim()) : isEmpty(str);
    }
}

// 2. 类型转换的便利性
public class DataConverter {
    public String convert(int value) {
        return String.valueOf(value);
    }

    public String convert(double value) {
        return String.valueOf(value);
    }

    public String convert(Object obj) {
        return obj.toString();
    }
}
```

#### 重写的应用

```java
// 1. 模板方法模式
public abstract class AbstractProcessor {
    public final void process() {
        preProcess();
        doProcess();  // 子类重写
        postProcess();
    }

    protected abstract void doProcess();

    protected void preProcess() {}
    protected void postProcess() {}
}

// 2. 策略模式
public interface PaymentStrategy {
    void pay(double amount);
}

public class AlipayStrategy implements PaymentStrategy {
    @Override
    public void pay(double amount) {
        System.out.println("支付宝支付：" + amount);
    }
}

public class WechatStrategy implements PaymentStrategy {
    @Override
    public void pay(double amount) {
        System.out.println("微信支付：" + amount);
    }
}
```

### 答题总结

**面试要点**：
- **重载**：同一类中方法名相同、参数不同，编译期决定调用哪个方法（静态多态）
- **重写**：子类重新定义父类方法，运行期根据对象实际类型决定调用哪个方法（动态多态）
- **记忆口诀**：
  - 重载看参数，编译期决定
  - 重写看对象，运行期决定
- **最佳实践**：
  - 重写方法必须加 `@Override` 注解，避免拼写错误
  - 重载方法参数差异要明显，避免调用歧义
  - 重写时遵守里氏替换原则，子类行为应符合父类契约
