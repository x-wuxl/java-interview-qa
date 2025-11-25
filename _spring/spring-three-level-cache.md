---
title: "Spring三级缓存机制深度解析"
date: 2025-11-02
categories: [Spring框架, IOC]
tags: [Spring, 三级缓存, 循环依赖, 源码分析]
description: "深入剖析Spring三级缓存的设计原理、工作流程以及在解决循环依赖中的关键作用"
nav_order: 455
parent: Spring框架
---
## 核心概念

Spring的**三级缓存**是解决单例Bean循环依赖的核心机制。它通过三个Map结构，在Bean的不同初始化阶段存储Bean对象，从而实现循环依赖的解决。

### 三级缓存定义

在`DefaultSingletonBeanRegistry`类中定义：

```java
public class DefaultSingletonBeanRegistry extends SimpleAliasRegistry implements SingletonBeanRegistry {
    
    /** 一级缓存：成品Bean缓存 */
    private final Map<String, Object> singletonObjects = new ConcurrentHashMap<>(256);
    
    /** 三级缓存：Bean工厂缓存 */
    private final Map<String, ObjectFactory<?>> singletonFactories = new HashMap<>(16);
    
    /** 二级缓存：半成品Bean缓存 */
    private final Map<String, Object> earlySingletonObjects = new ConcurrentHashMap<>(16);
    
    /** 正在创建中的Bean名称集合 */
    private final Set<String> singletonsCurrentlyInCreation = 
        Collections.newSetFromMap(new ConcurrentHashMap<>(16));
}
```

## 三级缓存详解

### 一级缓存：singletonObjects

**存储内容**：完全初始化好的单例Bean（成品）

**特点**：
- 使用`ConcurrentHashMap`，线程安全
- 存储的Bean已经完成：实例化 → 属性填充 → 初始化
- 可以直接使用

**时机**：Bean完全创建完成后放入

```java
// 添加到一级缓存
protected void addSingleton(String beanName, Object singletonObject) {
    synchronized (this.singletonObjects) {
        // 放入一级缓存
        this.singletonObjects.put(beanName, singletonObject);
        // 从三级缓存移除
        this.singletonFactories.remove(beanName);
        // 从二级缓存移除
        this.earlySingletonObjects.remove(beanName);
        // 记录已注册的单例Bean
        this.registeredSingletons.add(beanName);
    }
}
```

### 二级缓存：earlySingletonObjects

**存储内容**：早期的单例Bean引用（半成品）

**特点**：
- 使用`ConcurrentHashMap`，线程安全
- 存储的Bean已实例化，但未完成属性填充和初始化
- 如果需要代理，存储的是代理对象

**时机**：当发生循环依赖，从三级缓存的工厂获取Bean后放入

**作用**：
1. 缓存早期Bean引用，避免重复调用三级缓存的工厂
2. 提高性能（工厂方法可能涉及AOP等复杂逻辑）

```java
// 从三级缓存升级到二级缓存
ObjectFactory<?> singletonFactory = this.singletonFactories.get(beanName);
if (singletonFactory != null) {
    // 调用工厂获取Bean（可能创建代理）
    singletonObject = singletonFactory.getObject();
    // 放入二级缓存
    this.earlySingletonObjects.put(beanName, singletonObject);
    // 从三级缓存移除
    this.singletonFactories.remove(beanName);
}
```

### 三级缓存：singletonFactories

**存储内容**：创建Bean的工厂对象（ObjectFactory）

**特点**：
- 使用`HashMap`，非线程安全（通过锁保证安全）
- 存储的是Lambda表达式或工厂对象
- 只在需要时才调用（延迟执行）

**时机**：Bean实例化后，属性填充前放入

**作用**：
1. 延迟创建Bean的早期引用
2. 处理AOP代理对象的创建时机
3. 只有在发生循环依赖时才调用

```java
// 添加到三级缓存
protected void addSingletonFactory(String beanName, ObjectFactory<?> singletonFactory) {
    Assert.notNull(singletonFactory, "Singleton factory must not be null");
    synchronized (this.singletonObjects) {
        if (!this.singletonObjects.containsKey(beanName)) {
            // 放入三级缓存
            this.singletonFactories.put(beanName, singletonFactory);
            // 从二级缓存移除
            this.earlySingletonObjects.remove(beanName);
            // 记录已注册的Bean
            this.registeredSingletons.add(beanName);
        }
    }
}
```

## 三级缓存工作流程

### 完整流程图

