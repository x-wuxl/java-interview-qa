---
layout: default
title: "方法区存储什么数据？"
parent: JVM
nav_order: 111
description: "详细解析JVM方法区存储的数据内容，包括类信息、运行时常量池、字段方法元数据等核心内容"
author: "wuxl"
date: 2025-11-01
---
## 问题

方法区存储什么数据？

## 答案

### 核心概念

方法区(Method Area)是JVM规范定义的逻辑概念,用于存储**已被虚拟机加载的类型信息、常量、静态变量、即时编译器编译后的代码缓存**等数据。它是线程共享的内存区域,在JVM启动时创建。

### 方法区存储的数据类型

#### 1. 类型信息(Type Information)

每个加载的类(class)、接口(interface)、枚举(enum)、注解(annotation)都会在方法区存储以下信息:

**A. 类的基本信息**:
```java
// 示例类
public class User extends Person implements Serializable {
    // ...
}

// 方法区存储:
// - 类的完全限定名: com.example.User
// - 父类的完全限定名: com.example.Person
// - 类的访问修饰符: public
// - 类的类型: class (还可能是interface/enum/annotation)
// - 实现的接口列表: [java.io.Serializable]
// - 类的版本信息(major/minor version)
```

**B. 类的结构信息**:
```java
public class Student {
    private String name;
    private int age;

    public Student(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() {
        return name;
    }
}

// 方法区存储:
// 1. 字段信息:
//    - 字段名: name, age
//    - 字段类型: String, int
//    - 字段修饰符: private
//    - 字段的字节码偏移量
//
// 2. 方法信息:
//    - 方法名: <init>, getName
//    - 方法返回类型: void, String
//    - 方法参数类型: (String, int), ()
//    - 方法修饰符: public
//    - 方法的字节码(code)
//    - 操作数栈深度
//    - 局部变量表大小
//    - 异常表
```

**C. 类的继承关系**:
```java
// 类的继承树信息
class Animal {}
class Dog extends Animal {}
class Husky extends Dog {}

// 方法区存储:
// - Husky -> Dog -> Animal -> Object 的继承链
// - 用于方法查找、类型检查(instanceof)
```

#### 2. 运行时常量池(Runtime Constant Pool)

运行时常量池是方法区的一部分,是class文件中常量池表(Constant Pool Table)的运行时表示。

**A. 字面量常量**:
```java
public class ConstantExample {
    private static final int MAX = 100;              // 整型常量
    private static final String NAME = "Java";       // 字符串常量
    private static final double PI = 3.14159;        // 浮点常量
    private static final boolean FLAG = true;        // 布尔常量
}

// 运行时常量池存储:
// - 100 (整型字面量)
// - "Java" (字符串字面量的引用,实际字符串对象在堆中)
// - 3.14159 (双精度浮点字面量)
// - true (布尔字面量)
```

**B. 符号引用**:
```java
public class ReferenceExample {
    private User user;

    public void method() {
        user.getName();
    }
}

// 运行时常量池存储:
// 1. 类的全限定名: com/example/User (CONSTANT_Class_info)
// 2. 字段名称和描述符: user:Lcom/example/User; (CONSTANT_Fieldref_info)
// 3. 方法名称和描述符: getName:()Ljava/lang/String; (CONSTANT_Methodref_info)
//
// 类加载时,符号引用会被解析为直接引用(内存地址)
```

**C. 动态常量**:
```java
// JDK 11+ 支持的动态常量(CONSTANT_Dynamic)
// 通过invokedynamic指令在运行时计算
```

#### 3. 字段信息(Field Information)

**实例字段**:
```java
public class Book {
    private String title;           // 实例字段
    private String author;
    private double price;
    private int pages;
}

// 方法区存储字段元数据:
// - 字段名称: title, author, price, pages
// - 字段类型描述符: Ljava/lang/String;, Ljava/lang/String;, D, I
// - 字段访问标志: ACC_PRIVATE
// - 字段在对象中的偏移量(用于快速访问)
```

