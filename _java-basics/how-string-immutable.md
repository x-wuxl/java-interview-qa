---
title: "String是如何实现不可变的？"
date: 2025-11-01
description: "从源码角度剖析String不可变性的四大实现机制：final类、final字段、私有构造和防御性拷贝"
author: "wuxl"
categories: [Java基础]
tags: [String, 不可变性, final, 源码分析, 设计模式]
nav_order: 28
parent: Java基础
---
## 问题

String是如何实现不可变的？

## 答案

### 1. 核心实现机制

String通过**四个关键设计手段**保证不可变性：

1. **类声明为final** - 防止子类破坏不可变性
2. **内部数组使用final** - 保证引用不可变
3. **私有化内部状态** - 外部无法直接访问
4. **所有方法返回新对象** - 不修改原对象

### 2. 源码剖析

#### JDK 8 实现

```java
public final class String  // ① final类，不能被继承
    implements java.io.Serializable, Comparable<String>, CharSequence {

    /** The value is used for character storage. */
    private final char value[];  // ② final + private，内容不可变

    /** Cache the hash code for the string */
    private int hash; // Default to 0  // ③ hashCode缓存

    // ④ 构造方法进行防御性拷贝
    public String(char value[]) {
        this.value = Arrays.copyOf(value, value.length);  // 拷贝数组，而非直接引用
    }

    // ⑤ 所有"修改"方法都返回新对象
    public String substring(int beginIndex, int endIndex) {
        // ...
        return new String(value, beginIndex, subLen);  // 返回新对象
    }

    public String concat(String str) {
        // ...
        char buf[] = Arrays.copyOf(value, len + otherLen);
        str.getChars(buf, len);
        return new String(buf, true);  // 返回新对象
    }

    public String replace(char oldChar, char newChar) {
        // ...
        char buf[] = new char[len];
        // ... 填充buf
        return new String(buf, true);  // 返回新对象
    }
}
```

#### JDK 9+ 实现（Compact Strings优化）

```java
public final class String
    implements java.io.Serializable, Comparable<String>, CharSequence {

    @Stable
    private final byte[] value;  // 改用byte[]，节省内存

    private final byte coder;  // 编码标识：LATIN1 或 UTF16

    static final byte LATIN1 = 0;
    static final byte UTF16  = 1;

    // 根据字符集选择编码
    public String(char value[], int offset, int count) {
        if (COMPACT_STRINGS) {
            byte[] val = StringUTF16.compress(value, offset, count);
            if (val != null) {
                this.value = val;
                this.coder = LATIN1;  // 使用单字节编码
                return;
            }
        }
        this.coder = UTF16;  // 使用双字节编码
        this.value = StringUTF16.toBytes(value, offset, count);
    }
}
```

### 3. 四大实现技术详解

#### 技术1：final类声明

```java
public final class String {
    // ...
}
```

**作用：**
- 防止被继承，避免子类重写方法破坏不可变性

**假设String不是final：**
```java
// 假设String可以被继承
class MutableString extends String {
    private char[] mutableValue;

    @Override
    public char charAt(int index) {
        return mutableValue[index];  // 返回可变数组的内容
    }

    public void setCharAt(int index, char c) {
        mutableValue[index] = c;  // 破坏不可变性！
    }
}

// 问题：多态调用时无法保证不可变性
String str = new MutableString("hello");
((MutableString) str).setCharAt(0, 'H');  // 修改成功！
```

#### 技术2：final字段

```java
private final char[] value;  // JDK 8
private final byte[] value;  // JDK 9+
```

**作用：**
- `final`保证`value`引用不可变（不能指向新数组）
- `private`保证外部无法直接访问

**重要区别：**
```java
// final保证引用不变，但数组内容理论上可变
private final char[] value = {'h', 'e', 'l', 'l', 'o'};

// 以下操作是非法的（编译错误）
value = new char[]{'w', 'o', 'r', 'l', 'd'};  // ❌ final引用不能修改

// 以下操作理论上可行（如果能访问value的话）
value[0] = 'H';  // ⚠️ 数组内容可变，但String通过private和无修改方法防止了这一点
```

String通过**不暴露修改数组的方法**来保证数组内容不可变。

#### 技术3：防御性拷贝

```java
// 构造方法：拷贝传入的数组
public String(char value[]) {
    this.value = Arrays.copyOf(value, value.length);  // 深拷贝
}

// 错误示例：直接引用（假设）
public String(char value[]) {
    this.value = value;  // ❌ 外部可以修改数组
}
```

**防止外部修改：**
```java
char[] chars = {'h', 'e', 'l', 'l', 'o'};
String str = new String(chars);

// 如果没有防御性拷贝，外部修改会影响String
chars[0] = 'H';  // String内部拷贝了数组，不受影响
System.out.println(str);  // 输出：hello（而非Hello）
```

