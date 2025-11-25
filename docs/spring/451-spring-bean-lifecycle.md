---
layout: default
title: "SpringBean的生命周期详解"
parent: Spring框架
nav_order: 451
description: "全面解析Spring Bean从创建到销毁的完整生命周期，包括关键扩展点和源码分析"
date: 2025-11-02
---
## 核心概念

Spring Bean的生命周期指的是Bean从创建、初始化、使用到销毁的完整过程。理解Bean生命周期对于掌握Spring容器的运作机制、实现自定义扩展至关重要。

Spring容器通过一系列回调接口和扩展点，允许开发者在Bean生命周期的关键节点介入，实现自定义逻辑。

## Bean生命周期完整流程

### 生命周期阶段图

```
1. 实例化（Instantiation）
   ↓
2. 属性赋值（Populate Properties）
   ↓
3. Aware接口回调
   ↓
4. 初始化前置处理（BeanPostProcessor.postProcessBeforeInitialization）
   ↓
5. 初始化（Initialization）
   ↓
6. 初始化后置处理（BeanPostProcessor.postProcessAfterInitialization）
   ↓
7. 使用Bean
   ↓
8. 销毁（Destruction）
```

### 详细步骤说明

#### 1. 实例化阶段

```java
// Spring通过反射调用构造器创建Bean实例
// AbstractAutowireCapableBeanFactory.createBeanInstance()
Object bean = constructor.newInstance(args);
```

#### 2. 属性赋值阶段

```java
// 依赖注入，填充属性
// AbstractAutowireCapableBeanFactory.populateBean()
@Autowired
private UserRepository userRepository;  // 此时被注入
```

#### 3. Aware接口回调阶段

Spring容器会检测Bean是否实现了各种Aware接口，并注入相应的资源：

```java
public class MyBean implements BeanNameAware, BeanFactoryAware, 
                               ApplicationContextAware {
    
    private String beanName;
    private BeanFactory beanFactory;
    private ApplicationContext applicationContext;
    
    // 1. 注入Bean名称
    @Override
    public void setBeanName(String name) {
        this.beanName = name;
        System.out.println("BeanNameAware: " + name);
    }
    
    // 2. 注入BeanFactory
    @Override
    public void setBeanFactory(BeanFactory beanFactory) {
        this.beanFactory = beanFactory;
        System.out.println("BeanFactoryAware");
    }
    
    // 3. 注入ApplicationContext
    @Override
    public void setApplicationContext(ApplicationContext context) {
        this.applicationContext = context;
        System.out.println("ApplicationContextAware");
    }
}
```

常见的Aware接口：
- `BeanNameAware`：获取Bean在容器中的名称
- `BeanFactoryAware`：获取BeanFactory
- `ApplicationContextAware`：获取ApplicationContext
- `EnvironmentAware`：获取环境变量
- `ResourceLoaderAware`：获取资源加载器

#### 4. 初始化前置处理

```java
// BeanPostProcessor接口 - 所有Bean都会经过
public class MyBeanPostProcessor implements BeanPostProcessor {
    
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) {
        System.out.println("初始化前置处理: " + beanName);
        // 可以返回原始bean或包装后的bean
        return bean;
    }
}
```

#### 5. 初始化阶段

Spring提供三种初始化方法，执行顺序如下：

```java
public class UserService implements InitializingBean {
    
    // 方式1: @PostConstruct注解（最先执行）
    @PostConstruct
    public void postConstruct() {
        System.out.println("1. @PostConstruct执行");
    }
    
    // 方式2: InitializingBean接口（第二执行）
    @Override
    public void afterPropertiesSet() {
        System.out.println("2. afterPropertiesSet执行");
    }
    
    // 方式3: 自定义init-method（最后执行）
    public void customInit() {
        System.out.println("3. customInit执行");
    }
}

// 配置init-method
@Bean(initMethod = "customInit")
public UserService userService() {
    return new UserService();
}
```

#### 6. 初始化后置处理

```java
public class MyBeanPostProcessor implements BeanPostProcessor {
    
    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        System.out.println("初始化后置处理: " + beanName);
        
        // AOP代理对象在这里创建
        if (needProxy(bean)) {
            return createProxy(bean);
        }
        return bean;
    }
}
```

**关键点**：AOP代理对象通常在这个阶段由`AbstractAutoProxyCreator`创建。

#### 7. 使用Bean

Bean完全初始化完成，可以正常使用。

#### 8. 销毁阶段

容器关闭时，Spring会调用Bean的销毁方法：

