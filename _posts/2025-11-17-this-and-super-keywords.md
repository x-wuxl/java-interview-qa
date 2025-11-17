---
layout: post
title: "this 和 super 关键字的作用是什么？"
date: 2025-11-17
description: "全面解析 Java 中 this 和 super 关键字的用法、区别及应用场景"
author: "wuxl"
categories: [Java基础]
tags: [this, super, 继承, 关键字, 构造方法]
---

## 问题

this 和 super 关键字的作用是什么？

## 答案

### 核心概念

- **this**：代表**当前对象**的引用，指向调用该方法的对象实例
- **super**：代表**父类对象**的引用，用于访问父类的成员和构造方法

### this 关键字的三大用法

#### 1. 访问当前对象的成员变量

用于区分**成员变量**和**局部变量**（特别是参数名相同时）：

```java
public class User {
    private String name;
    private int age;

    public User(String name, int age) {
        // this.name 是成员变量，name 是参数
        this.name = name;  // 将参数赋值给成员变量
        this.age = age;
    }

    public void setName(String name) {
        this.name = name;  // 区分成员变量和参数
    }

    public void printInfo() {
        // 访问当前对象的成员变量（this 可省略）
        System.out.println("姓名：" + this.name);
        System.out.println("年龄：" + age);  // 等价于 this.age
    }
}
```

#### 2. 调用当前对象的其他方法

```java
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int addAndPrint(int a, int b) {
        int result = this.add(a, b);  // 调用当前对象的 add 方法
        System.out.println("结果：" + result);
        return result;
    }

    public void process() {
        this.addAndPrint(10, 20);  // this 可省略
        addAndPrint(30, 40);       // 等价写法
    }
}
```

#### 3. 调用当前类的其他构造方法（构造器重载）

```java
public class Student {
    private String name;
    private int age;
    private String school;

    // 构造方法 1
    public Student() {
        this("未知", 0);  // 调用构造方法 2
    }

    // 构造方法 2
    public Student(String name, int age) {
        this(name, age, "默认学校");  // 调用构造方法 3
    }

    // 构造方法 3
    public Student(String name, int age, String school) {
        this.name = name;
        this.age = age;
        this.school = school;
    }
}

// 使用示例
Student s1 = new Student();                    // 调用构造方法 1
Student s2 = new Student("张三", 20);          // 调用构造方法 2
Student s3 = new Student("李四", 22, "清华");  // 调用构造方法 3
```

**重要规则**：
- `this()` 必须是构造方法的**第一条语句**
- 不能同时调用 `this()` 和 `super()`（都要求第一条语句）
- 避免构造方法之间的循环调用

### super 关键字的三大用法

#### 1. 访问父类的成员变量

当子类和父类有**同名变量**时，用 super 访问父类的变量：

```java
class Parent {
    protected String name = "父类";
}

class Child extends Parent {
    private String name = "子类";

    public void printNames() {
        System.out.println("子类 name：" + this.name);   // 输出：子类
        System.out.println("父类 name：" + super.name);  // 输出：父类
    }
}
```

#### 2. 调用父类的方法

当子类**重写**了父类方法，但仍需调用父类的原始实现时：

```java
class Animal {
    public void eat() {
        System.out.println("动物在吃东西");
    }
}

class Dog extends Animal {
    @Override
    public void eat() {
        super.eat();  // 先调用父类的 eat 方法
        System.out.println("狗在吃骨头");  // 再执行子类的逻辑
    }
}

// 输出：
// 动物在吃东西
// 狗在吃骨头
```

**实际应用场景**：

```java
class BaseService {
    public void save(Object obj) {
        System.out.println("执行通用保存逻辑");
        // 数据校验、日志记录等
    }
}

class UserService extends BaseService {
    @Override
    public void save(Object obj) {
        super.save(obj);  // 复用父类的通用逻辑
        System.out.println("执行用户特定的保存逻辑");
        // 用户相关的特殊处理
    }
}
```

#### 3. 调用父类的构造方法

子类构造方法中**必须调用父类构造方法**（显式或隐式）：

```java
class Person {
    private String name;
    private int age;

    public Person(String name, int age) {
        this.name = name;
        this.age = age;
    }
}

class Employee extends Person {
    private String company;

    public Employee(String name, int age, String company) {
        super(name, age);  // 显式调用父类构造方法
        this.company = company;
    }
}
```

**重要规则**：
- `super()` 必须是构造方法的**第一条语句**
- 如果不显式调用 `super()`，编译器会自动插入 `super()`（调用父类无参构造）
- 如果父类没有无参构造，子类必须显式调用父类的有参构造

```java
class Parent {
    // 没有无参构造方法
    public Parent(String name) {
        System.out.println("父类构造：" + name);
    }
}

class Child extends Parent {
    public Child() {
        // ❌ 编译错误：父类没有无参构造
        // 编译器无法自动插入 super()
    }

    public Child(String name) {
        super(name);  // ✅ 必须显式调用父类有参构造
    }
}
```

### this 和 super 的对比

