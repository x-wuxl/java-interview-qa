---
layout: post
title: "SpringBoot是如何实现main方法启动Web项目的？"
date: 2025-11-02
description: "深入解析SpringBoot如何通过main方法启动Web应用，包括内嵌容器原理、WebServer启动机制和ServletContext初始化流程"
author: "wuxl"
categories: [Spring框架]
tags: [SpringBoot, 内嵌容器, Tomcat, Web启动, 面试]
---

## 问题

SpringBoot是如何实现main方法启动Web项目的？

## 答案

### 1. 核心概念

传统的Web项目需要打成WAR包部署到Tomcat等外部容器，而SpringBoot通过**内嵌Servlet容器**（如Tomcat、Jetty、Undertow），实现了通过main方法直接启动Web应用，打包成可执行JAR独立运行。

### 2. 实现原理详解

#### (1) 核心依赖：spring-boot-starter-web

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
</dependency>
```

该依赖包含：
- Spring MVC相关依赖
- **内嵌Tomcat依赖**（spring-boot-starter-tomcat）
- JSON处理库（Jackson）

#### (2) 应用类型推断

SpringBoot在启动时会推断应用类型：

```java
// SpringApplication构造器中
this.webApplicationType = WebApplicationType.deduceFromClasspath();

// WebApplicationType.deduceFromClasspath() 实现
static WebApplicationType deduceFromClasspath() {
    // 检查是否存在Reactive相关类
    if (ClassUtils.isPresent("org.springframework.web.reactive.DispatcherHandler", null)
        && !ClassUtils.isPresent("org.springframework.web.servlet.DispatcherServlet", null)
        && !ClassUtils.isPresent("org.glassfish.jersey.servlet.ServletContainer", null)) {
        return WebApplicationType.REACTIVE;
    }

    // 检查是否存在Servlet相关类
    for (String className : SERVLET_INDICATOR_CLASSES) {
        if (!ClassUtils.isPresent(className, null)) {
            return WebApplicationType.NONE;  // 非Web应用
        }
    }
    return WebApplicationType.SERVLET;  // 传统Servlet应用
}
```

**三种应用类型**：
- `SERVLET`：传统Servlet Web应用（包含spring-web依赖）
- `REACTIVE`：响应式Web应用（Spring WebFlux）
- `NONE`：非Web应用

#### (3) 创建Web应用上下文

根据应用类型创建对应的ApplicationContext：

```java
// SpringApplication.createApplicationContext()
protected ConfigurableApplicationContext createApplicationContext() {
    return this.applicationContextFactory.create(this.webApplicationType);
}

// 对应关系：
// SERVLET → AnnotationConfigServletWebServerApplicationContext
// REACTIVE → AnnotationConfigReactiveWebServerApplicationContext
// NONE → AnnotationConfigApplicationContext
```

**关键类层次结构**：

```
AnnotationConfigServletWebServerApplicationContext
  ├─ ServletWebServerApplicationContext（实现WebServer管理）
  │    └─ GenericWebApplicationContext
  │         └─ GenericApplicationContext
  └─ 包含 WebServer 生命周期管理
```

#### (4) WebServer创建与启动

**核心流程**（在refresh()的onRefresh()阶段）：

```java
// ServletWebServerApplicationContext.onRefresh()
@Override
protected void onRefresh() {
    super.onRefresh();
    try {
        createWebServer();  // 创建并启动WebServer
    } catch (Throwable ex) {
        throw new ApplicationContextException("Unable to start web server", ex);
    }
}

private void createWebServer() {
    WebServer webServer = this.webServer;
    ServletContext servletContext = getServletContext();

    if (webServer == null && servletContext == null) {
        // 1. 获取WebServerFactory（TomcatServletWebServerFactory）
        ServletWebServerFactory factory = getWebServerFactory();

        // 2. 创建WebServer（TomcatWebServer）
        this.webServer = factory.getWebServer(getSelfInitializer());

        // 3. 注册优雅停机回调
        getBeanFactory().registerSingleton("webServerGracefulShutdown",
            new WebServerGracefulShutdownLifecycle(this.webServer));
    }

    initPropertySources();
}
```

#### (5) Tomcat启动详细流程

**TomcatServletWebServerFactory.getWebServer()**：

```java
@Override
public WebServer getWebServer(ServletContextInitializer... initializers) {
    // 1. 创建Tomcat实例
    Tomcat tomcat = new Tomcat();

    // 2. 配置临时目录
    File baseDir = (this.baseDirectory != null) ? this.baseDirectory
                   : createTempDir("tomcat");
    tomcat.setBaseDir(baseDir.getAbsolutePath());

    // 3. 创建Connector（配置端口、协议等）
    Connector connector = new Connector(this.protocol);
    connector.setPort(getPort());  // 默认8080
    tomcat.getService().addConnector(connector);

    // 4. 配置Engine、Host、Context
    customizeConnector(connector);
    tomcat.setConnector(connector);
    tomcat.getHost().setAutoDeploy(false);

    // 5. 配置Context（对应Web应用）
    prepareContext(tomcat.getHost(), initializers);

    // 6. 返回TomcatWebServer（内部会启动Tomcat）
    return getTomcatWebServer(tomcat);
}

