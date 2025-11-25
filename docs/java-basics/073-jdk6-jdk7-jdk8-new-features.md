---
layout: default
title: "JDK6、JDK7、JDK8 分别提供了哪些新特性？"
parent: Java基础
nav_order: 73
description: "全面梳理 JDK 6、7、8 三个重要版本的核心新特性及其应用场景"
author: "wuxl"
date: 2025-11-17
---
## 问题

JDK6、JDK7、JDK8 分别提供了哪些新特性？

## 答案

### JDK 6 新特性（2006年发布）

JDK 6 主要关注**性能优化**和**工具增强**，是一个稳定的长期支持版本。

#### 核心特性

1. **脚本语言支持（JSR 223）**
   - 提供 `javax.script` 包，支持在 Java 中执行脚本语言
   - 内置 JavaScript 引擎（Rhino）

```java
import javax.script.*;

public class ScriptEngineDemo {
    public static void main(String[] args) throws Exception {
        ScriptEngineManager manager = new ScriptEngineManager();
        ScriptEngine engine = manager.getEngineByName("JavaScript");

        // 执行 JavaScript 代码
        engine.eval("print('Hello from JavaScript')");

        // 传递变量
        engine.put("x", 10);
        engine.put("y", 20);
        Object result = engine.eval("x + y");
        System.out.println("结果: " + result);  // 输出: 30
    }
}
```

2. **编译器 API（JSR 199）**
   - 提供 `javax.tools` 包，允许在运行时动态编译 Java 代码

```java
import javax.tools.*;

public class CompilerAPIDemo {
    public static void main(String[] args) {
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        int result = compiler.run(null, null, null, "HelloWorld.java");
        System.out.println("编译结果: " + (result == 0 ? "成功" : "失败"));
    }
}
```

3. **JDBC 4.0**
   - 自动加载驱动（不再需要 `Class.forName()`）
   - 增强的异常处理和 SQL XML 支持

```java
// JDK 6 之前
Class.forName("com.mysql.jdbc.Driver");
Connection conn = DriverManager.getConnection(url, user, password);

// JDK 6 之后（自动加载驱动）
Connection conn = DriverManager.getConnection(url, user, password);
```

4. **其他改进**
   - Web Services 支持（JAX-WS 2.0）
   - 轻量级 HTTP 服务器 API（`com.sun.net.httpserver`）
   - Console 类（用于读取控制台输入）
   - JVM 性能优化（锁优化、垃圾回收改进）

---

### JDK 7 新特性（2011年发布）

JDK 7 带来了**语法糖**和**实用工具**，提升了开发效率。

#### 核心特性

#### 1. **Diamond 操作符（<>）**

简化泛型实例化，编译器自动推断类型。

```java
// JDK 7 之前
Map<String, List<String>> map = new HashMap<String, List<String>>();

// JDK 7 之后
Map<String, List<String>> map = new HashMap<>();
```

#### 2. **try-with-resources**

自动资源管理，无需手动关闭资源。

```java
// JDK 7 之前
BufferedReader reader = null;
try {
    reader = new BufferedReader(new FileReader("file.txt"));
    String line = reader.readLine();
} catch (IOException e) {
    e.printStackTrace();
} finally {
    if (reader != null) {
        try {
            reader.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}

// JDK 7 之后
try (BufferedReader reader = new BufferedReader(new FileReader("file.txt"))) {
    String line = reader.readLine();
} catch (IOException e) {
    e.printStackTrace();
}
```

#### 3. **多异常捕获（Multi-Catch）**

一个 catch 块捕获多种异常。

```java
// JDK 7 之前
try {
    // 代码
} catch (IOException e) {
    logger.error(e);
} catch (SQLException e) {
    logger.error(e);
}

// JDK 7 之后
try {
    // 代码
} catch (IOException | SQLException e) {
    logger.error(e);
}
```

#### 4. **switch 支持 String**

```java
String day = "Monday";
switch (day) {
    case "Monday":
        System.out.println("星期一");
        break;
    case "Tuesday":
        System.out.println("星期二");
        break;
    default:
        System.out.println("其他");
}
```

#### 5. **数值字面量改进**

- 二进制字面量（`0b` 前缀）
- 数字中可以使用下划线分隔

