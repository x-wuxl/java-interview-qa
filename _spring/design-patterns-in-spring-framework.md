---
title: "Spring框架中用到的设计模式"
date: 2025-11-02
description: "全面解析Spring框架中应用的核心设计模式，包括单例、工厂、代理、模板方法、观察者等模式的实现与应用场景"
author: "wuxl"
categories: [Spring框架]
tags: [Spring, 设计模式, AOP, IoC, 源码分析]
nav_order: 480
parent: Spring框架
---
## 问题

Spring中用到了哪些设计模式？

## 答案

### 1. 核心概念

Spring框架是设计模式的集大成者，通过巧妙运用多种设计模式实现了**IoC（控制反转）**、**AOP（面向切面编程）**等核心特性。掌握这些设计模式有助于深入理解Spring源码和架构设计。

---

### 2. Spring中的核心设计模式

#### 2.1 单例模式（Singleton Pattern）

**应用场景**：Spring Bean默认作用域

**实现方式**：
```java
// Spring通过ConcurrentHashMap缓存单例Bean
public class DefaultSingletonBeanRegistry {
    // 一级缓存：存放完全初始化的单例Bean
    private final Map<String, Object> singletonObjects = new ConcurrentHashMap<>(256);

    public Object getSingleton(String beanName) {
        // 双重检查锁（DCL）保证线程安全
        Object singletonObject = singletonObjects.get(beanName);
        if (singletonObject == null) {
            synchronized (this.singletonObjects) {
                singletonObject = singletonObjects.get(beanName);
                if (singletonObject == null) {
                    singletonObject = createBean(beanName);
                    singletonObjects.put(beanName, singletonObject);
                }
            }
        }
        return singletonObject;
    }
}
```

**优势**：
- 减少对象创建开销
- 全局唯一实例，便于共享资源

**Bean作用域配置**：
```java
// 单例（默认）
@Component
@Scope("singleton")
public class UserService {}

// 原型（每次请求创建新实例）
@Component
@Scope("prototype")
public class OrderService {}
```

---

#### 2.2 工厂模式（Factory Pattern）

**应用场景**：BeanFactory和ApplicationContext创建Bean

**三种工厂模式的应用**：

**简单工厂**：
```java
// BeanFactory接口
public interface BeanFactory {
    Object getBean(String name);
    <T> T getBean(String name, Class<T> requiredType);
}
```

**工厂方法**：
```java
// FactoryBean接口：自定义Bean的创建逻辑
public class CarFactoryBean implements FactoryBean<Car> {
    @Override
    public Car getObject() throws Exception {
        // 复杂的创建逻辑
        Car car = new Car();
        car.setEngine(new Engine());
        car.setWheel(new Wheel());
        return car;
    }

    @Override
    public Class<?> getObjectType() {
        return Car.class;
    }

    @Override
    public boolean isSingleton() {
        return true;
    }
}
```

**抽象工厂**：
```java
// ApplicationContext体系
ApplicationContext context = new ClassPathXmlApplicationContext("beans.xml");
ApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);
ApplicationContext context = new FileSystemXmlApplicationContext("C:/beans.xml");
```

---

#### 2.3 代理模式（Proxy Pattern）

**应用场景**：AOP的核心实现机制

**两种代理实现**：

**JDK动态代理**（基于接口）：
```java
// Spring AOP使用JDK动态代理
public class JdkDynamicAopProxy implements InvocationHandler {
    private final Object target;

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        // 前置增强
        System.out.println("Before method: " + method.getName());

        // 执行目标方法
        Object result = method.invoke(target, args);

        // 后置增强
        System.out.println("After method: " + method.getName());

        return result;
    }
}
```

**CGLIB动态代理**（基于子类）：
```java
// 目标类无接口时，Spring使用CGLIB
public class CglibAopProxy implements MethodInterceptor {
    @Override
    public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy)
            throws Throwable {
        System.out.println("CGLIB Before: " + method.getName());
        Object result = proxy.invokeSuper(obj, args);
        System.out.println("CGLIB After: " + method.getName());
        return result;
    }
}
```

