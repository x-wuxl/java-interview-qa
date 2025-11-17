---
layout: post
title: "简述面向对象的六大原则与一条法则"
date: 2025-11-17
description: "全面解析面向对象设计的六大原则（SOLID + 迪米特法则）和一条法则（合成复用原则），包括定义、应用场景及实际代码示例"
author: "wuxl"
categories: [设计模式]
tags: [面向对象, SOLID原则, 设计原则, 迪米特法则, 合成复用, 软件设计]
---

## 问题

简述面向对象的六大原则与一条法则。

## 答案

### 一、六大原则（SOLID + 迪米特法则）

面向对象设计的六大原则是软件设计的基石，帮助我们编写可维护、可扩展、低耦合的代码。

#### 1. 单一职责原则（Single Responsibility Principle, SRP）

**定义**：一个类应该只有一个引起它变化的原因，即一个类只负责一项职责。

**核心思想**：高内聚，低耦合。每个类专注做好一件事。

**反例**：

```java
// ❌ 违反 SRP：一个类承担多个职责
public class User {
    private String name;
    private String email;

    // 职责1：用户数据管理
    public void setName(String name) {
        this.name = name;
    }

    // 职责2：数据持久化
    public void saveToDatabase() {
        // 数据库操作
    }

    // 职责3：邮件发送
    public void sendEmail(String message) {
        // 发送邮件
    }
}
```

**正例**：

```java
// ✅ 符合 SRP：职责分离
public class User {
    private String name;
    private String email;
    // 只负责用户数据
}

public class UserRepository {
    public void save(User user) {
        // 只负责数据持久化
    }
}

public class EmailService {
    public void sendEmail(String email, String message) {
        // 只负责邮件发送
    }
}
```

#### 2. 开闭原则（Open-Closed Principle, OCP）

**定义**：软件实体（类、模块、函数等）应该对扩展开放，对修改关闭。

**核心思想**：通过抽象和多态实现扩展，而不是修改已有代码。

**反例**：

```java
// ❌ 违反 OCP：每次新增类型都要修改代码
public class PaymentService {
    public void pay(String type, double amount) {
        if ("alipay".equals(type)) {
            System.out.println("支付宝支付: " + amount);
        } else if ("wechat".equals(type)) {
            System.out.println("微信支付: " + amount);
        }
        // 新增支付方式需要修改这里
    }
}
```

**正例**：

```java
// ✅ 符合 OCP：通过抽象扩展
public interface Payment {
    void pay(double amount);
}

public class AlipayPayment implements Payment {
    @Override
    public void pay(double amount) {
        System.out.println("支付宝支付: " + amount);
    }
}

public class WechatPayment implements Payment {
    @Override
    public void pay(double amount) {
        System.out.println("微信支付: " + amount);
    }
}

// 新增支付方式只需新增类，无需修改已有代码
public class UnionPayPayment implements Payment {
    @Override
    public void pay(double amount) {
        System.out.println("银联支付: " + amount);
    }
}
```

#### 3. 里氏替换原则（Liskov Substitution Principle, LSP）

**定义**：子类对象必须能够替换掉所有父类对象，且程序行为不变。

**核心思想**：继承必须确保超类所拥有的性质在子类中仍然成立。

**反例**：

```java
// ❌ 违反 LSP：正方形不是矩形的合理子类
public class Rectangle {
    protected int width;
    protected int height;

    public void setWidth(int width) {
        this.width = width;
    }

    public void setHeight(int height) {
        this.height = height;
    }

    public int getArea() {
        return width * height;
    }
}

public class Square extends Rectangle {
    @Override
    public void setWidth(int width) {
        this.width = width;
        this.height = width;  // 破坏了父类的行为
    }

    @Override
    public void setHeight(int height) {
        this.width = height;
        this.height = height;
    }
}

// 测试代码会失败
public void test(Rectangle rect) {
    rect.setWidth(5);
    rect.setHeight(4);
    assert rect.getArea() == 20;  // Square 会失败
}
```

**正例**：

```java
// ✅ 符合 LSP：使用组合而非继承
public interface Shape {
    int getArea();
}

public class Rectangle implements Shape {
    private int width;
    private int height;

    public Rectangle(int width, int height) {
        this.width = width;
        this.height = height;
    }

    @Override
    public int getArea() {
        return width * height;
    }
}

public class Square implements Shape {
    private int side;

    public Square(int side) {
        this.side = side;
    }

    @Override
    public int getArea() {
        return side * side;
    }
}
```

#### 4. 接口隔离原则（Interface Segregation Principle, ISP）

**定义**：客户端不应该依赖它不需要的接口，一个类对另一个类的依赖应该建立在最小的接口上。

**核心思想**：接口要小而专，不要设计臃肿的接口。

**反例**：

```java
// ❌ 违反 ISP：臃肿的接口
public interface Worker {
    void work();
    void eat();
    void sleep();
}

// 机器人不需要 eat 和 sleep
public class Robot implements Worker {
    @Override
    public void work() {
        System.out.println("机器人工作");
    }

    @Override
    public void eat() {
        // 机器人不需要吃饭，但被迫实现
    }

    @Override
    public void sleep() {
        // 机器人不需要睡觉，但被迫实现
    }
}
```

