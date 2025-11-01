---
layout: post
title: "String中intern的原理是什么？"
date: 2025-11-01
description: "深入剖析String.intern()方法的原理、字符串常量池机制、JDK6与JDK7+的区别及性能优化实践"
author: "wuxl"
categories: [Java基础]
tags: [String, intern, 字符串常量池, JVM, 内存优化]
---

## 问题

String中intern的原理是什么？

## 答案

### 1. 核心概念

`String.intern()`是一个**native方法**，用于手动将字符串对象放入**字符串常量池（String Pool）**：

```java
public native String intern();
```

**作用机制：**
- 如果常量池中**已存在**相同内容的字符串，返回常量池中的引用
- 如果常量池中**不存在**，将当前字符串加入常量池并返回引用

**核心价值：节省内存、提高性能**

### 2. 基本用法与原理

#### 典型示例

```java
String s1 = new String("hello");  // 堆中创建对象
String s2 = s1.intern();           // 从常量池获取引用
String s3 = "hello";               // 字面量，直接从常量池获取

System.out.println(s1 == s2);  // false - s1在堆，s2在常量池
System.out.println(s2 == s3);  // true  - 都指向常量池同一对象
System.out.println(s1.equals(s2));  // true - 内容相同
```

**内存结构：**
```
堆内存：
  s1 -> [String对象："hello"]

字符串常量池（方法区/元空间）：
  s2 -> ["hello"] <-+
  s3 -------------+
```

#### 常量池查找流程

```java
public String intern() {
    // 1. 在常量池中查找相同内容的字符串
    String pooledString = StringTable.lookup(this);

    // 2. 如果找到，直接返回常量池引用
    if (pooledString != null) {
        return pooledString;
    }

    // 3. 如果没找到，将当前字符串加入常量池
    StringTable.add(this);
    return this;
}
```

### 3. JDK 6 vs JDK 7+ 的重大区别

#### JDK 6：常量池在永久代（PermGen）

**特点：**
- 字符串常量池位于**永久代（PermGen）**
- `intern()`会**复制字符串对象**到永久代
- 永久代空间有限，易发生`OutOfMemoryError: PermGen space`

**示例（JDK 6）：**
```java
String s1 = new String("hello");  // 堆中对象
String s2 = s1.intern();           // 复制到永久代，返回永久代引用

System.out.println(s1 == s2);  // false - s1在堆，s2在永久代
```

**内存结构（JDK 6）：**
```
Java堆：
  s1 -> [String对象："hello"]

永久代（PermGen）：
  字符串常量池：
    s2 -> ["hello" 副本]  // 新创建的副本
```

#### JDK 7+：常量池在堆中

**特点：**
- 字符串常量池移到**Java堆**
- `intern()`不再复制对象，而是**存储堆中对象的引用**
- 避免了PermGen内存限制问题

**示例（JDK 7+）：**
```java
String s1 = new String("a") + new String("b");  // 堆中创建"ab"
String s2 = s1.intern();  // 常量池中不存在"ab"，存储s1的引用

System.out.println(s1 == s2);  // true - 都指向堆中同一对象！
```

**内存结构（JDK 7+）：**
```
Java堆：
  s1 -> [String对象："ab"] <-+
                            |
字符串常量池（也在堆中）：    |
  引用 ---------------------+  // 不是副本，而是引用
```

#### 对比测试

**JDK 6行为：**
```java
String s1 = new String("1");
s1.intern();
String s2 = "1";
System.out.println(s1 == s2);  // false

String s3 = new String("1") + new String("1");
s3.intern();
String s4 = "11";
System.out.println(s3 == s4);  // false
```

**JDK 7+行为：**
```java
String s1 = new String("1");
s1.intern();
String s2 = "1";
System.out.println(s1 == s2);  // false（"1"在类加载时已入池）

String s3 = new String("1") + new String("1");
s3.intern();  // 常量池中不存在"11"，存入s3的引用
String s4 = "11";
System.out.println(s3 == s4);  // true（JDK 7+特有）
```

### 4. 字符串常量池实现机制

#### 底层数据结构：StringTable

字符串常量池本质是一个**HashTable**结构：

```cpp
// HotSpot源码中的StringTable（C++实现）
class StringTable : public Hashtable<oop, mtSymbol> {
private:
    static StringTable* _the_table;
    static int _hash_seed;

public:
    // 查找或添加字符串
    static oop intern(Handle string_or_null, jchar* chars, int length, TRAPS);
    static oop lookup(Symbol* symbol);
    static oop lookup(jchar* chars, int length);
};
```

**特点：**
- 使用哈希表存储字符串引用
- 默认大小可通过`-XX:StringTableSize`调整
- JDK 7+默认大小为60013（质数，减少哈希冲突）

#### 垃圾回收

**JDK 6：**
- 常量池在永久代，Full GC时才回收
- 回收条件苛刻，容易内存泄漏

**JDK 7+：**
- 常量池在堆中，正常GC可回收
- 未被引用的字符串可以被回收

```java
// JDK 7+中，intern的字符串可以被GC
String s = new String("temp").intern();
s = null;  // 如果常量池中的"temp"没有其他引用，可以被GC
```

### 5. 性能优化应用

#### 场景1：大量重复字符串

