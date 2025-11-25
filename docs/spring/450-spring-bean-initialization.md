---
layout: default
title: "SpringBean的初始化过程详解"
parent: Spring框架
nav_order: 450
description: "深入解析Spring Bean从实例化到完全初始化的全过程，包括源码级别的分析"
date: 2025-11-02
---
## 核心概念

Spring Bean的**初始化过程**是指Bean从创建实例到可以使用的完整流程。需要区分两个概念：

- **实例化（Instantiation）**：通过反射调用构造器创建Bean对象
- **初始化（Initialization）**：对Bean对象进行属性填充、依赖注入、执行初始化回调等操作

完整的Bean初始化过程包含多个阶段，每个阶段都有特定的作用和扩展点。

## 初始化流程详解

### 整体流程图

```
Bean定义加载
   ↓
实例化前处理（InstantiationAwareBeanPostProcessor.postProcessBeforeInstantiation）
   ↓
实例化Bean（调用构造器）
   ↓
实例化后处理（InstantiationAwareBeanPostProcessor.postProcessAfterInstantiation）
   ↓
属性赋值前处理（InstantiationAwareBeanPostProcessor.postProcessProperties）
   ↓
属性填充（依赖注入）
   ↓
Aware接口回调
   ↓
初始化前处理（BeanPostProcessor.postProcessBeforeInitialization）
   ↓
初始化方法执行
   ↓
初始化后处理（BeanPostProcessor.postProcessAfterInitialization）
   ↓
Bean就绪
```

### 源码级别分析

#### 1. 入口方法

```java
// AbstractApplicationContext.refresh()
@Override
public void refresh() throws BeansException, IllegalStateException {
    synchronized (this.startupShutdownMonitor) {
        // ...
        
        // 完成BeanFactory的初始化，实例化所有单例Bean
        finishBeanFactoryInitialization(beanFactory);
        
        // ...
    }
}

// 初始化所有非懒加载的单例Bean
protected void finishBeanFactoryInitialization(ConfigurableListableBeanFactory beanFactory) {
    // ...
    
    // 实例化所有剩余的单例Bean
    beanFactory.preInstantiateSingletons();
}
```

#### 2. Bean创建核心方法

```java
// AbstractAutowireCapableBeanFactory.doCreateBean()
protected Object doCreateBean(String beanName, RootBeanDefinition mbd, Object[] args) {
    
    BeanWrapper instanceWrapper = null;
    
    // 【步骤1】实例化Bean
    if (instanceWrapper == null) {
        instanceWrapper = createBeanInstance(beanName, mbd, args);
    }
    Object bean = instanceWrapper.getWrappedInstance();
    
    // 【步骤2】允许后置处理器修改BeanDefinition
    synchronized (mbd.postProcessingLock) {
        if (!mbd.postProcessed) {
            applyMergedBeanDefinitionPostProcessors(mbd, beanType, beanName);
            mbd.postProcessed = true;
        }
    }
    
    // 【步骤3】提前暴露单例工厂，解决循环依赖
    boolean earlySingletonExposure = (mbd.isSingleton() && 
                                      this.allowCircularReferences &&
                                      isSingletonCurrentlyInCreation(beanName));
    if (earlySingletonExposure) {
        addSingletonFactory(beanName, () -> getEarlyBeanReference(beanName, mbd, bean));
    }
    
    // 【步骤4】属性填充
    Object exposedObject = bean;
    populateBean(beanName, mbd, instanceWrapper);
    
    // 【步骤5】初始化Bean
    exposedObject = initializeBean(beanName, exposedObject, mbd);
    
    return exposedObject;
}
```

### 关键步骤详解

#### 步骤1：实例化Bean（createBeanInstance）

```java
protected BeanWrapper createBeanInstance(String beanName, RootBeanDefinition mbd, Object[] args) {
    
    // 解析Bean的Class类型
    Class<?> beanClass = resolveBeanClass(mbd, beanName);
    
    // 使用工厂方法实例化
    if (mbd.getFactoryMethodName() != null) {
        return instantiateUsingFactoryMethod(beanName, mbd, args);
    }
    
    // 使用构造器自动装配
    Constructor<?>[] ctors = determineConstructorsFromBeanPostProcessors(beanClass, beanName);
    if (ctors != null) {
        return autowireConstructor(beanName, mbd, ctors, args);
    }
    
    // 使用默认构造器实例化
    return instantiateBean(beanName, mbd);
}

// 最终通过反射创建实例
protected Object instantiateBean(String beanName, RootBeanDefinition mbd) {
    // 使用CGLIB或反射实例化
    return getInstantiationStrategy().instantiate(mbd, beanName, this);
}
```

