---
layout: post
title: "什么是泛型？有什么好处？"
date: 2025-11-01
description: "深入理解Java泛型的概念、优势及应用场景"
author: "wuxl"
categories: [Java基础]
tags: [泛型, 类型安全, 编译检查, 集合框架]
---

## 问题

什么是泛型？有什么好处？

## 答案

### 核心概念

**泛型（Generics）** 是JDK 5引入的特性，允许在定义类、接口、方法时使用**类型参数**，在使用时指定具体类型，实现**参数化类型**。

### 基本语法

#### 1. 泛型类

```java
// 定义泛型类
public class Box<T> {
    private T data;

    public void set(T data) {
        this.data = data;
    }

    public T get() {
        return data;
    }
}

// 使用泛型类
Box<String> stringBox = new Box<>();
stringBox.set("Hello");
String value = stringBox.get(); // 无需强制转换

Box<Integer> intBox = new Box<>();
intBox.set(100);
Integer num = intBox.get();
```

#### 2. 泛型接口

```java
// 定义泛型接口
public interface Comparable<T> {
    int compareTo(T other);
}

// 实现泛型接口
public class User implements Comparable<User> {
    private String name;
    private int age;

    @Override
    public int compareTo(User other) {
        return Integer.compare(this.age, other.age);
    }
}
```

#### 3. 泛型方法

```java
// 定义泛型方法
public class ArrayUtils {
    // 静态泛型方法
    public static <T> void swap(T[] array, int i, int j) {
        T temp = array[i];
        array[i] = array[j];
        array[j] = temp;
    }

    // 实例泛型方法
    public <E> void printArray(E[] array) {
        for (E element : array) {
            System.out.print(element + " ");
        }
    }
}

// 使用
String[] names = {"Alice", "Bob", "Charlie"};
ArrayUtils.swap(names, 0, 2); // 编译器推断T为String

Integer[] numbers = {1, 2, 3};
ArrayUtils.swap(numbers, 0, 1); // 编译器推断T为Integer
```

### 泛型的好处

#### 1. 类型安全（编译期检查）

**没有泛型时**：

```java
// JDK 5之前
List list = new ArrayList();
list.add("字符串");
list.add(100); // 可以添加任何类型
list.add(new Date());

// 运行时类型转换错误
String str = (String) list.get(1); // ❌ ClassCastException
```

**使用泛型后**：

```java
// JDK 5之后
List<String> list = new ArrayList<>();
list.add("字符串");
// list.add(100); // ❌ 编译错误：类型不匹配

String str = list.get(0); // ✅ 无需强制转换
```

**优势**：将运行时错误提前到编译期发现。

#### 2. 消除强制类型转换

**没有泛型**：

```java
Map map = new HashMap();
map.put("key", "value");

// 需要强制转换
String value = (String) map.get("key");
```

**使用泛型**：

```java
Map<String, String> map = new HashMap<>();
map.put("key", "value");

// 无需强制转换
String value = map.get("key"); // ✅
```

#### 3. 代码复用

**没有泛型时**：需要为每种类型编写重复代码

```java
// 整数栈
public class IntStack {
    private int[] data;
    public void push(int value) { ... }
    public int pop() { ... }
}

// 字符串栈
public class StringStack {
    private String[] data;
    public void push(String value) { ... }
    public String pop() { ... }
}

// ... 需要为每种类型都写一遍
```

**使用泛型**：一套代码支持所有类型

```java
public class Stack<T> {
    private T[] data;

    public void push(T value) { ... }
    public T pop() { ... }
}

// 使用
Stack<Integer> intStack = new Stack<>();
Stack<String> stringStack = new Stack<>();
Stack<User> userStack = new Stack<>();
```

#### 4. 更好的可读性

```java
// 没有泛型：不清楚List存储什么类型
List list = getUserList();

// 使用泛型：一眼看出存储User对象
List<User> users = getUserList();
```

### 泛型应用场景

#### 1. 集合框架

```java
// List
List<String> names = new ArrayList<>();
List<Integer> numbers = new LinkedList<>();

// Set
Set<User> userSet = new HashSet<>();

// Map
Map<String, User> userMap = new HashMap<>();
Map<Long, Order> orderMap = new TreeMap<>();
```

#### 2. 工具类设计

```java
// 通用响应封装
public class Result<T> {
    private int code;
    private String message;
    private T data;

    public static <T> Result<T> success(T data) {
        Result<T> result = new Result<>();
        result.code = 200;
        result.data = data;
        return result;
    }

    public static <T> Result<T> error(String message) {
        Result<T> result = new Result<>();
        result.code = 500;
        result.message = message;
        return result;
    }
}

// 使用
Result<User> userResult = Result.success(user);
Result<List<Order>> orderResult = Result.success(orders);
```

#### 3. DAO层设计

```java
// 通用DAO接口
public interface BaseDao<T, ID> {
    T findById(ID id);
    List<T> findAll();
    void save(T entity);
    void update(T entity);
    void deleteById(ID id);
}

// 具体实现
public class UserDao implements BaseDao<User, Long> {
    @Override
    public User findById(Long id) {
        // 实现细节
    }

    @Override
    public List<User> findAll() {
        // 实现细节
    }
}

public class OrderDao implements BaseDao<Order, String> {
    @Override
    public Order findById(String id) {
        // 实现细节
    }
}
```

