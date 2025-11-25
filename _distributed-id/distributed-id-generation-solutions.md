---
title: "分布式ID生成方案有哪些？"
date: 2025-11-02
description: "详细介绍分布式系统中常见的ID生成方案，包括数据库自增、UUID、雪花算法、Redis、数据库号段模式等，并对比各方案的优缺点和适用场景"
author: "wuxl"
categories: [分布式]
tags: [分布式ID, UUID, 雪花算法, 数据库, Redis, 号段模式]
nav_order: 501
parent: 分布式ID
---
## 问题

分布式ID生成方案有哪些？

## 答案

### 1. 核心概念

分布式ID是在分布式系统中用于唯一标识数据的全局唯一标识符。好的分布式ID方案需要满足：
- **全局唯一性**：确保生成的ID在整个系统中唯一
- **高可用性**：ID生成服务需要高度可用
- **高性能**：能够快速生成大量ID
- **趋势递增**：有利于数据库索引性能（可选）
- **信息安全**：不暴露业务信息（可选）

### 2. 常见方案及原理

#### 方案1：数据库自增ID

**实现方式**：
```sql
CREATE TABLE id_generator (
    id BIGINT NOT NULL AUTO_INCREMENT,
    stub CHAR(1) NOT NULL DEFAULT '',
    PRIMARY KEY (id),
    UNIQUE KEY (stub)
) ENGINE=MyISAM;

-- 获取ID
REPLACE INTO id_generator (stub) VALUES ('a');
SELECT LAST_INSERT_ID();
```

**优点**：
- 实现简单，利用数据库原生特性
- ID递增，有序

**缺点**：
- 性能瓶颈：数据库压力大
- 单点故障风险
- 水平扩展困难

**优化方案**：
- 双主模式：设置不同的起始值和步长（Master1: 1,3,5... Master2: 2,4,6...）
- 多主模式：多台MySQL，每台设置不同的初始值和相同的步长

#### 方案2：UUID

**实现方式**：
```java
import java.util.UUID;

public class UUIDGenerator {
    public static String generate() {
        return UUID.randomUUID().toString().replace("-", "");
    }
}
```

**优点**：
- 本地生成，无网络消耗
- 性能高
- 全局唯一性有保障

**缺点**：
- 占用空间大（128位，通常用36字符字符串表示）
- 无序性，不利于MySQL索引（页分裂严重）
- 不具备业务含义
- 可读性差

**适用场景**：对性能要求不高、对ID顺序无要求的场景（如日志追踪ID）

#### 方案3：雪花算法（Snowflake）

**结构组成**（64位）：
```
0 - 0000000000 0000000000 0000000000 0000000000 0 - 00000 - 00000 - 000000000000
|   |-------------------------------------------|   |-----|   |-----|   |---------|
符  |                 41位时间戳                |    5位     5位       12位
号  |          (精确到毫秒，可用69年)           | 数据中心ID 机器ID    序列号
位  |                                          |          |         |
    |                                          |          |         └─ 同一毫秒内的序列号
    |                                          |          |             (最多4096个)
    |                                          |          └─ 机器ID (最多32台机器)
    |                                          └─ 数据中心ID (最多32个数据中心)
    └─ 符号位 (始终为0)
```

**实现示例**：
```java
public class SnowflakeIdGenerator {
    private final long twepoch = 1288834974657L; // 起始时间戳
    private final long datacenterIdBits = 5L;
    private final long workerIdBits = 5L;
    private final long sequenceBits = 12L;

    private final long maxDatacenterId = -1L ^ (-1L << datacenterIdBits);
    private final long maxWorkerId = -1L ^ (-1L << workerIdBits);
    private final long sequenceMask = -1L ^ (-1L << sequenceBits);

    private final long workerIdShift = sequenceBits;
    private final long datacenterIdShift = sequenceBits + workerIdBits;
    private final long timestampLeftShift = sequenceBits + workerIdBits + datacenterIdBits;

    private long datacenterId;
    private long workerId;
    private long sequence = 0L;
    private long lastTimestamp = -1L;

    public SnowflakeIdGenerator(long datacenterId, long workerId) {
        if (datacenterId > maxDatacenterId || datacenterId < 0) {
            throw new IllegalArgumentException("datacenter Id can't be greater than " + maxDatacenterId + " or less than 0");
        }
        if (workerId > maxWorkerId || workerId < 0) {
            throw new IllegalArgumentException("worker Id can't be greater than " + maxWorkerId + " or less than 0");
        }
        this.datacenterId = datacenterId;
        this.workerId = workerId;
    }

    public synchronized long nextId() {
        long timestamp = System.currentTimeMillis();

        // 时钟回拨检测
        if (timestamp < lastTimestamp) {
            throw new RuntimeException("Clock moved backwards. Refusing to generate id");
        }

        // 同一毫秒内
        if (lastTimestamp == timestamp) {
            sequence = (sequence + 1) & sequenceMask;
            if (sequence == 0) {
                // 序列号溢出，等待下一毫秒
                timestamp = tilNextMillis(lastTimestamp);
            }
        } else {
            sequence = 0L;
        }

        lastTimestamp = timestamp;

        return ((timestamp - twepoch) << timestampLeftShift)
                | (datacenterId << datacenterIdShift)
                | (workerId << workerIdShift)
                | sequence;
    }

    private long tilNextMillis(long lastTimestamp) {
        long timestamp = System.currentTimeMillis();
        while (timestamp <= lastTimestamp) {
            timestamp = System.currentTimeMillis();
        }
        return timestamp;
    }
}
```

