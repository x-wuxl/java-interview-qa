---
layout: default
title: "SpringBoot如何做优雅停机？"
parent: Spring框架
nav_order: 478
description: "详解SpringBoot优雅停机原理和配置，包括内嵌容器关闭、请求处理完成、自定义清理逻辑等实现方案"
author: "wuxl"
date: 2025-11-02
---
## 问题

SpringBoot如何做优雅停机？

## 答案

### 1. 核心概念

优雅停机（Graceful Shutdown）是指应用在关闭前，等待正在处理的请求完成，拒绝新请求，执行清理逻辑，确保数据一致性和用户体验，避免强制中断导致的问题。

**优雅停机 vs 强制停机**：

| 对比项 | 强制停机 | 优雅停机 |
|-------|---------|---------|
| 执行方式 | kill -9 或直接关闭 | kill -15 或正常shutdown |
| 正在处理的请求 | 立即中断 | 等待处理完成 |
| 新请求 | 继续接收（直到端口关闭） | 立即拒绝 |
| 数据一致性 | 可能丢失 | 保证完整 |
| 用户体验 | 报错500/连接重置 | 正常返回或503 |

### 2. SpringBoot优雅停机配置

#### (1) 基础配置（SpringBoot 2.3+）

```yaml
server:
  shutdown: graceful  # 启用优雅停机（默认是immediate）

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # 最大等待时间（默认30秒）
```

**配置说明**：
- `server.shutdown=graceful`：启用优雅停机
- `timeout-per-shutdown-phase`：等待时间超过此值将强制关闭

#### (2) 不同容器的支持

| 容器 | SpringBoot版本 | 优雅停机支持 |
|-----|---------------|-------------|
| Tomcat | 2.3+ | ✅ 完全支持 |
| Jetty | 2.3+ | ✅ 完全支持 |
| Undertow | 2.3+ | ✅ 完全支持 |
| Netty (WebFlux) | 2.3+ | ✅ 完全支持 |

### 3. 优雅停机原理详解

#### (1) 完整流程

```
1. 接收关闭信号（SIGTERM: kill -15）
         ↓
2. 触发ApplicationContext.close()
         ↓
3. 发布ContextClosedEvent事件
         ↓
4. 停止接收新请求（关闭ServerConnector）
         ↓
5. 等待现有请求处理完成（最长timeout-per-shutdown-phase）
         ↓
6. 调用@PreDestroy方法
         ↓
7. 关闭Bean（按依赖顺序反向销毁）
         ↓
8. 关闭WebServer（Tomcat/Jetty等）
         ↓
9. 释放资源（数据库连接池、线程池等）
         ↓
10. 进程退出
```

#### (2) 源码分析

**WebServer关闭入口**：

```java
// GracefulShutdown.shutDownGracefully()
boolean shutDownGracefully(GracefulShutdownCallback callback) {
    logger.info("Commencing graceful shutdown. Waiting for active requests to complete");

    // 1. 标记为关闭状态，拒绝新请求
    this.shuttingDown = true;

    // 2. 等待活跃请求完成
    new Thread(() -> {
        try {
            this.aborted = !doShutdown(callback);
        } catch (Exception ex) {
            logger.error("Graceful shutdown failed", ex);
        }
    }, "shutdown-thread").start();

    return true;
}
```

**Tomcat优雅停机实现**：

```java
// TomcatGracefulShutdown.doShutdown()
private boolean doShutdown(GracefulShutdownCallback callback) {
    // 暂停Connector，不再接收新请求
    List<Connector> connectors = getConnectors();
    connectors.forEach(this::pauseConnector);

    // 等待活跃请求完成
    long deadline = System.currentTimeMillis() + this.timeout;
    while (hasActiveRequests() && System.currentTimeMillis() < deadline) {
        try {
            Thread.sleep(50);  // 每50ms检查一次
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    // 检查是否所有请求都处理完成
    boolean allRequestsCompleted = !hasActiveRequests();
    callback.shutdownComplete(allRequestsCompleted
        ? GracefulShutdownResult.REQUESTS_ACTIVE
        : GracefulShutdownResult.IDLE);

    return allRequestsCompleted;
}

private boolean hasActiveRequests() {
    for (Container host : this.tomcat.getEngine().findChildren()) {
        for (Container context : host.findChildren()) {
            if (isActive(context)) {
                return true;
            }
        }
    }
    return false;
}
```

