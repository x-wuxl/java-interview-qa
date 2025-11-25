---
layout: default
title: "泛型中上下界限定符extends和super有什么区别"
parent: Java基础
nav_order: 63
description: "深入理解Java泛型通配符的上界与下界限定及PECS原则"
author: "wuxl"
date: 2025-11-01
---
## 问题

泛型中上下界限定符extends和super有什么区别？

## 答案

### 核心概念

- **上界通配符（Upper Bounded Wildcard）**：`<? extends T>` - 限定类型为T或T的**子类**
- **下界通配符（Lower Bounded Wildcard）**：`<? super T>` - 限定类型为T或T的**父类**

### 语法与含义

#### 1. 上界通配符 - extends

```java
// 定义：接受Number及其子类
public void process(List<? extends Number> list) {
    // ...
}

// 调用
List<Integer> ints = Arrays.asList(1, 2, 3);
List<Double> doubles = Arrays.asList(1.5, 2.5);
List<Number> numbers = Arrays.asList(1, 2.5);

process(ints);    // ✅ Integer extends Number
process(doubles); // ✅ Double extends Number
process(numbers); // ✅ Number本身
```

**类型层次**：

```
Number (上界)
  ├─ Integer
  ├─ Double
  ├─ Long
  └─ Float
```

#### 2. 下界通配符 - super

```java
// 定义：接受Integer及其父类
public void addNumbers(List<? super Integer> list) {
    // ...
}

// 调用
List<Integer> ints = new ArrayList<>();
List<Number> numbers = new ArrayList<>();
List<Object> objects = new ArrayList<>();

addNumbers(ints);    // ✅ Integer本身
addNumbers(numbers); // ✅ Number是Integer的父类
addNumbers(objects); // ✅ Object是Integer的父类
```

**类型层次**：

```
Object
  └─ Number
       └─ Integer (下界)
```

### 读写权限差异

#### 上界通配符（extends）：只读

```java
public void readList(List<? extends Number> list) {
    // ✅ 读取：可以读，返回值为Number
    Number num = list.get(0);
    double value = num.doubleValue();

    // ❌ 写入：不能写（编译错误）
    // list.add(new Integer(1));  // 编译错误
    // list.add(new Double(2.5)); // 编译错误
    // list.add(new Number());    // 编译错误

    // 唯一可以添加的是null
    list.add(null); // ✅
}
```

**原因**：编译器不知道list的确切类型

```java
List<Integer> ints = new ArrayList<>();
List<? extends Number> list = ints;

// 如果允许添加
// list.add(new Double(2.5)); // ❌ Double不能放入List<Integer>
```

#### 下界通配符（super）：只写

```java
public void writeList(List<? super Integer> list) {
    // ✅ 写入：可以写Integer及其子类
    list.add(new Integer(1));
    list.add(100); // 自动装箱为Integer

    // ❌ 读取：只能读出Object（编译器不知道确切类型）
    Object obj = list.get(0); // ✅ 只能当作Object

    // Integer num = list.get(0); // ❌ 编译错误
}
```

**原因**：编译器不知道list的确切类型

```java
List<Number> numbers = new ArrayList<>();
List<? super Integer> list = numbers;

// 写入安全
list.add(100); // ✅ Integer可以存入List<Number>

// 读取不安全
// Integer num = list.get(0); // ❌ 实际可能是Number或Object
```

### PECS原则

**PECS：Producer Extends, Consumer Super**

- **生产者（Producer）**：如果只需要**读取**数据，使用 `<? extends T>`
- **消费者（Consumer）**：如果只需要**写入**数据，使用 `<? super T>`

#### 示例1：复制列表

```java
// Collections.copy() 源码
public static <T> void copy(List<? super T> dest,
                             List<? extends T> src) {
    for (T item : src) {      // src是生产者，读取数据
        dest.add(item);       // dest是消费者，写入数据
    }
}

// 使用
List<Integer> ints = Arrays.asList(1, 2, 3);
List<Number> numbers = new ArrayList<>();

Collections.copy(numbers, ints);
// src: List<? extends T> → 读取Integer
// dest: List<? super T> → 写入Number（Integer的父类）
```

#### 示例2：查找最大值

```java
// 生产者：只需要读取元素进行比较
public static <T extends Comparable<? super T>> T max(List<? extends T> list) {
    if (list.isEmpty()) {
        throw new IllegalArgumentException("Empty list");
    }

    T maxElement = list.get(0);
    for (T element : list) {  // 只读取，不写入
        if (element.compareTo(maxElement) > 0) {
            maxElement = element;
        }
    }
    return maxElement;
}

// 使用
List<Integer> ints = Arrays.asList(1, 5, 3);
Integer max = max(ints); // 5
```

#### 示例3：添加所有元素

```java
// 消费者：只需要写入元素
public static <T> void addAll(List<? super T> dest, List<? extends T> src) {
    for (T item : src) {
        dest.add(item);  // 只写入，不读取
    }
}

// 使用
List<Integer> src = Arrays.asList(1, 2, 3);
List<Number> dest = new ArrayList<>();

addAll(dest, src);
// dest: List<? super Integer> → 写入
// src: List<? extends Integer> → 读取
```

### 多层继承关系示例

