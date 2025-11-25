---
title: "Spring循环依赖问题详解"
date: 2025-11-02
categories: [Spring框架, IOC]
tags: [Spring, 循环依赖, 三级缓存, 依赖注入]
description: "深入解析Spring循环依赖的产生原因、三级缓存解决机制及各种场景下的处理方案"
nav_order: 454
parent: Spring框架
---
## 核心概念

**循环依赖（Circular Dependency）** 是指两个或多个Bean之间相互依赖，形成一个闭环。

### 循环依赖的类型

```java
// 1. 直接循环依赖（A → B → A）
@Service
public class ServiceA {
    @Autowired
    private ServiceB serviceB;
}

@Service
public class ServiceB {
    @Autowired
    private ServiceA serviceA;
}

// 2. 间接循环依赖（A → B → C → A）
@Service
public class ServiceA {
    @Autowired
    private ServiceB serviceB;
}

@Service
public class ServiceB {
    @Autowired
    private ServiceC serviceC;
}

@Service
public class ServiceC {
    @Autowired
    private ServiceA serviceA;
}

// 3. 自我依赖（A → A）
@Service
public class ServiceA {
    @Autowired
    private ServiceA serviceA;  // 自己依赖自己
}
```

## Spring是否支持循环依赖

### 支持的情况

**✅ Spring默认支持单例Bean通过setter注入的循环依赖**

```java
@Service
public class ServiceA {
    @Autowired  // 字段注入（本质是setter）
    private ServiceB serviceB;
}

@Service
public class ServiceB {
    @Autowired  // 字段注入
    private ServiceA serviceA;
}

// ✅ 正常运行，Spring会自动解决
```

### 不支持的情况

**❌ 构造器注入的循环依赖**

```java
@Service
public class ServiceA {
    private final ServiceB serviceB;
    
    @Autowired
    public ServiceA(ServiceB serviceB) {
        this.serviceB = serviceB;
    }
}

@Service
public class ServiceB {
    private final ServiceA serviceA;
    
    @Autowired
    public ServiceB(ServiceA serviceA) {
        this.serviceA = serviceA;
    }
}

// ❌ 报错：BeanCurrentlyInCreationException
```

**❌ prototype作用域的循环依赖**

```java
@Service
@Scope("prototype")
public class ServiceA {
    @Autowired
    private ServiceB serviceB;
}

@Service
@Scope("prototype")
public class ServiceB {
    @Autowired
    private ServiceA serviceA;
}

// ❌ 报错：BeanCurrentlyInCreationException
```

**❌ 单例Bean通过@Async等代理的循环依赖**

```java
@Service
public class ServiceA {
    @Autowired
    private ServiceB serviceB;
}

@Service
public class ServiceB {
    @Autowired
    private ServiceA serviceA;
    
    @Async  // 需要创建代理对象
    public void asyncMethod() {
        // ...
    }
}

// ❌ 可能报错，取决于配置
```

## Spring三级缓存机制

Spring通过**三级缓存**解决单例Bean的循环依赖问题。

### 三级缓存定义

```java
// DefaultSingletonBeanRegistry类中的三个Map

/** 一级缓存：单例对象缓存池，存放完全初始化好的Bean */
private final Map<String, Object> singletonObjects = new ConcurrentHashMap<>(256);

/** 二级缓存：早期单例对象缓存池，存放实例化但未初始化的Bean */
private final Map<String, Object> earlySingletonObjects = new ConcurrentHashMap<>(16);

/** 三级缓存：单例工厂缓存池，存放Bean工厂对象 */
private final Map<String, ObjectFactory<?>> singletonFactories = new HashMap<>(16);
```

### 三级缓存的作用

| 缓存级别 | 名称 | 存储内容 | 作用 |
|---------|------|----------|------|
| 一级缓存 | singletonObjects | 完整的Bean对象 | 存放完全初始化好的单例Bean |
| 二级缓存 | earlySingletonObjects | 早期的Bean对象 | 存放实例化但未完成初始化的Bean |
| 三级缓存 | singletonFactories | Bean工厂 | 存放创建Bean的工厂，用于生成代理对象 |

### 为什么需要三级缓存？

1. **一级缓存**：存放完整Bean，正常情况使用
2. **二级缓存**：存放半成品Bean，解决循环依赖
3. **三级缓存**：解决AOP代理对象的循环依赖问题

