---
layout: default
title: "Spring中的Bean作用域详解"
parent: Spring框架
nav_order: 452
description: "全面解析Spring支持的各种Bean作用域，包括单例、原型、Web作用域等，以及实际应用场景"
date: 2025-11-02
---
## 核心概念

**Bean作用域（Scope）** 定义了Spring容器如何创建和管理Bean实例。不同的作用域决定了Bean的生命周期、实例数量以及共享方式。

Spring支持多种作用域，主要分为两大类：
- **核心容器作用域**：singleton、prototype
- **Web应用作用域**：request、session、application、websocket

## Spring支持的作用域

### 1. singleton（单例）- 默认

**特点**：
- 整个Spring容器中只有一个Bean实例
- 容器启动时创建（非懒加载）
- 所有对该Bean的请求都返回同一个实例
- 容器关闭时销毁

```java
@Component
@Scope("singleton")  // 默认值，可以省略
public class SingletonBean {
    private int counter = 0;
    
    public void increment() {
        counter++;
    }
    
    public int getCounter() {
        return counter;
    }
}

// 测试
ApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
SingletonBean bean1 = context.getBean(SingletonBean.class);
SingletonBean bean2 = context.getBean(SingletonBean.class);

System.out.println(bean1 == bean2);  // true，同一个实例
bean1.increment();
System.out.println(bean2.getCounter());  // 1，共享状态
```

**使用场景**：
- 无状态的Service、DAO层
- 工具类、配置类
- 需要全局共享的对象

**线程安全考量**：
- 单例Bean默认不是线程安全的
- 避免使用可变的成员变量
- 如需共享状态，使用`ThreadLocal`或同步机制

### 2. prototype（原型）

**特点**：
- 每次请求都创建新实例
- 不会缓存
- Spring不负责销毁（不会调用destroy方法）

```java
@Component
@Scope("prototype")
public class PrototypeBean {
    private String id = UUID.randomUUID().toString();
    
    public String getId() {
        return id;
    }
}

// 测试
ApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
PrototypeBean bean1 = context.getBean(PrototypeBean.class);
PrototypeBean bean2 = context.getBean(PrototypeBean.class);

System.out.println(bean1 == bean2);  // false，不同实例
System.out.println(bean1.getId());   // 不同的UUID
System.out.println(bean2.getId());   // 不同的UUID
```

**使用场景**：
- 有状态的Bean
- 需要每次都创建新实例的对象
- 线程不安全但需要多线程使用的对象

**注意事项**：
```java
// ❌ 错误：单例Bean注入原型Bean，原型失效
@Component
public class SingletonService {
    @Autowired
    private PrototypeBean prototypeBean;  // 只会注入一次
}

// ✅ 正确：使用方法注入或ObjectFactory
@Component
public class SingletonService {
    @Autowired
    private ApplicationContext context;
    
    public void doSomething() {
        // 每次都获取新实例
        PrototypeBean bean = context.getBean(PrototypeBean.class);
    }
}

// ✅ 正确：使用ObjectFactory
@Component
public class SingletonService {
    @Autowired
    private ObjectFactory<PrototypeBean> prototypeBeanFactory;
    
    public void doSomething() {
        PrototypeBean bean = prototypeBeanFactory.getObject();
    }
}
```

### 3. request（请求作用域）

**特点**：
- 每个HTTP请求创建一个Bean实例
- 请求结束时销毁
- 仅在Web应用中有效

```java
@Component
@Scope(value = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
public class RequestBean {
    private String requestId = UUID.randomUUID().toString();
    
    public String getRequestId() {
        return requestId;
    }
}

@RestController
public class TestController {
    
    @Autowired
    private RequestBean requestBean;
    
    @GetMapping("/test")
    public String test() {
        // 同一个请求内，requestBean是同一个实例
        return requestBean.getRequestId();
    }
}
```

**proxyMode说明**：
- `TARGET_CLASS`：使用CGLIB代理
- `INTERFACES`：使用JDK动态代理
- 必须使用代理，否则单例Bean无法注入request作用域的Bean

**使用场景**：
- 存储请求级别的数据（用户信息、请求参数等）
- 替代ThreadLocal的场景

### 4. session（会话作用域）

**特点**：
- 每个HTTP Session创建一个Bean实例
- Session销毁时Bean也销毁
- 仅在Web应用中有效