| 特性 | this | super |
|------|------|-------|
| **指向** | 当前对象 | 父类对象 |
| **访问变量** | 当前类的成员变量 | 父类的成员变量 |
| **调用方法** | 当前类的方法 | 父类的方法 |
| **调用构造** | 当前类的其他构造方法 | 父类的构造方法 |
| **使用位置** | 构造方法第一行（调用构造时） | 构造方法第一行（调用构造时） |
| **能否共存** | 不能同时使用 `this()` 和 `super()` | 不能同时使用 `this()` 和 `super()` |

### 综合示例

```java
class Vehicle {
    protected String brand;

    public Vehicle(String brand) {
        this.brand = brand;
        System.out.println("Vehicle 构造方法");
    }

    public void start() {
        System.out.println(brand + " 启动");
    }
}

class Car extends Vehicle {
    private String model;

    // 构造方法 1
    public Car(String brand, String model) {
        super(brand);  // 调用父类构造方法
        this.model = model;
        System.out.println("Car 构造方法");
    }

    // 构造方法 2
    public Car(String brand) {
        this(brand, "默认型号");  // 调用当前类的其他构造方法
    }

    @Override
    public void start() {
        super.start();  // 调用父类的 start 方法
        System.out.println(this.model + " 型号启动");  // 访问当前对象的成员
    }

    public void showInfo() {
        System.out.println("品牌：" + super.brand);  // 访问父类变量
        System.out.println("型号：" + this.model);   // 访问当前类变量
    }
}

// 测试
public class Test {
    public static void main(String[] args) {
        Car car = new Car("特斯拉", "Model 3");
        car.start();
        car.showInfo();
    }
}

// 输出：
// Vehicle 构造方法
// Car 构造方法
// 特斯拉 启动
// Model 3 型号启动
// 品牌：特斯拉
// 型号：Model 3
```

### 常见陷阱

#### 陷阱 1：构造方法调用顺序错误

```java
class Parent {
    public Parent(String name) {
        System.out.println("父类构造");
    }
}

class Child extends Parent {
    public Child() {
        System.out.println("子类逻辑");  // ❌ 错误：super() 必须是第一条语句
        super("test");
    }
}
```

#### 陷阱 2：静态方法中使用 this/super

```java
public class Example {
    public static void staticMethod() {
        // ❌ 错误：静态方法中不能使用 this 或 super
        this.instanceMethod();  // 编译错误
        super.parentMethod();   // 编译错误
    }
}
```

#### 陷阱 3：构造方法循环调用

```java
public class BadExample {
    public BadExample() {
        this(10);  // 调用构造方法 2
    }

    public BadExample(int x) {
        this();  // ❌ 错误：循环调用，导致栈溢出
    }
}
```

### 实际应用场景

#### 场景 1：Builder 模式

```java
public class User {
    private String name;
    private int age;
    private String email;

    private User(Builder builder) {
        this.name = builder.name;
        this.age = builder.age;
        this.email = builder.email;
    }

    public static class Builder {
        private String name;
        private int age;
        private String email;

        public Builder name(String name) {
            this.name = name;
            return this;  // 返回当前对象，支持链式调用
        }

        public Builder age(int age) {
            this.age = age;
            return this;
        }

        public Builder email(String email) {
            this.email = email;
            return this;
        }

        public User build() {
            return new User(this);
        }
    }
}

// 使用
User user = new User.Builder()
    .name("张三")
    .age(25)
    .email("zhangsan@example.com")
    .build();
```

#### 场景 2：模板方法模式

```java
abstract class AbstractProcessor {
    // 模板方法
    public final void process() {
        preProcess();
        doProcess();
        postProcess();
    }

    protected void preProcess() {
        System.out.println("通用前置处理");
    }

    protected abstract void doProcess();

    protected void postProcess() {
        System.out.println("通用后置处理");
    }
}

class ConcreteProcessor extends AbstractProcessor {
    @Override
    protected void doProcess() {
        super.preProcess();  // 可选：调用父类方法
        System.out.println("具体业务处理");
    }
}
```

### 面试答题要点

1. **this 的作用**：
   - 引用当前对象
   - 区分成员变量和局部变量
   - 调用当前类的其他构造方法（`this()`）

2. **super 的作用**：
   - 引用父类对象
   - 访问父类被隐藏的成员变量
   - 调用父类被重写的方法
   - 调用父类构造方法（`super()`）

3. **关键规则**：
   - `this()` 和 `super()` 必须是构造方法的第一条语句
   - 不能同时使用 `this()` 和 `super()`
   - 静态方法中不能使用 this 和 super

4. **实际应用**：
   - 构造方法重载（this）
   - 继承中复用父类逻辑（super）
   - Builder 模式（this）
   - 模板方法模式（super）

### 记忆技巧

- **this**：我自己（当前对象）
- **super**：我爸爸（父类对象）
- **构造调用**：必须第一个打招呼（第一条语句）
- **不能同时**：不能同时叫自己和爸爸（只能选一个）