**关键点**：如果存在循环依赖且需要创建代理对象，必须在Bean未完全初始化前就创建代理，这时就需要三级缓存。

## 循环依赖解决流程

### 完整解决流程

以ServiceA和ServiceB相互依赖为例：

```
1. 实例化ServiceA（调用构造器）
   ↓
2. 将ServiceA的工厂放入三级缓存
   ↓
3. 填充ServiceA的属性，发现依赖ServiceB
   ↓
4. 开始创建ServiceB（实例化）
   ↓
5. 将ServiceB的工厂放入三级缓存
   ↓
6. 填充ServiceB的属性，发现依赖ServiceA
   ↓
7. 从三级缓存获取ServiceA的工厂
   ↓
8. 调用工厂创建ServiceA的早期引用（可能是代理对象）
   ↓
9. 将ServiceA的早期引用放入二级缓存，从三级缓存移除
   ↓
10. ServiceB完成初始化，放入一级缓存
   ↓
11. ServiceA注入ServiceB，完成初始化，放入一级缓存
```

### 源码分析

#### 1. 获取Bean的核心方法

```java
// AbstractBeanFactory.doGetBean()
protected <T> T doGetBean(String name, Class<T> requiredType, Object[] args, boolean typeCheckOnly) {
    
    String beanName = transformedBeanName(name);
    Object bean;
    
    // 从缓存中获取单例Bean
    Object sharedInstance = getSingleton(beanName);
    if (sharedInstance != null && args == null) {
        bean = getObjectForBeanInstance(sharedInstance, name, beanName, null);
    }
    else {
        // 检查是否正在创建中（解决prototype循环依赖）
        if (isPrototypeCurrentlyInCreation(beanName)) {
            throw new BeanCurrentlyInCreationException(beanName);
        }
        
        // 创建Bean
        if (mbd.isSingleton()) {
            sharedInstance = getSingleton(beanName, () -> {
                return createBean(beanName, mbd, args);
            });
            bean = getObjectForBeanInstance(sharedInstance, name, beanName, mbd);
        }
    }
    
    return (T) bean;
}
```

#### 2. 从三级缓存获取Bean

```java
// DefaultSingletonBeanRegistry.getSingleton()
@Nullable
protected Object getSingleton(String beanName, boolean allowEarlyReference) {
    // 1. 从一级缓存获取
    Object singletonObject = this.singletonObjects.get(beanName);
    
    // 2. 一级缓存没有，且Bean正在创建中
    if (singletonObject == null && isSingletonCurrentlyInCreation(beanName)) {
        // 3. 从二级缓存获取
        singletonObject = this.earlySingletonObjects.get(beanName);
        
        // 4. 二级缓存也没有，且允许早期引用
        if (singletonObject == null && allowEarlyReference) {
            synchronized (this.singletonObjects) {
                singletonObject = this.singletonObjects.get(beanName);
                if (singletonObject == null) {
                    singletonObject = this.earlySingletonObjects.get(beanName);
                    if (singletonObject == null) {
                        // 5. 从三级缓存获取工厂
                        ObjectFactory<?> singletonFactory = this.singletonFactories.get(beanName);
                        if (singletonFactory != null) {
                            // 6. 调用工厂创建Bean（可能是代理对象）
                            singletonObject = singletonFactory.getObject();
                            // 7. 放入二级缓存
                            this.earlySingletonObjects.put(beanName, singletonObject);
                            // 8. 从三级缓存移除
                            this.singletonFactories.remove(beanName);
                        }
                    }
                }
            }
        }
    }
    return singletonObject;
}
```

#### 3. 添加到三级缓存

```java
// AbstractAutowireCapableBeanFactory.doCreateBean()
protected Object doCreateBean(String beanName, RootBeanDefinition mbd, Object[] args) {
    
    // 1. 实例化Bean
    BeanWrapper instanceWrapper = createBeanInstance(beanName, mbd, args);
    Object bean = instanceWrapper.getWrappedInstance();
    
    // 2. 判断是否需要提前暴露（解决循环依赖）
    boolean earlySingletonExposure = (mbd.isSingleton() && 
                                      this.allowCircularReferences &&
                                      isSingletonCurrentlyInCreation(beanName));
    
    if (earlySingletonExposure) {
        // 3. 添加到三级缓存
        addSingletonFactory(beanName, () -> getEarlyBeanReference(beanName, mbd, bean));
    }
    
    // 4. 属性填充（可能触发循环依赖）
    populateBean(beanName, mbd, instanceWrapper);
    
    // 5. 初始化Bean
    Object exposedObject = initializeBean(beanName, bean, mbd);
    
    return exposedObject;
}

// 添加到三级缓存
protected void addSingletonFactory(String beanName, ObjectFactory<?> singletonFactory) {
    synchronized (this.singletonObjects) {
        if (!this.singletonObjects.containsKey(beanName)) {
            this.singletonFactories.put(beanName, singletonFactory);
            this.earlySingletonObjects.remove(beanName);
            this.registeredSingletons.add(beanName);
        }
    }
}
```

