---
layout: default
title: "Java中类加载的过程是怎么样的？"
parent: JVM
nav_order: 148
description: "详解Java类加载的完整流程，包括加载、验证、准备、解析、初始化五个阶段的核心原理和关键细节"
author: "wuxl"
date: 2025-11-01
---
## 问题

Java中类加载的过程是怎么样的?

## 答案

### 核心概念

Java类加载是指将`.class`文件的二进制数据读入内存，在方法区生成Class对象，并使其可用的完整过程。类加载分为**加载、连接（验证、准备、解析）、初始化**五个阶段。

### 类加载的完整流程

```
加载(Loading) → 验证(Verification) → 准备(Preparation)
    → 解析(Resolution) → 初始化(Initialization)
```

#### 1. **加载（Loading）**

将类的字节码从磁盘、网络或其他来源加载到JVM内存，完成三件事：

1. **通过类的全限定名获取二进制字节流**
   - 从ZIP包读取（JAR、WAR）
   - 从网络获取（Applet）
   - 运行时动态生成（动态代理）
   - 从数据库读取
   - 从加密文件读取

2. **将字节流的静态存储结构转化为方法区的运行时数据结构**

3. **在堆中生成代表这个类的`java.lang.Class`对象**，作为方法区数据的访问入口

**关键点**：数组类不通过类加载器创建，由JVM直接创建。

#### 2. **验证（Verification）**

确保Class文件的字节流符合JVM规范，不会危害虚拟机安全。验证分为4个阶段：

1. **文件格式验证**
   ```
   - 魔数是否为 0xCAFEBABE
   - 主次版本号是否在JVM支持范围内
   - 常量池的常量类型是否合法
   - UTF-8编码是否合法
   ```

2. **元数据验证**
   ```
   - 是否有父类（除Object外所有类都应有父类）
   - 父类是否继承了不可继承的类（final修饰的类）
   - 抽象类是否实现了所有抽象方法或接口方法
   ```

3. **字节码验证**（最复杂）
   ```
   - 数据流和控制流分析
   - 保证操作数栈的数据类型与指令代码序列能配合工作
   - 保证跳转指令不会跳转到方法体以外的字节码指令上
   ```

4. **符号引用验证**（解析阶段触发）
   ```
   - 符号引用的类、字段、方法是否可被当前类访问
   - 检查权限（private、protected、public、default）
   ```

**优化**：可使用`-Xverify:none`跳过验证，缩短类加载时间（生产环境不推荐）。

#### 3. **准备（Preparation）**

在方法区为**类变量**（static变量）分配内存并设置初始值。

**关键原理**：
- **初始值是零值**，而非代码赋值的实际值
- `public static int value = 123;` → 准备阶段value=0，初始化阶段才赋值123
- **例外**：`public static final int value = 123;` → 准备阶段直接赋值123（常量）

**内存位置**：
- JDK 7及之前：方法区（永久代）
- JDK 8及之后：方法区（元空间 Metaspace）

**零值表**：
```java
int/short/byte/long → 0
float/double → 0.0
char → '\u0000'
boolean → false
引用类型 → null
```

#### 4. **解析（Resolution）**

将常量池内的**符号引用**替换为**直接引用**的过程。

**概念区分**：
- **符号引用**：用字符串描述目标，如`com/example/MyClass`
- **直接引用**：直接指向目标的指针、偏移量或句柄

**解析内容**：
1. **类或接口的解析**（CONSTANT_Class_info）
2. **字段解析**（CONSTANT_Fieldref_info）
3. **类方法解析**（CONSTANT_Methodref_info）
4. **接口方法解析**（CONSTANT_InterfaceMethodref_info）

**时机**：JVM规范未强制要求解析时机，由实现决定：
- 静态解析：类加载时完成（JDK早期版本）
- 动态解析：首次使用时解析（现代JVM）

#### 5. **初始化（Initialization）**

执行类构造器`<clinit>()`方法的过程，真正执行类中定义的Java代码。

**<clinit>() 方法特点**：
1. 由编译器自动收集类中**所有类变量的赋值动作**和**静态代码块**中的语句合并生成
2. 执行顺序按源文件中的出现顺序决定
3. 父类的`<clinit>()`先于子类执行
4. 如果类中没有静态代码块和类变量赋值，可以不生成`<clinit>()`方法
5. 接口不能有静态代码块，但可以有变量初始化，也会生成`<clinit>()`
6. JVM保证`<clinit>()`的线程安全（多线程环境下只执行一次）

**示例代码**：

```java
public class ClassLoadingProcess {
    // 准备阶段：value = 0
    // 初始化阶段：value = 100 → value = 200
    static {
        value = 100;
        // 可以赋值，但不能访问（非法前向引用）
        // System.out.println(value); // 编译错误
    }

    public static int value = 200;

    public static void main(String[] args) {
        System.out.println(value); // 输出：200
    }
}
```

**执行顺序示例**：

```java
class Parent {
    static {
        System.out.println("Parent static block");
    }
}

class Child extends Parent {
    static {
        System.out.println("Child static block");
    }
}

public class Test {
    public static void main(String[] args) {
        new Child();
        // 输出：
        // Parent static block
        // Child static block
    }
}
```

### 线程安全保障

JVM内部使用同步机制确保`<clinit>()`方法在多线程环境下只执行一次：

```java
public class DeadLoopClass {
    static {
        // 如果不加if，会导致其他线程永久阻塞
        if (true) {
            System.out.println(Thread.currentThread() + " init");
            while (true) {
                // 模拟耗时初始化
            }
        }
    }
}
```

### 面试要点总结

1. **五个阶段顺序**：加载 → 验证 → 准备 → 解析 → 初始化（连接=验证+准备+解析）
2. **准备阶段的零值赋值** vs **初始化阶段的实际值赋值**是高频考点
3. **<clinit>() 方法**的线程安全特性：JVM保证只执行一次
4. **父类先于子类初始化**的原则
5. **符号引用与直接引用**的概念区分