protected TomcatWebServer getTomcatWebServer(Tomcat tomcat) {
    return new TomcatWebServer(tomcat, getPort() >= 0, getShutdown());
}
```

**TomcatWebServer构造器（启动Tomcat）**：

```java
public TomcatWebServer(Tomcat tomcat, boolean autoStart, Shutdown shutdown) {
    this.tomcat = tomcat;
    this.autoStart = autoStart;
    this.gracefulShutdown = (shutdown == Shutdown.GRACEFUL)
                           ? new GracefulShutdown(tomcat) : null;
    initialize();  // 真正启动
}

private void initialize() throws WebServerException {
    logger.info("Tomcat initialized with port(s): " + getPortsDescription(false));
    synchronized (this.monitor) {
        try {
            // 添加LifecycleListener
            addInstanceIdToEngineName();

            Context context = findContext();
            context.addLifecycleListener((event) -> {
                if (context.equals(event.getSource())
                    && Lifecycle.START_EVENT.equals(event.getType())) {
                    removeServiceConnectors();
                }
            });

            // 启动Tomcat
            this.tomcat.start();

            // 注册阻塞防止退出（非守护线程）
            rethrowDeferredStartupExceptions();
            startDaemonAwaitThread();

        } catch (Exception ex) {
            stopSilently();
            destroySilently();
            throw new WebServerException("Unable to start embedded Tomcat", ex);
        }
    }
}
```

#### (6) ServletContext初始化

**ServletContextInitializer回调机制**：

```java
// ServletWebServerApplicationContext.getSelfInitializer()
private org.springframework.boot.web.servlet.ServletContextInitializer getSelfInitializer() {
    return this::selfInitialize;
}

private void selfInitialize(ServletContext servletContext) throws ServletException {
    // 设置ServletContext到ApplicationContext
    prepareWebApplicationContext(servletContext);

    // 注册ApplicationContextFacade
    registerApplicationScope(servletContext);

    // 添加ApplicationListener到ServletContext
    WebApplicationContextUtils.registerEnvironmentBeans(
        getBeanFactory(), servletContext);

    // 执行所有ServletContextInitializer（注册Servlet、Filter、Listener）
    for (ServletContextInitializer beans : getServletContextInitializerBeans()) {
        beans.onStartup(servletContext);
    }
}
```

**DispatcherServlet注册**：

```java
// DispatcherServletAutoConfiguration自动配置
@Bean
@ConditionalOnBean(MultipartResolver.class)
public ServletRegistrationBean<DispatcherServlet> dispatcherServletRegistration(
        DispatcherServlet dispatcherServlet) {
    ServletRegistrationBean<DispatcherServlet> registration =
        new ServletRegistrationBean<>(dispatcherServlet, "/");
    registration.setLoadOnStartup(1);
    return registration;
}
```

### 3. 完整启动时序

```
main()
  ↓
SpringApplication.run()
  ↓
createApplicationContext()
  ├─ 创建AnnotationConfigServletWebServerApplicationContext
  ↓
refresh()
  ├─ prepareRefresh()
  ├─ obtainFreshBeanFactory()
  ├─ ...
  ├─ onRefresh()  ← 关键步骤
  │    └─ createWebServer()
  │         ├─ 获取TomcatServletWebServerFactory
  │         ├─ factory.getWebServer()
  │         │    ├─ new Tomcat()
  │         │    ├─ 配置Connector（端口8080）
  │         │    ├─ 配置Context（Web应用上下文）
  │         │    └─ return new TomcatWebServer()
  │         │         └─ tomcat.start()  ← Tomcat启动
  │         └─ 注册DispatcherServlet
  ├─ finishBeanFactoryInitialization()
  └─ finishRefresh()
       └─ 发布ServletWebServerInitializedEvent
  ↓
WebServer启动完成，监听8080端口
```

### 4. 切换其他内嵌容器

#### 切换到Jetty

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
    <exclusions>
        <exclusion>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-tomcat</artifactId>
        </exclusion>
    </exclusions>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-jetty</artifactId>
</dependency>
```

#### 切换到Undertow

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-undertow</artifactId>
</dependency>
```

SpringBoot会自动检测并使用对应的`ServletWebServerFactory`实现。

### 5. 配置调优

```yaml
server:
  port: 8080                     # 端口
  servlet:
    context-path: /api           # 上下文路径
  tomcat:
    threads:
      max: 200                   # 最大线程数
      min-spare: 10              # 最小空闲线程
    max-connections: 8192        # 最大连接数
    accept-count: 100            # 等待队列长度
    connection-timeout: 20000    # 连接超时
  compression:
    enabled: true                # 启用压缩
    min-response-size: 1024      # 最小压缩大小
```

### 6. 面试答题要点总结

**核心原理三步走**：
1. **依赖内嵌容器**：通过starter引入Tomcat等内嵌容器依赖
2. **创建Web上下文**：根据classpath推断应用类型，创建`ServletWebServerApplicationContext`
3. **启动WebServer**：在refresh的onRefresh阶段，通过`ServletWebServerFactory`创建并启动Tomcat

**关键技术点**：
- `WebApplicationType`自动推断应用类型
- `ServletWebServerApplicationContext`管理WebServer生命周期
- `TomcatServletWebServerFactory`创建并配置Tomcat实例
- `ServletContextInitializer`回调机制注册Servlet、Filter
- 通过`@ConditionalOnClass`条件注解实现容器自动切换

**一句话总结**：SpringBoot通过内嵌Servlet容器（默认Tomcat），在ApplicationContext的refresh阶段通过`onRefresh()`方法创建并启动WebServer，将Web容器的生命周期纳入Spring容器管理，实现了main方法启动Web应用。
