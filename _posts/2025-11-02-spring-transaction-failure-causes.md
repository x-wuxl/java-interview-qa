---
layout: post
title: "Spring事务失效可能是哪些原因？"
date: 2025-11-02
description: "详解Spring事务失效的8大常见原因及解决方案，包括方法非public、自调用、异常类型不匹配等高频面试考点"
author: "wuxl"
categories: [Spring框架]
tags: [Spring, 事务失效, "@Transactional", AOP, 事务回滚]
---

## 问题

Spring事务失效可能是哪些原因？

## 答案

### 一、核心原理

Spring事务基于 **AOP动态代理** 实现，事务失效本质是代理未生效或事务配置不当。

### 二、8种常见失效原因

#### 1. 方法不是public（最易忽略）

**原因：** `@Transactional` 只能作用于 `public` 方法，因为Spring AOP基于JDK动态代理或CGLIB代理，默认只代理public方法。

```java
@Service
public class UserService {

    // ❌ 事务不生效
    @Transactional
    private void updateUser(User user) {
        userMapper.update(user);
    }

    // ✅ 正确写法
    @Transactional
    public void updateUser(User user) {
        userMapper.update(user);
    }
}
```

**解决：** 改为 `public` 方法。

---

#### 2. 方法被类内部调用（自调用问题）

**原因：** 类内部的方法调用不会经过代理对象，而是直接调用目标对象（this），导致事务不生效。

```java
@Service
public class OrderService {

    // ❌ 内部调用，事务不生效
    public void placeOrder(Order order) {
        this.saveOrder(order); // 直接调用，不走代理
    }

    @Transactional
    public void saveOrder(Order order) {
        orderMapper.insert(order);
    }
}
```

**解决方案：**

```java
// 方案1：注入自己（推荐）
@Service
public class OrderService {

    @Autowired
    private OrderService self;

    public void placeOrder(Order order) {
        self.saveOrder(order); // 通过代理调用
    }

    @Transactional
    public void saveOrder(Order order) {
        orderMapper.insert(order);
    }
}

// 方案2：使用AopContext（需开启expose-proxy）
@EnableAspectJAutoProxy(exposeProxy = true)
public void placeOrder(Order order) {
    ((OrderService) AopContext.currentProxy()).saveOrder(order);
}
```

---

#### 3. 异常类型不匹配

**原因：** Spring默认只对 **RuntimeException** 和 **Error** 回滚，不对受检异常（Checked Exception）回滚。

```java
@Transactional
public void createUser(User user) throws Exception {
    userMapper.insert(user);
    // ❌ 抛出Exception不会回滚
    throw new Exception("业务异常");
}
```

**解决：**

```java
// 方案1：指定回滚异常类型（推荐）
@Transactional(rollbackFor = Exception.class)
public void createUser(User user) throws Exception {
    userMapper.insert(user);
    throw new Exception("业务异常"); // ✅ 会回滚
}

// 方案2：抛出RuntimeException
@Transactional
public void createUser(User user) {
    userMapper.insert(user);
    throw new RuntimeException("业务异常"); // ✅ 会回滚
}
```

---

#### 4. 异常被捕获未抛出

**原因：** 事务方法内部捕获了异常但未重新抛出，Spring感知不到异常，不会回滚。

```java
@Transactional
public void transferMoney(Long fromId, Long toId, BigDecimal amount) {
    try {
        accountMapper.deduct(fromId, amount);
        accountMapper.add(toId, amount);
        int i = 1 / 0; // 异常
    } catch (Exception e) {
        // ❌ 异常被吞掉，事务不会回滚
        log.error("转账失败", e);
    }
}
```

**解决：**

```java
@Transactional(rollbackFor = Exception.class)
public void transferMoney(Long fromId, Long toId, BigDecimal amount) {
    try {
        accountMapper.deduct(fromId, amount);
        accountMapper.add(toId, amount);
    } catch (Exception e) {
        log.error("转账失败", e);
        throw e; // ✅ 重新抛出异常
    }
}

// 或手动回滚
@Transactional
public void transferMoney(Long fromId, Long toId, BigDecimal amount) {
    try {
        accountMapper.deduct(fromId, amount);
        accountMapper.add(toId, amount);
    } catch (Exception e) {
        TransactionAspectSupport.currentTransactionStatus().setRollbackOnly(); // 手动标记回滚
    }
}
```

---

#### 5. 数据库引擎不支持事务

**原因：** MySQL的MyISAM引擎不支持事务，只有InnoDB支持。

```sql
-- 检查表引擎
SHOW CREATE TABLE user;

-- 修改为InnoDB
ALTER TABLE user ENGINE=InnoDB;
```

---

#### 6. 传播行为配置错误

**原因：** 配置了不支持事务的传播行为，如 `NOT_SUPPORTED`、`NEVER`。

```java
// ❌ 不支持事务
@Transactional(propagation = Propagation.NOT_SUPPORTED)
public void updateUser(User user) {
    userMapper.update(user);
}
```

**解决：** 使用默认的 `REQUIRED` 或其他支持事务的传播行为。

---

#### 7. 未开启事务管理

**原因：** 没有配置 `@EnableTransactionManagement` 或事务管理器。

```java
// ❌ 缺少配置
@Configuration
public class AppConfig {
    // 缺少事务管理器配置
}

// ✅ 正确配置
@Configuration
@EnableTransactionManagement
public class AppConfig {

    @Bean
    public PlatformTransactionManager transactionManager(DataSource dataSource) {
        return new DataSourceTransactionManager(dataSource);
    }
}
```

---

#### 8. 多线程调用

**原因：** Spring事务基于ThreadLocal，新线程中无法获取原事务上下文。

```java
@Transactional
public void batchProcess(List<Order> orders) {
    orders.parallelStream().forEach(order -> {
        // ❌ 在新线程中，事务不生效
        orderMapper.insert(order);
    });
}
```

**解决：** 不要在事务方法中使用多线程，或为每个线程单独开启事务。

---

### 三、快速排查清单

| 失效原因 | 排查方法 | 解决方案 |
|---------|---------|---------|
| 方法非public | 检查方法修饰符 | 改为public |
| 自调用 | 检查是否用this调用 | 注入自己或使用AopContext |
| 异常类型不匹配 | 检查是否是Checked Exception | 加rollbackFor=Exception.class |
| 异常被捕获 | 检查try-catch | 重新抛出或手动标记回滚 |
| 数据库引擎 | 检查表引擎 | 改为InnoDB |
| 传播行为错误 | 检查propagation配置 | 使用REQUIRED |
| 未开启事务管理 | 检查配置类 | 加@EnableTransactionManagement |
| 多线程 | 检查是否有并行流 | 避免多线程或单独开启事务 |

### 四、答题总结

**简洁回答：**

Spring事务失效的常见原因有：

1. **方法不是public**（AOP只代理public方法）
2. **类内部自调用**（不走代理对象）
3. **异常类型不匹配**（默认只回滚RuntimeException）
4. **异常被捕获未抛出**（Spring感知不到异常）
5. **数据库引擎不支持**（如MyISAM）
6. **传播行为配置错误**（如NOT_SUPPORTED）
7. **未开启事务管理**（缺少@EnableTransactionManagement）
8. **多线程调用**（事务基于ThreadLocal）

**最高频的3个原因：** 自调用、异常类型不匹配、异常被捕获。

**排查思路：** 检查代理是否生效（方法修饰符、调用方式）→ 检查异常处理（类型、是否重新抛出）→ 检查配置（事务管理器、数据库引擎）。
