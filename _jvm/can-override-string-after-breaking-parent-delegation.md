---
title: "破坏双亲委派之后，能重写String类吗？"
date: 2025-11-01
description: "深入理解破坏双亲委派模型后为什么仍然无法重写JDK核心类如String的技术原因和安全机制"
author: "wuxl"
categories: [JVM]
tags: [类加载器, 双亲委派, JVM安全, 面试]
nav_order: 154
parent: JVM
---
## 问题

破坏双亲委派之后,能重写String类吗?

## 答案

### 核心结论

**不能**。即使完全破坏双亲委派机制，也无法重写`java.lang.String`等JDK核心类。这是由JVM的**多重安全机制**保障的，而非仅依赖双亲委派模型。

### 原因分析

#### 1. **包访问权限限制（核心防护）**

JVM在`ClassLoader.preDefineClass()`方法中有严格检查：

```java
// ClassLoader.java 源码
private ProtectionDomain preDefineClass(String name, ProtectionDomain pd) {
    if (!checkName(name))
        throw new NoClassDefFoundError("IllegalName: " + name);

    // 检查是否以 "java." 开头
    if ((name != null) && name.startsWith("java.")) {
        throw new SecurityException(
            "Prohibited package name: " +
            name.substring(0, name.lastIndexOf('.')));
    }
    // ...
}
```

**结果**：任何自定义类加载器尝试加载`java.*`包下的类都会抛出`SecurityException`。

#### 2. **启动类加载器优先权**

即使绕过包名检查，双亲委派（未完全破坏的情况下）仍会确保：

```java
// 尝试加载 java.lang.String
ClassLoader customLoader = new CustomClassLoader();
Class<?> stringClass = customLoader.loadClass("java.lang.String");

// 实际结果：由启动类加载器（Bootstrap ClassLoader）加载
System.out.println(stringClass.getClassLoader()); // null（启动类加载器）
```

#### 3. **类的唯一性判定**

JVM判断两个类是否相同的条件：
```java
类相同 = 类的全限定名相同 + 加载它的ClassLoader相同
```

即使自定义类加载器成功加载了一个名为`java.lang.String`的类，它与JDK的`String`也是**不同的类**：

```java
// 假设绕过了所有检查（实际不可能）
Class<?> customString = customLoader.loadClass("java.lang.String");
Class<?> jdkString = String.class;

// customString != jdkString（不同的类）
System.out.println(customString == jdkString); // false
```

### 实战验证

#### **尝试1：自定义String类**

```java
// 创建 MyClassLoader.java
public class MyClassLoader extends ClassLoader {
    @Override
    public Class<?> loadClass(String name) throws ClassNotFoundException {
        // 破坏双亲委派：自己先加载
        if (name.equals("java.lang.String")) {
            byte[] classData = loadClassData(name);
            return defineClass(name, classData, 0, classData.length);
        }
        return super.loadClass(name);
    }

    private byte[] loadClassData(String name) {
        // 读取自定义的 String.class 文件
        // ...
    }
}

// 测试
public class Test {
    public static void main(String[] args) throws Exception {
        MyClassLoader loader = new MyClassLoader();
        Class<?> clazz = loader.loadClass("java.lang.String");
    }
}
```

**运行结果**：
```
Exception in thread "main" java.lang.SecurityException:
Prohibited package name: java.lang
```

#### **尝试2：修改包名检查（理论分析）**

即使通过修改JVM源码或使用native方法绕过包名检查，仍然面临问题：

```java
// 假设成功加载了自定义的 java.lang.String
Class<?> myString = customLoader.loadClass("java.lang.String");

// 问题1：无法替换已加载的官方String
String str = "hello"; // 使用的仍是官方String

// 问题2：类型不兼容
Object obj = myString.newInstance();
String realStr = (String) obj; // ClassCastException！
```

### JVM的多层防护机制

```
第1层：双亲委派模型
  ↓ 破坏后
第2层：包访问权限检查（java.* 禁止）
  ↓ 绕过后
第3层：类加载器命名空间隔离
  ↓ 绕过后
第4层：安全管理器（SecurityManager）检查
  ↓ 绕过后
第5层：JVM底层的类型检查
```

### 为什么需要这么多层防护？

#### **安全性考量**

如果允许重写核心类，可能导致：

```java
// 恶意重写的 String 类
package java.lang;

public class String {
    private char[] value;

    public String(String original) {
        // 窃取敏感信息
        sendToHacker(original);
        this.value = original.value;
    }

    private void sendToHacker(String data) {
        // 上传用户数据到黑客服务器
    }
}
```

#### **稳定性考量**

核心类如`String`、`Object`、`Class`等被整个JVM和标准库依赖：

```java
// 如果String被替换，所有依赖String的代码都会出问题
HashMap<String, Object> map = new HashMap<>(); // 可能崩溃
System.out.println("hello"); // 可能崩溃
```

### 特殊场景：Instrumentation

**唯一合法的核心类修改方式**是使用Java Agent的`Instrumentation` API：

```java
// Java Agent 方式
public class MyAgent {
    public static void premain(String agentArgs, Instrumentation inst) {
        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader,
                                  String className,
                                  Class<?> classBeingRedefined,
                                  ProtectionDomain protectionDomain,
                                  byte[] classfileBuffer) {
                if ("java/lang/String".equals(className)) {
                    // 可以修改字节码（仅限于增强，不能破坏原有逻辑）
                    return modifyStringClass(classfileBuffer);
                }
                return null;
            }
        });
    }
}
```

**限制**：
- 必须在JVM启动时通过`-javaagent`参数加载
- 只能增强现有方法，不能完全替换类
- 受到严格的权限检查

### 其他核心类保护

同样受保护的包还有：
```java
java.*          // 核心类库
javax.*         // 扩展类库
sun.*           // 私有实现（不建议使用）
com.sun.*       // 私有实现
jdk.*           // JDK内部实现（JDK 9+）
```

### 实战对比：可替换的普通类

```java
// 可以替换自己的类
public class CustomClassLoader extends ClassLoader {
    @Override
    public Class<?> loadClass(String name) throws ClassNotFoundException {
        // 可以替换 com.myapp.MyClass
        if (name.equals("com.myapp.MyClass")) {
            byte[] classData = loadClassData(name);
            return defineClass(name, classData, 0, classData.length);
        }
        return super.loadClass(name);
    }
}

// 应用场景
// 1. 热部署（Tomcat）
// 2. 插件系统
// 3. 代码动态生成（CGLIB、Javassist）
```

### 面试要点总结

1. **核心结论**：破坏双亲委派后仍然**无法重写String**等核心类
2. **主要原因**：JVM的包访问权限检查（`java.*`包禁止自定义类加载器加载）
3. **多重防护**：双亲委派只是第一层，还有包名检查、类命名空间、安全管理器等
4. **类的唯一性**：即使加载成功，由不同ClassLoader加载的同名类也是不同的类
5. **合法方式**：使用Java Agent的Instrumentation API进行字节码增强（有限制）
6. **安全考量**：防止恶意代码替换核心类导致安全漏洞和系统崩溃
7. **实际应用**：普通应用类可以通过自定义类加载器实现热部署和动态加载
