---
layout: post
title: "为什么不能用浮点数表示金额"
date: 2025-11-01
description: "深入分析浮点数精度问题及金额计算的正确方案"
author: "wuxl"
categories: [Java基础]
tags: [浮点数, BigDecimal, 精度, 金额计算]
---

## 问题

为什么不能用浮点数表示金额?

## 答案

### 核心原因

浮点数（float/double）采用**二进制浮点表示**，大部分十进制小数无法精确存储，导致**计算误差累积**,不满足金融场景的精度要求。

### 精度问题演示

#### 1. 存储误差

```java
double price = 0.1;
System.out.println(price); // 0.1（显示格式化后）

// 实际存储值
System.out.println(new BigDecimal(price));
// 输出：0.1000000000000000055511151231257827021181583404541015625
// ❌ 不是精确的0.1
```

#### 2. 计算误差

```java
// 场景：计算 0.1 + 0.2
double result1 = 0.1 + 0.2;
System.out.println(result1); // 0.30000000000000004 ❌

// 场景：货币计算
double balance = 1.0;
double cost = 0.9;
double remaining = balance - cost;
System.out.println(remaining); // 0.09999999999999998 ❌

// 场景：循环累加
double sum = 0.0;
for (int i = 0; i < 10; i++) {
    sum += 0.1;
}
System.out.println(sum); // 0.9999999999999999 ❌ 期望1.0
```

#### 3. 比较失效

```java
double a = 0.1 + 0.2; // 0.30000000000000004
double b = 0.3;       // 0.3

System.out.println(a == b); // false ❌
System.out.println(a);      // 0.30000000000000004
System.out.println(b);      // 0.3
```

### 根本原理

#### IEEE 754标准

double使用64位二进制存储：

```
[符号位:1位][指数:11位][尾数:52位]
```

**问题**：十进制小数转二进制时产生无限循环：

```
十进制 0.1 = 1/10
二进制表示 = 0.0001100110011001100110011... (无限循环)

存储时截断 → 精度丢失
```

#### 示例：0.1的二进制表示

```
0.1(十进制)
= 1/16 + 1/32 + 1/256 + 1/512 + ...
= 0.0001100110011001100110011...(二进制)

double存储（52位尾数）:
0.00011001100110011001100110011001100110011001100110011010
↑ 截断后的值 ≈ 0.1000000000000000055511...
```

### 金融场景的风险

#### 1. 累计误差

```java
// 场景：计算100笔0.01元的交易
double total = 0.0;
for (int i = 0; i < 100; i++) {
    total += 0.01;
}
System.out.println(total); // 0.9999999999999999 ❌
// 实际应该是1.0，误差虽小但不可接受
```

#### 2. 舍入错误

```java
// 场景：优惠券计算
double originalPrice = 29.9;
double discount = 0.85; // 85折
double finalPrice = originalPrice * discount;

System.out.println(finalPrice);
// 25.415000000000003 ❌ 产生了0.000000000000003的误差

// 四舍五入到分
System.out.println(Math.round(finalPrice * 100) / 100.0);
// 25.42，但中间过程已有误差累积
```

#### 3. 账户不平

```java
// 场景：多人分账
double totalAmount = 100.0;
int people = 3;
double perPerson = totalAmount / people; // 33.33333333333333

double distributed = perPerson * people;
System.out.println(distributed); // 99.99999999999999 ❌
// 分账后总和不等于原始金额！
```

### 正确方案：BigDecimal

```java
// ✅ 使用BigDecimal
BigDecimal price1 = new BigDecimal("0.1");
BigDecimal price2 = new BigDecimal("0.2");
BigDecimal sum = price1.add(price2);

System.out.println(sum); // 0.3 ✅ 精确

// ✅ 循环累加
BigDecimal total = BigDecimal.ZERO;
for (int i = 0; i < 10; i++) {
    total = total.add(new BigDecimal("0.1"));
}
System.out.println(total); // 1.0 ✅
```

### BigDecimal最佳实践

#### 1. 构造器选择

```java
// ❌ 错误：使用double构造器
BigDecimal wrong = new BigDecimal(0.1);
// 0.1000000000000000055511151231257827021181583404541015625

// ✅ 正确：使用String构造器
BigDecimal correct = new BigDecimal("0.1"); // 0.1

// ✅ 或使用valueOf
BigDecimal correct2 = BigDecimal.valueOf(0.1); // 内部调用Double.toString
```

#### 2. 运算操作

