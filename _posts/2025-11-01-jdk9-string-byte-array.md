---
layout: post
title: "为什么JDK9中把String的char[]改成了byte[]？"
date: 2025-11-01
description: "深入剖析JDK9 Compact Strings优化：从char[]到byte[]的内存优化、Latin1与UTF-16编码切换及性能提升"
author: "wuxl"
categories: [Java基础]
tags: [String, JDK9, Compact Strings, 内存优化, 编码]
---

## 问题

为什么JDK9中把String的char[]改成了byte[]？

## 答案

### 1. 核心答案

**主要原因：内存优化（节省约50%的堆内存）**

JDK 9引入了**Compact Strings（紧凑字符串）**特性：
- **JDK 8及之前**：使用`char[]`存储字符，每个字符占用**2字节**（UTF-16编码）
- **JDK 9+**：使用`byte[]`存储字符，根据内容选择**1字节（Latin1）**或**2字节（UTF-16）**编码

**优化效果：**
- 大部分字符串仅包含ASCII字符（0-127）
- ASCII字符用1字节即可表示，char[]却占用2字节
- 改用byte[]后，纯ASCII字符串节省50%内存

### 2. JDK 8 vs JDK 9+ 对比

#### JDK 8实现

```java
public final class String {
    private final char[] value;  // 每个字符2字节

    public String(String original) {
        this.value = original.value;
    }
}
```

**内存占用示例：**
```java
String s = "Hello";  // 5个字符
// 内存：5 * 2 = 10字节（char数组）
```

#### JDK 9+实现

```java
public final class String {
    @Stable
    private final byte[] value;  // 动态1字节或2字节

    private final byte coder;  // 编码标识

    static final byte LATIN1 = 0;  // 单字节编码
    static final byte UTF16  = 1;  // 双字节编码
}
```

**内存占用示例：**
```java
String s1 = "Hello";  // 纯ASCII
// 内存：5 * 1 = 5字节（LATIN1编码）

String s2 = "你好";  // 中文
// 内存：2 * 2 = 4字节（UTF16编码）
```

### 3. Compact Strings实现机制

#### 编码选择策略

```java
// String构造方法（简化）
public String(char[] value, int offset, int count) {
    if (COMPACT_STRINGS) {
        // 尝试压缩为Latin1编码
        byte[] val = StringUTF16.compress(value, offset, count);
        if (val != null) {
            // 所有字符都在0-255范围，使用Latin1
            this.value = val;
            this.coder = LATIN1;
            return;
        }
    }
    // 包含非Latin1字符，使用UTF16
    this.coder = UTF16;
    this.value = StringUTF16.toBytes(value, offset, count);
}
```

#### compress方法实现

```java
// StringUTF16.compress源码（简化）
public static byte[] compress(char[] val, int off, int len) {
    byte[] ret = new byte[len];
    for (int i = 0; i < len; i++) {
        char c = val[off + i];
        if (c > 0xFF) {  // 字符值超过255
            return null;  // 无法压缩，返回null
        }
        ret[i] = (byte) c;  // 转为单字节
    }
    return ret;  // 压缩成功
}
```

**关键判断：**
- 遍历所有字符，检查是否都 `<= 0xFF`（255）
- 全部符合 → 使用Latin1编码（1字节）
- 存在超出 → 使用UTF16编码（2字节）

### 4. 字符编码范围

| 编码 | 字符范围 | 每字符字节数 | 适用字符 |
|------|---------|------------|---------|
| **Latin1** | 0-255 | 1字节 | 英文、数字、基础符号 |
| **UTF16** | 0-65535 | 2字节 | 中文、日文、韩文、Emoji |

**Latin1包含的字符：**
- ASCII字符（0-127）：英文字母、数字、常见符号
- 扩展ASCII（128-255）：欧洲语言字符（如é、ñ、ü）

```java
String s1 = "Hello123";  // ✅ Latin1（纯ASCII）
String s2 = "café";      // ✅ Latin1（é在Latin1范围）
String s3 = "你好";      // ❌ UTF16（中文超出Latin1）
String s4 = "Hello你好";  // ❌ UTF16（混合，有中文）
```

### 5. 内存优化效果

#### 典型应用场景

**场景1：配置文件**
```java
// 大部分配置都是ASCII字符
Properties props = new Properties();
props.setProperty("server.port", "8080");
props.setProperty("app.name", "MyApp");
// JDK 8：每个value用char[]，2倍内存
// JDK 9+：Latin1编码，节省50%内存
```

**场景2：日志系统**
```java
// 日志消息大多是英文
logger.info("User login successfully");  // Latin1
logger.error("Connection timeout");      // Latin1
// 大量日志字符串，内存节省显著
```

**场景3：JSON/XML解析**
```java
String json = "{\"name\":\"John\",\"age\":30}";
// 纯ASCII字符，Latin1编码，节省50%
```

#### 内存对比测试

```java
// 假设10万个字符串，平均20个字符（ASCII）
// JDK 8：100,000 * 20 * 2 = 4,000,000字节 ≈ 3.8 MB
// JDK 9+：100,000 * 20 * 1 = 2,000,000字节 ≈ 1.9 MB
// 节省：1.9 MB（50%）
```

### 6. 性能影响

#### 优势：内存和GC

**内存优势：**
- 堆内存占用减少约50%（对于ASCII字符串）
- GC压力减小，Young GC频率降低
- 缓存友好（更多字符串可缓存在CPU缓存中）

