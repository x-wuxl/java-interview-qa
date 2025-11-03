---
layout: post
title: "Spring事务实现原理及@Transactional注解原理"
date: 2025-11-02
description: "深入解析Spring事务的底层实现机制，包括AOP代理、TransactionInterceptor、事务管理器等核心源码"
author: "wuxl"
categories: [Spring框架]
tags: [Spring, "@Transactional", AOP, 源码分析, 事务原理, TransactionInterceptor]
---

## 问题

Spring事务实现原理及@Transactional注解原理是什么？

## 答案

### 一、核心原理概述

Spring事务基于 **AOP（面向切面编程）** 实现，通过动态代理在目标方法执行前后织入事务管理逻辑。

**核心流程：**
```
调用@Transactional方法
  ↓
进入代理对象（TransactionInterceptor）
  ↓
开启事务（获取连接、设置autoCommit=false）
  ↓
执行目标方法
  ↓
成功：提交事务（commit）
  ↓
失败：回滚事务（rollback）
  ↓
返回结果
```

---

### 二、核心组件

#### 1. @EnableTransactionManagement

**作用：** 开启事务管理，导入核心配置。

```java
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Import(TransactionManagementConfigurationSelector.class)
public @interface EnableTransactionManagement {
    boolean proxyTargetClass() default false;  // 是否使用CGLIB
    AdviceMode mode() default AdviceMode.PROXY; // 代理模式
    int order() default Ordered.LOWEST_PRECEDENCE;
}
```

**核心源码：**

```java
public class TransactionManagementConfigurationSelector extends AdviceModeImportSelector<EnableTransactionManagement> {
    @Override
    protected String[] selectImports(AdviceMode adviceMode) {
        if (adviceMode == AdviceMode.PROXY) {
            // 导入核心配置类
            return new String[] {
                AutoProxyRegistrar.class.getName(),
                ProxyTransactionManagementConfiguration.class.getName()
            };
        }
    }
}
```

**导入的关键类：**
- `AutoProxyRegistrar`：注册自动代理创建器
- `ProxyTransactionManagementConfiguration`：配置事务拦截器

---

#### 2. TransactionInterceptor（事务拦截器）

**核心源码：**

```java
public class TransactionInterceptor extends TransactionAspectSupport implements MethodInterceptor {

    @Override
    public Object invoke(MethodInvocation invocation) throws Throwable {
        // 获取目标类
        Class<?> targetClass = invocation.getThis().getClass();

        // 执行事务方法
        return invokeWithinTransaction(
            invocation.getMethod(),
            targetClass,
            invocation::proceed  // 目标方法
        );
    }
}
```

#### 3. TransactionAspectSupport（事务切面支持）

**核心方法：** `invokeWithinTransaction`

```java
protected Object invokeWithinTransaction(Method method, Class<?> targetClass, InvocationCallback invocation) {

    // 1. 获取事务属性
    TransactionAttributeSource tas = getTransactionAttributeSource();
    TransactionAttribute txAttr = tas.getTransactionAttribute(method, targetClass);

    // 2. 获取事务管理器
    PlatformTransactionManager tm = determineTransactionManager(txAttr);

    // 3. 构造连接点标识
    String joinpointIdentification = methodIdentification(method, targetClass);

    if (txAttr == null || !(tm instanceof CallbackPreferringPlatformTransactionManager)) {
        // 4. 开启事务
        TransactionInfo txInfo = createTransactionIfNecessary(tm, txAttr, joinpointIdentification);

        Object retVal;
        try {
            // 5. 执行目标方法
            retVal = invocation.proceedWithInvocation();
        } catch (Throwable ex) {
            // 6. 异常回滚
            completeTransactionAfterThrowing(txInfo, ex);
            throw ex;
        } finally {
            // 7. 清理事务信息
            cleanupTransactionInfo(txInfo);
        }

        // 8. 提交事务
        commitTransactionAfterReturning(txInfo);
        return retVal;
    }
}
```

---

### 三、事务执行流程详解

#### 步骤1：开启事务

```java
protected TransactionInfo createTransactionIfNecessary(
    PlatformTransactionManager tm,
    TransactionAttribute txAttr,
    String joinpointIdentification) {

    // 获取事务状态
    TransactionStatus status = tm.getTransaction(txAttr);

    // 准备事务信息
    return prepareTransactionInfo(tm, txAttr, joinpointIdentification, status);
}
```