#### 4. 获取早期引用（处理AOP）

```java
// AbstractAutowireCapableBeanFactory.getEarlyBeanReference()
protected Object getEarlyBeanReference(String beanName, RootBeanDefinition mbd, Object bean) {
    Object exposedObject = bean;
    
    // 调用所有SmartInstantiationAwareBeanPostProcessor
    if (!mbd.isSynthetic() && hasInstantiationAwareBeanPostProcessors()) {
        for (SmartInstantiationAwareBeanPostProcessor bp : getBeanPostProcessorCache().smartInstantiationAware) {
            // 如果需要AOP代理，这里会返回代理对象
            exposedObject = bp.getEarlyBeanReference(exposedObject, beanName);
        }
    }
    
    return exposedObject;
}
```

## 为什么构造器注入无法解决循环依赖

```java
@Service
public class ServiceA {
    private final ServiceB serviceB;
    
    @Autowired
    public ServiceA(ServiceB serviceB) {  // 构造时就需要ServiceB
        this.serviceB = serviceB;
    }
}

@Service
public class ServiceB {
    private final ServiceA serviceA;
    
    @Autowired
    public ServiceB(ServiceA serviceA) {  // 构造时就需要ServiceA
        this.serviceA = serviceA;
    }
}
```

**原因**：
1. 创建ServiceA需要先创建ServiceB
2. 创建ServiceB需要先创建ServiceA
3. 形成死锁，无法实例化任何一个对象
4. 三级缓存的前提是Bean已经实例化，而构造器注入时Bean还未实例化

**错误信息**：
```
BeanCurrentlyInCreationException: Error creating bean with name 'serviceA': 
Requested bean is currently in creation: Is there an unresolvable circular reference?
```

## 循环依赖解决方案

### 方案1：使用@Lazy注解（推荐）

```java
@Service
public class ServiceA {
    private final ServiceB serviceB;
    
    @Autowired
    public ServiceA(@Lazy ServiceB serviceB) {  // 延迟注入
        this.serviceB = serviceB;
    }
}

@Service
public class ServiceB {
    private final ServiceA serviceA;
    
    @Autowired
    public ServiceB(ServiceA serviceA) {
        this.serviceA = serviceA;
    }
}
```

**原理**：@Lazy会创建一个代理对象，延迟真正的依赖注入。

### 方案2：改用Setter注入

```java
@Service
public class ServiceA {
    private ServiceB serviceB;
    
    @Autowired
    public void setServiceB(ServiceB serviceB) {
        this.serviceB = serviceB;
    }
}

@Service
public class ServiceB {
    private ServiceA serviceA;
    
    @Autowired
    public void setServiceA(ServiceA serviceA) {
        this.serviceA = serviceA;
    }
}
```

**优点**：Spring三级缓存可以解决  
**缺点**：失去了final的不可变性保证

### 方案3：使用@PostConstruct

```java
@Service
public class ServiceA {
    @Autowired
    private ApplicationContext context;
    
    private ServiceB serviceB;
    
    @PostConstruct
    public void init() {
        this.serviceB = context.getBean(ServiceB.class);
    }
}
```

### 方案4：重新设计，消除循环依赖（最佳）

```java
// 引入中间层，打破循环
@Service
public class ServiceA {
    @Autowired
    private CommonService commonService;
}

@Service
public class ServiceB {
    @Autowired
    private CommonService commonService;
}

@Service
public class CommonService {
    // 公共逻辑
}
```

### 方案5：使用ObjectProvider

```java
@Service
public class ServiceA {
    private final ObjectProvider<ServiceB> serviceBProvider;
    
    @Autowired
    public ServiceA(ObjectProvider<ServiceB> serviceBProvider) {
        this.serviceBProvider = serviceBProvider;
    }
    
    public void doSomething() {
        ServiceB serviceB = serviceBProvider.getObject();
        // 使用serviceB
    }
}
```

