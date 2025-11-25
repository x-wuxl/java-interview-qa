---
title: "如何实现对象克隆？"
date: 2025-11-16
description: "深入理解 Java 对象克隆机制，掌握浅克隆与深克隆的实现方式"
author: "wuxl"
categories: [Java基础]
tags: [克隆, Cloneable, 深拷贝, 浅拷贝, 序列化]
nav_order: 9
parent: Java基础
---
## 问题

如何实现对象克隆？

## 答案

### 核心概念

Java 中对象克隆是指创建一个与原对象内容相同但独立的新对象。主要有两种方式：
- **浅克隆（Shallow Clone）**：只复制对象本身和基本类型字段，引用类型字段仍指向原对象
- **深克隆（Deep Clone）**：递归复制对象及其所有引用对象，完全独立

### 实现方式

#### 1. 浅克隆：实现 Cloneable 接口

```java
public class Person implements Cloneable {
    private String name;
    private int age;
    private Address address;  // 引用类型

    @Override
    protected Object clone() throws CloneNotSupportedException {
        return super.clone();  // 调用 Object 的 clone() 方法
    }
}

// 使用示例
Person p1 = new Person("张三", 25, new Address("北京"));
Person p2 = (Person) p1.clone();

// 注意：p1.address 和 p2.address 指向同一个对象
```

**关键点**：
- 必须实现 `Cloneable` 接口（标记接口），否则抛出 `CloneNotSupportedException`
- 重写 `clone()` 方法，调用 `super.clone()`
- 浅克隆只复制对象的直接字段，引用类型字段共享

#### 2. 深克隆：手动递归克隆

```java
public class Person implements Cloneable {
    private String name;
    private int age;
    private Address address;

    @Override
    protected Object clone() throws CloneNotSupportedException {
        Person cloned = (Person) super.clone();
        // 手动克隆引用类型字段
        cloned.address = (Address) this.address.clone();
        return cloned;
    }
}

public class Address implements Cloneable {
    private String city;

    @Override
    protected Object clone() throws CloneNotSupportedException {
        return super.clone();
    }
}
```

#### 3. 深克隆：序列化方式

```java
import java.io.*;

public class Person implements Serializable {
    private String name;
    private int age;
    private Address address;

    // 通过序列化实现深克隆
    public Person deepClone() {
        try {
            // 写入字节流
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            ObjectOutputStream oos = new ObjectOutputStream(bos);
            oos.writeObject(this);

            // 从字节流读取
            ByteArrayInputStream bis = new ByteArrayInputStream(bos.toByteArray());
            ObjectInputStream ois = new ObjectInputStream(bis);
            return (Person) ois.readObject();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
```

**优点**：自动处理所有引用类型，无需手动递归
**缺点**：性能较低，所有类必须实现 `Serializable`

#### 4. 深克隆：使用第三方库

```java
// 使用 Apache Commons Lang
import org.apache.commons.lang3.SerializationUtils;

Person p2 = SerializationUtils.clone(p1);

// 使用 JSON 库（如 Gson、Jackson）
Gson gson = new Gson();
String json = gson.toJson(p1);
Person p2 = gson.fromJson(json, Person.class);
```

### 对比总结

| 方式 | 实现难度 | 性能 | 适用场景 |
|------|---------|------|---------|
| **浅克隆** | 简单 | 高 | 对象无引用类型字段，或引用可共享 |
| **深克隆（手动）** | 中等 | 高 | 引用层级少，需要完全独立的对象 |
| **深克隆（序列化）** | 简单 | 低 | 引用层级复杂，性能要求不高 |
| **第三方库** | 简单 | 中 | 快速开发，依赖外部库 |

### 注意事项

1. **Cloneable 接口的缺陷**
   - 是标记接口，没有定义 `clone()` 方法
   - `clone()` 方法在 `Object` 中是 `protected`，需要手动重写为 `public`
   - 容易出错，建议使用拷贝构造函数或工厂方法

2. **线程安全**
   - `clone()` 方法不是线程安全的，多线程环境需要额外同步

3. **推荐实践**
   - 简单对象：使用拷贝构造函数
   - 复杂对象：使用序列化或第三方库
   - 避免过度使用 `Cloneable`，优先考虑不可变对象设计

### 面试总结

- **浅克隆**：实现 `Cloneable` + 重写 `clone()`，引用类型共享
- **深克隆**：手动递归克隆、序列化、第三方库
- **最佳实践**：优先使用拷贝构造函数或工厂方法，避免 `Cloneable` 的设计缺陷
