---
layout: post
title: "MySQL主从库的读操作有几种分配策略？"
date: 2025-12-28
categories: [大厂项目场景实战, 数据库高可用]
tags: [MySQL, 读写分离, 主从复制, 高可用]
description: "讲解MySQL读写分离的多种策略，包括强制主库、延迟检测、半同步等方案。"
---

# MySQL主从库的读操作有几种分配策略？

## 面试场景

面试官："你们的数据库做了读写分离吗？读操作怎么分配的？"

读写分离是数据库高可用的基础方案，但"从库读"存在数据延迟问题，需要有策略应对。

---

## 读写分离基础

### 架构图

```
       ┌────────────────┐
       │   应用服务      │
       └───────┬────────┘
               │
       ┌───────┴────────┐
       │  读写分离代理   │
       └───────┬────────┘
               │
       ┌───────┴────────────────┐
       │                        │
  ┌────┴────┐           ┌──────┴──────┐
  │  主库   │ ─同步复制→ │  从库1/从库2│
  │ (写)    │           │   (读)      │
  └─────────┘           └─────────────┘
```

### 核心问题

主从复制存在**延迟**，从库读到的可能是旧数据。

```
时间线：
T1: 主库写入数据
T2: 用户查询从库 → 数据还没同步过来！
T3: 从库同步完成
```

---

## 策略一：强制读主库

### 适用场景
对数据实时性要求极高的查询。

### 实现方式

```java
@Service
public class OrderService {
    
    @Autowired
    @Qualifier("masterDataSource")
    private DataSource masterDataSource;
    
    // 订单创建后立即查询，走主库
    @Transactional
    public OrderVO createAndQuery(OrderRequest request) {
        Order order = createOrder(request);
        
        // 使用主库数据源查询
        return queryFromMaster(order.getId());
    }
}
```

### 注解方式

```java
// 自定义注解
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ForceMaster {
}

// 拦截器切换数据源
@Aspect
@Component
public class DataSourceAspect {
    
    @Around("@annotation(ForceMaster)")
    public Object forceMaster(ProceedingJoinPoint pjp) throws Throwable {
        DynamicDataSource.setMaster();
        try {
            return pjp.proceed();
        } finally {
            DynamicDataSource.clear();
        }
    }
}

// 使用
@ForceMaster
public Order getOrder(Long orderId) {
    return orderMapper.findById(orderId);
}
```

---

## 策略二：延迟检测

### 原理
查询从库前，检查主从延迟是否在可接受范围内。

### 实现方式

```java
public Order getOrder(Long orderId) {
    // 检查从库延迟
    long lag = getReplicationLag();
    
    if (lag > 1000) {  // 延迟超过1秒
        return queryFromMaster(orderId);
    } else {
        return queryFromSlave(orderId);
    }
}

private long getReplicationLag() {
    // 查询从库状态
    // SHOW SLAVE STATUS
    Map<String, Object> status = jdbcTemplate.queryForMap("SHOW SLAVE STATUS");
    return (Long) status.get("Seconds_Behind_Master");
}
```

### 缺点
- 每次查询都要检测延迟，有性能开销
- 延迟值不完全准确

---

## 策略三：写后强制主库时间窗口

### 原理
写操作后N秒内，该用户的读操作都走主库。

### 实现方式

```java
@Service
public class OrderService {
    
    private static final String WRITE_FLAG = "user:write:flag:";
    
    @Autowired
    private RedisTemplate<String, String> redis;
    
    public Order createOrder(OrderRequest request) {
        Order order = doCreate(request);
        
        // 标记该用户刚执行过写操作，5秒内读走主库
        redis.opsForValue().set(
            WRITE_FLAG + request.getUserId(), 
            "1", 
            5, TimeUnit.SECONDS
        );
        
        return order;
    }
    
    public Order getOrder(Long userId, Long orderId) {
        // 检查是否有写标记
        String flag = redis.opsForValue().get(WRITE_FLAG + userId);
        
        if ("1".equals(flag)) {
            return queryFromMaster(orderId);
        } else {
            return queryFromSlave(orderId);
        }
    }
}
```

---

## 策略四：半同步复制

### 原理
主库等待至少一个从库确认收到binlog后才返回。

### MySQL配置

```sql
-- 主库
SET GLOBAL rpl_semi_sync_master_enabled = 1;
SET GLOBAL rpl_semi_sync_master_timeout = 1000;  -- 1秒超时

-- 从库
SET GLOBAL rpl_semi_sync_slave_enabled = 1;
```

### 优缺点

| 优点 | 缺点 |
|------|------|
| 数据强一致 | 写性能下降 |
| 无需应用层控制 | 网络抖动影响可用性 |

---

## 策略五：MGR组复制

### 原理
MySQL Group Replication，多主模式，Paxos协议保证一致性。

```
┌──────────────────────────────────────┐
│            MGR 集群                   │
├──────────────────────────────────────┤
│  节点1 ←→ 节点2 ←→ 节点3              │
│  (主)     (主)     (主)              │
│  读写     读写     读写              │
└──────────────────────────────────────┘
```

**特点**：
- 任意节点都可读写
- 数据强一致
- 自动故障切换

---

## 策略对比

| 策略 | 一致性 | 性能 | 复杂度 | 适用场景 |
|------|--------|------|--------|----------|
| 强制主库 | 强 | 差 | 低 | 关键查询 |
| 延迟检测 | 中 | 中 | 中 | 通用 |
| 写后窗口 | 中 | 好 | 中 | 常见选择 |
| 半同步 | 强 | 差 | 低 | 金融级 |
| MGR | 强 | 中 | 高 | 新项目 |

---

## 中间件支持

### ShardingSphere读写分离

```yaml
spring:
  shardingsphere:
    rules:
      readwrite-splitting:
        data-sources:
          rw:
            write-data-source-name: master
            read-data-source-names:
              - slave1
              - slave2
            load-balancer-name: round-robin
        load-balancers:
          round-robin:
            type: ROUND_ROBIN
```

### Hint强制主库

```java
// ShardingSphere Hint
try (HintManager hintManager = HintManager.getInstance()) {
    hintManager.setWriteRouteOnly();  // 强制走主库
    return orderMapper.findById(orderId);
}
```

---

## 面试答题框架

```
读写分离问题：主从延迟导致读到旧数据

解决策略：
1. 强制主库：关键查询走主库
2. 延迟检测：延迟大时切主库
3. 写后窗口：写操作后N秒读主库
4. 半同步复制：等从库确认
5. MGR组复制：强一致集群

常用方案：
- 业务层：自定义@ForceMaster注解
- 中间件：ShardingSphere读写分离
- 数据库：半同步/MGR
```

---

## 总结

| 场景 | 推荐策略 |
|------|----------|
| 写后立即读 | 强制主库/写后窗口 |
| 普通查询 | 从库 + 延迟检测 |
| 金融级业务 | 半同步/MGR |
| 报表查询 | 从库（允许延迟） |
