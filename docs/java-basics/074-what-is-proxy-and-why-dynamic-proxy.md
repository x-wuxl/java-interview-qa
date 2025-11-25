---
layout: default
title: "什么是代理？为什么要使用动态代理？"
parent: Java基础
nav_order: 74
description: "全面解析代理模式的概念、静态代理与动态代理的区别、动态代理的优势及在Spring AOP、RPC等框架中的实际应用"
author: "wuxl"
date: 2025-11-17
---
## 问题

什么是代理？为什么要使用动态代理？

## 答案

### 一、什么是代理？

#### 核心概念

**代理模式（Proxy Pattern）**：为其他对象提供一种代理以控制对这个对象的访问。代理对象在客户端和目标对象之间起到中介作用。

#### 生活中的例子

```
客户 ──→ 房产中介（代理） ──→ 房东（目标对象）
       ↑
       增强功能：
       - 筛选客户
       - 带看房子
       - 签订合同
       - 收取佣金
```

#### 代理模式的三个角色

```java
// 1. 抽象主题（Subject）：定义代理和真实对象的共同接口
interface Subject {
    void request();
}

// 2. 真实主题（RealSubject）：实际的业务对象
class RealSubject implements Subject {
    @Override
    public void request() {
        System.out.println("执行真实业务逻辑");
    }
}

// 3. 代理（Proxy）：持有真实对象的引用，控制对真实对象的访问
class ProxySubject implements Subject {
    private RealSubject realSubject;

    public ProxySubject(RealSubject realSubject) {
        this.realSubject = realSubject;
    }

    @Override
    public void request() {
        before();  // 前置增强
        realSubject.request();  // 调用真实对象
        after();   // 后置增强
    }

    private void before() {
        System.out.println("代理：前置处理");
    }

    private void after() {
        System.out.println("代理：后置处理");
    }
}
```

### 二、代理的主要作用

#### 1. 功能增强

在不修改原有代码的情况下，增加额外功能：

```java
// 原始功能
public void transfer(String from, String to, double amount) {
    // 转账逻辑
}

// 代理增强：添加日志、权限检查、事务管理
public void transfer(String from, String to, double amount) {
    log("开始转账");           // 日志
    checkPermission();        // 权限检查
    beginTransaction();       // 开启事务
    try {
        realObject.transfer(from, to, amount);  // 原始功能
        commit();             // 提交事务
    } catch (Exception e) {
        rollback();           // 回滚事务
    }
    log("转账完成");
}
```

#### 2. 控制访问

```java
// 延迟加载（虚拟代理）
class ImageProxy implements Image {
    private RealImage realImage;
    private String filename;

    public ImageProxy(String filename) {
        this.filename = filename;
    }

    @Override
    public void display() {
        if (realImage == null) {
            realImage = new RealImage(filename);  // 延迟创建
        }
        realImage.display();
    }
}

// 权限控制（保护代理）
class ProtectedProxy implements Service {
    private RealService realService;
    private User currentUser;

    @Override
    public void execute() {
        if (currentUser.hasPermission()) {
            realService.execute();
        } else {
            throw new SecurityException("无权限访问");
        }
    }
}
```

#### 3. 远程代理

```java
// RPC 远程调用
interface UserService {
    User getUser(int id);
}

// 客户端代理
class UserServiceProxy implements UserService {
    @Override
    public User getUser(int id) {
        // 1. 序列化请求
        Request request = new Request("getUser", id);
        // 2. 网络传输
        Response response = httpClient.send(request);
        // 3. 反序列化响应
        return (User) response.getData();
    }
}

// 使用（像调用本地方法一样）
UserService userService = new UserServiceProxy();
User user = userService.getUser(123);
```

### 三、静态代理 vs 动态代理

#### 静态代理

**定义**：在编译期就确定代理类，需要手动编写代理类代码。

**示例**：

