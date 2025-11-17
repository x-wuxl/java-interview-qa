---
layout: post
title: "描述类的实例化顺序（父类静态成员、构造函数、子类静态成员、构造函数）"
date: 2025-11-16
description: "深入解析 Java 类加载和实例化的完整顺序，包括静态代码块、实例代码块、构造方法的执行时机"
author: "wuxl"
categories: [Java基础]
tags: [类加载, 初始化顺序, 静态代码块, 构造方法]
---

## 问题

描述类的实例化顺序（父类静态成员、构造函数、子类静态成员、构造函数）。

## 答案

### 一、完整的初始化顺序

Java 类的实例化遵循严格的顺序，以分为 **类加载阶段** 和 **实例创建阶段**：

#### 标准顺序（5 步）

1. **父类静态成员** 和 **静态代码块**（类加载时执行，只执行一次）
2. **子类静态成员** 和 **静态代码块**（类加载时执行，只执行一次）
3. **父类实例变量** 和 **实例代码块**（每次创建对象时执行）
4. **父类构造方法**（每次创建对象时执行）
5. **子类实例变量** 和 **实例代码块**（每次创建对象时执行）
6. **子类构造方法**（每次创建对象时执行）

**关键原则**：
- 静态成员在类加载时初始化，**只执行一次**
- 实例成员在对象创建时初始化，**每次创建对象都执行**
- 父类优先于子类
- 静态优先于实例
- 成员变量/代码块优先于构造方法

---

### 二、完整示例代码

```java
class Parent {
    // 1. 父类静态变量
    private static String staticField = initStaticField();

    // 2. 父类静态代码块
    static {
        System.out.println("1. 父类静态代码块");
    }

    // 3. 父类实例变量
    private String instanceField = initInstanceField();

    // 4. 父类实例代码块
    {
        System.out.println("3. 父类实例代码块");
    }

    // 5. 父类构造方法
    public Parent() {
        System.out.println("4. 父类构造方法");
    }

    private static String initStaticField() {
        System.out.println("0. 父类静态变量初始化");
        return "parent static";
    }

    private String initInstanceField() {
        System.out.println("2. 父类实例变量初始化");
        return "parent instance";
    }
}

class Child extends Parent {
    // 6. 子类静态变量
    private static String staticField = initStaticField();

    // 7. 子类静态代码块
    static {
        System.out.println("5. 子类静态代码块");
    }

    // 8. 子类实例变量
    private String instanceField = initInstanceField();

    // 9. 子类实例代码块
    {
        System.out.println("7. 子类实例代码块");
    }

    // 10. 子类构造方法
    public Child() {
        System.out.println("8. 子类构造方法");
    }

    private static String initStaticField() {
        System.out.println("4. 子类静态变量初始化");
        return "child static";
    }

    private String initInstanceField() {
        System.out.println("6. 子类实例变量初始化");
        return "child instance";
    }
}

public class InitializationOrderDemo {
    public static void main(String[] args) {
        System.out.println("===== 第一次创建对象 =====");
        Child child1 = new Child();

        System.out.println("\n===== 第二次创建对象 =====");
        Child child2 = new Child();
    }
}
```

---

### 三、执行结果

```
===== 第一次创建对象 =====
0. 父类静态变量初始化
1. 父类静态代码块
4. 子类静态变量初始化
5. 子类静态代码块
2. 父类实例变量初始化
3. 父类实例代码块
4. 父类构造方法
6. 子类实例变量初始化
7. 子类实例代码块
8. 子类构造方法

===== 第二次创建对象 =====
2. 父类实例变量初始化
3. 父类实例代码块
4. 父类构造方法
6. 子类实例变量初始化
7. 子类实例代码块
8. 子类构造方法
```

**分析**：
- 第一次创建对象时，静态成员被初始化（步骤 0-5）
- 第二次创建对象时，**静态成员不再执行**，直接从实例成员开始（步骤 2-8）

---

### 四、详细执行流程图

```
类加载阶段（只执行一次）
├── 父类静态变量初始化
├── 父类静态代码块
├── 子类静态变量初始化
└── 子类静态代码块

实例创建阶段（每次 new 都执行）
├── 父类实例变量初始化
├── 父类实例代码块
├── 父类构造方法
├── 子类实例变量初始化
├── 子类实例代码块
└── 子类构造方法
```

---

### 五、关键知识点

#### 1. 静态成员的初始化时机

```java
public class StaticDemo {
    static {
        System.out.println("静态代码块执行");
    }

    public static void main(String[] args) {
        System.out.println("main 方法执行");
    }
}
```

**输出**：
```
静态代码块执行
main 方法执行
```

**说明**：静态代码块在 `main` 方法之前执行，因为类加载先于方法调用。

