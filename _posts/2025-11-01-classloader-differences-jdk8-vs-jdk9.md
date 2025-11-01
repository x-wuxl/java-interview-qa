---
layout: post
title: "JDK 1.8和1.9中类加载器有哪些不同？"
date: 2025-11-01
description: "深入对比JDK 8与JDK 9+类加载器体系的重大变化，包括模块化系统、类加载器结构调整及API变更"
author: "wuxl"
categories: [JVM]
tags: [类加载器, JDK版本差异, JPMS, 模块化, 面试]
---

## 问题

JDK1.8和1.9中类加载器有哪些不同？

## 答案

### 核心变化概述

JDK 9引入了**JPMS（Java Platform Module System，Java平台模块系统）**，导致类加载器体系发生重大变革。主要变化包括类加载器层次结构调整、扩展机制废弃、平台类加载器引入等。

### 类加载器层次结构对比

#### **JDK 8及之前**

```
Bootstrap ClassLoader (启动类加载器)
    ↓ 父类加载器
Extension ClassLoader (扩展类加载器)
    ↓ 父类加载器
Application ClassLoader (应用程序类加载器)
```

#### **JDK 9及之后**

```
Bootstrap ClassLoader (启动类加载器)
    ↓ 父类加载器
Platform ClassLoader (平台类加载器) ← 新增
    ↓ 父类加载器
Application ClassLoader (应用程序类加载器/系统类加载器)
```

### 主要区别详解

#### **1. 扩展类加载器被废弃**

| 特性 | JDK 8 | JDK 9+ |
|------|-------|--------|
| **类加载器名称** | Extension ClassLoader | Platform ClassLoader |
| **实现类** | `sun.misc.Launcher$ExtClassLoader` | `jdk.internal.loader.ClassLoaders$PlatformClassLoader` |
| **加载路径** | `$JAVA_HOME/lib/ext`<br>`java.ext.dirs系统属性` | 由模块系统定义的平台模块 |
| **扩展机制** | 支持（将JAR放入ext目录） | **废弃**（不再支持ext目录） |

**JDK 8示例**：
```bash
# JDK 8可以使用ext目录扩展
cp mylib.jar $JAVA_HOME/jre/lib/ext/
# 自动被所有Java应用加载
```

**JDK 9+替代方案**：
```bash
# 使用 --add-modules 或 --module-path
java --module-path mods --add-modules com.example.mylib -m myapp/com.example.Main
```

#### **2. 平台类加载器（Platform ClassLoader）**

**作用**：
- 加载Java SE平台的所有模块（非java.*包的平台类）
- 加载JDK内部模块（如`java.sql`、`java.xml`等）

**加载内容对比**：

| 类库 | JDK 8 | JDK 9+ |
|------|-------|--------|
| `java.lang.*` | Bootstrap ClassLoader | Bootstrap ClassLoader |
| `javax.swing.*` | Extension ClassLoader | **Platform ClassLoader** |
| `java.sql.*` | Bootstrap ClassLoader | **Platform ClassLoader** |
| `jdk.internal.*` | - | Platform ClassLoader |

#### **3. 模块化系统（JPMS）影响**

**JDK 9引入模块系统**：
```java
// module-info.java
module com.example.myapp {
    requires java.sql;      // 依赖平台模块
    requires java.logging;  // 依赖平台模块
    exports com.example.api; // 导出包
}
```

**类加载行为变化**：

```java
// JDK 8：通过classpath加载所有类
java -cp app.jar:lib1.jar:lib2.jar com.example.Main

// JDK 9+：模块路径 + 类路径混合
java --module-path mods --add-modules java.sql \
     -cp app.jar com.example.Main
```

#### **4. 类加载器API变化**

**JDK 8获取类加载器**：
```java
// JDK 8
ClassLoader extClassLoader =
    ClassLoader.getSystemClassLoader().getParent();
System.out.println(extClassLoader.getClass().getName());
// 输出：sun.misc.Launcher$ExtClassLoader
```

**JDK 9+获取类加载器**：
```java
// JDK 9+
ClassLoader platformClassLoader =
    ClassLoader.getSystemClassLoader().getParent();
System.out.println(platformClassLoader.getClass().getName());
// 输出：jdk.internal.loader.ClassLoaders$PlatformClassLoader

// 新增的getPlatformClassLoader()方法
ClassLoader platform = ClassLoader.getPlatformClassLoader();
```

#### **5. 类可见性规则变化**

**JDK 8**：
```java
// 任何类都可以反射访问JDK内部类
Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
// 成功
```