```java
// 类层次
class Animal { }
class Dog extends Animal { }
class Puppy extends Dog { }

// 上界通配符
public void processDogs(List<? extends Dog> dogs) {
    // 可以接受
    List<Dog> dogList = Arrays.asList(new Dog());
    List<Puppy> puppyList = Arrays.asList(new Puppy());

    processDogs(dogList);   // ✅
    processDogs(puppyList); // ✅

    // 读取
    Dog dog = dogs.get(0); // ✅ 至少是Dog

    // 写入
    // dogs.add(new Dog());   // ❌ 编译错误
    // dogs.add(new Puppy()); // ❌ 编译错误
}

// 下界通配符
public void addDogs(List<? super Dog> list) {
    // 可以接受
    List<Dog> dogList = new ArrayList<>();
    List<Animal> animalList = new ArrayList<>();
    List<Object> objectList = new ArrayList<>();

    addDogs(dogList);     // ✅
    addDogs(animalList);  // ✅
    addDogs(objectList);  // ✅

    // 写入
    list.add(new Dog());   // ✅
    list.add(new Puppy()); // ✅ Puppy是Dog的子类

    // 读取
    Object obj = list.get(0); // ✅ 只能当作Object
    // Dog dog = list.get(0);   // ❌ 编译错误
}
```

### 对比表格

| 特性 | `<? extends T>` | `<? super T>` |
|-----|----------------|--------------|
| **类型范围** | T及其子类 | T及其父类 |
| **读取操作** | ✅ 可以读，返回T | ⚠️ 只能读出Object |
| **写入操作** | ❌ 不能写（除null） | ✅ 可以写T及其子类 |
| **典型用途** | 数据提供者（Producer） | 数据消费者（Consumer） |
| **代表方法** | `Collections.max()` | `Collections.copy()` |

### 实战应用

#### 1. Stream API

```java
// Stream.max() 使用上界通配符
public interface Stream<T> {
    Optional<T> max(Comparator<? super T> comparator);
    //                        ↑ 下界通配符
}

// 使用
Stream<Integer> stream = Stream.of(1, 5, 3);
Optional<Integer> max = stream.max(Comparator.naturalOrder());
```

#### 2. 集合工具类

```java
public class CollectionUtils {
    // 查找：上界通配符（读取）
    public static <T extends Comparable<? super T>> T findMax(
            List<? extends T> list) {
        // 实现
        return null;
    }

    // 添加：下界通配符（写入）
    public static <T> void addAll(
            List<? super T> dest,
            List<? extends T> src) {
        dest.addAll(src);
    }

    // 过滤：上界通配符（读取）
    public static <T> List<T> filter(
            List<? extends T> list,
            Predicate<? super T> predicate) {
        // 实现
        return null;
    }
}
```

#### 3. DAO层设计

```java
public interface BaseDao<T> {
    // 查询：返回T的子类列表（上界）
    <S extends T> List<S> findAll(Class<S> subClass);

    // 保存：接受T及其子类（上界）
    <S extends T> void save(S entity);

    // 批量保存：接受T及其子类的列表
    <S extends T> void saveAll(List<? extends S> entities);
}
```

### 常见陷阱

#### 陷阱1：混淆上下界

```java
// ❌ 错误：想要写入，却用了extends
public void addItems(List<? extends Number> list) {
    // list.add(100); // 编译错误
}

// ✅ 正确：使用super
public void addItems(List<? super Integer> list) {
    list.add(100); // ✅
}
```

#### 陷阱2：不必要的通配符

```java
// ❌ 过度使用通配符
public <T> void process(List<? extends T> list) {
    // 如果只需要T，不需要通配符
}

// ✅ 简化
public <T> void process(List<T> list) {
    // 足够了
}
```

#### 陷阱3：不能同时读写

```java
// ❌ 既想读又想写
public void processNumbers(List<? extends Number> list) {
    Number num = list.get(0);  // ✅ 可以读
    // list.add(100);           // ❌ 不能写
}

// ✅ 如果需要读写，使用具体类型
public void processNumbers(List<Number> list) {
    Number num = list.get(0);  // ✅
    list.add(100);              // ✅
}
```

### 高级用法

#### 递归类型限定

```java
// Comparable接口使用递归限定
public interface Comparable<T> {
    int compareTo(T other);
}

// 确保元素可以与自己比较
public static <T extends Comparable<T>> T max(List<T> list) {
    // ...
}

// 更灵活的版本（允许父类实现Comparable）
public static <T extends Comparable<? super T>> T max(List<? extends T> list) {
    // ...
}

// 示例：子类继承父类的Comparable实现
class Parent implements Comparable<Parent> {
    @Override
    public int compareTo(Parent other) { return 0; }
}

class Child extends Parent {
    // 继承了Comparable<Parent>，而不是Comparable<Child>
}

List<Child> children = Arrays.asList(new Child());
Child max = max(children); // 使用 <? super T> 才能编译通过
```

### 答题总结

**上界通配符 `<? extends T>`**：
- 类型范围：T及其子类
- 操作特点：**只读不写**（生产者）
- 使用场景：从集合中**读取**数据进行处理

**下界通配符 `<? super T>`**：
- 类型范围：T及其父类
- 操作特点：**只写不读**（消费者）
- 使用场景：向集合中**写入**数据

**PECS原则**：
- **Producer Extends**（生产者用extends）
- **Consumer Super**（消费者用super）

典型应用：`Collections.copy(List<? super T> dest, List<? extends T> src)` - 源列表是生产者（读取），目标列表是消费者（写入）。