```java
BigDecimal a = new BigDecimal("100.00");
BigDecimal b = new BigDecimal("30.50");

// 加法
BigDecimal sum = a.add(b); // 130.50

// 减法
BigDecimal diff = a.subtract(b); // 69.50

// 乘法
BigDecimal product = a.multiply(b); // 3050.0000

// 除法（必须指定精度和舍入模式）
BigDecimal quotient = a.divide(b, 2, RoundingMode.HALF_UP); // 3.28
```

#### 3. 除法陷阱

```java
BigDecimal a = new BigDecimal("10");
BigDecimal b = new BigDecimal("3");

// ❌ 错误：不指定精度会抛异常
try {
    BigDecimal result = a.divide(b); // ArithmeticException
} catch (ArithmeticException e) {
    // Non-terminating decimal expansion; no exact representable decimal result.
}

// ✅ 正确：指定精度和舍入模式
BigDecimal result = a.divide(b, 2, RoundingMode.HALF_UP); // 3.33
```

#### 4. 舍入模式

```java
BigDecimal value = new BigDecimal("2.355");

// HALF_UP：四舍五入
value.setScale(2, RoundingMode.HALF_UP); // 2.36

// HALF_DOWN：五舍六入
value.setScale(2, RoundingMode.HALF_DOWN); // 2.35

// DOWN：直接截断
value.setScale(2, RoundingMode.DOWN); // 2.35

// UP：向上取整
value.setScale(2, RoundingMode.UP); // 2.36
```

### 替代方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| **BigDecimal** | 精度完美、API丰富 | 性能较慢、代码冗长 | **金额计算（首选）** |
| **整数（分）** | 性能好、简单 | 需手动处理小数点 | 高性能要求场景 |
| **第三方库** | 如Joda-Money | 引入依赖 | 复杂金融系统 |

#### 整数方案示例

```java
// 用整数（分）表示金额
public class Money {
    private final long cents; // 以分为单位

    public Money(String amount) {
        // "10.50" → 1050分
        this.cents = new BigDecimal(amount)
            .multiply(new BigDecimal("100"))
            .longValue();
    }

    public Money add(Money other) {
        return new Money(this.cents + other.cents);
    }

    public String toString() {
        return String.format("%.2f", cents / 100.0);
    }
}

// 使用
Money m1 = new Money("10.50");
Money m2 = new Money("5.30");
Money total = m1.add(m2); // 15.80
```

### 实战案例

#### 订单金额计算

```java
public class Order {
    private List<OrderItem> items;

    // ✅ 正确：使用BigDecimal
    public BigDecimal calculateTotal() {
        return items.stream()
            .map(item -> item.getPrice()
                .multiply(BigDecimal.valueOf(item.getQuantity())))
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    // ❌ 错误：使用double
    public double calculateTotalWrong() {
        return items.stream()
            .mapToDouble(item -> item.getPriceDouble() * item.getQuantity())
            .sum(); // 精度丢失
    }
}
```

#### 数据库存储

```sql
-- ✅ 正确：使用DECIMAL类型
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    total_amount DECIMAL(19, 2) -- 总额最多17位整数，2位小数
);

-- ❌ 错误：使用DOUBLE
CREATE TABLE orders_wrong (
    total_amount DOUBLE -- 精度问题
);
```

```java
// Entity定义
@Entity
public class Order {
    @Column(precision = 19, scale = 2)
    private BigDecimal totalAmount; // ✅ 正确

    // private double totalAmount; // ❌ 错误
}
```

### 性能考量

```java
// JMH基准测试（百万次操作）
@Benchmark
public double testDoubleAdd() {
    double sum = 0.0;
    for (int i = 0; i < 1000; i++) {
        sum += 0.01;
    }
    return sum;
}

@Benchmark
public BigDecimal testBigDecimalAdd() {
    BigDecimal sum = BigDecimal.ZERO;
    BigDecimal increment = new BigDecimal("0.01");
    for (int i = 0; i < 1000; i++) {
        sum = sum.add(increment);
    }
    return sum;
}

// 典型结果
// testDoubleAdd:       2 μs/op
// testBigDecimalAdd:  50 μs/op  (慢25倍)
```

**结论**：BigDecimal慢20-30倍，但金额计算**精度优先于性能**。

### 答题总结

浮点数采用**二进制表示**，无法精确存储大部分十进制小数（如0.1），导致存储误差和计算误差累积。金融场景不能容忍任何精度损失，必须使用 **BigDecimal**（String构造器）进行金额计算。典型问题包括：`0.1+0.2=0.30000000000000004`、累加误差、账户不平等。最佳实践：
1. 使用 `new BigDecimal("0.1")` 构造
2. 除法必须指定精度和舍入模式
3. 数据库使用DECIMAL类型
4. 高性能场景可考虑整数（分）方案
