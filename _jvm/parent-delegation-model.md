---
title: "什么是双亲委派？如何破坏？"
date: 2025-11-01
description: "深入理解Java双亲委派模型的工作原理、设计目的、破坏方式及典型应用场景"
author: "wuxl"
categories: [JVM]
tags: [类加载器, 双亲委派, JVM, 面试]
nav_order: 151
parent: JVM
---
## 问题

什么是双亲委派？如何破坏？

## 答案

### 核心概念

**双亲委派模型**（Parent Delegation Model）是Java类加载器的工作机制：当一个类加载器收到类加载请求时，首先不会自己尝试加载，而是委派给父类加载器完成，只有父类加载器无法完成时，子类加载器才尝试自己加载。

### 类加载器的层次结构

```
启动类加载器（Bootstrap ClassLoader）
    ↑ 父类加载器
扩展类加载器（Extension ClassLoader）
    ↑ 父类加载器
应用程序类加载器（Application ClassLoader）
    ↑ 父类加载器
自定义类加载器（Custom ClassLoader）
```

#### 三种系统类加载器

| 类加载器 | 实现语言 | 加载路径 | 典型类 |
|---------|---------|---------|--------|
| **启动类加载器**<br>Bootstrap ClassLoader | C++ | `$JAVA_HOME/lib`<br>或`-Xbootclasspath`指定 | `java.lang.*`<br>`java.util.*` |
| **扩展类加载器**<br>Extension ClassLoader | Java | `$JAVA_HOME/lib/ext`<br>或`java.ext.dirs`指定 | `javax.swing.*`<br>`javax.crypto.*` |
| **应用程序类加载器**<br>Application ClassLoader | Java | `classpath`<br>或`-cp`指定 | 应用程序类 |

### 双亲委派的工作流程

```java
// ClassLoader.java 源码核心逻辑
protected Class<?> loadClass(String name, boolean resolve) {
    synchronized (getClassLoadingLock(name)) {
        // 1. 检查类是否已被加载
        Class<?> c = findLoadedClass(name);

        if (c == null) {
            try {
                if (parent != null) {
                    // 2. 委派给父类加载器
                    c = parent.loadClass(name, false);
                } else {
                    // 3. 父类为null，委派给启动类加载器
                    c = findBootstrapClassOrNull(name);
                }
            } catch (ClassNotFoundException e) {
                // 父类加载器无法加载
            }

            if (c == null) {
                // 4. 父类无法加载，自己加载
                c = findClass(name);
            }
        }

        if (resolve) {
            resolveClass(c);
        }
        return c;
    }
}
```

**流程图**：
```
1. 检查类是否已加载 → 已加载则直接返回
2. 委派给父类加载器 → 父类加载成功则返回
3. 父类加载失败 → 自己调用findClass()加载
4. 都失败 → 抛出ClassNotFoundException
```

### 双亲委派的优势

#### 1. **避免类的重复加载**
```java
// 每个类只会被加载一次
// 父类加载器已加载的类，子类不会再加载
```

#### 2. **保护核心类库安全**
```java
// 自定义 java.lang.String 不会被加载
// 因为启动类加载器已经加载了官方的String类
public class String {
    // 这个类不会替换JDK的String
    static {
        System.out.println("自定义String");
    }
}
```

#### 3. **确保类的唯一性**
```java
// 同一个类文件由同一个类加载器加载
// JVM中类的唯一性 = 类本身 + 加载它的类加载器
```

### 如何破坏双亲委派模型

#### **方式1：重写loadClass()方法**

```java
public class CustomClassLoader extends ClassLoader {

    @Override
    public Class<?> loadClass(String name) throws ClassNotFoundException {
        // 破坏双亲委派：不再委派给父类加载器

        // 1. 检查是否已加载
        Class<?> c = findLoadedClass(name);
        if (c != null) {
            return c;
        }

        // 2. 自己先尝试加载（破坏点）
        try {
            c = findClass(name);
            return c;
        } catch (ClassNotFoundException e) {
            // 3. 失败后再委派给父类
            return super.loadClass(name);
        }
    }

    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        // 自定义加载逻辑
        byte[] classData = loadClassData(name);
        return defineClass(name, classData, 0, classData.length);
    }

    private byte[] loadClassData(String name) {
        // 从自定义路径加载字节码
        // ...
    }
}
```

