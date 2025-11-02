---
layout: post
title: "SpringBoot的启动流程是怎么样的？"
date: 2025-11-02
description: "详细解析SpringBoot从main方法到应用启动完成的全过程，包括SpringApplication创建、环境准备、上下文初始化等关键阶段"
author: "wuxl"
categories: [Spring框架]
tags: [SpringBoot, 启动流程, 源码分析, 面试]
---

## 问题

SpringBoot的启动流程是怎么样的？

## 答案

### 1. 核心概念

SpringBoot启动流程是从 `main` 方法调用 `SpringApplication.run()` 开始，经过环境准备、上下文创建、自动配置加载、Bean初始化等阶段，最终启动内嵌容器完成应用启动。

### 2. 完整启动流程详解

#### 第一阶段：SpringApplication实例化

```java
@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

**run方法内部实现**：

```java
public static ConfigurableApplicationContext run(Class<?> primarySource, String... args) {
    return new SpringApplication(primarySource).run(args);
}
```

**实例化过程（构造器）**：

```java
public SpringApplication(ResourceLoader resourceLoader, Class<?>... primarySources) {
    this.resourceLoader = resourceLoader;
    this.primarySources = new LinkedHashSet<>(Arrays.asList(primarySources));

    // 1. 推断应用类型（SERVLET、REACTIVE、NONE）
    this.webApplicationType = WebApplicationType.deduceFromClasspath();

    // 2. 加载ApplicationContextInitializer（从spring.factories）
    setInitializers(getSpringFactoriesInstances(ApplicationContextInitializer.class));

    // 3. 加载ApplicationListener（从spring.factories）
    setListeners(getSpringFactoriesInstances(ApplicationListener.class));

    // 4. 推断主启动类
    this.mainApplicationClass = deduceMainApplicationClass();
}
```

#### 第二阶段：执行run方法

```java
public ConfigurableApplicationContext run(String... args) {
    // 1. 创建StopWatch，用于统计启动时间
    StopWatch stopWatch = new StopWatch();
    stopWatch.start();

    // 2. 创建启动上下文
    DefaultBootstrapContext bootstrapContext = createBootstrapContext();
    ConfigurableApplicationContext context = null;

    // 3. 配置Headless模式（适用于无图形界面的服务器环境）
    configureHeadlessProperty();

    // 4. 获取并启动SpringApplicationRunListeners（事件发布）
    SpringApplicationRunListeners listeners = getRunListeners(args);
    listeners.starting(bootstrapContext, this.mainApplicationClass);

    try {
        // 5. 封装命令行参数
        ApplicationArguments applicationArguments = new DefaultApplicationArguments(args);

        // 6. 准备环境（Environment）
        ConfigurableEnvironment environment = prepareEnvironment(listeners,
                                              bootstrapContext, applicationArguments);
        configureIgnoreBeanInfo(environment);

        // 7. 打印Banner
        Banner printedBanner = printBanner(environment);

        // 8. 创建ApplicationContext（根据应用类型）
        context = createApplicationContext();
        context.setApplicationStartup(this.applicationStartup);

        // 9. 准备上下文
        prepareContext(bootstrapContext, context, environment, listeners,
                      applicationArguments, printedBanner);

        // 10. 刷新上下文（核心）
        refreshContext(context);

        // 11. 刷新后处理
        afterRefresh(context, applicationArguments);

        stopWatch.stop();

        // 12. 发布启动完成事件
        listeners.started(context);

        // 13. 执行Runners（CommandLineRunner、ApplicationRunner）
        callRunners(context, applicationArguments);

    } catch (Throwable ex) {
        handleRunFailure(context, ex, listeners);
        throw new IllegalStateException(ex);
    }

    try {
        // 14. 发布就绪事件
        listeners.running(context);
    } catch (Throwable ex) {
        handleRunFailure(context, ex, null);
        throw new IllegalStateException(ex);
    }

    return context;
}
```

### 3. 关键步骤详解

#### (1) 环境准备（prepareEnvironment）

```java
private ConfigurableEnvironment prepareEnvironment(
        SpringApplicationRunListeners listeners,
        DefaultBootstrapContext bootstrapContext,
        ApplicationArguments applicationArguments) {

    // 创建Environment对象（根据应用类型）
    ConfigurableEnvironment environment = getOrCreateEnvironment();

    // 配置Environment（添加命令行参数、激活profile等）
    configureEnvironment(environment, applicationArguments.getSourceArgs());

    // 绑定Environment到SpringApplication
    ConfigurationPropertySources.attach(environment);

    // 发布环境准备完成事件
    listeners.environmentPrepared(bootstrapContext, environment);

    return environment;
}
```

#### (2) 创建ApplicationContext

```java
protected ConfigurableApplicationContext createApplicationContext() {
    return this.applicationContextFactory.create(this.webApplicationType);
}

