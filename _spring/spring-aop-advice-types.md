---
title: "AOP通知类型"
date: 2025-11-02
description: "深入剖析Spring AOP的五种通知类型（前置、后置、返回、异常、环绕），包括执行顺序、使用场景及最佳实践"
author: "wuxl"
categories: [Spring框架]
tags: [Spring AOP, 通知类型, Advice, 执行顺序, 最佳实践]
nav_order: 457
parent: Spring框架
---
## 问题

AOP通知类型

## 答案

### 1. 核心概念

**通知（Advice）**是切面在特定连接点执行的动作，定义了"在何时做什么"。Spring AOP支持**5种通知类型**。

**通知类型**：
1. **前置通知（Before）**：方法执行前
2. **后置通知（After）**：方法执行后（无论正常或异常）
3. **返回通知（AfterReturning）**：方法正常返回后
4. **异常通知（AfterThrowing）**：方法抛出异常后
5. **环绕通知（Around）**：包围方法执行，最强大

### 2. 五种通知类型详解

#### （1）前置通知（@Before）

**执行时机**：目标方法**执行前**执行。

**特点**：
- 无法阻止方法执行（除非抛出异常）
- 无法获取方法返回值
- 可以修改方法参数（通过反射）

```java
@Aspect
@Component
@Slf4j
public class LogAspect {
    
    @Before("execution(* com.example.service.*.*(..))")
    public void logBefore(JoinPoint joinPoint) {
        String className = joinPoint.getTarget().getClass().getName();
        String methodName = joinPoint.getSignature().getName();
        Object[] args = joinPoint.getArgs();
        
        log.info("【前置通知】方法开始执行: {}.{}, 参数: {}", 
                 className, methodName, Arrays.toString(args));
    }
}
```

**使用场景**：
- 参数校验
- 权限检查
- 日志记录
- 初始化资源

**实际案例**：

```java
@Aspect
@Component
public class ValidationAspect {
    
    // 参数校验
    @Before("@annotation(com.example.annotation.Validate)")
    public void validateParams(JoinPoint joinPoint) {
        Object[] args = joinPoint.getArgs();
        
        for (Object arg : args) {
            if (arg == null) {
                throw new IllegalArgumentException("参数不能为空");
            }
        }
    }
}

@Aspect
@Component
public class PermissionAspect {
    
    @Autowired
    private UserContext userContext;
    
    // 权限检查
    @Before("@annotation(requirePermission)")
    public void checkPermission(JoinPoint joinPoint, RequirePermission requirePermission) {
        User currentUser = userContext.getCurrentUser();
        
        if (currentUser == null) {
            throw new UnauthorizedException("未登录");
        }
        
        String[] permissions = requirePermission.value();
        boolean hasPermission = Arrays.stream(permissions)
            .anyMatch(p -> currentUser.hasPermission(p));
        
        if (!hasPermission) {
            throw new ForbiddenException("权限不足");
        }
    }
}
```

#### （2）后置通知（@After）

**执行时机**：目标方法**执行后**执行，**无论方法正常返回还是抛出异常**。

**特点**：
- 类似于`finally`块
- 无法获取方法返回值
- 无法处理异常
- 常用于资源清理

```java
@Aspect
@Component
@Slf4j
public class ResourceAspect {
    
    @After("execution(* com.example.service.*.*(..))")
    public void releaseResources(JoinPoint joinPoint) {
        String methodName = joinPoint.getSignature().getName();
        log.info("【后置通知】方法执行结束: {}", methodName);
        
        // 清理资源
        // 释放连接
        // 清除缓存
    }
}
```

**使用场景**：
- 资源释放
- 清理临时数据
- 记录方法执行结束

**实际案例**：

```java
@Aspect
@Component
public class ThreadLocalAspect {
    
    private static final ThreadLocal<Long> START_TIME = new ThreadLocal<>();
    
    @Before("execution(* com.example.controller.*.*(..))")
    public void before() {
        START_TIME.set(System.currentTimeMillis());
    }
    
    // 后置通知：清理ThreadLocal
    @After("execution(* com.example.controller.*.*(..))")
    public void after() {
        START_TIME.remove();  // 防止内存泄漏
    }
}
```

#### （3）返回通知（@AfterReturning）

**执行时机**：目标方法**正常返回**后执行。

**特点**：
- 只有方法正常返回才执行（异常不执行）
- 可以获取方法返回值
- 可以修改返回值（如果是对象）
- 无法阻止返回值返回给调用者（除非抛出异常）