**实际应用**：
```java
@Aspect
@Component
public class LogAspect {
    @Around("execution(* com.example.service.*.*(..))")
    public Object logAround(ProceedingJoinPoint joinPoint) throws Throwable {
        System.out.println("方法执行前");
        Object result = joinPoint.proceed();  // 代理调用目标方法
        System.out.println("方法执行后");
        return result;
    }
}
```

---

#### 2.4 模板方法模式（Template Method Pattern）

**应用场景**：JdbcTemplate、RestTemplate、TransactionTemplate

**核心思想**：定义算法骨架，将某些步骤延迟到子类实现

**JdbcTemplate示例**：
```java
public class JdbcTemplate {
    // 模板方法：定义执行流程
    public <T> T execute(StatementCallback<T> action) {
        Connection con = null;
        Statement stmt = null;
        try {
            // 1. 获取连接
            con = DataSourceUtils.getConnection(dataSource);
            // 2. 创建Statement
            stmt = con.createStatement();
            // 3. 执行回调（变化部分由用户实现）
            T result = action.doInStatement(stmt);
            return result;
        } catch (SQLException ex) {
            // 4. 异常处理
            throw translateException(ex);
        } finally {
            // 5. 释放资源
            JdbcUtils.closeStatement(stmt);
            DataSourceUtils.releaseConnection(con, dataSource);
        }
    }
}
```

**使用示例**：
```java
jdbcTemplate.execute(new StatementCallback<Integer>() {
    @Override
    public Integer doInStatement(Statement stmt) throws SQLException {
        return stmt.executeUpdate("UPDATE user SET name = 'Alice' WHERE id = 1");
    }
});
```

---

#### 2.5 观察者模式（Observer Pattern）

**应用场景**：Spring事件机制（ApplicationEvent和ApplicationListener）

**实现示例**：

**自定义事件**：
```java
// 1. 定义事件
public class OrderCreatedEvent extends ApplicationEvent {
    private Order order;

    public OrderCreatedEvent(Object source, Order order) {
        super(source);
        this.order = order;
    }

    public Order getOrder() {
        return order;
    }
}
```

**事件监听器**：
```java
// 2. 定义监听器
@Component
public class OrderEventListener implements ApplicationListener<OrderCreatedEvent> {
    @Override
    public void onApplicationEvent(OrderCreatedEvent event) {
        Order order = event.getOrder();
        System.out.println("订单创建事件触发：" + order.getId());
        // 发送邮件、扣减库存等操作
    }
}

// 或使用@EventListener注解
@Component
public class AnotherListener {
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        System.out.println("处理订单：" + event.getOrder().getId());
    }
}
```

**发布事件**：
```java
@Service
public class OrderService {
    @Autowired
    private ApplicationEventPublisher publisher;

    public void createOrder(Order order) {
        // 保存订单
        orderRepository.save(order);

        // 发布事件
        publisher.publishEvent(new OrderCreatedEvent(this, order));
    }
}
```

**内置事件**：
- `ContextRefreshedEvent`：容器刷新完成
- `ContextStartedEvent`：容器启动
- `ContextStoppedEvent`：容器停止
- `ContextClosedEvent`：容器关闭

---

#### 2.6 策略模式（Strategy Pattern）

**应用场景**：Resource加载策略、事务传播行为

**Resource加载策略**：
```java
public interface Resource {
    InputStream getInputStream() throws IOException;
}

// 不同的加载策略
public class ClassPathResource implements Resource { }
public class FileSystemResource implements Resource { }
public class UrlResource implements Resource { }

// ResourceLoader根据路径前缀选择策略
public class DefaultResourceLoader {
    public Resource getResource(String location) {
        if (location.startsWith("classpath:")) {
            return new ClassPathResource(location);
        } else if (location.startsWith("file:")) {
            return new FileSystemResource(location);
        } else if (location.startsWith("http:")) {
            return new UrlResource(location);
        }
        return new ClassPathResource(location);
    }
}
```

