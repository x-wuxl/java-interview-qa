---
title: "什么是深拷贝和浅拷贝？"
date: 2025-11-01
description: "深入剖析Java中深拷贝与浅拷贝的概念、实现方式、Cloneable接口、序列化拷贝及实际应用场景"
author: "wuxl"
categories: [Java基础]
tags: [深拷贝, 浅拷贝, clone, 序列化, 对象拷贝]
nav_order: 8
parent: Java基础
---
## 问题

什么是深拷贝和浅拷贝？

## 答案

### 1. 核心概念

**浅拷贝（Shallow Copy）**：
- 创建一个新对象，新对象的字段值是原对象字段的**精确拷贝**
- 基本类型字段：拷贝值
- 引用类型字段：拷贝引用（指向同一对象）

**深拷贝（Deep Copy）**：
- 创建一个新对象，递归拷贝所有引用对象
- 基本类型字段：拷贝值
- 引用类型字段：创建新对象并拷贝内容（完全独立）

**关键区别：**引用类型字段是否指向同一对象

### 2. 图解对比

#### 浅拷贝示意图

```
原对象:
  ┌─────────────┐
  │ Person      │
  │ name: "Tom" │
  │ age: 25     │
  │ address: ───┼───┐
  └─────────────┘   │
                    ↓
               ┌─────────┐
               │ Address │
               │ city    │
               └─────────┘
                    ↑
  ┌─────────────┐   │
  │ Person拷贝  │   │
  │ name: "Tom" │   │
  │ age: 25     │   │
  │ address: ───┼───┘
  └─────────────┘

说明：两个Person对象共享同一个Address对象
```

#### 深拷贝示意图

```
原对象:
  ┌─────────────┐
  │ Person      │
  │ name: "Tom" │
  │ age: 25     │
  │ address: ───┼───→ ┌─────────┐
  └─────────────┘      │ Address │
                       │ city    │
                       └─────────┘

拷贝对象:
  ┌─────────────┐
  │ Person拷贝  │
  │ name: "Tom" │
  │ age: 25     │
  │ address: ───┼───→ ┌─────────┐
  └─────────────┘      │ Address │
                       │ city    │
                       └─────────┘

说明：两个Person对象各有独立的Address对象
```

### 3. 浅拷贝实现

#### 方式1：Object.clone()方法

```java
public class Person implements Cloneable {
    private String name;
    private int age;
    private Address address;  // 引用类型

    @Override
    protected Object clone() throws CloneNotSupportedException {
        return super.clone();  // 默认浅拷贝
    }
}

class Address {
    private String city;
    private String street;

    // getters and setters
}
```

**测试：**
```java
Person p1 = new Person("Tom", 25, new Address("Beijing", "Street1"));
Person p2 = (Person) p1.clone();

// 修改p2的address
p2.getAddress().setCity("Shanghai");

System.out.println(p1.getAddress().getCity());  // Shanghai（受影响！）
System.out.println(p2.getAddress().getCity());  // Shanghai
System.out.println(p1.getAddress() == p2.getAddress());  // true（同一对象）
```

**问题：**修改拷贝对象的引用字段会影响原对象！

#### 方式2：拷贝构造函数（浅拷贝）

```java
public class Person {
    private String name;
    private int age;
    private Address address;

    // 拷贝构造函数（浅拷贝）
    public Person(Person other) {
        this.name = other.name;
        this.age = other.age;
        this.address = other.address;  // 直接赋值引用（浅拷贝）
    }
}
```

### 4. 深拷贝实现

#### 方式1：重写clone()方法

```java
public class Person implements Cloneable {
    private String name;
    private int age;
    private Address address;

    @Override
    protected Object clone() throws CloneNotSupportedException {
        // 先浅拷贝自身
        Person cloned = (Person) super.clone();

        // 深拷贝引用类型字段
        if (this.address != null) {
            cloned.address = (Address) this.address.clone();
        }

        return cloned;
    }
}

class Address implements Cloneable {
    private String city;
    private String street;

    @Override
    protected Object clone() throws CloneNotSupportedException {
        return super.clone();
    }
}
```

**测试：**
```java
Person p1 = new Person("Tom", 25, new Address("Beijing", "Street1"));
Person p2 = (Person) p1.clone();

p2.getAddress().setCity("Shanghai");

System.out.println(p1.getAddress().getCity());  // Beijing（不受影响）
System.out.println(p2.getAddress().getCity());  // Shanghai
System.out.println(p1.getAddress() == p2.getAddress());  // false（不同对象）
```

#### 方式2：序列化实现深拷贝

```java
import java.io.*;

public class Person implements Serializable {
    private static final long serialVersionUID = 1L;

    private String name;
    private int age;
    private Address address;

    // 深拷贝方法（通过序列化）
    public Person deepCopy() {
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
            throw new RuntimeException("深拷贝失败", e);
        }
    }
}

class Address implements Serializable {
    private static final long serialVersionUID = 1L;

    private String city;
    private String street;
}
```