```java
@Aspect
@Component
@Slf4j
public class ReturnAspect {
    
    @AfterReturning(
        pointcut = "execution(* com.example.service.*.*(..))",
        returning = "result"  // 指定返回值参数名
    )
    public void logAfterReturning(JoinPoint joinPoint, Object result) {
        String methodName = joinPoint.getSignature().getName();
        log.info("【返回通知】方法返回: {}, 返回值: {}", methodName, result);
    }
}
```

**使用场景**：
- 记录返回值
- 数据加工（修改返回值）
- 审计日志
- 缓存写入

**实际案例**：

```java
@Aspect
@Component
public class CacheAspect {
    
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;
    
    // 方法返回后写入缓存
    @AfterReturning(
        pointcut = "@annotation(cachePut)",
        returning = "result"
    )
    public void putCache(JoinPoint joinPoint, CachePut cachePut, Object result) {
        String key = generateKey(joinPoint, cachePut.key());
        redisTemplate.opsForValue().set(key, result, cachePut.timeout(), TimeUnit.SECONDS);
        log.info("写入缓存: key={}, value={}", key, result);
    }
}

@Aspect
@Component
public class SensitiveDataAspect {
    
    // 返回值脱敏
    @AfterReturning(
        pointcut = "execution(* com.example.service.UserService.getUser(..))",
        returning = "user"
    )
    public void maskSensitiveData(User user) {
        if (user != null) {
            // 手机号脱敏
            user.setPhone(maskPhone(user.getPhone()));
            // 身份证脱敏
            user.setIdCard(maskIdCard(user.getIdCard()));
        }
    }
    
    private String maskPhone(String phone) {
        if (phone != null && phone.length() == 11) {
            return phone.substring(0, 3) + "****" + phone.substring(7);
        }
        return phone;
    }
}
```

#### （4）异常通知（@AfterThrowing）

**执行时机**：目标方法**抛出异常**后执行。

**特点**：
- 只有方法抛出异常才执行
- 可以获取异常对象
- 可以指定捕获的异常类型
- 可以抛出新异常或包装异常
- 无法阻止异常传播（除非不再抛出）

```java
@Aspect
@Component
@Slf4j
public class ExceptionAspect {
    
    @AfterThrowing(
        pointcut = "execution(* com.example.service.*.*(..))",
        throwing = "ex"  // 指定异常参数名
    )
    public void logException(JoinPoint joinPoint, Exception ex) {
        String methodName = joinPoint.getSignature().getName();
        Object[] args = joinPoint.getArgs();
        
        log.error("【异常通知】方法异常: {}, 参数: {}, 异常: {}", 
                  methodName, Arrays.toString(args), ex.getMessage(), ex);
    }
}
```

**指定异常类型**：

```java
@Aspect
@Component
public class SpecificExceptionAspect {
    
    // 只捕获NullPointerException
    @AfterThrowing(
        pointcut = "execution(* com.example.service.*.*(..))",
        throwing = "ex"
    )
    public void handleNullPointerException(JoinPoint joinPoint, NullPointerException ex) {
        log.error("空指针异常: {}", ex.getMessage());
    }
    
    // 只捕获自定义业务异常
    @AfterThrowing(
        pointcut = "execution(* com.example.service.*.*(..))",
        throwing = "ex"
    )
    public void handleBusinessException(JoinPoint joinPoint, BusinessException ex) {
        log.error("业务异常: code={}, message={}", ex.getCode(), ex.getMessage());
    }
}
```

**使用场景**：
- 异常日志记录
- 异常告警
- 异常转换
- 回滚操作
- 错误统计

**实际案例**：

```java
@Aspect
@Component
public class AlertAspect {
    
    @Autowired
    private AlertService alertService;
    
    // 异常告警
    @AfterThrowing(
        pointcut = "execution(* com.example.service.*.*(..))",
        throwing = "ex"
    )
    public void sendAlert(JoinPoint joinPoint, Exception ex) {
        String methodName = joinPoint.getSignature().toShortString();
        
        // 发送告警
        alertService.sendAlert(
            "方法异常告警",
            String.format("方法: %s, 异常: %s", methodName, ex.getMessage())
        );
        
        // 记录到监控系统
        metricsService.recordException(methodName, ex.getClass().getName());
    }
}

@Aspect
@Component
public class ExceptionTransformAspect {
    
    // 异常转换
    @AfterThrowing(
        pointcut = "execution(* com.example.dao.*.*(..))",
        throwing = "ex"
    )
    public void transformException(JoinPoint joinPoint, SQLException ex) throws DataAccessException {
        // 将SQLException转换为自定义异常
        throw new DataAccessException("数据库访问异常: " + ex.getMessage(), ex);
    }
}
```

