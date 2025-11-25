---
layout: default
title: "@Lazy注解能解决循环依赖吗？"
parent: Spring框架
nav_order: 453
description: "详解@Lazy注解的工作原理及其在解决循环依赖问题中的应用"
date: 2025-11-02
---
## 核心概念

**答案：可以！** `@Lazy`注解可以解决循环依赖问题，特别是构造器注入导致的循环依赖。

### @Lazy注解的作用

`@Lazy`是Spring提供的延迟初始化注解，主要作用：

1. **延迟Bean的创建**：在首次使用时才创建Bean，而不是容器启动时
2. **创建代理对象**：在依赖注入时注入一个代理对象，延迟实际Bean的加载
3. **打破循环依赖**：通过代理延迟依赖的解析，避免死锁

## @Lazy解决循环依赖的原理

### 工作机制

```java
@Service
public class ServiceA {
    private final ServiceB serviceB;
    
    @Autowired
    public ServiceA(@Lazy ServiceB serviceB) {  // 注入代理对象
        this.serviceB = serviceB;
    }
    
    public void methodA() {
        serviceB.methodB();  // 首次调用时才获取真实对象
    }
}

@Service
public class ServiceB {
    private final ServiceA serviceA;
    
    @Autowired
    public ServiceB(ServiceA serviceA) {  // 正常注入
        this.serviceA = serviceA;
    }
    
    public void methodB() {
        System.out.println("ServiceB.methodB");
    }
}
```

**原理分析**：

1. **创建ServiceA时**：
   - 调用构造器，需要注入ServiceB
   - 发现`@Lazy`注解，不立即创建ServiceB
   - 创建ServiceB的**代理对象**注入
   - ServiceA创建完成

2. **创建ServiceB时**：
   - 调用构造器，需要注入ServiceA
   - ServiceA已经创建完成（步骤1）
   - 直接注入ServiceA
   - ServiceB创建完成

3. **首次调用serviceB.methodB()时**：
   - 代理拦截方法调用
   - 从Spring容器获取真实的ServiceB
   - 调用真实对象的方法

### 流程对比

#### 不使用@Lazy（死锁）

```
创建ServiceA
  → 构造器需要ServiceB
    → 创建ServiceB
      → 构造器需要ServiceA
        → 创建ServiceA（循环）❌ 死锁
```

#### 使用@Lazy（成功）

```
创建ServiceA
  → 构造器需要ServiceB
    → 注入ServiceB的代理✅
  → ServiceA创建完成

创建ServiceB
  → 构造器需要ServiceA
    → 注入已存在的ServiceA✅
  → ServiceB创建完成

调用serviceB.methodB()
  → 代理拦截
  → 获取真实ServiceB
  → 调用方法✅
```

## @Lazy的使用场景

### 场景1：构造器注入的循环依赖（最常用）

```java
@Service
public class OrderService {
    private final UserService userService;
    
    @Autowired
    public OrderService(@Lazy UserService userService) {
        this.userService = userService;
    }
    
    public void createOrder(Long userId) {
        User user = userService.findById(userId);
        // 创建订单逻辑
    }
}

@Service
public class UserService {
    private final OrderService orderService;
    
    @Autowired
    public UserService(OrderService orderService) {
        this.orderService = orderService;
    }
    
    public User findById(Long id) {
        // 查询用户逻辑
        return new User();
    }
}
```

**优势**：
- 保持构造器注入的优点（依赖明确、不可变）
- 解决循环依赖问题
- 代码改动最小（只需添加`@Lazy`）

### 场景2：延迟加载重量级Bean

```java
@Configuration
public class AppConfig {
    
    @Bean
    @Lazy  // 容器启动时不创建，首次使用时才创建
    public HeavyService heavyService() {
        return new HeavyService();
    }
}

@Service
public class MyService {
    
    @Autowired
    @Lazy  // 注入代理，延迟加载
    private HeavyService heavyService;
    
    public void doSomething() {
        if (needHeavyService) {
            heavyService.process();  // 这里才真正创建
        }
    }
}
```

**优势**：
- 减少启动时间
- 降低内存占用
- 按需加载

### 场景3：字段注入和Setter注入

```java
@Service
public class ServiceA {
    
    // 字段注入
    @Autowired
    @Lazy
    private ServiceB serviceB;
    
    // Setter注入
    private ServiceC serviceC;
    
    @Autowired
    public void setServiceC(@Lazy ServiceC serviceC) {
        this.serviceC = serviceC;
    }
}
```

**注意**：字段注入和Setter注入的循环依赖Spring本身就能解决，使用`@Lazy`主要是为了延迟加载。

## @Lazy的实现原理

### 源码分析

#### 1. 代理对象的创建