### 4. 生产环境完整配置

#### (1) application.yml配置

```yaml
server:
  shutdown: graceful
  tomcat:
    connection-timeout: 20000  # 连接超时
    threads:
      max: 200
      min-spare: 10

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # 优雅停机等待时间

management:
  endpoints:
    web:
      exposure:
        include: health,shutdown  # 暴露shutdown端点
  endpoint:
    shutdown:
      enabled: true  # 启用shutdown端点（仅用于调试，生产慎用）
```

#### (2) 自定义清理逻辑

**方式一：@PreDestroy注解**

```java
@Component
public class ResourceCleanup {

    private static final Logger logger = LoggerFactory.getLogger(ResourceCleanup.class);

    @PreDestroy
    public void cleanup() {
        logger.info("Executing cleanup logic before shutdown...");

        // 关闭定时任务
        shutdownScheduledTasks();

        // 清理缓存
        clearCache();

        // 关闭第三方连接
        closeExternalConnections();

        logger.info("Cleanup completed");
    }

    private void shutdownScheduledTasks() {
        // 停止所有定时任务
    }

    private void clearCache() {
        // 清理本地缓存
    }

    private void closeExternalConnections() {
        // 关闭Redis、ES等连接
    }
}
```

**方式二：实现DisposableBean接口**

```java
@Component
public class CustomDisposableBean implements DisposableBean {

    @Override
    public void destroy() throws Exception {
        // 自定义销毁逻辑
        System.out.println("Destroying CustomDisposableBean");
    }
}
```

**方式三：监听ContextClosedEvent**

```java
@Component
public class ShutdownListener implements ApplicationListener<ContextClosedEvent> {

    private static final Logger logger = LoggerFactory.getLogger(ShutdownListener.class);

    @Override
    public void onApplicationEvent(ContextClosedEvent event) {
        logger.info("Application is shutting down, executing custom logic...");

        // 执行关闭前逻辑
        // 1. 从注册中心下线
        deregisterFromServiceRegistry();

        // 2. 等待一段时间，确保调用方感知到下线
        try {
            Thread.sleep(5000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // 3. 停止接收新任务
        stopAcceptingNewTasks();

        logger.info("Custom shutdown logic completed");
    }

    private void deregisterFromServiceRegistry() {
        // 从Nacos/Eureka等注册中心下线
    }

    private void stopAcceptingNewTasks() {
        // 停止消费MQ消息等
    }
}
```

### 5. 线程池优雅关闭

```java
@Configuration
public class ThreadPoolConfig {

    @Bean
    public ThreadPoolTaskExecutor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-task-");

        // 优雅关闭配置
        executor.setWaitForTasksToCompleteOnShutdown(true);  // 等待任务完成
        executor.setAwaitTerminationSeconds(60);  // 最长等待60秒

        executor.initialize();
        return executor;
    }
}
```

### 6. 数据库连接池优雅关闭

```yaml
spring:
  datasource:
    hikari:
      connection-timeout: 30000
      maximum-pool-size: 20
      # HikariCP会自动优雅关闭，等待活跃连接归还
```

### 7. 信号处理（Linux环境）

#### (1) 优雅停机信号

```bash
# 优雅停机（推荐）
kill -15 <pid>  # 或 kill -SIGTERM <pid>

# 强制停机（不推荐）
kill -9 <pid>   # 或 kill -SIGKILL <pid>
```

#### (2) Docker容器优雅停机

```dockerfile
FROM openjdk:17-jdk-slim

COPY target/app.jar /app.jar

# 设置STOP信号为SIGTERM（默认）
STOPSIGNAL SIGTERM

ENTRYPOINT ["java", "-jar", "/app.jar"]
```

**docker stop配置**：

