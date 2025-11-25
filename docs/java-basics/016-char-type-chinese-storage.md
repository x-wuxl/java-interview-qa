---
layout: default
title: "char 类型变量能否存储中文汉字？为什么？"
parent: Java基础
nav_order: 16
description: "深入理解 Java char 类型与 Unicode 编码，解析为什么 char 可以存储中文汉字"
author: "wuxl"
date: 2025-11-16
---
## 问题

char 类型变量能否存储中文汉字？为什么？

## 答案

### 核心结论

**可以存储**。Java 的 `char` 类型采用 **UTF-16 编码**，占用 2 个字节（16 位），能够表示 Unicode 基本多文种平面（BMP）中的字符，包括绝大多数常用中文汉字。

### 原理说明

1. **char 的本质**
   - Java 中 `char` 是 16 位无符号整数，取值范围：`0 ~ 65535`（`\u0000` ~ `\uffff`）
   - 采用 UTF-16 编码，直接对应 Unicode 码点

2. **中文汉字的 Unicode 范围**
   - 常用汉字位于 **CJK 统一表意文字区**（U+4E00 ~ U+9FFF）
   - 这些码点都在 BMP（基本平面，U+0000 ~ U+FFFF）内，可以用单个 `char` 表示

3. **特殊情况**
   - 超出 BMP 的字符（如生僻字、emoji）需要使用 **代理对**（Surrogate Pair），占用 2 个 `char`
   - 例如：`𠮷`（U+20BB7）需要用 `String` 或 `int` 类型的码点来处理

### 代码示例

```java
public class CharTest {
    public static void main(String[] args) {
        // 直接赋值中文字符
        char ch1 = '中';
        char ch2 = '国';

        // 使用 Unicode 转义序列
        char ch3 = '\u4e2d';  // '中' 的 Unicode 码点

        System.out.println(ch1);  // 输出：中
        System.out.println(ch2);  // 输出：国
        System.out.println(ch3);  // 输出：中
        System.out.println(ch1 == ch3);  // 输出：true

        // 查看字符的 Unicode 码点
        System.out.println((int) ch1);  // 输出：20013（十进制）
        System.out.println(Integer.toHexString(ch1));  // 输出：4e2d（十六进制）
    }
}
```

### 关键要点

| 方面 | 说明 |
|------|------|
| **存储能力** | 可以存储 BMP 内的所有中文汉字（99% 以上的常用汉字） |
| **编码方式** | UTF-16，每个 char 占 2 字节 |
| **取值范围** | 0 ~ 65535（无符号） |
| **特殊字符** | 生僻字、emoji 等需要代理对（2 个 char） |

### 面试总结

- **能存储**：`char` 采用 UTF-16 编码，2 字节足以表示常用中文汉字
- **原理**：中文汉字的 Unicode 码点在 BMP 范围内（U+4E00 ~ U+9FFF）
- **注意**：超出 BMP 的字符需要使用 `String` 或 `int` 类型的码点处理