```
[开始创建Bean A]
      ↓
1. 实例化A（调用构造器）
      ↓
2. 将A的ObjectFactory放入三级缓存
      ↓
3. 填充A的属性，发现依赖B
      ↓
[开始创建Bean B]
      ↓
4. 实例化B
      ↓
5. 将B的ObjectFactory放入三级缓存
      ↓
6. 填充B的属性，发现依赖A
      ↓
7. 查找A：一级缓存❌ → 二级缓存❌ → 三级缓存✅
      ↓
8. 从三级缓存获取A的工厂，调用工厂获取A的早期引用
      ↓
9. 将A的早期引用放入二级缓存，从三级缓存移除A
      ↓
10. B注入A的早期引用
      ↓
11. B完成初始化，放入一级缓存，从三级缓存移除B
      ↓
12. A注入B
      ↓
13. A完成初始化，放入一级缓存，从二级缓存移除A
      ↓
[完成]
```

### 源码分析

#### 1. 获取单例Bean

```java
// DefaultSingletonBeanRegistry.getSingleton()
@Nullable
protected Object getSingleton(String beanName, boolean allowEarlyReference) {
    // 快速检查：从一级缓存获取（无锁）
    Object singletonObject = this.singletonObjects.get(beanName);
    
    // 一级缓存没有，且Bean正在创建中
    if (singletonObject == null && isSingletonCurrentlyInCreation(beanName)) {
        // 从二级缓存获取
        singletonObject = this.earlySingletonObjects.get(beanName);
        
        // 二级缓存也没有，且允许早期引用
        if (singletonObject == null && allowEarlyReference) {
            // 加锁，防止并发问题
            synchronized (this.singletonObjects) {
                // 双重检查
                singletonObject = this.singletonObjects.get(beanName);
                if (singletonObject == null) {
                    singletonObject = this.earlySingletonObjects.get(beanName);
                    if (singletonObject == null) {
                        // 从三级缓存获取工厂
                        ObjectFactory<?> singletonFactory = this.singletonFactories.get(beanName);
                        if (singletonFactory != null) {
                            // 调用工厂创建Bean（关键步骤）
                            singletonObject = singletonFactory.getObject();
                            // 升级到二级缓存
                            this.earlySingletonObjects.put(beanName, singletonObject);
                            // 从三级缓存移除
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

#### 2. 创建Bean并添加到三级缓存

```java
// AbstractAutowireCapableBeanFactory.doCreateBean()
protected Object doCreateBean(String beanName, RootBeanDefinition mbd, @Nullable Object[] args) {
    
    // 1. 实例化Bean
    BeanWrapper instanceWrapper = null;
    if (mbd.isSingleton()) {
        instanceWrapper = this.factoryBeanInstanceCache.remove(beanName);
    }
    if (instanceWrapper == null) {
        instanceWrapper = createBeanInstance(beanName, mbd, args);
    }
    
    Object bean = instanceWrapper.getWrappedInstance();
    Class<?> beanType = instanceWrapper.getWrappedClass();
    
    // 2. 判断是否允许提前暴露
    boolean earlySingletonExposure = (mbd.isSingleton() && 
                                      this.allowCircularReferences &&
                                      isSingletonCurrentlyInCreation(beanName));
    
    if (earlySingletonExposure) {
        // 3. 添加到三级缓存（Lambda表达式）
        addSingletonFactory(beanName, () -> getEarlyBeanReference(beanName, mbd, bean));
    }
    
    // 4. 属性填充（可能触发循环依赖）
    Object exposedObject = bean;
    try {
        populateBean(beanName, mbd, instanceWrapper);
        // 5. 初始化Bean
        exposedObject = initializeBean(beanName, exposedObject, mbd);
    }
    catch (Throwable ex) {
        // ...
    }
    
    // 6. 检查循环依赖
    if (earlySingletonExposure) {
        Object earlySingletonReference = getSingleton(beanName, false);
        if (earlySingletonReference != null) {
            if (exposedObject == bean) {
                exposedObject = earlySingletonReference;
            }
        }
    }
    
    return exposedObject;
}
```

#### 3. 获取早期Bean引用（处理AOP）

```java
// AbstractAutowireCapableBeanFactory.getEarlyBeanReference()
protected Object getEarlyBeanReference(String beanName, RootBeanDefinition mbd, Object bean) {
    Object exposedObject = bean;
    
    // 如果有InstantiationAwareBeanPostProcessor
    if (!mbd.isSynthetic() && hasInstantiationAwareBeanPostProcessors()) {
        for (SmartInstantiationAwareBeanPostProcessor bp : getBeanPostProcessorCache().smartInstantiationAware) {
            // 调用后置处理器（AOP在这里创建代理）
            exposedObject = bp.getEarlyBeanReference(exposedObject, beanName);
        }
    }
    
    return exposedObject;
}
```

**关键点**：如果Bean需要AOP代理，`AbstractAutoProxyCreator`会在这里创建代理对象。

## 为什么需要三级缓存？

### 问题：二级缓存不够吗？

理论上，解决循环依赖只需要二级缓存：
- **一级缓存**：完整Bean
- **二级缓存**：半成品Bean

但为什么需要三级缓存呢？

### 答案：为了处理AOP代理

**核心问题**：如果Bean需要被AOP代理，什么时候创建代理对象？

#### 场景1：没有循环依赖

```java
@Service
public class UserService {
    @Autowired
    private UserRepository userRepository;
    
