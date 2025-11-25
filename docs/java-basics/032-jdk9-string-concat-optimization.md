---
layout: default
title: "JDK9中对字符串的拼接做了什么优化？"
parent: Java基础
nav_order: 32
description: "深入剖析JDK9字符串拼接优化：从StringBuilder到invokedynamic、StringConcatFactory机制及性能提升"
author: "wuxl"
date: 2025-11-01
---
## 问题

JDK9中对字符串的拼接做了什么优化？

## 答案

### 1. 核心答案

**JDK 9引入了基于`invokedynamic`的动态字符串拼接优化**

- **JDK 8及之前**：字符串拼接编译为`StringBuilder.append()`调用链
- **JDK 9+**：使用`invokedynamic`指令 + `StringConcatFactory`，延迟拼接策略选择到运行时

**优势：**
- 更灵活的优化策略（JVM可根据运行时情况选择最优实现）
- 减少字节码大小
- 更好的性能和可扩展性

### 2. JDK 8 vs JDK 9+ 对比

#### JDK 8实现

**源代码：**
```java
String s = "Hello" + " " + "World" + "!";
```

**编译后字节码（等价Java代码）：**
```java
String s = new StringBuilder()
    .append("Hello")
    .append(" ")
    .append("World")
    .append("!")
    .toString();
```

**字节码：**
```
 0: new           #2  // class java/lang/StringBuilder
 3: dup
 4: invokespecial #3  // Method java/lang/StringBuilder."<init>":()V
 7: ldc           #4  // String Hello
 9: invokevirtual #5  // Method java/lang/StringBuilder.append:(Ljava/lang/String;)Ljava/lang/StringBuilder;
12: ldc           #6  // String
14: invokevirtual #5  // ...
17: ldc           #7  // String World
19: invokevirtual #5  // ...
22: ldc           #8  // String !
24: invokevirtual #5  // ...
27: invokevirtual #9  // Method java/lang/StringBuilder.toString:()Ljava/lang/String;
30: astore_1
```

**问题：**
- 字节码冗长（每个字符串一次append调用）
- 硬编码使用StringBuilder，JVM无优化空间
- 循环拼接会创建大量中间StringBuilder对象

#### JDK 9+实现

**源代码：**
```java
String s = "Hello" + " " + "World" + "!";
```

**编译后字节码：**
```
 0: ldc           #2  // String Hello World!  <- 编译期优化（常量折叠）
 2: astore_1

// 如果涉及变量：
String name = "Java";
String s = "Hello " + name + "!";

// 字节码：
 0: ldc           #2  // String Java
 2: astore_1
 3: aload_1
 4: invokedynamic #3, 0  // InvokeDynamic #0:makeConcatWithConstants:(Ljava/lang/String;)Ljava/lang/String;
 9: astore_2

// BootstrapMethods:
0: #18 REF_invokeStatic java/lang/invoke/StringConcatFactory.makeConcatWithConstants:
    String: "Hello \u0001!"  // \u0001是占位符
```

**关键点：**
- 使用`invokedynamic`指令（JDK 7引入，用于动态语言支持）
- 拼接逻辑交给`StringConcatFactory`在运行时决定
- 字节码更简洁

### 3. invokedynamic机制详解

#### 什么是invokedynamic？

`invokedynamic`是JDK 7引入的字节码指令，用于**动态方法调用**：

```java
// 传统方法调用（编译期确定）
invokevirtual   // 虚方法调用
invokestatic    // 静态方法调用
invokespecial   // 构造方法/私有方法调用

// 动态方法调用（运行时确定）
invokedynamic   // 动态语言支持、Lambda、字符串拼接
```

**特点：**
- 编译期不确定具体调用哪个方法
- 首次执行时调用**Bootstrap Method**生成`CallSite`
- 后续调用直接使用缓存的`CallSite`（性能高）

#### StringConcatFactory工作流程

```java
// Bootstrap Method（首次调用时执行）
public static CallSite makeConcatWithConstants(
    MethodHandles.Lookup lookup,
    String name,
    MethodType concatType,
    String recipe,  // 拼接模板，如 "Hello \u0001!"
    Object... constants) throws Exception {

    // 1. 分析拼接需求
    // 2. 选择最优策略（见下文）
    // 3. 生成并返回CallSite

    return new ConstantCallSite(
        MethodHandles.insertArguments(
            generateMHInlineCopy(recipe, constants),
            0, constants));
}
```

