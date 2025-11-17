---
layout: post
title: "抽象工厂模式与工厂方法模式有何区别？"
date: 2025-11-17
description: "深入对比抽象工厂模式与工厂方法模式的核心区别，包括定义、使用场景、结构差异及实际应用示例"
author: "wuxl"
categories: [设计模式]
tags: [设计模式, 工厂模式, 抽象工厂, 工厂方法, 创建型模式]
---

## 问题

抽象工厂模式与工厂方法模式有何区别？

## 答案

### 一、核心概念

**工厂方法模式（Factory Method）**：定义一个创建对象的接口，让子类决定实例化哪个类。工厂方法将对象的实例化延迟到子类。

**抽象工厂模式（Abstract Factory）**：提供一个创建一系列相关或相互依赖对象的接口，而无需指定它们具体的类。

### 二、关键区别

| 维度 | 工厂方法模式 | 抽象工厂模式 |
|------|------------|------------|
| **产品层级** | 针对单一产品等级结构 | 针对多个产品等级结构 |
| **抽象程度** | 一个抽象产品类 | 多个抽象产品类 |
| **工厂职责** | 创建一种产品 | 创建一系列相关产品 |
| **扩展方式** | 增加新产品需要新增工厂子类 | 增加新产品族需要修改所有工厂 |
| **使用场景** | 产品种类单一但实现多样 | 产品成套出现，需要保证兼容性 |

### 三、工厂方法模式示例

```java
// 抽象产品
interface Product {
    void use();
}

// 具体产品
class ConcreteProductA implements Product {
    @Override
    public void use() {
        System.out.println("使用产品A");
    }
}

class ConcreteProductB implements Product {
    @Override
    public void use() {
        System.out.println("使用产品B");
    }
}

// 抽象工厂
abstract class Factory {
    public abstract Product createProduct();
}

// 具体工厂
class FactoryA extends Factory {
    @Override
    public Product createProduct() {
        return new ConcreteProductA();
    }
}

class FactoryB extends Factory {
    @Override
    public Product createProduct() {
        return new ConcreteProductB();
    }
}

// 使用
Factory factory = new FactoryA();
Product product = factory.createProduct();
product.use();
```

### 四、抽象工厂模式示例

```java
// 抽象产品族：按钮和文本框
interface Button {
    void display();
}

interface TextField {
    void render();
}

// Windows 风格产品
class WindowsButton implements Button {
    @Override
    public void display() {
        System.out.println("显示 Windows 风格按钮");
    }
}

class WindowsTextField implements TextField {
    @Override
    public void render() {
        System.out.println("渲染 Windows 风格文本框");
    }
}

// Mac 风格产品
class MacButton implements Button {
    @Override
    public void display() {
        System.out.println("显示 Mac 风格按钮");
    }
}

class MacTextField implements TextField {
    @Override
    public void render() {
        System.out.println("渲染 Mac 风格文本框");
    }
}

// 抽象工厂
interface GUIFactory {
    Button createButton();
    TextField createTextField();
}

// 具体工厂
class WindowsFactory implements GUIFactory {
    @Override
    public Button createButton() {
        return new WindowsButton();
    }

    @Override
    public TextField createTextField() {
        return new WindowsTextField();
    }
}

class MacFactory implements GUIFactory {
    @Override
    public Button createButton() {
        return new MacButton();
    }

    @Override
    public TextField createTextField() {
        return new MacTextField();
    }
}

// 使用
GUIFactory factory = new WindowsFactory();
Button button = factory.createButton();
TextField textField = factory.createTextField();
button.display();
textField.render();
```

### 五、实际应用场景

**工厂方法模式**：
- JDBC 中的 `Connection` 创建（不同数据库驱动提供不同实现）
- Spring 的 `FactoryBean` 接口
- 日志框架中不同级别日志对象的创建

**抽象工厂模式**：
- 跨平台 UI 组件库（Windows/Mac/Linux 风格）
- 数据库访问层（MySQL/Oracle/PostgreSQL 的 Connection、Statement、ResultSet）
- 游戏开发中的场景工厂（不同关卡的敌人、道具、地图组合）

### 六、选择建议

**使用工厂方法模式**：
- 只需要创建一种类型的产品
- 产品的创建逻辑较为复杂，需要封装
- 需要灵活扩展产品种类

**使用抽象工厂模式**：
- 需要创建一系列相关的产品对象
- 产品之间存在约束关系（如 UI 风格统一）
- 系统需要在多个产品族中切换

### 七、面试答题要点

1. **核心区别**：工厂方法针对单一产品，抽象工厂针对产品族
2. **结构差异**：工厂方法一个工厂方法创建一个产品；抽象工厂多个工厂方法创建多个相关产品
3. **扩展性**：工厂方法符合开闭原则，易于扩展新产品；抽象工厂增加新产品需要修改接口
4. **实际应用**：能举出 Spring、JDBC 等框架中的实际例子