```java
// ContextAnnotationAutowireCandidateResolver
@Override
@Nullable
public Object getLazyResolutionProxyIfNecessary(DependencyDescriptor descriptor, @Nullable String beanName) {
    // 检查是否有@Lazy注解
    return (isLazy(descriptor) ? buildLazyResolutionProxy(descriptor, beanName) : null);
}

protected Object buildLazyResolutionProxy(final DependencyDescriptor descriptor, final @Nullable String beanName) {
    // 创建代理工厂
    TargetSource ts = new TargetSource() {
        @Override
        public Object getTarget() {
            // 延迟获取真实Bean
            return beanFactory.doResolveDependency(descriptor, beanName, null, null);
        }
        
        @Override
        public Class<?> getTargetClass() {
            return descriptor.getDependencyType();
        }
    };
    
    // 创建代理对象
    ProxyFactory pf = new ProxyFactory();
    pf.setTargetSource(ts);
    
    Class<?> dependencyType = descriptor.getDependencyType();
    if (dependencyType.isInterface()) {
        pf.addInterface(dependencyType);  // JDK动态代理
    }
    
    return pf.getProxy(beanFactory.getBeanClassLoader());  // 返回代理
}
```

**关键点**：
1. 检测到`@Lazy`注解时，不立即获取Bean
2. 创建一个代理对象
3. 代理内部持有`TargetSource`，延迟获取真实Bean
4. 首次调用方法时，才从容器获取真实Bean

#### 2. 代理的调用流程

```java
// CGLIB代理的拦截器
public class LazyInitTargetSourceInterceptor implements MethodInterceptor {
    
    private final TargetSource targetSource;
    
    @Override
    public Object intercept(Object proxy, Method method, Object[] args, MethodProxy methodProxy) {
        // 获取真实对象
        Object target = this.targetSource.getTarget();
        
        // 调用真实对象的方法
        return method.invoke(target, args);
    }
}
```

**流程**：
```
调用代理方法
  ↓
拦截器拦截
  ↓
首次调用：从Spring容器获取真实Bean
  ↓
后续调用：直接使用缓存的Bean
  ↓
执行真实方法
```

## 完整示例

### 示例1：构造器循环依赖解决

```java
// 配置类
@Configuration
@ComponentScan("com.example")
public class AppConfig {
}

// ServiceA
@Service
public class ServiceA {
    private final ServiceB serviceB;
    
    @Autowired
    public ServiceA(@Lazy ServiceB serviceB) {
        System.out.println("ServiceA构造器执行");
        System.out.println("注入的ServiceB: " + serviceB.getClass().getName());
        this.serviceB = serviceB;
    }
    
    public void methodA() {
        System.out.println("ServiceA.methodA调用");
        serviceB.methodB();
    }
}

// ServiceB
@Service
public class ServiceB {
    private final ServiceA serviceA;
    
    @Autowired
    public ServiceB(ServiceA serviceA) {
        System.out.println("ServiceB构造器执行");
        this.serviceA = serviceA;
    }
    
    public void methodB() {
        System.out.println("ServiceB.methodB调用");
    }
}

// 测试
@SpringBootTest
public class LazyTest {
    
    @Autowired
    private ServiceA serviceA;
    
    @Test
    public void test() {
        System.out.println("\n=== 开始调用方法 ===");
        serviceA.methodA();
    }
}
```

**输出结果**：

```
ServiceA构造器执行
注入的ServiceB: com.example.ServiceB$$EnhancerBySpringCGLIB$$12345678  // 代理对象
ServiceB构造器执行

=== 开始调用方法 ===
ServiceA.methodA调用
ServiceB.methodB调用
```

**分析**：
1. ServiceA先创建，注入ServiceB的代理
2. ServiceB后创建，注入真实的ServiceA
3. 调用方法时，代理转发到真实ServiceB

### 示例2：多个依赖的选择性@Lazy

```java
@Service
public class ComplexService {
    
    private final ServiceA serviceA;
    private final ServiceB serviceB;
    private final ServiceC serviceC;
    
    @Autowired
    public ComplexService(
        @Lazy ServiceA serviceA,    // 延迟加载
        ServiceB serviceB,           // 立即加载
        @Lazy ServiceC serviceC      // 延迟加载
    ) {
        this.serviceA = serviceA;
        this.serviceB = serviceB;
        this.serviceC = serviceC;
    }
    
    public void process() {
        serviceB.method();           // 直接调用
        
        if (condition1) {
            serviceA.method();       // 条件调用，延迟加载
        }
        
        if (condition2) {
            serviceC.method();       // 条件调用，延迟加载
        }
    }
}
```

**优势**：
- 必需的依赖立即加载
- 可选的依赖延迟加载
- 提高启动性能

### 示例3：@Lazy在@Configuration中的使用

```java
@Configuration
public class DatabaseConfig {
    
    // 方法级别的@Lazy：Bean定义为懒加载
    @Bean
    @Lazy
    public DataSource dataSource() {
        System.out.println("创建DataSource（耗时操作）");
        HikariDataSource ds = new HikariDataSource();
        ds.setJdbcUrl("jdbc:mysql://localhost:3306/test");
        return ds;
    }
    
    @Bean
    public UserRepository userRepository(@Lazy DataSource dataSource) {
        // 注入时也是懒加载
        return new UserRepository(dataSource);
    }
}

// 类级别的@Lazy：所有Bean都懒加载
@Configuration
@Lazy
public class CacheConfig {
    
    @Bean
    public CacheManager cacheManager() {
        return new ConcurrentMapCacheManager();
    }
    
    @Bean
    public CacheService cacheService() {
        return new CacheService();
    }
}
```

