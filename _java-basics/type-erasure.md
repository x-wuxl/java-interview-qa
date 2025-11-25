---
title: "什么是类型擦除"
date: 2025-11-01
description: "深入剖析Java泛型的类型擦除机制、原理及其影响"
author: "wuxl"
categories: [Java基础]
tags: [泛型, 类型擦除, 字节码, JVM]
nav_order: 61
parent: Java基础
---
## 问题

什么是类型擦除？

## 答案

### 核心概念

**类型擦除（Type Erasure）** 是Java泛型的实现机制：编译器在编译期检查泛型类型，编译后**擦除所有泛型信息**，运行时泛型类型不存在。

### 类型擦除原理

#### 1. 编译前的源代码

```java
public class Box<T> {
    private T data;

    public void set(T data) {
        this.data = data;
    }

    public T get() {
        return data;
    }
}

// 使用
Box<String> stringBox = new Box<>();
stringBox.set("Hello");
String value = stringBox.get();
```

#### 2. 编译后的字节码

```java
// 类型参数T被擦除为Object
public class Box {
    private Object data; // T → Object

    public void set(Object data) { // T → Object
        this.data = data;
    }

    public Object get() { // T → Object
        return data;
    }
}

// 使用处插入强制类型转换
Box stringBox = new Box();
stringBox.set("Hello");
String value = (String) stringBox.get(); // 编译器自动插入强转
```

#### 3. 字节码验证

使用 `javap -c` 查看字节码：

```java
// 源码
public T get() {
    return data;
}

// 字节码
public java.lang.Object get();
  Code:
     0: aload_0
     1: getfield      #2  // Field data:Ljava/lang/Object;
     4: areturn
```

**结论**：泛型类型T在字节码中变成了Object。

### 擦除规则

#### 规则1：无限定类型参数擦除为Object

```java
// 源码
public class Box<T> {
    private T data;
}

// 擦除后
public class Box {
    private Object data; // T → Object
}
```

#### 规则2：有限定类型参数擦除为限定类型

```java
// 源码：上界限定
public class NumberBox<T extends Number> {
    private T data;

    public void process() {
        double value = data.doubleValue(); // 可以调用Number的方法
    }
}

// 擦除后
public class NumberBox {
    private Number data; // T extends Number → Number

    public void process() {
        double value = data.doubleValue();
    }
}
```

```java
// 源码：多个上界
public class MyClass<T extends Comparable<T> & Serializable> {
    private T data;
}

// 擦除后（擦除为第一个边界）
public class MyClass {
    private Comparable data; // 擦除为Comparable
}
```

#### 规则3：方法的类型参数也会被擦除

```java
// 源码
public <T> T getFirst(List<T> list) {
    return list.get(0);
}

// 擦除后
public Object getFirst(List list) { // T → Object, List<T> → List
    return list.get(0);
}
```

### 类型擦除的影响

#### 1. 运行时无法获取泛型类型

```java
List<String> stringList = new ArrayList<>();
List<Integer> intList = new ArrayList<>();

// 运行时类型相同
System.out.println(stringList.getClass() == intList.getClass()); // true

// 无法判断泛型类型
if (stringList instanceof List<String>) { // ❌ 编译错误
    // 非法的泛型类型
}

// 只能判断原始类型
if (stringList instanceof List) { // ✅ 正确
    // 合法
}
```

#### 2. 不能创建泛型数组

```java
// ❌ 错误：不能创建泛型数组
List<String>[] arrayOfLists = new List<String>[10]; // 编译错误

// ✅ 正确：可以创建原始类型数组
List[] arrayOfLists = new List[10];

// ✅ 或使用通配符
List<?>[] arrayOfLists = new List<?>[10];
```

**原因**：

```java
// 如果允许创建泛型数组，会导致类型不安全
Object[] arr = new List<String>[10]; // 假设允许
arr[0] = new ArrayList<Integer>(); // 数组协变，运行时类型擦除，无法检测
List<String> list = (List<String>) arr[0];
String s = list.get(0); // ClassCastException
```

#### 3. 重载冲突

```java
public class OverloadTest {
    // ❌ 错误：方法签名冲突
    public void process(List<String> list) { }
    public void process(List<Integer> list) { } // 编译错误

    // 原因：擦除后都变成 process(List list)
}
```

```java
// ✅ 正确：通过不同参数个数或类型区分
public void process(List<String> list) { }
public void process(List<String> list, int flag) { }
public void process(Set<Integer> set) { }
```

#### 4. 异常捕获限制

```java
// ❌ 错误：不能捕获泛型异常
try {
    // ...
} catch (T e) { // 编译错误
    // ...
}

// ❌ 错误：泛型类不能继承Throwable
public class MyException<T> extends Exception { } // 编译错误
```

#### 5. 静态上下文限制

```java
public class Box<T> {
    // ❌ 错误：静态方法不能使用类的类型参数
    public static T staticMethod() { // 编译错误
        return null;
    }

    // ✅ 正确：静态方法可以有自己的类型参数
    public static <E> E genericStaticMethod() {
        return null;
    }
}
```

### 桥接方法（Bridge Method）

类型擦除会导致方法覆盖问题，编译器通过**桥接方法**解决。

```java
// 父类
public class Node<T> {
    private T data;

    public void setData(T data) {
        this.data = data;
    }
}

// 子类
public class IntegerNode extends Node<Integer> {
    @Override
    public void setData(Integer data) {
        System.out.println("Setting integer: " + data);
        super.setData(data);
    }
}
```

**擦除后**：

