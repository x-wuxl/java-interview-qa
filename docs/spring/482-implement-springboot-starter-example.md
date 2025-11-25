---
layout: default
title: "实现一个SpringBoot Starter（实战案例）"
parent: Spring框架
nav_order: 482
description: "通过完整的短信发送Starter实战案例，演示自定义SpringBoot Starter的完整开发流程和代码实现"
author: "wuxl"
date: 2025-11-02
---
## 问题

实现一个SpringBoot Starter

## 答案

### 1. 实战场景说明

我们将实现一个**通用短信发送Starter**（sms-spring-boot-starter），支持多种短信服务商（阿里云、腾讯云），提供统一的发送接口，开箱即用。

**功能需求**：
- 支持多短信服务商（阿里云、腾讯云）
- 统一的发送接口
- 可配置化（AppKey、密钥、签名、模板等）
- 支持异步发送
- 提供发送记录日志

### 2. 项目结构

```
sms-spring-boot-starter/
├─ sms-spring-boot-autoconfigure/
│  ├─ pom.xml
│  └─ src/main/
│     ├─ java/com/example/sms/
│     │  ├─ autoconfigure/
│     │  │  ├─ SmsAutoConfiguration.java
│     │  │  └─ SmsProperties.java
│     │  ├─ service/
│     │  │  ├─ SmsService.java
│     │  │  ├─ AliyunSmsService.java
│     │  │  └─ TencentSmsService.java
│     │  └─ model/
│     │     ├─ SmsRequest.java
│     │     └─ SmsResponse.java
│     └─ resources/
│        └─ META-INF/spring/
│           └─ org.springframework.boot.autoconfigure.AutoConfiguration.imports
└─ sms-spring-boot-starter/
   └─ pom.xml
```

### 3. 完整代码实现

#### 第一步：autoconfigure模块pom.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>sms-spring-boot-autoconfigure</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <!-- SpringBoot自动配置 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-autoconfigure</artifactId>
            <version>3.0.0</version>
        </dependency>

        <!-- 配置处理器（生成元数据） -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-configuration-processor</artifactId>
            <version>3.0.0</version>
            <optional>true</optional>
        </dependency>

        <!-- 日志 -->
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
            <version>2.0.7</version>
        </dependency>

        <!-- HTTP客户端（调用短信API） -->
        <dependency>
            <groupId>org.apache.httpcomponents.client5</groupId>
            <artifactId>httpclient5</artifactId>
            <version>5.2.1</version>
        </dependency>

        <!-- JSON处理 -->
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
            <version>2.15.0</version>
        </dependency>
    </dependencies>
</project>
```

#### 第二步：配置属性类

```java
package com.example.sms.autoconfigure;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "sms")
public class SmsProperties {

    /**
     * 是否启用短信服务
     */
    private boolean enabled = true;

    /**
     * 短信服务商类型：aliyun、tencent
     */
    private String provider = "aliyun";

    /**
     * 阿里云配置
     */
    private Aliyun aliyun = new Aliyun();

    /**
     * 腾讯云配置
     */
    private Tencent tencent = new Tencent();

    /**
     * 是否异步发送
     */
    private boolean async = false;

    /**
     * 异步线程池大小
     */
    private int threadPoolSize = 5;

    // Getters and Setters

    public static class Aliyun {
        private String accessKeyId;
        private String accessKeySecret;
        private String signName;
        private String templateCode;

        // Getters and Setters
        public String getAccessKeyId() { return accessKeyId; }
        public void setAccessKeyId(String accessKeyId) { this.accessKeyId = accessKeyId; }
        public String getAccessKeySecret() { return accessKeySecret; }
        public void setAccessKeySecret(String accessKeySecret) { this.accessKeySecret = accessKeySecret; }
        public String getSignName() { return signName; }
        public void setSignName(String signName) { this.signName = signName; }
        public String getTemplateCode() { return templateCode; }
        public void setTemplateCode(String templateCode) { this.templateCode = templateCode; }
    }