**静态字段(JDK 7之前在方法区,JDK 7+移至堆中)**:
```java
public class Config {
    public static String APP_NAME = "MyApp";        // 静态变量
    public static final int VERSION = 1;            // 静态常量
    private static Connection connection;           // 静态对象引用
}

// JDK 6及以前: 静态变量存储在方法区(PermGen)
// JDK 7及以后: 静态变量移至堆中,方法区只保留元数据
```

#### 4. 方法信息(Method Information)

**方法元数据**:
```java
public int calculate(int a, int b) throws IllegalArgumentException {
    if (a < 0 || b < 0) {
        throw new IllegalArgumentException("参数不能为负数");
    }
    return a + b;
}

// 方法区存储:
// 1. 方法名称: calculate
// 2. 方法描述符: (II)I  // (int, int) -> int
// 3. 访问标志: ACC_PUBLIC
// 4. 方法字节码指令序列:
//    0: iload_1        // 加载参数a
//    1: ifge 12        // 如果a >= 0跳转到12
//    4: new #2         // 创建IllegalArgumentException
//    ...
// 5. 异常表:
//    from  to  target  type
//    0     12   15    IllegalArgumentException
// 6. 局部变量表大小: 3 (this, a, b)
// 7. 操作数栈最大深度: 2
// 8. 行号表(用于调试):
//    line 10: 0
//    line 11: 4
//    ...
```

**方法的Code属性**:
```java
// 每个方法(除abstract/native外)都有Code属性
// 包含:
// - max_stack: 操作数栈最大深度
// - max_locals: 局部变量表最大长度
// - code[]: 字节码指令数组
// - exception_table[]: 异常处理表
// - attributes[]: 其他属性(LineNumberTable, LocalVariableTable等)
```

#### 5. 即时编译器编译后的代码缓存(Code Cache)

**JIT编译代码**:
```java
// 热点代码会被JIT编译为本地机器码
public int hotMethod(int n) {
    int sum = 0;
    for (int i = 0; i < n; i++) {
        sum += i;
    }
    return sum;
}

// 执行流程:
// 1. 最初: 解释执行字节码
// 2. 达到阈值(-XX:CompileThreshold): 触发JIT编译
// 3. 编译后: 本地机器码存储在Code Cache
// 4. 后续: 直接执行本地机器码(性能提升10-100倍)
```

**Code Cache配置**:
```bash
# 查看Code Cache使用情况
jinfo -flag ReservedCodeCacheSize <pid>

# 配置Code Cache大小
-XX:ReservedCodeCacheSize=240m     # 默认约240MB
-XX:InitialCodeCacheSize=128m      # 初始大小

# 监控Code Cache
jstat -compiler <pid>              # 查看编译统计
```

#### 6. 其他重要信息

**A. 类的常量池表**:
```java
// class文件的Constant Pool在加载后成为运行时常量池
// 包含:
// - CONSTANT_Utf8: 字符串字面量
// - CONSTANT_Integer/Float/Long/Double: 数值常量
// - CONSTANT_Class: 类或接口的符号引用
// - CONSTANT_String: 字符串常量的符号引用
// - CONSTANT_Fieldref: 字段的符号引用
// - CONSTANT_Methodref: 方法的符号引用
// - CONSTANT_InterfaceMethodref: 接口方法的符号引用
```

**B. 类的属性(Attributes)**:
```java
// 类级别的属性存储在方法区:
// - SourceFile: 源文件名
// - InnerClasses: 内部类信息
// - Signature: 泛型签名
// - Annotations: 注解信息
// - BootstrapMethods: invokedynamic指令的引导方法

@Deprecated
@MyCustomAnnotation(value = "test")
public class Example {
    // 注解信息存储在方法区
}
```

### 版本差异

#### JDK 7及以前: 永久代(PermGen)

