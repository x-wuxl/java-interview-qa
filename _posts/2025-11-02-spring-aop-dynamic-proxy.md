---
layout: post
title: "Spring AOP实现，动态代理"
date: 2025-11-02
description: "深入剖析Spring AOP的动态代理实现原理，包括JDK动态代理和CGLIB代理的源码分析、对比及使用场景"
author: "wuxl"
categories: [Spring框架]
tags: [Spring AOP, 动态代理, JDK动态代理, CGLIB代理, 设计模式]
---

## 问题

Spring AOP实现，动态代理

## 答案

### 1. 核心概念

Spring AOP的底层是通过**动态代理**实现的，在运行时为目标对象生成代理对象，在代理对象中织入增强逻辑。

**动态代理的两种实现方式**：
- **JDK动态代理**：基于接口，使用Java反射机制
- **CGLIB代理**：基于继承，使用字节码生成技术

### 2. JDK动态代理

#### （1）实现原理

JDK动态代理基于**反射机制**，通过`java.lang.reflect.Proxy`类动态生成代理对象。

**核心API**：
- `Proxy.newProxyInstance()`：创建代理对象
- `InvocationHandler`：定义代理逻辑

**限制**：只能代理实现了接口的类。

#### （2）手动实现示例

```java
// 定义接口
public interface UserService {
    void addUser(String name);
    String getUser(Long id);
}

// 目标类实现接口
public class UserServiceImpl implements UserService {
    
    @Override
    public void addUser(String name) {
        System.out.println("添加用户: " + name);
    }
    
    @Override
    public String getUser(Long id) {
        System.out.println("查询用户: " + id);
        return "User-" + id;
    }
}

// 实现InvocationHandler
public class LogInvocationHandler implements InvocationHandler {
    
    private Object target;  // 目标对象
    
    public LogInvocationHandler(Object target) {
        this.target = target;
    }
    
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        // 前置增强
        System.out.println("Before: " + method.getName());
        
        // 调用目标方法
        Object result = method.invoke(target, args);
        
        // 后置增强
        System.out.println("After: " + method.getName());
        
        return result;
    }
}

// 测试
public class JdkProxyTest {
    
    public static void main(String[] args) {
        // 创建目标对象
        UserService target = new UserServiceImpl();
        
        // 创建代理对象
        UserService proxy = (UserService) Proxy.newProxyInstance(
            target.getClass().getClassLoader(),  // 类加载器
            target.getClass().getInterfaces(),   // 代理的接口
            new LogInvocationHandler(target)     // InvocationHandler
        );
        
        // 通过代理对象调用方法
        proxy.addUser("张三");
        String user = proxy.getUser(1L);
        
        // 输出：
        // Before: addUser
        // 添加用户: 张三
        // After: addUser
        // Before: getUser
        // 查询用户: 1
        // After: getUser
    }
}
```

#### （3）原理分析

```java
// JDK动态代理生成的代理类（简化版）
public final class $Proxy0 extends Proxy implements UserService {
    
    private static Method m3;  // addUser方法
    private static Method m4;  // getUser方法
    
    static {
        try {
            m3 = Class.forName("com.example.UserService")
                .getMethod("addUser", new Class[]{String.class});
            m4 = Class.forName("com.example.UserService")
                .getMethod("getUser", new Class[]{Long.class});
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
    
    public $Proxy0(InvocationHandler h) {
        super(h);
    }
    
    @Override
    public void addUser(String name) {
        try {
            // 调用InvocationHandler.invoke()
            this.h.invoke(this, m3, new Object[]{name});
        } catch (Throwable t) {
            throw new RuntimeException(t);
        }
    }
    
    @Override
    public String getUser(Long id) {
        try {
            return (String) this.h.invoke(this, m4, new Object[]{id});
        } catch (Throwable t) {
            throw new RuntimeException(t);
        }
    }
}
```

**调用流程**：

```java
// 调用链
proxy.addUser("张三")
  → $Proxy0.addUser("张三")
    → InvocationHandler.invoke(proxy, addUserMethod, ["张三"])
      → method.invoke(target, ["张三"])  // 反射调用目标方法
        → UserServiceImpl.addUser("张三")
```

#### （4）查看生成的代理类

```java
public class ProxyClassTest {
    
    public static void main(String[] args) throws Exception {
        // JDK 8及以前：设置系统属性，将代理类保存到文件
        System.getProperties().put("sun.misc.ProxyGenerator.saveGeneratedFiles", "true");
        
        // JDK 9+：使用jdk.proxy.ProxyGenerator.saveGeneratedFiles
        System.getProperties().put("jdk.proxy.ProxyGenerator.saveGeneratedFiles", "true");
        
        UserService target = new UserServiceImpl();
        UserService proxy = (UserService) Proxy.newProxyInstance(
            target.getClass().getClassLoader(),
            target.getClass().getInterfaces(),
            new LogInvocationHandler(target)
        );
        
        proxy.addUser("张三");
        
        // 生成的代理类位于：com/sun/proxy/$Proxy0.class
    }
}
```