#### （5）环绕通知（@Around）

**执行时机**：**包围**目标方法执行，可以在方法执行前后都执行自定义逻辑。

**特点**：
- 最强大的通知类型
- 可以控制方法是否执行
- 可以修改方法参数
- 可以修改方法返回值
- 必须调用`ProceedingJoinPoint.proceed()`执行目标方法
- 必须返回目标方法的返回值（或修改后的值）

```java
@Aspect
@Component
@Slf4j
public class AroundAspect {
    
    @Around("execution(* com.example.service.*.*(..))")
    public Object logAround(ProceedingJoinPoint joinPoint) throws Throwable {
        String methodName = joinPoint.getSignature().getName();
        Object[] args = joinPoint.getArgs();
        
        // 前置逻辑
        log.info("【环绕通知-前】方法开始: {}, 参数: {}", methodName, Arrays.toString(args));
        long startTime = System.currentTimeMillis();
        
        Object result = null;
        try {
            // 执行目标方法
            result = joinPoint.proceed();  // 必须调用
            
            // 正常返回后的逻辑
            long endTime = System.currentTimeMillis();
            log.info("【环绕通知-后】方法返回: {}, 结果: {}, 耗时: {}ms", 
                     methodName, result, endTime - startTime);
            
            return result;  // 必须返回
        } catch (Throwable throwable) {
            // 异常处理逻辑
            log.error("【环绕通知-异常】方法异常: {}, 异常: {}", 
                      methodName, throwable.getMessage());
            throw throwable;  // 重新抛出或处理
        }
    }
}
```

**使用场景**：
- 性能监控
- 事务管理
- 缓存管理
- 重试机制
- 限流熔断
- 方法拦截

**实际案例**：

**案例1：性能监控**

```java
@Aspect
@Component
public class PerformanceAspect {
    
    @Around("@annotation(com.example.annotation.Monitor)")
    public Object monitor(ProceedingJoinPoint joinPoint) throws Throwable {
        String methodName = joinPoint.getSignature().toShortString();
        long startTime = System.currentTimeMillis();
        
        Object result = joinPoint.proceed();
        
        long endTime = System.currentTimeMillis();
        long duration = endTime - startTime;
        
        // 性能告警
        if (duration > 1000) {
            log.warn("方法执行慢: {}, 耗时: {}ms", methodName, duration);
            alertService.sendAlert("性能告警", methodName + " 耗时 " + duration + "ms");
        }
        
        // 上报监控指标
        metricsService.recordMethodDuration(methodName, duration);
        
        return result;
    }
}
```

**案例2：缓存管理**

```java
@Aspect
@Component
public class CacheAspect {
    
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;
    
    @Around("@annotation(cacheable)")
    public Object cache(ProceedingJoinPoint joinPoint, Cacheable cacheable) throws Throwable {
        // 生成缓存key
        String key = generateKey(joinPoint, cacheable.key());
        
        // 查询缓存
        Object cachedValue = redisTemplate.opsForValue().get(key);
        if (cachedValue != null) {
            log.info("缓存命中: {}", key);
            return cachedValue;
        }
        
        log.info("缓存未命中: {}", key);
        
        // 执行方法
        Object result = joinPoint.proceed();
        
        // 写入缓存
        redisTemplate.opsForValue().set(key, result, cacheable.timeout(), TimeUnit.SECONDS);
        
        return result;
    }
}
```

**案例3：重试机制**

```java
@Aspect
@Component
public class RetryAspect {
    
    @Around("@annotation(retry)")
    public Object retry(ProceedingJoinPoint joinPoint, Retry retry) throws Throwable {
        int maxRetries = retry.maxRetries();
        int retryCount = 0;
        Throwable lastException = null;
        
        while (retryCount < maxRetries) {
            try {
                return joinPoint.proceed();
            } catch (Throwable throwable) {
                lastException = throwable;
                retryCount++;
                
                if (retryCount < maxRetries) {
                    log.warn("方法执行失败，第{}次重试: {}", 
                             retryCount, joinPoint.getSignature().toShortString());
                    Thread.sleep(retry.delay());
                }
            }
        }
        
        log.error("方法执行失败，重试{}次后仍失败", maxRetries);
        throw lastException;
    }
}

// 使用
@Service
public class OrderService {
    
    @Retry(maxRetries = 3, delay = 1000)
    public void createOrder(Order order) {
        // 可能失败的操作
        orderApi.create(order);
    }
}
```

