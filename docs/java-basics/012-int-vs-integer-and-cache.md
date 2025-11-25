---
layout: default
title: "int 和 Integer 有何区别？Integer 缓存如何实现？"
parent: Java基础
nav_order: 12
description: "深入解析 Java 中基本类型 int 与包装类 Integer 的区别，以及 Integer 缓存机制的实现原理"
author: "wuxl"
date: 2025-11-16
---
## 问题

int 和 Integer 有何区别？Integer 缓存如何实现？

## 答案

### 一、核心区别

**int** 是 Java 的基本数据类型（primitive type），而 **Integer** 是 int 的包装类（wrapper class）。主要区别如下：

| 特性 | int | Integer |
|------|-----|---------|
| 类型 | 基本类型 | 引用类型（对象） |
| 默认值 | 0 | null |
| 存储位置 | 栈内存 | 堆内存（对象本身） |
| 比较方式 | `==` 比较值 | `==` 比较引用，`equals()` 比较值 |
| 是否可为 null | 否 | 是 |
| 性能 | 更高（直接操作） | 较低（需要装箱/拆箱） |

### 二、自动装箱与拆箱

从 Java 5 开始，引入了自动装箱（Autoboxing）和拆箱（Unboxing）机制：

```java
// 自动装箱：int -> Integer
Integer a = 100;  // 等价于 Integer.valueOf(100)

// 自动拆箱：Integer -> int
int b = a;  // 等价于 a.intValue()

// 混合运算会自动拆箱
Integer c = 200;
int result = c + 100;  // c 自动拆箱为 int
```

### 三、Integer 缓存机制

#### 1. 缓存范围

Integer 类内部维护了一个缓存池，默认缓存 **-128 到 127** 之间的整数对象。这个范围可以通过 JVM 参数 `-XX:AutoBoxCacheMax=<size>` 调整上限（下限固定为 -128）。

#### 2. 源码实现

```java
public static Integer valueOf(int i) {
    // 如果值在缓存范围内，直接返回缓存对象
    if (i >= IntegerCache.low && i <= IntegerCache.high)
        return IntegerCache.cache[i + (-IntegerCache.low)];
    // 否则创建新对象
    return new Integer(i);
}

// 内部缓存类
private static class IntegerCache {
    static final int low = -128;
    static final int high;
    static final Integer cache[];

    static {
        // 默认 high = 127，可通过 JVM 参数调整
        int h = 127;
        String integerCacheHighPropValue =
            sun.misc.VM.getSavedProperty("java.lang.Integer.IntegerCache.high");
        if (integerCacheHighPropValue != null) {
            try {
                int i = parseInt(integerCacheHighPropValue);
                i = Math.max(i, 127);  // 最小为 127
                h = Math.min(i, Integer.MAX_VALUE - (-low) - 1);
            } catch( NumberFormatException nfe) {
                // 忽略异常，使用默认值
            }
        }
        high = h;

        // 初始化缓存数组
        cache = new Integer[(high - low) + 1];
        int j = low;
        for(int k = 0; k < cache.length; k++)
            cache[k] = new Integer(j++);
    }
}
```

#### 3. 缓存的影响

```java
// 缓存范围内：返回同一对象
Integer x = 127;
Integer y = 127;
System.out.println(x == y);  // true（引用相同）

// 超出缓存范围：创建新对象
Integer m = 128;
Integer n = 128;
System.out.println(m == n);  // false（引用不同）

// 使用 new 关键字：强制创建新对象
Integer p = new Integer(127);
Integer q = new Integer(127);
System.out.println(p == q);  // false（绕过缓存）

// 正确的比较方式
System.out.println(m.equals(n));  // true（比较值）
```

### 四、性能与使用建议

1. **优先使用基本类型**：在不需要 null 值且性能敏感的场景下，使用 int 而非 Integer。
2. **避免频繁装箱/拆箱**：循环中的自动装箱会产生大量临时对象，影响性能。
3. **使用 `equals()` 比较**：比较 Integer 对象时，务必使用 `equals()` 而非 `==`。
4. **注意缓存陷阱**：不要依赖 `==` 比较 Integer 对象，即使在缓存范围内。

### 五、其他包装类的缓存

- **Byte、Short、Long**：缓存 -128 到 127
- **Character**：缓存 0 到 127
- **Boolean**：缓存 TRUE 和 FALSE
- **Float、Double**：无缓存

### 总结

int 是基本类型，性能高但功能受限；Integer 是对象，支持 null 且可用于泛型，但有装箱开销。Integer 通过缓存池优化了常用小整数的内存占用，面试中需重点掌握缓存范围（-128~127）及其对 `==` 比较的影响。
