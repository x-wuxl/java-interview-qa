---
layout: post
title: "如何自定义一个SpringBoot Starter？"
date: 2025-11-02
description: "详细讲解自定义SpringBoot Starter的完整流程，包括模块结构、自动配置类编写、条件注解使用和最佳实践"
author: "wuxl"
categories: [Spring框架]
tags: [SpringBoot, Starter, 自动配置, 实战, 面试]
---

## 问题

如何自定义一个SpringBoot Starter？

## 答案

### 1. 核心概念

Starter是SpringBoot的依赖整合模块，将相关依赖和自动配置打包在一起，让使用者只需引入一个依赖即可完成功能集成。自定义Starter可以将通用功能封装成可复用组件。

### 2. 命名规范

**官方命名**：`spring-boot-starter-{name}`（如spring-boot-starter-web）
**第三方命名**：`{name}-spring-boot-starter`（如mybatis-spring-boot-starter）

### 3. 完整实现步骤

#### 第一步：创建Maven模块结构

推荐采用两个模块的结构：

```
my-spring-boot-starter-parent/
├─ my-spring-boot-autoconfigure/     （自动配置模块）
│   ├─ pom.xml
│   └─ src/main/java/
│       └─ com/example/autoconfigure/
│           ├─ MyAutoConfiguration.java
│           ├─ MyProperties.java
│           └─ MyService.java
└─ my-spring-boot-starter/           （依赖整合模块）
    ├─ pom.xml
    └─ 无代码，仅依赖管理
```

**或采用单模块结构**（适用于简单场景）：

```
my-spring-boot-starter/
├─ pom.xml
└─ src/main/java/
    └─ com/example/starter/
        ├─ autoconfigure/
        │   ├─ MyAutoConfiguration.java
        │   └─ MyProperties.java
        └─ service/
            └─ MyService.java
```

#### 第二步：编写autoconfigure模块的pom.xml

```xml
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>my-spring-boot-autoconfigure</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <!-- SpringBoot自动配置依赖 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-autoconfigure</artifactId>
            <version>3.0.0</version>
        </dependency>

        <!-- 配置处理器（生成配置元数据，IDE提示） -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-configuration-processor</artifactId>
            <version>3.0.0</version>
            <optional>true</optional>
        </dependency>

        <!-- 你的功能依赖 -->
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>my-core-library</artifactId>
            <version>1.0.0</version>
        </dependency>
    </dependencies>
</project>
```

#### 第三步：编写配置属性类

```java
package com.example.autoconfigure;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Starter配置属性
 */
@ConfigurationProperties(prefix = "my.service")
public class MyProperties {

    /**
     * 是否启用服务
     */
    private boolean enabled = true;

    /**
     * 服务名称
     */
    private String name = "default-service";

    /**
     * 超时时间（毫秒）
     */
    private int timeout = 5000;

    /**
     * 连接配置
     */
    private Connection connection = new Connection();

    // Getters and Setters

    public static class Connection {
        private String host = "localhost";
        private int port = 8080;
        private String username;
        private String password;

        // Getters and Setters
    }
}
```

#### 第四步：编写核心服务类

```java
package com.example.autoconfigure;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Starter提供的核心服务
 */
public class MyService {

    private static final Logger logger = LoggerFactory.getLogger(MyService.class);

    private final MyProperties properties;

    public MyService(MyProperties properties) {
        this.properties = properties;
        logger.info("MyService initialized with name: {}", properties.getName());
    }

    public String execute(String input) {
        if (!properties.isEnabled()) {
            logger.warn("Service is disabled");
            return null;
        }

        // 核心业务逻辑
        String result = doProcess(input);
        logger.info("Processed: {} -> {}", input, result);
        return result;
    }

    private String doProcess(String input) {
        // 实际处理逻辑
        return String.format("[%s] %s", properties.getName(), input);
    }

    public void connect() {
        MyProperties.Connection conn = properties.getConnection();
        logger.info("Connecting to {}:{}", conn.getHost(), conn.getPort());
        // 连接逻辑
    }
}
```

#### 第五步：编写自动配置类

```java
package com.example.autoconfigure;

import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

/**
 * 自动配置类
 */
@AutoConfiguration  // SpringBoot 3.x使用@AutoConfiguration，2.x使用@Configuration
@ConditionalOnClass(MyService.class)  // 当MyService类存在时才生效
@ConditionalOnProperty(prefix = "my.service", name = "enabled", havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(MyProperties.class)  // 启用配置属性
public class MyAutoConfiguration {

    /**
     * 注册核心服务Bean
     */
    @Bean
    @ConditionalOnMissingBean  // 用户未自定义MyService时才生效
    public MyService myService(MyProperties properties) {
        return new MyService(properties);
    }

    /**
     * 可选：注册其他Bean
     */
    @Bean
    @ConditionalOnProperty(prefix = "my.service", name = "async-enabled")
    public MyAsyncService myAsyncService() {
        return new MyAsyncService();
    }
}
```

#### 第六步：注册自动配置类

