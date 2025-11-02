---
layout: post
title: "Spring的事务传播机制有哪些？"
date: 2025-11-02
description: "全面解析Spring的7种事务传播行为，包括REQUIRED、REQUIRES_NEW等常用传播机制的原理和应用场景"
author: "wuxl"
categories: [Spring框架]
tags: [Spring, 事务传播, Propagation, 事务管理, @Transactional]
---

## 问题

Spring的事务传播机制有哪些？

## 答案

### 一、核心概念

**事务传播行为（Propagation）** 定义了当一个事务方法被另一个事务方法调用时，事务应该如何传播。

Spring定义了 **7种传播行为**，通过 `@Transactional(propagation = Propagation.XXX)` 来指定。

### 二、7种传播行为详解

#### 1. REQUIRED（默认，最常用）

**行为：** 如果当前存在事务，则加入该事务；如果没有事务，则创建新事务。

```java
@Transactional(propagation = Propagation.REQUIRED)
public void methodA() {
    // 操作1
    methodB(); // 加入到methodA的事务中
}

@Transactional(propagation = Propagation.REQUIRED)
public void methodB() {
    // 操作2
}
```

**场景：** 默认行为，适用于大部分业务场景。

---

#### 2. REQUIRES_NEW（高频考点）

**行为：** 无论当前是否存在事务，都创建新事务；如果存在外部事务，则挂起外部事务。

```java
@Transactional
public void methodA() {
    // 事务A
    orderService.createOrder(); // 创建新事务B
    // 即使这里抛异常，createOrder的事务B已提交，不会回滚
}

@Transactional(propagation = Propagation.REQUIRES_NEW)
public void createOrder() {
    // 新事务B（独立于外部事务）
}
```

**场景：** 日志记录、审计操作（需要独立提交，不受外部事务影响）。

---

#### 3. SUPPORTS

**行为：** 如果当前存在事务，则加入事务；如果没有事务，则以非事务方式执行。

```java
@Transactional(propagation = Propagation.SUPPORTS)
public void query() {
    // 查询操作，有事务就用，没有也无所谓
}
```

**场景：** 只读查询操作。

---

#### 4. NOT_SUPPORTED

**行为：** 以非事务方式执行；如果当前存在事务，则挂起当前事务。

```java
@Transactional(propagation = Propagation.NOT_SUPPORTED)
public void sendEmail() {
    // 非事务操作（即使外部有事务也不参与）
}
```

**场景：** 发送邮件、调用第三方接口等不需要事务的操作。

---

#### 5. MANDATORY（强制）

**行为：** 必须在事务中运行，如果当前没有事务，则抛出异常。

```java
@Transactional(propagation = Propagation.MANDATORY)
public void updateInventory() {
    // 必须在事务中调用，否则抛异常
}
```

**场景：** 强制调用者提供事务上下文。

---

#### 6. NEVER

**行为：** 必须在非事务中运行，如果当前存在事务，则抛出异常。

```java
@Transactional(propagation = Propagation.NEVER)
public void statisticsReport() {
    // 禁止在事务中调用
}
```

**场景：** 确保某些方法不在事务环境中执行。

---

#### 7. NESTED（嵌套事务）

**行为：** 如果当前存在事务，则在嵌套事务中执行；如果没有事务，则类似REQUIRED。

**关键点：** 基于数据库的SavePoint机制，内部事务回滚不影响外部事务，但外部事务回滚会影响内部事务。

```java
@Transactional
public void methodA() {
    // 外部事务
    try {
        methodB(); // 嵌套事务
    } catch (Exception e) {
        // methodB回滚，但methodA可以继续
    }
}

@Transactional(propagation = Propagation.NESTED)
public void methodB() {
    // 嵌套事务（基于SavePoint）
}
```

**场景：** 部分操作允许失败，但不影响主流程。

**注意：** 需要数据库支持SavePoint（如MySQL的InnoDB）。

---

### 三、常见对比

| 传播行为 | 有外部事务 | 无外部事务 | 使用场景 |
|---------|-----------|-----------|---------|
| **REQUIRED** | 加入事务 | 创建新事务 | **默认，最常用** |
| **REQUIRES_NEW** | 挂起外部事务，创建新事务 | 创建新事务 | **独立提交（日志、审计）** |
| **NESTED** | 创建嵌套事务（SavePoint） | 创建新事务 | **部分回滚** |
| **SUPPORTS** | 加入事务 | 非事务执行 | 只读查询 |
| **NOT_SUPPORTED** | 挂起事务 | 非事务执行 | 第三方调用 |
| **MANDATORY** | 加入事务 | **抛异常** | 强制要求事务 |
| **NEVER** | **抛异常** | 非事务执行 | 禁止事务 |

### 四、实战案例

```java
@Service
public class OrderService {

    @Autowired
    private OrderMapper orderMapper;
    @Autowired
    private LogService logService;

    @Transactional
    public void placeOrder(Order order) {
        // 1. 插入订单（REQUIRED，加入当前事务）
        orderMapper.insert(order);

        // 2. 记录日志（REQUIRES_NEW，独立事务，必定保存）
        logService.saveLog("订单创建", order.getId());

        // 3. 扣减库存（可能失败）
        try {
            inventoryService.deduct(order.getProductId());
        } catch (Exception e) {
            // 即使库存扣减失败，日志已保存
            throw e;
        }
    }
}

@Service
public class LogService {

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void saveLog(String action, Long orderId) {
        // 独立事务，不受外部事务影响
        logMapper.insert(new Log(action, orderId));
    }
}
```

### 五、答题总结

**简洁回答：**

Spring提供了 **7种事务传播行为**：

1. **REQUIRED（默认）**：有事务就用，没有就创建
2. **REQUIRES_NEW**：总是创建新事务，挂起外部事务
3. **NESTED**：嵌套事务（基于SavePoint）
4. **SUPPORTS**：有事务就用，没有则非事务执行
5. **NOT_SUPPORTED**：总是非事务执行，挂起外部事务
6. **MANDATORY**：必须有事务，否则抛异常
7. **NEVER**：必须非事务，否则抛异常

**高频考点：**
- **REQUIRED** 和 **REQUIRES_NEW** 的区别：前者共享事务，后者独立事务
- **REQUIRES_NEW** 的应用场景：日志记录、审计操作（需要独立提交）
- **NESTED** 需要数据库支持SavePoint，适合部分回滚场景
