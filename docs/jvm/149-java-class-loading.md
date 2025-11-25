---
layout: default
title: "Java类加载流程与过程"
parent: JVM
nav_order: 149
description: "深入剖析Java类加载机制、双亲委派模型及类加载的完整生命周期"
author: "wuxl"
date: 2025-11-01
---
## 问题

Java类加载流程和过程是什么？

## 答案

### 类加载的生命周期

Java类从被加载到JVM内存到卸载出内存,整个生命周期包括7个阶段：

```
加载 → 验证 → 准备 → 解析 → 初始化 → 使用 → 卸载
└───────── 连接 ───────┘
```

### 1. 加载（Loading）

#### 核心任务

通过类的全限定名获取二进制字节流，并创建Class对象。

```java
// 触发加载的方式
Class<?> clazz = Class.forName("com.example.User"); // 显式加载
User user = new User(); // 隐式加载
```

#### 具体操作

1. **获取字节流**：从不同来源读取.class文件
   ```
   - 本地文件系统（.class文件）
   - JAR/WAR包
   - 网络（Applet）
   - 数据库
   - 运行时动态生成（动态代理、CGLIB）
   ```

2. **转换为方法区数据结构**：将字节流转为运行时数据结构

3. **创建Class对象**：在堆中生成Class对象作为访问入口

```java
// ClassLoader.loadClass()源码简化
protected Class<?> loadClass(String name, boolean resolve) {
    // 1. 检查类是否已加载
    Class<?> c = findLoadedClass(name);

    if (c == null) {
        // 2. 委派给父加载器（双亲委派）
        if (parent != null) {
            c = parent.loadClass(name, false);
        } else {
            c = findBootstrapClassOrNull(name);
        }

        // 3. 父加载器无法加载，自己加载
        if (c == null) {
            c = findClass(name); // 读取字节流
        }
    }

    // 4. 如果需要，进行解析
    if (resolve) {
        resolveClass(c);
    }

    return c;
}
```

### 2. 验证（Verification）

确保Class文件的字节流符合JVM规范，保证安全性。

#### 验证内容

| 验证阶段 | 检查内容 | 示例 |
|---------|---------|------|
| **文件格式验证** | 魔数(0xCAFEBABE)、版本号 | class文件格式正确性 |
| **元数据验证** | 语义分析 | 是否有父类、抽象类是否实现方法 |
| **字节码验证** | 数据流和控制流分析 | 类型转换合法性、跳转指令正确性 |
| **符号引用验证** | 符号引用转直接引用 | 类/字段/方法的访问性检查 |

```java
// 字节码验证示例
public void method() {
    String s = "hello";
    int i = (int) s; // ❌ 验证失败：String不能转int
}
```

**跳过验证**（不推荐）：
```bash
java -Xverify:none MyClass
```

### 3. 准备（Preparation）

为**类变量**（static变量）分配内存并设置**零值**。

```java
public class PrepareExample {
    private static int a = 10;        // 准备阶段：a = 0
    private static final int b = 20;  // 准备阶段：b = 20（常量直接赋值）
    private int c = 30;                // 准备阶段：不处理（实例变量）
}
```

**零值对照表**：

| 数据类型 | 零值 |
|---------|------|
| int | 0 |
| long | 0L |
| float | 0.0f |
| double | 0.0d |
| boolean | false |
| char | '\u0000' |
| reference | null |

**注意**：
- `static final` 常量在准备阶段直接赋值
- 真正的初始化（a=10）在初始化阶段执行

### 4. 解析（Resolution）

将常量池中的**符号引用**替换为**直接引用**。

#### 符号引用 vs 直接引用

```java
// 源码
public class Client {
    public void call() {
        Service service = new Service();
        service.doWork();
    }
}

// 编译后的常量池（符号引用）
#1 = Class           #2  // com/example/Service
#2 = Utf8            com/example/Service
#3 = Methodref       #1.#4  // Service.doWork:()V

// 解析后（直接引用）
Service类的内存地址 → 0x12345678
doWork()方法的入口地址 → 0xABCDEF00
```