```bash
# 永久代配置
-XX:PermSize=128m          # 初始大小
-XX:MaxPermSize=256m       # 最大大小

# 永久代存储:
# - 类元数据
# - 运行时常量池
# - 字符串常量池 (JDK 6在PermGen, JDK 7移至堆)
# - 静态变量 (JDK 7移至堆)
```

#### JDK 8及以后: 元空间(Metaspace)

```bash
# 元空间配置
-XX:MetaspaceSize=128m          # 初始大小
-XX:MaxMetaspaceSize=512m       # 最大大小(默认无限制)

# 元空间存储:
# - 类元数据 (在本地内存中)
# - 运行时常量池(不含字符串常量池)
# - Code Cache (独立区域)

# 注意:
# - 字符串常量池在堆中
# - 静态变量在堆中
```

### 实际示例

```java
public class MethodAreaExample {
    // 类信息: MethodAreaExample, extends Object, public

    // 字段信息
    private static int staticVar = 10;        // 静态变量(JDK7+在堆)
    private String instanceVar = "hello";     // 实例字段元数据在方法区

    // 常量信息
    public static final String CONSTANT = "CONST";  // 常量池

    // 方法信息
    public void method() {
        // 方法字节码存储在方法区
        String local = "local";
        System.out.println(local);
    }

    // Native方法
    public native void nativeMethod();

    public static void main(String[] args) {
        // 触发类加载,方法区创建MethodAreaExample类的元数据
        MethodAreaExample example = new MethodAreaExample();
        example.method();
    }
}

// 方法区存储内容总结:
// 1. 类型信息: MethodAreaExample的类元数据
// 2. 字段信息: staticVar, instanceVar的元数据
// 3. 方法信息: method, nativeMethod, main的字节码和元数据
// 4. 常量池: "CONST", "hello", "local"的符号引用
// 5. 符号引用: System, String, PrintStream等的引用
```

### 查看方法区数据

```bash
# 1. 查看加载的类
jcmd <pid> VM.classes

# 2. 查看常量池
javap -v MethodAreaExample.class

# 输出示例:
# Constant pool:
#    #1 = Methodref          #6.#20         // java/lang/Object."<init>":()V
#    #2 = String             #21            // hello
#    #3 = Fieldref           #5.#22         // MethodAreaExample.instanceVar:Ljava/lang/String;
#    ...

# 3. 查看元空间使用情况
jstat -gcmetacapacity <pid>

# 4. 使用JConsole/VisualVM查看
# Memory -> Metaspace
```

### 方法区的GC

方法区也会进行垃圾回收,主要回收:
1. **废弃的常量**: 没有任何对象引用的常量
2. **不再使用的类**: 满足以下条件的类可以被卸载
   - 该类所有实例已被回收
   - 加载该类的ClassLoader已被回收
   - 该类的java.lang.Class对象没有被引用

```bash
# 启用类卸载日志
-XX:+TraceClassUnloading
-verbose:class

# 输出示例:
# [Unloading class com.example.DynamicClass]
```

### 面试总结

**方法区主要存储**:

1. **类型信息**:
   - 类的全限定名、父类、接口
   - 类的修饰符、类型(class/interface/enum)

2. **字段信息**:
   - 字段名称、类型、修饰符
   - 字段元数据(偏移量等)

3. **方法信息**:
   - 方法名称、返回类型、参数
   - 方法字节码、异常表
   - 局部变量表大小、操作数栈深度

4. **运行时常量池**:
   - 字面量常量(数值、字符串引用)
   - 符号引用(类、字段、方法)

5. **即时编译代码缓存**:
   - JIT编译的本地机器码

**版本变化**:
- JDK 7: 字符串常量池、静态变量移至堆
- JDK 8: 永久代移除,改用元空间(本地内存)

**关键点**:
- 方法区是逻辑概念,永久代/元空间是实现
- 存储类的"元数据",不是类的实例数据(实例在堆上)
- 方法区也会GC,回收废弃常量和不再使用的类
