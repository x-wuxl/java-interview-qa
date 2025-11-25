---
layout: default
title: "为什么不能用BigDecimal的equals方法做等值比较"
parent: Java基础
nav_order: 39
description: "深入分析BigDecimal的equals陷阱与正确的等值比较方法"
author: "wuxl"
date: 2025-11-01
---
## 问题

为什么不能用BigDecimal的equals方法做等值比较?

## 答案

### 核心问题

`BigDecimal.equals()` 不仅比较**数值**，还比较**精度（scale）**，导致数值相同但精度不同的对象返回 `false`。

### 问题演示

```java
BigDecimal num1 = new BigDecimal("1.0");
BigDecimal num2 = new BigDecimal("1.00");

// equals比较：返回false（精度不同）
System.out.println(num1.equals(num2)); // false ❌

// compareTo比较：返回0（数值相同）
System.out.println(num1.compareTo(num2)); // 0 ✅

// 查看精度
System.out.println(num1.scale()); // 1
System.out.println(num2.scale()); // 2
```

### equals源码分析

```java
// BigDecimal.equals()源码
public boolean equals(Object x) {
    if (!(x instanceof BigDecimal))
        return false;

    BigDecimal xDec = (BigDecimal) x;

    // 1. 先比较数值
    if (this.intVal != xDec.intVal)
        return false;

    // 2. 再比较精度（scale）
    if (this.scale != xDec.scale)
        return false; // ← 关键：精度不同直接返回false

    return true;
}
```

**问题根源**：`equals` 将 `1.0` 和 `1.00` 视为不同对象。

### compareTo方法

```java
// BigDecimal.compareTo()源码（简化）
public int compareTo(BigDecimal val) {
    // 只比较数值大小，忽略精度
    // 1.0 和 1.00 返回0（相等）
    // 2.0 和 1.0 返回1（大于）
    // 1.0 和 2.0 返回-1（小于）
}
```

### 实际影响场景

#### 1. HashMap/HashSet去重失败

```java
Set<BigDecimal> set = new HashSet<>();
set.add(new BigDecimal("1.0"));
set.add(new BigDecimal("1.00"));

System.out.println(set.size()); // 2 ❌ 期望1，实际2
```

**原因**：`equals` 返回false，hashCode也不同：

```java
BigDecimal num1 = new BigDecimal("1.0");
BigDecimal num2 = new BigDecimal("1.00");

System.out.println(num1.hashCode()); // 311
System.out.println(num2.hashCode()); // 3101
// hashCode = intVal * 31 + scale
```

#### 2. 金额比较错误

```java
// 从数据库查询的金额（精度可能不一致）
BigDecimal dbPrice = new BigDecimal("99.9"); // scale=1
BigDecimal inputPrice = new BigDecimal("99.90"); // scale=2

if (dbPrice.equals(inputPrice)) {
    // 永远不会执行 ❌
    System.out.println("价格相同");
}
```

#### 3. List.contains失效

```java
List<BigDecimal> prices = Arrays.asList(
    new BigDecimal("10.0"),
    new BigDecimal("20.0")
);

boolean found = prices.contains(new BigDecimal("10.00"));
System.out.println(found); // false ❌
```

### 正确的比较方式

#### 1. 使用compareTo（推荐）

```java
BigDecimal num1 = new BigDecimal("1.0");
BigDecimal num2 = new BigDecimal("1.00");

// ✅ 正确：数值比较
if (num1.compareTo(num2) == 0) {
    System.out.println("数值相等");
}

// 封装为工具方法
public static boolean isEqual(BigDecimal a, BigDecimal b) {
    if (a == null && b == null) return true;
    if (a == null || b == null) return false;
    return a.compareTo(b) == 0;
}
```

#### 2. 统一精度后比较

```java
BigDecimal num1 = new BigDecimal("1.0");
BigDecimal num2 = new BigDecimal("1.00");

// 统一精度为2位小数
num1 = num1.setScale(2, RoundingMode.HALF_UP);
num2 = num2.setScale(2, RoundingMode.HALF_UP);

System.out.println(num1.equals(num2)); // true ✅
```

#### 3. 使用stripTrailingZeros

```java
BigDecimal num1 = new BigDecimal("1.0").stripTrailingZeros();
BigDecimal num2 = new BigDecimal("1.00").stripTrailingZeros();

System.out.println(num1.equals(num2)); // true ✅

// 注意特殊情况
BigDecimal zero1 = new BigDecimal("0.0").stripTrailingZeros();
BigDecimal zero2 = new BigDecimal("0.00").stripTrailingZeros();
System.out.println(zero1.equals(zero2)); // false ❌
// 0.0 → 0, scale=0
// 0.00 → 0.0, scale=1 (保留一位小数)
```

