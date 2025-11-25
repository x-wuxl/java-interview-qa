---
title: "有了equals为什么还需要hashCode方法"
date: 2025-11-01
description: "深入理解hashCode与equals的关系及在哈希表中的关键作用"
author: "wuxl"
categories: [Java基础]
tags: [hashCode, equals, HashMap, HashSet, 哈希表]
nav_order: 22
parent: Java基础
---
## 问题

有了equals为啥需要hashCode方法？

## 答案

### 核心原因

`hashCode` 是为**哈希表（如HashMap、HashSet）提供高效查找**而设计的。如果只有 `equals` 而没有 `hashCode`，哈希表的性能会从 **O(1)** 退化为 **O(n)**。

### 工作原理

#### 1. HashMap的查找流程

```java
HashMap<User, String> map = new HashMap<>();
User user = new User("张三", 25);
map.put(user, "员工信息");

// 查找过程
String value = map.get(new User("张三", 25));
```

**内部执行流程**：

```
1. 计算key的hashCode → hash = key.hashCode()
2. 根据hash定位数组索引 → index = hash & (table.length - 1)
3. 在该索引的链表/红黑树中遍历
4. 使用equals比较每个节点的key
5. 找到匹配的key，返回value
```

```java
// HashMap.get()源码简化
public V get(Object key) {
    // 步骤1: 计算hashCode
    int hash = hash(key.hashCode());

    // 步骤2: 定位数组索引
    int index = hash & (table.length - 1);

    // 步骤3: 遍历链表
    Node<K,V> node = table[index];
    while (node != null) {
        // 步骤4: 使用equals比较
        if (node.hash == hash &&
            (node.key == key || key.equals(node.key))) {
            return node.value; // 步骤5: 返回结果
        }
        node = node.next;
    }
    return null;
}
```

#### 2. hashCode的作用

**快速定位**：将对象分散到不同的"桶"中，避免全局遍历。

```
假设HashMap有16个桶：

没有hashCode（只能放在同一个桶）:
[0] → user1 → user2 → user3 → ... → user10000
[1]
[2]
...
查找复杂度：O(n)

有hashCode（分散到不同桶）:
[0] → user1 → user5
[1] → user2
[2] → user3 → user9
...
查找复杂度：O(1)
```

### 问题演示

#### 问题1：只重写equals，不重写hashCode

```java
public class User {
    private String name;
    private int age;

    // ✅ 重写了equals
    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (!(obj instanceof User)) return false;
        User other = (User) obj;
        return age == other.age &&
               Objects.equals(name, other.name);
    }

    // ❌ 没有重写hashCode（使用Object默认实现）
}

// 测试
User u1 = new User("张三", 25);
User u2 = new User("张三", 25);

System.out.println(u1.equals(u2)); // true ✅

// 放入HashMap
Map<User, String> map = new HashMap<>();
map.put(u1, "员工1");

// 使用逻辑相等的对象查询
String result = map.get(u2); // null ❌ 期望"员工1"
```

**原因**：
```java
u1.hashCode() // 假设 12345
u2.hashCode() // 假设 67890（不同的内存地址）

// HashMap查找时：
// u2的hashCode定位到不同的桶 → 找不到u1存储的数据
```

#### 问题2：HashSet去重失效

```java
Set<User> set = new HashSet<>();
set.add(new User("张三", 25));
set.add(new User("张三", 25)); // 逻辑相等的对象

System.out.println(set.size()); // 2 ❌ 期望1
```

### equals与hashCode契约

**Java规范要求**：

1. **如果两个对象equals相等，则hashCode必须相等**
   ```java
   if (obj1.equals(obj2)) {
       // 必须保证：
       obj1.hashCode() == obj2.hashCode()
   }
   ```

2. **如果两个对象hashCode相等，equals不一定相等**（哈希冲突）
   ```java
   if (obj1.hashCode() == obj2.hashCode()) {
       // obj1.equals(obj2) 可能为true或false
   }
   ```

3. **不相等的对象，hashCode应该尽量不同**（减少冲突）

### 正确实现

#### 方式1：手动实现

```java
public class User {
    private String name;
    private int age;

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (!(obj instanceof User)) return false;
        User other = (User) obj;
        return age == other.age &&
               Objects.equals(name, other.name);
    }

    @Override
    public int hashCode() {
        // 使用Objects.hash计算多个字段的哈希值
        return Objects.hash(name, age);
    }
}
```

#### 方式2：IDE自动生成

```java
// IDEA: Alt + Insert → equals() and hashCode()
@Override
public boolean equals(Object o) {
    if (this == o) return true;
    if (o == null || getClass() != o.getClass()) return false;
    User user = (User) o;
    return age == user.age && Objects.equals(name, user.name);
}

@Override
public int hashCode() {
    return Objects.hash(name, age);
}
```

#### 方式3：使用Lombok

```java
@Data
@EqualsAndHashCode
public class User {
    private String name;
    private int age;
}
```

### hashCode实现原则

#### 1. 使用关键字段

