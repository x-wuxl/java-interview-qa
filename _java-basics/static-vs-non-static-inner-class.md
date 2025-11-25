---
title: "静态内部类与非静态内部类有何区别？"
date: 2025-11-16
description: "深入解析 Java 中静态内部类与非静态内部类的区别，包括内存模型、访问权限和使用场景"
author: "wuxl"
categories: [Java基础]
tags: [内部类, 静态内部类, 成员内部类, 内存泄漏]
nav_order: 45
parent: Java基础
---
## 问题

静态内部类与非静态内部类有何区别？

## 答案

### 一、核心区别

| 特性 | 静态内部类（Static Nested Class） | 非静态内部类（Inner Class） |
|------|-----------------------------------|----------------------------|
| 定义方式 | 使用 `static` 修饰 | 不使用 `static` 修饰 |
| 依赖关系 | **不依赖外部类实例** | **依赖外部类实例** |
| 创建方式 | `Outer.Inner inner = new Outer.Inner()` | `Outer.Inner inner = outer.new Inner()` |
| 访问外部类成员 | 只能访问外部类的 **静态成员** | 可以访问外部类的 **所有成员**（包括私有） |
| 持有外部类引用 | **不持有** | **隐式持有** `Outer.this` |
| 内存占用 | 更小（无额外引用） | 更大（持有外部类引用） |
| 内存泄漏风险 | 低 | 高（可能导致外部类无法回收） |

---

### 二、静态内部类（Static Nested Class）

#### 1. 定义与特点

```java
public class Outer {
    private static String staticField = "外部类静态字段";
    private String instanceField = "外部类实例字段";

    // 静态内部类
    public static class StaticInner {
        public void display() {
            // ✅ 可以访问外部类的静态成员
            System.out.println(staticField);

            // ❌ 不能直接访问外部类的实例成员
            // System.out.println(instanceField);  // 编译错误
        }
    }
}
```

#### 2. 创建方式

```java
// 不需要外部类实例，直接通过类名创建
Outer.StaticInner inner = new Outer.StaticInner();
inner.display();
```

#### 3. 访问外部类实例成员

```java
public class Outer {
    private String instanceField = "实例字段";

    public static class StaticInner {
        public void display(Outer outer) {
            // 需要显式传入外部类实例
            System.out.println(outer.instanceField);
        }
    }
}

// 使用
Outer outer = new Outer();
Outer.StaticInner inner = new Outer.StaticInner();
inner.display(outer);
```

---

### 三、非静态内部类（Inner Class / Member Inner Class）

#### 1. 定义与特点

```java
public class Outer {
    private static String staticField = "外部类静态字段";
    private String instanceField = "外部类实例字段";

    // 非静态内部类（成员内部类）
    public class Inner {
        public void display() {
            // ✅ 可以访问外部类的静态成员
            System.out.println(staticField);

            // ✅ 可以访问外部类的实例成员
            System.out.println(instanceField);

            // ✅ 显式引用外部类实例
            System.out.println(Outer.this.instanceField);
        }
    }
}
```

#### 2. 创建方式

```java
// 必须先创建外部类实例
Outer outer = new Outer();
Outer.Inner inner = outer.new Inner();
inner.display();

// 或者在外部类方法中创建
public class Outer {
    public Inner createInner() {
        return new Inner();  // 隐式使用 this
    }
}
```

#### 3. 隐式持有外部类引用

```java
public class Outer {
    private String name = "Outer";

    public class Inner {
        public void printOuterName() {
            // 隐式持有 Outer.this 引用
            System.out.println(Outer.this.name);
        }

        public Outer getOuter() {
            return Outer.this;  // 返回外部类实例
        }
    }
}
```

---

### 四、内存模型对比

#### 1. 静态内部类

```
堆内存：
┌─────────────────┐
│ StaticInner 对象 │  (独立存在，不持有外部类引用)
└─────────────────┘
```

#### 2. 非静态内部类

```
堆内存：
┌─────────────┐
│ Outer 对象   │ ←─────┐
└─────────────┘       │
                      │ this$0 (隐式引用)
┌─────────────┐       │
│ Inner 对象   │ ──────┘
└─────────────┘
```

**关键点**：非静态内部类对象会持有一个名为 `this$0` 的隐式引用，指向外部类实例。

---

### 五、字节码层面的差异

#### 1. 静态内部类字节码

```java
// 编译后生成：Outer$StaticInner.class
public class Outer$StaticInner {
    public void display() {
        // 直接访问静态字段
        System.out.println(Outer.staticField);
    }
}
```

#### 2. 非静态内部类字节码

```java
// 编译后生成：Outer$Inner.class
public class Outer$Inner {
    final Outer this$0;  // 隐式持有外部类引用

    public Outer$Inner(Outer outer) {
        this.this$0 = outer;  // 构造方法中传入外部类实例
    }

    public void display() {
        // 通过 this$0 访问外部类成员
        System.out.println(this$0.instanceField);
    }
}
```

---

### 六、内存泄漏风险

#### 1. 非静态内部类导致的内存泄漏

```java
public class Activity {
    private byte[] data = new byte[1024 * 1024];  // 1MB 数据

    // ❌ 错误示例：非静态内部类
    public class AsyncTask {
        public void execute() {
            new Thread(() -> {
                // 长时间运行的任务
                try {
                    Thread.sleep(10000);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
                // 隐式持有 Activity.this，导致 Activity 无法回收
            }).start();
        }
    }

    public void startTask() {
        new AsyncTask().execute();
    }
}
```