```java
// 父类擦除后
public class Node {
    public void setData(Object data) { // T → Object
        this.data = data;
    }
}

// 子类擦除后
public class IntegerNode extends Node {
    // 程序员编写的方法
    public void setData(Integer data) {
        System.out.println("Setting integer: " + data);
        super.setData(data);
    }

    // 编译器自动生成的桥接方法
    public void setData(Object data) { // 保持多态
        setData((Integer) data); // 调用Integer版本
    }
}
```

**验证桥接方法**：

```java
IntegerNode node = new IntegerNode();
for (Method method : node.getClass().getDeclaredMethods()) {
    System.out.println(method.getName() + " - isBridge: " + method.isBridge());
}

// 输出：
// setData - isBridge: false  (程序员编写的方法)
// setData - isBridge: true   (编译器生成的桥接方法)
```

### 类型擦除的绕过方式

#### 1. 通过反射获取泛型类型（有限）

```java
// 方式1：通过父类的泛型信息
public abstract class BaseDao<T> {
    private Class<T> entityClass;

    @SuppressWarnings("unchecked")
    public BaseDao() {
        // 获取父类的泛型类型
        Type superclass = getClass().getGenericSuperclass();
        if (superclass instanceof ParameterizedType) {
            ParameterizedType parameterizedType = (ParameterizedType) superclass;
            Type[] typeArguments = parameterizedType.getActualTypeArguments();
            this.entityClass = (Class<T>) typeArguments[0];
        }
    }

    public T newInstance() throws Exception {
        return entityClass.newInstance();
    }
}

// 子类
public class UserDao extends BaseDao<User> {
    // entityClass = User.class
}

// 使用
UserDao dao = new UserDao();
User user = dao.newInstance(); // 可以创建User实例
```

#### 2. 通过构造参数传递Class对象

```java
public class Repository<T> {
    private Class<T> entityClass;

    public Repository(Class<T> entityClass) {
        this.entityClass = entityClass;
    }

    public T newInstance() throws Exception {
        return entityClass.newInstance();
    }

    public List<T> query(String sql) {
        // 使用entityClass进行JDBC查询
        return Collections.emptyList();
    }
}

// 使用
Repository<User> userRepo = new Repository<>(User.class);
User user = userRepo.newInstance();
```

### 类型擦除 vs C++模板

| 维度 | Java泛型（类型擦除） | C++模板 |
|-----|-------------------|---------|
| **实现机制** | 编译期检查 + 运行时擦除 | 代码生成 |
| **字节码** | 只生成一份字节码 | 为每种类型生成代码 |
| **运行时类型** | 不存在 | 存在 |
| **性能** | 有装箱拆箱开销 | 无开销 |
| **代码膨胀** | 无 | 可能膨胀 |
| **向后兼容** | 兼容Java 5之前 | N/A |

```java
// Java：只生成一份Box类的字节码
Box<String> stringBox = new Box<>();
Box<Integer> intBox = new Box<>();
// stringBox.getClass() == intBox.getClass() → true
```

```cpp
// C++：为String和int分别生成代码
Box<std::string> stringBox;
Box<int> intBox;
// typeid(stringBox) != typeid(intBox)
```

### 类型擦除的历史原因

Java在设计泛型时面临的约束：

1. **向后兼容**：必须兼容Java 5之前的代码
2. **JVM改动最小**：不改变JVM字节码格式
3. **库迁移成本**：已有的集合类库需要平滑升级

```java
// Java 5之前
List list = new ArrayList();
list.add("字符串");

// Java 5之后（类型擦除保证兼容）
List<String> list = new ArrayList<>();
list.add("字符串");
// 两者的字节码基本一致
```

### 实战陷阱

#### 陷阱1：无法使用instanceof判断泛型

```java
public <T> void process(Object obj) {
    // ❌ 错误
    if (obj instanceof T) { // 编译错误
        // ...
    }

    // ✅ 正确：传递Class对象
    public <T> void process(Object obj, Class<T> clazz) {
        if (clazz.isInstance(obj)) {
            T t = clazz.cast(obj);
        }
    }
}
```

#### 陷阱2：泛型单例模式

```java
// ❌ 错误：所有类型共享同一实例
public class Singleton<T> {
    private static Singleton<?> instance; // 静态字段

    public static <T> Singleton<T> getInstance() {
        if (instance == null) {
            instance = new Singleton<>();
        }
        return (Singleton<T>) instance;
    }
}

Singleton<String> s1 = Singleton.getInstance();
Singleton<Integer> s2 = Singleton.getInstance();
System.out.println(s1 == s2); // true ← 同一个实例！
```

#### 陷阱3：数组协变与泛型

```java
// 数组是协变的
Object[] objArray = new String[10];
objArray[0] = 100; // ArrayStoreException（运行时检查）

// 泛型不是协变的
List<Object> objList = new ArrayList<String>(); // ❌ 编译错误
```

### 答题总结

**类型擦除**是Java泛型的实现机制：编译器在编译期进行类型检查，编译后擦除所有泛型信息，运行时泛型类型不存在。

**擦除规则**：
- 无限定类型参数擦除为Object（如`T` → `Object`）
- 有限定类型参数擦除为限定类型（如`T extends Number` → `Number`）
- 编译器自动插入类型转换和桥接方法

**主要影响**：
1. 运行时无法获取泛型类型信息
2. 不能创建泛型数组
3. 不能捕获泛型异常
4. 静态上下文无法使用类的类型参数

类型擦除是为了**向后兼容**和**减少JVM改动**而采用的折中方案，虽有局限但保证了平滑升级。可通过反射或传递Class对象部分绕过限制。