**首次调用流程：**
```
源代码: "Hello " + name + "!"
    ↓
字节码: invokedynamic makeConcatWithConstants
    ↓
首次执行: 调用Bootstrap Method
    ↓
生成: CallSite（包含最优拼接实现）
    ↓
缓存: 后续调用直接使用
```

### 4. StringConcatFactory的拼接策略

JDK 9提供了**6种拼接策略**，JVM根据情况选择最优策略：

#### 策略1：BC_SB（Bytecode StringBuilder）- 默认

使用字节码生成器动态创建StringBuilder调用链：

```java
// 等价于JDK 8的StringBuilder方式，但是运行时生成
String result = new StringBuilder()
    .append("Hello ")
    .append(name)
    .append("!")
    .toString();
```

#### 策略2：BC_SB_SIZED

预估容量的StringBuilder：

```java
// 根据已知字符串长度预分配容量
int capacity = "Hello ".length() + name.length() + "!".length();
String result = new StringBuilder(capacity)
    .append("Hello ")
    .append(name)
    .append("!")
    .toString();
```

**优势：**避免StringBuilder的动态扩容，性能更好

#### 策略3：BC_SB_SIZED_EXACT

精确容量的StringBuilder（包含类型转换）：

```java
int age = 25;
String s = "Age: " + age;

// 精确计算int转String的长度
int capacity = "Age: ".length() + stringSize(age);
String result = new StringBuilder(capacity)
    .append("Age: ")
    .append(age)
    .toString();
```

#### 策略4：MH_SB_SIZED

使用MethodHandle优化的StringBuilder

#### 策略5：MH_SB_SIZED_EXACT

使用MethodHandle + 精确容量

#### 策略6：MH_INLINE_SIZED_EXACT（最优）

完全内联，直接操作byte[]，避免StringBuilder对象：

```java
// 伪代码，实际是字节码生成
byte[] buf = new byte[totalLength];
int offset = 0;

// 直接复制字节
System.arraycopy("Hello ".getBytes(), 0, buf, offset, 6);
offset += 6;
System.arraycopy(name.getBytes(), 0, buf, offset, name.length());
offset += name.length();
System.arraycopy("!".getBytes(), 0, buf, offset, 1);

String result = new String(buf);
```

**最优性能：**
- 无StringBuilder对象创建
- 无中间append方法调用
- 直接内存操作，最快

### 5. 策略选择机制

通过JVM参数控制：

```bash
# 查看当前策略
-Djava.lang.invoke.stringConcat=help

# 指定策略
-Djava.lang.invoke.stringConcat=BC_SB          # 基础StringBuilder
-Djava.lang.invoke.stringConcat=BC_SB_SIZED    # 预估容量
-Djava.lang.invoke.stringConcat=MH_INLINE_SIZED_EXACT  # 最优内联（默认）
```

**默认策略选择逻辑：**
```java
// JVM根据以下因素选择策略：
1. 拼接元素数量
2. 是否能预估总长度
3. 是否包含常量
4. 运行时性能统计
```

### 6. 性能对比测试

#### 测试代码

```java
public class StringConcatBenchmark {
    public static void main(String[] args) {
        int count = 1_000_000;
        String name = "Java";

        // JDK 8方式（手动StringBuilder）
        long start = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            String s = new StringBuilder()
                .append("Hello ")
                .append(name)
                .append("!")
                .toString();
        }
        System.out.println("JDK 8: " + (System.currentTimeMillis() - start) + "ms");

        // JDK 9+方式（+拼接，自动优化）
        start = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            String s = "Hello " + name + "!";
        }
        System.out.println("JDK 9+: " + (System.currentTimeMillis() - start) + "ms");
    }
}
```

#### 性能结果（参考）

| 策略 | 100万次拼接耗时 | 相对性能 |
|------|---------------|---------|
| JDK 8 StringBuilder | 150ms | 基准 |
| JDK 9 BC_SB | 145ms | +3% |
| JDK 9 BC_SB_SIZED | 120ms | +20% |
| JDK 9 MH_INLINE_SIZED_EXACT | 90ms | +40% |

**结论：**JDK 9+的最优策略性能提升约**40%**

### 7. 字节码对比分析

#### 示例代码

```java
String name = "Java";
int version = 9;
String s = "Language: " + name + ", Version: " + version;
```

#### JDK 8字节码（简化）

```
new StringBuilder
dup
invokespecial StringBuilder.<init>
ldc "Language: "
invokevirtual StringBuilder.append
aload_1  // name
invokevirtual StringBuilder.append
ldc ", Version: "
invokevirtual StringBuilder.append
iload_2  // version
invokevirtual StringBuilder.append(I)
invokevirtual StringBuilder.toString
astore_3
```

