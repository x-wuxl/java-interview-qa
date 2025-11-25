---
title: "两个不相等的对象是否可能拥有相同的 hashCode？"
date: 2025-11-17
description: "深入理解 hashCode 与 equals 的关系，以及哈希冲突的本质"
author: "wuxl"
categories: [Java基础]
tags: [hashCode, equals, 哈希冲突]
nav_order: 24
parent: Java基础
---
## 问题

两个不相等的对象是否可能拥有相同的 hashCode？

## 答案

### 核心结论

**可以**。两个不相等的对象（即 `equals()` 返回 `false`）完全可能拥有相同的 `hashCode()`，这种现象称为**哈希冲突**（Hash Collision）。

### hashCode 与 equals 的契约关系

Java 规范明确定义了 `hashCode()` 和 `equals()` 之间的契约：

1. **如果两个对象相等**（`equals()` 返回 `true`），那么它们**必须**拥有相同的 `hashCode()`
2. **如果两个对象不相等**（`equals()` 返回 `false`），它们的 `hashCode()` **可以相同，也可以不同**
3. **如果两个对象的 `hashCode()` 不同**，那么它们**一定不相等**

这是一个单向约束：相等必须同 hash，但同 hash 不一定相等。

### 为什么会出现哈希冲突？

1. **哈希值空间有限**：`hashCode()` 返回 `int` 类型，取值范围只有 2³² 个（约 42 亿），而对象的可能状态是无限的
2. **哈希算法的映射特性**：任何哈希算法都是将无限空间映射到有限空间，必然存在多对一的情况
3. **性能与分布的权衡**：好的 `hashCode()` 实现追求均匀分布，但不可能完全避免冲突

### 实际场景示例

```java
public class HashCodeDemo {
    public static void main(String[] args) {
        // 示例1：字符串的哈希冲突
        String str1 = "Aa";
        String str2 = "BB";

        System.out.println(str1.hashCode());  // 2112
        System.out.println(str2.hashCode());  // 2112
        System.out.println(str1.equals(str2)); // false

        // 示例2：自定义对象
        Person p1 = new Person("张三", 25);
        Person p2 = new Person("李四", 25);

        // 如果只根据 age 计算 hashCode
        System.out.println(p1.hashCode() == p2.hashCode()); // true
        System.out.println(p1.equals(p2)); // false
    }
}

class Person {
    private String name;
    private int age;

    public Person(String name, int age) {
        this.name = name;
        this.age = age;
    }

    @Override
    public int hashCode() {
        // 简化示例：仅根据 age 计算（实际应包含所有关键字段）
        return age;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;
        Person person = (Person) obj;
        return age == person.age && name.equals(person.name);
    }
}
```

### 在集合中的影响

在 `HashMap`、`HashSet` 等基于哈希表的集合中：

1. **先比较 hashCode**：快速定位到哈希桶（bucket）
2. **再用 equals 判断**：在同一个桶内通过 `equals()` 逐一比较，解决哈希冲突

```java
// HashMap 的 put 操作简化逻辑
int hash = key.hashCode();
int index = hash & (table.length - 1);  // 定位桶位置

// 在桶内遍历链表/红黑树，用 equals 判断是否为同一个 key
for (Node node : bucket[index]) {
    if (node.hash == hash && node.key.equals(key)) {
        // 找到相同的 key，更新 value
        return oldValue;
    }
}
// 未找到，添加新节点
```

### 性能优化考量

1. **良好的 hashCode 实现**：应尽量减少冲突，提升哈希表性能
2. **避免频繁 equals 调用**：如果 `hashCode()` 分布均匀，大部分情况下不需要调用 `equals()`
3. **JDK 8 优化**：当哈希桶内元素超过 8 个时，链表会转为红黑树，将查找复杂度从 O(n) 降至 O(log n)

### 面试答题要点

1. **明确回答"可以"**，并说明这是哈希冲突
2. **阐述契约关系**：相等必同 hash，同 hash 不一定相等
3. **解释原因**：有限的 int 空间无法表示无限的对象状态
4. **举例说明**：字符串 "Aa" 和 "BB" 的 hashCode 相同
5. **关联集合**：HashMap 通过 hashCode 定位桶，再用 equals 解决冲突

这道题考察对 Java 对象契约的理解，以及哈希表底层原理的掌握程度。