```java
// 二进制字面量
int binary = 0b1010;  // 10

// 下划线分隔（提高可读性）
int million = 1_000_000;
long creditCard = 1234_5678_9012_3456L;
```

#### 6. **NIO 2.0（New I/O）**

增强的文件操作 API（`java.nio.file` 包）。

```java
import java.nio.file.*;

public class NIO2Demo {
    public static void main(String[] args) throws Exception {
        // 读取文件
        Path path = Paths.get("file.txt");
        List<String> lines = Files.readAllLines(path);

        // 写入文件
        Files.write(path, "Hello NIO 2.0".getBytes());

        // 复制文件
        Files.copy(Paths.get("source.txt"), Paths.get("target.txt"));

        // 遍历目录
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(Paths.get("."))) {
            for (Path entry : stream) {
                System.out.println(entry.getFileName());
            }
        }
    }
}
```

#### 7. **Fork/Join 框架**

并行计算框架，充分利用多核 CPU。

```java
import java.util.concurrent.*;

public class ForkJoinDemo extends RecursiveTask<Long> {
    private long start, end;

    public ForkJoinDemo(long start, long end) {
        this.start = start;
        this.end = end;
    }

    @Override
    protected Long compute() {
        if (end - start <= 10000) {
            // 任务足够小，直接计算
            long sum = 0;
            for (long i = start; i <= end; i++) {
                sum += i;
            }
            return sum;
        } else {
            // 任务太大，拆分成两个子任务
            long mid = (start + end) / 2;
            ForkJoinDemo left = new ForkJoinDemo(start, mid);
            ForkJoinDemo right = new ForkJoinDemo(mid + 1, end);
            left.fork();
            right.fork();
            return left.join() + right.join();
        }
    }

    public static void main(String[] args) {
        ForkJoinPool pool = new ForkJoinPool();
        Long result = pool.invoke(new ForkJoinDemo(1, 1000000));
        System.out.println("结果: " + result);
    }
}
```

---

### JDK 8 新特性（2014年发布）

JDK 8 是**里程碑式**的版本，引入了**函数式编程**，是 Java 历史上最重要的更新之一。

#### 核心特性

#### 1. **Lambda 表达式**

函数式编程的核心，简化匿名内部类。

```java
// JDK 8 之前
List<String> list = Arrays.asList("a", "b", "c");
Collections.sort(list, new Comparator<String>() {
    @Override
    public int compare(String s1, String s2) {
        return s1.compareTo(s2);
    }
});

// JDK 8 之后
Collections.sort(list, (s1, s2) -> s1.compareTo(s2));

// 更简洁的方法引用
Collections.sort(list, String::compareTo);
```

#### 2. **Stream API**

声明式数据处理，支持并行操作。

```java
import java.util.*;
import java.util.stream.*;

public class StreamDemo {
    public static void main(String[] args) {
        List<Integer> numbers = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);

        // 过滤、映射、求和
        int sum = numbers.stream()
                .filter(n -> n % 2 == 0)  // 过滤偶数
                .map(n -> n * n)          // 平方
                .reduce(0, Integer::sum); // 求和
        System.out.println("偶数平方和: " + sum);  // 220

        // 并行流
        long count = numbers.parallelStream()
                .filter(n -> n > 5)
                .count();
        System.out.println("大于 5 的数量: " + count);  // 5

        // 分组
        Map<Boolean, List<Integer>> partitioned = numbers.stream()
                .collect(Collectors.partitioningBy(n -> n % 2 == 0));
        System.out.println("偶数: " + partitioned.get(true));
        System.out.println("奇数: " + partitioned.get(false));
    }
}
```

#### 3. **函数式接口（Functional Interface）**

只有一个抽象方法的接口，可以用 Lambda 表达式实现。

```java
@FunctionalInterface
public interface Calculator {
    int calculate(int a, int b);
}

public class FunctionalInterfaceDemo {
    public static void main(String[] args) {
        Calculator add = (a, b) -> a + b;
        Calculator multiply = (a, b) -> a * b;

        System.out.println("加法: " + add.calculate(5, 3));      // 8
        System.out.println("乘法: " + multiply.calculate(5, 3)); // 15
    }
}
```

#### 4. **方法引用（Method Reference）**

