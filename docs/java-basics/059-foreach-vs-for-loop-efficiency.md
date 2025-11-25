---
layout: default
title: "for-each 与常规 for 循环的效率如何对比？"
parent: Java基础
nav_order: 59
description: "深入分析 for-each 和传统 for 循环的性能差异及适用场景"
author: "wuxl"
date: 2025-11-16
---
## 问题

for-each 与常规 for 循环的效率如何对比？

## 答案

### 核心结论

**效率对比取决于数据结构**：
- **数组**：两者性能几乎相同（编译后字节码一致）
- **ArrayList**：性能相近，for-each 略有开销（迭代器创建）
- **LinkedList**：for-each 显著优于传统 for（避免 O(n²) 复杂度）
- **其他集合**：for-each 通常更优，因为使用了优化的迭代器

### 原理分析

#### 1. for-each 的本质

for-each（增强 for 循环）是 **语法糖**，编译后会转换为：
- **数组**：转换为传统 for 循环
- **集合**：转换为迭代器（Iterator）

```java
// 源代码
for (String item : list) {
    System.out.println(item);
}

// 编译后（集合）
Iterator<String> iterator = list.iterator();
while (iterator.hasNext()) {
    String item = iterator.next();
    System.out.println(item);
}
```

#### 2. 不同数据结构的性能对比

##### （1）数组：性能相同

```java
// for-each
int[] arr = {1, 2, 3, 4, 5};
for (int num : arr) {
    System.out.println(num);
}

// 传统 for
for (int i = 0; i < arr.length; i++) {
    System.out.println(arr[i]);
}
```

**结论**：编译后字节码几乎一致，性能无差异。

##### （2）ArrayList：性能相近

```java
List<Integer> list = new ArrayList<>(Arrays.asList(1, 2, 3, 4, 5));

// for-each（使用迭代器）
for (Integer num : list) {
    System.out.println(num);
}

// 传统 for（直接索引访问）
for (int i = 0; i < list.size(); i++) {
    System.out.println(list.get(i));
}
```

**结论**：
- ArrayList 的 `get(i)` 是 O(1) 操作，传统 for 略快
- for-each 有迭代器创建开销，但差异极小（纳秒级）
- **实际应用中可忽略不计**

##### （3）LinkedList：for-each 显著更快

```java
List<Integer> list = new LinkedList<>(Arrays.asList(1, 2, 3, 4, 5));

// for-each（使用迭代器，O(n)）
for (Integer num : list) {
    System.out.println(num);
}

// 传统 for（每次 get(i) 都要遍历，O(n²)）
for (int i = 0; i < list.size(); i++) {
    System.out.println(list.get(i));  // 每次都从头遍历到第 i 个节点
}
```

**结论**：
- LinkedList 的 `get(i)` 是 O(n) 操作，传统 for 总复杂度为 **O(n²)**
- for-each 使用迭代器，复杂度为 **O(n)**
- **for-each 性能远超传统 for**

### 性能测试示例

```java
import java.util.*;

public class LoopPerformanceTest {
    public static void main(String[] args) {
        int size = 100000;
        List<Integer> arrayList = new ArrayList<>(size);
        List<Integer> linkedList = new LinkedList<>();
        for (int i = 0; i < size; i++) {
            arrayList.add(i);
            linkedList.add(i);
        }

        // ArrayList - for-each
        long start = System.nanoTime();
        for (Integer num : arrayList) { }
        System.out.println("ArrayList for-each: " + (System.nanoTime() - start) / 1_000_000 + " ms");

        // ArrayList - 传统 for
        start = System.nanoTime();
        for (int i = 0; i < arrayList.size(); i++) {
            Integer num = arrayList.get(i);
        }
        System.out.println("ArrayList for: " + (System.nanoTime() - start) / 1_000_000 + " ms");

        // LinkedList - for-each
        start = System.nanoTime();
        for (Integer num : linkedList) { }
        System.out.println("LinkedList for-each: " + (System.nanoTime() - start) / 1_000_000 + " ms");

        // LinkedList - 传统 for（慎用，极慢）
        start = System.nanoTime();
        for (int i = 0; i < linkedList.size(); i++) {
            Integer num = linkedList.get(i);
        }
        System.out.println("LinkedList for: " + (System.nanoTime() - start) / 1_000_000 + " ms");
    }
}
```

**典型输出**（10 万元素）：
```
ArrayList for-each: 2 ms
ArrayList for: 1 ms
LinkedList for-each: 3 ms
LinkedList for: 15000 ms  // 慢 5000 倍！
```

### 对比总结

| 数据结构 | for-each | 传统 for | 推荐 |
|---------|---------|---------|------|
| **数组** | O(n) | O(n) | 两者皆可 |
| **ArrayList** | O(n) | O(n) | 两者皆可（for-each 更简洁） |
| **LinkedList** | O(n) | O(n²) | **强烈推荐 for-each** |
| **Set/Map** | O(n) | 不支持索引 | **必须用 for-each** |

### 其他考量

#### 1. 可读性
```java
// for-each：简洁、意图明确
for (String name : names) {
    System.out.println(name);
}

// 传统 for：冗长、容易出错（如索引越界）
for (int i = 0; i < names.size(); i++) {
    System.out.println(names.get(i));
}
```

#### 2. 使用限制

**for-each 不适用的场景**：
- 需要修改元素（数组除外）
- 需要删除元素（会抛出 `ConcurrentModificationException`）
- 需要访问索引
- 需要并行遍历多个集合

```java
// 错误示例：for-each 中删除元素
for (String name : names) {
    if (name.equals("张三")) {
        names.remove(name);  // 抛出 ConcurrentModificationException
    }
}

// 正确做法：使用迭代器
Iterator<String> iterator = names.iterator();
while (iterator.hasNext()) {
    if (iterator.next().equals("张三")) {
        iterator.remove();  // 安全删除
    }
}
```

### 面试总结

- **数组/ArrayList**：性能相近，for-each 更简洁
- **LinkedList**：for-each 远快于传统 for（O(n) vs O(n²)）
- **原理**：for-each 是语法糖，集合使用迭代器，数组转为传统 for
- **推荐**：优先使用 for-each，除非需要索引或修改/删除元素
- **注意**：for-each 遍历时不能修改集合结构（增删元素）