```java
@Component
@Scope(value = WebApplicationContext.SCOPE_SESSION, proxyMode = ScopedProxyMode.TARGET_CLASS)
public class SessionBean {
    private String sessionId = UUID.randomUUID().toString();
    private User currentUser;
    
    public void setCurrentUser(User user) {
        this.currentUser = user;
    }
    
    public User getCurrentUser() {
        return currentUser;
    }
}

@RestController
public class UserController {
    
    @Autowired
    private SessionBean sessionBean;
    
    @PostMapping("/login")
    public String login(@RequestBody User user) {
        sessionBean.setCurrentUser(user);
        return "登录成功";
    }
    
    @GetMapping("/profile")
    public User getProfile() {
        // 同一个会话内，sessionBean是同一个实例
        return sessionBean.getCurrentUser();
    }
}
```

**使用场景**：
- 用户登录状态
- 购物车数据
- 用户个性化设置

### 5. application（应用作用域）

**特点**：
- 每个ServletContext创建一个Bean实例
- 整个Web应用共享
- 类似singleton，但范围是ServletContext

```java
@Component
@Scope(value = WebApplicationContext.SCOPE_APPLICATION, proxyMode = ScopedProxyMode.TARGET_CLASS)
public class ApplicationBean {
    private AtomicInteger visitCount = new AtomicInteger(0);
    
    public int incrementAndGet() {
        return visitCount.incrementAndGet();
    }
}

@RestController
public class StatisticsController {
    
    @Autowired
    private ApplicationBean applicationBean;
    
    @GetMapping("/visit")
    public String visit() {
        int count = applicationBean.incrementAndGet();
        return "总访问次数: " + count;
    }
}
```

**使用场景**：
- 全局配置信息
- 应用级别的缓存
- 统计数据

### 6. websocket（WebSocket作用域）

**特点**：
- 每个WebSocket连接创建一个Bean实例
- WebSocket关闭时销毁
- 需要Spring WebSocket支持

```java
@Component
@Scope(scopeName = "websocket", proxyMode = ScopedProxyMode.TARGET_CLASS)
public class WebSocketBean {
    private String connectionId = UUID.randomUUID().toString();
    
    public String getConnectionId() {
        return connectionId;
    }
}
```

## 作用域对比表

| 作用域 | 实例数量 | 生命周期 | 是否线程安全 | 使用场景 |
|--------|----------|----------|--------------|----------|
| singleton | 1个 | 容器启动到关闭 | 否（需注意） | 无状态Service |
| prototype | 每次创建 | 由调用者管理 | 是（每次新建） | 有状态Bean |
| request | 每请求1个 | 请求开始到结束 | 是（请求隔离） | 请求级数据 |
| session | 每会话1个 | 会话创建到销毁 | 是（会话隔离） | 用户会话数据 |
| application | 1个 | ServletContext生命周期 | 否（需注意） | 应用级共享数据 |
| websocket | 每连接1个 | 连接建立到断开 | 是（连接隔离） | WebSocket数据 |

## 源码分析

### Scope注解定义

```java
@Target({ElementType.TYPE, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface Scope {
    
    @AliasFor("scopeName")
    String value() default "";
    
    @AliasFor("value")
    String scopeName() default "";
    
    // 代理模式
    ScopedProxyMode proxyMode() default ScopedProxyMode.DEFAULT;
}
```

### 作用域管理

```java
// AbstractBeanFactory.doGetBean()
protected <T> T doGetBean(String name, Class<T> requiredType, Object[] args, boolean typeCheckOnly) {
    
    String beanName = transformedBeanName(name);
    Object bean;
    
    // 1. 尝试从单例缓存获取
    Object sharedInstance = getSingleton(beanName);
    if (sharedInstance != null && args == null) {
        bean = getObjectForBeanInstance(sharedInstance, name, beanName, null);
    }
    else {
        // 2. 检查是否是prototype循环依赖
        if (isPrototypeCurrentlyInCreation(beanName)) {
            throw new BeanCurrentlyInCreationException(beanName);
        }
        
        RootBeanDefinition mbd = getMergedLocalBeanDefinition(beanName);
        
        // 3. 根据作用域创建Bean
        if (mbd.isSingleton()) {
            // 单例
            sharedInstance = getSingleton(beanName, () -> {
                return createBean(beanName, mbd, args);
            });
            bean = getObjectForBeanInstance(sharedInstance, name, beanName, mbd);
        }
        else if (mbd.isPrototype()) {
            // 原型
            Object prototypeInstance = createBean(beanName, mbd, args);
            bean = getObjectForBeanInstance(prototypeInstance, name, beanName, mbd);
        }
        else {
            // 自定义作用域（request、session等）
            String scopeName = mbd.getScope();
            Scope scope = this.scopes.get(scopeName);
            Object scopedInstance = scope.get(beanName, () -> {
                return createBean(beanName, mbd, args);
            });
            bean = getObjectForBeanInstance(scopedInstance, name, beanName, mbd);
        }
    }
    
    return (T) bean;
}
```

## 实战示例

### 示例1：单例Bean的线程安全问题

