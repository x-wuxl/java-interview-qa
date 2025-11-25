---
layout: default
title: "Spring事务管理全面解析"
parent: Spring框架
nav_order: 463
description: "全面解析Spring事务管理机制，包括ACID特性、隔离级别、传播行为、实现原理等核心概念"
author: "wuxl"
date: 2025-11-02
---
## 问题

请全面介绍Spring事务管理。

## 答案

### 一、事务的ACID特性

#### 1. 原子性（Atomicity）

事务是不可分割的最小工作单元，要么全部成功，要么全部失败。

```java
@Transactional
public void transferMoney(Long fromId, Long toId, BigDecimal amount) {
    accountMapper.deduct(fromId, amount);  // 操作1
    accountMapper.add(toId, amount);       // 操作2
    // 要么两个操作都成功，要么都回滚
}
```

#### 2. 一致性（Consistency）

事务执行前后，数据保持一致性状态。

```java
// 转账前：账户A = 1000，账户B = 500，总和 = 1500
transferMoney(A, B, 100);
// 转账后：账户A = 900，账户B = 600，总和 = 1500（保持一致）
```

#### 3. 隔离性（Isolation）

多个事务并发执行时，彼此隔离，互不干扰。

```java
// 事务1
@Transactional(isolation = Isolation.READ_COMMITTED)
public void updateUser(User user) {
    userMapper.update(user);
}

// 事务2不会读取到事务1未提交的数据
```

#### 4. 持久性（Durability）

事务一旦提交，对数据的修改是永久性的。

```java
@Transactional
public void createOrder(Order order) {
    orderMapper.insert(order);
    // 提交后，即使系统崩溃，订单数据也已持久化
}
```

---

### 二、事务隔离级别

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 说明 |
|---------|------|-----------|------|------|
| **READ_UNCOMMITTED** | ✓ | ✓ | ✓ | 读未提交（几乎不用） |
| **READ_COMMITTED** | × | ✓ | ✓ | 读已提交（Oracle默认） |
| **REPEATABLE_READ** | × | × | ✓ | 可重复读（MySQL默认） |
| **SERIALIZABLE** | × | × | × | 串行化（性能最差） |

#### 1. READ_UNCOMMITTED（读未提交）

```java
@Transactional(isolation = Isolation.READ_UNCOMMITTED)
public void readUser(Long id) {
    // ❌ 可能读到其他事务未提交的数据（脏读）
    User user = userMapper.selectById(id);
}
```

#### 2. READ_COMMITTED（读已提交）

```java
@Transactional(isolation = Isolation.READ_COMMITTED)
public void processOrder(Long orderId) {
    Order order1 = orderMapper.selectById(orderId);
    // ... 其他操作
    Order order2 = orderMapper.selectById(orderId);
    // order1和order2可能不同（不可重复读）
}
```

#### 3. REPEATABLE_READ（可重复读）

```java
@Transactional(isolation = Isolation.REPEATABLE_READ)
public void processOrder(Long orderId) {
    Order order1 = orderMapper.selectById(orderId);
    // ... 其他操作
    Order order2 = orderMapper.selectById(orderId);
    // order1和order2相同（可重复读）
}
```

#### 4. SERIALIZABLE（串行化）

```java
@Transactional(isolation = Isolation.SERIALIZABLE)
public void criticalOperation() {
    // 完全隔离，但性能最差
}
```

**MySQL InnoDB默认：** `REPEATABLE_READ`，且通过MVCC + Next-Key Lock解决了幻读问题。

---

### 三、事务传播行为

| 传播行为 | 说明 | 使用场景 |
|---------|------|---------|
| **REQUIRED** | 有事务就用，没有就创建（默认） | 最常用 |
| **REQUIRES_NEW** | 总是创建新事务，挂起外部事务 | 日志记录、审计 |
| **NESTED** | 嵌套事务（基于SavePoint） | 部分回滚 |
| **SUPPORTS** | 有事务就用，没有则非事务执行 | 查询操作 |
| **NOT_SUPPORTED** | 非事务执行，挂起外部事务 | 第三方调用 |
| **MANDATORY** | 必须有事务，否则抛异常 | 强制要求事务 |
| **NEVER** | 必须非事务，否则抛异常 | 禁止事务 |

**详细说明：** 参见《Spring的事务传播机制有哪些？》

---

### 四、事务管理方式

#### 1. 声明式事务（推荐）

**基于注解：**

```java
@Configuration
@EnableTransactionManagement
public class AppConfig {

    @Bean
    public PlatformTransactionManager transactionManager(DataSource dataSource) {
        return new DataSourceTransactionManager(dataSource);
    }
}

@Service
public class UserService {

    @Transactional(
        propagation = Propagation.REQUIRED,
        isolation = Isolation.DEFAULT,
        timeout = 30,
        readOnly = false,
        rollbackFor = Exception.class
    )
    public void createUser(User user) {
        userMapper.insert(user);
    }
}
```

**基于XML：**

```xml
<tx:advice id="txAdvice" transaction-manager="transactionManager">
    <tx:attributes>
        <tx:method name="create*" propagation="REQUIRED" rollback-for="Exception"/>
        <tx:method name="update*" propagation="REQUIRED" rollback-for="Exception"/>
        <tx:method name="delete*" propagation="REQUIRED" rollback-for="Exception"/>
        <tx:method name="get*" read-only="true"/>
    </tx:attributes>
</tx:advice>

<aop:config>
    <aop:advisor advice-ref="txAdvice" pointcut="execution(* com.example.service.*.*(..))"/>
</aop:config>
```

#### 2. 编程式事务

**使用TransactionTemplate：**