    public static class Tencent {
        private String secretId;
        private String secretKey;
        private String sdkAppId;
        private String signName;
        private String templateId;

        // Getters and Setters
        public String getSecretId() { return secretId; }
        public void setSecretId(String secretId) { this.secretId = secretId; }
        public String getSecretKey() { return secretKey; }
        public void setSecretKey(String secretKey) { this.secretKey = secretKey; }
        public String getSdkAppId() { return sdkAppId; }
        public void setSdkAppId(String sdkAppId) { this.sdkAppId = sdkAppId; }
        public String getSignName() { return signName; }
        public void setSignName(String signName) { this.signName = signName; }
        public String getTemplateId() { return templateId; }
        public void setTemplateId(String templateId) { this.templateId = templateId; }
    }

    // Getters and Setters
    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public String getProvider() { return provider; }
    public void setProvider(String provider) { this.provider = provider; }
    public Aliyun getAliyun() { return aliyun; }
    public void setAliyun(Aliyun aliyun) { this.aliyun = aliyun; }
    public Tencent getTencent() { return tencent; }
    public void setTencent(Tencent tencent) { this.tencent = tencent; }
    public boolean isAsync() { return async; }
    public void setAsync(boolean async) { this.async = async; }
    public int getThreadPoolSize() { return threadPoolSize; }
    public void setThreadPoolSize(int threadPoolSize) { this.threadPoolSize = threadPoolSize; }
}
```

#### 第三步：数据模型类

```java
package com.example.sms.model;

import java.util.Map;

public class SmsRequest {
    private String phoneNumber;
    private String templateCode;
    private Map<String, String> templateParams;

    public SmsRequest() {}

    public SmsRequest(String phoneNumber, String templateCode, Map<String, String> templateParams) {
        this.phoneNumber = phoneNumber;
        this.templateCode = templateCode;
        this.templateParams = templateParams;
    }

    // Getters and Setters
    public String getPhoneNumber() { return phoneNumber; }
    public void setPhoneNumber(String phoneNumber) { this.phoneNumber = phoneNumber; }
    public String getTemplateCode() { return templateCode; }
    public void setTemplateCode(String templateCode) { this.templateCode = templateCode; }
    public Map<String, String> getTemplateParams() { return templateParams; }
    public void setTemplateParams(Map<String, String> templateParams) { this.templateParams = templateParams; }
}
```

```java
package com.example.sms.model;

public class SmsResponse {
    private boolean success;
    private String message;
    private String requestId;

    public SmsResponse(boolean success, String message, String requestId) {
        this.success = success;
        this.message = message;
        this.requestId = requestId;
    }

    // Getters and Setters
    public boolean isSuccess() { return success; }
    public void setSuccess(boolean success) { this.success = success; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
}
```

#### 第四步：短信服务接口

```java
package com.example.sms.service;

import com.example.sms.model.SmsRequest;
import com.example.sms.model.SmsResponse;

public interface SmsService {

    /**
     * 发送短信
     */
    SmsResponse send(SmsRequest request);

    /**
     * 批量发送短信
     */
    SmsResponse batchSend(String[] phoneNumbers, String templateCode,
                         java.util.Map<String, String> templateParams);
}
```

#### 第五步：阿里云实现

```java
package com.example.sms.service;

import com.example.sms.autoconfigure.SmsProperties;
import com.example.sms.model.SmsRequest;
import com.example.sms.model.SmsResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

public class AliyunSmsService implements SmsService {

    private static final Logger logger = LoggerFactory.getLogger(AliyunSmsService.class);

    private final SmsProperties.Aliyun config;
    private final ObjectMapper objectMapper;

