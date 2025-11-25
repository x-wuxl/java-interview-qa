---
layout: default
title: "策略模式与代理模式的区别"
parent: 设计模式
nav_order: 492
description: "深入对比策略模式和代理模式的定义、应用场景、实现方式，以及在实际项目中的常见设计模式应用"
author: "wuxl"
date: 2025-11-02
---
## 问题

用过哪些设计模式？策略模式和代理模式有什么区别？

## 答案

### 1. 常用设计模式概览

在实际开发中，最常用的设计模式包括：

**创建型模式**：
- **单例模式**：Spring Bean、数据库连接池
- **工厂模式**：BeanFactory、DAO工厂
- **建造者模式**：StringBuilder、Lombok的@Builder

**结构型模式**：
- **代理模式**：Spring AOP、MyBatis Mapper接口
- **装饰器模式**：Java IO流（BufferedReader包装FileReader）
- **适配器模式**：SpringMVC的HandlerAdapter

**行为型模式**：
- **策略模式**：支付方式选择、排序算法
- **模板方法模式**：JdbcTemplate、抽象类定义流程
- **观察者模式**：Spring事件机制、消息队列

---

### 2. 策略模式详解

#### 2.1 定义与核心思想

**定义**：定义一系列算法，将每个算法封装起来，并使它们可以相互替换。策略模式让算法的变化独立于使用算法的客户端。

**核心要素**：
- **策略接口**（Strategy）：定义算法族的公共接口
- **具体策略**（ConcreteStrategy）：实现不同的算法
- **上下文**（Context）：持有策略引用，根据需要调用策略

---

#### 2.2 实现示例

**场景：电商平台支付方式**

```java
// 1. 策略接口
public interface PaymentStrategy {
    void pay(BigDecimal amount);
}

// 2. 具体策略：支付宝
@Component("alipay")
public class AlipayStrategy implements PaymentStrategy {
    @Override
    public void pay(BigDecimal amount) {
        System.out.println("使用支付宝支付：" + amount);
        // 调用支付宝SDK
    }
}

// 3. 具体策略：微信支付
@Component("wechat")
public class WechatPayStrategy implements PaymentStrategy {
    @Override
    public void pay(BigDecimal amount) {
        System.out.println("使用微信支付：" + amount);
        // 调用微信支付SDK
    }
}

// 4. 具体策略：银行卡支付
@Component("bankcard")
public class BankCardStrategy implements PaymentStrategy {
    @Override
    public void pay(BigDecimal amount) {
        System.out.println("使用银行卡支付：" + amount);
        // 调用银行接口
    }
}

// 5. 上下文：订单服务
@Service
public class OrderService {
    @Autowired
    private Map<String, PaymentStrategy> strategies;  // Spring自动注入所有策略

    public void checkout(Order order, String paymentType) {
        // 根据支付类型动态选择策略
        PaymentStrategy strategy = strategies.get(paymentType);
        if (strategy == null) {
            throw new IllegalArgumentException("不支持的支付方式");
        }

        // 执行支付
        strategy.pay(order.getAmount());
    }
}
```

**使用示例**：
```java
@RestController
public class OrderController {
    @Autowired
    private OrderService orderService;

    @PostMapping("/checkout")
    public Result checkout(@RequestBody Order order,
                          @RequestParam String paymentType) {
        // paymentType: alipay / wechat / bankcard
        orderService.checkout(order, paymentType);
        return Result.success();
    }
}
```

---

#### 2.3 策略模式的优势

**消除条件语句**：

**改造前（硬编码）**：
```java
public void pay(String type, BigDecimal amount) {
    if ("alipay".equals(type)) {
        System.out.println("支付宝支付");
    } else if ("wechat".equals(type)) {
        System.out.println("微信支付");
    } else if ("bankcard".equals(type)) {
        System.out.println("银行卡支付");
    }
    // 新增支付方式需要修改此方法（违反开闭原则）
}
```

**改造后（策略模式）**：
```java
// 新增支付方式只需添加新策略类，无需修改现有代码
@Component("crypto")
public class CryptoPayStrategy implements PaymentStrategy {
    public void pay(BigDecimal amount) {
        System.out.println("数字货币支付");
    }
}
```

---

### 3. 代理模式详解

#### 3.1 定义与核心思想

**定义**：为目标对象提供一个代理，通过代理控制对目标对象的访问。

**核心要素**：
- **抽象主题**（Subject）：定义真实对象和代理对象的共同接口
- **真实主题**（RealSubject）：被代理的目标对象
- **代理**（Proxy）：持有真实对象引用，控制访问并增强功能

