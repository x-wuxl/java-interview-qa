---
layout: post
title: "Spring中的事务事件如何使用？"
date: 2025-11-02
description: "详解Spring事务事件机制@TransactionalEventListener的使用方法、执行时机和实际应用场景"
author: "wuxl"
categories: [Spring框架]
tags: [Spring, 事务事件, "@TransactionalEventListener", 事件驱动, 事务回调]
---

## 问题

Spring中的事务事件如何使用？

## 答案

### 一、核心概念

**事务事件（Transactional Event）** 是Spring提供的一种机制，允许在事务的特定阶段（提交前、提交后、回滚后等）触发事件监听器，解决事务与异步操作的协调问题。

**关键注解：** `@TransactionalEventListener`

### 二、基本用法

#### 1. 定义事件

```java
// 事件类（普通POJO）
public class OrderCreatedEvent {
    private final Order order;

    public OrderCreatedEvent(Order order) {
        this.order = order;
    }

    public Order getOrder() {
        return order;
    }
}
```

#### 2. 发布事件

```java
@Service
public class OrderService {

    @Autowired
    private ApplicationEventPublisher eventPublisher;

    @Transactional
    public void createOrder(Order order) {
        // 1. 保存订单
        orderMapper.insert(order);

        // 2. 发布事件
        eventPublisher.publishEvent(new OrderCreatedEvent(order));

        // 3. 事务提交后，监听器才会执行
    }
}
```

#### 3. 监听事件

```java
@Component
public class OrderEventListener {

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleOrderCreated(OrderCreatedEvent event) {
        // 在事务提交后执行
        Order order = event.getOrder();

        // 发送邮件、推送消息等
        emailService.sendOrderConfirmation(order);
        smsService.sendNotification(order.getUserId());
    }
}
```

---

### 三、事务阶段（TransactionPhase）

#### 1. AFTER_COMMIT（默认，最常用）

**执行时机：** 事务成功提交后执行。

```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void handleAfterCommit(OrderCreatedEvent event) {
    // ✅ 事务已提交，数据已持久化
    // 适合：发送邮件、推送消息、记录日志
}
```

**应用场景：**
- 发送通知（邮件、短信、站内信）
- 清除缓存
- 发送MQ消息
- 调用第三方接口

---

#### 2. BEFORE_COMMIT

**执行时机：** 事务提交前执行，但还在事务中。

```java
@TransactionalEventListener(phase = TransactionPhase.BEFORE_COMMIT)
public void handleBeforeCommit(OrderCreatedEvent event) {
    // ⚠️ 事务还未提交，数据未持久化
    // 适合：数据校验、补充操作
    Order order = event.getOrder();
    orderMapper.updateStatus(order.getId(), "PENDING");
}
```

**应用场景：**
- 在提交前进行最后的数据校验
- 补充一些数据操作（仍在事务中）

---

#### 3. AFTER_ROLLBACK

**执行时机：** 事务回滚后执行。

```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_ROLLBACK)
public void handleAfterRollback(OrderCreatedEvent event) {
    // ❌ 事务已回滚，数据未保存
    // 适合：记录失败日志、发送告警
    log.error("订单创建失败，已回滚：{}", event.getOrder().getId());
    alertService.sendAlert("订单创建失败");
}
```

**应用场景：**
- 记录失败日志
- 发送告警通知
- 回滚补偿操作

---

#### 4. AFTER_COMPLETION

**执行时机：** 事务完成后执行（无论提交还是回滚）。

```java
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMPLETION)
public void handleAfterCompletion(OrderCreatedEvent event) {
    // 无论成功或失败都会执行
    // 适合：清理资源、记录监控指标
    metricsService.record("order.create.completed");
}
```

**应用场景：**
- 清理临时资源
- 记录监控指标
- finally块的逻辑

---

### 四、完整实战案例

#### 场景：用户注册后发送欢迎邮件

```java
// 1. 定义事件
public class UserRegisteredEvent {
    private final User user;

    public UserRegisteredEvent(User user) {
        this.user = user;
    }

    public User getUser() {
        return user;
    }
}

// 2. 发布事件
@Service
public class UserService {

    @Autowired
    private ApplicationEventPublisher eventPublisher;

    @Transactional(rollbackFor = Exception.class)
    public void register(User user) {
        // 保存用户
        userMapper.insert(user);

        // 赠送积分
        pointMapper.insert(new Point(user.getId(), 100));

        // 发布事件
        eventPublisher.publishEvent(new UserRegisteredEvent(user));

        // ⚠️ 此时监听器还未执行，等待事务提交
    }
}

// 3. 监听事件
@Component
public class UserEventListener {

    @Autowired
    private EmailService emailService;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleUserRegistered(UserRegisteredEvent event) {
        User user = event.getUser();

        // ✅ 事务已提交，用户数据已持久化
        // 发送欢迎邮件
        emailService.sendWelcomeEmail(user.getEmail());

        // 如果发送失败，不影响注册流程（已解耦）
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_ROLLBACK)
    public void handleUserRegisterFailed(UserRegisteredEvent event) {
        // ❌ 注册失败，记录日志
        log.error("用户注册失败：{}", event.getUser().getUsername());
    }
}
```