    public AliyunSmsService(SmsProperties.Aliyun config) {
        this.config = config;
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public SmsResponse send(SmsRequest request) {
        logger.info("Sending SMS via Aliyun to: {}", request.getPhoneNumber());

        try {
            // 模拟调用阿里云API
            // 实际项目中应调用阿里云SDK
            String params = objectMapper.writeValueAsString(request.getTemplateParams());

            logger.info("Aliyun SMS API called - Phone: {}, Template: {}, Params: {}",
                    request.getPhoneNumber(), request.getTemplateCode(), params);

            // 模拟成功响应
            return new SmsResponse(true, "发送成功", generateRequestId());

        } catch (Exception e) {
            logger.error("Failed to send SMS via Aliyun", e);
            return new SmsResponse(false, "发送失败: " + e.getMessage(), null);
        }
    }

    @Override
    public SmsResponse batchSend(String[] phoneNumbers, String templateCode,
                                 Map<String, String> templateParams) {
        logger.info("Batch sending {} SMS via Aliyun", phoneNumbers.length);

        for (String phone : phoneNumbers) {
            SmsRequest request = new SmsRequest(phone, templateCode, templateParams);
            send(request);
        }

        return new SmsResponse(true, "批量发送完成", generateRequestId());
    }

    private String generateRequestId() {
        return "ALY-" + System.currentTimeMillis();
    }
}
```

#### 第六步：腾讯云实现

```java
package com.example.sms.service;

import com.example.sms.autoconfigure.SmsProperties;
import com.example.sms.model.SmsRequest;
import com.example.sms.model.SmsResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

public class TencentSmsService implements SmsService {

    private static final Logger logger = LoggerFactory.getLogger(TencentSmsService.class);

    private final SmsProperties.Tencent config;
    private final ObjectMapper objectMapper;

