---
title: "JDK 动态代理与 CGLIB 的实现有何区别？"
date: 2025-11-17
description: "深入对比JDK动态代理与CGLIB的实现原理、底层机制、性能差异及Spring AOP中的应用策略"
author: "wuxl"
categories: [设计模式]
tags: [动态代理, JDK动态代理, CGLIB, Spring AOP, 字节码, 反射]
nav_order: 76
parent: Java基础
---
## 问题

JDK 动态代理与 CGLIB 的实现有何区别？

## 答案

### 一、核心区别总览

| 对比维度 | JDK 动态代理 | CGLIB 动态代理 |
|---------|------------|--------------|
| **实现方式** | 基于接口的代理（Proxy） | 基于继承的代理（Subclass） |
| **底层技术** | Java 反射机制 | ASM 字节码框架 |
| **代理对象** | 实现目标接口的代理类 | 目标类的子类 |
| **使用条件** | 目标类必须实现接口 | 目标类不能是 final |
| **方法调用** | 通过反射 `Method.invoke()` | 直接调用（FastClass 机制） |
| **性能** | 创建快，调用慢 | 创建慢，调用快 |
| **依赖** | JDK 原生支持 | 需要 cglib 依赖 |

### 二、JDK 动态代理实现原理

#### 核心机制

1. **基于接口**：代理类实现目标对象的所有接口
2. **Proxy 类**：通过 `Proxy.newProxyInstance()` 动态生成代理类
3. **InvocationHandler**：所有方法调用都转发到 `invoke()` 方法
4. **反射调用**：通过 `Method.invoke()` 调用目标方法

#### 源码关键点

```java
// Proxy.newProxyInstance 核心流程
public static Object newProxyInstance(ClassLoader loader,
                                      Class<?>[] interfaces,
                                      InvocationHandler h) {
    // 1. 查找或生成代理类
    Class<?> cl = getProxyClass0(loader, interfaces);

    // 2. 获取代理类的构造器（参数为 InvocationHandler）
    Constructor<?> cons = cl.getConstructor(InvocationHandler.class);

    // 3. 创建代理实例
    return cons.newInstance(h);
}
```

#### 生成的代理类结构

```java
// JDK 动态生成的代理类（简化版）
public final class $Proxy0 extends Proxy implements UserService {
    private static Method m3; // addUser 方法

    public $Proxy0(InvocationHandler h) {
        super(h);
    }

    @Override
    public void addUser(String name) {
        try {
            // 调用 InvocationHandler.invoke()
            super.h.invoke(this, m3, new Object[]{name});
        } catch (Throwable e) {
            throw new UndeclaredThrowableException(e);
        }
    }
}
```

#### 完整示例

```java
interface UserService {
    void addUser(String name);
}

class UserServiceImpl implements UserService {
    @Override
    public void addUser(String name) {
        System.out.println("添加用户: " + name);
    }
}

class JdkProxyHandler implements InvocationHandler {
    private Object target;

    public JdkProxyHandler(Object target) {
        this.target = target;
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        System.out.println("[JDK代理] 方法执行前");
        Object result = method.invoke(target, args);
        System.out.println("[JDK代理] 方法执行后");
        return result;
    }
}

// 使用
UserService target = new UserServiceImpl();
UserService proxy = (UserService) Proxy.newProxyInstance(
    target.getClass().getClassLoader(),
    target.getClass().getInterfaces(),
    new JdkProxyHandler(target)
);
proxy.addUser("张三");
```

### 三、CGLIB 动态代理实现原理

#### 核心机制

1. **基于继承**：生成目标类的子类作为代理类
2. **字节码生成**：使用 ASM 框架直接生成字节码
3. **MethodInterceptor**：拦截所有方法调用
4. **FastClass 机制**：避免反射调用，直接通过索引调用方法

#### 核心组件

```java
// Enhancer：CGLIB 的核心类
Enhancer enhancer = new Enhancer();
enhancer.setSuperclass(TargetClass.class);  // 设置父类
enhancer.setCallback(new MethodInterceptor() {
    @Override
    public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy) {
        // obj: 代理对象
        // method: 被拦截的方法
        // args: 方法参数
        // proxy: 方法代理（用于调用父类方法）
        return proxy.invokeSuper(obj, args);
    }
});
```

#### 生成的代理类结构

```java
// CGLIB 生成的代理类（简化版）
public class UserService$$EnhancerByCGLIB$$12345 extends UserService {
    private MethodInterceptor interceptor;

    @Override
    public void addUser(String name) {
        // 调用 MethodInterceptor.intercept()
        interceptor.intercept(this,
            CGLIB$addUser$0$Method,
            new Object[]{name},
            CGLIB$addUser$0$Proxy);
    }

    // FastClass 机制：通过索引直接调用，避免反射
    final void CGLIB$addUser$0(String name) {
        super.addUser(name);
    }
}
```

