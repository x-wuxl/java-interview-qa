---
title: "当项目访问量激增时如何应对？"
date: 2025-11-20
categories: [架构, 性能优化]
tags: [高并发, 缓存, 限流, 降级, 扩容]
description: "系统化解析流量激增场景下的应对策略，涵盖缓存、限流、降级、扩容等核心手段"
nav_order: 604
parent: 架构设计与实战
---
## 一、问题分析

**访问量激增场景**：
- 营销活动（双11、618）
- 突发热点（明星八卦、突发新闻）
- 恶意攻击（DDoS）

**核心挑战**：
- 数据库成为瓶颈
- 服务响应变慢
- 资源耗尽宕机

---

## 二、应对策略全景图

```
┌────────────────────────────────────────┐
│           流量入口层                    │
│  CDN → DNS 调度 → 负载均衡              │
└─────────────┬──────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│          接入层防护                     │
│  限流 → 黑白名单 → 防刷                 │
└─────────────┬──────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│          应用层优化                     │
│  缓存 → 降级 → 熔断 → 异步              │
└─────────────┬──────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│          数据层优化                     │
│  读写分离 → 分库分表 → 索引优化         │
└────────────────────────────────────────┘
```

---

## 三、分层应对方案

### 1. 流量入口层

#### （1）CDN 静态资源加速

```nginx
# 静态资源配置 CDN
location ~* \.(jpg|png|js|css)$ {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

**效果**：分流 70% 静态资源请求

#### （2）DNS 智能调度

- 地域就近接入（华东用户 → 杭州机房）
- 故障自动切换

#### （3）负载均衡

```yaml
# Nginx 负载均衡
upstream backend {
    server 192.168.1.10:8080 weight=3;
    server 192.168.1.11:8080 weight=2;
    server 192.168.1.12:8080 backup;  # 备用节点
}
```

---

### 2. 接入层防护

#### （1）限流

**令牌桶算法**（Guava RateLimiter）

```java
@RestController
public class OrderController {
    
    // 每秒放行 100 个请求
    private final RateLimiter limiter = RateLimiter.create(100);
    
    @PostMapping("/order")
    public Result createOrder() {
        if (!limiter.tryAcquire()) {
            return Result.fail("系统繁忙，请稍后重试");
        }
        return orderService.create();
    }
}
```

**Sentinel 规则**

```java
// 热点参数限流：同一用户每秒最多 10 次
@SentinelResource(value = "createOrder")
public void create(Long userId) {
    // 业务逻辑
}

// 规则配置
ParamFlowRule rule = new ParamFlowRule("createOrder")
    .setParamIdx(0)  // 第一个参数 userId
    .setCount(10);
```

#### （2）黑白名单

```java
// IP 黑名单拦截
@Component
public class IpFilter implements Filter {
    private static final Set<String> BLACKLIST = Set.of(
        "192.168.1.100", "10.0.0.50"
    );
    
    @Override
    public void doFilter(ServletRequest request, ...) {
        String ip = request.getRemoteAddr();
        if (BLACKLIST.contains(ip)) {
            throw new ForbiddenException();
        }
        chain.doFilter(request, response);
    }
}
```

---

### 3. 应用层优化

#### （1）多级缓存

```java
// 本地缓存 + Redis
@Service
public class ProductService {
    
    @Cacheable(value = "product", key = "#id")
    public Product getById(Long id) {
        // 查数据库
        return productRepository.findById(id);
    }
}

// 缓存架构
浏览器缓存 (CDN)
    ↓
Nginx 本地缓存
    ↓
应用进程缓存 (Caffeine)
    ↓
Redis 集群
    ↓
数据库
```

#### （2）降级

```java
// Hystrix 降级示例
@HystrixCommand(fallbackMethod = "getDefaultRecommend")
public List<Product> getRecommend(Long userId) {
    // 调用推荐服务（高延迟）
    return recommendService.query(userId);
}

// 降级方法：返回默认推荐
public List<Product> getDefaultRecommend(Long userId) {
    return hotProductCache.get();  // 热门商品兜底
}
```

#### （3）异步化

```java
// 订单创建异步化
@PostMapping("/order")
public Result create(@RequestBody OrderDTO dto) {
    // 1. 同步校验库存（快速失败）
    if (!stockService.check(dto.getProductId())) {
        return Result.fail("库存不足");
    }
    
    // 2. 异步创建订单
    CompletableFuture.runAsync(() -> {
        orderService.create(dto);
    });
    
    // 3. 立即返回（前端轮询结果）
    return Result.success("订单创建中");
}
```

---

### 4. 数据层优化

#### （1）读写分离

```yaml
# ShardingSphere 配置
spring:
  shardingsphere:
    datasource:
      names: master,slave0,slave1
      master:
        url: jdbc:mysql://master:3306/db
      slave0:
        url: jdbc:mysql://slave0:3306/db
    rules:
      readwrite-splitting:
        data-sources:
          ds:
            write-data-source-name: master
            read-data-source-names: slave0,slave1