```java
// ❌ 不安全的单例Bean
@Service
public class UnsafeService {
    private int count = 0;  // 共享可变状态
    
    public void increment() {
        count++;  // 非线程安全
    }
}

// ✅ 安全的单例Bean
@Service
public class SafeService {
    private final AtomicInteger count = new AtomicInteger(0);
    
    public void increment() {
        count.incrementAndGet();  // 线程安全
    }
}

// ✅ 使用ThreadLocal
@Service
public class ThreadLocalService {
    private ThreadLocal<Integer> count = ThreadLocal.withInitial(() -> 0);
    
    public void increment() {
        count.set(count.get() + 1);
    }
    
    public int getCount() {
        return count.get();
    }
}
```

### 示例2：原型Bean的正确使用

```java
@Configuration
public class BeanConfig {
    
    // 原型Bean
    @Bean
    @Scope("prototype")
    public PrototypeTask prototypeTask() {
        return new PrototypeTask();
    }
}

@Service
public class TaskService {
    
    @Autowired
    private ApplicationContext context;
    
    public void executeTasks(int count) {
        for (int i = 0; i < count; i++) {
            // 每次获取新实例
            PrototypeTask task = context.getBean(PrototypeTask.class);
            task.execute();
        }
    }
}
```

### 示例3：Web作用域的完整应用

```java
// Request作用域Bean
@Component
@Scope(value = "request", proxyMode = ScopedProxyMode.TARGET_CLASS)
public class RequestContext {
    private String requestId;
    private LocalDateTime requestTime;
    private String userIp;
    
    @PostConstruct
    public void init() {
        this.requestId = UUID.randomUUID().toString();
        this.requestTime = LocalDateTime.now();
    }
    
    // Getters and Setters
}

// Session作用域Bean
@Component
@Scope(value = "session", proxyMode = ScopedProxyMode.TARGET_CLASS)
public class UserSession {
    private User currentUser;
    private List<String> recentPages = new ArrayList<>();
    
    public void addPage(String page) {
        recentPages.add(page);
        if (recentPages.size() > 10) {
            recentPages.remove(0);
        }
    }
    
    // Getters and Setters
}

// Controller使用
@RestController
@RequestMapping("/api")
public class ApiController {
    
    @Autowired
    private RequestContext requestContext;
    
    @Autowired
    private UserSession userSession;
    
    @GetMapping("/info")
    public Map<String, Object> getInfo() {
        userSession.addPage("/api/info");
        
        Map<String, Object> result = new HashMap<>();
        result.put("requestId", requestContext.getRequestId());
        result.put("user", userSession.getCurrentUser());
        result.put("recentPages", userSession.getRecentPages());
        
        return result;
    }
}
```

## 性能与最佳实践

### 1. 作用域选择原则

```java
// 无状态 → singleton
@Service
public class UserService {
    @Autowired
    private UserRepository userRepository;
    
    public User findById(Long id) {
        return userRepository.findById(id);
    }
}

// 有状态 → prototype
@Component
@Scope("prototype")
public class OrderProcessor {
    private Order currentOrder;
    
    public void process(Order order) {
        this.currentOrder = order;
        // 处理逻辑
    }
}
```

### 2. 性能考虑

- **singleton**：性能最好，只创建一次
- **prototype**：每次创建都有开销，避免频繁获取
- **request/session**：需要代理，有轻微性能损耗

### 3. 内存管理

```java
// 注意：原型Bean不会被Spring销毁，需要手动管理
@Component
@Scope("prototype")
public class ResourceBean implements DisposableBean {
    
    private Connection connection;
    
    @Override
    public void destroy() {
        // Spring不会自动调用，需要手动管理
        if (connection != null) {
            connection.close();
        }
    }
}
```

## 面试总结

### 关键要点

1. **默认作用域是singleton**，容器中只有一个实例
2. **prototype每次创建新实例**，Spring不负责销毁
3. **Web作用域需要proxyMode**，才能注入到单例Bean
4. **单例Bean不是线程安全的**，需要注意可变状态
5. **单例注入原型会失效**，需要使用特殊方法

### 常见面试题

**Q1**: 单例Bean是线程安全的吗？  
**A**: 不是。单例Bean在多线程环境下共享，如果有可变状态需要做同步处理。

**Q2**: 如何在单例Bean中正确使用原型Bean？  
**A**: 使用`ApplicationContext.getBean()`、`ObjectFactory`或`@Lookup`注解。

**Q3**: request作用域和ThreadLocal的区别？  
**A**: request作用域由Spring管理生命周期，自动清理；ThreadLocal需要手动清理，容易内存泄漏。

**Q4**: 为什么Web作用域需要代理？  
**A**: 因为单例Bean在容器启动时就创建，而request/session作用域的Bean还不存在，需要通过代理延迟获取。