#### 完整示例

```java
import net.sf.cglib.proxy.Enhancer;
import net.sf.cglib.proxy.MethodInterceptor;
import net.sf.cglib.proxy.MethodProxy;

// 目标类（无需实现接口）
class OrderService {
    public void createOrder(String orderId) {
        System.out.println("创建订单: " + orderId);
    }
}

class CglibInterceptor implements MethodInterceptor {
    @Override
    public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy) throws Throwable {
        System.out.println("[CGLIB代理] 方法执行前");
        // 注意：使用 invokeSuper 而不是 invoke，避免死循环
        Object result = proxy.invokeSuper(obj, args);
        System.out.println("[CGLIB代理] 方法执行后");
        return result;
    }
}

// 使用
Enhancer enhancer = new Enhancer();
enhancer.setSuperclass(OrderService.class);
enhancer.setCallback(new CglibInterceptor());
OrderService proxy = (OrderService) enhancer.create();
proxy.createOrder("ORDER-001");
```

### 四、性能对比分析

#### 创建性能

```java
// JDK 动态代理：快
// - 只需生成接口实现类
// - 类结构简单

// CGLIB：慢
// - 需要生成子类并重写所有方法
// - 字节码生成开销大
```

#### 调用性能

```java
// JDK 动态代理：慢
public Object invoke(Object proxy, Method method, Object[] args) {
    return method.invoke(target, args);  // 反射调用
}

// CGLIB：快
public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy) {
    return proxy.invokeSuper(obj, args);  // FastClass 直接调用
}
```

#### 实际测试数据（参考）

| 操作 | JDK 动态代理 | CGLIB |
|-----|------------|-------|
| 创建代理对象 | ~0.1ms | ~10ms |
| 方法调用（100万次） | ~50ms | ~30ms |

**结论**：
- 代理对象创建频繁：选 JDK 动态代理
- 方法调用频繁：选 CGLIB
- 实际应用中差异不大（Spring 会缓存代理对象）

### 五、使用限制对比

#### JDK 动态代理限制

```java
// ❌ 无法代理没有接口的类
class UserService {  // 没有实现接口
    public void addUser(String name) { }
}

// ❌ 无法代理接口中没有的方法
interface UserService {
    void addUser(String name);
}
class UserServiceImpl implements UserService {
    public void addUser(String name) { }
    public void deleteUser(int id) { }  // 无法被代理
}
```

#### CGLIB 限制

```java
// ❌ 无法代理 final 类
public final class UserService {
    public void addUser(String name) { }
}

// ❌ 无法代理 final 方法
public class UserService {
    public final void addUser(String name) { }
}

// ❌ 无法代理 private 方法
public class UserService {
    private void addUser(String name) { }
}

// ❌ 无法代理 static 方法
public class UserService {
    public static void addUser(String name) { }
}
```

### 六、Spring AOP 中的应用

#### 代理选择策略

```java
// Spring AOP 默认策略
if (目标类实现了接口) {
    使用 JDK 动态代理;
} else {
    使用 CGLIB 代理;
}

// 强制使用 CGLIB
@EnableAspectJAutoProxy(proxyTargetClass = true)
```

#### 配置示例

```java
// 1. 默认行为（有接口用 JDK，无接口用 CGLIB）
@Configuration
@EnableAspectJAutoProxy
public class AppConfig { }

// 2. 强制使用 CGLIB
@Configuration
@EnableAspectJAutoProxy(proxyTargetClass = true)
public class AppConfig { }

// 3. Spring Boot 配置
spring.aop.proxy-target-class=true  # 强制 CGLIB
```

#### 实际影响

```java
// JDK 代理：只能注入接口类型
@Autowired
private UserService userService;  // ✅ 接口类型

@Autowired
private UserServiceImpl userService;  // ❌ 实现类类型（报错）

// CGLIB 代理：可以注入实现类类型
@Autowired
private UserServiceImpl userService;  // ✅ 实现类类型
```

### 七、面试答题要点

1. **实现方式**：JDK 基于接口代理，CGLIB 基于继承生成子类
2. **底层技术**：JDK 用反射，CGLIB 用 ASM 字节码
3. **使用条件**：JDK 需要接口，CGLIB 不能代理 final
4. **性能差异**：JDK 创建快调用慢，CGLIB 相反；实际应用差异不大
5. **Spring 策略**：默认有接口用 JDK，无接口用 CGLIB；可通过配置强制使用 CGLIB
6. **实际选择**：优先 JDK（无依赖、简单），无接口时用 CGLIB
