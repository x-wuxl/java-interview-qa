---
layout: default
title: "什么是Class常量池，和运行时常量池关系是什么？"
parent: JVM
nav_order: 157
description: "深入理解Class文件常量池与运行时常量池的区别和联系，以及它们在类加载过程中的转换机制"
author: "wuxl"
date: 2025-11-01
---
## 问题

什么是Class常量池，和运行时常量池关系是什么？

## 答案

### 核心概念

- **Class常量池（Class Constant Pool）**：存在于`.class`文件中的静态常量池，编译期生成
- **运行时常量池（Runtime Constant Pool）**：JVM加载Class文件后，将Class常量池的内容存放到方法区的运行时常量池

**关系**：Class常量池是**静态存储结构**，运行时常量池是**运行时数据结构**，后者由前者在类加载时生成。

### Class常量池详解

#### 1. **定义与位置**

Class常量池是Class文件结构的一部分，位于文件头部的`constant_pool`表中：

```
ClassFile {
    u4 magic;              // 魔数 0xCAFEBABE
    u2 minor_version;      // 次版本号
    u2 major_version;      // 主版本号
    u2 constant_pool_count; // 常量池计数
    cp_info constant_pool[constant_pool_count-1]; // 常量池
    // ...
}
```

#### 2. **存储内容**

Class常量池存储以下类型的常量：

| 常量类型 | 标签 | 存储内容 | 示例 |
|---------|------|---------|------|
| **字面量** | | | |
| CONSTANT_String | 8 | 字符串字面量 | `"hello"` |
| CONSTANT_Integer | 3 | int字面量 | `100` |
| CONSTANT_Long | 5 | long字面量 | `100L` |
| CONSTANT_Float | 4 | float字面量 | `3.14f` |
| CONSTANT_Double | 6 | double字面量 | `3.14` |
| **符号引用** | | | |
| CONSTANT_Class | 7 | 类/接口的全限定名 | `java/lang/String` |
| CONSTANT_Fieldref | 9 | 字段的符号引用 | `User.name:Ljava/lang/String;` |
| CONSTANT_Methodref | 10 | 方法的符号引用 | `User.getName()Ljava/lang/String;` |
| CONSTANT_InterfaceMethodref | 11 | 接口方法的符号引用 | `List.add(Ljava/lang/Object;)Z` |
| CONSTANT_NameAndType | 12 | 字段/方法的名称和类型 | `name:Ljava/lang/String;` |
| CONSTANT_Utf8 | 1 | UTF-8编码的字符串 | 类名、方法名、字段名 |
| CONSTANT_MethodHandle | 15 | 方法句柄 (JDK 7+) | - |
| CONSTANT_MethodType | 16 | 方法类型 (JDK 7+) | - |
| CONSTANT_InvokeDynamic | 18 | 动态调用点 (JDK 7+) | lambda表达式 |

#### 3. **查看Class常量池**

```bash
# 使用javap查看
javap -v MyClass.class

# 输出示例
Constant pool:
   #1 = Methodref          #6.#20         // java/lang/Object."<init>":()V
   #2 = String             #21            // hello
   #3 = Fieldref           #22.#23        // java/lang/System.out:Ljava/io/PrintStream;
   #4 = Methodref          #24.#25        // java/io/PrintStream.println:(Ljava/lang/String;)V
   #5 = Class              #26            // com/example/MyClass
   // ...
```

### 运行时常量池详解

#### 1. **定义与位置**

运行时常量池是**方法区（Metaspace）**的一部分，每个类都有一个独立的运行时常量池。

**位置演变**：
- **JDK 7之前**：方法区（永久代 PermGen）
- **JDK 8及之后**：方法区（元空间 Metaspace）

#### 2. **生成时机**

在**类加载的准备阶段**，JVM将Class常量池的内容加载到运行时常量池：

```
Class文件加载 → 验证 → 准备阶段
    ↓
Class常量池 → 运行时常量池
```

#### 3. **核心特性**

**动态性**：运行时常量池相比Class常量池具有**动态性**：

```java
// 运行时可以向常量池添加新内容
String str = new String("hello").intern(); // 将字符串添加到字符串常量池
```

**符号引用 → 直接引用**：
- **Class常量池**：存储符号引用（字符串描述）
- **运行时常量池**：解析阶段将符号引用转换为直接引用（内存地址）

### Class常量池 vs 运行时常量池

| 对比项 | Class常量池 | 运行时常量池 |
|-------|------------|-------------|
| **生命周期** | 编译期生成 | 类加载时创建 |
| **存储位置** | `.class`文件 | 方法区（Metaspace） |
| **数据结构** | 静态表结构 | 运行时数据结构 |
| **内容** | 字面量 + 符号引用 | 字面量 + 直接引用（解析后） |
| **动态性** | 固定不变 | 可动态添加（如`String.intern()`） |
| **可见性** | 文件级别 | JVM级别 |