## 实战案例

### 案例1：检测循环依赖

```java
@Configuration
public class CircularDependencyConfig {
    
    @Bean
    public ServiceA serviceA(ServiceB serviceB) {
        return new ServiceA(serviceB);
    }
    
    @Bean
    public ServiceB serviceB(ServiceA serviceA) {
        return new ServiceB(serviceA);
    }
}

// 启动时报错：
// The dependencies of some of the beans in the application context form a cycle
```

### 案例2：使用@Lazy解决

```java
@Service
public class OrderService {
    private final UserService userService;
    
    @Autowired
    public OrderService(@Lazy UserService userService) {
        this.userService = userService;
    }
    
    public void createOrder(Order order) {
        // 首次使用时才真正注入
        User user = userService.findById(order.getUserId());
        // ...
    }
}

@Service
public class UserService {
    private final OrderService orderService;
    
    @Autowired
    public UserService(OrderService orderService) {
        this.orderService = orderService;
    }
}
```

### 案例3：prototype循环依赖

```java
@Service
@Scope("prototype")
public class PrototypeA {
    @Autowired
    private PrototypeB prototypeB;
}

@Service
@Scope("prototype")
public class PrototypeB {
    @Autowired
    private PrototypeA prototypeA;
}

// 报错：BeanCurrentlyInCreationException

// 解决方案：使用@Lookup方法注入
@Service
@Scope("prototype")
public abstract class PrototypeA {
    
    @Lookup
    protected abstract PrototypeB getPrototypeB();
    
    public void doSomething() {
        PrototypeB b = getPrototypeB();
        // ...
    }
}
```

## 最佳实践

### 1. 优先使用构造器注入

```java
// ✅ 推荐：构造器注入
@Service
public class UserService {
    private final UserRepository userRepository;
    
    @Autowired
    public UserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }
}
```

**优点**：
- 依赖明确，不可变
- 强制依赖（无法创建不完整对象）
- 易于测试

**缺点**：
- 无法处理循环依赖（但这是好事，强制你重新设计）

### 2. 避免循环依赖

循环依赖通常是设计问题的信号，应该重构代码：

```java
// ❌ 坏设计
class UserService {
    @Autowired OrderService orderService;
}

class OrderService {
    @Autowired UserService userService;
}

// ✅ 好设计：引入中间层
class UserService {
    @Autowired UserOrderFacade facade;
}

class OrderService {
    @Autowired UserOrderFacade facade;
}

class UserOrderFacade {
    @Autowired UserRepository userRepository;
    @Autowired OrderRepository orderRepository;
}
```

### 3. 必要时使用@Lazy

```java
@Service
public class ServiceA {
    private final ServiceB serviceB;
    
    @Autowired
    public ServiceA(@Lazy ServiceB serviceB) {
        this.serviceB = serviceB;
    }
}
```

## 面试总结

### 核心要点

1. **Spring默认支持单例setter注入的循环依赖**
2. **通过三级缓存解决循环依赖**：
   - 一级缓存：完整Bean
   - 二级缓存：早期Bean
   - 三级缓存：Bean工厂（用于创建代理）
3. **构造器注入无法解决循环依赖**（Bean未实例化）
4. **prototype作用域无法解决循环依赖**（不缓存）
5. **解决方案**：@Lazy、Setter注入、重新设计

### 常见面试问题

**Q1**: 什么是循环依赖？  
**A**: 两个或多个Bean相互依赖，形成闭环。

**Q2**: Spring如何解决循环依赖？  
**A**: 通过三级缓存：提前暴露未完全初始化的Bean，允许其他Bean引用。

**Q3**: 为什么需要三级缓存，两级不够吗？  
**A**: 两级缓存可以解决普通循环依赖，但无法处理AOP代理的情况。三级缓存存放工厂对象，可以在需要时创建代理对象。

**Q4**: 构造器注入的循环依赖如何解决？  
**A**: 使用@Lazy注解延迟注入，或改用Setter注入，或重新设计消除循环依赖。

**Q5**: Spring能解决所有循环依赖吗？  
**A**: 不能。只能解决单例Bean通过setter/字段注入的循环依赖。构造器注入和prototype作用域无法解决。

