---
layout: default
title: "final关键字与可见性是否有关"
parent: 并发编程
nav_order: 190
description: "深入分析final关键字在并发场景下的内存语义与可见性保证"
author: "wuxl"
date: 2025-11-01
---
## 问题

final关键字,和可见性是否有关？

## 答案

### 核心结论

**final关键字与可见性有关**。Java内存模型（JMM）为final字段提供了特殊的**可见性保证**和**重排序限制**，确保对象安全发布。

### final的内存语义

#### 1. 写final字段的重排序规则

**禁止将final字段的写操作重排序到构造函数之外**。

```java
public class FinalExample {
    private final int x;
    private int y;

    public FinalExample() {
        x = 10; // final字段写入
        y = 20; // 普通字段写入
    }
}

// JMM保证：
// 1. x的写入不会被重排序到构造函数外
// 2. 构造函数完成前，x的值对其他线程可见
```

**重排序规则**：

```
禁止：
构造函数内：x = 10  ←─┐
构造函数外：引用赋值   │  × 禁止重排序
                      └──

允许：
普通字段：y = 20     ←─┐
构造函数外：引用赋值   │  ✓ 可以重排序
                      └──
```

#### 2. 读final字段的重排序规则

**禁止读final字段的操作重排序到获取对象引用之前**。

```java
// 线程A
FinalExample obj = new FinalExample();

// 线程B
if (obj != null) {
    int x = obj.x; // 读取final字段
    int y = obj.y; // 读取普通字段
}

// JMM保证：
// 如果线程B看到obj不为null，则一定能看到x=10
// 但不保证能看到y=20（可能为0）
```

### 可见性演示

#### 问题场景：不安全发布

```java
public class UnsafeExample {
    private int value; // 非final字段

    public UnsafeExample() {
        value = 42;
    }
}

// 线程A
UnsafeExample obj = new UnsafeExample();

// 线程B
if (obj != null) {
    System.out.println(obj.value); // 可能输出0 ❌
}
```

**原因**：构造函数内的赋值可能被重排序到引用赋值之后。

#### 解决方案：使用final

```java
public class SafeExample {
    private final int value; // final字段

    public SafeExample() {
        value = 42;
    }
}

// 线程A
SafeExample obj = new SafeExample();

// 线程B
if (obj != null) {
    System.out.println(obj.value); // 保证输出42 ✅
}
```

**原因**：JMM禁止final字段的写操作重排序到构造函数外。

### JMM的final语义保证

#### 底层实现

```java
// 编译器/JVM插入内存屏障

public class FinalExample {
    private final int x;

    public FinalExample() {
        x = 10;        // final字段写入
        // ← JVM插入StoreStore屏障
    }
    // ← 构造函数结束前插入StoreStore屏障
}
```

**内存屏障作用**：
- **StoreStore屏障**：确保final字段的写入在对象引用对其他线程可见之前完成
- **LoadLoad屏障**：确保读取对象引用后，final字段的值立即可见

### final与volatile对比

| 特性 | final | volatile |
|-----|-------|----------|
| **可见性** | ✅ 初始化后可见 | ✅ 每次读写都可见 |
| **重排序** | 禁止构造函数内外重排序 | 禁止所有读写重排序 |
| **适用场景** | 不可变字段 | 可变共享变量 |
| **性能** | 无额外开销 | 每次访问都有开销 |
| **修改性** | 不可修改 | 可以修改 |

```java
public class ComparisonExample {
    private final int finalValue = 10;      // 初始化后不变
    private volatile int volatileValue = 10; // 可随时修改

    public void update() {
        // finalValue = 20; // ❌ 编译错误
        volatileValue = 20; // ✅ 可以修改
    }
}
```

### final的局限性

#### 1. 引用类型final的陷阱

```java
public class FinalReferenceExample {
    private final List<String> list = new ArrayList<>();

    public FinalReferenceExample() {
        list.add("初始值");
    }

    public void addItem(String item) {
        list.add(item); // ✅ 可以修改list内容
    }

    public void reassign() {
        // list = new ArrayList<>(); // ❌ 不能重新赋值
    }
}

// 线程安全问题
FinalReferenceExample obj = new FinalReferenceExample();

// 线程A
obj.addItem("A");

// 线程B
System.out.println(obj.list.size()); // 可能看到0、1或2 ❌
```

**原因**：final只保证引用不变，不保证引用对象内部状态的可见性。

**解决方案**：

```java
// 方案1：不可变集合
private final List<String> list =
    Collections.unmodifiableList(Arrays.asList("初始值"));

// 方案2：使用CopyOnWriteArrayList
private final List<String> list = new CopyOnWriteArrayList<>();

// 方案3：同步访问
private final List<String> list = new ArrayList<>();

public synchronized void addItem(String item) {
    list.add(item);
}

public synchronized int getSize() {
    return list.size();
}
```