**GC优势：**
```java
// 示例：1GB堆内存，字符串占用40%
// JDK 8：400MB字符串数据
// JDK 9+：200MB字符串数据（节省200MB）
// 结果：GC次数减少，应用更流畅
```

#### 劣势：编码判断开销

**额外开销：**
- 每次创建String需判断是否可压缩
- 字符串操作需检查编码类型（Latin1/UTF16）
- 两套方法实现（`StringLatin1`和`StringUTF16`）

**方法分发示例：**
```java
// JDK 9+ charAt实现（简化）
public char charAt(int index) {
    if (isLatin1()) {  // 编码判断
        return StringLatin1.charAt(value, index);
    } else {
        return StringUTF16.charAt(value, index);
    }
}
```

#### 性能测试结果

Oracle官方测试数据：
- **内存**：减少约10-15%堆内存占用
- **性能**：大部分场景无明显性能损失，部分场景更快
- **GC**：GC暂停时间减少约5-10%

### 7. 源码实现细节

#### coder字段作用

```java
private final byte coder;  // 编码标识

static final byte LATIN1 = 0;
static final byte UTF16  = 1;

// 判断方法
private boolean isLatin1() {
    return coder == LATIN1;
}
```

#### 分层实现：StringLatin1 vs StringUTF16

```java
// StringLatin1工具类（Latin1编码的操作）
final class StringLatin1 {
    public static char charAt(byte[] value, int index) {
        return (char) (value[index] & 0xFF);  // 单字节转char
    }

    public static int length(byte[] value) {
        return value.length;  // 长度=字节数
    }
}

// StringUTF16工具类（UTF16编码的操作）
final class StringUTF16 {
    public static char charAt(byte[] value, int index) {
        return getChar(value, index);  // 双字节转char
    }

    public static int length(byte[] value) {
        return value.length >> 1;  // 长度=字节数/2
    }
}
```

#### 具体方法示例：substring

```java
public String substring(int beginIndex, int endIndex) {
    int length = endIndex - beginIndex;
    if (isLatin1()) {
        // Latin1编码：直接复制字节
        return new String(Arrays.copyOfRange(value, beginIndex, endIndex), LATIN1);
    } else {
        // UTF16编码：需要*2计算字节偏移
        int off = beginIndex << 1;
        int len = length << 1;
        return new String(Arrays.copyOfRange(value, off, off + len), UTF16);
    }
}
```

### 8. 禁用Compact Strings

可以通过JVM参数禁用此优化：

```bash
# 禁用紧凑字符串（回退到JDK 8行为，使用char[]）
java -XX:-CompactStrings MyApp

# 默认是启用的
java -XX:+CompactStrings MyApp
```

**禁用场景：**
- 应用字符串大多包含非Latin1字符（如中文应用）
- 性能测试发现编码判断开销过大
- 兼容性测试（对比新旧版本）

### 9. 实际应用建议

#### 适合Compact Strings的场景

✅ **英文为主的应用**
```java
// 配置管理、日志系统、API接口
String apiUrl = "https://api.example.com/users";
String logMsg = "Request processed successfully";
```

✅ **JSON/XML数据处理**
```java
String json = "{\"id\":123,\"name\":\"Alice\"}";
```

✅ **数据库字段（英文/数字）**
```java
String username = "john_doe";
String orderId = "ORD-20231101-001";
```

#### 不适合的场景

❌ **大量非Latin1字符**
```java
// 中文、日文、韩文为主的应用
String chinese = "这是一段中文文本";  // 全部UTF16，无优化效果
```

### 10. 面试答题要点

**标准回答结构：**

1. **核心原因**：内存优化，节省约50%堆内存（对于ASCII字符串）
2. **实现机制**：
   - JDK 8用char[]，固定2字节/字符
   - JDK 9+用byte[]，根据内容动态选择1字节（Latin1）或2字节（UTF16）
3. **编码选择**：
   - 字符值都≤255 → Latin1（1字节）
   - 存在>255字符 → UTF16（2字节）
4. **优势**：内存占用减少、GC压力减小、缓存友好
5. **代价**：每次操作需判断编码类型，增加少量CPU开销

**加分点：**
- 说明Latin1和UTF16的字符范围
- 了解`StringLatin1`和`StringUTF16`的分层实现
- 知道可通过`-XX:-CompactStrings`禁用
- 提到实际应用场景和优化效果
- 了解Oracle官方的性能测试数据

### 11. 总结

**JDK 9 Compact Strings核心要点：**

| 维度 | JDK 8 | JDK 9+ |
|------|-------|--------|
| **存储结构** | `char[]` | `byte[]` + `coder` |
| **字符占用** | 固定2字节 | 动态1或2字节 |
| **ASCII字符串** | 10字节 | 5字节（节省50%） |
| **中文字符串** | 4字节 | 4字节（无优化） |
| **编码判断** | 无 | 有（轻微开销） |
| **内存优化** | - | 10-15%堆内存减少 |

**设计思想：**
- **空间换时间** → **时间换空间**：用少量CPU开销换取大量内存节省
- **适应实际场景**：大部分字符串是ASCII，优化常见情况
- **向后兼容**：对开发者透明，无需修改代码

这是JDK在性能优化方面的重要改进，体现了Java对**内存效率**和**实际应用场景**的持续关注。