```java
// 接口
interface UserService {
    void addUser(String name);
    void deleteUser(int id);
}

// 真实对象
class UserServiceImpl implements UserService {
    @Override
    public void addUser(String name) {
        System.out.println("添加用户: " + name);
    }

    @Override
    public void deleteUser(int id) {
        System.out.println("删除用户: " + id);
    }
}

// 静态代理类（手动编写）
class UserServiceProxy implements UserService {
    private UserService target;

    public UserServiceProxy(UserService target) {
        this.target = target;
    }

    @Override
    public void addUser(String name) {
        System.out.println("[日志] 调用 addUser");
        target.addUser(name);
        System.out.println("[日志] addUser 完成");
    }

    @Override
    public void deleteUser(int id) {
        System.out.println("[日志] 调用 deleteUser");
        target.deleteUser(id);
        System.out.println("[日志] deleteUser 完成");
    }
}
```

**静态代理的问题**：

1. **代码冗余**：每个方法都要写重复的增强逻辑
2. **维护困难**：接口新增方法，代理类也要修改
3. **扩展性差**：每个接口都需要单独的代理类

```java
// 如果有 100 个接口，需要写 100 个代理类
class OrderServiceProxy { }
class ProductServiceProxy { }
class PaymentServiceProxy { }
// ...
```

#### 动态代理

**定义**：在运行时动态生成代理类，无需手动编写代理类代码。

**JDK 动态代理示例**：

```java
// 通用的日志处理器
class LogHandler implements InvocationHandler {
    private Object target;

    public LogHandler(Object target) {
        this.target = target;
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        System.out.println("[日志] 调用 " + method.getName());
        Object result = method.invoke(target, args);
        System.out.println("[日志] " + method.getName() + " 完成");
        return result;
    }
}

// 使用（一个 Handler 处理所有接口）
UserService userService = new UserServiceImpl();
UserService proxy = (UserService) Proxy.newProxyInstance(
    userService.getClass().getClassLoader(),
    userService.getClass().getInterfaces(),
    new LogHandler(userService)
);

OrderService orderService = new OrderServiceImpl();
OrderService orderProxy = (OrderService) Proxy.newProxyInstance(
    orderService.getClass().getClassLoader(),
    orderService.getClass().getInterfaces(),
    new LogHandler(orderService)  // 复用同一个 Handler
);
```

### 四、为什么要使用动态代理？

#### 1. 减少代码冗余

**静态代理**：

```java
// 需要为每个接口写代理类
class UserServiceProxy { }      // 100 行
class OrderServiceProxy { }     // 100 行
class ProductServiceProxy { }   // 100 行
// 总计：300 行重复代码
```

**动态代理**：

```java
// 一个 InvocationHandler 处理所有接口
class LogHandler implements InvocationHandler {
    // 20 行代码，适用于所有接口
}
```

#### 2. 提高可维护性

**静态代理**：

```java
// 接口新增方法
interface UserService {
    void addUser(String name);
    void deleteUser(int id);
    void updateUser(User user);  // 新增方法
}

// 代理类必须同步修改
class UserServiceProxy implements UserService {
    // 必须实现新方法
    @Override
    public void updateUser(User user) {
        // 重复的增强逻辑
    }
}
```

**动态代理**：

```java
// 接口新增方法，无需修改代理代码
class LogHandler implements InvocationHandler {
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) {
        // 自动处理所有方法（包括新增的）
        System.out.println("[日志] 调用 " + method.getName());
        return method.invoke(target, args);
    }
}
```

#### 3. 灵活的功能组合

```java
// 可以动态组合多个增强功能
Object proxy = target;

// 添加日志
proxy = Proxy.newProxyInstance(..., new LogHandler(proxy));

// 添加性能监控
proxy = Proxy.newProxyInstance(..., new PerformanceHandler(proxy));

// 添加事务管理
proxy = Proxy.newProxyInstance(..., new TransactionHandler(proxy));

// 最终代理对象具备：日志 + 性能监控 + 事务管理
```