**正例**：

```java
// ✅ 符合 ISP：接口隔离
public interface Workable {
    void work();
}

public interface Eatable {
    void eat();
}

public interface Sleepable {
    void sleep();
}

public class Human implements Workable, Eatable, Sleepable {
    @Override
    public void work() {
        System.out.println("人类工作");
    }

    @Override
    public void eat() {
        System.out.println("人类吃饭");
    }

    @Override
    public void sleep() {
        System.out.println("人类睡觉");
    }
}

public class Robot implements Workable {
    @Override
    public void work() {
        System.out.println("机器人工作");
    }
}
```

#### 5. 依赖倒置原则（Dependency Inversion Principle, DIP）

**定义**：高层模块不应该依赖低层模块，两者都应该依赖抽象；抽象不应该依赖细节，细节应该依赖抽象。

**核心思想**：面向接口编程，而不是面向实现编程。

**反例**：

```java
// ❌ 违反 DIP：高层依赖低层具体实现
public class MySQLDatabase {
    public void save(String data) {
        System.out.println("保存到 MySQL: " + data);
    }
}

public class UserService {
    private MySQLDatabase database = new MySQLDatabase();

    public void saveUser(String user) {
        database.save(user);  // 直接依赖具体实现
    }
}
```

**正例**：

```java
// ✅ 符合 DIP：依赖抽象
public interface Database {
    void save(String data);
}

public class MySQLDatabase implements Database {
    @Override
    public void save(String data) {
        System.out.println("保存到 MySQL: " + data);
    }
}

public class MongoDatabase implements Database {
    @Override
    public void save(String data) {
        System.out.println("保存到 MongoDB: " + data);
    }
}

public class UserService {
    private Database database;

    // 依赖注入
    public UserService(Database database) {
        this.database = database;
    }

    public void saveUser(String user) {
        database.save(user);
    }
}
```

#### 6. 迪米特法则（Law of Demeter, LoD）/ 最少知识原则

**定义**：一个对象应该对其他对象保持最少的了解，只与直接的朋友通信。

**核心思想**：降低类之间的耦合度，减少类之间的依赖关系。

**反例**：

```java
// ❌ 违反迪米特法则：过多了解其他对象的内部结构
public class Customer {
    public Wallet getWallet() {
        return new Wallet();
    }
}

public class Wallet {
    private double money;

    public double getMoney() {
        return money;
    }

    public void setMoney(double money) {
        this.money = money;
    }
}

public class Cashier {
    public void charge(Customer customer, double amount) {
        Wallet wallet = customer.getWallet();
        if (wallet.getMoney() >= amount) {
            wallet.setMoney(wallet.getMoney() - amount);
        }
    }
}
```

**正例**：

```java
// ✅ 符合迪米特法则：只与直接朋友通信
public class Customer {
    private Wallet wallet = new Wallet();

    public boolean pay(double amount) {
        return wallet.deduct(amount);
    }
}

public class Wallet {
    private double money;

    public boolean deduct(double amount) {
        if (money >= amount) {
            money -= amount;
            return true;
        }
        return false;
    }
}

public class Cashier {
    public void charge(Customer customer, double amount) {
        customer.pay(amount);  // 只与 Customer 交互
    }
}
```

### 二、一条法则：合成复用原则（Composite Reuse Principle, CRP）

**定义**：尽量使用对象组合/聚合，而不是继承来达到复用的目的。

**核心思想**：优先使用组合（has-a）而非继承（is-a）。

**反例**：

```java
// ❌ 滥用继承
public class ArrayList {
    // ArrayList 实现
}

public class MyList extends ArrayList {
    // 为了复用 ArrayList 的功能而继承
    public void customMethod() {
        // 自定义方法
    }
}
```

**正例**：

```java
// ✅ 使用组合
public class MyList {
    private List<Object> list = new ArrayList<>();

    public void add(Object obj) {
        list.add(obj);
    }

    public void customMethod() {
        // 自定义方法
    }
}
```

### 三、原则之间的关系

```
单一职责原则 ──┐
开闭原则 ──────┼──→ 高内聚、低耦合
里氏替换原则 ──┤
接口隔离原则 ──┤
依赖倒置原则 ──┤
迪米特法则 ────┘

合成复用原则 ──→ 实现代码复用的最佳方式
```

### 四、实际应用场景

**Spring 框架中的体现**：
- **SRP**：Controller、Service、Repository 各司其职
- **OCP**：通过接口和 AOP 实现扩展
- **LSP**：Bean 的多态替换
- **ISP**：各种细粒度接口（InitializingBean、DisposableBean）
- **DIP**：依赖注入（IoC）
- **LoD**：通过接口隔离实现
- **CRP**：装饰器模式（BeanWrapper）

### 五、面试答题要点

1. **SOLID 五大原则**：单一职责、开闭、里氏替换、接口隔离、依赖倒置
2. **第六原则**：迪米特法则（最少知识原则）
3. **一条法则**：合成复用原则（组合优于继承）
4. **核心目标**：高内聚、低耦合、易扩展、易维护
5. **实际应用**：能结合 Spring、设计模式等框架说明原则的应用
6. **权衡取舍**：原则不是教条，要根据实际情况灵活运用