**执行流程：**
```
register() 开始
  ↓
insert user（在事务中）
  ↓
insert point（在事务中）
  ↓
publishEvent（事件发布，但监听器还未执行）
  ↓
register() 结束
  ↓
事务提交
  ↓
handleUserRegistered() 执行（AFTER_COMMIT）
  ↓
发送邮件
```

---

### 五、对比传统方式

#### ❌ 传统方式（有问题）

```java
@Transactional
public void createOrder(Order order) {
    orderMapper.insert(order);

    // ❌ 事务还未提交，如果发邮件失败会导致订单回滚
    emailService.sendEmail(order);

    // ❌ 如果这里抛异常，订单和邮件都会失败
}
```

**问题：**
- 邮件发送失败会导致订单回滚（耦合）
- 事务时间过长（包含发邮件的时间）
- 无法保证邮件一定在订单保存后发送

---

#### ✅ 使用事务事件

```java
@Transactional
public void createOrder(Order order) {
    orderMapper.insert(order);

    // 发布事件（立即返回）
    eventPublisher.publishEvent(new OrderCreatedEvent(order));

    // 事务正常提交
}

@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void handleOrderCreated(OrderCreatedEvent event) {
    // ✅ 订单已保存，发邮件失败不影响订单
    emailService.sendEmail(event.getOrder());
}
```

**优势：**
- 业务解耦（订单创建和邮件发送分离）
- 事务时间短（不包含邮件时间）
- 可靠性高（只有订单保存成功才发邮件）

---

### 六、高级用法

#### 1. 条件执行

```java
@TransactionalEventListener(
    phase = TransactionPhase.AFTER_COMMIT,
    condition = "#event.order.amount > 1000"  // SpEL表达式
)
public void handleBigOrder(OrderCreatedEvent event) {
    // 只处理金额大于1000的订单
}
```

#### 2. 异步执行

```java
@Async
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void handleOrderCreatedAsync(OrderCreatedEvent event) {
    // 异步执行，不阻塞主流程
    emailService.sendEmail(event.getOrder());
}
```

#### 3. 多个监听器

```java
// 监听器1：发送邮件
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void sendEmail(OrderCreatedEvent event) {
    emailService.sendEmail(event.getOrder());
}

// 监听器2：清除缓存
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void clearCache(OrderCreatedEvent event) {
    cacheService.clear("order:" + event.getOrder().getId());
}

// 监听器3：发送MQ消息
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void sendMQ(OrderCreatedEvent event) {
    rabbitTemplate.convertAndSend("order.exchange", event.getOrder());
}
```

---

### 七、注意事项

| 项目 | 说明 |
|-----|------|
| **默认阶段** | AFTER_COMMIT（最常用） |
| **事务传播** | 监听器方法默认没有事务，如需事务需单独加@Transactional |
| **异常处理** | AFTER_COMMIT阶段的异常不影响原事务（已提交） |
| **执行顺序** | 多个监听器的执行顺序不确定，可用@Order指定 |
| **同步/异步** | 默认同步，可配合@Async异步执行 |

---

### 八、答题总结

**简洁回答：**

Spring事务事件通过 `@TransactionalEventListener` 实现，允许在事务的不同阶段触发监听器。

**使用步骤：**
1. 定义事件类（POJO）
2. 在事务方法中使用 `ApplicationEventPublisher.publishEvent()` 发布事件
3. 使用 `@TransactionalEventListener` 监听事件

**4种执行阶段：**
- **AFTER_COMMIT（默认）**：事务提交后执行，最常用
- **BEFORE_COMMIT**：事务提交前执行
- **AFTER_ROLLBACK**：事务回滚后执行
- **AFTER_COMPLETION**：事务完成后执行（无论成功失败）

**典型应用场景：**
- 事务提交后发送邮件、短信通知
- 事务提交后清除缓存、发送MQ消息
- 事务回滚后记录日志、发送告警

**优势：** 业务解耦、事务时间短、可靠性高（只有事务成功才执行）。
