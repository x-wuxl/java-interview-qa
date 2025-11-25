---
layout: default
title: "一个空的 Java Object 对象占用多少内存？"
parent: JVM
nav_order: 121
description: "通过 JOL 工具实测，详解 Java 空对象在开启和关闭指针压缩情况下的内存占用大小，以及对象头、实例数据和对齐填充的计算方式。"
date: 2025-11-19
---
“`new Object()` 到底占多少内存？”
这道题看似简单，实则考察了面试者对 **JVM 对象内存布局**、**指针压缩（Compressed Oops）** 以及 **内存对齐（Padding）** 的理解。

## 1. 核心概念

在 HotSpot 虚拟机中，对象在堆内存中的存储布局分为三块：
1.  **对象头（Header）**：包含 Mark Word 和类型指针（Klass Pointer）。
2.  **实例数据（Instance Data）**：对象真正存储的有效信息（空对象这部分为 0）。
3.  **对齐填充（Padding）**：JVM 要求对象的大小必须是 **8 字节的整数倍**，不足的需要补齐。

---

## 2. 内存计算（64位 JVM）

我们主要讨论 64 位 JVM，因为 32 位现在已经很少见。64 位 JVM 有两种情况：**开启指针压缩**（默认开启）和 **关闭指针压缩**。

### 2.1 情况一：开启指针压缩（默认）
JVM 参数：`-XX:+UseCompressedOops`（JDK 1.6 update 14 后默认开启）。

*   **Mark Word**：8 字节。
*   **Klass Pointer**：被压缩为 4 字节。
*   **实例数据**：0 字节。
*   **对齐填充**：目前总共 `8 + 4 = 12` 字节。为了满足 8 字节对齐，需要填充 **4 字节**。

**总计：8 + 4 + 0 + 4 = 16 字节。**

### 2.2 情况二：关闭指针压缩
JVM 参数：`-XX:-UseCompressedOops`。

*   **Mark Word**：8 字节。
*   **Klass Pointer**：不压缩，占用 8 字节。
*   **实例数据**：0 字节。
*   **对齐填充**：目前总共 `8 + 8 = 16` 字节。正好是 8 的倍数，不需要填充。

**总计：8 + 8 + 0 + 0 = 16 字节。**

> **有趣结论**：无论是否开启指针压缩，一个空对象在 64 位 JVM 下通常都占用 **16 字节**。但内部结构不同（前者有填充，后者无）。

---

## 3. 验证工具：JOL

口说无凭，我们可以使用 OpenJDK 提供的 **JOL (Java Object Layout)** 工具来打印对象内存布局。

**引入依赖：**
```xml
<dependency>
    <groupId>org.openjdk.jol</groupId>
    <artifactId>jol-core</artifactId>
    <version>0.16</version>
</dependency>
```

**测试代码：**
```java
import org.openjdk.jol.info.ClassLayout;

public class ObjectSizeTest {
    public static void main(String[] args) {
        Object obj = new Object();
        System.out.println(ClassLayout.parseInstance(obj).toPrintable());
    }
}
```

**输出结果（开启指针压缩）：**
```text
java.lang.Object object internals:
OFF  SZ   TYPE DESCRIPTION               VALUE
  0   8        (object header: mark)     0x0000000000000001 (non-biasable; age: 0)
  8   4        (object header: class)    0xf80001e5
 12   4        (object alignment gap)    
Instance size: 16 bytes
Space losses: 0 bytes internal + 4 bytes external = 4 bytes total
```
可以看到 `Instance size: 16 bytes`，并且最后有 4 字节的 `alignment gap`（对齐填充）。

---

## 4. 总结

**面试回答总结：**

> 在 64 位 HotSpot 虚拟机中，一个空的 `new Object()` 对象通常占用 **16 字节**。
>
> **计算公式**：`对象头 + 实例数据 + 对齐填充`。
> *   **开启指针压缩（默认）**：Mark Word (8) + Klass Pointer (4) + Padding (4) = 16 字节。
> *   **关闭指针压缩**：Mark Word (8) + Klass Pointer (8) + Padding (0) = 16 字节。
>
> 这里的关键点在于理解 **对齐填充** 的作用：JVM 强制要求对象起始地址必须是 8 字节的整数倍，因此对象大小也必须是 8 的倍数。