## @Lazy的注意事项

### 1. 性能权衡

```java
// 优点：减少启动时间
@Lazy
@Bean
public HeavyService heavyService() {
    return new HeavyService();  // 延迟创建
}

// 缺点：首次调用时可能有延迟
public void firstCall() {
    heavyService.process();  // 这里可能会慢
}
```

**建议**：
- 启动时不需要的Bean使用`@Lazy`
- 关键路径的Bean不使用`@Lazy`

### 2. 代理的副作用

```java
@Service
public class ServiceA {
    @Autowired
    @Lazy
    private ServiceB serviceB;
    
    public void test() {
        // serviceB是代理对象，不是原始对象
        System.out.println(serviceB.getClass());
        // 输出：ServiceB$$EnhancerBySpringCGLIB$$...
        
        // instanceof检查仍然有效
        System.out.println(serviceB instanceof ServiceB);  // true
        
        // 但类型不完全相等
        System.out.println(serviceB.getClass() == ServiceB.class);  // false
    }
}
```

### 3. final方法无法被代理

```java
@Service
public class ServiceB {
    
    public final void finalMethod() {
        // CGLIB无法代理final方法
    }
    
    public void normalMethod() {
        // 可以被代理
    }
}
```

**限制**：
- CGLIB代理无法代理final类和final方法
- 如果需要代理final方法，考虑使用接口（JDK动态代理）

### 4. 事务失效问题

```java
@Service
public class ServiceA {
    @Autowired
    @Lazy
    private ServiceB serviceB;
    
    public void method() {
        serviceB.transactionalMethod();  // 代理调用，事务生效✅
    }
}

@Service
public class ServiceB {
    
    @Transactional
    public void transactionalMethod() {
        // 事务方法
    }
}
```

**注意**：通过`@Lazy`代理调用事务方法是有效的，因为代理会正确处理事务。

## @Lazy vs 其他解决方案

### 对比表

| 解决方案 | 优点 | 缺点 | 适用场景 |
|---------|------|------|---------|
| @Lazy | 代码改动小，保持构造器注入 | 引入代理，轻微性能损耗 | 构造器循环依赖 |
| Setter注入 | Spring原生支持，无代理 | 失去不可变性，依赖不明确 | 可选依赖 |
| 重新设计 | 消除循环依赖，设计更好 | 需要重构代码 | 架构调整阶段 |
| @PostConstruct | 延迟初始化依赖 | 需要额外方法，初始化复杂 | 复杂初始化逻辑 |
| ObjectProvider | 延迟获取，灵活 | 每次获取需要调用方法 | 多次获取不同实例 |

### 推荐方案

```java
// ✅ 优先：重新设计，消除循环依赖
// 引入中间层
@Service
public class UserOrderService {
    @Autowired
    private UserRepository userRepository;
    
    @Autowired
    private OrderRepository orderRepository;
}

// ✅ 次选：使用@Lazy（保持构造器注入）
@Service
public class ServiceA {
    private final ServiceB serviceB;
    
    @Autowired
    public ServiceA(@Lazy ServiceB serviceB) {
        this.serviceB = serviceB;
    }
}

// ⚠️ 可用：Setter注入（失去不可变性）
@Service
public class ServiceA {
    private ServiceB serviceB;
    
    @Autowired
    public void setServiceB(ServiceB serviceB) {
        this.serviceB = serviceB;
    }
}

// ❌ 避免：字段注入（难以测试）
@Service
public class ServiceA {
    @Autowired
    private ServiceB serviceB;
}
```

## 面试总结

### 核心要点

1. **@Lazy可以解决循环依赖**，特别是构造器注入的循环依赖
2. **工作原理**：注入代理对象，延迟获取真实Bean
3. **适用场景**：
   - 构造器注入的循环依赖
   - 重量级Bean的延迟加载
   - 条件性使用的依赖
4. **注意事项**：
   - 引入代理对象
   - 首次调用可能有延迟
   - final方法无法代理

### 常见面试问题

**Q1**: @Lazy注解能解决循环依赖吗？  
**A**: 能。@Lazy会创建代理对象，延迟依赖的解析，从而打破循环依赖的死锁。

**Q2**: @Lazy解决循环依赖的原理是什么？  
**A**: 注入时不立即创建真实Bean，而是注入一个代理对象。首次调用方法时，代理才从容器获取真实Bean。

**Q3**: 使用@Lazy有什么缺点？  
**A**: ① 引入代理对象，有轻微性能损耗；② 首次调用可能有延迟；③ final方法无法代理。

**Q4**: @Lazy和Setter注入解决循环依赖有什么区别？  
**A**: @Lazy保持构造器注入的优点（不可变性、依赖明确），Setter注入失去不可变性但无代理开销。

**Q5**: 所有循环依赖都应该用@Lazy解决吗？  
**A**: 不。最好的方式是重新设计代码，消除循环依赖。@Lazy只是临时解决方案。