**实例化策略**：
- 默认使用`CglibSubclassingInstantiationStrategy`
- 通过反射调用构造器：`Constructor.newInstance()`

#### 步骤2：属性填充（populateBean）

```java
protected void populateBean(String beanName, RootBeanDefinition mbd, BeanWrapper bw) {
    
    // 给InstantiationAwareBeanPostProcessor机会在属性注入前修改Bean
    for (InstantiationAwareBeanPostProcessor bp : getBeanPostProcessorCache().instantiationAware) {
        if (!bp.postProcessAfterInstantiation(bw.getWrappedInstance(), beanName)) {
            return;
        }
    }
    
    PropertyValues pvs = mbd.getPropertyValues();
    
    // 自动装配模式（byName、byType）
    int resolvedAutowireMode = mbd.getResolvedAutowireMode();
    if (resolvedAutowireMode == AUTOWIRE_BY_NAME) {
        autowireByName(beanName, mbd, bw, newPvs);
    }
    if (resolvedAutowireMode == AUTOWIRE_BY_TYPE) {
        autowireByType(beanName, mbd, bw, newPvs);
    }
    
    // 应用后置处理器（处理@Autowired、@Value等注解）
    for (InstantiationAwareBeanPostProcessor bp : getBeanPostProcessorCache().instantiationAware) {
        PropertyValues pvsToUse = bp.postProcessProperties(pvs, bw.getWrappedInstance(), beanName);
    }
    
    // 应用属性值
    if (pvs != null) {
        applyPropertyValues(beanName, mbd, bw, pvs);
    }
}
```

**关键后置处理器**：
- `AutowiredAnnotationBeanPostProcessor`：处理`@Autowired`、`@Value`注解
- `CommonAnnotationBeanPostProcessor`：处理`@Resource`注解

#### 步骤3：初始化Bean（initializeBean）

```java
protected Object initializeBean(String beanName, Object bean, RootBeanDefinition mbd) {
    
    // 【1】调用Aware接口方法
    invokeAwareMethods(beanName, bean);
    
    Object wrappedBean = bean;
    
    // 【2】初始化前置处理
    if (mbd == null || !mbd.isSynthetic()) {
        wrappedBean = applyBeanPostProcessorsBeforeInitialization(wrappedBean, beanName);
    }
    
    // 【3】调用初始化方法
    invokeInitMethods(beanName, wrappedBean, mbd);
    
    // 【4】初始化后置处理（AOP代理在这里创建）
    if (mbd == null || !mbd.isSynthetic()) {
        wrappedBean = applyBeanPostProcessorsAfterInitialization(wrappedBean, beanName);
    }
    
    return wrappedBean;
}
```

##### 3.1 Aware接口回调

```java
private void invokeAwareMethods(String beanName, Object bean) {
    if (bean instanceof Aware) {
        if (bean instanceof BeanNameAware) {
            ((BeanNameAware) bean).setBeanName(beanName);
        }
        if (bean instanceof BeanClassLoaderAware) {
            ((BeanClassLoaderAware) bean).setBeanClassLoader(getBeanClassLoader());
        }
        if (bean instanceof BeanFactoryAware) {
            ((BeanFactoryAware) bean).setBeanFactory(this);
        }
    }
}
```

##### 3.2 调用初始化方法

```java
protected void invokeInitMethods(String beanName, Object bean, RootBeanDefinition mbd) {
    
    // 1. 检查是否实现InitializingBean接口
    boolean isInitializingBean = (bean instanceof InitializingBean);
    if (isInitializingBean && (mbd == null || !mbd.isExternallyManagedInitMethod("afterPropertiesSet"))) {
        ((InitializingBean) bean).afterPropertiesSet();
    }
    
    // 2. 调用自定义init-method
    if (mbd != null && bean.getClass() != NullBean.class) {
        String initMethodName = mbd.getInitMethodName();
        if (StringUtils.hasLength(initMethodName) &&
            !(isInitializingBean && "afterPropertiesSet".equals(initMethodName))) {
            invokeCustomInitMethod(beanName, bean, mbd);
        }
    }
}
```

**注意**：`@PostConstruct`注解的方法在`CommonAnnotationBeanPostProcessor.postProcessBeforeInitialization()`中被调用，早于`InitializingBean.afterPropertiesSet()`。

## 关键扩展点

### 1. InstantiationAwareBeanPostProcessor

在实例化前后提供扩展点：

