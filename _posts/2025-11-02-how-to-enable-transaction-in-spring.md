---
layout: post
title: "Spring中如何开启事务？"
date: 2025-11-02
description: "详解Spring事务的两种开启方式：声明式事务和编程式事务，包括配置方法和使用示例"
author: "wuxl"
categories: [Spring框架]
tags: [Spring, 事务管理, @Transactional, 声明式事务, 编程式事务]
---

## 问题

Spring中如何开启事务？

## 答案

### 一、核心概念

Spring提供了两种事务管理方式：
1. **声明式事务**：通过注解或XML配置，由Spring AOP自动管理事务
2. **编程式事务**：通过编程API手动控制事务的开启、提交和回滚

**实际开发中，95%的场景使用声明式事务**，因为它简洁、无侵入、易维护。

### 二、声明式事务（推荐）

#### 1. 基于注解（最常用）

**开启步骤：**

```java
// 1. 在配置类上添加 @EnableTransactionManagement
@Configuration
@EnableTransactionManagement
public class AppConfig {

    @Bean
    public DataSource dataSource() {
        // 配置数据源
        return new HikariDataSource();
    }

    @Bean
    public PlatformTransactionManager transactionManager(DataSource dataSource) {
        return new DataSourceTransactionManager(dataSource);
    }
}

// 2. 在Service方法上使用 @Transactional
@Service
public class UserService {

    @Autowired
    private UserMapper userMapper;

    @Transactional(rollbackFor = Exception.class)
    public void createUser(User user) {
        userMapper.insert(user);
        // 如果发生异常，事务自动回滚
    }
}
```

#### 2. 基于XML配置（传统方式）

```xml
<!-- 配置事务管理器 -->
<bean id="transactionManager" class="org.springframework.jdbc.datasource.DataSourceTransactionManager">
    <property name="dataSource" ref="dataSource"/>
</bean>

<!-- 开启事务注解驱动 -->
<tx:annotation-driven transaction-manager="transactionManager"/>
```

### 三、编程式事务

适用于需要精细控制事务边界的场景。

#### 1. 使用 TransactionTemplate

```java
@Service
public class OrderService {

    @Autowired
    private TransactionTemplate transactionTemplate;

    public void processOrder(Order order) {
        transactionTemplate.execute(status -> {
            try {
                // 执行业务逻辑
                orderMapper.insert(order);
                inventoryService.deduct(order.getProductId());
                return true;
            } catch (Exception e) {
                status.setRollbackOnly(); // 手动标记回滚
                throw e;
            }
        });
    }
}
```

#### 2. 使用 PlatformTransactionManager

```java
@Service
public class PaymentService {

    @Autowired
    private PlatformTransactionManager transactionManager;

    public void payment(Payment payment) {
        TransactionDefinition def = new DefaultTransactionDefinition();
        TransactionStatus status = transactionManager.getTransaction(def);

        try {
            paymentMapper.insert(payment);
            accountService.deduct(payment.getAmount());
            transactionManager.commit(status); // 手动提交
        } catch (Exception e) {
            transactionManager.rollback(status); // 手动回滚
            throw e;
        }
    }
}
```

### 四、关键配置说明

#### @Transactional常用属性

```java
@Transactional(
    propagation = Propagation.REQUIRED,      // 事务传播行为
    isolation = Isolation.DEFAULT,           // 隔离级别
    timeout = 30,                             // 超时时间（秒）
    readOnly = false,                         // 是否只读
    rollbackFor = Exception.class,            // 回滚异常类型
    noRollbackFor = BusinessException.class   // 不回滚的异常
)
```

### 五、答题总结

**简洁回答：**

Spring开启事务主要有两种方式：

1. **声明式事务**（推荐）：
   - 在配置类上添加 `@EnableTransactionManagement`
   - 配置 `PlatformTransactionManager` Bean
   - 在方法上使用 `@Transactional` 注解

2. **编程式事务**：
   - 使用 `TransactionTemplate` 或 `PlatformTransactionManager` API
   - 适合需要精细控制事务边界的场景

**实际开发中优先使用声明式事务**，因为它通过AOP实现，代码简洁、无侵入性，且符合Spring的设计理念。只有在需要动态控制事务边界时才考虑编程式事务。
