---
layout: post
title: "两个对象的 hashCode 相同，equals 是否一定为 true？"
date: 2025-11-16
description: "深入理解 hashCode 与 equals 的关系，以及哈希冲突的本质原因"
author: "wuxl"
categories: [Java基础]
tags: [hashCode, equals, 哈希冲突, HashMap, 对象比较]
---

## 问题

两个对象的 hashCode 相同，equals 是否一定为 true？

## 答案

### 核心结论

**不一定为 true**。两个对象的 hashCode 相同，只能说明它们可能相等，但不能保证一定相等。这种现象称为**哈希冲突（Hash Collision）**。

### hashCode 与 equals 的约定

Java 规范要求 hashCode 和 equals 必须遵守以下契约：

| 规则 | 说明 | 示例 |
|------|------|------|
| **规则1** | 如果 `a.equals(b)` 为 true，则 `a.hashCode() == b.hashCode()` **必须**为 true | 相等对象必须有相同哈希码 |
| **规则2** | 如果 `a.hashCode() == b.hashCode()`，`a.equals(b)` **不一定**为 true | 哈希码相同不代表对象相等 |
| **规则3** | 如果 `a.equals(b)` 为 false，`a.hashCode()` 和 `b.hashCode()` **可以**相同或不同 | 不相等对象可以有相同哈希码 |

### 原理分析

#### 1. 哈希冲突的本质

```java
public class HashCodeDemo {
    public static void main(String[] args) {
        // 示例1：不同字符串可能有相同 hashCode
        String s1 = "Aa";
        String s2 = "BB";
        System.out.println(s1.hashCode());  // 2112
        System.out.println(s2.hashCode());  // 2112
        System.out.println(s1.equals(s2));  // false

        // 示例2：自定义对象的哈希冲突
        Person p1 = new Person("张三", 25);
        Person p2 = new Person("李四", 25);
        System.out.println(p1.hashCode() == p2.hashCode());  // 可能为 true
        System.out.println(p1.equals(p2));                   // false
    }
}
```

#### 2. 为什么会发生哈希冲突？

```java
// String 的 hashCode 实现（简化版）
public int hashCode() {
    int h = 0;
    for (int i = 0; i < length; i++) {
        h = 31 * h + charAt(i);
    }
    return h;
}

// 计算 "Aa" 的 hashCode
// 'A' = 65, 'a' = 97
// h = 31 * 0 + 65 = 65
// h = 31 * 65 + 97 = 2112

// 计算 "BB" 的 hashCode
// 'B' = 66
// h = 31 * 0 + 66 = 66
// h = 31 * 66 + 66 = 2112

// 结果：不同字符串产生相同哈希码
```

**根本原因**：
- hashCode 返回 int 类型（32位，约 42 亿个值）
- 对象数量理论上无限
- 根据**鸽巢原理**，必然存在不同对象映射到相同哈希码

### HashMap 中的应用

#### 1. HashMap 的存储原理

```java
public class HashMap<K,V> {
    // 简化的 put 方法逻辑
    public V put(K key, V value) {
        int hash = hash(key);           // 1. 计算 hashCode
        int index = hash & (n - 1);     // 2. 定位数组下标
        Node<K,V> node = table[index];  // 3. 获取链表/红黑树头节点

        // 4. 遍历链表，使用 equals 判断是否存在相同 key
        while (node != null) {
            if (node.hash == hash &&
                (node.key == key || key.equals(node.key))) {
                // 找到相同 key，更新 value
                return node.setValue(value);
            }
            node = node.next;
        }

        // 5. 未找到，插入新节点
        addNode(hash, key, value);
        return null;
    }
}
```

#### 2. 查找过程的两步验证

```java
public class HashMapDemo {
    public static void main(String[] args) {
        Map<Person, String> map = new HashMap<>();

        Person p1 = new Person("张三", 25);
        Person p2 = new Person("张三", 25);

        map.put(p1, "员工1");

        // 查找过程：
        // 1. 先比较 hashCode：p2.hashCode() == p1.hashCode()
        // 2. 再比较 equals：p2.equals(p1)
        // 两者都为 true 才认为是同一个 key
        System.out.println(map.get(p2));  // 输出：员工1
    }
}

class Person {
    private String name;
    private int age;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Person person = (Person) o;
        return age == person.age && Objects.equals(name, person.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(name, age);
    }
}
```

### 违反契约的后果

#### 1. 只重写 equals，不重写 hashCode