#### 4. 回调接口

```java
// 通用回调接口
public interface Callback<T> {
    void onSuccess(T result);
    void onError(Exception e);
}

// 异步任务
public class AsyncTask<T> {
    public void execute(Callback<T> callback) {
        try {
            T result = doInBackground();
            callback.onSuccess(result);
        } catch (Exception e) {
            callback.onError(e);
        }
    }

    protected T doInBackground() {
        // 具体实现
        return null;
    }
}

// 使用
AsyncTask<String> task = new AsyncTask<>();
task.execute(new Callback<String>() {
    @Override
    public void onSuccess(String result) {
        System.out.println("成功: " + result);
    }

    @Override
    public void onError(Exception e) {
        System.err.println("失败: " + e.getMessage());
    }
});
```

### 泛型的限制

#### 1. 不能实例化类型参数

```java
public class Box<T> {
    // ❌ 错误：不能直接new T()
    // private T instance = new T();

    // ✅ 正确：通过反射或工厂方法
    private T instance;

    public Box(Class<T> clazz) throws Exception {
        this.instance = clazz.newInstance();
    }
}
```

#### 2. 不能创建泛型数组

```java
// ❌ 错误
// T[] array = new T[10];

// ✅ 正确：使用通配符或反射
@SuppressWarnings("unchecked")
T[] array = (T[]) new Object[10];

// 或者
T[] array = (T[]) Array.newInstance(clazz, 10);
```

#### 3. 静态字段不能使用类型参数

```java
public class Box<T> {
    // ❌ 错误：静态字段不能使用T
    // private static T staticField;

    // ✅ 正确：实例字段可以
    private T instanceField;
}
```

#### 4. 不能用基本类型

```java
// ❌ 错误：不能使用基本类型
// List<int> numbers = new ArrayList<>();

// ✅ 正确：使用包装类型
List<Integer> numbers = new ArrayList<>();
```

### 多类型参数

```java
// 多个类型参数
public class Pair<K, V> {
    private K key;
    private V value;

    public Pair(K key, V value) {
        this.key = key;
        this.value = value;
    }

    public K getKey() { return key; }
    public V getValue() { return value; }
}

// 使用
Pair<String, Integer> pair1 = new Pair<>("年龄", 25);
Pair<Long, User> pair2 = new Pair<>(1L, user);
```

### 泛型与继承

```java
// 父类泛型
public class Animal<T> {
    private T attribute;
}

// 子类可以指定具体类型
public class Dog extends Animal<String> {
    // attribute的类型为String
}

// 子类也可以保持泛型
public class Cat<T> extends Animal<T> {
    // attribute的类型仍为T
}

// 子类可以有自己的泛型参数
public class Bird<T, E> extends Animal<T> {
    private E extraAttribute;
}
```

### 实战案例

#### 分页结果封装

```java
public class PageResult<T> {
    private int pageNum;      // 当前页码
    private int pageSize;     // 每页大小
    private long total;       // 总记录数
    private List<T> data;     // 数据列表

    // 计算总页数
    public int getTotalPages() {
        return (int) Math.ceil((double) total / pageSize);
    }

    // 是否有下一页
    public boolean hasNext() {
        return pageNum < getTotalPages();
    }

    // Getter/Setter
}

// 使用
PageResult<User> userPage = userService.findUsers(1, 10);
PageResult<Order> orderPage = orderService.findOrders(2, 20);
```

#### 构建器模式

```java
public class QueryBuilder<T> {
    private Class<T> entityClass;
    private List<String> conditions = new ArrayList<>();

    public QueryBuilder(Class<T> entityClass) {
        this.entityClass = entityClass;
    }

    public QueryBuilder<T> where(String field, Object value) {
        conditions.add(field + " = '" + value + "'");
        return this;
    }

    public QueryBuilder<T> and(String field, Object value) {
        conditions.add("AND " + field + " = '" + value + "'");
        return this;
    }

    public List<T> execute() {
        String sql = "SELECT * FROM " + entityClass.getSimpleName()
            + " WHERE " + String.join(" ", conditions);
        // 执行SQL查询
        return Collections.emptyList();
    }
}

// 使用（链式调用）
List<User> users = new QueryBuilder<>(User.class)
    .where("age", 25)
    .and("city", "北京")
    .execute();
```

### 答题总结

**泛型**是Java的参数化类型机制，允许在定义类/接口/方法时使用类型参数，使用时指定具体类型。

**主要好处**：
1. **类型安全**：编译期检查，将运行时错误提前到编译期
2. **消除强制转换**：自动类型推断，代码更简洁
3. **代码复用**：一套代码支持多种类型
4. **可读性更好**：代码意图更清晰

**典型应用**：集合框架、通用工具类、DAO层设计、响应封装、回调接口等。泛型是现代Java开发的基础特性，在框架设计和业务开发中广泛使用。