#### 2. 实例变量与实例代码块的顺序

```java
public class InstanceDemo {
    // 实例变量和实例代码块按声明顺序执行
    private String field1 = init("field1");

    {
        System.out.println("实例代码块1");
    }

    private String field2 = init("field2");

    {
        System.out.println("实例代码块2");
    }

    public InstanceDemo() {
        System.out.println("构造方法");
    }

    private String init(String name) {
        System.out.println("初始化: " + name);
        return name;
    }
}
```

**输出**：
```
初始化: field1
实例代码块1
初始化: field2
实例代码块2
构造方法
```

#### 3. 构造方法中的隐式 super()

```java
class Parent {
    public Parent() {
        System.out.println("父类构造方法");
        // 此时子类实例变量还未初始化
        display();  // 调用被子类重写的方法
    }

    public void display() {
        System.out.println("父类 display");
    }
}

class Child extends Parent {
    private int value = 100;

    public Child() {
        System.out.println("子类构造方法，value = " + value);
    }

    @Override
    public void display() {
        // 此时 value 还是默认值 0（未初始化）
        System.out.println("子类 display，value = " + value);
    }
}

public class ConstructorDemo {
    public static void main(String[] args) {
        new Child();
    }
}
```

**输出**：
```
父类构造方法
子类 display，value = 0
子类构造方法，value = 100
```

**陷阱**：父类构造方法中调用被子类重写的方法时，子类实例变量还未初始化，值为默认值（int 为 0）。

---

### 六、常见面试陷阱

#### 陷阱 1：静态代码块只执行一次

```java
public class StaticTrap {
    static {
        System.out.println("静态代码块");
    }

    public StaticTrap() {
        System.out.println("构造方法");
    }

    public static void main(String[] args) {
        new StaticTrap();
        new StaticTrap();
    }
}
```

**输出**：
```
静态代码块
构造方法
构造方法
```

#### 陷阱 2：实例变量的初始化顺序

```java
public class FieldOrderTrap {
    private int a = getA();
    private int b = 20;

    {
        b = 30;
    }

    public FieldOrderTrap() {
        b = 40;
    }

    private int getA() {
        System.out.println("getA() 执行，此时 b = " + b);
        return 10;
    }

    public static void main(String[] args) {
        FieldOrderTrap obj = new FieldOrderTrap();
        System.out.println("最终 b = " + obj.b);
    }
}
```

**输出**：
```
getA() 执行，此时 b = 0
最终 b = 40
```

**分析**：
1. `a` 初始化时调用 `getA()`，此时 `b` 还未初始化，值为默认值 0
2. `b` 初始化为 20
3. 实例代码块将 `b` 修改为 30
4. 构造方法将 `b` 修改为 40

---

### 七、实际应用场景

#### 1. 单例模式（静态代码块初始化）

```java
public class Singleton {
    private static final Singleton INSTANCE;

    static {
        // 静态代码块中初始化单例
        INSTANCE = new Singleton();
        System.out.println("单例初始化完成");
    }

    private Singleton() {
        // 私有构造方法
    }

    public static Singleton getInstance() {
        return INSTANCE;
    }
}
```

#### 2. 资源初始化（实例代码块）

```java
public class DatabaseConnection {
    private Connection connection;

    {
        // 实例代码块中初始化资源
        try {
            connection = DriverManager.getConnection("jdbc:mysql://...");
            System.out.println("数据库连接初始化");
        } catch (SQLException e) {
            e.printStackTrace();
        }
    }

    public DatabaseConnection() {
        System.out.println("构造方法执行");
    }
}
```

---

### 八、面试要点总结

#### 记忆口诀

**"父静子静，父实子实，父构子构"**

1. **父静**：父类静态成员和静态代码块
2. **子静**：子类静态成员和静态代码块
3. **父实**：父类实例变量和实例代码块
4. **父构**：父类构造方法
5. **子实**：子类实例变量和实例代码块
6. **子构**：子类构造方法

#### 关键点

1. **静态成员只初始化一次**，在类加载时执行
2. **实例成员每次创建对象都执行**
3. **父类优先于子类**，静态优先于实例
4. **成员变量/代码块优先于构造方法**
5. **构造方法隐式调用 `super()`**，必须在第一行
6. **父类构造方法中调用被重写的方法**，子类实例变量还未初始化

#### 典型面试题

**Q：为什么静态代码块只执行一次？**
A：静态成员属于类，在类加载时初始化，JVM 保证每个类只加载一次。

**Q：实例代码块和构造方法有什么区别？**
A：实例代码块在所有构造方法之前执行，可用于提取多个构造方法的公共代码。

**Q：子类构造方法为什么必须调用父类构造方法？**
A：确保父类成员正确初始化，Java 通过隐式 `super()` 或显式调用实现。
