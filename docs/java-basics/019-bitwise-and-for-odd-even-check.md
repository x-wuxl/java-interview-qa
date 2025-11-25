---
layout: default
title: "除了对 2 取余，如何快速判断一个数的奇偶性？"
parent: Java基础
nav_order: 19
description: "使用位运算高效判断整数奇偶性的原理与实现"
author: "wuxl"
date: 2025-11-17
---
## 问题

除了对 2 取余，如何快速判断一个数的奇偶性？

## 答案

### 核心结论

使用**位运算 `& 1`** 可以高效判断奇偶性：
- `n & 1 == 0`：偶数
- `n & 1 == 1`：奇数

这种方法比取余运算 `n % 2` 更快，因为位运算是 CPU 的基本指令，效率更高。

### 原理说明

**二进制特性**：
- 偶数的二进制表示最低位（最右边一位）是 **0**
- 奇数的二进制表示最低位（最右边一位）是 **1**

**位与运算 `& 1`**：
- `& 1` 会保留数字的最低位，其他位全部变为 0
- 结果为 0 表示偶数，结果为 1 表示奇数

### 二进制示例

```java
// 偶数示例
6 的二进制: 0000 0110
1 的二进制: 0000 0001
6 & 1 结果: 0000 0000 = 0 (偶数)

// 奇数示例
7 的二进制: 0000 0111
1 的二进制: 0000 0001
7 & 1 结果: 0000 0001 = 1 (奇数)
```

### 代码实现

```java
public class OddEvenCheck {
    public static void main(String[] args) {
        // 方法一：位运算（推荐）
        System.out.println("=== 位运算判断 ===");
        System.out.println("6 是偶数: " + isEvenByBitwise(6));  // true
        System.out.println("7 是奇数: " + isOddByBitwise(7));   // true
        System.out.println("-4 是偶数: " + isEvenByBitwise(-4)); // true
        System.out.println("-5 是奇数: " + isOddByBitwise(-5));  // true

        // 方法二：取余运算（传统方法）
        System.out.println("\n=== 取余运算判断 ===");
        System.out.println("6 是偶数: " + isEvenByModulo(6));   // true
        System.out.println("7 是奇数: " + isOddByModulo(7));    // true

        // 性能对比
        performanceTest();
    }

    // 位运算判断偶数
    public static boolean isEvenByBitwise(int n) {
        return (n & 1) == 0;
    }

    // 位运算判断奇数
    public static boolean isOddByBitwise(int n) {
        return (n & 1) == 1;
    }

    // 取余判断偶数
    public static boolean isEvenByModulo(int n) {
        return n % 2 == 0;
    }

    // 取余判断奇数
    public static boolean isOddByModulo(int n) {
        return n % 2 != 0;
    }

    // 性能测试
    public static void performanceTest() {
        int count = 100_000_000;

        // 测试位运算
        long start1 = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            boolean result = (i & 1) == 0;
        }
        long end1 = System.currentTimeMillis();

        // 测试取余运算
        long start2 = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            boolean result = i % 2 == 0;
        }
        long end2 = System.currentTimeMillis();

        System.out.println("\n=== 性能对比（" + count + " 次操作）===");
        System.out.println("位运算耗时: " + (end1 - start1) + " ms");
        System.out.println("取余运算耗时: " + (end2 - start2) + " ms");
    }
}
```

### 输出结果

```
=== 位运算判断 ===
6 是偶数: true
7 是奇数: true
-4 是偶数: true
-5 是奇数: true

=== 取余运算判断 ===
6 是偶数: true
7 是奇数: true

=== 性能对比（100000000 次操作）===
位运算耗时: 45 ms
取余运算耗时: 78 ms
```

### 方法对比

| 方法 | 表达式 | 性能 | 可读性 | 适用场景 |
|------|--------|------|--------|---------|
| 位运算 | `n & 1` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 性能敏感场景 |
| 取余运算 | `n % 2` | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 一般业务场景 |

### 负数处理

位运算对负数同样有效，因为负数的二进制表示（补码）最低位规律相同：

```java
// 负数示例
-4 的二进制（补码）: 1111 1100
-4 & 1 结果:         0000 0000 = 0 (偶数)

-5 的二进制（补码）: 1111 1011
-5 & 1 结果:         0000 0001 = 1 (奇数)
```

### 扩展：其他位运算技巧

```java
// 1. 判断是否为 2 的幂次方
boolean isPowerOfTwo(int n) {
    return n > 0 && (n & (n - 1)) == 0;
}

// 2. 交换两个数（不使用临时变量）
void swap(int a, int b) {
    a = a ^ b;
    b = a ^ b;
    a = a ^ b;
}

// 3. 获取最低位的 1
int getLowestBit(int n) {
    return n & (-n);
}

// 4. 统计二进制中 1 的个数
int countOnes(int n) {
    int count = 0;
    while (n != 0) {
        n = n & (n - 1);
        count++;
    }
    return count;
}
```

### 面试要点总结

1. **位运算 `& 1` 是最优解**：
   - 原理：检查二进制最低位
   - 性能：比取余快约 40%-50%
   - 适用：所有整数（包括负数）

2. **为什么更快**：
   - 位运算是 CPU 的基本指令
   - 取余运算需要除法操作，开销更大

3. **实际应用**：
   - 算法竞赛、性能敏感代码
   - 底层库、JDK 源码中常见
   - 例如 `HashMap` 的索引计算

4. **可读性权衡**：
   - 性能关键路径：用位运算
   - 一般业务代码：用取余（更直观）

```java
// 推荐写法
if ((n & 1) == 0) {
    // 偶数处理
} else {
    // 奇数处理
}
```

这道题考察的是对位运算的理解和性能优化意识，是算法和底层编程的重要知识点。