#### 4. 支持 AOP 编程

```java
// Spring AOP 使用动态代理实现切面编程
@Aspect
@Component
public class LogAspect {
    @Around("execution(* com.example.service.*.*(..))")
    public Object log(ProceedingJoinPoint joinPoint) throws Throwable {
        System.out.println("方法执行前");
        Object result = joinPoint.proceed();
        System.out.println("方法执行后");
        return result;
    }
}

// 底层使用动态代理实现
// 无需手动编写代理类
```

### 五、动态代理的实际应用场景

#### 1. Spring AOP

```java
// 事务管理
@Transactional
public void transfer(String from, String to, double amount) {
    // Spring 使用动态代理自动添加事务管理
}

// 权限控制
@PreAuthorize("hasRole('ADMIN')")
public void deleteUser(int id) {
    // Spring Security 使用动态代理检查权限
}
```

#### 2. MyBatis Mapper 接口

```java
// 只定义接口，无需实现类
public interface UserMapper {
    @Select("SELECT * FROM user WHERE id = #{id}")
    User getUserById(int id);
}

// MyBatis 使用动态代理生成实现类
UserMapper mapper = sqlSession.getMapper(UserMapper.class);
User user = mapper.getUserById(123);
```

#### 3. RPC 框架（Dubbo、Feign）

```java
// Dubbo 服务调用
@Reference
private UserService userService;

// Feign 远程调用
@FeignClient("user-service")
public interface UserClient {
    @GetMapping("/users/{id}")
    User getUser(@PathVariable int id);
}

// 底层使用动态代理实现远程调用
```

#### 4. 日志、监控、缓存

```java
// 统一日志记录
class LogHandler implements InvocationHandler {
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) {
        logger.info("调用方法: {}, 参数: {}", method.getName(), args);
        Object result = method.invoke(target, args);
        logger.info("返回结果: {}", result);
        return result;
    }
}

// 性能监控
class PerformanceHandler implements InvocationHandler {
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) {
        long start = System.currentTimeMillis();
        Object result = method.invoke(target, args);
        long end = System.currentTimeMillis();
        System.out.println(method.getName() + " 耗时: " + (end - start) + "ms");
        return result;
    }
}

// 缓存
class CacheHandler implements InvocationHandler {
    private Map<String, Object> cache = new HashMap<>();

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) {
        String key = method.getName() + Arrays.toString(args);
        if (cache.containsKey(key)) {
            return cache.get(key);  // 返回缓存
        }
        Object result = method.invoke(target, args);
        cache.put(key, result);
        return result;
    }
}
```

### 六、静态代理 vs 动态代理对比

| 对比维度 | 静态代理 | 动态代理 |
|---------|---------|---------|
| **代码量** | 每个接口需要一个代理类 | 一个 Handler 处理所有接口 |
| **维护性** | 接口变化需要同步修改代理类 | 无需修改代理代码 |
| **灵活性** | 编译期确定，不灵活 | 运行时生成，灵活 |
| **性能** | 直接调用，性能好 | 反射调用，略有损耗 |
| **使用场景** | 简单场景，代理类少 | 复杂场景，需要通用增强 |
| **实际应用** | 装饰器模式 | Spring AOP、RPC 框架 |

### 七、面试答题要点

1. **代理定义**：为其他对象提供代理以控制访问，在客户端和目标对象之间起中介作用
2. **代理作用**：功能增强、控制访问、远程代理
3. **静态代理问题**：代码冗余、维护困难、扩展性差
4. **动态代理优势**：减少代码、提高维护性、灵活组合功能、支持 AOP
5. **实际应用**：Spring AOP、MyBatis Mapper、RPC 框架、日志监控
6. **实现方式**：JDK 动态代理（基于接口）、CGLIB（基于继承）
7. **选择建议**：简单场景用静态代理，复杂场景用动态代理
