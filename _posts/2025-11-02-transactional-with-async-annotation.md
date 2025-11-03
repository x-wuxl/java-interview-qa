---
layout: post
title: "同时使用@Transactional与@Async时，事务会不会生效？"
date: 2025-11-02
description: "深入分析@Transactional和@Async注解同时使用时的事务失效问题、原因及正确的处理方案"
author: "wuxl"
categories: [Spring框架]
tags: [Spring, "@Transactional", "@Async", 异步事务, 多线程]
---

## 问题

同时使用@Transactional与@Async时，事务会不会生效？

## 答案

### 一、结论

**事务不会生效**。

### 二、原因分析

#### 1. 核心原理

```java
@Service
public class UserService {

    // ❌ 事务不生效
    @Transactional
    @Async
    public void createUser(User user) {
        userMapper.insert(user);
        // 异步执行，在新线程中运行
        // 新线程无法获取主线程的事务上下文
    }
}
```

**失效原因：**
1. `@Async` 会将方法提交到线程池中异步执行
2. **新线程没有事务上下文**（Spring事务基于ThreadLocal）
3. 虽然 `@Transactional` 也生成了代理，但在新线程中无法获取数据库连接和事务信息

#### 2. 执行流程

```
调用createUser()
  ↓
@Async代理拦截，提交到线程池
  ↓
新线程执行方法
  ↓
@Transactional代理生效，但ThreadLocal中无事务上下文
  ↓
方法以自动提交模式执行（autocommit=true）
  ↓
事务失效
```

#### 3. 验证实验

```java
@Service
public class UserService {

    @Autowired
    private UserMapper userMapper;

    @Transactional
    @Async
    public void createUser(User user) {
        System.out.println("当前线程: " + Thread.currentThread().getName());
        System.out.println("是否有事务: " + TransactionSynchronizationManager.isActualTransactionActive());

        userMapper.insert(user);

        // 制造异常
        int i = 1 / 0;
    }
}

// 调用
userService.createUser(new User("张三"));
```

**输出：**
```
当前线程: task-1  // 异步线程
是否有事务: false  // ❌ 无事务
```

**结果：** 尽管抛出异常，数据仍然插入成功（未回滚）。

---

### 三、注解顺序的影响

#### 情况1：@Transactional + @Async

```java
@Transactional
@Async
public void method() {
    // ❌ 事务不生效
}
```

**代理链：** `@Async代理 → @Transactional代理 → 目标方法`

**执行：** 先进入Async代理，提交到新线程；新线程中Transactional代理无法获取事务上下文。

#### 情况2：@Async + @Transactional

```java
@Async
@Transactional
public void method() {
    // ❌ 事务不生效
}
```

**代理链：** `@Transactional代理 → @Async代理 → 目标方法`

**执行：** 先进入Transactional代理，但随后Async代理将方法提交到新线程，事务上下文丢失。

**结论：** 无论顺序如何，**事务都不生效**。

---

### 四、正确的解决方案

#### 方案1：分离事务和异步（推荐）

```java
@Service
public class UserService {

    @Autowired
    private UserService self;

    // 异步方法（不带事务）
    @Async
    public void createUserAsync(User user) {
        // 调用事务方法
        self.createUserInTransaction(user);
    }

    // 事务方法（不带异步）
    @Transactional(rollbackFor = Exception.class)
    public void createUserInTransaction(User user) {
        userMapper.insert(user);
    }
}

// 调用
userService.createUserAsync(user);
```

**关键：** 在异步方法内部调用事务方法，每个异步线程都有独立的事务。

#### 方案2：使用TransactionTemplate

```java
@Service
public class UserService {

    @Autowired
    private TransactionTemplate transactionTemplate;

    @Async
    public void createUserAsync(User user) {
        transactionTemplate.execute(status -> {
            try {
                userMapper.insert(user);
                return true;
            } catch (Exception e) {
                status.setRollbackOnly();
                throw e;
            }
        });
    }
}
```

#### 方案3：使用消息队列解耦

```java
@Service
public class UserService {

    @Autowired
    private RabbitTemplate rabbitTemplate;

    // 同步事务方法
    @Transactional
    public void createUser(User user) {
        userMapper.insert(user);
        // 发送消息
        rabbitTemplate.convertAndSend("user.exchange", "user.create", user);
    }
}

// 消费者（异步处理）
@RabbitListener(queues = "user.queue")
@Transactional
public void handleUserCreate(User user) {
    // 异步处理，独立事务
    emailService.sendWelcomeEmail(user);
}
```

#### 方案4：使用CompletableFuture

```java
@Service
public class UserService {

    @Autowired
    private UserService self;

    public void batchCreateUsers(List<User> users) {
        CompletableFuture[] futures = users.stream()
            .map(user -> CompletableFuture.runAsync(() ->
                self.createUserInTransaction(user)
            ))
            .toArray(CompletableFuture[]::new);

        // 等待所有任务完成
        CompletableFuture.allOf(futures).join();
    }

    @Transactional(rollbackFor = Exception.class)
    public void createUserInTransaction(User user) {
        userMapper.insert(user);
    }
}
```

---

### 五、实战案例对比

#### ❌ 错误写法

```java
@Transactional
@Async
public void processOrder(Order order) {
    orderMapper.insert(order);
    inventoryMapper.deduct(order.getProductId());
    // 如果抛异常，数据不会回滚（事务失效）
    throw new RuntimeException("处理失败");
}
```

#### ✅ 正确写法

```java
@Service
public class OrderService {

    @Autowired
    private OrderService self;

    @Async
    public void processOrderAsync(Order order) {
        // 异步执行
        self.processOrderInTransaction(order);
    }

    @Transactional(rollbackFor = Exception.class)
    public void processOrderInTransaction(Order order) {
        orderMapper.insert(order);
        inventoryMapper.deduct(order.getProductId());
        // 如果抛异常，数据会回滚（事务生效）
        throw new RuntimeException("处理失败");
    }
}
```

---

### 六、源码分析

#### @Async执行流程

```java
// AsyncExecutionInterceptor.java
@Override
public Object invoke(final MethodInvocation invocation) throws Throwable {
    // 获取线程池
    Executor executor = determineAsyncExecutor(method);

    // 提交到线程池异步执行
    Future<?> result = executor.submit(() -> {
        // 在新线程中执行目标方法
        return invocation.proceed();
    });

    return result;
}
```

**关键：** 方法在新线程中执行，ThreadLocal中无事务上下文。

---

### 七、答题总结

**简洁回答：**

**同时使用@Transactional和@Async，事务不会生效**，原因是：

1. **@Async将方法提交到新线程执行**
2. **Spring事务基于ThreadLocal**，新线程无法获取主线程的事务上下文
3. **方法以自动提交模式执行**（autocommit=true），无事务保护

**正确做法：**
- **分离异步和事务**：在异步方法内部调用事务方法
- 每个异步任务都有独立的事务
- 或使用消息队列解耦异步处理

**示例：**
```java
@Async
public void asyncMethod() {
    // 调用事务方法
    self.transactionalMethod();
}

@Transactional
public void transactionalMethod() {
    // 业务逻辑
}
```

**面试加分点：** 无论注解顺序如何，事务都不生效；本质原因是ThreadLocal的线程隔离特性。