**优点：**
- 自动处理所有引用类型的深拷贝
- 无需手动实现每个类的clone()方法

**缺点：**
- 性能较差（涉及IO操作）
- 所有类必须实现Serializable接口
- transient字段不会被拷贝

#### 方式3：使用JSON序列化

```java
import com.google.gson.Gson;

public class Person {
    private String name;
    private int age;
    private Address address;

    // 深拷贝方法（通过JSON）
    public Person deepCopy() {
        Gson gson = new Gson();
        String json = gson.toJson(this);
        return gson.fromJson(json, Person.class);
    }
}
```

**优点：**
- 实现简单
- 不需要实现Serializable或Cloneable

**缺点：**
- 性能开销较大
- 需要依赖第三方库（Gson/Jackson）
- 无法处理复杂对象（如循环引用）

#### 方式4：Apache Commons的SerializationUtils

```java
import org.apache.commons.lang3.SerializationUtils;

Person p1 = new Person("Tom", 25, new Address("Beijing", "Street1"));
Person p2 = SerializationUtils.clone(p1);  // 深拷贝
```

### 5. Cloneable接口详解

#### 接口定义

```java
public interface Cloneable {
    // 标记接口，无方法
}
```

**特点：**
- Cloneable是**标记接口**（Marker Interface）
- 不包含任何方法
- 仅用于标识对象可被clone

#### clone()方法

```java
// Object类中的clone()方法
protected native Object clone() throws CloneNotSupportedException;
```

**关键点：**
- clone()是Object类的protected方法
- 必须实现Cloneable接口，否则抛出CloneNotSupportedException
- 默认执行浅拷贝（逐字段复制）

#### 正确使用clone的规范

```java
public class Person implements Cloneable {
    private String name;
    private int age;
    private Address address;

    @Override
    public Person clone() {  // 修改返回类型（协变返回类型）
        try {
            Person cloned = (Person) super.clone();

            // 深拷贝引用字段
            if (this.address != null) {
                cloned.address = this.address.clone();
            }

            return cloned;
        } catch (CloneNotSupportedException e) {
            // 实现了Cloneable，不会发生
            throw new AssertionError();
        }
    }
}
```

### 6. 深拷贝vs浅拷贝对比

| 维度 | 浅拷贝 | 深拷贝 |
|------|--------|--------|
| **基本类型** | 拷贝值 | 拷贝值 |
| **引用类型** | 拷贝引用（共享对象） | 递归拷贝（独立对象） |
| **修改影响** | 会相互影响 | 互不影响 |
| **实现难度** | 简单 | 复杂 |
| **性能** | 快 | 慢 |
| **内存占用** | 少 | 多 |
| **适用场景** | 不可变对象、共享数据 | 独立对象、数据隔离 |

### 7. 常见陷阱与注意事项

#### 陷阱1：String的特殊性

```java
public class Person implements Cloneable {
    private String name;  // String虽然是引用类型，但不可变

    @Override
    protected Object clone() throws CloneNotSupportedException {
        return super.clone();  // 浅拷贝String没问题
    }
}

Person p1 = new Person("Tom");
Person p2 = (Person) p1.clone();
p2.setName("Jerry");

System.out.println(p1.getName());  // Tom（不受影响）
```

**原因：**String是不可变对象，修改实际是创建新对象，不影响原对象。

#### 陷阱2：集合的拷贝

```java
public class Team implements Cloneable {
    private List<Person> members;

    @Override
    protected Object clone() throws CloneNotSupportedException {
        Team cloned = (Team) super.clone();

        // ❌ 错误：仅拷贝List引用（浅拷贝）
        // cloned.members = this.members;

        // ✅ 正确：深拷贝List
        cloned.members = new ArrayList<>();
        for (Person person : this.members) {
            cloned.members.add(person.clone());
        }

        return cloned;
    }
}
```

#### 陷阱3：循环引用

```java
public class Node implements Cloneable {
    private String value;
    private Node next;  // 可能形成环

    @Override
    protected Object clone() throws CloneNotSupportedException {
        Node cloned = (Node) super.clone();

        // ⚠️ 简单递归会导致栈溢出
        if (this.next != null) {
            cloned.next = this.next.clone();  // 可能死循环
        }

        return cloned;
    }
}
```

**解决方案：**使用Map记录已拷贝对象，避免重复拷贝。

### 8. 实际应用场景

#### 场景1：原型模式（设计模式）

```java
// 原型模式：通过拷贝创建对象
public abstract class Shape implements Cloneable {
    private String id;
    protected String type;

    public abstract void draw();

    @Override
    public Shape clone() {
        try {
            return (Shape) super.clone();
        } catch (CloneNotSupportedException e) {
            return null;
        }
    }
}

public class Circle extends Shape {
    public Circle() {
        type = "Circle";
    }

    @Override
    public void draw() {
        System.out.println("Drawing Circle");
    }
}

// 使用
Shape circle1 = new Circle();
Shape circle2 = circle1.clone();  // 快速创建相同对象
```