### 3. CGLIB代理

#### （1）实现原理

CGLIB（Code Generation Library）基于**ASM字节码框架**，通过**继承目标类**生成子类代理。

**核心API**：
- `Enhancer`：代理类生成器
- `MethodInterceptor`：方法拦截器

**优势**：可以代理没有接口的类。

**限制**：
- 无法代理final类
- 无法代理final方法
- 无法代理private方法

#### （2）添加依赖

```xml
<!-- Spring Boot已包含CGLIB，无需单独引入 -->
<!-- 如果是纯Spring项目，需要添加 -->
<dependency>
    <groupId>cglib</groupId>
    <artifactId>cglib</artifactId>
    <version>3.3.0</version>
</dependency>
```

#### （3）手动实现示例

```java
import net.sf.cglib.proxy.Enhancer;
import net.sf.cglib.proxy.MethodInterceptor;
import net.sf.cglib.proxy.MethodProxy;

// 目标类（无需实现接口）
public class UserService {
    
    public void addUser(String name) {
        System.out.println("添加用户: " + name);
    }
    
    public String getUser(Long id) {
        System.out.println("查询用户: " + id);
        return "User-" + id;
    }
}

// 实现MethodInterceptor
public class LogMethodInterceptor implements MethodInterceptor {
    
    @Override
    public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy) throws Throwable {
        // 前置增强
        System.out.println("Before: " + method.getName());
        
        // 调用目标方法（两种方式）
        // 方式1：通过父类方法调用（推荐，性能更好）
        Object result = proxy.invokeSuper(obj, args);
        
        // 方式2：通过反射调用（不推荐）
        // Object result = method.invoke(target, args);
        
        // 后置增强
        System.out.println("After: " + method.getName());
        
        return result;
    }
}

// 测试
public class CglibProxyTest {
    
    public static void main(String[] args) {
        // 创建Enhancer对象
        Enhancer enhancer = new Enhancer();
        
        // 设置父类
        enhancer.setSuperclass(UserService.class);
        
        // 设置回调
        enhancer.setCallback(new LogMethodInterceptor());
        
        // 创建代理对象
        UserService proxy = (UserService) enhancer.create();
        
        // 通过代理对象调用方法
        proxy.addUser("张三");
        String user = proxy.getUser(1L);
        
        // 输出：
        // Before: addUser
        // 添加用户: 张三
        // After: addUser
        // Before: getUser
        // 查询用户: 1
        // After: getUser
    }
}
```

#### （4）原理分析

```java
// CGLIB生成的代理类（简化版）
public class UserService$$EnhancerByCGLIB$$12345678 extends UserService {
    
    private MethodInterceptor interceptor;
    
    @Override
    public void addUser(String name) {
        // 调用MethodInterceptor.intercept()
        interceptor.intercept(
            this,                          // 代理对象
            addUserMethod,                 // 目标方法
            new Object[]{name},            // 方法参数
            addUserMethodProxy             // 方法代理（用于调用父类方法）
        );
    }
    
    @Override
    public String getUser(Long id) {
        return (String) interceptor.intercept(
            this,
            getUserMethod,
            new Object[]{id},
            getUserMethodProxy
        );
    }
    
    // 父类方法的快速访问（FastClass机制）
    final void CGLIB$addUser$0(String name) {
        super.addUser(name);  // 直接调用父类方法
    }
}
```

**调用流程**：

```java
// 调用链
proxy.addUser("张三")
  → UserService$$EnhancerByCGLIB$$12345678.addUser("张三")
    → MethodInterceptor.intercept(proxy, addUserMethod, ["张三"], addUserMethodProxy)
      → MethodProxy.invokeSuper(proxy, ["张三"])
        → proxy.CGLIB$addUser$0("张三")  // FastClass机制，避免反射
          → UserService.addUser("张三")
```

#### （5）FastClass机制

CGLIB使用**FastClass机制**避免反射调用，提高性能。

```java
// 为目标类生成FastClass
public class UserService$$FastClassByCGLIB$$12345678 extends FastClass {
    
    @Override
    public Object invoke(int index, Object obj, Object[] args) {
        UserService target = (UserService) obj;
        
        switch (index) {
            case 0:  // addUser方法的索引
                target.addUser((String) args[0]);
                return null;
            case 1:  // getUser方法的索引
                return target.getUser((Long) args[0]);
            default:
                throw new IllegalArgumentException("Unknown method index: " + index);
        }
    }
}

// 直接通过索引调用，避免反射
fastClass.invoke(0, target, new Object[]{"张三"});  // 调用addUser
```