**问题**：即使 `Activity` 不再使用，由于 `AsyncTask` 持有 `Activity` 的引用，导致 1MB 数据无法回收。

#### 2. 使用静态内部类避免泄漏

```java
public class Activity {
    private byte[] data = new byte[1024 * 1024];

    // ✅ 正确示例：静态内部类 + 弱引用
    public static class AsyncTask {
        private final WeakReference<Activity> activityRef;

        public AsyncTask(Activity activity) {
            this.activityRef = new WeakReference<>(activity);
        }

        public void execute() {
            new Thread(() -> {
                try {
                    Thread.sleep(10000);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }

                Activity activity = activityRef.get();
                if (activity != null) {
                    // 使用 activity
                }
            }).start();
        }
    }

    public void startTask() {
        new AsyncTask(this).execute();
    }
}
```

---

### 七、使用场景

#### 1. 静态内部类适用场景

**（1）工具类或辅助类**

```java
public class Calculator {
    // 静态内部类：不依赖外部类实例
    public static class MathUtils {
        public static int add(int a, int b) {
            return a + b;
        }
    }
}

// 使用
int result = Calculator.MathUtils.add(1, 2);
```

**（2）单例模式（静态内部类实现）**

```java
public class Singleton {
    private Singleton() {}

    // 静态内部类：延迟加载 + 线程安全
    private static class Holder {
        private static final Singleton INSTANCE = new Singleton();
    }

    public static Singleton getInstance() {
        return Holder.INSTANCE;
    }
}
```

**（3）Builder 模式**

```java
public class User {
    private final String name;
    private final int age;

    private User(Builder builder) {
        this.name = builder.name;
        this.age = builder.age;
    }

    // 静态内部类：构建器
    public static class Builder {
        private String name;
        private int age;

        public Builder name(String name) {
            this.name = name;
            return this;
        }

        public Builder age(int age) {
            this.age = age;
            return this;
        }

        public User build() {
            return new User(this);
        }
    }
}

// 使用
User user = new User.Builder()
    .name("Alice")
    .age(25)
    .build();
```

#### 2. 非静态内部类适用场景

**（1）需要访问外部类实例成员**

```java
public class LinkedList<E> {
    private Node<E> first;

    // 非静态内部类：需要访问外部类的 first
    private class Node<E> {
        E item;
        Node<E> next;

        Node(E element) {
            this.item = element;
        }
    }

    public void add(E element) {
        Node<E> newNode = new Node<>(element);
        if (first == null) {
            first = newNode;
        }
    }
}
```

**（2）迭代器模式**

```java
public class MyList<E> {
    private E[] elements;
    private int size;

    // 非静态内部类：迭代器需要访问外部类的 elements 和 size
    private class Iterator {
        private int cursor = 0;

        public boolean hasNext() {
            return cursor < size;
        }

        public E next() {
            return elements[cursor++];
        }
    }

    public Iterator iterator() {
        return new Iterator();
    }
}
```

---

### 八、其他类型的内部类

#### 1. 局部内部类（Local Inner Class）

```java
public class Outer {
    public void method() {
        final int localVar = 10;

        // 局部内部类：定义在方法内
        class LocalInner {
            public void display() {
                System.out.println(localVar);  // 可以访问 final 或 effectively final 变量
            }
        }

        LocalInner inner = new LocalInner();
        inner.display();
    }
}
```

#### 2. 匿名内部类（Anonymous Inner Class）

```java
public class Outer {
    public void method() {
        // 匿名内部类：实现接口
        Runnable runnable = new Runnable() {
            @Override
            public void run() {
                System.out.println("匿名内部类");
            }
        };

        new Thread(runnable).start();
    }
}
```

---

### 九、性能对比

| 维度 | 静态内部类 | 非静态内部类 |
|------|-----------|-------------|
| 对象大小 | 小（无额外引用） | 大（多 4-8 字节存储 `this$0`） |
| 创建速度 | 快 | 稍慢（需要传递外部类引用） |
| 内存泄漏风险 | 低 | 高 |
| GC 压力 | 小 | 大 |

---

### 十、面试要点总结

#### 1. 核心区别

- **静态内部类**：不依赖外部类实例，不持有外部类引用，只能访问静态成员
- **非静态内部类**：依赖外部类实例，隐式持有 `Outer.this` 引用，可访问所有成员

#### 2. 创建方式

```java
// 静态内部类
Outer.StaticInner inner1 = new Outer.StaticInner();

// 非静态内部类
Outer outer = new Outer();
Outer.Inner inner2 = outer.new Inner();
```

#### 3. 内存泄漏

非静态内部类持有外部类引用，可能导致外部类无法回收。解决方案：
- 使用静态内部类 + 弱引用（`WeakReference`）
- 及时解除引用

#### 4. 使用建议

- **优先使用静态内部类**：除非必须访问外部类实例成员
- **避免在 Activity/Fragment 中使用非静态内部类**：防止内存泄漏
- **Builder 模式、单例模式**：使用静态内部类

#### 5. 典型面试题

**Q：为什么非静态内部类会持有外部类引用？**
A：编译器自动在非静态内部类中添加 `this$0` 字段，并在构造方法中传入外部类实例。

**Q：如何避免非静态内部类导致的内存泄漏？**
A：改用静态内部类 + 弱引用，或及时解除引用。

**Q：静态内部类能否访问外部类的实例成员？**
A：不能直接访问，需要显式传入外部类实例。