**解析内容**：
1. 类或接口解析
2. 字段解析
3. 方法解析
4. 接口方法解析

### 5. 初始化（Initialization）

执行类构造器 `<clinit>()` 方法，真正初始化类变量。

#### <clinit>方法生成

```java
public class InitExample {
    private static int a = 10;
    private static int b;

    static {
        b = 20;
        c = 30;
    }

    private static int c = 40;
}

// 编译器生成的<clinit>()方法（伪代码）
static void <clinit>() {
    a = 10;        // 赋值语句
    b = 20;        // static块
    c = 30;        // static块
    c = 40;        // 赋值语句（覆盖前面的30）
}

// 最终结果：a=10, b=20, c=40
```

#### 初始化时机

**主动引用**（触发初始化）：

```java
// 1. 创建实例
User user = new User();

// 2. 访问静态变量/方法
int value = MyClass.staticVar;
MyClass.staticMethod();

// 3. 反射调用
Class.forName("com.example.User");

// 4. 初始化子类时，先初始化父类
class Child extends Parent { }
new Child(); // 先初始化Parent

// 5. main方法所在的类
public static void main(String[] args) { }

// 6. MethodHandle调用
MethodHandle mh = ...;
mh.invoke();
```

**被动引用**（不触发初始化）：

```java
// 1. 通过子类引用父类静态字段
class Parent {
    public static int value = 10;
}
class Child extends Parent { }

int v = Child.value; // 只初始化Parent，不初始化Child

// 2. 数组定义
User[] users = new User[10]; // 不初始化User

// 3. 常量
class Constants {
    public static final String NAME = "张三";
}
String name = Constants.NAME; // 不初始化Constants（编译期已优化）
```

#### 初始化顺序

```java
public class InitOrder {
    // 父类
    static class Parent {
        static {
            System.out.println("1. 父类静态块");
        }

        {
            System.out.println("3. 父类构造块");
        }

        public Parent() {
            System.out.println("4. 父类构造函数");
        }
    }

    // 子类
    static class Child extends Parent {
        static {
            System.out.println("2. 子类静态块");
        }

        {
            System.out.println("5. 子类构造块");
        }

        public Child() {
            System.out.println("6. 子类构造函数");
        }
    }

    public static void main(String[] args) {
        new Child();
    }
}

// 输出顺序：
// 1. 父类静态块
// 2. 子类静态块
// 3. 父类构造块
// 4. 父类构造函数
// 5. 子类构造块
// 6. 子类构造函数
```

### 类加载器（ClassLoader）

#### 类加载器层次

```
Bootstrap ClassLoader（启动类加载器）
        ↑
Extension ClassLoader（扩展类加载器）
        ↑
Application ClassLoader（应用类加载器）
        ↑
Custom ClassLoader（自定义类加载器）
```

| 类加载器 | 加载路径 | 实现 |
|---------|---------|------|
| **Bootstrap** | `$JAVA_HOME/jre/lib`（rt.jar等） | C++实现 |
| **Extension** | `$JAVA_HOME/jre/lib/ext` | Java实现 |
| **Application** | classpath | Java实现 |
| **Custom** | 自定义路径 | 继承ClassLoader |

```java
// 查看类加载器
public class ClassLoaderTest {
    public static void main(String[] args) {
        // 应用类加载器
        ClassLoader appLoader = ClassLoaderTest.class.getClassLoader();
        System.out.println(appLoader);
        // sun.misc.Launcher$AppClassLoader@18b4aac2

        // 扩展类加载器
        ClassLoader extLoader = appLoader.getParent();
        System.out.println(extLoader);
        // sun.misc.Launcher$ExtClassLoader@1b6d3586

        // 启动类加载器（null，C++实现）
        ClassLoader bootstrapLoader = extLoader.getParent();
        System.out.println(bootstrapLoader);
        // null

        // String类由启动类加载器加载
        ClassLoader stringLoader = String.class.getClassLoader();
        System.out.println(stringLoader);
        // null
    }
}
```

### 双亲委派模型

#### 工作流程

```
1. 收到类加载请求
2. 委派给父加载器（递归）
3. 父加载器无法加载时，自己加载
```