Lambda 表达式的简化形式。

```java
// 静态方法引用
Function<String, Integer> parser = Integer::parseInt;

// 实例方法引用
String str = "Hello";
Supplier<Integer> lengthGetter = str::length;

// 构造方法引用
Supplier<List<String>> listSupplier = ArrayList::new;
```

#### 5. **接口默认方法（Default Method）**

接口可以提供方法的默认实现。

```java
public interface Vehicle {
    // 抽象方法
    void start();

    // 默认方法
    default void stop() {
        System.out.println("车辆停止");
    }

    // 静态方法
    static void honk() {
        System.out.println("鸣笛");
    }
}

public class Car implements Vehicle {
    @Override
    public void start() {
        System.out.println("汽车启动");
    }

    // 可以选择重写默认方法
    @Override
    public void stop() {
        System.out.println("汽车刹车停止");
    }
}
```

#### 6. **Optional 类**

优雅地处理 null 值，避免空指针异常。

```java
import java.util.Optional;

public class OptionalDemo {
    public static void main(String[] args) {
        String name = null;

        // 传统方式
        if (name != null) {
            System.out.println(name.toUpperCase());
        }

        // Optional 方式
        Optional<String> optional = Optional.ofNullable(name);
        optional.ifPresent(n -> System.out.println(n.toUpperCase()));

        // 提供默认值
        String result = optional.orElse("默认名称");
        System.out.println(result);  // 默认名称

        // 链式调用
        String upperName = Optional.ofNullable(name)
                .map(String::toUpperCase)
                .orElse("UNKNOWN");
        System.out.println(upperName);  // UNKNOWN
    }
}
```

#### 7. **新的日期时间 API（java.time）**

替代旧的 `Date` 和 `Calendar`，线程安全且易用。

```java
import java.time.*;
import java.time.format.DateTimeFormatter;

public class DateTimeDemo {
    public static void main(String[] args) {
        // 当前日期时间
        LocalDate today = LocalDate.now();
        LocalTime now = LocalTime.now();
        LocalDateTime dateTime = LocalDateTime.now();

        System.out.println("今天: " + today);        // 2025-11-17
        System.out.println("现在: " + now);          // 14:30:45.123
        System.out.println("日期时间: " + dateTime); // 2025-11-17T14:30:45.123

        // 创建指定日期
        LocalDate birthday = LocalDate.of(1990, 5, 20);

        // 日期计算
        LocalDate nextWeek = today.plusWeeks(1);
        LocalDate lastMonth = today.minusMonths(1);

        // 格式化
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
        String formatted = dateTime.format(formatter);
        System.out.println("格式化: " + formatted);

        // 解析
        LocalDate parsed = LocalDate.parse("2025-12-25");
        System.out.println("解析: " + parsed);
    }
}
```

#### 8. **其他重要特性**

- **Nashorn JavaScript 引擎**：替代 Rhino，性能更好
- **Base64 编码支持**：`java.util.Base64`
- **并行数组操作**：`Arrays.parallelSort()`
- **CompletableFuture**：异步编程增强
- **JVM 优化**：
  - 永久代（PermGen）被元空间（Metaspace）替代
  - G1 垃圾回收器改进

---

### 版本对比总结

| 版本 | 发布年份 | 核心特性 | 重要性 |
|------|---------|---------|--------|
| **JDK 6** | 2006 | 脚本引擎、编译器 API、JDBC 4.0 | ⭐⭐⭐ |
| **JDK 7** | 2011 | try-with-resources、NIO 2.0、Fork/Join | ⭐⭐⭐⭐ |
| **JDK 8** | 2014 | Lambda、Stream、Optional、新日期 API | ⭐⭐⭐⭐⭐ |

### 面试要点总结

1. **JDK 6**：工具增强（脚本引擎、编译器 API）
2. **JDK 7**：语法糖（Diamond、try-with-resources、switch String）+ NIO 2.0
3. **JDK 8**：函数式编程（Lambda、Stream、Optional）+ 新日期 API

**记忆口诀**：
- JDK 6：工具强
- JDK 7：语法糖
- JDK 8：函数式

JDK 8 是最重要的版本，Lambda 和 Stream 是现代 Java 开发的基础，必须熟练掌握。