**PlatformTransactionManager.getTransaction()：**

```java
public final TransactionStatus getTransaction(TransactionDefinition definition) {
    // 获取事务对象（包含数据库连接）
    Object transaction = doGetTransaction();

    // 检查是否存在事务
    if (isExistingTransaction(transaction)) {
        // 处理事务传播行为
        return handleExistingTransaction(definition, transaction);
    }

    // 创建新事务
    return startTransaction(definition, transaction);
}
```

**DataSourceTransactionManager.doBegin()：**

```java
protected void doBegin(Object transaction, TransactionDefinition definition) {
    DataSourceTransactionObject txObject = (DataSourceTransactionObject) transaction;

    // 1. 获取数据库连接
    Connection con = obtainDataSource().getConnection();

    // 2. 设置事务隔离级别
    if (definition.getIsolationLevel() != TransactionDefinition.ISOLATION_DEFAULT) {
        con.setTransactionIsolation(definition.getIsolationLevel());
    }

    // 3. 关闭自动提交（开启事务）
    con.setAutoCommit(false);

    // 4. 设置超时时间
    if (definition.getTimeout() != TransactionDefinition.TIMEOUT_DEFAULT) {
        txObject.getConnectionHolder().setTimeoutInSeconds(definition.getTimeout());
    }

    // 5. 绑定连接到ThreadLocal
    TransactionSynchronizationManager.bindResource(obtainDataSource(), txObject.getConnectionHolder());
}
```

**关键：** 将数据库连接绑定到ThreadLocal，保证同一线程使用同一连接。

---

#### 步骤2：执行目标方法

```java
// 通过反射调用目标方法
retVal = invocation.proceedWithInvocation();
```

---

#### 步骤3：提交事务

```java
protected void commitTransactionAfterReturning(TransactionInfo txInfo) {
    if (txInfo != null && txInfo.getTransactionStatus() != null) {
        // 提交事务
        txInfo.getTransactionManager().commit(txInfo.getTransactionStatus());
    }
}
```

**DataSourceTransactionManager.doCommit()：**

```java
protected void doCommit(DefaultTransactionStatus status) {
    DataSourceTransactionObject txObject = (DataSourceTransactionObject) status.getTransaction();
    Connection con = txObject.getConnectionHolder().getConnection();

    // 提交事务
    con.commit();
}
```

---

#### 步骤4：回滚事务

```java
protected void completeTransactionAfterThrowing(TransactionInfo txInfo, Throwable ex) {
    if (txInfo != null && txInfo.getTransactionStatus() != null) {
        // 判断是否需要回滚
        if (txInfo.transactionAttribute.rollbackOn(ex)) {
            // 回滚事务
            txInfo.getTransactionManager().rollback(txInfo.getTransactionStatus());
        } else {
            // 提交事务（不回滚的异常）
            txInfo.getTransactionManager().commit(txInfo.getTransactionStatus());
        }
    }
}
```

**rollbackOn判断：**

```java
public boolean rollbackOn(Throwable ex) {
    // 默认：RuntimeException和Error回滚
    return (ex instanceof RuntimeException || ex instanceof Error);
}
```

**DataSourceTransactionManager.doRollback()：**

```java
protected void doRollback(DefaultTransactionStatus status) {
    DataSourceTransactionObject txObject = (DataSourceTransactionObject) status.getTransaction();
    Connection con = txObject.getConnectionHolder().getConnection();

    // 回滚事务
    con.rollback();
}
```

---

### 四、ThreadLocal实现线程隔离

```java
public abstract class TransactionSynchronizationManager {

    // 存储数据库连接（ThreadLocal）
    private static final ThreadLocal<Map<Object, Object>> resources =
        new NamedThreadLocal<>("Transactional resources");

    // 绑定连接到当前线程
    public static void bindResource(Object key, Object value) {
        Map<Object, Object> map = resources.get();
        if (map == null) {
            map = new HashMap<>();
            resources.set(map);
        }
        map.put(key, value);
    }

    // 获取当前线程的连接
    public static Object getResource(Object key) {
        Map<Object, Object> map = resources.get();
        return map != null ? map.get(key) : null;
    }
}
```