// 根据应用类型创建不同的Context
// SERVLET -> AnnotationConfigServletWebServerApplicationContext
// REACTIVE -> AnnotationConfigReactiveWebServerApplicationContext
// NONE -> AnnotationConfigApplicationContext
```

#### (3) 准备上下文（prepareContext）

```java
private void prepareContext(DefaultBootstrapContext bootstrapContext,
                           ConfigurableApplicationContext context,
                           ConfigurableEnvironment environment,
                           SpringApplicationRunListeners listeners,
                           ApplicationArguments applicationArguments,
                           Banner printedBanner) {
    // 设置环境
    context.setEnvironment(environment);

    // 后置处理ApplicationContext
    postProcessApplicationContext(context);

    // 应用初始化器（ApplicationContextInitializer）
    applyInitializers(context);

    // 发布上下文准备完成事件
    listeners.contextPrepared(context);

    // 注册启动参数Bean
    context.getBeanFactory().registerSingleton("springApplicationArguments",
                                               applicationArguments);

    // 加载主启动类
    Set<Object> sources = getAllSources();
    load(context, sources.toArray(new Object[0]));

    // 发布上下文加载完成事件
    listeners.contextLoaded(context);
}
```

#### (4) 刷新上下文（refreshContext）

这是Spring容器启动的核心，底层调用 `AbstractApplicationContext.refresh()`：

```java
@Override
public void refresh() throws BeansException, IllegalStateException {
    synchronized (this.startupShutdownMonitor) {
        // 1. 准备刷新
        prepareRefresh();

        // 2. 获取BeanFactory
        ConfigurableListableBeanFactory beanFactory = obtainFreshBeanFactory();

        // 3. 准备BeanFactory
        prepareBeanFactory(beanFactory);

        try {
            // 4. BeanFactory后置处理
            postProcessBeanFactory(beanFactory);

            // 5. 执行BeanFactoryPostProcessor
            invokeBeanFactoryPostProcessors(beanFactory);

            // 6. 注册BeanPostProcessor
            registerBeanPostProcessors(beanFactory);

            // 7. 初始化消息源
            initMessageSource();

            // 8. 初始化事件广播器
            initApplicationEventMulticaster();

            // 9. 刷新子类特定的Bean（如启动内嵌Tomcat）
            onRefresh();

            // 10. 注册监听器
            registerListeners();

            // 11. 实例化所有非懒加载的单例Bean
            finishBeanFactoryInitialization(beanFactory);

            // 12. 完成刷新，发布ContextRefreshedEvent
            finishRefresh();
        }
        // 异常处理省略...
    }
}
```

**内嵌Tomcat启动**（onRefresh阶段）：

```java
@Override
protected void onRefresh() {
    super.onRefresh();
    try {
        // 创建并启动WebServer（Tomcat/Jetty/Undertow）
        createWebServer();
    } catch (Throwable ex) {
        throw new ApplicationContextException("Unable to start web server", ex);
    }
}
```

### 4. 启动流程时序图

```
main()
  ↓
new SpringApplication()
  ├─ 推断应用类型
  ├─ 加载初始化器
  ├─ 加载监听器
  └─ 推断主类
  ↓
run()
  ├─ starting事件
  ├─ 准备Environment
  ├─ environmentPrepared事件
  ├─ 打印Banner
  ├─ 创建ApplicationContext
  ├─ 准备Context
  │   ├─ 应用初始化器
  │   ├─ contextPrepared事件
  │   └─ contextLoaded事件
  ├─ 刷新Context
  │   ├─ 自动配置加载
  │   ├─ Bean实例化
  │   └─ 启动内嵌容器
  ├─ started事件
  ├─ 执行Runners
  └─ running事件
  ↓
应用启动完成
```

### 5. 性能优化考量

1. **懒加载**：配置 `spring.main.lazy-initialization=true` 延迟Bean初始化
2. **排除自动配置**：排除不需要的AutoConfiguration减少启动时间
3. **Profile优化**：根据环境按需加载配置
4. **Spring Native**：使用GraalVM编译为原生镜像，启动时间从秒级降至毫秒级

### 6. 实战调试技巧

#### 启用启动日志

```properties
# application.properties
debug=true
logging.level.org.springframework.boot=DEBUG
```

#### 自定义监听器监控启动过程

```java
@Component
public class StartupListener implements ApplicationListener<ApplicationEvent> {

    @Override
    public void onApplicationEvent(ApplicationEvent event) {
        if (event instanceof ApplicationStartingEvent) {
            System.out.println("应用正在启动...");
        } else if (event instanceof ApplicationEnvironmentPreparedEvent) {
            System.out.println("环境准备完成");
        } else if (event instanceof ApplicationContextInitializedEvent) {
            System.out.println("上下文初始化完成");
        } else if (event instanceof ApplicationPreparedEvent) {
            System.out.println("应用准备完成");
        } else if (event instanceof ApplicationStartedEvent) {
            System.out.println("应用启动完成");
        } else if (event instanceof ApplicationReadyEvent) {
            System.out.println("应用就绪");
        }
    }
}
```

### 7. 面试答题要点总结

**完整流程概括**：
1. **实例化SpringApplication**：推断应用类型、加载初始化器和监听器
2. **准备环境**：加载配置文件、激活profile
3. **创建上下文**：根据应用类型创建对应的ApplicationContext
4. **准备上下文**：应用初始化器、加载主配置类
5. **刷新上下文**：执行Spring容器的refresh流程，加载自动配置、实例化Bean、启动内嵌容器
6. **执行Runners**：调用CommandLineRunner和ApplicationRunner
7. **发布就绪事件**：应用完全启动，可对外提供服务

**核心关键点**：
- `SpringApplication.run()` 是入口
- `refresh()` 是Spring容器启动的核心
- 自动配置在 `invokeBeanFactoryPostProcessors` 阶段加载
- 内嵌Tomcat在 `onRefresh()` 阶段启动
