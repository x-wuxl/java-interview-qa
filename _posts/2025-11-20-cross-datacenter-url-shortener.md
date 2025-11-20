---
layout: post
title: "如何设计跨机房部署的短链服务？"
date: 2025-11-20 16:00:00 +0800
categories: [系统设计]
tags: [系统设计, 分布式, 短链服务, 多机房, 高可用, ID生成]
description: 详解跨机房部署的短链服务架构设计，包括全局唯一ID生成、多机房数据一致性、容灾切换、性能优化等核心技术方案。
---

## 一、核心概念

短链服务（URL Shortener）是将长网址转换为短网址的系统，典型应用如微博短链、营销推广链接等。**跨机房部署**需重点解决：

1. **全局唯一性**：不同机房生成的短链 ID 不能冲突
2. **高可用性**：单机房故障不影响整体服务
3. **数据一致性**：多机房间数据同步延迟与一致性保证
4. **就近访问**：用户请求路由到最近机房，降低延迟

## 二、原理与设计关键点

### 2.1 短链生成核心流程

#### 基本转换逻辑

```java
@Service
public class ShortUrlService {
    
    // 将长链转为短链
    public String getShortUrl(String longUrl) {
        // 1. 检查是否已存在（缓存 + DB）
        String existing = checkExisting(longUrl);
        if (existing != null) return existing;
        
        // 2. 生成全局唯一ID
        long id = idGenerator.nextId();
        
        // 3. ID转为62进制短码（a-z, A-Z, 0-9）
        String shortCode = base62Encode(id);
        
        // 4. 存储映射关系
        saveMapping(shortCode, longUrl);
        
        return "https://short.link/" + shortCode;
    }
    
    // 62进制编码
    private static final String CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    
    private String base62Encode(long num) {
        StringBuilder sb = new StringBuilder();
        while (num > 0) {
            sb.append(CHARS.charAt((int)(num % 62)));
            num /= 62;
        }
        return sb.reverse().toString();
    }
}
```

**为什么用 62 进制？**
- 7 位 62 进制可表示 `62^7 ≈ 3.5万亿` 个短链，足够使用
- URL 友好（不含特殊字符）

### 2.2 跨机房全局唯一 ID 生成

#### 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **号段模式** | 简单、高性能 | 需预分配号段、可能浪费 | 中小规模 |
| **雪花算法** | 趋势递增、性能高 | 依赖时钟、机器ID管理 | **推荐** |
| **Redis自增** | 实现简单 | 单点瓶颈、性能受限 | 小规模 |
| **UUID** | 完全分布式 | 不递增、太长（36位）| 不推荐 |

#### 推荐方案：雪花算法（Snowflake）改良版

**标准雪花算法结构**（64位）：

```
[1位符号] [41位时间戳] [5位数据中心ID] [5位机器ID] [12位序列号]
```

**跨机房优化改造**：

```
[1位符号] [41位时间戳] [3位机房ID] [7位机器ID] [12位序列号]
```

- **3 位机房 ID**：支持 8 个机房
- **7 位机器 ID**：每机房 128 台机器
- **12 位序列号**：每毫秒 4096 个 ID