**返回值的防御性处理：**
```java
// String的toCharArray方法也进行拷贝
public char[] toCharArray() {
    char result[] = new char[value.length];
    System.arraycopy(value, 0, result, 0, value.length);
    return result;  // 返回新数组，防止外部修改内部状态
}
```

#### 技术4：返回新对象而非修改原对象

```java
// substring：返回新String
public String substring(int beginIndex) {
    // ...
    return new String(value, beginIndex, subLen);
}

// concat：返回新String
public String concat(String str) {
    char buf[] = Arrays.copyOf(value, len + otherLen);
    str.getChars(buf, len);
    return new String(buf, true);
}

// replace：返回新String
public String replace(char oldChar, char newChar) {
    // ... 查找替换逻辑
    return new String(buf, true);
}

// toLowerCase：返回新String
public String toLowerCase() {
    // ...
    return new String(result, 0, len + resultOffset);
}
```

**关键点：**
- 所有看似"修改"的方法都创建新对象
- 原对象保持完全不变
- 符合**不可变对象模式**的设计原则

### 4. 反射能否破坏不可变性？

**理论上可以通过反射修改：**
```java
String str = "hello";
System.out.println(str);  // hello

// 通过反射获取value字段
Field valueField = String.class.getDeclaredField("value");
valueField.setAccessible(true);

// JDK 8
char[] value = (char[]) valueField.get(str);
value[0] = 'H';

// JDK 9+
byte[] value = (byte[]) valueField.get(str);
value[0] = 'H';

System.out.println(str);  // Hello - 不可变性被破坏！
```

**警告：**
- 这种做法**极不推荐**，会导致不可预测的行为
- 可能影响字符串常量池中的所有引用
- 破坏hashCode缓存，导致HashMap等数据结构失效

**字符串常量池问题：**
```java
String s1 = "hello";
String s2 = "hello";  // 指向同一对象

// 反射修改s1
Field field = String.class.getDeclaredField("value");
field.setAccessible(true);
char[] value = (char[]) field.get(s1);
value[0] = 'H';

System.out.println(s1);  // Hello
System.out.println(s2);  // Hello - s2也被修改了！
```

### 5. 不可变性的完整保证

```java
// 不可变类的标准实现模式
public final class String {  // ① final类
    private final char[] value;  // ② final + private字段

    public String(char[] value) {  // ③ 防御性拷贝
        this.value = Arrays.copyOf(value, value.length);
    }

    public char[] toCharArray() {  // ④ 返回拷贝
        return Arrays.copyOf(value, value.length);
    }

    public String concat(String str) {  // ⑤ 返回新对象
        // ...
        return new String(buf, true);
    }

    // ⑥ 没有提供任何修改内部状态的公开方法
    // 没有setValue()、setCharAt()等方法
}
```

### 6. 不可变类设计最佳实践

基于String的实现，设计不可变类的通用模式：

```java
public final class ImmutablePerson {
    private final String name;
    private final int age;
    private final List<String> hobbies;

    public ImmutablePerson(String name, int age, List<String> hobbies) {
        this.name = name;
        this.age = age;
        // 防御性拷贝
        this.hobbies = new ArrayList<>(hobbies);
    }

    public String getName() {
        return name;
    }

    public int getAge() {
        return age;
    }

    public List<String> getHobbies() {
        // 返回不可修改的视图
        return Collections.unmodifiableList(hobbies);
    }

    // "修改"方法返回新对象
    public ImmutablePerson withAge(int newAge) {
        return new ImmutablePerson(this.name, newAge, this.hobbies);
    }
}
```

### 7. 面试答题要点

**标准回答结构：**

1. **final类**：防止继承破坏不可变性
2. **final字段**：内部char[]/byte[]使用final修饰，保证引用不变
3. **私有字段**：private修饰，外部无法直接访问
4. **防御性拷贝**：构造方法拷贝传入的数组，返回方法拷贝内部数组
5. **返回新对象**：所有"修改"方法（substring、concat等）都返回新String对象
6. **无修改方法**：不提供任何修改内部状态的公开方法

**加分点：**
- 说明JDK 9的byte[]优化（Compact Strings）
- 提到反射可以破坏不可变性，但不推荐
- 了解不可变对象模式的设计原则
- 能够设计自己的不可变类

### 8. 总结

String的不可变性是通过**语言级别（final）、封装（private）、拷贝（防御性）和设计（无修改方法）**的多层保障实现的：

| 层次 | 技术手段 | 保障内容 |
|------|---------|---------|
| 类级别 | `final class` | 防止继承 |
| 字段级别 | `final` + `private` | 引用不变 + 不可访问 |
| 构造级别 | 防御性拷贝 | 防止外部修改 |
| 方法级别 | 返回新对象 | 不修改原对象 |
| API级别 | 无修改方法 | 无破坏接口 |

这种**纵深防御**的设计思想，使String成为Java中最可靠的不可变类，也是不可变对象模式的典范实现。
