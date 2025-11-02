---
layout: post
title: "什么是模板方法模式？"
date: 2025-11-02
description: "详解模板方法模式的定义、实现原理、钩子方法的使用，以及在Spring框架、JDBC、Servlet中的实际应用"
author: "wuxl"
categories: [设计模式]
tags: [模板方法模式, 设计模式, 继承, Spring, JDBC, 钩子方法]
---

## 问题

什么是模板方法模式?

## 答案

### 1. 核心概念

**模板方法模式（Template Method Pattern）** 是一种行为型设计模式，在父类中定义算法的骨架（模板），将某些步骤延迟到子类实现。模板方法使得子类可以在不改变算法整体结构的情况下，重新定义算法的某些特定步骤。

**核心思想**：
- **父类**：定义算法流程框架（模板方法），控制执行顺序
- **子类**：实现具体步骤（抽象方法），不改变流程结构

**典型应用场景**：
- 数据访问层的通用操作流程（打开连接 → 执行 SQL → 关闭连接）
- HTTP 请求处理流程（解析请求 → 业务处理 → 返回响应）
- Spring 的 JdbcTemplate、RestTemplate
- Servlet 的 service() 方法

### 2. 实现原理与代码示例

#### 基础实现

```java
// 抽象类：定义模板方法
abstract class DataProcessor {

    // 模板方法：定义算法骨架（final 防止子类修改流程）
    public final void process() {
        openConnection();    // 步骤1：打开连接
        extractData();       // 步骤2：提取数据（子类实现）
        processData();       // 步骤3：处理数据（子类实现）
        closeConnection();   // 步骤4：关闭连接
    }

    // 通用步骤：父类实现
    private void openConnection() {
        System.out.println("打开数据连接");
    }

    // 抽象步骤：子类必须实现
    protected abstract void extractData();
    protected abstract void processData();

    // 通用步骤：父类实现
    private void closeConnection() {
        System.out.println("关闭数据连接");
    }
}

// 具体子类1：CSV 数据处理
class CsvDataProcessor extends DataProcessor {
    @Override
    protected void extractData() {
        System.out.println("从 CSV 文件提取数据");
    }

    @Override
    protected void processData() {
        System.out.println("处理 CSV 数据格式");
    }
}

// 具体子类2：JSON 数据处理
class JsonDataProcessor extends DataProcessor {
    @Override
    protected void extractData() {
        System.out.println("从 JSON 文件提取数据");
    }

    @Override
    protected void processData() {
        System.out.println("处理 JSON 数据格式");
    }
}

// 使用示例
public class Client {
    public static void main(String[] args) {
        DataProcessor csvProcessor = new CsvDataProcessor();
        csvProcessor.process();

        System.out.println("---");

        DataProcessor jsonProcessor = new JsonDataProcessor();
        jsonProcessor.process();
    }
}
```

**输出结果**：
```
打开数据连接
从 CSV 文件提取数据
处理 CSV 数据格式
关闭数据连接
---
打开数据连接
从 JSON 文件提取数据
处理 JSON 数据格式
关闭数据连接
```

### 3. 钩子方法（Hook Method）

钩子方法是一种特殊的模板方法技巧，允许子类通过覆盖钩子方法来影响模板流程，但不强制子类实现。

```java
abstract class DataProcessor {

    // 模板方法
    public final void process() {
        openConnection();
        extractData();
        processData();

        // 钩子方法：可选的数据验证步骤
        if (needValidation()) {
            validateData();
        }

        closeConnection();
    }

    // 通用步骤
    private void openConnection() {
        System.out.println("打开数据连接");
    }

    // 抽象步骤
    protected abstract void extractData();
    protected abstract void processData();

    // 钩子方法：默认实现，子类可选择覆盖
    protected boolean needValidation() {
        return false; // 默认不需要验证
    }

    protected void validateData() {
        System.out.println("验证数据完整性");
    }

    private void closeConnection() {
        System.out.println("关闭数据连接");
    }
}

// 子类可以通过钩子方法控制流程
class SecureCsvProcessor extends DataProcessor {
    @Override
    protected void extractData() {
        System.out.println("从 CSV 文件提取数据");
    }

    @Override
    protected void processData() {
        System.out.println("处理 CSV 数据格式");
    }

    // 覆盖钩子方法，启用验证
    @Override
    protected boolean needValidation() {
        return true;
    }
}
```

**钩子方法特点**：
- 提供默认实现（可以是空方法或返回默认值）
- 子类可选择性覆盖
- 用于控制模板流程的可选步骤

### 4. Spring 中的模板方法模式

#### JdbcTemplate

