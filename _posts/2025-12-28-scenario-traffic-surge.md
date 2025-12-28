---
layout: post
title: "QPS/TPS突然提升十倍甚至百倍，如何应对？"
date: 2025-12-28
categories: [大厂项目场景实战, 高并发实战]
tags: [高并发, 扩容, 限流, 降级, 弹性伸缩]
description: "讲解面对流量暴增的应对策略，包括横向扩容、限流降级、缓存加速等综合方案。"
---

# QPS/TPS突然提升十倍甚至百倍，如何应对？

## 面试场景

面试官："如果你的系统QPS突然从1000增长到10000，你怎么办？"

这道题考察**高并发应对能力**和**系统弹性**。

---

## 分析问题

首先要区分是**可预期**还是**突发**：

| 类型 | 示例 | 应对时间 |
|------|------|----------|
| 可预期 | 双11大促、活动上线 | 提前准备 |
| 突发 | 热点事件、病毒传播 | 即时响应 |

---

## 应对策略全景图

```
流量暴增应对
    │
    ├── 1. 横向扩容（增加处理能力）
    │
    ├── 2. 限流降级（保护系统）
    │
    ├── 3. 缓存加速（减少压力）
    │
    ├── 4. 异步削峰（平滑流量）
    │
    └── 5. 弹性伸缩（自动化）
```

---

## 策略一：横向扩容

### 应用服务器扩容

```bash
# K8s快速扩容
kubectl scale deployment order-service --replicas=20

# 或配置HPA自动扩容
kubectl autoscale deployment order-service \
  --min=5 --max=50 --cpu-percent=70
```

### 数据库扩容

| 层级 | 扩容方式 |
|------|----------|
| 读压力 | 增加从库 |
| 写压力 | 分库分表 |
| 连接数 | 连接池代理（如ProxySQL） |

### 缓存扩容

```bash
# Redis Cluster扩容
redis-cli --cluster add-node new-node:6379 existing-node:6379
redis-cli --cluster reshard existing-node:6379
```

---

## 策略二：限流降级

### 入口限流

```java
// Sentinel限流配置
FlowRule rule = new FlowRule();
rule.setResource("createOrder");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);
rule.setCount(1000);  // 限制1000 QPS
FlowRuleManager.loadRules(Collections.singletonList(rule));
```

### 分级限流

```
┌─────────────────────────────────────────────┐
│              总入口限流：10000 QPS           │
├─────────────────────────────────────────────┤
│  核心接口      │  非核心接口                  │
│  8000 QPS     │  2000 QPS                  │
├───────────────┼─────────────────────────────┤
│  VIP用户      │  普通用户                    │
│  优先保障     │  可限流                      │
└───────────────┴─────────────────────────────┘
```

### 功能降级

```java
@Component
public class DegradeConfig {
    
    @Value("${degrade.recommendation:true}")
    private boolean recommendationEnabled;
    
    @Value("${degrade.comment:true}")
    private boolean commentEnabled;
    
    public ProductVO getProductDetail(Long productId) {
        ProductVO vo = productService.getBasicInfo(productId);
        
        // 降级开关
        if (recommendationEnabled) {
            vo.setRecommendations(recommendService.getList(productId));
        }
        
        if (commentEnabled) {
            vo.setComments(commentService.getList(productId));
        }
        
        return vo;
    }
}
```

---

## 策略三：缓存加速

### 多级缓存

```
请求 → L1本地缓存（Caffeine）10ms内返回
         │ miss
         ↓
      L2分布式缓存（Redis）50ms内返回
         │ miss
         ↓
      L3数据库

命中率目标：L1 60% + L2 35% = 95%
```

### 热点数据探测

```java
@Scheduled(fixedRate = 60000)
public void detectHotspot() {
    // 统计最近1分钟访问最多的key
    List<String> hotKeys = accessCounter.getTopN(100);
    
    // 预加载到本地缓存
    for (String key : hotKeys) {
        Object value = redis.get(key);
        localCache.put(key, value);
    }
}
```

### 缓存预热

```java
@PostConstruct
public void warmUp() {
    // 系统启动时预热热点数据
    List<Long> hotProductIds = productService.getHotProductIds(1000);
    
    for (Long id : hotProductIds) {
        Product product = productMapper.findById(id);
        redisTemplate.opsForValue().set("product:" + id, product);
    }
}
```

---

## 策略四：异步削峰

### MQ缓冲

```
瞬时10万请求
    │
    ↓
┌─────────────┐
│   Kafka     │  缓冲压力
└─────────────┘
    │
    ↓ 匀速消费
┌─────────────┐
│  业务服务   │  1000 QPS处理
└─────────────┘
```

### 请求排队

```java
@RestController
public class OrderController {
    
    private BlockingQueue<OrderRequest> queue = new LinkedBlockingQueue<>(10000);
    
    @PostMapping("/order")
    public Result createOrder(@RequestBody OrderRequest request) {
        boolean offered = queue.offer(request, 100, TimeUnit.MILLISECONDS);
        if (!offered) {
            return Result.fail("系统繁忙，请稍后重试");
        }
        return Result.success("订单已提交，请耐心等待");
    }
    
    @Scheduled(fixedDelay = 10)
    public void processQueue() {
        OrderRequest request = queue.poll();
        if (request != null) {
            orderService.process(request);
        }
    }
}
```

---

## 策略五：弹性伸缩

### K8s HPA配置

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 5
  maxReplicas: 100
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: 1000
```

### 自定义扩容触发器

```java
@Scheduled(fixedRate = 10000)
public void checkAndScale() {
    double currentQps = metricsService.getCurrentQps();
    int currentReplicas = k8sService.getReplicas("order-service");
    
    // 预估需要的副本数
    int targetReplicas = (int) Math.ceil(currentQps / QPS_PER_POD);
    
    // 扩容（最多翻倍，避免过度扩容）
    if (targetReplicas > currentReplicas) {
        int newReplicas = Math.min(targetReplicas, currentReplicas * 2);
        k8sService.scale("order-service", newReplicas);
        log.info("扩容: {} → {}", currentReplicas, newReplicas);
    }
}
```

---

## 应急预案

### 分级响应

| 等级 | 触发条件 | 响应动作 |
|------|----------|----------|
| P0 | 系统崩溃 | 切流、回滚 |
| P1 | QPS超10倍 | 紧急扩容+限流 |
| P2 | QPS超5倍 | 扩容+降级非核心 |
| P3 | QPS超2倍 | 监控+准备扩容 |

### 快速止血清单

```
1. 开启限流（Sentinel控制台）
2. 关闭非核心功能（配置中心）
3. 紧急扩容（K8s快速扩容）
4. 切流到备用集群（如有）
5. 通知相关方（告警群）
```

---

## 面试答题框架

```
快速响应：
1. 限流保护系统（Sentinel/Nginx）
2. 降级非核心功能（配置开关）
3. 紧急扩容（K8s Scale）

深层优化：
4. 缓存加速（多级缓存）
5. 异步削峰（MQ缓冲）
6. 弹性伸缩（HPA自动扩缩）

预防措施：
- 压测确定系统容量
- 提前准备扩容资源
- 完善监控告警
```

---

## 总结

| 策略 | 作用 | 生效时间 |
|------|------|----------|
| 限流 | 保护系统不崩 | 秒级 |
| 降级 | 保核心舍边缘 | 秒级 |
| 扩容 | 提升处理能力 | 分钟级 |
| 缓存 | 减轻下游压力 | 需预热 |
| 削峰 | 平滑流量曲线 | 即时 |