```

#### （2）分库分表

```java
// 按用户 ID 哈希分库
@TableSharding(shardingColumns = "user_id", 
               algorithmType = "HASH_MOD")
public class Order {
    private Long userId;
    // ...
}
```

#### （3）索引优化

```sql
-- 慢查询优化
-- 原 SQL（全表扫描）
SELECT * FROM order WHERE created_time > '2025-01-01';

-- 优化：添加索引
CREATE INDEX idx_created_time ON order(created_time);

-- 覆盖索引（避免回表）
CREATE INDEX idx_user_status ON order(user_id, status);
SELECT status FROM order WHERE user_id = 123;
```

---

## 四、秒杀场景专项方案

### 架构设计

```
用户请求
  ↓
CDN (静态页面)
  ↓
API 网关 (限流 1 万 QPS)
  ↓
Redis 预减库存 (Lua 原子操作)
  ↓ (通过)
MQ 异步下单 (削峰)
  ↓
订单服务 (扣减数据库库存)
```

### Redis 预减库存

```lua
-- Lua 脚本保证原子性
local stock = redis.call('GET', KEYS[1])
if tonumber(stock) > 0 then
    redis.call('DECR', KEYS[1])
    return 1
else
    return 0
end
```

```java
@Service
public class SeckillService {
    
    public boolean seckill(Long productId, Long userId) {
        String key = "seckill:stock:" + productId;
        
        // 1. Redis 预减库存
        Long result = redisTemplate.execute(luaScript, 
            Collections.singletonList(key));
        if (result == 0) {
            return false;  // 库存不足
        }
        
        // 2. 发送 MQ 异步创建订单
        rabbitTemplate.convertAndSend("order.queue", 
            new OrderMessage(productId, userId));
        
        return true;
    }
}
```

---

## 五、扩容方案

### 1. 水平扩容

```bash
# K8s 自动扩容
kubectl autoscale deployment app \
  --cpu-percent=70 \
  --min=3 \
  --max=20

# 阿里云 ECS 弹性伸缩
aliyun ess CreateScalingRule \
  --ScalingGroupId asg-xxx \
  --AdjustmentType QuantityChangeInCapacity \
  --AdjustmentValue 5  # 流量高峰加 5 台
```

### 2. 数据库扩容

```sql
-- MySQL 分表（按月）
CREATE TABLE order_202511 LIKE order;
CREATE TABLE order_202512 LIKE order;

-- 应用层路由
int month = LocalDate.now().getMonthValue();
String tableName = "order_2025" + String.format("%02d", month);
```

---

## 六、监控预警

### Prometheus 告警规则

```yaml
groups:
- name: high_traffic
  rules:
  - alert: HighQPS
    expr: sum(rate(http_requests_total[1m])) > 10000
    for: 1m
    annotations:
      summary: "QPS 超过 1 万"
  
  - alert: HighErrorRate
    expr: rate(http_errors_total[1m]) / rate(http_requests_total[1m]) > 0.05
    annotations:
      summary: "错误率超过 5%"
```

---

## 七、实战案例：双11大促

### 准备阶段

1. **全链路压测**：模拟 10 倍流量
2. **资源预留**：提前扩容至日常 3 倍
3. **降级预案**：非核心功能（推荐、评价）可降级

### 当天执行

```
00:00 活动开始
  ├─ CDN 命中率 95%（静态资源）
  ├─ Redis QPS 50 万（库存查询）
  ├─ MQ 积压 10 万（异步创建订单）
  └─ 数据库 QPS 5000（从库读取）

10:00 流量回落
  └─ 自动缩容至 1.5 倍日常
```

---

## 八、答题总结

**3 分钟框架**：

### 1. 分层策略（1分钟）

| 层级 | 手段 | 工具 |
|------|------|------|
| 入口层 | CDN + 负载均衡 | 阿里云 CDN |
| 接入层 | 限流 + 黑名单 | Sentinel |
| 应用层 | 缓存 + 降级 + 异步 | Redis + Hystrix |
| 数据层 | 读写分离 + 分库分表 | ShardingSphere |

### 2. 核心技术（1分钟）

- **限流**：令牌桶（100 QPS）
- **缓存**：多级（本地 + Redis）
- **异步**：MQ 削峰（订单入队）
- **扩容**：K8s HPA（CPU > 70% 扩容）

### 3. 秒杀方案（1分钟）

```
Redis 预减库存 → MQ 异步下单 → 数据库扣减
```

**加分点**：
- 提及具体数据（CDN 分流 70%、Redis QPS 50 万）
- 全链路压测、监控预警
- 实战案例（双11 准备）