```java
@Component
public class SnowflakeIdGenerator {
    private final long dataCenterId;  // 机房ID
    private final long workerId;      // 机器ID
    private long sequence = 0L;
    private long lastTimestamp = -1L;
    
    // 位移量
    private static final long DATACENTER_ID_BITS = 3L;
    private static final long WORKER_ID_BITS = 7L;
    private static final long SEQUENCE_BITS = 12L;
    
    private static final long WORKER_ID_SHIFT = SEQUENCE_BITS;
    private static final long DATACENTER_ID_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS;
    private static final long TIMESTAMP_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS + DATACENTER_ID_BITS;
    
    public SnowflakeIdGenerator(long dataCenterId, long workerId) {
        this.dataCenterId = dataCenterId;
        this.workerId = workerId;
    }
    
    public synchronized long nextId() {
        long timestamp = System.currentTimeMillis();
        
        // 时钟回拨检测
        if (timestamp < lastTimestamp) {
            throw new RuntimeException("Clock moved backwards!");
        }
        
        if (timestamp == lastTimestamp) {
            // 同一毫秒内，序列号自增
            sequence = (sequence + 1) & ((1 << SEQUENCE_BITS) - 1);
            if (sequence == 0) {
                // 序列号用完，等待下一毫秒
                timestamp = waitNextMillis(lastTimestamp);
            }
        } else {
            sequence = 0L;
        }
        
        lastTimestamp = timestamp;
        
        // 组装ID
        return ((timestamp - EPOCH) << TIMESTAMP_SHIFT)
                | (dataCenterId << DATACENTER_ID_SHIFT)
                | (workerId << WORKER_ID_SHIFT)
                | sequence;
    }
    
    private long waitNextMillis(long lastTimestamp) {
        long timestamp = System.currentTimeMillis();
        while (timestamp <= lastTimestamp) {
            timestamp = System.currentTimeMillis();
        }
        return timestamp;
    }
}
```

**机房 ID 与机器 ID 配置**：
- 通过 **配置中心**（Naomi/Apollo）动态下发
- 或从 **环境变量** 读取（K8s Pod 标签）

### 2.3 数据存储与同步

#### 核心表结构

```sql
CREATE TABLE t_short_url (
    id BIGINT PRIMARY KEY,              -- 雪花ID
    short_code VARCHAR(10) UNIQUE NOT NULL,  -- 短码（如 aBc123）
    long_url VARCHAR(2048) NOT NULL,    -- 原始长链
    expire_time DATETIME,               -- 过期时间（可选）
    create_time DATETIME NOT NULL,
    status TINYINT DEFAULT 1,           -- 状态（1有效 0失败）
    INDEX idx_long_url_hash (long_url(255))  -- 用HASH索引或MD5字段
) ENGINE=InnoDB;
```

#### 多机房数据同步策略

**方案一：主从异步复制**（推荐中小规模）

```
机房A（主）                机房B（从）
   ↓ 写入                     ↓ 只读
  MySQL Master  ────binlog──→ MySQL Slave
   ↑ 读取                     ↑ 读取
```

- **写请求**：统一路由到主机房
- **读请求**：就近访问本地机房（容忍秒级延迟）
- **优点**：实现简单、成本低
- **缺点**：主机房故障影响写入

**方案二：多主双写**（推荐大规模）

```java
@Service
public class MultiDataCenterShortUrlService {
    
    @Autowired
    private List<DataSource> dataSources;  // 多机房数据源
    
    public void saveMapping(String shortCode, String longUrl) {
        // 1. 写入本地机房（同步）
        saveToLocal(shortCode, longUrl);
        
        // 2. 异步同步到其他机房（MQ）
        for (DataCenter dc : otherDataCenters) {
            mqTemplate.send(dc.getSyncTopic(), new SyncEvent(shortCode, longUrl));
        }
    }
    
    // MQ消费者
    @RabbitListener(queues = "short-url-sync")
    public void handleSync(SyncEvent event) {
        // 幂等性检查（避免重复写入）
        if (!exists(event.getShortCode())) {
            saveToLocal(event.getShortCode(), event.getLongUrl());
        }
    }
}
```

**方案三：分布式数据库**（终极方案）
- 使用 **TiDB** / **OceanBase**：自动跨机房数据同步
- 使用 **Cassandra**：多数据中心拓扑、最终一致性

### 2.4 读取流程与缓存优化

#### 短链重定向流程