```java
// 未优化：大量重复字符串占用内存
List<String> urls = new ArrayList<>();
for (int i = 0; i < 1000000; i++) {
    String url = new String("https://api.example.com");  // 100万个重复对象
    urls.add(url);
}

// ✅ 优化：使用intern()复用
List<String> urls = new ArrayList<>();
for (int i = 0; i < 1000000; i++) {
    String url = new String("https://api.example.com").intern();  // 只有1个对象
    urls.add(url);
}
```

**内存节省：**
- 未优化：100万个String对象
- 优化后：1个String对象 + 100万个引用

#### 场景2：数据库字段去重

```java
// 数据库查询结果处理
public List<User> loadUsers() {
    List<User> users = jdbcTemplate.query("SELECT * FROM users", rs -> {
        User user = new User();
        // ✅ 常见字段值使用intern()
        user.setCity(rs.getString("city").intern());  // "北京"可能出现10万次
        user.setDepartment(rs.getString("dept").intern());  // "技术部"可能出现5万次
        return user;
    });
    return users;
}
```

#### 场景3：日志分析

```java
// 分析100万条日志，URL重复度高
Map<String, Integer> urlCount = new HashMap<>();
try (BufferedReader reader = new BufferedReader(new FileReader("access.log"))) {
    String line;
    while ((line = reader.readLine()) != null) {
        String url = extractUrl(line).intern();  // 复用重复的URL字符串
        urlCount.merge(url, 1, Integer::sum);
    }
}
```

### 6. 性能陷阱与注意事项

#### 陷阱1：滥用intern导致常量池膨胀

```java
// ❌ 错误做法：对唯一值使用intern
for (int i = 0; i < 1000000; i++) {
    String unique = UUID.randomUUID().toString().intern();  // 100万个不同字符串
    // intern没有意义，反而增加常量池负担
}
```

**后果：**
- 常量池持续膨胀
- 哈希冲突增加，查找性能下降
- 占用大量内存，无法释放

#### 陷阱2：常量池大小配置不当

```bash
# 默认StringTable大小较小，大量intern会导致性能下降
# 可通过JVM参数调整

# 查看默认大小
-XX:+PrintStringTableStatistics

# 调整大小（设为更大的质数）
-XX:StringTableSize=1000003
```

#### 陷阱3：不必要的intern调用

```java
// ❌ 字面量已经在常量池，无需intern
String s1 = "hello".intern();  // 多余

// ✅ 正确做法
String s1 = "hello";  // 字面量自动入池
```

### 7. 最佳实践

#### 适合使用intern的场景

1. **枚举值较少的字段**：性别、状态、城市等
2. **重复率高的数据**：配置项、URL、错误信息
3. **内存敏感的应用**：缓存系统、大数据处理

#### 不适合使用intern的场景

1. **唯一值字符串**：UUID、随机生成的ID
2. **超长字符串**：大文本内容
3. **临时字符串**：中间计算结果

#### 代码示例

```java
public class InternBestPractice {
    // ✅ 适合：枚举值
    public static final String STATUS_SUCCESS = "SUCCESS";
    public static final String STATUS_FAILED = "FAILED";

    public String processStatus(String status) {
        // 从外部系统获取的状态字符串
        return status.intern();  // 复用常量池中的值
    }

    // ❌ 不适合：唯一标识
    public String generateId() {
        String id = UUID.randomUUID().toString();
        return id.intern();  // 无意义，反而增加开销
    }

    // ✅ 适合：大量重复字符串
    public void processLogs(List<String> logs) {
        Map<String, Integer> logCount = new HashMap<>();
        for (String log : logs) {
            String level = extractLevel(log).intern();  // "ERROR"等级重复率高
            logCount.merge(level, 1, Integer::sum);
        }
    }
}
```

### 8. 面试答题要点

**标准回答结构：**

1. **定义**：intern()将字符串放入常量池，已存在则返回常量池引用，不存在则加入
2. **JDK差异**：
   - JDK 6：常量池在PermGen，intern会复制对象
   - JDK 7+：常量池在堆中，intern存储引用而非复制
3. **底层实现**：基于HashTable的StringTable结构
4. **应用场景**：大量重复字符串的内存优化
5. **注意事项**：避免对唯一值使用，防止常量池膨胀

**加分点：**
- 能说明JDK 6和JDK 7+的内存模型差异
- 了解StringTable的哈希表实现和大小配置
- 知道intern的性能陷阱和最佳实践
- 能用代码演示JDK版本差异（`s3 == s4`的例子）

### 9. 总结

`String.intern()`的核心要点：

| 维度 | JDK 6 | JDK 7+ |
|------|-------|--------|
| **常量池位置** | PermGen（永久代） | Heap（堆） |
| **intern行为** | 复制对象到PermGen | 存储堆对象引用 |
| **内存限制** | PermGen易溢出 | 受堆大小限制 |
| **GC回收** | Full GC才回收 | 正常GC可回收 |
| **性能** | 复制开销大 | 引用存储快 |

**最佳实践总结：**
- ✅ 用于重复率高的字符串（>10%）
- ✅ 枚举值、配置项等有限集合
- ❌ 避免对唯一值使用
- ❌ 避免对超长字符串使用
- ⚙️ 根据场景调整`-XX:StringTableSize`

理解intern的原理和版本差异，是深入掌握Java内存模型和性能优化的重要一步。