**实际应用**：
```java
// 业务场景：支付策略
public interface PaymentStrategy {
    void pay(BigDecimal amount);
}

@Component("alipay")
public class AlipayStrategy implements PaymentStrategy {
    public void pay(BigDecimal amount) {
        System.out.println("支付宝支付：" + amount);
    }
}

@Component("wechat")
public class WechatPayStrategy implements PaymentStrategy {
    public void pay(BigDecimal amount) {
        System.out.println("微信支付：" + amount);
    }
}

@Service
public class PaymentService {
    @Autowired
    private Map<String, PaymentStrategy> strategies;  // Spring自动注入所有实现

    public void pay(String type, BigDecimal amount) {
        PaymentStrategy strategy = strategies.get(type);
        strategy.pay(amount);
    }
}
```

---

#### 2.7 适配器模式（Adapter Pattern）

**应用场景**：SpringMVC的HandlerAdapter

**原理**：
```java
// SpringMVC支持多种Controller写法
// 1. 实现Controller接口
public class OldStyleController implements Controller {
    @Override
    public ModelAndView handleRequest(HttpServletRequest request,
                                      HttpServletResponse response) {
        return new ModelAndView("index");
    }
}

// 2. 使用@RequestMapping注解
@Controller
public class NewStyleController {
    @RequestMapping("/hello")
    public String hello() {
        return "hello";
    }
}

// HandlerAdapter适配不同的Controller实现
public interface HandlerAdapter {
    boolean supports(Object handler);
    ModelAndView handle(HttpServletRequest request,
                       HttpServletResponse response,
                       Object handler);
}

// 适配实现Controller接口的控制器
public class SimpleControllerHandlerAdapter implements HandlerAdapter {
    public boolean supports(Object handler) {
        return (handler instanceof Controller);
    }

    public ModelAndView handle(..., Object handler) {
        return ((Controller) handler).handleRequest(request, response);
    }
}

// 适配@RequestMapping注解的控制器
public class RequestMappingHandlerAdapter implements HandlerAdapter {
    public boolean supports(Object handler) {
        return (handler instanceof HandlerMethod);
    }

    public ModelAndView handle(..., Object handler) {
        // 通过反射调用@RequestMapping方法
        return invokeHandlerMethod(request, response, (HandlerMethod) handler);
    }
}
```

---

#### 2.8 装饰器模式（Decorator Pattern）

**应用场景**：BeanWrapper、HttpServletRequestWrapper

**BeanWrapper示例**：
```java
// BeanWrapper为Bean提供属性访问和类型转换功能
BeanWrapper bw = new BeanWrapperImpl(new User());
bw.setPropertyValue("name", "Alice");
bw.setPropertyValue("age", "30");  // 自动类型转换String -> Integer

// 装饰器模式：为原始Bean增强功能
public class BeanWrapperImpl implements BeanWrapper {
    private Object wrappedObject;
    private PropertyAccessor propertyAccessor;  // 装饰功能

    public void setPropertyValue(String propertyName, Object value) {
        // 类型转换
        Object convertedValue = convertIfNecessary(value, getPropertyType(propertyName));
        // 设置属性
        propertyAccessor.setPropertyValue(wrappedObject, propertyName, convertedValue);
    }
}
```

**实际应用**：
```java
// Spring MVC中包装HttpServletRequest
public class ContentCachingRequestWrapper extends HttpServletRequestWrapper {
    private final ByteArrayOutputStream cachedContent = new ByteArrayOutputStream();

    @Override
    public ServletInputStream getInputStream() throws IOException {
        // 装饰原始InputStream，缓存内容供后续读取
        return new CachedServletInputStream(super.getInputStream());
    }
}
```

---

#### 2.9 责任链模式（Chain of Responsibility Pattern）

**应用场景**：Spring Security过滤器链、AOP拦截器链

