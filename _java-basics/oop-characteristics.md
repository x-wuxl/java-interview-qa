---
title: "面向对象有哪些特征？"
date: 2025-11-16
description: "全面解析面向对象编程的四大核心特征：封装、继承、多态和抽象，以及在 Java 中的实现方式"
author: "wuxl"
categories: [Java基础]
tags: [面向对象, 封装, 继承, 多态, 抽象]
nav_order: 1
parent: Java基础
---
## 问题

面向对象有哪些特征？

## 答案

### 一、核心概念

面向对象编程（OOP）有 **四大核心特征**：**封装（Encapsulation）**、**继承（Inheritance）**、**多态（Polymorphism）** 和 **抽象（Abstraction）**。这些特征共同构成了面向对象设计的基础。

---

### 二、封装（Encapsulation）

#### 定义
将对象的状态（属性）和行为（方法）封装在一起，隐藏内部实现细节，只对外暴露必要的接口。

#### 实现方式
- 使用 `private` 修饰属性，防止外部直接访问
- 提供 `public` 的 getter/setter 方法控制访问
- 通过访问控制符（private、protected、public）限制访问权限

#### 示例代码

```java
public class BankAccount {
    // 私有属性，外部无法直接访问
    private String accountNumber;
    private double balance;

    // 构造方法
    public BankAccount(String accountNumber, double initialBalance) {
        this.accountNumber = accountNumber;
        this.balance = initialBalance;
    }

    // 公开方法，提供受控访问
    public void deposit(double amount) {
        if (amount > 0) {
            balance += amount;
        }
    }

    public boolean withdraw(double amount) {
        if (amount > 0 && balance >= amount) {
            balance -= amount;
            return true;
        }
        return false;
    }

    // 只读访问
    public double getBalance() {
        return balance;
    }
}
```

#### 优势
- **数据安全**：防止非法修改
- **灵活性**：内部实现可随时修改，不影响外部调用
- **可维护性**：降低模块间耦合

---

### 三、继承（Inheritance）

#### 定义
子类可以继承父类的属性和方法，实现代码复用和层次化设计。Java 使用 `extends` 关键字实现继承。

#### 关键特性
- Java 只支持 **单继承**（一个类只能继承一个父类）
- 支持 **多层继承**（A → B → C）
- 子类可以重写（Override）父类方法
- 使用 `super` 关键字访问父类成员

#### 示例代码

```java
// 父类
public class Animal {
    protected String name;

    public Animal(String name) {
        this.name = name;
    }

    public void eat() {
        System.out.println(name + " is eating");
    }
}

// 子类继承父类
public class Dog extends Animal {
    private String breed;

    public Dog(String name, String breed) {
        super(name);  // 调用父类构造方法
        this.breed = breed;
    }

    // 重写父类方法
    @Override
    public void eat() {
        System.out.println(name + " (a " + breed + ") is eating dog food");
    }

    // 子类特有方法
    public void bark() {
        System.out.println(name + " is barking");
    }
}
```

#### 优势
- **代码复用**：避免重复编写相同代码
- **扩展性**：在不修改原有代码的基础上扩展功能
- **层次结构**：建立清晰的类关系

---

### 四、多态（Polymorphism）

#### 定义
同一个方法调用，在不同对象上产生不同的行为。多态是面向对象最强大的特性之一。

#### 实现方式
1. **编译时多态（静态多态）**：方法重载（Overload）
2. **运行时多态（动态多态）**：方法重写（Override）+ 父类引用指向子类对象

#### 示例代码

```java
// 父类引用指向子类对象
Animal animal1 = new Dog("Buddy", "Golden Retriever");
Animal animal2 = new Cat("Whiskers", "Persian");

// 运行时根据实际对象类型调用对应方法
animal1.eat();  // 输出：Buddy (a Golden Retriever) is eating dog food
animal2.eat();  // 输出：Whiskers (a Persian) is eating cat food

// 多态在集合中的应用
List<Animal> animals = new ArrayList<>();
animals.add(new Dog("Max", "Labrador"));
animals.add(new Cat("Luna", "Siamese"));

for (Animal animal : animals) {
    animal.eat();  // 根据实际类型调用不同实现
}
```

#### 实现条件
1. 必须有继承关系
2. 子类必须重写父类方法
3. 父类引用指向子类对象

#### 优势
- **灵活性**：同一接口，多种实现
- **可扩展性**：新增子类无需修改现有代码
- **解耦**：面向接口编程，降低依赖

---

### 五、抽象（Abstraction）

#### 定义
隐藏复杂的实现细节，只暴露必要的功能接口。抽象关注"做什么"而非"怎么做"。

#### 实现方式
1. **抽象类（abstract class）**：可以包含抽象方法和具体方法
2. **接口（interface）**：只定义方法签名，不包含实现（Java 8+ 支持默认方法）

#### 示例代码

```java
// 抽象类
public abstract class Shape {
    protected String color;

    public Shape(String color) {
        this.color = color;
    }

    // 抽象方法：子类必须实现
    public abstract double calculateArea();

    // 具体方法：子类可直接使用
    public void displayColor() {
        System.out.println("Color: " + color);
    }
}

// 具体实现类
public class Circle extends Shape {
    private double radius;

    public Circle(String color, double radius) {
        super(color);
        this.radius = radius;
    }

    @Override
    public double calculateArea() {
        return Math.PI * radius * radius;
    }
}

// 接口
public interface Drawable {
    void draw();  // 抽象方法

    // Java 8+ 默认方法
    default void display() {
        System.out.println("Displaying shape");
    }
}

// 实现接口
public class Rectangle extends Shape implements Drawable {
    private double width;
    private double height;

    public Rectangle(String color, double width, double height) {
        super(color);
        this.width = width;
        this.height = height;
    }

    @Override
    public double calculateArea() {
        return width * height;
    }

    @Override
    public void draw() {
        System.out.println("Drawing a rectangle");
    }
}
```

#### 抽象类 vs 接口

| 特性 | 抽象类 | 接口 |
|------|--------|------|
| 继承/实现 | 单继承（extends） | 多实现（implements） |
| 方法类型 | 抽象 + 具体方法 | 抽象方法（Java 8+ 支持 default/static） |
| 成员变量 | 可以有实例变量 | 只能有常量（public static final） |
| 构造方法 | 可以有 | 不能有 |
| 使用场景 | 有共同实现逻辑 | 定义行为规范 |

#### 优势
- **简化复杂性**：隐藏实现细节
- **提高可维护性**：修改实现不影响接口
- **强制规范**：确保子类实现必要方法

---

### 六、四大特征的关系

```
封装：保护数据，提供接口
  ↓
继承：复用代码，建立层次
  ↓
多态：灵活调用，动态绑定
  ↓
抽象：定义规范，隐藏细节
```

这四个特征相辅相成：
- **封装** 是基础，保证数据安全
- **继承** 实现代码复用和扩展
- **多态** 提供灵活性和可扩展性
- **抽象** 定义规范和接口

---

### 七、面试要点总结

1. **封装**：通过访问控制符隐藏实现，提供 getter/setter
2. **继承**：extends 关键字，单继承，支持方法重写
3. **多态**：父类引用指向子类对象，运行时动态绑定
4. **抽象**：抽象类（abstract）和接口（interface），定义规范

**典型面试追问**：
- 多态的实现原理？（虚方法表、动态绑定）
- 抽象类和接口的区别？（见上表）
- 重载和重写的区别？（编译时 vs 运行时多态）
