---
layout: default
title: "SpringBoot和Spring的区别是什么？"
parent: Spring框架
nav_order: 469
description: "详解SpringBoot与传统Spring框架的核心区别，包括自动配置、依赖管理、内嵌容器等关键特性"
author: "wuxl"
date: 2025-11-02
---
## 问题

SpringBoot和Spring的区别是什么？

## 答案

### 1. 核心概念

**Spring** 是一个轻量级的Java企业级应用开发框架，提供了IoC容器、AOP、事务管理等核心功能，但需要大量的XML或Java配置。

**SpringBoot** 是在Spring框架基础上的进一步封装，通过"约定优于配置"的理念，简化了Spring应用的搭建和开发过程。

### 2. 核心区别

#### (1) 配置方式
- **Spring**: 需要大量XML配置或Java Config，手动配置各种Bean、数据源、事务管理器等
- **SpringBoot**: 通过自动配置（Auto-Configuration）和起步依赖（Starter），极大简化配置

```java
// Spring传统方式：需要手动配置数据源
@Configuration
public class DataSourceConfig {
    @Bean
    public DataSource dataSource() {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.jdbc.Driver");
        dataSource.setUrl("jdbc:mysql://localhost:3306/db");
        dataSource.setUsername("root");
        dataSource.setPassword("password");
        return dataSource;
    }
}

// SpringBoot方式：只需在application.yml中配置
// spring:
//   datasource:
//     url: jdbc:mysql://localhost:3306/db
//     username: root
//     password: password
```

#### (2) 依赖管理
- **Spring**: 需要手动管理各个依赖的版本，容易出现版本冲突
- **SpringBoot**: 提供了spring-boot-starter-parent父POM，统一管理依赖版本

```xml
<!-- Spring传统方式 -->
<dependency>
    <groupId>org.springframework</groupId>
    <artifactId>spring-core</artifactId>
    <version>5.3.10</version>
</dependency>
<dependency>
    <groupId>org.springframework</groupId>
    <artifactId>spring-web</artifactId>
    <version>5.3.10</version>
</dependency>

<!-- SpringBoot方式：一个starter搞定 -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
</dependency>
```

#### (3) 内嵌容器
- **Spring**: 需要打成WAR包部署到外部Tomcat等容器
- **SpringBoot**: 内嵌Tomcat/Jetty/Undertow，可直接以JAR包运行

```java
// SpringBoot启动方式
@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
// 直接运行：java -jar app.jar
```

#### (4) 监控与运维
- **Spring**: 需要自己整合各种监控组件
- **SpringBoot**: 提供Actuator模块，开箱即用的健康检查、指标监控、审计等功能

### 3. 技术实现关键点

- **自动配置原理**: 通过`@EnableAutoConfiguration`注解，SpringBoot会扫描classpath下的`META-INF/spring.factories`文件（SpringBoot 3.0改为`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`），根据条件注解（`@ConditionalOnClass`、`@ConditionalOnBean`等）决定是否加载配置类

- **Starter机制**: 将相关依赖打包成一个starter，简化依赖管理

- **外部化配置**: 支持`application.properties`/`application.yml`，支持profile、环境变量等多种配置源

### 4. 最佳实践与总结

**选择建议**:
- 新项目优先选择SpringBoot，开发效率高
- 老项目迁移需评估改造成本
- 微服务架构场景，SpringBoot + Spring Cloud是首选

**核心优势总结**:
1. 极简配置：零XML配置，注解驱动
2. 快速启动：内嵌容器，独立运行
3. 生产就绪：Actuator提供完善的监控能力
4. 生态丰富：大量官方和第三方starter

SpringBoot本质上是Spring的增强版，并非替代关系，底层仍是Spring的IoC、AOP等核心能力。
