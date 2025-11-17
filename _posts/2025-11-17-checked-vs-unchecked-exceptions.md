---
layout: post
title: "什么是受检异常与非受检异常？"
date: 2025-11-17
description: "深入理解 Java 中受检异常和非受检异常的区别、使用场景及最佳实践"
author: "wuxl"
categories: [Java基础]
tags: [异常处理, 受检异常, 非受检异常, Exception]
---

## 问题

什么是受检异常与非受检异常？

## 答案

### 核心结论

**受检异常（Checked Exception）**：
- 编译时必须处理的异常（捕获或声明抛出）
- 继承自 `Exception` 但不是 `RuntimeException` 的子类
- 代表可预见的、可恢复的异常情况

**非受检异常（Unchecked Exception）**：
- 编译时不强制处理的异常
- 包括 `RuntimeException` 及其子类，以及 `Error` 及其子类
- 代表编程错误或系统错误

### 异常分类体系

```
Throwable
├── Error (非受检异常)
│   ├── OutOfMemoryError
│   ├── StackOverflowError
│   └── ...
└── Exception
    ├── IOException (受检异常)
    ├── SQLException (受检异常)
    ├── ClassNotFoundException (受检异常)
    └── RuntimeException (非受检异常)
        ├── NullPointerException
        ├── ArrayIndexOutOfBoundsException
        └── ...
```

### 受检异常（Checked Exception）

#### 特点

1. **编译时检查**：必须显式处理，否则编译不通过
2. **可预见性**：通常是外部因素导致，可以预见并恢复
3. **强制处理**：必须用 `try-catch` 捕获或用 `throws` 声明

#### 常见受检异常

| 异常类型 | 触发场景 |
|---------|---------|
| `IOException` | 文件读写、网络通信失败 |
| `FileNotFoundException` | 文件不存在 |
| `SQLException` | 数据库操作失败 |
| `ClassNotFoundException` | 类加载失败 |
| `InterruptedException` | 线程中断 |
| `ParseException` | 日期/数字解析失败 |

#### 代码示例

```java
// 示例 1：必须捕获或声明抛出
public class CheckedExceptionDemo {
    // 方式一：使用 try-catch 捕获
    public void readFile1(String path) {
        try {
            FileReader reader = new FileReader(path);
            // 读取文件
            reader.close();
        } catch (FileNotFoundException e) {
            System.out.println("文件不存在: " + e.getMessage());
        } catch (IOException e) {
            System.out.println("读取文件失败: " + e.getMessage());
        }
    }

    // 方式二：使用 throws 声明抛出
    public void readFile2(String path) throws IOException {
        FileReader reader = new FileReader(path);
        // 读取文件
        reader.close();
    }

    // 方式三：JDK7+ try-with-resources（推荐）
    public void readFile3(String path) {
        try (FileReader reader = new FileReader(path)) {
            // 读取文件，自动关闭资源
        } catch (IOException e) {
            System.out.println("文件操作失败: " + e.getMessage());
        }
    }
}
```

```java
// 示例 2：数据库操作
public class DatabaseDemo {
    public List<User> queryUsers() throws SQLException {
        Connection conn = null;
        PreparedStatement stmt = null;
        ResultSet rs = null;
        List<User> users = new ArrayList<>();

        try {
            conn = DriverManager.getConnection("jdbc:mysql://localhost:3306/db", "user", "pass");
            stmt = conn.prepareStatement("SELECT * FROM users");
            rs = stmt.executeQuery();

            while (rs.next()) {
                User user = new User();
                user.setId(rs.getInt("id"));
                user.setName(rs.getString("name"));
                users.add(user);
            }
        } finally {
            // 关闭资源
            if (rs != null) rs.close();
            if (stmt != null) stmt.close();
            if (conn != null) conn.close();
        }

        return users;
    }
}
```

### 非受检异常（Unchecked Exception）

#### 特点

1. **编译时不检查**：不强制处理，编译器不会报错
2. **编程错误**：通常是代码逻辑错误导致
3. **可选处理**：可以捕获，但更应该通过代码逻辑避免

#### 常见非受检异常

| 异常类型 | 触发场景 |
|---------|---------|
| `NullPointerException` | 空指针访问 |
| `ArrayIndexOutOfBoundsException` | 数组越界 |
| `ClassCastException` | 类型转换错误 |
| `IllegalArgumentException` | 非法参数 |
| `ArithmeticException` | 算术错误（如除零） |
| `IllegalStateException` | 非法状态 |

#### 代码示例