```java
public class Order {
    private Long id;           // 关键字段
    private String orderNo;    // 关键字段
    private Date createTime;   // 非关键字段
    private BigDecimal amount; // 非关键字段

    @Override
    public int hashCode() {
        // 只使用关键字段（唯一标识）
        return Objects.hash(id, orderNo);
    }
}
```

#### 2. 保持一致性

```java
// ❌ 错误：使用可变字段
public class User {
    private String name; // 可变

    @Override
    public int hashCode() {
        return Objects.hash(name); // name改变后hashCode也变
    }
}

// 测试
User user = new User("张三");
map.put(user, "数据");

user.setName("李四"); // 修改name
map.get(user); // null ❌ 找不到了（hashCode变了）
```

**建议**：
- 不可变类：使用所有字段
- 可变类：只使用不变的标识字段（如ID）

#### 3. 质数优化

```java
// 经典实现（JDK源码风格）
@Override
public int hashCode() {
    int result = 17; // 初始值用质数
    result = 31 * result + (name != null ? name.hashCode() : 0);
    result = 31 * result + age;
    return result;
}

// 为什么用31？
// 1. 31是质数，减少哈希冲突
// 2. 31 * i = (i << 5) - i，JVM可优化为位运算
```

### 性能影响

#### 糟糕的hashCode实现

```java
// ❌ 最差：所有对象返回相同hashCode
@Override
public int hashCode() {
    return 1; // 所有对象哈希冲突
}

// 影响：HashMap退化为链表，O(1) → O(n)
```

```java
// ❌ 次差：使用常量
@Override
public int hashCode() {
    return 100;
}
```

#### 良好的hashCode实现

```java
// ✅ 分布均匀
@Override
public int hashCode() {
    return Objects.hash(id, name, age);
}
```

**JMH性能测试**：

```java
// 100万次查询操作
Map<User, String> map = new HashMap<>();
// ... 插入10000个User对象

// 糟糕的hashCode（返回1）
// 查询时间：500 ms

// 良好的hashCode（Objects.hash）
// 查询时间：2 ms  ← 快250倍
```

### 特殊场景

#### 不可变类

```java
@Immutable
public final class Point {
    private final int x;
    private final int y;

    // 缓存hashCode（不可变对象可以这样优化）
    private int hashCode;

    @Override
    public int hashCode() {
        int result = hashCode;
        if (result == 0) {
            result = 17;
            result = 31 * result + x;
            result = 31 * result + y;
            hashCode = result;
        }
        return result;
    }
}
```

#### 继承关系

```java
public class Employee extends Person {
    private String employeeId;

    @Override
    public boolean equals(Object obj) {
        if (!super.equals(obj)) return false;
        if (!(obj instanceof Employee)) return false;
        Employee other = (Employee) obj;
        return Objects.equals(employeeId, other.employeeId);
    }

    @Override
    public int hashCode() {
        // 包含父类的hashCode
        return Objects.hash(super.hashCode(), employeeId);
    }
}
```

### 常见错误

```java
// ❌ 错误1：只重写equals
@Override
public boolean equals(Object obj) { ... }
// 缺少hashCode实现

// ❌ 错误2：equals和hashCode使用不同字段
@Override
public boolean equals(Object obj) {
    return Objects.equals(this.name, other.name); // 只比较name
}

@Override
public int hashCode() {
    return Objects.hash(name, age); // 包含age
}

// ❌ 错误3：hashCode使用随机数
@Override
public int hashCode() {
    return new Random().nextInt(); // 每次调用结果不同
}
```

### 实战检查清单

```java
// ✅ 完整实现示例
public class Product {
    private Long id;
    private String name;
    private BigDecimal price;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Product product = (Product) o;
        return Objects.equals(id, product.id) &&
               Objects.equals(name, product.name) &&
               Objects.equals(price, product.price);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, name, price);
    }
}

// 验证
Product p1 = new Product(1L, "商品A", new BigDecimal("99.9"));
Product p2 = new Product(1L, "商品A", new BigDecimal("99.9"));

// 1. equals相等
assert p1.equals(p2); // ✅

// 2. hashCode相等
assert p1.hashCode() == p2.hashCode(); // ✅

// 3. HashMap正常工作
Map<Product, Integer> map = new HashMap<>();
map.put(p1, 100);
assert map.get(p2) == 100; // ✅

// 4. HashSet去重
Set<Product> set = new HashSet<>();
set.add(p1);
set.add(p2);
assert set.size() == 1; // ✅
```

### 答题总结

`hashCode` 用于哈希表（HashMap/HashSet）的**快速定位**，将对象分散到不同的桶中，实现O(1)查找。如果只重写 `equals` 而不重写 `hashCode`，会导致：
1. HashMap/HashSet无法正确工作（查询失败、去重失效）
2. 违反Java规范：**equals相等的对象hashCode必须相等**

最佳实践：
1. 同时重写 `equals` 和 `hashCode`
2. 使用相同字段计算（推荐 `Objects.hash()`）
3. 避免使用可变字段或确保不修改
4. IDE自动生成或使用Lombok简化代码