**Spring Security示例**：
```java
// 多个安全过滤器组成责任链
public class FilterChainProxy {
    private List<SecurityFilterChain> filterChains;

    public void doFilter(ServletRequest request, ServletResponse response) {
        // 按顺序执行过滤器
        VirtualFilterChain chain = new VirtualFilterChain(filters);
        chain.doFilter(request, response);
    }
}

// 过滤器链执行
UsernamePasswordAuthenticationFilter  // 用户名密码认证
    -> BasicAuthenticationFilter       // Basic认证
    -> CsrfFilter                       // CSRF保护
    -> ExceptionTranslationFilter       // 异常处理
    -> FilterSecurityInterceptor        // 权限控制
```

---

#### 2.10 建造者模式（Builder Pattern）

**应用场景**：RestTemplateBuilder、UriComponentsBuilder

**示例**：
```java
// RestTemplate构建
RestTemplate restTemplate = new RestTemplateBuilder()
    .rootUri("https://api.example.com")
    .basicAuthentication("user", "password")
    .connectTimeout(Duration.ofSeconds(5))
    .readTimeout(Duration.ofSeconds(10))
    .build();

// URI构建
UriComponents uri = UriComponentsBuilder.newInstance()
    .scheme("https")
    .host("example.com")
    .path("/api/users/{id}")
    .queryParam("active", true)
    .buildAndExpand(1001);
// 结果：https://example.com/api/users/1001?active=true
```

---

### 3. 设计模式在Spring中的协作

**实际场景：用户登录**

```java
// 1. 单例模式：UserService是单例Bean
@Service
public class UserService {

    // 2. 工厂模式：通过ApplicationContext创建Bean
    @Autowired
    private UserRepository userRepository;

    // 3. 模板方法模式：JdbcTemplate封装数据库操作
    @Autowired
    private JdbcTemplate jdbcTemplate;

    // 4. 代理模式：@Transactional通过AOP实现事务管理
    @Transactional
    public User login(String username, String password) {
        // 5. 策略模式：不同的加密策略
        PasswordEncoder encoder = new BCryptPasswordEncoder();

        User user = userRepository.findByUsername(username);
        if (encoder.matches(password, user.getPassword())) {
            // 6. 观察者模式：发布登录成功事件
            publisher.publishEvent(new LoginSuccessEvent(this, user));
            return user;
        }
        throw new BadCredentialsException("密码错误");
    }
}
```

---

### 4. 面试答题总结

**标准回答模板**：

> Spring框架中应用了大量设计模式，主要包括：
> 1. **单例模式**：Spring Bean默认是单例，通过ConcurrentHashMap缓存
> 2. **工厂模式**：BeanFactory、FactoryBean、ApplicationContext创建和管理Bean
> 3. **代理模式**：AOP的核心实现（JDK动态代理 + CGLIB）
> 4. **模板方法模式**：JdbcTemplate、RestTemplate定义算法骨架
> 5. **观察者模式**：Spring事件机制（ApplicationEvent + ApplicationListener）
> 6. **策略模式**：Resource加载、事务传播行为
> 7. **适配器模式**：SpringMVC的HandlerAdapter适配不同Controller
> 8. **装饰器模式**：BeanWrapper为Bean增强属性访问能力
> 9. **责任链模式**：Spring Security过滤器链、AOP拦截器链
> 10. **建造者模式**：RestTemplateBuilder、UriComponentsBuilder
>
> **核心价值**：
> - 提高代码复用性和可维护性
> - 降低模块间耦合
> - 使框架具备良好的扩展性

**常见追问**：
- **Spring AOP使用哪种代理？** → 默认JDK动态代理（基于接口），无接口时用CGLIB（基于子类）
- **单例Bean是否线程安全？** → 取决于Bean本身，Spring只保证单例，不保证线程安全（无状态Bean是线程安全的）
- **模板方法模式和策略模式的区别？** → 模板方法定义算法骨架（继承），策略模式封装算法族（组合）