#### 场景2：缓存对象

```java
public class CacheManager {
    private Map<String, User> cache = new HashMap<>();

    public User getUser(String id) {
        User cached = cache.get(id);
        if (cached != null) {
            // 返回深拷贝，防止外部修改缓存
            return cached.deepCopy();
        }
        return loadUserFromDB(id);
    }
}
```

#### 场景3：撤销/重做功能

```java
public class TextEditor {
    private Document currentDoc;
    private Stack<Document> history = new Stack<>();

    public void saveState() {
        // 保存当前状态的深拷贝
        history.push(currentDoc.deepCopy());
    }

    public void undo() {
        if (!history.isEmpty()) {
            currentDoc = history.pop();
        }
    }
}
```

#### 场景4：多线程数据隔离

```java
public class ThreadSafeProcessor {
    private Data template;

    public void process() {
        // 每个线程使用独立的数据副本
        Data localData = template.deepCopy();
        // 处理localData，不影响其他线程
        doProcess(localData);
    }
}
```

### 9. 性能对比

```java
// 性能测试（10万次拷贝）
public class CopyPerformanceTest {
    public static void main(String[] args) {
        Person template = createComplexPerson();
        int count = 100000;

        // 1. 浅拷贝（clone）
        long start = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            Person p = template.shallowClone();
        }
        System.out.println("浅拷贝: " + (System.currentTimeMillis() - start) + "ms");

        // 2. 深拷贝（手动clone）
        start = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            Person p = template.deepClone();
        }
        System.out.println("深拷贝(clone): " + (System.currentTimeMillis() - start) + "ms");

        // 3. 深拷贝（序列化）
        start = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            Person p = template.deepCopyBySerialization();
        }
        System.out.println("深拷贝(序列化): " + (System.currentTimeMillis() - start) + "ms");
    }
}

// 典型结果：
// 浅拷贝: 50ms
// 深拷贝(clone): 150ms
// 深拷贝(序列化): 2000ms
```

### 10. 最佳实践

#### ✅ 推荐做法

```java
// 1. 优先使用不可变对象，避免拷贝问题
public final class Person {
    private final String name;
    private final int age;
    private final Address address;

    // 构造时传入，无setter方法
}

// 2. 对于可变对象，明确提供深拷贝方法
public class MutablePerson {
    public MutablePerson deepCopy() {
        // 明确语义，优于clone()
        return new MutablePerson(
            this.name,
            this.age,
            this.address.deepCopy()
        );
    }
}

// 3. 使用工具类简化深拷贝
Person copy = SerializationUtils.clone(original);
```

#### ❌ 避免做法

```java
// 1. 避免在clone()中抛出异常
@Override
public Person clone() throws CloneNotSupportedException {
    // 如果实现了Cloneable，不应抛出异常
    return (Person) super.clone();
}

// 2. 避免在构造函数中调用可重写方法
public Person(Person other) {
    this.name = other.getName();  // ✅ 调用final方法
    this.age = other.calculateAge();  // ❌ 可能被子类重写
}

// 3. 避免浅拷贝可变对象
public Person shallowClone() {
    return new Person(this.name, this.age, this.address);  // ❌ address仍共享
}
```

### 11. 面试答题要点

**标准回答结构：**

1. **定义**：
   - 浅拷贝：拷贝对象，引用类型字段共享
   - 深拷贝：拷贝对象，递归拷贝所有引用对象

2. **实现方式**：
   - 浅拷贝：Object.clone()（默认）
   - 深拷贝：重写clone()递归拷贝 / 序列化 / JSON转换

3. **关键区别**：修改拷贝对象的引用字段是否影响原对象

4. **使用场景**：
   - 浅拷贝：不可变对象、共享数据
   - 深拷贝：需要完全独立的对象副本

5. **注意事项**：Cloneable接口、循环引用、性能开销

**加分点：**
- 了解Cloneable的标记接口特性
- 知道String等不可变对象的特殊性
- 能说明多种深拷贝实现方式的优缺点
- 提到原型模式等设计模式应用
- 了解性能差异和最佳实践

### 12. 总结

**核心要点：**

| 方面 | 浅拷贝 | 深拷贝 |
|------|--------|--------|
| **实现** | `super.clone()` | 递归clone/序列化 |
| **独立性** | 部分独立 | 完全独立 |
| **性能** | 高 | 低 |
| **复杂度** | 低 | 高 |
| **使用场景** | 简单对象、不可变字段 | 复杂对象、需要隔离 |

**记忆口诀：**
- 浅拷贝：拷贝表面，内部共享
- 深拷贝：彻底复制，完全独立
- String特殊：虽是引用，行为似值
- 集合注意：需要递归，逐个拷贝

理解深浅拷贝是掌握Java对象机制、内存模型和面向对象编程的重要基础。