### 4. Spring AOP代理选择

#### （1）代理选择策略

```java
@Configuration
@EnableAspectJAutoProxy  // 启用AOP
public class AopConfig {
}
```

**默认策略**：
- 目标对象**实现了接口** → JDK动态代理
- 目标对象**未实现接口** → CGLIB代理

#### （2）强制使用CGLIB

```java
@Configuration
@EnableAspectJAutoProxy(proxyTargetClass = true)  // 强制CGLIB
public class AopConfig {
}
```

或在配置文件中：

```yaml
spring:
  aop:
    proxy-target-class: true  # 强制使用CGLIB
```

#### （3）源码分析

```java
// Spring AOP代理创建核心类：DefaultAopProxyFactory
public class DefaultAopProxyFactory implements AopProxyFactory {
    
    @Override
    public AopProxy createAopProxy(AdvisedSupport config) throws AopConfigException {
        // 判断使用JDK代理还是CGLIB代理
        if (config.isOptimize() || 
            config.isProxyTargetClass() || 
            hasNoUserSuppliedProxyInterfaces(config)) {
            
            Class<?> targetClass = config.getTargetClass();
            
            if (targetClass == null) {
                throw new AopConfigException("TargetSource cannot determine target class");
            }
            
            // 如果目标类是接口或已经是JDK代理，使用JDK代理
            if (targetClass.isInterface() || Proxy.isProxyClass(targetClass)) {
                return new JdkDynamicAopProxy(config);
            }
            
            // 否则使用CGLIB代理
            return new ObjenesisCglibAopProxy(config);
        } else {
            // 有接口，使用JDK代理
            return new JdkDynamicAopProxy(config);
        }
    }
}
```

### 5. JDK动态代理 vs CGLIB代理

| 维度 | JDK动态代理 | CGLIB代理 |
|------|-----------|----------|
| **实现方式** | 基于接口（反射） | 基于继承（字节码） |
| **要求** | 必须实现接口 | 无需接口 |
| **代理对象** | 实现接口的代理类 | 目标类的子类 |
| **性能（JDK 8+）** | 调用性能接近CGLIB | 创建代理快，调用略慢 |
| **限制** | 只能代理接口方法 | 无法代理final类/方法 |
| **Spring默认** | 有接口时使用 | 无接口时使用 |
| **依赖** | JDK自带 | 需要第三方库 |

#### 性能对比

```java
public class PerformanceTest {
    
    public static void main(String[] args) {
        int count = 10_000_000;
        
        // 1. 创建代理性能测试
        long jdkCreateStart = System.currentTimeMillis();
        for (int i = 0; i < 1000; i++) {
            UserService jdkProxy = createJdkProxy();
        }
        long jdkCreateEnd = System.currentTimeMillis();
        System.out.println("JDK创建代理: " + (jdkCreateEnd - jdkCreateStart) + "ms");
        
        long cglibCreateStart = System.currentTimeMillis();
        for (int i = 0; i < 1000; i++) {
            UserService cglibProxy = createCglibProxy();
        }
        long cglibCreateEnd = System.currentTimeMillis();
        System.out.println("CGLIB创建代理: " + (cglibCreateEnd - cglibCreateStart) + "ms");
        
        // 2. 方法调用性能测试
        UserService jdkProxy = createJdkProxy();
        long jdkInvokeStart = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            jdkProxy.getUser(1L);
        }
        long jdkInvokeEnd = System.currentTimeMillis();
        System.out.println("JDK方法调用: " + (jdkInvokeEnd - jdkInvokeStart) + "ms");
        
        UserService cglibProxy = createCglibProxy();
        long cglibInvokeStart = System.currentTimeMillis();
        for (int i = 0; i < count; i++) {
            cglibProxy.getUser(1L);
        }
        long cglibInvokeEnd = System.currentTimeMillis();
        System.out.println("CGLIB方法调用: " + (cglibInvokeEnd - cglibInvokeStart) + "ms");
    }
}

// 典型结果（JDK 8+）：
// JDK创建代理: 50ms
// CGLIB创建代理: 200ms（慢4倍）
// JDK方法调用: 150ms
// CGLIB方法调用: 160ms（性能接近）
```

**结论**：
- **JDK 6/7**：CGLIB调用性能明显优于JDK代理
- **JDK 8+**：JDK代理调用性能大幅优化，与CGLIB接近
- **创建性能**：JDK代理创建更快
- **Spring推荐**：优先使用JDK代理（有接口）

### 6. 实际应用场景

#### 场景1：基于接口设计（推荐）