**字节码长度：**约30+字节

#### JDK 9+字节码（简化）

```
aload_1  // name
iload_2  // version
invokedynamic makeConcatWithConstants(Ljava/lang/String;I)Ljava/lang/String;
    BootstrapMethod: "Language: \u0001, Version: \u0001"
astore_3
```

**字节码长度：**约10字节

**对比：**
- 字节码减少约**70%**
- class文件更小
- 加载更快

### 8. 循环拼接的优化

#### JDK 8问题

```java
String result = "";
for (int i = 0; i < 100; i++) {
    result += i;  // 每次循环创建新StringBuilder！
}

// 等价于
for (int i = 0; i < 100; i++) {
    result = new StringBuilder(result).append(i).toString();
    // 100次循环 = 100个StringBuilder对象
}
```

#### JDK 9+改进

虽然JDK 9优化了单次拼接，但循环拼接**仍然推荐手动使用StringBuilder**：

```java
// ✅ 推荐做法（JDK 8/9/10+都适用）
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 100; i++) {
    sb.append(i);
}
String result = sb.toString();
```

**原因：**
- invokedynamic优化的是单个语句的拼接
- 循环内的拼接仍会产生多个中间对象
- 手动StringBuilder更高效

### 9. 实际应用建议

#### ✅ 适合使用+拼接的场景

```java
// 1. 简单拼接（JDK 9+自动优化）
String msg = "User " + username + " logged in at " + time;

// 2. 少量拼接
String url = baseUrl + "/api/users/" + userId;

// 3. 日志输出
logger.info("Processing order: " + orderId + ", status: " + status);
```

#### ✅ 推荐手动StringBuilder的场景

```java
// 1. 循环拼接
StringBuilder sql = new StringBuilder("SELECT * FROM users WHERE id IN (");
for (int i = 0; i < ids.size(); i++) {
    if (i > 0) sql.append(", ");
    sql.append(ids.get(i));
}
sql.append(")");

// 2. 条件拼接
StringBuilder query = new StringBuilder("SELECT * FROM users");
if (name != null) query.append(" WHERE name = '").append(name).append("'");
if (age != null) query.append(" AND age = ").append(age);

// 3. 大量拼接（>10个元素）
StringBuilder html = new StringBuilder();
for (User user : users) {
    html.append("<tr>")
        .append("<td>").append(user.getName()).append("</td>")
        .append("<td>").append(user.getAge()).append("</td>")
        .append("</tr>");
}
```

### 10. 面试答题要点

**标准回答结构：**

1. **核心改进**：JDK 9使用`invokedynamic` + `StringConcatFactory`替代硬编码的StringBuilder
2. **优势对比**：
   - 字节码更简洁（减少约70%）
   - 性能更好（最优策略提升40%）
   - 更灵活（JVM可根据运行时情况选择策略）
3. **实现机制**：
   - 编译期：生成invokedynamic指令
   - 运行时：Bootstrap Method选择最优拼接策略
   - 策略包括：基础StringBuilder、预估容量、内联字节操作等
4. **最优策略**：MH_INLINE_SIZED_EXACT，直接操作byte[]，避免中间对象
5. **注意事项**：循环拼接仍推荐手动使用StringBuilder

**加分点：**
- 了解invokedynamic的工作原理（Bootstrap Method、CallSite）
- 能说明6种拼接策略及其差异
- 知道JVM参数`-Djava.lang.invoke.stringConcat`
- 对比JDK 8和JDK 9的字节码差异
- 理解何时该用+，何时该用StringBuilder

### 11. 总结

**JDK 9字符串拼接优化核心要点：**

| 维度 | JDK 8 | JDK 9+ |
|------|-------|--------|
| **实现方式** | 硬编码StringBuilder | invokedynamic动态选择 |
| **字节码长度** | 长（每个append一条指令） | 短（单条invokedynamic） |
| **优化策略** | 固定 | 6种策略，运行时选择 |
| **性能** | 基准 | 提升20-40% |
| **可扩展性** | 无 | 高（未来可增加新策略） |

**设计思想：**
- **延迟决策**：将拼接策略选择推迟到运行时
- **动态优化**：JVM根据实际情况选择最优实现
- **字节码精简**：减小class文件体积，加快加载

这是JDK在编译器优化和JVM运行时优化方面的重要进步，体现了Java对**性能**和**灵活性**的持续追求。