**JDK 9+**：
```java
// 强封装：默认无法访问内部API
Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
// 抛出 IllegalAccessError

// 需要使用 --add-opens 打开封装
java --add-opens java.base/sun.misc=ALL-UNNAMED \
     -jar myapp.jar
```

#### **6. 类加载路径变化**

| 路径类型 | JDK 8 | JDK 9+ |
|---------|-------|--------|
| **启动类路径** | `-Xbootclasspath` | `-Xbootclasspath`（部分支持） |
| **扩展路径** | `-Djava.ext.dirs` | **废弃**（忽略） |
| **应用类路径** | `-cp`/`-classpath` | `-cp`/`-classpath`（保留） |
| **模块路径** | 无 | `--module-path`/`-p`（新增） |

### 代码示例对比

#### **示例1：列出类加载器层次**

```java
public class ClassLoaderHierarchyDemo {
    public static void main(String[] args) {
        ClassLoader loader = ClassLoaderHierarchyDemo.class.getClassLoader();

        System.out.println("=== 类加载器层次 ===");
        while (loader != null) {
            System.out.println(loader.getClass().getName());
            loader = loader.getParent();
        }
        System.out.println("Bootstrap ClassLoader (null)");
    }
}
```

**JDK 8输出**：
```
=== 类加载器层次 ===
sun.misc.Launcher$AppClassLoader
sun.misc.Launcher$ExtClassLoader
Bootstrap ClassLoader (null)
```

**JDK 9+输出**：
```
=== 类加载器层次 ===
jdk.internal.loader.ClassLoaders$AppClassLoader
jdk.internal.loader.ClassLoaders$PlatformClassLoader
Bootstrap ClassLoader (null)
```

#### **示例2：查看特定类的加载器**

```java
public class ClassLoaderCheckDemo {
    public static void main(String[] args) {
        printClassLoader("java.lang.String");    // 核心类
        printClassLoader("java.sql.Connection"); // 平台类
        printClassLoader("com.example.MyClass"); // 应用类
    }

    static void printClassLoader(String className) {
        try {
            Class<?> clazz = Class.forName(className);
            ClassLoader loader = clazz.getClassLoader();
            System.out.println(className + " -> " +
                (loader == null ? "Bootstrap" : loader.getClass().getName()));
        } catch (ClassNotFoundException e) {
            System.out.println(className + " -> Not Found");
        }
    }
}
```

**JDK 8输出**：
```
java.lang.String -> Bootstrap
java.sql.Connection -> Bootstrap (或 Extension)
com.example.MyClass -> sun.misc.Launcher$AppClassLoader
```

**JDK 9+输出**：
```
java.lang.String -> Bootstrap
java.sql.Connection -> jdk.internal.loader.ClassLoaders$PlatformClassLoader
com.example.MyClass -> jdk.internal.loader.ClassLoaders$AppClassLoader
```

### 迁移注意事项

#### **1. ext目录不再有效**

```bash
# JDK 8：有效
cp mylib.jar $JAVA_HOME/jre/lib/ext/

# JDK 9+：无效，需要改用
java --module-path mods --add-modules mylib.module
# 或者使用classpath
java -cp mylib.jar:app.jar com.example.Main
```

#### **2. 内部API访问受限**

```java
// JDK 8：可以直接访问
import sun.misc.BASE64Encoder;

// JDK 9+：建议使用标准API
import java.util.Base64;

// 或者添加JVM参数
// --add-exports java.base/sun.misc=ALL-UNNAMED
```

#### **3. ClassLoader类型判断**

```java
// JDK 8
if (loader instanceof sun.misc.Launcher.ExtClassLoader) {
    // 处理扩展类加载器
}

// JDK 9+：ExtClassLoader不存在，改用
if (loader == ClassLoader.getPlatformClassLoader()) {
    // 处理平台类加载器
}
```

### 模块化带来的优势

1. **更强的封装性**：内部API不再随意暴露
2. **明确的依赖关系**：模块间依赖清晰可见
3. **更小的运行时镜像**：`jlink`工具可创建精简JRE
4. **更好的性能**：类加载更高效，减少类路径扫描

### 面试要点总结

1. **核心变化**：Extension ClassLoader → Platform ClassLoader
2. **ext目录废弃**：不再支持`$JAVA_HOME/lib/ext`扩展机制
3. **模块化系统**：JDK 9引入JPMS，改变类加载和可见性规则
4. **新增API**：`ClassLoader.getPlatformClassLoader()`
5. **强封装**：默认无法访问JDK内部API（需`--add-opens`）
6. **类加载路径**：新增`--module-path`，废弃`-Djava.ext.dirs`
7. **迁移建议**：使用标准API替代内部API，使用模块系统或classpath替代ext目录
