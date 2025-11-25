---
layout: default
title: "Java中的类什么时候会被加载？"
parent: JVM
nav_order: 147
description: "深入理解Java类加载的时机，包括主动引用和被动引用的场景，以及类初始化的触发条件"
author: "wuxl"
date: 2025-11-01
---
## 问题

Java中的类什么时候会被加载？

## 答案

### 核心概念

Java类的加载是指将`.class`文件的二进制数据读入内存，在方法区创建类的Class对象的过程。类的加载时机遵循"**懒加载**"（Lazy Loading）原则，即在首次主动使用时才会触发加载。

### 类加载的时机

Java虚拟机规范严格规定了**有且只有6种情况**必须立即对类进行"初始化"（而加载、验证、准备则在此之前完成）：

#### 1. **主动引用场景（触发类加载）**

1. **遇到new、getstatic、putstatic或invokestatic字节码指令时**
   - 使用`new`关键字实例化对象
   - 读取或设置类的静态字段（被final修饰且已在编译期放入常量池的静态字段除外）
   - 调用类的静态方法

2. **使用反射调用类时**
   ```java
   Class.forName("com.example.MyClass");
   ```

3. **初始化子类时，父类未初始化**
   - 子类初始化前会先触发父类的初始化

4. **虚拟机启动时，包含main()方法的主类**
   - JVM启动时会先初始化主类

5. **使用JDK 7新增的动态语言支持**
   - 当`java.lang.invoke.MethodHandle`实例最后的解析结果为`REF_getStatic`、`REF_putStatic`、`REF_invokeStatic`的方法句柄时

6. **接口定义了default方法（JDK 8+）**
   - 当接口的实现类初始化时，接口会被初始化

#### 2. **被动引用场景（不触发类加载）**

以下场景不会触发类的初始化：

```java
// 1. 通过子类引用父类的静态字段，不会导致子类初始化
System.out.println(SubClass.parentStaticField);

// 2. 通过数组定义来引用类，不会触发类初始化
SuperClass[] arr = new SuperClass[10];

// 3. 访问类的常量（编译期常量），不会触发类初始化
System.out.println(ConstClass.CONSTANT); // CONSTANT是final static
```

### 关键原理

1. **类加载三个阶段**：加载 → 连接（验证、准备、解析）→ 初始化
2. **初始化时机严格控制**：只有主动引用才触发初始化，被动引用不会
3. **类加载器的懒加载策略**：减少内存占用，提升启动速度

### 实战示例

```java
public class ClassLoadingDemo {
    static {
        System.out.println("ClassLoadingDemo 初始化");
    }

    public static void main(String[] args) {
        // 不会触发 ConstClass 初始化（常量在编译期已放入常量池）
        System.out.println(ConstClass.CONSTANT);

        // 触发 ActiveClass 初始化（访问非编译期常量）
        System.out.println(ActiveClass.value);
    }
}

class ConstClass {
    static {
        System.out.println("ConstClass 初始化");
    }
    public static final String CONSTANT = "hello"; // 编译期常量
}

class ActiveClass {
    static {
        System.out.println("ActiveClass 初始化");
    }
    public static String value = "world"; // 非编译期常量
}
```

**输出结果**：
```
ClassLoadingDemo 初始化
hello
ActiveClass 初始化
world
```

### 面试要点总结

1. **主动引用6种场景**是必须掌握的核心考点
2. **被动引用典型场景**要能快速识别（数组、常量、父类静态字段）
3. **类加载的懒加载特性**是JVM优化的重要策略
4. **类初始化时机**与**类加载时机**有细微区别：加载发生在初始化之前，但不是所有加载的类都会被初始化