---

#### 3.2 实现示例

**场景：用户服务加权限控制**

**静态代理**：
```java
// 1. 抽象主题
public interface UserService {
    void deleteUser(Long userId);
}

// 2. 真实主题
public class UserServiceImpl implements UserService {
    @Override
    public void deleteUser(Long userId) {
        System.out.println("删除用户：" + userId);
        // 实际删除逻辑
    }
}

// 3. 代理类：增加权限控制
public class UserServiceProxy implements UserService {
    private UserService target;
    private String currentUser;

    public UserServiceProxy(UserService target, String currentUser) {
        this.target = target;
        this.currentUser = currentUser;
    }

    @Override
    public void deleteUser(Long userId) {
        // 前置增强：权限检查
        if (!"admin".equals(currentUser)) {
            throw new SecurityException("无权限删除用户");
        }

        // 调用真实对象
        target.deleteUser(userId);

        // 后置增强：记录日志
        System.out.println("管理员 " + currentUser + " 删除了用户 " + userId);
    }
}
```

**使用示例**：
```java
UserService realService = new UserServiceImpl();
UserService proxy = new UserServiceProxy(realService, "admin");
proxy.deleteUser(1001L);  // 通过代理访问
```

---

**动态代理（JDK）**：
```java
// JDK动态代理：基于接口
public class JdkProxyFactory {
    public static <T> T createProxy(T target) {
        return (T) Proxy.newProxyInstance(
            target.getClass().getClassLoader(),
            target.getClass().getInterfaces(),
            new InvocationHandler() {
                @Override
                public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
                    // 前置增强
                    System.out.println("Before: " + method.getName());

                    // 执行目标方法
                    Object result = method.invoke(target, args);

                    // 后置增强
                    System.out.println("After: " + method.getName());

                    return result;
                }
            }
        );
    }
}
```

**CGLIB动态代理**：
```java
// CGLIB动态代理：基于子类（目标类无接口时使用）
public class CglibProxyFactory {
    public static <T> T createProxy(Class<T> clazz) {
        Enhancer enhancer = new Enhancer();
        enhancer.setSuperclass(clazz);
        enhancer.setCallback(new MethodInterceptor() {
            @Override
            public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy)
                    throws Throwable {
                System.out.println("CGLIB Before: " + method.getName());
                Object result = proxy.invokeSuper(obj, args);
                System.out.println("CGLIB After: " + method.getName());
                return result;
            }
        });
        return (T) enhancer.create();
    }
}
```

---

#### 3.3 Spring AOP中的代理模式

```java
// Spring通过代理实现AOP
@Aspect
@Component
public class LogAspect {
    // 环绕通知：完全控制目标方法执行
    @Around("execution(* com.example.service.*.*(..))")
    public Object logAround(ProceedingJoinPoint joinPoint) throws Throwable {
        // 前置增强
        System.out.println("方法执行前：" + joinPoint.getSignature());
        long startTime = System.currentTimeMillis();

        // 调用目标方法（相当于代理调用真实对象）
        Object result = joinPoint.proceed();

        // 后置增强
        long endTime = System.currentTimeMillis();
        System.out.println("方法执行后，耗时：" + (endTime - startTime) + "ms");

        return result;
    }
}
```

---

### 4. 策略模式 vs 代理模式

| 维度 | 策略模式 | 代理模式 |
|------|---------|---------|
| **目的** | 封装**可替换的算法族**，让算法独立于客户端变化 | 控制对目标对象的访问，**增强或限制**其功能 |
| **关注点** | **算法的选择和切换** | **对象的访问控制和功能增强** |
| **结构** | 客户端**主动选择**策略 | 客户端通过代理**间接访问**目标对象 |
| **接口** | 策略接口定义算法规范 | 代理和真实对象实现同一接口 |
| **扩展性** | 新增策略无需修改上下文 | 新增功能需修改代理类（静态代理）或切面（动态代理） |
| **典型场景** | 支付方式、排序算法、折扣计算 | 权限控制、日志记录、事务管理、延迟加载 |
| **Spring中应用** | Resource加载策略、事务传播行为 | AOP（@Transactional、@Cacheable、安全校验） |

---

### 5. 核心区别详解

#### 5.1 意图不同

**策略模式**：
- **目的**：让客户端选择**不同的行为**（算法）
- **本质**：定义一组可替换的算法
- **客户端视角**：我要选择**哪种方式**完成任务

