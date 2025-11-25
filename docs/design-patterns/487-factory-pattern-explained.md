---
layout: default
title: "什么是工厂模式？"
parent: 设计模式
nav_order: 487
description: "详解工厂模式的三种形态：简单工厂、工厂方法和抽象工厂模式，包括应用场景、实现原理及在Spring框架中的实际应用"
author: "wuxl"
date: 2025-11-02
---
## 问题

什么是工厂模式？

## 答案

### 1. 核心概念

**工厂模式（Factory Pattern）** 是一种创建型设计模式，通过工厂类封装对象的创建逻辑，客户端无需关心对象创建的具体细节，只需调用工厂方法即可获取所需对象。

**核心思想**：将对象的创建与使用分离，降低耦合度。

**典型应用场景**：
- Spring 中的 BeanFactory、FactoryBean
- JDBC 中的 DriverManager
- 日志框架的 LoggerFactory
- 复杂对象创建过程封装

### 2. 三种工厂模式详解

#### 形态1：简单工厂模式（Static Factory）

```java
// 产品接口
interface Product {
    void use();
}

// 具体产品
class ProductA implements Product {
    public void use() {
        System.out.println("使用产品A");
    }
}

class ProductB implements Product {
    public void use() {
        System.out.println("使用产品B");
    }
}

// 简单工厂
class SimpleFactory {
    public static Product createProduct(String type) {
        switch (type) {
            case "A": return new ProductA();
            case "B": return new ProductB();
            default: throw new IllegalArgumentException("未知产品类型");
        }
    }
}

// 使用示例
public class Client {
    public static void main(String[] args) {
        Product product = SimpleFactory.createProduct("A");
        product.use();
    }
}
```

**特点**：
- ✅ 实现简单，一个工厂类负责所有产品创建
- ❌ 违反开闭原则（新增产品需修改工厂类）
- ❌ 工厂类职责过重

#### 形态2：工厂方法模式（Factory Method）

```java
// 产品接口
interface Product {
    void use();
}

// 具体产品
class ProductA implements Product {
    public void use() {
        System.out.println("使用产品A");
    }
}

class ProductB implements Product {
    public void use() {
        System.out.println("使用产品B");
    }
}

// 工厂接口
interface Factory {
    Product createProduct();
}

// 具体工厂
class FactoryA implements Factory {
    public Product createProduct() {
        return new ProductA();
    }
}

class FactoryB implements Factory {
    public Product createProduct() {
        return new ProductB();
    }
}

// 使用示例
public class Client {
    public static void main(String[] args) {
        Factory factory = new FactoryA();
        Product product = factory.createProduct();
        product.use();
    }
}
```

**特点**：
- ✅ 符合开闭原则（新增产品只需新增工厂类）
- ✅ 单一职责（每个工厂类负责一种产品）
- ❌ 类数量增加（每个产品对应一个工厂）

**工厂方法模式 vs 简单工厂**：
- 简单工厂：一个工厂类，静态方法创建所有产品
- 工厂方法：多个工厂类，每个工厂创建一种产品

#### 形态3：抽象工厂模式（Abstract Factory）

```java
// 产品族：按钮和文本框
interface Button {
    void display();
}

interface TextBox {
    void render();
}

// Windows 产品族
class WindowsButton implements Button {
    public void display() {
        System.out.println("Windows 风格按钮");
    }
}

class WindowsTextBox implements TextBox {
    public void render() {
        System.out.println("Windows 风格文本框");
    }
}

// Mac 产品族
class MacButton implements Button {
    public void display() {
        System.out.println("Mac 风格按钮");
    }
}

class MacTextBox implements TextBox {
    public void render() {
        System.out.println("Mac 风格文本框");
    }
}

// 抽象工厂
interface GUIFactory {
    Button createButton();
    TextBox createTextBox();
}

// 具体工厂
class WindowsFactory implements GUIFactory {
    public Button createButton() {
        return new WindowsButton();
    }
    public TextBox createTextBox() {
        return new WindowsTextBox();
    }
}

class MacFactory implements GUIFactory {
    public Button createButton() {
        return new MacButton();
    }
    public TextBox createTextBox() {
        return new MacTextBox();
    }
}

// 使用示例
public class Client {
    public static void main(String[] args) {
        GUIFactory factory = new WindowsFactory();
        Button button = factory.createButton();
        TextBox textBox = factory.createTextBox();

        button.display();
        textBox.render();
    }
}
```

**特点**：
- ✅ 适合创建产品族（一组相关的产品）
- ✅ 确保产品一致性（同一工厂创建的产品风格统一）
- ❌ 扩展困难（新增产品类型需修改所有工厂）

### 3. Spring 中的工厂模式应用

#### BeanFactory

```java
// Spring 的工厂方法模式
ApplicationContext context = new ClassPathXmlApplicationContext("beans.xml");
MyService service = context.getBean("myService", MyService.class);
```

#### FactoryBean

```java
public class MyFactoryBean implements FactoryBean<MyObject> {
    @Override
    public MyObject getObject() throws Exception {
        // 复杂的创建逻辑
        MyObject obj = new MyObject();
        obj.init();
        return obj;
    }

    @Override
    public Class<?> getObjectType() {
        return MyObject.class;
    }

    @Override
    public boolean isSingleton() {
        return true;
    }
}
```

### 4. 三种模式对比

| 模式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **简单工厂** | 产品种类少且固定 | 实现简单 | 违反开闭原则 |
| **工厂方法** | 产品种类可能扩展 | 符合开闭原则 | 类数量增加 |
| **抽象工厂** | 需要创建产品族 | 保证产品一致性 | 扩展产品类型困难 |

### 5. 答题总结

**简洁回答模板**：

"工厂模式是创建型设计模式，将对象创建逻辑封装在工厂类中，降低客户端与具体类的耦合。

主要分为三种：
1. **简单工厂**：一个工厂类通过参数决定创建哪种产品，实现简单但违反开闭原则
2. **工厂方法**：为每种产品定义专门的工厂类，符合开闭原则但类数量增加
3. **抽象工厂**：用于创建产品族（一组相关产品），保证产品风格一致性

Spring 中 BeanFactory 是工厂方法模式的典型应用，FactoryBean 可用于封装复杂的 Bean 创建逻辑。实际开发中根据产品数量和扩展性需求选择合适的工厂模式。"