    @Transactional  // 需要AOP代理
    public void saveUser(User user) {
        // ...
    }
}
```

**流程**：
```
1. 实例化UserService
2. 属性填充
3. 初始化
4. 后置处理器创建AOP代理 ← 正常在这里创建代理
5. 返回代理对象
```

#### 场景2：有循环依赖

```java
@Service
public class ServiceA {
    @Autowired
    private ServiceB serviceB;
    
    @Transactional  // 需要AOP代理
    public void methodA() { }
}

@Service
public class ServiceB {
    @Autowired
    private ServiceA serviceA;  // 循环依赖
}
```

**问题**：ServiceB需要注入ServiceA，但ServiceA还未完成初始化，无法走到后置处理器创建代理的步骤。

**解决**：通过三级缓存存储工厂，在需要时提前创建代理对象。

```
1. 实例化ServiceA
2. 将ServiceA的工厂放入三级缓存（工厂能创建代理）
3. 填充ServiceA属性，发现依赖ServiceB
4. 创建ServiceB
5. 填充ServiceB属性，发现依赖ServiceA
6. 从三级缓存获取ServiceA的工厂
7. 调用工厂，提前创建ServiceA的代理对象 ← 关键
8. ServiceB注入ServiceA的代理
9. ServiceB完成创建
10. ServiceA注入ServiceB
11. ServiceA完成创建（使用已创建的代理）
```

### 三级缓存的价值

```java
// 如果没有三级缓存，只能存储原始Bean
Map<String, Object> earlySingletonObjects; // 存储原始Bean

// 问题：ServiceB注入的是原始Bean，但最终需要的是代理Bean
// 会导致：ServiceB中的ServiceA != 容器中的ServiceA代理对象

// 有三级缓存，存储工厂
Map<String, ObjectFactory<?>> singletonFactories;

// 工厂可以根据情况决定返回原始Bean还是代理Bean
ObjectFactory<ServiceA> factory = () -> {
    if (needsProxy(serviceA)) {
        return createProxy(serviceA);  // 返回代理
    }
    return serviceA;  // 返回原始Bean
};
```

## 为什么不能解决构造器循环依赖

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
```

**原因**：
1. 三级缓存的前提是Bean已经实例化（调用构造器完成）
2. 构造器注入时，Bean还未实例化
3. 无法提前暴露Bean引用
4. 形成死锁

**流程分析**：
```
1. 开始创建ServiceA
2. 调用ServiceA构造器 ← 需要ServiceB
3. 开始创建ServiceB
4. 调用ServiceB构造器 ← 需要ServiceA
5. 回到步骤2，死锁 ❌
```

## 为什么不能解决prototype循环依赖

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
```

**原因**：
1. prototype作用域每次都创建新实例
2. Spring不会缓存prototype的Bean
3. 无法使用三级缓存机制
4. 会无限递归创建

**源码检测**：
```java
// AbstractBeanFactory.doGetBean()
if (isPrototypeCurrentlyInCreation(beanName)) {
    // 检测到prototype循环依赖，直接抛异常
    throw new BeanCurrentlyInCreationException(beanName);
}
```

## 实战示例

### 示例1：正常的循环依赖解决

```java
@Service
public class OrderService {
    @Autowired
    private PaymentService paymentService;
    
    public void createOrder() {
        System.out.println("OrderService.createOrder");
        paymentService.pay();
    }
}

@Service
public class PaymentService {
    @Autowired
    private OrderService orderService;
    
    public void pay() {
        System.out.println("PaymentService.pay");
    }
}

// 测试
@SpringBootTest
public class CircularDependencyTest {
    @Autowired
    private OrderService orderService;
    