**代理模式**：
- **目的**：控制对目标对象的访问，增加**额外职责**
- **本质**：在不改变目标对象的前提下扩展功能
- **客户端视角**：我要访问这个对象，但可能有**额外的控制或增强**

---

#### 5.2 类图对比

**策略模式类图**：
```
Client --> Context --> Strategy <<interface>>
                           ^
                           |
          +----------------+----------------+
          |                |                |
    AlipayStrategy   WechatPayStrategy  BankCardStrategy

（客户端选择策略，Context持有策略引用）
```

**代理模式类图**：
```
Client --> Proxy --> Subject <<interface>>
             |            ^
             |            |
             +----> RealSubject

（客户端访问代理，代理持有真实对象引用）
```

---

#### 5.3 代码示例对比

**策略模式关键代码**：
```java
// 客户端主动选择策略
public void checkout(Order order, String paymentType) {
    PaymentStrategy strategy = strategies.get(paymentType);  // 选择策略
    strategy.pay(order.getAmount());  // 执行算法
}
```

**代理模式关键代码**：
```java
// 代理在执行前后增强功能
public void deleteUser(Long userId) {
    checkPermission();           // 前置增强
    target.deleteUser(userId);   // 调用真实对象
    logOperation(userId);        // 后置增强
}
```

---

### 6. 实际项目中的应用

#### 6.1 策略模式实战

**场景：电商促销活动**

```java
// 策略接口
public interface DiscountStrategy {
    BigDecimal calculate(BigDecimal originalPrice);
}

// 满减策略
@Component("fullReduction")
public class FullReductionStrategy implements DiscountStrategy {
    public BigDecimal calculate(BigDecimal originalPrice) {
        return originalPrice.compareTo(new BigDecimal("100")) >= 0
            ? originalPrice.subtract(new BigDecimal("20"))
            : originalPrice;
    }
}

// 折扣策略
@Component("discount")
public class PercentDiscountStrategy implements DiscountStrategy {
    public BigDecimal calculate(BigDecimal originalPrice) {
        return originalPrice.multiply(new BigDecimal("0.8"));  // 8折
    }
}

// VIP策略
@Component("vip")
public class VipDiscountStrategy implements DiscountStrategy {
    public BigDecimal calculate(BigDecimal originalPrice) {
        return originalPrice.multiply(new BigDecimal("0.7"));  // 7折
    }
}
```

---

#### 6.2 代理模式实战

**场景：数据库查询缓存**

```java
@Aspect
@Component
public class CacheAspect {
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Around("@annotation(Cacheable)")
    public Object cache(ProceedingJoinPoint joinPoint) throws Throwable {
        // 生成缓存key
        String key = generateKey(joinPoint);

        // 查询缓存
        Object cached = redisTemplate.opsForValue().get(key);
        if (cached != null) {
            return cached;
        }

        // 缓存未命中，执行目标方法
        Object result = joinPoint.proceed();

        // 写入缓存
        redisTemplate.opsForValue().set(key, result, 30, TimeUnit.MINUTES);

        return result;
    }
}
```

---

### 7. 面试答题总结

**标准回答模板**：

> **常用设计模式**：
> - 创建型：单例（Spring Bean）、工厂（BeanFactory）、建造者（StringBuilder）
> - 结构型：代理（AOP）、装饰器（IO流）、适配器（HandlerAdapter）
> - 行为型：策略（支付方式）、模板方法（JdbcTemplate）、观察者（事件机制）
>
> **策略模式 vs 代理模式**：
> - **策略模式**：封装可替换的算法族，客户端选择不同策略完成任务（如支付方式选择）
> - **代理模式**：控制对目标对象的访问，在不改变目标对象的前提下增强功能（如AOP的权限控制、日志记录）
>
> **核心区别**：
> - **意图**：策略模式关注算法的**选择和替换**，代理模式关注功能的**增强和控制**
> - **结构**：策略模式客户端主动选择策略，代理模式客户端通过代理间接访问目标对象
> - **应用场景**：策略模式用于业务规则多变场景，代理模式用于横切关注点（日志、事务、权限）

**常见追问**：
- **策略模式如何避免if-else？** → 通过Map存储策略实例，根据key动态获取
- **Spring AOP使用哪种代理？** → 默认JDK动态代理（基于接口），无接口时用CGLIB（基于子类）
- **装饰器模式和代理模式的区别？** → 装饰器关注增强对象功能（层层包装），代理关注控制访问（单层代理）