```java
protected Class<?> loadClass(String name, boolean resolve) {
    // 1. 检查是否已加载
    Class<?> c = findLoadedClass(name);

    if (c == null) {
        try {
            // 2. 委派给父加载器
            if (parent != null) {
                c = parent.loadClass(name, false);
            } else {
                // 父加载器为null，使用Bootstrap ClassLoader
                c = findBootstrapClassOrNull(name);
            }
        } catch (ClassNotFoundException e) {
            // 父加载器抛出异常，说明无法加载
        }

        if (c == null) {
            // 3. 父加载器无法加载，自己加载
            c = findClass(name);
        }
    }

    return c;
}
```

#### 优势

1. **避免重复加载**：父加载器已加载的类，子加载器不会再加载
2. **安全性**：防止核心类被篡改

```java
// 尝试自定义java.lang.String
package java.lang;

public class String {
    // 恶意代码
}

// 加载时会委派给Bootstrap ClassLoader
// Bootstrap加载的是JDK自带的String
// 自定义String不会被加载 ✅
```

### 自定义类加载器

```java
public class MyClassLoader extends ClassLoader {
    private String classPath;

    public MyClassLoader(String classPath) {
        this.classPath = classPath;
    }

    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        try {
            // 1. 读取class文件
            byte[] data = loadClassData(name);

            // 2. 转换为Class对象
            return defineClass(name, data, 0, data.length);
        } catch (Exception e) {
            throw new ClassNotFoundException(name);
        }
    }

    private byte[] loadClassData(String name) throws IOException {
        String fileName = classPath + "/" + name.replace('.', '/') + ".class";
        try (FileInputStream fis = new FileInputStream(fileName);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {

            byte[] buffer = new byte[1024];
            int len;
            while ((len = fis.read(buffer)) != -1) {
                baos.write(buffer, 0, len);
            }
            return baos.toByteArray();
        }
    }
}

// 使用
MyClassLoader loader = new MyClassLoader("/custom/path");
Class<?> clazz = loader.loadClass("com.example.MyClass");
Object obj = clazz.newInstance();
```

### 破坏双亲委派

#### 场景1：JDBC驱动加载

```java
// DriverManager由Bootstrap ClassLoader加载
// 但需要加载厂商的JDBC驱动（由Application ClassLoader加载）
// 使用线程上下文类加载器打破双亲委派

Thread.currentThread().setContextClassLoader(appClassLoader);
ServiceLoader<Driver> loader = ServiceLoader.load(Driver.class);
```

#### 场景2：Tomcat

```
Bootstrap ClassLoader
    ↑
System ClassLoader
    ↑
Common ClassLoader → Catalina ClassLoader
    ↑                    ↑
Shared ClassLoader   Webapp ClassLoader
```

### 实战应用

#### 热部署

```java
public class HotSwapClassLoader extends ClassLoader {
    @Override
    public Class<?> loadClass(String name) throws ClassNotFoundException {
        // 不委派给父加载器，直接加载（破坏双亲委派）
        if (name.startsWith("com.myapp")) {
            return findClass(name);
        }
        return super.loadClass(name);
    }
}

// 实现热部署
HotSwapClassLoader loader1 = new HotSwapClassLoader();
Class<?> clazz1 = loader1.loadClass("com.myapp.Service");

// 修改Service.class后
HotSwapClassLoader loader2 = new HotSwapClassLoader();
Class<?> clazz2 = loader2.loadClass("com.myapp.Service");

// clazz1 != clazz2（不同的Class对象）
```

### 答题总结

Java类加载分为**加载、验证、准备、解析、初始化**五个阶段：
1. **加载**：读取字节流，创建Class对象
2. **验证**：确保class文件符合JVM规范
3. **准备**：为static变量分配内存并设置零值
4. **解析**：符号引用转直接引用
5. **初始化**：执行`<clinit>()`方法，真正初始化类变量

**类加载器**采用**双亲委派模型**：先委派给父加载器，父加载器无法加载时才自己加载。优势是避免重复加载和保证核心类安全。特殊场景（JDBC、Tomcat）会打破双亲委派以满足需求。