### 集合去重方案

#### 方案1：使用TreeSet + compareTo

```java
// TreeSet基于compareTo排序和去重
Set<BigDecimal> set = new TreeSet<>();
set.add(new BigDecimal("1.0"));
set.add(new BigDecimal("1.00"));

System.out.println(set.size()); // 1 ✅
```

#### 方案2：统一精度后放入HashSet

```java
Set<BigDecimal> set = new HashSet<>();

public void addPrice(BigDecimal price) {
    // 统一精度为2位小数
    BigDecimal normalized = price.setScale(2, RoundingMode.HALF_UP);
    set.add(normalized);
}
```

#### 方案3：自定义Comparator

```java
Set<BigDecimal> set = new TreeSet<>((a, b) -> a.compareTo(b));
set.add(new BigDecimal("1.0"));
set.add(new BigDecimal("1.00"));

System.out.println(set.size()); // 1 ✅
```

### equals vs compareTo 完整对比

```java
BigDecimal a = new BigDecimal("2.0");
BigDecimal b = new BigDecimal("2.00");
BigDecimal c = new BigDecimal("3.0");

// equals比较（值 + 精度）
System.out.println(a.equals(b));   // false（精度不同）
System.out.println(a.equals(c));   // false（值不同）

// compareTo比较（仅值）
System.out.println(a.compareTo(b)); // 0（相等）
System.out.println(a.compareTo(c)); // -1（小于）
System.out.println(c.compareTo(a)); // 1（大于）
```

### 实战最佳实践

#### 金额比较工具类

```java
public class MoneyUtils {
    /**
     * 判断两个金额是否相等
     */
    public static boolean equals(BigDecimal a, BigDecimal b) {
        if (a == null && b == null) return true;
        if (a == null || b == null) return false;
        return a.compareTo(b) == 0;
    }

    /**
     * 判断a是否大于b
     */
    public static boolean greaterThan(BigDecimal a, BigDecimal b) {
        return a.compareTo(b) > 0;
    }

    /**
     * 判断a是否大于等于b
     */
    public static boolean greaterOrEqual(BigDecimal a, BigDecimal b) {
        return a.compareTo(b) >= 0;
    }

    /**
     * 判断a是否小于b
     */
    public static boolean lessThan(BigDecimal a, BigDecimal b) {
        return a.compareTo(b) < 0;
    }

    /**
     * 判断a是否小于等于b
     */
    public static boolean lessOrEqual(BigDecimal a, BigDecimal b) {
        return a.compareTo(b) <= 0;
    }
}

// 使用示例
if (MoneyUtils.greaterThan(accountBalance, orderAmount)) {
    // 余额充足
}
```

#### 数据库查询比较

```java
// MyBatis Mapper
@Select("SELECT * FROM orders WHERE price = #{price}")
List<Order> findByPrice(BigDecimal price);

// 调用时注意精度
BigDecimal searchPrice = new BigDecimal("99.90");
List<Order> orders = orderMapper.findByPrice(searchPrice);

// 如果数据库中存储为99.9，则查询不到结果！
// 解决方案：使用范围查询
@Select("SELECT * FROM orders WHERE ABS(price - #{price}) < 0.01")
List<Order> findByPriceRange(BigDecimal price);
```

### 常见陷阱

```java
// 陷阱1：List.remove失效
List<BigDecimal> list = new ArrayList<>();
list.add(new BigDecimal("1.0"));
list.remove(new BigDecimal("1.00")); // ❌ 删除失败
System.out.println(list.size()); // 1

// 陷阱2：Map.get返回null
Map<BigDecimal, String> map = new HashMap<>();
map.put(new BigDecimal("1.0"), "value");
String result = map.get(new BigDecimal("1.00")); // ❌ null

// 陷阱3：distinct失效
List<BigDecimal> list = Arrays.asList(
    new BigDecimal("1.0"),
    new BigDecimal("1.00")
);
long count = list.stream().distinct().count();
System.out.println(count); // 2 ❌ 期望1
```

### 答题总结

`BigDecimal.equals()` 会同时比较**数值和精度（scale）**，导致 `1.0` 和 `1.00` 返回false。**正确做法是使用 `compareTo()`** 进行数值比较，返回0表示相等。这会影响HashMap/HashSet去重、List.contains等集合操作。最佳实践是：
1. 金额比较统一使用 `compareTo`
2. 集合去重使用 `TreeSet`
3. 或统一精度后再使用 `equals`
4. 封装工具类简化调用