```bash
# 等待30秒优雅停机，超时则强制kill
docker stop --time 30 container_name
```

**docker-compose配置**：

```yaml
services:
  app:
    image: myapp:latest
    stop_grace_period: 30s  # 优雅停机等待时间
```

### 8. Kubernetes优雅停机

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
      - name: myapp
        image: myapp:latest
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]  # 等待15秒
        ports:
        - containerPort: 8080

      terminationGracePeriodSeconds: 30  # Pod终止等待时间
```

**K8s优雅停机流程**：

```
1. Pod状态变为Terminating
         ↓
2. 从Service的Endpoints中移除（停止接收新流量）
         ↓
3. 执行preStop Hook（如sleep 15s，等待客户端感知）
         ↓
4. 发送SIGTERM信号给容器主进程
         ↓
5. 等待terminationGracePeriodSeconds（默认30s）
         ↓
6. 超时则发送SIGKILL强制终止
```

### 9. 验证优雅停机

#### (1) 测试脚本

```bash
#!/bin/bash

# 1. 启动应用
java -jar app.jar &
APP_PID=$!
echo "Application started with PID: $APP_PID"

# 2. 等待启动完成
sleep 10

# 3. 发送测试请求
while true; do
    curl -s http://localhost:8080/api/test
    sleep 0.5
done &
REQUEST_PID=$!

# 4. 等待5秒后优雅停机
sleep 5
echo "Sending SIGTERM to gracefully shutdown..."
kill -15 $APP_PID

# 5. 等待进程结束
wait $APP_PID
EXIT_CODE=$?

kill $REQUEST_PID

echo "Application exited with code: $EXIT_CODE"
```

#### (2) 日志观察

```
2023-11-02 10:30:00.123 INFO  - Commencing graceful shutdown. Waiting for active requests to complete
2023-11-02 10:30:05.456 INFO  - Graceful shutdown complete, 10 active requests completed
2023-11-02 10:30:05.789 INFO  - Executing cleanup logic before shutdown...
2023-11-02 10:30:06.123 INFO  - Cleanup completed
2023-11-02 10:30:06.456 INFO  - Closing ApplicationContext
```

### 10. 常见问题与最佳实践

#### 问题1：优雅停机超时后仍有请求在处理

**解决方案**：
- 增加`timeout-per-shutdown-phase`值
- 优化慢查询和长时间任务
- 对超长任务使用异步处理

#### 问题2：从注册中心下线不及时

**解决方案**：
```java
@Component
public class DeregisterListener implements ApplicationListener<ContextClosedEvent> {

    @Autowired
    private Registration registration;

    @Override
    public void onApplicationEvent(ContextClosedEvent event) {
        // 主动下线
        registration.deregister();

        // 等待客户端感知（推荐5-10秒）
        try {
            Thread.sleep(10000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

#### 问题3：数据库事务中断

**解决方案**：
- 设置合理的事务超时时间
- 优雅停机时间大于最长事务时间
- 避免长事务

### 11. 面试答题要点总结

**核心配置**：
1. `server.shutdown=graceful` 启用优雅停机
2. `spring.lifecycle.timeout-per-shutdown-phase` 设置等待时间

**原理流程**：
1. 接收SIGTERM信号
2. 停止接收新请求（暂停Connector）
3. 等待活跃请求完成（最长timeout时间）
4. 执行@PreDestroy清理逻辑
5. 关闭Bean和资源
6. 进程退出

**生产实践**：
1. 配置合理的超时时间（30-60秒）
2. 实现自定义清理逻辑（@PreDestroy、监听ContextClosedEvent）
3. 线程池配置`setWaitForTasksToCompleteOnShutdown(true)`
4. K8s配置preStop Hook和terminationGracePeriodSeconds
5. 从注册中心下线后等待一段时间再关闭

**一句话总结**：SpringBoot通过配置`server.shutdown=graceful`启用优雅停机，接收SIGTERM信号后停止接收新请求，等待现有请求处理完成（最长timeout时间），执行清理逻辑后关闭应用，确保服务平滑下线。