```java
public interface InstantiationAwareBeanPostProcessor extends BeanPostProcessor {
    
    // 实例化前调用，可以返回代理对象
    @Nullable
    default Object postProcessBeforeInstantiation(Class<?> beanClass, String beanName) {
        return null;
    }
    
    // 实例化后调用，返回false可以阻止属性填充
    default boolean postProcessAfterInstantiation(Object bean, String beanName) {
        return true;
    }
    
    // 属性填充前调用，可以修改属性值
    @Nullable
    default PropertyValues postProcessProperties(PropertyValues pvs, Object bean, String beanName) {
        return null;
    }
}
```

### 2. BeanPostProcessor

在初始化前后提供扩展点：

```java
public interface BeanPostProcessor {
    
    // 初始化前调用
    @Nullable
    default Object postProcessBeforeInitialization(Object bean, String beanName) {
        return bean;
    }
    
    // 初始化后调用（AOP代理创建）
    @Nullable
    default Object postProcessAfterInitialization(Object bean, String beanName) {
        return bean;
    }
}
```

## 实战示例

### 完整初始化流程演示

```java
@Component
public class UserService implements BeanNameAware, InitializingBean {
    
    private String beanName;
    
    @Autowired
    private UserRepository userRepository;
    
    // 1. 构造器（实例化阶段）
    public UserService() {
        System.out.println("1. UserService构造器执行");
    }
    
    // 2. 依赖注入（属性填充阶段）
    @Autowired
    public void setUserRepository(UserRepository userRepository) {
        this.userRepository = userRepository;
        System.out.println("2. 依赖注入: userRepository");
    }
    
    // 3. Aware接口回调
    @Override
    public void setBeanName(String name) {
        this.beanName = name;
        System.out.println("3. BeanNameAware.setBeanName: " + name);
    }
    
    // 4. @PostConstruct（初始化前处理中执行）
    @PostConstruct
    public void postConstruct() {
        System.out.println("4. @PostConstruct执行");
    }
    
    // 5. InitializingBean接口
    @Override
    public void afterPropertiesSet() {
        System.out.println("5. afterPropertiesSet执行");
    }
    
    // 6. 自定义init-method
    public void customInit() {
        System.out.println("6. customInit执行");
    }
    
    public void doSomething() {
        System.out.println("7. Bean正常使用");
    }
}

// 配置类
@Configuration
public class AppConfig {
    
    @Bean(initMethod = "customInit")
    public UserService userService() {
        return new UserService();
    }
}

// 自定义后置处理器
@Component
public class CustomBeanPostProcessor implements BeanPostProcessor {
    
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) {
        if (bean instanceof UserService) {
            System.out.println("3.5. 初始化前置处理");
        }
        return bean;
    }
    
    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        if (bean instanceof UserService) {
            System.out.println("6.5. 初始化后置处理");
        }
        return bean;
    }
}
```

### 输出结果

```
1. UserService构造器执行
2. 依赖注入: userRepository
3. BeanNameAware.setBeanName: userService
3.5. 初始化前置处理
4. @PostConstruct执行
5. afterPropertiesSet执行
6. customInit执行
6.5. 初始化后置处理
7. Bean正常使用
```

## 性能优化考量

### 1. 懒加载

```java
@Lazy  // 延迟初始化，首次使用时才创建
@Component
public class HeavyService {
    // 耗时的初始化操作
}
```

### 2. 条件装配

```java
@ConditionalOnProperty(name = "feature.enabled", havingValue = "true")
@Component
public class OptionalService {
    // 根据配置决定是否初始化
}
```

### 3. 原型Bean的创建优化

```java
@Scope("prototype")
@Component
public class PrototypeBean {
    // 每次获取都会执行完整初始化流程，需要注意性能
}
```

## 面试总结

### 核心要点

1. **两个关键概念**：实例化（创建对象）vs 初始化（配置对象）
2. **核心流程**：实例化 → 属性填充 → Aware回调 → 初始化前处理 → 初始化方法 → 初始化后处理
3. **关键方法**：`doCreateBean()` → `createBeanInstance()` → `populateBean()` → `initializeBean()`
4. **初始化顺序**：@PostConstruct → afterPropertiesSet → init-method
5. **扩展点**：BeanPostProcessor（最常用）、InstantiationAwareBeanPostProcessor（更细粒度）

### 常见面试追问

- **Q**: 实例化和初始化的区别？
  - **A**: 实例化是通过反射创建对象；初始化是给对象赋值、注入依赖、执行初始化回调
  
- **Q**: AOP代理在哪个阶段创建？
  - **A**: 初始化后置处理阶段，由`AbstractAutoProxyCreator.postProcessAfterInitialization()`创建

- **Q**: 如何在Bean初始化前后执行自定义逻辑？
  - **A**: 实现`BeanPostProcessor`接口，或使用`@PostConstruct`/`@PreDestroy`注解