### 实战示例

#### **示例1：Class常量池内容**

```java
public class ConstantPoolDemo {
    private static final String CONSTANT = "Hello";
    private int value = 100;

    public void sayHello() {
        System.out.println(CONSTANT);
    }
}
```

**编译后的Class常量池**（`javap -v ConstantPoolDemo.class`）：

```
Constant pool:
   #1 = Methodref          #2.#3          // java/lang/Object."<init>":()V
   #2 = Class              #4             // java/lang/Object
   #3 = NameAndType        #5:#6          // "<init>":()V
   #4 = Utf8               java/lang/Object
   #5 = Utf8               <init>
   #6 = Utf8               ()V
   #7 = Fieldref           #8.#9          // ConstantPoolDemo.value:I
   #8 = Class              #10            // ConstantPoolDemo
   #9 = NameAndType        #11:#12        // value:I
   #10 = Utf8              ConstantPoolDemo
   #11 = Utf8              value
   #12 = Utf8              I
   #13 = Fieldref          #14.#15        // java/lang/System.out:Ljava/io/PrintStream;
   #14 = Class             #16            // java/lang/System
   #15 = NameAndType       #17:#18        // out:Ljava/io/PrintStream;
   #16 = Utf8              java/lang/System
   #17 = Utf8              out
   #18 = Utf8              Ljava/io/PrintStream;
   #19 = String            #20            // "Hello"
   #20 = Utf8              Hello
   // ...
```

**解读**：
- `#19`：字符串字面量`"Hello"`
- `#7`：字段引用`ConstantPoolDemo.value:I`
- `#13`：字段引用`System.out`

#### **示例2：符号引用到直接引用的转换**

```java
public class ReferenceDemo {
    public static void main(String[] args) {
        User user = new User();
        user.getName(); // 方法调用
    }
}
```

**转换过程**：

```
1. 编译期：
   Class常量池存储 "User.getName()Ljava/lang/String;" （符号引用）

2. 加载期：
   运行时常量池存储 "User.getName()Ljava/lang/String;" （符号引用）

3. 解析期：
   运行时常量池解析为 内存地址0x12345678 （直接引用）

4. 执行期：
   直接通过内存地址调用方法（invokevirtual #2）
```

### 运行时常量池的动态性

```java
public class DynamicConstantPoolDemo {
    public static void main(String[] args) {
        // 编译期："hello"在Class常量池
        String s1 = "hello";

        // 运行期：intern()尝试将字符串加入字符串常量池（运行时常量池的一部分）
        String s2 = new String("world").intern();

        // 运行期：拼接后的字符串可能加入常量池
        String s3 = (s1 + s2).intern();

        System.out.println(s1 == "hello");        // true（来自常量池）
        System.out.println(s2 == "world");        // true（intern()返回常量池引用）
        System.out.println(s3 == "helloworld");   // true（intern()返回常量池引用）
    }
}
```

### 常量池相关的内存区域

```
.class文件（磁盘）
    ↓
Class常量池（静态）
    ↓ 类加载
运行时常量池（方法区/Metaspace）
    ↓ 包含
字符串常量池（堆中，JDK 7+）
```

### 常量池与性能优化

#### **1. 减少Class文件大小**
```java
// 复用常量
// 编译器会自动优化，相同的字面量在常量池中只存储一份
String s1 = "hello";
String s2 = "hello";
String s3 = "hello";
// 常量池中只存储一个"hello"
```

#### **2. 字符串intern优化**
```java
// 大量重复字符串时使用intern()减少内存占用
List<String> list = new ArrayList<>();
for (String line : readLinesFromFile()) {
    list.add(line.intern()); // 重复字符串共享内存
}
```

### 常见面试题

**Q：Class常量池能存储对象吗？**
A：不能。只能存储字面量和符号引用（字符串描述），不能存储对象实例。

**Q：运行时常量池溢出怎么办？**
A：
- JDK 7之前：`OutOfMemoryError: PermGen space`
- JDK 8之后：`OutOfMemoryError: Metaspace`

调优参数：
```bash
# JDK 8+
-XX:MetaspaceSize=128m
-XX:MaxMetaspaceSize=512m
```

### 面试要点总结

1. **Class常量池**：编译期生成，存储在`.class`文件中的静态常量表
2. **运行时常量池**：类加载时从Class常量池生成，存储在方法区（Metaspace）
3. **核心区别**：静态 vs 动态、符号引用 vs 直接引用
4. **转换过程**：Class常量池 → 加载 → 运行时常量池 → 解析 → 直接引用
5. **动态性**：运行时常量池可通过`String.intern()`等动态添加内容
6. **内存位置**：JDK 8之后在元空间（Metaspace），不再在永久代
7. **性能优化**：合理使用常量池减少内存占用，避免大量`intern()`导致常量池膨胀