**SpringBoot 2.x方式**：

创建 `src/main/resources/META-INF/spring.factories` 文件：

```properties
org.springframework.boot.autoconfigure.EnableAutoConfiguration=\
com.example.autoconfigure.MyAutoConfiguration
```

**SpringBoot 3.x方式**（推荐）：

创建 `src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` 文件：

```
com.example.autoconfigure.MyAutoConfiguration
```

#### 第七步：生成配置元数据（可选）

运行Maven编译后会自动生成 `META-INF/spring-configuration-metadata.json`，为IDE提供配置提示：

```json
{
  "groups": [
    {
      "name": "my.service",
      "type": "com.example.autoconfigure.MyProperties",
      "sourceType": "com.example.autoconfigure.MyProperties"
    }
  ],
  "properties": [
    {
      "name": "my.service.enabled",
      "type": "java.lang.Boolean",
      "description": "是否启用服务",
      "defaultValue": true
    },
    {
      "name": "my.service.name",
      "type": "java.lang.String",
      "description": "服务名称",
      "defaultValue": "default-service"
    }
  ]
}
```

#### 第八步：编写starter模块的pom.xml

```xml
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>my-spring-boot-starter</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <!-- 引入autoconfigure模块 -->
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>my-spring-boot-autoconfigure</artifactId>
            <version>${project.version}</version>
        </dependency>

        <!-- 可选：引入其他必需依赖 -->
    </dependencies>
</project>
```

### 4. 使用自定义Starter

#### (1) 添加依赖

```xml
<dependency>
    <groupId>com.example</groupId>
    <artifactId>my-spring-boot-starter</artifactId>
    <version>1.0.0</version>
</dependency>
```

#### (2) 配置application.yml

```yaml
my:
  service:
    enabled: true
    name: my-custom-service
    timeout: 3000
    connection:
      host: 192.168.1.100
      port: 9090
      username: admin
      password: secret
```

#### (3) 注入使用

```java
@RestController
public class MyController {

    @Autowired
    private MyService myService;

    @GetMapping("/process")
    public String process(@RequestParam String input) {
        return myService.execute(input);
    }
}
```

### 5. 高级特性

#### (1) 条件注解组合

```java
@Configuration
@ConditionalOnClass(RedisTemplate.class)
@ConditionalOnProperty(prefix = "my.cache", name = "type", havingValue = "redis")
public class RedisCacheConfiguration {
    // Redis缓存配置
}
```

#### (2) 配置顺序控制

```java
@AutoConfiguration
@AutoConfigureAfter(DataSourceAutoConfiguration.class)  // 在数据源配置之后
@AutoConfigureBefore(RedisAutoConfiguration.class)     // 在Redis配置之前
public class MyAutoConfiguration {
}
```

#### (3) 监听ApplicationContext事件

```java
@Component
public class MyStartupListener implements ApplicationListener<ApplicationReadyEvent> {

    @Override
    public void onApplicationEvent(ApplicationReadyEvent event) {
        // 应用启动完成后执行
        System.out.println("MyService is ready!");
    }
}
```

### 6. 最佳实践

1. **命名规范**：遵循第三方starter命名规范 `{name}-spring-boot-starter`
2. **配置前缀**：使用有意义且不易冲突的前缀（如 `my.service` 而非 `service`）
3. **默认值**：为所有配置提供合理的默认值
4. **条件注解**：充分利用条件注解，避免不必要的Bean加载
5. **配置元数据**：使用`spring-boot-configuration-processor`生成元数据，提升开发体验
6. **文档**：提供详细的README和配置示例
7. **版本兼容**：明确支持的SpringBoot版本范围
8. **单元测试**：编写自动配置的单元测试

### 7. 测试自动配置

```java
@SpringBootTest
@EnableAutoConfiguration
class MyAutoConfigurationTest {

    @Autowired(required = false)
    private MyService myService;

    @Test
    void testAutoConfiguration() {
        assertNotNull(myService);
        String result = myService.execute("test");
        assertEquals("[default-service] test", result);
    }

    @Test
    @TestPropertySource(properties = "my.service.enabled=false")
    void testDisabled() {
        assertNull(myService);
    }
}
```

### 8. 面试答题要点总结

**自定义Starter四步骤**：
1. **创建模块**：autoconfigure模块（核心）+ starter模块（依赖整合）
2. **编写配置**：Properties类 + 自动配置类 + 核心服务类
3. **注册配置**：在`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`注册
4. **打包发布**：Maven install/deploy，供其他项目使用

**关键技术点**：
- `@ConfigurationProperties` 绑定外部配置
- `@ConditionalOnXxx` 条件注解控制加载
- `@EnableConfigurationProperties` 启用配置属性
- `spring-boot-configuration-processor` 生成配置元数据

**一句话总结**：自定义Starter需要创建autoconfigure模块编写自动配置类，通过`@ConfigurationProperties`绑定配置、`@ConditionalOnXxx`控制加载时机，最后在`META-INF/spring`目录注册配置类即可实现开箱即用的功能模块。