```java
// 定义接口
public interface UserService {
    void addUser(User user);
    User getUser(Long id);
}

// 实现类
@Service
public class UserServiceImpl implements UserService {
    
    @Override
    @Transactional
    public void addUser(User user) {
        userDao.save(user);
    }
    
    @Override
    public User getUser(Long id) {
        return userDao.findById(id);
    }
}

// Spring使用JDK动态代理
// 代理类：UserService$$Proxy0 implements UserService
```

#### 场景2：无接口类（使用CGLIB）

```java
@Service
public class OrderService {  // 未实现接口
    
    @Transactional
    public void createOrder(Order order) {
        orderDao.save(order);
    }
}

// Spring使用CGLIB代理
// 代理类：OrderService$$EnhancerBySpringCGLIB$$xxx extends OrderService
```

#### 场景3：检查代理类型

```java
@Service
public class UserService implements UserServiceInterface {
    
    @Autowired
    private ApplicationContext context;
    
    public void checkProxyType() {
        UserService bean = context.getBean(UserService.class);
        
        // 检查是否是JDK代理
        boolean isJdkProxy = Proxy.isProxyClass(bean.getClass());
        System.out.println("Is JDK Proxy: " + isJdkProxy);
        
        // 检查是否是CGLIB代理
        boolean isCglibProxy = bean.getClass().getName().contains("$$");
        System.out.println("Is CGLIB Proxy: " + isCglibProxy);
        
        // 输出代理类名
        System.out.println("Proxy Class: " + bean.getClass().getName());
        // JDK: com.sun.proxy.$Proxy123
        // CGLIB: com.example.UserService$$EnhancerBySpringCGLIB$$12345678
    }
}
```

### 7. 代理失效问题

#### （1）JDK代理失效

```java
// 接口
public interface UserService {
    void method();
}

// 实现类添加了接口没有的方法
@Service
public class UserServiceImpl implements UserService {
    
    @Override
    public void method() {
        System.out.println("Interface method");
    }
    
    // 这个方法不在接口中
    @Transactional
    public void extraMethod() {
        System.out.println("Extra method");
    }
}

// 使用
@Autowired
private UserService userService;  // 注入接口类型

public void test() {
    userService.method();  // 正常
    // userService.extraMethod();  // 编译错误，接口没有此方法
    
    // 如果强制转换
    ((UserServiceImpl) userService).extraMethod();  // ClassCastException
}
```

**解决方案**：注入实现类类型

```java
@Autowired
private UserServiceImpl userService;  // 注入实现类类型

public void test() {
    userService.extraMethod();  // 正常（Spring会使用CGLIB代理）
}
```

#### （2）CGLIB代理限制

```java
@Service
public final class FinalService {  // final类，无法被CGLIB代理
    
    @Transactional
    public void method() {
        // AOP失效
    }
}

@Service
public class UserService {
    
    @Transactional
    public final void finalMethod() {  // final方法，无法被重写
        // AOP失效
    }
}
```

### 8. 面试答题要点

**标准回答结构**：

1. **核心概念**：Spring AOP基于动态代理实现，有JDK动态代理和CGLIB代理两种方式

2. **JDK动态代理**：
   - 基于接口和反射
   - 使用Proxy和InvocationHandler
   - 只能代理实现了接口的类

3. **CGLIB代理**：
   - 基于继承和字节码生成
   - 使用Enhancer和MethodInterceptor
   - 可以代理没有接口的类
   - 无法代理final类/方法

4. **代理选择**：
   - 有接口 → JDK代理
   - 无接口 → CGLIB代理
   - 可强制使用CGLIB

5. **性能对比**：
   - JDK 8+性能接近
   - JDK代理创建更快
   - CGLIB有FastClass优化

**加分点**：
- 了解代理类生成机制
- 知道FastClass优化原理
- 能说明Spring的代理选择策略
- 了解两种代理的限制和适用场景
- 能手写简单的动态代理示例

### 9. 总结

**核心要点**：

| 维度 | JDK动态代理 | CGLIB代理 |
|------|-----------|----------|
| **原理** | 反射 + 接口 | 字节码 + 继承 |
| **前提** | 必须有接口 | 无需接口 |
| **限制** | 只代理接口方法 | 无法代理final |
| **性能** | 创建快，调用快（JDK 8+） | 创建慢，调用快 |
| **使用** | Spring默认（有接口） | Spring默认（无接口） |

**记忆口诀**：
- 动态代理两方式，JDK和CGLIB
- JDK基于接口，反射来实现
- CGLIB基于继承，字节码生成
- 有接口用JDK，无接口用CGLIB
- final类和方法，CGLIB代理不了
- FastClass优化好，避免反射慢

**使用建议**：
- 优先设计接口：使用JDK代理
- 无接口场景：使用CGLIB代理
- 避免使用final：保证代理生效
- 注入接口类型：避免类型转换问题

理解Spring AOP的动态代理实现原理，是掌握AOP技术和排查代理问题的关键，也是Spring面试的高频考点。