**关键：**
- 每个线程都有独立的数据库连接
- 同一线程内的所有操作共享同一连接（保证事务一致性）
- 不同线程之间完全隔离

---

### 五、动态代理实现

#### 1. JDK动态代理（接口代理）

```java
// 目标类实现了接口
public interface UserService {
    void createUser(User user);
}

@Service
public class UserServiceImpl implements UserService {

    @Transactional
    @Override
    public void createUser(User user) {
        userMapper.insert(user);
    }
}

// Spring创建JDK动态代理
UserService proxy = (UserService) Proxy.newProxyInstance(
    classLoader,
    new Class[]{UserService.class},
    new TransactionInvocationHandler(target)
);
```

#### 2. CGLIB代理（类代理）

```java
// 目标类没有实现接口
@Service
public class OrderService {

    @Transactional
    public void createOrder(Order order) {
        orderMapper.insert(order);
    }
}

// Spring创建CGLIB代理（继承目标类）
OrderService proxy = (OrderService) Enhancer.create(
    OrderService.class,
    new TransactionMethodInterceptor(target)
);
```

**代理选择规则：**
- 如果目标类实现了接口，默认使用 **JDK动态代理**
- 如果目标类没有实现接口，使用 **CGLIB代理**
- 可通过 `@EnableTransactionManagement(proxyTargetClass = true)` 强制使用CGLIB

---

### 六、完整流程图

```
@EnableTransactionManagement
  ↓
导入ProxyTransactionManagementConfiguration
  ↓
注册TransactionInterceptor（事务拦截器）
  ↓
注册BeanFactoryTransactionAttributeSourceAdvisor（切面）
  ↓
Spring容器启动时，扫描@Transactional注解
  ↓
为带有@Transactional的Bean创建代理对象
  ↓
调用方法时，进入代理对象
  ↓
TransactionInterceptor.invoke()
  ↓
TransactionAspectSupport.invokeWithinTransaction()
  ↓
1. 开启事务（getTransaction）
2. 执行目标方法（proceed）
3. 提交事务（commit）或回滚（rollback）
  ↓
返回结果
```

---

### 七、关键源码总结

| 组件 | 作用 |
|------|------|
| `@EnableTransactionManagement` | 开启事务管理，导入配置类 |
| `TransactionInterceptor` | 事务拦截器，实现MethodInterceptor |
| `TransactionAspectSupport` | 事务切面支持，核心方法invokeWithinTransaction |
| `PlatformTransactionManager` | 事务管理器接口（getTransaction、commit、rollback） |
| `DataSourceTransactionManager` | 数据源事务管理器实现 |
| `TransactionSynchronizationManager` | 事务同步管理器，使用ThreadLocal存储连接 |

---

### 八、答题总结

**简洁回答：**

Spring事务基于 **AOP动态代理** 实现，核心原理如下：

**1. 启动阶段：**
- `@EnableTransactionManagement` 导入配置类
- 注册 `TransactionInterceptor`（事务拦截器）
- 为带有 `@Transactional` 的Bean创建代理对象（JDK动态代理或CGLIB）

**2. 执行阶段：**
```java
代理对象.方法()
  ↓
TransactionInterceptor.invoke()
  ↓
开启事务：
  - 获取数据库连接
  - 设置autoCommit=false
  - 绑定到ThreadLocal
  ↓
执行目标方法
  ↓
成功：commit提交事务
失败：rollback回滚事务
```

**3. 关键技术：**
- **AOP代理**：JDK动态代理（接口）或CGLIB（类）
- **ThreadLocal**：存储数据库连接，实现线程隔离
- **事务管理器**：`PlatformTransactionManager` 统一管理事务

**4. 核心类：**
- `TransactionInterceptor`：事务拦截器
- `TransactionAspectSupport`：事务切面支持（核心逻辑）
- `DataSourceTransactionManager`：数据源事务管理器
- `TransactionSynchronizationManager`：事务同步管理器（ThreadLocal）

**面试加分点：** 能说出ThreadLocal的作用（线程隔离）、代理选择规则（接口用JDK，类用CGLIB）、以及invokeWithinTransaction方法的核心流程。