```java
public class BadPerson {
    private String name;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        BadPerson that = (BadPerson) o;
        return Objects.equals(name, that.name);
    }

    // 未重写 hashCode，使用 Object 的默认实现（基于内存地址）
}

public class Test {
    public static void main(String[] args) {
        BadPerson p1 = new BadPerson("张三");
        BadPerson p2 = new BadPerson("张三");

        System.out.println(p1.equals(p2));  // true

        // 问题：HashMap 无法正确工作
        Map<BadPerson, String> map = new HashMap<>();
        map.put(p1, "员工1");
        System.out.println(map.get(p2));  // null（期望是"员工1"）

        // 原因：p1 和 p2 的 hashCode 不同，定位到不同的桶
        System.out.println(p1.hashCode());  // 例如：123456
        System.out.println(p2.hashCode());  // 例如：789012
    }
}
```

#### 2. hashCode 不一致导致的问题

```java
public class MutableKeyDemo {
    public static void main(String[] args) {
        Map<MutablePerson, String> map = new HashMap<>();

        MutablePerson p = new MutablePerson("张三", 25);
        map.put(p, "员工1");

        // 修改对象状态，导致 hashCode 变化
        p.setAge(26);

        // 无法找到之前存入的值（hashCode 变了，定位到错误的桶）
        System.out.println(map.get(p));  // null

        // HashMap 内部出现"内存泄漏"（无法访问的键值对）
    }
}
```

### 正确实现 hashCode 的原则

#### 1. 使用 Objects.hash() 工具方法

```java
public class Person {
    private String name;
    private int age;
    private String email;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Person person = (Person) o;
        return age == person.age &&
               Objects.equals(name, person.name) &&
               Objects.equals(email, person.email);
    }

    @Override
    public int hashCode() {
        // 推荐：使用 Objects.hash()
        return Objects.hash(name, age, email);
    }
}
```

#### 2. 手动实现高质量 hashCode

```java
public class Person {
    private String name;
    private int age;

    @Override
    public int hashCode() {
        int result = 17;  // 初始值（非零质数）

        // 每个字段乘以质数（通常用 31）再累加
        result = 31 * result + (name != null ? name.hashCode() : 0);
        result = 31 * result + age;

        return result;
    }
}
```

**为什么选择 31？**
- 31 是质数，减少哈希冲突
- `31 * i == (i << 5) - i`，JVM 可优化为位运算
- 经验值，广泛应用于 JDK 源码

### 性能优化考量

#### 1. 缓存 hashCode（不可变对象）

```java
public final class ImmutablePerson {
    private final String name;
    private final int age;
    private int hashCode;  // 缓存 hashCode

    @Override
    public int hashCode() {
        int result = hashCode;
        if (result == 0) {  // 延迟计算
            result = 17;
            result = 31 * result + name.hashCode();
            result = 31 * result + age;
            hashCode = result;
        }
        return result;
    }
}
```

#### 2. 避免使用可变字段

```java
public class GoodPerson {
    private final String id;      // 不可变字段
    private String name;          // 可变字段
    private int age;              // 可变字段

    @Override
    public int hashCode() {
        // 只使用不可变字段计算 hashCode
        return Objects.hash(id);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        GoodPerson that = (GoodPerson) o;
        return Objects.equals(id, that.id);
    }
}
```

### 实际案例分析

```java
public class HashCollisionDemo {
    public static void main(String[] args) {
        // 案例1：String 的哈希冲突
        Set<String> set = new HashSet<>();
        set.add("Aa");
        set.add("BB");
        System.out.println(set.size());  // 2（虽然 hashCode 相同，但 equals 不同）

        // 案例2：Integer 的 hashCode 就是其值
        Integer i1 = 100;
        Integer i2 = 100;
        System.out.println(i1.hashCode() == i2.hashCode());  // true
        System.out.println(i1.equals(i2));                   // true

        // 案例3：自定义对象
        Person p1 = new Person("张三", 25);
        Person p2 = new Person("李四", 25);
        // 如果 hashCode 只基于 age，则 hashCode 相同但 equals 为 false
    }
}
```

### 答题总结

**面试要点**：
1. **直接回答**：hashCode 相同，equals 不一定为 true，这是哈希冲突
2. **契约关系**：
   - `equals 为 true → hashCode 必须相同`（强制）
   - `hashCode 相同 → equals 不一定为 true`（允许冲突）
3. **原因分析**：hashCode 是 int 类型（有限），对象数量无限，必然冲突
4. **HashMap 应用**：先用 hashCode 定位桶，再用 equals 遍历链表查找
5. **最佳实践**：
   - 重写 equals 必须重写 hashCode
   - 使用 `Objects.hash()` 或遵循 31 倍累加算法
   - 不可变对象可缓存 hashCode
   - 避免使用可变字段计算 hashCode

**记忆口诀**：
- equals 相等，hashCode 必相等
- hashCode 相等，equals 不一定
- 重写 equals，别忘 hashCode