```java
public class JdbcTemplate {

    // 模板方法：定义 JDBC 操作流程
    public <T> T execute(ConnectionCallback<T> action) {
        Connection con = null;
        try {
            // 步骤1：获取连接
            con = getConnection();

            // 步骤2：执行具体操作（由回调对象实现）
            return action.doInConnection(con);

        } catch (SQLException ex) {
            // 步骤3：异常处理
            throw new DataAccessException(ex);
        } finally {
            // 步骤4：释放连接
            releaseConnection(con);
        }
    }

    private Connection getConnection() { ... }
    private void releaseConnection(Connection con) { ... }
}

// 使用示例
jdbcTemplate.execute(new ConnectionCallback<Integer>() {
    public Integer doInConnection(Connection con) throws SQLException {
        PreparedStatement ps = con.prepareStatement("SELECT COUNT(*) FROM users");
        ResultSet rs = ps.executeQuery();
        rs.next();
        return rs.getInt(1);
    }
});
```

**优势**：
- 自动管理连接和资源释放
- 统一异常处理
- 简化 JDBC 样板代码

#### HttpServlet

```java
public abstract class HttpServlet {

    // 模板方法
    protected void service(HttpServletRequest req, HttpServletResponse resp) {
        String method = req.getMethod();

        if (method.equals("GET")) {
            doGet(req, resp);
        } else if (method.equals("POST")) {
            doPost(req, resp);
        } else if (method.equals("PUT")) {
            doPut(req, resp);
        }
        // ... 其他 HTTP 方法
    }

    // 抽象方法：子类实现具体的业务逻辑
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        // 默认实现：返回 405 Method Not Allowed
    }

    protected void doPost(HttpServletRequest req, HttpServletResponse resp) {
        // 默认实现
    }
}

// 子类只需实现需要的方法
public class MyServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        // 处理 GET 请求
    }
}
```

#### AbstractApplicationContext

```java
public abstract class AbstractApplicationContext {

    // 模板方法：定义容器刷新流程
    public void refresh() {
        prepareRefresh();           // 刷新前准备
        ConfigurableListableBeanFactory beanFactory = obtainFreshBeanFactory();
        prepareBeanFactory(beanFactory);

        try {
            postProcessBeanFactory(beanFactory);  // 钩子方法
            invokeBeanFactoryPostProcessors(beanFactory);
            registerBeanPostProcessors(beanFactory);
            initMessageSource();
            initApplicationEventMulticaster();
            onRefresh();              // 钩子方法（子类扩展点）
            registerListeners();
            finishBeanFactoryInitialization(beanFactory);
            finishRefresh();
        } catch (BeansException ex) {
            destroyBeans();
            cancelRefresh(ex);
        }
    }

    // 钩子方法：子类可覆盖
    protected void onRefresh() throws BeansException {
        // 默认为空，子类可扩展
    }
}
```

### 5. 模板方法 vs 策略模式

| 对比维度 | 模板方法模式 | 策略模式 |
|---------|------------|---------|
| **实现方式** | 继承（父类定义流程） | 组合（持有策略对象） |
| **流程控制** | 父类控制整体流程 | 客户端控制策略选择 |
| **扩展方式** | 子类覆盖方法 | 新增策略类 |
| **耦合度** | 子类依赖父类（高） | 策略间独立（低） |
| **适用场景** | 流程固定，步骤可变 | 算法可互换 |

### 6. 优缺点分析

**优点**：
- ✅ 复用通用代码，减少重复
- ✅ 控制流程顺序，确保执行规范
- ✅ 符合开闭原则（新增子类扩展功能）
- ✅ 符合里氏替换原则（子类可替换父类）

**缺点**：
- ❌ 增加类的数量（每个变体需要一个子类）
- ❌ 继承的强耦合（子类依赖父类实现）
- ❌ 违反依赖倒置原则（依赖具体的父类）

### 7. 答题总结

**简洁回答模板**：

"模板方法模式在父类中定义算法骨架，将某些步骤延迟到子类实现，保证流程一致性。

**核心结构**：
1. **父类**：定义模板方法（final）和算法流程
2. **抽象方法**：子类必须实现的步骤
3. **钩子方法**：子类可选择性覆盖的扩展点

**典型应用**：
- Spring 的 JdbcTemplate、RestTemplate（封装资源管理）
- HttpServlet 的 service() 方法（HTTP 请求分发）
- AbstractApplicationContext 的 refresh() 方法（容器初始化流程）

**与策略模式的区别**：
- 模板方法用继承，父类控制流程
- 策略模式用组合，客户端选择算法

适用于流程固定但步骤实现多样的场景，能有效复用代码并保证执行规范。"