```java
public class UserService implements DisposableBean {
    
    // 方式1: @PreDestroy注解（最先执行）
    @PreDestroy
    public void preDestroy() {
        System.out.println("1. @PreDestroy执行");
    }
    
    // 方式2: DisposableBean接口（第二执行）
    @Override
    public void destroy() {
        System.out.println("2. destroy执行");
    }
    
    // 方式3: 自定义destroy-method（最后执行）
    public void customDestroy() {
        System.out.println("3. customDestroy执行");
    }
}

// 配置destroy-method
@Bean(destroyMethod = "customDestroy")
public UserService userService() {
    return new UserService();
}
```

## 源码关键点

### 核心方法调用链

```java
// AbstractApplicationContext.refresh()
public void refresh() {
    // ...
    finishBeanFactoryInitialization(beanFactory);  // 初始化所有单例Bean
}

// AbstractAutowireCapableBeanFactory.doCreateBean()
protected Object doCreateBean(String beanName, RootBeanDefinition mbd, Object[] args) {
    // 1. 实例化
    instanceWrapper = createBeanInstance(beanName, mbd, args);
    
    // 2. 属性填充
    populateBean(beanName, mbd, instanceWrapper);
    
    // 3. 初始化
    exposedObject = initializeBean(beanName, exposedObject, mbd);
    
    return exposedObject;
}

// AbstractAutowireCapableBeanFactory.initializeBean()
protected Object initializeBean(String beanName, Object bean, RootBeanDefinition mbd) {
    // 3.1 Aware接口回调
    invokeAwareMethods(beanName, bean);
    
    // 3.2 初始化前置处理
    wrappedBean = applyBeanPostProcessorsBeforeInitialization(wrappedBean, beanName);
    
    // 3.3 初始化方法
    invokeInitMethods(beanName, wrappedBean, mbd);
    
    // 3.4 初始化后置处理（AOP）
    wrappedBean = applyBeanPostProcessorsAfterInitialization(wrappedBean, beanName);
    
    return wrappedBean;
}
```

## 实战示例

### 完整生命周期演示

```java
@Component
public class LifecycleBean implements BeanNameAware, ApplicationContextAware,
                                     InitializingBean, DisposableBean {
    
    private String beanName;
    private ApplicationContext applicationContext;
    
    public LifecycleBean() {
        System.out.println("1. 构造器执行");
    }
    
    @Autowired
    public void setDependency(Dependency dependency) {
        System.out.println("2. 属性注入");
    }
    
    @Override
    public void setBeanName(String name) {
        this.beanName = name;
        System.out.println("3. BeanNameAware: " + name);
    }
    
    @Override
    public void setApplicationContext(ApplicationContext context) {
        this.applicationContext = context;
        System.out.println("4. ApplicationContextAware");
    }
    
    @PostConstruct
    public void postConstruct() {
        System.out.println("6. @PostConstruct");
    }
    
    @Override
    public void afterPropertiesSet() {
        System.out.println("7. afterPropertiesSet");
    }
    
    @Bean(initMethod = "customInit")
    public void customInit() {
        System.out.println("8. customInit");
    }
    
    @PreDestroy
    public void preDestroy() {
        System.out.println("10. @PreDestroy");
    }
    
    @Override
    public void destroy() {
        System.out.println("11. destroy");
    }
}

// 自定义BeanPostProcessor
@Component
public class MyBeanPostProcessor implements BeanPostProcessor {
    
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) {
        if (bean instanceof LifecycleBean) {
            System.out.println("5. postProcessBeforeInitialization");
        }
        return bean;
    }
    
    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        if (bean instanceof LifecycleBean) {
            System.out.println("9. postProcessAfterInitialization");
        }
        return bean;
    }
}
```

### 输出结果

```
1. 构造器执行
2. 属性注入
3. BeanNameAware: lifecycleBean
4. ApplicationContextAware
5. postProcessBeforeInitialization
6. @PostConstruct
7. afterPropertiesSet
8. customInit
9. postProcessAfterInitialization
Bean使用中...
10. @PreDestroy
11. destroy
```

## 面试总结

### 关键点记忆

1. **四个主要阶段**：实例化 → 属性填充 → 初始化 → 销毁
2. **扩展点**：BeanPostProcessor是最强大的扩展点，AOP就是在此实现
3. **初始化顺序**：@PostConstruct → afterPropertiesSet → init-method
4. **销毁顺序**：@PreDestroy → destroy → destroy-method
5. **Aware接口**：用于获取Spring容器资源

### 常见应用场景

- **数据库连接池初始化**：在初始化方法中建立连接
- **缓存预热**：在初始化后置处理中加载缓存数据
- **AOP代理创建**：在初始化后置处理中创建代理对象
- **资源清理**：在销毁方法中关闭连接、释放资源