**优点**：
- 高性能：本地生成，无网络开销
- 趋势递增：按时间自增，对索引友好
- 灵活：可自定义各部分位数
- 信息可携带：包含时间戳、机器ID等信息

**缺点**：
- 依赖系统时钟：时钟回拨会导致ID重复
- 分布式环境需要协调机器ID
- 强依赖机器时钟，时间回拨会造成ID重复或服务不可用

#### 方案4：Redis生成ID

**实现方式**：
```java
public class RedisIdGenerator {
    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    public Long generateId(String key) {
        String dateKey = key + LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
        return redisTemplate.opsForValue().increment(dateKey);
    }
}
```

**优点**：
- 性能优异：Redis基于内存
- 有序递增
- 实现简单

**缺点**：
- 依赖Redis：需要保证Redis的高可用
- 占用内存
- 网络开销

**优化**：
- 使用Redis主从+哨兵模式保证高可用
- 批量获取ID，减少网络请求

#### 方案5：数据库号段模式

**原理**：每次从数据库批量获取一段ID号段，用完再取下一段。

**实现思路**：
```sql
CREATE TABLE id_segment (
    biz_type VARCHAR(63) NOT NULL COMMENT '业务类型',
    max_id BIGINT NOT NULL COMMENT '当前最大ID',
    step INT NOT NULL COMMENT '号段步长',
    version INT NOT NULL COMMENT '版本号-乐观锁',
    PRIMARY KEY (biz_type)
);

-- 获取号段（使用乐观锁）
UPDATE id_segment
SET max_id = max_id + step, version = version + 1
WHERE biz_type = 'order' AND version = #{currentVersion};
```

```java
public class SegmentIdGenerator {
    private long currentId;
    private long maxId;
    private int step;

    public synchronized long nextId(String bizType) {
        if (currentId >= maxId) {
            // 从数据库获取新号段
            Segment segment = fetchSegmentFromDb(bizType);
            currentId = segment.getMaxId() - segment.getStep();
            maxId = segment.getMaxId();
            step = segment.getStep();
        }
        return ++currentId;
    }
}
```

**优点**：
- 减少数据库访问频率
- ID有序递增
- 可根据业务调整步长

**缺点**：
- 重启服务可能造成ID段浪费
- 仍有数据库依赖

**开源实现**：美团的Leaf-segment

#### 方案6：第三方ID生成服务

**常见框架**：
- **美团Leaf**：支持号段模式和Snowflake模式
- **百度UidGenerator**：基于Snowflake改进
- **滴滴TinyId**：基于号段模式

### 3. 方案选型建议

| 方案 | 性能 | 有序性 | 复杂度 | 适用场景 |
|------|------|--------|--------|----------|
| 数据库自增 | ★★☆ | ★★★ | ★☆☆ | 并发低、数据量小 |
| UUID | ★★★ | ☆☆☆ | ★☆☆ | 对顺序无要求、快速生成 |
| 雪花算法 | ★★★ | ★★☆ | ★★☆ | 高并发、需趋势递增 |
| Redis | ★★★ | ★★★ | ★★☆ | 有Redis环境、需有序 |
| 号段模式 | ★★★ | ★★★ | ★★☆ | 多业务类型、需有序 |

### 4. 实际应用总结

**互联网公司常用方案**：
- **订单ID**：雪花算法或号段模式（需要趋势递增）
- **用户ID**：雪花算法（全局唯一、高性能）
- **日志追踪ID**：UUID（简单快速）
- **消息ID**：雪花算法 + Redis（高并发场景）

**最佳实践**：
1. **中小型系统**：Redis + 号段模式（实现简单）
2. **大型系统**：雪花算法 + 时钟回拨处理
3. **超大型系统**：自研或使用美团Leaf等成熟方案

**关键考量点**：
- 是否需要有序性（影响数据库索引性能）
- 并发量级（决定性能要求）
- 是否需要包含业务信息
- 运维复杂度接受程度