    public TencentSmsService(SmsProperties.Tencent config) {
        this.config = config;
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public SmsResponse send(SmsRequest request) {
        logger.info("Sending SMS via Tencent to: {}", request.getPhoneNumber());

        try {
            String params = objectMapper.writeValueAsString(request.getTemplateParams());

            logger.info("Tencent SMS API called - Phone: {}, Template: {}, Params: {}",
                    request.getPhoneNumber(), request.getTemplateCode(), params);

            return new SmsResponse(true, "发送成功", generateRequestId());

        } catch (Exception e) {
            logger.error("Failed to send SMS via Tencent", e);
            return new SmsResponse(false, "发送失败: " + e.getMessage(), null);
        }
    }

    @Override
    public SmsResponse batchSend(String[] phoneNumbers, String templateCode,
                                 Map<String, String> templateParams) {
        logger.info("Batch sending {} SMS via Tencent", phoneNumbers.length);

        for (String phone : phoneNumbers) {
            SmsRequest request = new SmsRequest(phone, templateCode, templateParams);
            send(request);
        }

        return new SmsResponse(true, "批量发送完成", generateRequestId());
    }

    private String generateRequestId() {
        return "TC-" + System.currentTimeMillis();
    }
}
```

#### 第七步：自动配置类

```java
package com.example.sms.autoconfigure;

import com.example.sms.service.AliyunSmsService;
import com.example.sms.service.SmsService;
import com.example.sms.service.TencentSmsService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

@AutoConfiguration
@ConditionalOnProperty(prefix = "sms", name = "enabled", havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(SmsProperties.class)
public class SmsAutoConfiguration {

    private static final Logger logger = LoggerFactory.getLogger(SmsAutoConfiguration.class);

    /**
     * 阿里云短信服务
     */
    @Bean
    @ConditionalOnProperty(prefix = "sms", name = "provider", havingValue = "aliyun", matchIfMissing = true)
    @ConditionalOnMissingBean(SmsService.class)
    public SmsService aliyunSmsService(SmsProperties properties) {
        logger.info("Initializing Aliyun SMS Service");
        return new AliyunSmsService(properties.getAliyun());
    }

    /**
     * 腾讯云短信服务
     */
    @Bean
    @ConditionalOnProperty(prefix = "sms", name = "provider", havingValue = "tencent")
    @ConditionalOnMissingBean(SmsService.class)
    public SmsService tencentSmsService(SmsProperties properties) {
        logger.info("Initializing Tencent SMS Service");
        return new TencentSmsService(properties.getTencent());
    }

    /**
     * 异步线程池（可选）
     */
    @Bean("smsExecutor")
    @ConditionalOnProperty(prefix = "sms", name = "async", havingValue = "true")
    public Executor smsExecutor(SmsProperties properties) {
        logger.info("Initializing SMS Async Executor with pool size: {}",
                   properties.getThreadPoolSize());

        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(properties.getThreadPoolSize());
        executor.setMaxPoolSize(properties.getThreadPoolSize() * 2);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("sms-async-");
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(60);
        executor.initialize();

        return executor;
    }
}
```

#### 第八步：注册自动配置

创建文件：`src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`

```
com.example.sms.autoconfigure.SmsAutoConfiguration
```

#### 第九步：starter模块pom.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>sms-spring-boot-starter</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>sms-spring-boot-autoconfigure</artifactId>
            <version>${project.version}</version>
        </dependency>
    </dependencies>
</project>
```

### 4. 使用示例

#### (1) 添加依赖

```xml
<dependency>
    <groupId>com.example</groupId>
    <artifactId>sms-spring-boot-starter</artifactId>
    <version>1.0.0</version>
</dependency>
```

#### (2) 配置application.yml

```yaml
sms:
  enabled: true
  provider: aliyun  # 或 tencent
  async: false
  thread-pool-size: 10

  # 阿里云配置
  aliyun:
    access-key-id: LTAI5tXXXXXXXXXXXXXX
    access-key-secret: xxxxxxxxxxxxxxxxxxxxx
    sign-name: 我的签名
    template-code: SMS_123456789

  # 腾讯云配置
  tencent:
    secret-id: AKIDxxxxxxxxxxxxx
    secret-key: xxxxxxxxxxxxxxxxxxxxx
    sdk-app-id: 1400123456
    sign-name: 我的签名
    template-id: 123456
```

#### (3) 业务代码中使用

```java
@RestController
@RequestMapping("/sms")
public class SmsController {

    @Autowired
    private SmsService smsService;

    @PostMapping("/send")
    public String sendSms(@RequestParam String phone) {
        // 构建请求
        Map<String, String> params = new HashMap<>();
        params.put("code", "123456");
        params.put("time", "5");

        SmsRequest request = new SmsRequest(phone, null, params);

        // 发送短信
        SmsResponse response = smsService.send(request);

        return response.isSuccess() ? "发送成功" : "发送失败: " + response.getMessage();
    }

    @PostMapping("/batch-send")
    public String batchSend(@RequestBody String[] phones) {
        Map<String, String> params = new HashMap<>();
        params.put("content", "您有新的订单，请及时处理");

        SmsResponse response = smsService.batchSend(phones, null, params);

        return response.isSuccess() ? "批量发送成功" : "批量发送失败";
    }
}
```

### 5. 测试验证

```java
@SpringBootTest
public class SmsServiceTest {

    @Autowired
    private SmsService smsService;

    @Test
    public void testSendSms() {
        Map<String, String> params = new HashMap<>();
        params.put("code", "888888");

        SmsRequest request = new SmsRequest("13800138000", "SMS_123456", params);
        SmsResponse response = smsService.send(request);

        assertTrue(response.isSuccess());
        assertNotNull(response.getRequestId());
    }
}
```

### 6. 面试答题要点总结

**实现步骤**：
1. 创建autoconfigure模块：编写Properties、Service、AutoConfiguration
2. 创建starter模块：依赖autoconfigure
3. 注册自动配置：AutoConfiguration.imports
4. 打包发布：mvn install

**关键技术**：
- `@ConfigurationProperties`：绑定配置属性
- `@ConditionalOnProperty`：根据配置值选择服务商
- `@ConditionalOnMissingBean`：支持用户自定义覆盖
- `@EnableConfigurationProperties`：启用配置属性

**实战价值**：
- 统一封装：屏蔽不同服务商API差异
- 开箱即用：引入依赖+配置即可使用
- 灵活扩展：支持多服务商切换、异步发送等

这个Starter展示了工业级实现的完整流程，是面试中展示工程能力的优秀案例。