**案例4：修改参数和返回值**

```java
@Aspect
@Component
public class DataTransformAspect {
    
    @Around("execution(* com.example.service.UserService.getUser(..))")
    public Object transformData(ProceedingJoinPoint joinPoint) throws Throwable {
        Object[] args = joinPoint.getArgs();
        
        // 修改参数：将userId转为大写
        if (args.length > 0 && args[0] instanceof String) {
            args[0] = ((String) args[0]).toUpperCase();
        }
        
        // 执行方法（使用修改后的参数）
        Object result = joinPoint.proceed(args);
        
        // 修改返回值：添加前缀
        if (result instanceof String) {
            result = "PREFIX_" + result;
        }
        
        return result;
    }
}
```

**案例5：限流**

```java
@Aspect
@Component
public class RateLimitAspect {
    
    private final Map<String, RateLimiter> limiters = new ConcurrentHashMap<>();
    
    @Around("@annotation(rateLimit)")
    public Object rateLimit(ProceedingJoinPoint joinPoint, RateLimit rateLimit) throws Throwable {
        String key = joinPoint.getSignature().toShortString();
        
        // 获取或创建限流器
        RateLimiter limiter = limiters.computeIfAbsent(
            key, 
            k -> RateLimiter.create(rateLimit.permitsPerSecond())
        );
        
        // 尝试获取许可
        if (!limiter.tryAcquire(rateLimit.timeout(), TimeUnit.MILLISECONDS)) {
            throw new RateLimitException("请求过于频繁，请稍后再试");
        }
        
        return joinPoint.proceed();
    }
}
```

### 3. 通知执行顺序

#### （1）单个切面的执行顺序

```java
@Aspect
@Component
@Slf4j
public class OrderAspect {
    
    @Before("execution(* com.example.service.*.*(..))")
    public void before() {
        log.info("1. Before");
    }
    
    @Around("execution(* com.example.service.*.*(..))")
    public Object around(ProceedingJoinPoint joinPoint) throws Throwable {
        log.info("2. Around - 前");
        Object result = joinPoint.proceed();
        log.info("5. Around - 后");
        return result;
    }
    
    @AfterReturning("execution(* com.example.service.*.*(..))")
    public void afterReturning() {
        log.info("4. AfterReturning");
    }
    
    @After("execution(* com.example.service.*.*(..))")
    public void after() {
        log.info("3. After");
    }
}

// 正常执行顺序：
// 1. Around - 前
// 2. Before
// 3. 目标方法
// 4. AfterReturning (或 AfterThrowing)
// 5. After
// 6. Around - 后
```

**实际执行顺序（Spring 5.2.7+）**：

```
正常执行：
Around前 → Before → 目标方法 → AfterReturning → After → Around后

异常执行：
Around前 → Before → 目标方法（异常） → AfterThrowing → After → Around异常处理
```

#### （2）多个切面的执行顺序

```java
@Aspect
@Component
@Order(1)  // 优先级：数字越小优先级越高
@Slf4j
public class FirstAspect {
    
    @Around("execution(* com.example.service.*.*(..))")
    public Object around(ProceedingJoinPoint joinPoint) throws Throwable {
        log.info("First - Around前");
        Object result = joinPoint.proceed();
        log.info("First - Around后");
        return result;
    }
}

@Aspect
@Component
@Order(2)
@Slf4j
public class SecondAspect {
    
    @Around("execution(* com.example.service.*.*(..))")
    public Object around(ProceedingJoinPoint joinPoint) throws Throwable {
        log.info("Second - Around前");
        Object result = joinPoint.proceed();
        log.info("Second - Around后");
        return result;
    }
}

// 执行顺序（洋葱模型）：
// First - Around前
//   Second - Around前
//     目标方法
//   Second - Around后
// First - Around后
```

**多切面执行图示**：

```
@Order(1)切面 ─┐
              │ Before
@Order(2)切面 ─┐
              │ Before
              │
         目标方法
              │
@Order(2)切面 ─┘ After / AfterReturning
              │
@Order(1)切面 ─┘ After / AfterReturning
```

