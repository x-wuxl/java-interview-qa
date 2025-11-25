---
title: "双亲委派机制如何打破（详细补充）"
date: 2025-11-01
description: "详细剖析打破双亲委派模型的多种方式，包括实战代码示例、典型场景分析及注意事项"
author: "wuxl"
categories: [JVM]
tags: [类加载器, 双亲委派, 破坏双亲委派, 实战, 面试]
nav_order: 153
parent: JVM
---
## 问题

双亲委派机制如何打破？

## 答案

### 核心方法

打破双亲委派机制主要通过以下**三种方式**实现：

1. **重写loadClass()方法**（完全破坏）
2. **使用线程上下文类加载器**（父类请求子类加载）
3. **OSGi平行委派模型**（模块化加载）

### 方式1：重写loadClass()方法

#### **标准双亲委派实现**

```java
// ClassLoader.java源码
protected Class<?> loadClass(String name, boolean resolve) {
    synchronized (getClassLoadingLock(name)) {
        // 1. 检查类是否已加载
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
                // 父类无法加载
            }

            if (c == null) {
                // 4. 自己尝试加载
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

#### **完全破坏双亲委派**

```java
public class CustomClassLoader extends ClassLoader {

    private String classPath;

    public CustomClassLoader(String classPath) {
        this.classPath = classPath;
    }

    @Override
    public Class<?> loadClass(String name) throws ClassNotFoundException {
        // 破坏点：不调用父类的loadClass()

        // 1. 检查是否已加载
        Class<?> c = findLoadedClass(name);
        if (c != null) {
            return c;
        }

        // 2. 自己先尝试加载（破坏双亲委派的关键）
        if (name.startsWith("com.myapp")) {
            try {
                c = findClass(name);
                return c;
            } catch (ClassNotFoundException e) {
                // 加载失败，继续向下
            }
        }

        // 3. 失败后再委派给父类
        return super.loadClass(name);
    }

    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        // 从自定义路径加载字节码
        byte[] classData = loadClassData(name);
        if (classData == null) {
            throw new ClassNotFoundException(name);
        }
        return defineClass(name, classData, 0, classData.length);
    }

    private byte[] loadClassData(String className) {
        String fileName = classPath + "/" +
            className.replace('.', '/') + ".class";
        try (FileInputStream fis = new FileInputStream(fileName);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = fis.read(buffer)) != -1) {
                baos.write(buffer, 0, bytesRead);
            }
            return baos.toByteArray();
        } catch (IOException e) {
            return null;
        }
    }
}
```

#### **测试破坏效果**

```java
public class BreakDelegationDemo {
    public static void main(String[] args) throws Exception {
        // 准备两个版本的同一个类
        // v1/com/myapp/Service.class
        // v2/com/myapp/Service.class

        CustomClassLoader loader1 = new CustomClassLoader("v1");
        CustomClassLoader loader2 = new CustomClassLoader("v2");

        // 加载不同版本的类
        Class<?> serviceV1 = loader1.loadClass("com.myapp.Service");
        Class<?> serviceV2 = loader2.loadClass("com.myapp.Service");

        // 验证：两个类不同（破坏双亲委派的结果）
        System.out.println(serviceV1 == serviceV2); // false

        // 创建实例并调用方法
        Object instanceV1 = serviceV1.newInstance();
        Object instanceV2 = serviceV2.newInstance();

        serviceV1.getMethod("printVersion").invoke(instanceV1);
        // 输出：Service Version 1

        serviceV2.getMethod("printVersion").invoke(instanceV2);
        // 输出：Service Version 2
    }
}
```

### 方式2：线程上下文类加载器

#### **典型场景：JDBC驱动加载**

**问题背景**：
```
DriverManager（由启动类加载器加载）
    ↓ 需要加载
MySQL驱动（com.mysql.jdbc.Driver，在classpath中）
    ↑
应用类加载器加载

矛盾：父类加载器（启动）需要请求子类加载器（应用）加载类
→ 违反双亲委派的自下而上流程
```

**解决方案**：

```java
// DriverManager.java (JDK源码)
public class DriverManager {
    static {
        loadInitialDrivers();
    }