**注意**：即使破坏双亲委派，也不能加载`java.*`包下的类（受包访问权限保护）。

#### **方式2：使用线程上下文类加载器**

**场景**：SPI（Service Provider Interface）机制

```java
// JDBC驱动加载示例
public class DriverManager {
    static {
        // 启动类加载器加载的类，需要加载classpath下的驱动
        // 通过线程上下文类加载器（应用类加载器）加载
        AccessController.doPrivileged(new PrivilegedAction<Void>() {
            public Void run() {
                ServiceLoader<Driver> loadedDrivers =
                    ServiceLoader.load(Driver.class);
                // ...
            }
        });
    }
}

// ServiceLoader.java
public static <S> ServiceLoader<S> load(Class<S> service) {
    // 获取线程上下文类加载器（默认是应用类加载器）
    ClassLoader cl = Thread.currentThread().getContextClassLoader();
    return ServiceLoader.load(service, cl);
}
```

**原理**：父类加载器请求子类加载器加载类，违反了自下而上的委派方向。

#### **方式3：实现热部署/热替换**

```java
// OSGi/Tomcat等热部署实现
public class HotSwapClassLoader extends ClassLoader {

    @Override
    public Class<?> loadClass(String name) throws ClassNotFoundException {
        // 对于需要热替换的类，不委派给父类
        if (name.startsWith("com.myapp.hotswap")) {
            return findClass(name);
        }
        // 其他类遵循双亲委派
        return super.loadClass(name);
    }
}

// 热部署流程
public void hotDeploy() {
    // 1. 卸载旧的类加载器
    oldClassLoader = null;

    // 2. 创建新的类加载器
    HotSwapClassLoader newClassLoader = new HotSwapClassLoader();

    // 3. 重新加载类
    Class<?> newClass = newClassLoader.loadClass("com.myapp.hotswap.Service");
    Object newInstance = newClass.newInstance();
}
```

### 典型破坏场景

| 场景 | 破坏方式 | 典型应用 |
|------|---------|---------|
| **SPI机制** | 线程上下文类加载器 | JDBC、JNDI、JAXP |
| **热部署** | 自定义loadClass() | Tomcat、OSGi、JRebel |
| **代码隔离** | 平行委派模型 | OSGi Bundle |
| **动态加载** | 完全自定义加载逻辑 | 插件系统、脚本引擎 |

### 实战示例

```java
public class ParentDelegationDemo {
    public static void main(String[] args) throws Exception {
        // 1. 查看类加载器层次
        ClassLoader loader = ParentDelegationDemo.class.getClassLoader();
        while (loader != null) {
            System.out.println(loader);
            loader = loader.getParent();
        }
        System.out.println("Bootstrap ClassLoader (null)");

        // 输出：
        // sun.misc.Launcher$AppClassLoader@xxx (应用类加载器)
        // sun.misc.Launcher$ExtClassLoader@xxx (扩展类加载器)
        // Bootstrap ClassLoader (null) (启动类加载器)

        // 2. 验证双亲委派
        ClassLoader appLoader = ClassLoader.getSystemClassLoader();
        ClassLoader customLoader = new CustomClassLoader();

        // String类一定由启动类加载器加载
        Class<?> stringClass1 = appLoader.loadClass("java.lang.String");
        Class<?> stringClass2 = customLoader.loadClass("java.lang.String");

        System.out.println(stringClass1 == stringClass2); // true
        System.out.println(stringClass1.getClassLoader()); // null（启动类加载器）
    }
}
```

### 面试要点总结

1. **双亲委派模型核心**：先委派父类加载，父类加载失败才自己加载
2. **三层类加载器结构**：启动类加载器 → 扩展类加载器 → 应用程序类加载器
3. **双亲委派的优势**：避免重复加载、保护核心类库、确保类唯一性
4. **破坏方式**：重写loadClass()、线程上下文类加载器、自定义加载逻辑
5. **典型破坏场景**：JDBC的SPI机制、Tomcat的热部署、OSGi的模块化
6. **重要限制**：即使破坏双亲委派，也无法加载`java.*`核心类（安全机制保护）