    @Test
    public void test() {
        orderService.createOrder();
        // 输出：
        // OrderService.createOrder
        // PaymentService.pay
    }
}
```

**流程跟踪**：
```
1. getBean(OrderService)
   - 一级缓存：无
   - 创建OrderService
   - 实例化完成
   - 放入三级缓存
   - 填充属性：需要PaymentService

2. getBean(PaymentService)
   - 一级缓存：无
   - 创建PaymentService
   - 实例化完成
   - 放入三级缓存
   - 填充属性：需要OrderService

3. getBean(OrderService) [循环依赖]
   - 一级缓存：无
   - 二级缓存：无
   - 三级缓存：有（工厂）
   - 调用工厂获取OrderService早期引用
   - 放入二级缓存
   - 返回给PaymentService

4. PaymentService完成初始化
   - 放入一级缓存

5. OrderService完成初始化
   - 从二级缓存移除
   - 放入一级缓存
```

### 示例2：带AOP的循环依赖

```java
@Service
public class ServiceA {
    @Autowired
    private ServiceB serviceB;
    
    @Transactional  // 需要AOP代理
    public void methodA() {
        System.out.println("ServiceA.methodA");
    }
}

@Service
public class ServiceB {
    @Autowired
    private ServiceA serviceA;
    
    public void methodB() {
        System.out.println("ServiceB.methodB");
        serviceA.methodA();
    }
}

// 测试
@SpringBootTest
public class AopCircularDependencyTest {
    @Autowired
    private ServiceB serviceB;
    
    @Test
    public void test() {
        serviceB.methodB();
        // ServiceB注入的是ServiceA的代理对象
    }
}
```

**关键点**：
1. 从三级缓存获取ServiceA时，会调用`getEarlyBeanReference`
2. `AbstractAutoProxyCreator`检测到需要代理，提前创建代理对象
3. ServiceB注入的是ServiceA的代理对象
4. 最终容器中的ServiceA也是同一个代理对象

## 性能考量

### 缓存查找性能

```java
// 性能分析
// 1. 一级缓存查找：O(1)，最快
Object bean = singletonObjects.get(beanName);

// 2. 二级缓存查找：O(1)，很快
if (bean == null && isSingletonCurrentlyInCreation(beanName)) {
    bean = earlySingletonObjects.get(beanName);
}

// 3. 三级缓存查找：O(1) + 工厂调用，稍慢
if (bean == null) {
    ObjectFactory<?> factory = singletonFactories.get(beanName);
    if (factory != null) {
        bean = factory.getObject();  // 可能涉及AOP等复杂操作
    }
}
```

### 优化建议

1. **避免循环依赖**：最好的优化是不产生循环依赖
2. **使用构造器注入**：强制暴露循环依赖问题，促使重构
3. **合理使用@Lazy**：延迟加载，减少启动时的循环依赖

## 面试总结

### 核心要点

1. **三级缓存定义**：
   - 一级：singletonObjects（完整Bean）
   - 二级：earlySingletonObjects（早期Bean）
   - 三级：singletonFactories（Bean工厂）

2. **为什么需要三级缓存**：
   - 二级缓存可以解决普通循环依赖
   - 三级缓存是为了处理AOP代理的循环依赖
   - 需要在Bean未完全初始化时提前创建代理对象

3. **工作流程**：
   - 实例化后放入三级缓存
   - 发生循环依赖时从三级缓存获取工厂
   - 调用工厂得到早期引用，放入二级缓存
   - 完全初始化后放入一级缓存

4. **限制**：
   - 只能解决单例Bean的循环依赖
   - 不能解决构造器注入的循环依赖
   - 不能解决prototype的循环依赖

### 常见面试问题

**Q1**: 什么是Spring的三级缓存？  
**A**: 三个Map：singletonObjects（完整Bean）、earlySingletonObjects（早期Bean）、singletonFactories（Bean工厂）。

**Q2**: 为什么需要三级缓存，二级不够吗？  
**A**: 二级缓存可以解决普通循环依赖，但无法处理AOP代理的情况。三级缓存存储工厂，可以在需要时提前创建代理对象。

**Q3**: 三级缓存的查找顺序是什么？  
**A**: 一级缓存 → 二级缓存 → 三级缓存（调用工厂）→ 升级到二级缓存。

**Q4**: 什么时候Bean会被放入三级缓存？  
**A**: Bean实例化后、属性填充前，会将Bean的工厂对象放入三级缓存。

**Q5**: 如果没有循环依赖，还会用到三级缓存吗？  
**A**: 会放入三级缓存，但不会从三级缓存获取。Bean会直接完成初始化并放入一级缓存。