#### 2. final字段逃逸问题

```java
public class EscapeExample {
    private final int value;

    public EscapeExample() {
        // ❌ 危险：在构造函数中泄露this引用
        EventBus.register(this); // this引用逃逸
        value = 42; // final字段写入
    }

    public int getValue() {
        return value;
    }
}

// 其他线程可能通过EventBus获取this引用
// 此时value可能还未初始化完成！
```

**规则**：**不要在构造函数中泄露this引用**。

```java
// ✅ 正确做法
public class SafeExample {
    private final int value;

    private SafeExample() {
        value = 42;
    }

    public static SafeExample create() {
        SafeExample obj = new SafeExample();
        EventBus.register(obj); // 构造完成后再注册
        return obj;
    }
}
```

### 实战应用

#### 1. 不可变对象设计

```java
// ✅ 完全不可变的类
public final class ImmutablePoint {
    private final int x;
    private final int y;

    public ImmutablePoint(int x, int y) {
        this.x = x;
        this.y = y;
    }

    public int getX() { return x; }
    public int getY() { return y; }

    // 修改操作返回新对象
    public ImmutablePoint move(int dx, int dy) {
        return new ImmutablePoint(x + dx, y + dy);
    }
}

// 线程安全，无需同步
ImmutablePoint point = new ImmutablePoint(1, 2);
// 多线程直接访问，无竞态条件
```

#### 2. 单例模式的安全发布

```java
// ❌ 不安全的双重检查锁定
public class UnsafeSingleton {
    private static UnsafeSingleton instance;

    public static UnsafeSingleton getInstance() {
        if (instance == null) {
            synchronized (UnsafeSingleton.class) {
                if (instance == null) {
                    instance = new UnsafeSingleton(); // 可能重排序
                }
            }
        }
        return instance;
    }
}

// ✅ 使用final字段的安全方案
public class SafeSingleton {
    private static class Holder {
        // final保证安全发布
        private static final SafeSingleton INSTANCE = new SafeSingleton();
    }

    public static SafeSingleton getInstance() {
        return Holder.INSTANCE;
    }
}
```

#### 3. 配置类设计

```java
@Configuration
public class AppConfig {
    // ✅ 配置项声明为final
    private final String apiUrl;
    private final int timeout;

    public AppConfig(
        @Value("${api.url}") String apiUrl,
        @Value("${api.timeout}") int timeout
    ) {
        this.apiUrl = apiUrl;
        this.timeout = timeout;
    }

    // 线程安全访问，无需同步
    public String getApiUrl() {
        return apiUrl;
    }

    public int getTimeout() {
        return timeout;
    }
}
```

### 性能影响

#### JIT优化

```java
public class OptimizationExample {
    private final int constant = 100;

    public int calculate(int x) {
        return x * constant; // JIT可能内联为 x * 100
    }
}
```

**优势**：
- 常量折叠
- 方法内联
- 消除冗余读取

#### 无额外同步开销

```java
// final字段：无额外开销
public class FinalField {
    private final int value;

    public int getValue() {
        return value; // 直接读取，无内存屏障
    }
}

// volatile字段：每次访问都有开销
public class VolatileField {
    private volatile int value;

    public int getValue() {
        return value; // 插入内存屏障
    }
}
```

### 常见误区

```java
// ❌ 误区1：认为final字段不需要同步
public class WrongExample {
    private final List<String> list = new ArrayList<>();

    public void addItem(String item) {
        list.add(item); // ❌ 仍需同步
    }
}

// ❌ 误区2：认为final可以替代volatile
public class WrongFlag {
    private final boolean flag = false; // ❌ 无法修改

    public void setFlag() {
        // flag = true; // 编译错误
    }
}

// ❌ 误区3：构造函数中泄露this
public class WrongConstructor {
    private final int value;

    public WrongConstructor() {
        register(this); // ❌ this逃逸
        value = 42;
    }
}
```

### 答题总结

**final关键字与可见性有关**。JMM为final字段提供特殊保证：
1. **写操作不会重排序到构造函数外**：确保对象安全发布
2. **读操作保证能看到构造时的值**：其他线程看到对象引用时，final字段已初始化完成
3. **通过内存屏障实现**：StoreStore屏障禁止重排序

**与volatile区别**：
- final：初始化后不可变，仅保证初始化可见性
- volatile：可修改,保证所有读写操作可见性

**注意事项**：
- final只保证引用不变，不保证对象内部状态
- 不要在构造函数中泄露this引用
- 适合不可变对象、配置类、单例模式等场景