```java
@RestController
public class ShortUrlController {
    
    @GetMapping("/{shortCode}")
    public ResponseEntity<Void> redirect(@PathVariable String shortCode) {
        // 1. 查询长链（多级缓存）
        String longUrl = getLongUrl(shortCode);
        
        if (longUrl == null) {
            return ResponseEntity.notFound().build();
        }
        
        // 2. 302重定向到长链
        return ResponseEntity.status(HttpStatus.FOUND)
                .header(HttpHeaders.LOCATION, longUrl)
                .build();
    }
    
    private String getLongUrl(String shortCode) {
        // L1: 本地缓存（Caffeine，1分钟）
        String url = localCache.get(shortCode);
        if (url != null) return url;
        
        // L2: Redis缓存（10分钟）
        url = redisTemplate.opsForValue().get("short:" + shortCode);
        if (url != null) {
            localCache.put(shortCode, url);
            return url;
        }
        
        // L3: 数据库
        url = shortUrlMapper.selectByCode(shortCode);
        if (url != null) {
            redisTemplate.opsForValue().set("short:" + shortCode, url, 10, TimeUnit.MINUTES);
            localCache.put(shortCode, url);
        }
        return url;
    }
}
```

#### 缓存预热

- 通过 **访问日志分析** 提取热门短链
- 定时任务预加载到 Redis + 本地缓存

### 2.5 跨机房容灾与切换

#### 流量调度方案

**全局负载均衡**（GSLB）：
```
用户请求
   ↓
DNS解析（智能调度）
   ↓
┌──────┬──────┬──────┐
│ 机房A │ 机房B │ 机房C │
└──────┴──────┴──────┘
```

- **正常情况**：根据地理位置就近接入
- **机房故障**：DNS 秒级切换到健康机房

#### 故障检测与降级

```java
@Component
public class DataCenterHealthChecker {
    
    @Scheduled(fixedRate = 3000)  // 每3秒检测
    public void healthCheck() {
        for (DataCenter dc : allDataCenters) {
            boolean healthy = pingDataCenter(dc);
            if (!healthy) {
                // 标记为不可用，触发告警
                zkClient.setData("/dc/" + dc.getId() + "/status", "DOWN");
                alertService.send("机房" + dc.getId() + "异常！");
            }
        }
    }
}
```

**降级策略**：
- 写入失败时返回 503，引导用户重试
- 读取失败时查询其他机房（牺牲延迟保证可用性）

## 三、性能与分布式考量

### 3.1 性能优化

| 优化维度 | 方案 |
|----------|------|
| **缓存命中率** | 布隆过滤器前置（判断短码是否存在） |
| **DB压力** | 读写分离 + 分库分表（按短码前缀） |
| **网络延迟** | CDN 加速重定向响应 |
| **并发写入** | 批量插入 + 异步落库 |

### 3.2 一致性保证

1. **强一致性写入**：写入本地机房 MySQL 后才返回成功
2. **最终一致性同步**：通过 MQ 异步同步到其他机房
3. **冲突解决**：短码由全局唯一 ID 生成，天然无冲突

### 3.3 扩展性

- **水平扩展**：新增机房只需分配新的 `dataCenterId`
- **存储扩展**：按短码前缀分表（如 `a` 开头存 `t_short_url_a`）
- **ID容量**：雪花算法 41 位时间戳可用 69 年

### 3.4 安全与监控

**防刷机制**：
```java
// 基于IP的限流
@RateLimiter(key = "shorturl:create:#{request.remoteAddr}", rate = 10, per = 60)
public String createShortUrl(String longUrl) {
    // ...
}
```

**监控指标**：
- 短链生成 QPS、RT
- 各机房数据同步延迟
- 缓存命中率
- 机房健康度

## 四、答题总结

**核心架构设计**：
1. **ID 生成**：改良雪花算法（3位机房ID + 7位机器ID）保证全局唯一
2. **数据同步**：
   - 中小规模：主从异步复制
   - 大规模：多主双写 + MQ 异步同步
3. **缓存策略**：本地缓存 + Redis 二级缓存，布隆过滤器防穿透
4. **容灾切换**：GSLB 智能调度 + 健康检查自动摘除故障机房

**面试加分项**：
- 提及 **302 vs 301**：短链建议用 302（便于统计、修改）
- 提及 **短码回收**：过期短链定期回收释放 ID 空间
- 提及 **数据分析**：通过 ClickHouse 存储访问日志做实时分析
- 提及 **长链去重**：对长链做 MD5 并建索引，避免重复生成