### 4. JoinPoint vs ProceedingJoinPoint

| 特性 | JoinPoint | ProceedingJoinPoint |
|------|-----------|---------------------|
| **使用场景** | Before、After、AfterReturning、AfterThrowing | Around |
| **功能** | 获取方法信息 | 获取方法信息 + 控制方法执行 |
| **关键方法** | getSignature()、getArgs()、getTarget() | proceed()、proceed(args) |
| **能否执行目标方法** | ❌ | ✅ |

```java
// JoinPoint常用方法
public void advice(JoinPoint joinPoint) {
    // 获取方法签名
    Signature signature = joinPoint.getSignature();
    String methodName = signature.getName();
    String className = signature.getDeclaringTypeName();
    
    // 获取方法参数
    Object[] args = joinPoint.getArgs();
    
    // 获取目标对象
    Object target = joinPoint.getTarget();
    
    // 获取代理对象
    Object proxy = joinPoint.getThis();
}

// ProceedingJoinPoint常用方法
public Object advice(ProceedingJoinPoint joinPoint) throws Throwable {
    // 继承JoinPoint的所有方法
    String methodName = joinPoint.getSignature().getName();
    Object[] args = joinPoint.getArgs();
    
    // 执行目标方法（使用原参数）
    Object result = joinPoint.proceed();
    
    // 执行目标方法（使用修改后的参数）
    Object[] newArgs = new Object[]{"modified"};
    Object result2 = joinPoint.proceed(newArgs);
    
    return result;
}
```

### 5. 通知类型选择建议

| 需求 | 推荐通知 | 原因 |
|------|---------|------|
| **只需方法前执行** | @Before | 简单直接 |
| **只需方法后执行** | @After | 类似finally |
| **需要返回值** | @AfterReturning | 获取返回值 |
| **需要异常信息** | @AfterThrowing | 获取异常 |
| **需要控制执行流程** | @Around | 最灵活 |
| **性能监控** | @Around | 需要前后逻辑 |
| **缓存** | @Around | 可能不执行方法 |
| **事务管理** | @Around | 需要异常回滚 |
| **参数校验** | @Before | 执行前校验 |
| **资源清理** | @After | 保证执行 |

### 6. 面试答题要点

**标准回答结构**：

1. **5种通知类型**：
   - @Before：方法执行前
   - @After：方法执行后（finally）
   - @AfterReturning：正常返回后
   - @AfterThrowing：抛出异常后
   - @Around：环绕方法执行

2. **执行顺序**（单切面）：
   - 正常：Around前 → Before → 方法 → AfterReturning → After → Around后
   - 异常：Around前 → Before → 方法 → AfterThrowing → After → Around异常

3. **多切面顺序**：使用@Order控制，洋葱模型

4. **@Around最强大**：
   - 可控制方法是否执行
   - 可修改参数和返回值
   - 需要调用proceed()
   - 需要返回结果

5. **选择建议**：
   - 简单场景用具体通知
   - 复杂场景用@Around

**加分点**：
- 了解Spring 5.2.7前后执行顺序的变化
- 知道洋葱模型
- 能说明@Around的强大之处
- 了解ProceedingJoinPoint的特殊性
- 能举实际应用案例

### 7. 总结

**核心要点**：

| 通知类型 | 执行时机 | 特点 | 常见场景 |
|---------|---------|------|---------|
| **@Before** | 方法前 | 无法阻止执行 | 参数校验、权限检查 |
| **@After** | 方法后（finally） | 必定执行 | 资源清理 |
| **@AfterReturning** | 正常返回后 | 获取返回值 | 结果处理、缓存写入 |
| **@AfterThrowing** | 异常后 | 获取异常 | 异常日志、告警 |
| **@Around** | 环绕执行 | 最强大 | 性能监控、缓存、事务 |

**记忆口诀**：
- 通知有五种，前后返异环
- Before方法前，校验和权限
- After类finally，资源要清理
- AfterReturning，返回值可取
- AfterThrowing，异常要记录
- Around最强大，环绕全掌控

**使用建议**：
- 简单场景：使用具体通知（Before/After等）
- 复杂场景：使用@Around
- 性能监控：@Around
- 异常处理：@AfterThrowing + 全局异常处理器
- 多切面：用@Order控制顺序

理解Spring AOP的通知类型和执行顺序，是掌握AOP编程和排查AOP问题的关键，也是面试中的高频考点。