```java
@Service
public class OrderService {

    @Autowired
    private TransactionTemplate transactionTemplate;

    public void processOrder(Order order) {
        transactionTemplate.execute(status -> {
            try {
                orderMapper.insert(order);
                inventoryMapper.deduct(order.getProductId());
                return true;
            } catch (Exception e) {
                status.setRollbackOnly();
                throw e;
            }
        });
    }
}
```

**使用PlatformTransactionManager：**

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
            accountMapper.deduct(payment.getAmount());
            transactionManager.commit(status);
        } catch (Exception e) {
            transactionManager.rollback(status);
            throw e;
        }
    }
}
```

---

### 五、@Transactional注解属性

```java
@Transactional(
    // 传播行为
    propagation = Propagation.REQUIRED,

    // 隔离级别
    isolation = Isolation.DEFAULT,

    // 超时时间（秒）
    timeout = 30,

    // 是否只读
    readOnly = false,

    // 回滚的异常类型
    rollbackFor = {Exception.class, RuntimeException.class},

    // 不回滚的异常类型
    noRollbackFor = {BusinessException.class},

    // 事务管理器名称（多数据源场景）
    transactionManager = "primaryTransactionManager"
)
```

---

### 六、事务实现原理

#### 1. 基于AOP动态代理

```java
// Spring事务代理流程
调用@Transactional方法
  ↓
进入代理对象（TransactionInterceptor）
  ↓
开启事务（getTransaction）
  ↓
执行目标方法
  ↓
提交事务（commit）或回滚（rollback）
  ↓
返回结果
```

#### 2. 核心组件

```java
// 事务管理器
public interface PlatformTransactionManager {
    TransactionStatus getTransaction(TransactionDefinition definition);
    void commit(TransactionStatus status);
    void rollback(TransactionStatus status);
}

// 数据源事务管理器
public class DataSourceTransactionManager extends AbstractPlatformTransactionManager {
    protected void doBegin(Object transaction, TransactionDefinition definition) {
        // 获取数据库连接
        Connection con = dataSource.getConnection();
        // 设置自动提交为false
        con.setAutoCommit(false);
        // 绑定到ThreadLocal
        TransactionSynchronizationManager.bindResource(dataSource, new ConnectionHolder(con));
    }
}
```

#### 3. ThreadLocal实现线程隔离

```java
public abstract class TransactionSynchronizationManager {
    // 数据库连接存储在ThreadLocal中
    private static final ThreadLocal<Map<Object, Object>> resources =
        new NamedThreadLocal<>("Transactional resources");

    // 绑定连接到当前线程
    public static void bindResource(Object key, Object value) {
        Map<Object, Object> map = resources.get();
        map.put(key, value);
    }
}
```

---

### 七、常见问题与解决方案

#### 1. 事务失效

**常见原因：**
- 方法不是public
- 自调用（this调用）
- 异常类型不匹配
- 异常被捕获未抛出

**详细说明：** 参见《Spring事务失效可能是哪些原因？》

#### 2. 多线程事务失效

**原因：** ThreadLocal线程隔离

**详细说明：** 参见《Spring的事务在多线程下生效吗？为什么？》

#### 3. @Async与@Transactional冲突

**原因：** 异步执行，新线程无事务上下文

**详细说明：** 参见《同时使用@Transactional与@Async时，事务会不会生效？》

---

### 八、最佳实践

#### 1. 事务粒度要小

```java
// ❌ 不推荐：事务太大
@Transactional
public void processOrder(Order order) {
    orderMapper.insert(order);
    emailService.sendEmail(order);  // 耗时操作
    smsService.sendSMS(order);      // 耗时操作
}

// ✅ 推荐：事务粒度小
@Transactional
public void createOrder(Order order) {
    orderMapper.insert(order);
    // 发布事件，异步处理
    eventPublisher.publishEvent(new OrderCreatedEvent(order));
}
```

#### 2. 只读事务优化查询

```java
@Transactional(readOnly = true)
public List<User> listUsers() {
    // 只读事务，优化性能
    return userMapper.selectList(null);
}
```

#### 3. 指定回滚异常

```java
// ✅ 推荐：明确指定回滚异常
@Transactional(rollbackFor = Exception.class)
public void updateUser(User user) throws Exception {
    userMapper.update(user);
}
```

#### 4. 合理使用传播行为

```java
@Transactional
public void placeOrder(Order order) {
    // 主业务
    orderMapper.insert(order);

    // 日志独立事务（不影响主业务）
    logService.saveLog(order.getId());
}

@Transactional(propagation = Propagation.REQUIRES_NEW)
public void saveLog(Long orderId) {
    // 独立事务，即使外部事务回滚，日志也会保存
    logMapper.insert(new Log(orderId));
}
```

---

### 九、答题总结

**简洁回答：**

Spring事务管理提供了声明式和编程式两种方式，以声明式事务（`@Transactional`）为主。

**核心特性：**
1. **ACID特性**：原子性、一致性、隔离性、持久性
2. **4种隔离级别**：读未提交、读已提交、可重复读、串行化
3. **7种传播行为**：REQUIRED、REQUIRES_NEW、NESTED等

**实现原理：**
- 基于AOP动态代理（JDK动态代理或CGLIB）
- 使用ThreadLocal存储事务上下文（数据库连接）
- 通过PlatformTransactionManager统一管理事务

**最佳实践：**
- 事务粒度要小，避免长事务
- 明确指定 `rollbackFor = Exception.class`
- 只读查询使用 `readOnly = true`
- 合理使用传播行为（如REQUIRES_NEW做日志记录）

**常见问题：**
- 事务失效（方法非public、自调用、异常类型不匹配）
- 多线程事务失效（ThreadLocal线程隔离）
- 与@Async冲突（异步执行，无事务上下文）