```java
public class UncheckedExceptionDemo {
    // 非受检异常不需要强制处理
    public void divide(int a, int b) {
        // 可能抛出 ArithmeticException，但不需要 try-catch
        int result = a / b;
        System.out.println("结果: " + result);
    }

    // 推荐：通过防御性编程避免异常
    public void divideSafe(int a, int b) {
        if (b == 0) {
            throw new IllegalArgumentException("除数不能为 0");
        }
        int result = a / b;
        System.out.println("结果: " + result);
    }

    // 处理空指针
    public void processString(String str) {
        // 不推荐：依赖 try-catch
        try {
            System.out.println(str.length());
        } catch (NullPointerException e) {
            System.out.println("字符串为 null");
        }

        // 推荐：提前检查
        if (str != null) {
            System.out.println(str.length());
        } else {
            System.out.println("字符串为 null");
        }

        // 更推荐：使用 Java 8+ Optional 或工具类
        Objects.requireNonNull(str, "字符串不能为 null");
        System.out.println(str.length());
    }
}
```

### 对比总结

| 特性 | 受检异常 | 非受检异常 |
|------|---------|-----------|
| **父类** | `Exception`（非 `RuntimeException`） | `RuntimeException` 或 `Error` |
| **编译检查** | ✅ 必须处理 | ❌ 不强制处理 |
| **触发原因** | 外部因素（IO、网络、数据库等） | 编程错误或系统错误 |
| **可恢复性** | 通常可恢复 | 通常不可恢复或不应恢复 |
| **处理方式** | `try-catch` 或 `throws` | 防御性编程，避免发生 |
| **典型示例** | `IOException`、`SQLException` | `NullPointerException`、`OutOfMemoryError` |

### 设计原则与最佳实践

#### 1. 何时使用受检异常

```java
// 适合使用受检异常的场景：外部资源操作
public class FileService {
    // 文件可能不存在，调用者应该处理
    public String readFile(String path) throws IOException {
        return Files.readString(Paths.get(path));
    }

    // 网络请求可能失败，调用者应该处理
    public String fetchData(String url) throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        // 处理请求
        return "data";
    }
}
```

#### 2. 何时使用非受检异常

```java
// 适合使用非受检异常的场景：参数校验
public class UserService {
    public void createUser(String username, int age) {
        // 参数错误是编程错误，使用非受检异常
        if (username == null || username.isEmpty()) {
            throw new IllegalArgumentException("用户名不能为空");
        }
        if (age < 0 || age > 150) {
            throw new IllegalArgumentException("年龄必须在 0-150 之间");
        }
        // 创建用户
    }
}
```

#### 3. 不要过度使用受检异常

```java
// ❌ 不推荐：滥用受检异常
public void validateAge(int age) throws InvalidAgeException {
    if (age < 0) {
        throw new InvalidAgeException("年龄不能为负数");
    }
}

// ✅ 推荐：参数校验使用非受检异常
public void validateAge(int age) {
    if (age < 0) {
        throw new IllegalArgumentException("年龄不能为负数");
    }
}
```

#### 4. 异常转换

```java
// 将受检异常转换为非受检异常（适用于框架层）
public class DataAccessException extends RuntimeException {
    public DataAccessException(String message, Throwable cause) {
        super(message, cause);
    }
}

public class UserDao {
    public User findById(int id) {
        try {
            // 数据库操作
            Connection conn = getConnection();
            // ...
        } catch (SQLException e) {
            // 转换为非受检异常，简化调用者代码
            throw new DataAccessException("查询用户失败", e);
        }
    }
}
```

### 实际应用场景

```java
public class ExceptionBestPractice {
    // 场景 1：文件上传（受检异常）
    public void uploadFile(MultipartFile file) throws IOException {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("文件不能为空");  // 非受检
        }

        String path = "/uploads/" + file.getOriginalFilename();
        file.transferTo(new File(path));  // 可能抛出 IOException（受检）
    }

    // 场景 2：业务逻辑校验（非受检异常）
    public void transfer(Account from, Account to, BigDecimal amount) {
        if (amount.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("转账金额必须大于 0");
        }
        if (from.getBalance().compareTo(amount) < 0) {
            throw new IllegalStateException("余额不足");
        }
        // 执行转账
    }

    // 场景 3：外部 API 调用（受检异常）
    public String callExternalApi(String url) throws IOException {
        HttpClient client = HttpClient.newHttpClient();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .build();

        HttpResponse<String> response = client.send(request,
                HttpResponse.BodyHandlers.ofString());

        return response.body();
    }
}
```

### 面试要点总结

1. **受检异常**：
   - 编译时必须处理
   - 代表可预见的外部错误
   - 典型：IO、SQL、网络异常

2. **非受检异常**：
   - 编译时不强制处理
   - 代表编程错误或系统错误
   - 典型：空指针、数组越界、类型转换

3. **设计原则**：
   - 外部资源操作 → 受检异常
   - 参数校验、编程错误 → 非受检异常
   - 避免过度使用受检异常

4. **最佳实践**：
   - 受检异常：用 `try-with-resources` 管理资源
   - 非受检异常：通过防御性编程避免
   - 异常转换：框架层可将受检异常转为非受检异常

```java
// 记忆口诀
// 受检异常：IO、SQL、网络，编译必须管
// 非受检异常：空指针、越界、转换，编程错误自己担
```

这道题考察的是对 Java 异常处理机制的深入理解，是面试中的重要考点。