    private static void loadInitialDrivers() {
        // 使用ServiceLoader加载驱动
        AccessController.doPrivileged(new PrivilegedAction<Void>() {
            public Void run() {
                // 关键：使用线程上下文类加载器
                ServiceLoader<Driver> loadedDrivers =
                    ServiceLoader.load(Driver.class);

                Iterator<Driver> driversIterator = loadedDrivers.iterator();
                while (driversIterator.hasNext()) {
                    driversIterator.next();
                }
                return null;
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

**工作流程**：

```
1. JVM启动 → 加载DriverManager（启动类加载器）
2. DriverManager静态块执行
3. 调用ServiceLoader.load()
4. ServiceLoader使用线程上下文类加载器（应用类加载器）
5. 加载classpath下的MySQL驱动类
6. 完成驱动注册
```

#### **自定义SPI实现**

```java
public class SPIDemo {
    public static void main(String[] args) throws Exception {
        // 保存原始类加载器
        ClassLoader originalLoader = Thread.currentThread().getContextClassLoader();

        try {
            // 设置自定义类加载器为线程上下文类加载器
            CustomClassLoader customLoader = new CustomClassLoader("plugins");
            Thread.currentThread().setContextClassLoader(customLoader);

            // 使用SPI机制加载插件
            ServiceLoader<Plugin> plugins = ServiceLoader.load(Plugin.class);
            for (Plugin plugin : plugins) {
                plugin.execute();
            }
        } finally {
            // 恢复原始类加载器
            Thread.currentThread().setContextClassLoader(originalLoader);
        }
    }
}
```

### 方式3：OSGi平行委派模型

#### **OSGi架构**

```
    ┌─────────────┐
    │   Parent    │
    │ ClassLoader │
    └──────┬──────┘
           │
    ┌──────┴──────────────────┐
    │                         │
┌───▼────┐              ┌────▼────┐
│Bundle A│◄────────────►│Bundle B │  ← 平行委派
│Loader  │  互相导入导出  │Loader   │
└────────┘              └─────────┘
```

**特点**：
- Bundle之间可以互相委派（平行关系）
- 不遵循严格的父子关系
- 通过`Export-Package`和`Import-Package`控制可见性

#### **OSGi示例**

```java
// Bundle A的MANIFEST.MF
Bundle-Name: BundleA
Export-Package: com.example.api;version="1.0.0"

// Bundle B的MANIFEST.MF
Bundle-Name: BundleB
Import-Package: com.example.api;version="1.0.0"

// BundleB可以使用BundleA导出的类
// 即使它们是平行的类加载器关系
```

### Tomcat的自定义类加载器

#### **Tomcat类加载器层次**

```
Bootstrap ClassLoader
    ↓
System ClassLoader
    ↓
Common ClassLoader（Tomcat共享类库）
    ↓
├─ Catalina ClassLoader（Tomcat内部类）
└─ Shared ClassLoader（所有Web应用共享）
    ↓
    ├─ WebApp1 ClassLoader（破坏双亲委派）
    └─ WebApp2 ClassLoader（破坏双亲委派）
```

#### **WebappClassLoader实现**

```java
// Tomcat的WebappClassLoader（简化版）
public class WebappClassLoader extends URLClassLoader {

    @Override
    public Class<?> loadClass(String name, boolean resolve) {
        Class<?> clazz = null;

        // 1. 先从本地缓存查找
        clazz = findLoadedClass(name);
        if (clazz != null) {
            return clazz;
        }

        // 2. 从系统类加载器查找（避免覆盖JDK类）
        try {
            clazz = getSystemClassLoader().loadClass(name);
            if (clazz != null) {
                return clazz;
            }
        } catch (ClassNotFoundException e) {
            // 忽略
        }

        // 3. 破坏双亲委派：先自己加载
        // （优先加载WEB-INF/classes和WEB-INF/lib）
        if (name.startsWith("org.") || name.startsWith("com.myapp")) {
            try {
                clazz = findClass(name);
                if (clazz != null) {
                    return clazz;
                }
            } catch (ClassNotFoundException e) {
                // 继续
            }
        }

        // 4. 最后委派给父类加载器
        if (clazz == null) {
            clazz = super.loadClass(name, resolve);
        }

        return clazz;
    }
}
```

**优势**：
```java
// 不同Web应用可以使用不同版本的库
webapp1/WEB-INF/lib/spring-5.0.jar
webapp2/WEB-INF/lib/spring-4.3.jar
// 两者互不影响，实现应用隔离
```

### 热部署实现

```java
public class HotDeployManager {
    private Map<String, CustomClassLoader> loaders = new ConcurrentHashMap<>();
    private Map<String, Object> instances = new ConcurrentHashMap<>();

    public void deploy(String appName, String classPath) throws Exception {
        // 创建新的类加载器
        CustomClassLoader newLoader = new CustomClassLoader(classPath);
        loaders.put(appName, newLoader);

        // 加载应用主类
        Class<?> mainClass = newLoader.loadClass("com.myapp.Main");
        Object instance = mainClass.newInstance();
        instances.put(appName, instance);

        // 启动应用
        mainClass.getMethod("start").invoke(instance);
    }

    public void undeploy(String appName) throws Exception {
        // 停止应用
        Object instance = instances.remove(appName);
        instance.getClass().getMethod("stop").invoke(instance);

        // 移除类加载器引用
        CustomClassLoader loader = loaders.remove(appName);
        loader = null;

        // 触发GC，卸载类
        System.gc();
    }

    public void redeploy(String appName, String classPath) throws Exception {
        undeploy(appName);
        Thread.sleep(1000); // 等待GC
        deploy(appName, classPath);
    }
}
```

### 注意事项

#### **1. 核心类无法覆盖**

```java
// 即使破坏双亲委派，也无法加载java.*包
public class MyClassLoader extends ClassLoader {
    @Override
    public Class<?> loadClass(String name) {
        if (name.startsWith("java.")) {
            // 抛出SecurityException
            // Prohibited package name: java.lang
        }
        // ...
    }
}
```

#### **2. 类型转换问题**

```java
CustomClassLoader loader1 = new CustomClassLoader("v1");
CustomClassLoader loader2 = new CustomClassLoader("v2");

Class<?> class1 = loader1.loadClass("com.myapp.User");
Class<?> class2 = loader2.loadClass("com.myapp.User");

Object obj1 = class1.newInstance();

// 错误：ClassCastException
Object obj2 = (class2类型) obj1;
```

#### **3. 单例模式失效**

```java
// 不同类加载器会创建不同的单例实例
Singleton instance1 = loader1.loadClass("Singleton").getInstance();
Singleton instance2 = loader2.loadClass("Singleton").getInstance();

System.out.println(instance1 == instance2); // false
```

### 面试要点总结

1. **三种破坏方式**：重写loadClass()、线程上下文类加载器、OSGi平行委派
2. **典型应用场景**：JDBC SPI、Tomcat应用隔离、OSGi模块化、热部署
3. **Tomcat实现**：WebappClassLoader先自己加载WEB-INF下的类
4. **JDBC SPI**：通过线程上下文类加载器实现父类请求子类加载
5. **核心限制**：无法覆盖`java.*`核心类（安全机制）
6. **注意陷阱**：类型转换异常、单例模式失效、内存泄漏风险
7. **热部署原理**：创建新ClassLoader加载新类，旧ClassLoader被GC回收
