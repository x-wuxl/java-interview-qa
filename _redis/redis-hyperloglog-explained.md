---
title: "Redis的HyperLogLog了解过吗？"
date: 2025-11-02
description: "深入解析Redis HyperLogLog的原理、应用场景及优缺点，包括基数估算算法、内存优化和UV统计最佳实践"
author: "wuxl"
categories: [中间件]
tags: [Redis, HyperLogLog, 基数统计, 算法]
nav_order: 412
parent: Redis
---
## 问题

Redis的HyperLogLog了解过吗？

## 答案

### 1. 核心概念

**HyperLogLog（HLL）**是一种**概率性数据结构**，用于**基数统计**（统计集合中不重复元素的数量）。Redis的HLL实现用**12KB内存**即可估算**2^64个元素的基数**，标准误差率仅为**0.81%**。

---

### 2. 应用场景

#### 2.1 典型场景：UV（独立访客）统计

**传统方案**：Set存储
```bash
# 每天一个Set
SADD uv:2024-11-02 "user:1001" "user:1002" ...
SCARD uv:2024-11-02  # 统计UV

# 问题：1亿UV需要约1.6GB内存
# 1亿 * 16字节（假设ID平均长度）= 1.6GB
```

**HLL方案**：
```bash
# 每天一个HLL
PFADD uv:2024-11-02 "user:1001" "user:1002" ...
PFCOUNT uv:2024-11-02  # 统计UV

# 优势：固定12KB，误差0.81%
# 1亿UV仍然只需12KB！
```

**内存对比**：
| UV数量 | Set内存 | HLL内存 | 内存节省 |
|--------|---------|---------|----------|
| 1万 | 160KB | 12KB | 92% |
| 100万 | 16MB | 12KB | 99.9% |
| 1亿 | 1.6GB | 12KB | 99.999% |

---

#### 2.2 其他应用场景

**页面访问统计**：
```bash
PFADD page:1001:uv "user:1001" "user:1001" "user:1002"
PFCOUNT page:1001:uv  # 结果：2（自动去重）
```

**搜索词统计**：
```bash
PFADD search:keywords "redis" "mysql" "redis"
PFCOUNT search:keywords  # 统计不重复搜索词数量
```

**IP去重统计**：
```bash
PFADD ip:access "192.168.1.1" "192.168.1.2" ...
PFCOUNT ip:access
```

---

### 3. HyperLogLog原理

#### 3.1 核心思想：伯努利试验

**问题**：扔硬币，首次出现正面前扔了几次？

**推论**：
- 首次正面在第k次出现的概率：1/2^k
- 如果n次试验中，最大k值为k_max
- 则n ≈ 2^k_max

**基数估算类比**：
```java
// 将每个元素hash后看作一次"扔硬币"
hash("user:1001") = 0b00101000... 
// 前导0的个数 = 2（相当于第3次才出现正面）

// 如果10000个元素中，最大前导0个数为15
// 估算基数 = 2^15 ≈ 32768
```

---

#### 3.2 LogLog算法

**问题**：单次试验误差大

**改进**：分桶平均
```java
1. 将hash值分为两部分：
   - 前p位：决定桶号（2^p个桶）
   - 后64-p位：计算前导0个数

2. 每个桶独立估算
3. 调和平均求总基数

// Redis使用16384个桶（p=14）
基数估算 = 常数 * 桶数^2 / Σ(2^(-桶值))
```

---

#### 3.3 HyperLogLog优化

**改进点**：
1. **稀疏表示**：元素少时用稀疏编码，节省内存
2. **密集表示**：元素多时转换为密集数组（12KB固定）
3. **偏差修正**：针对小基数和大基数的修正算法

**Redis的实现**：
```c
// 稀疏编码（元素少时）
struct hllhdr {
    char magic[4];      // "HYLL"
    uint8_t encoding;   // HLL_SPARSE or HLL_DENSE
    uint8_t notused[3];
    uint8_t card[8];    // 缓存的基数估算
    uint8_t registers[];// 寄存器数组
};

// 密集编码（元素多时）
16384个6位寄存器 = 16384 * 6 / 8 = 12288字节 ≈ 12KB
```

---

### 4. Redis HLL命令详解

#### 4.1 PFADD（添加元素）

```bash
PFADD key element [element ...]
```

**示例**：
```bash
PFADD uv:2024-11-02 "user:1001" "user:1002" "user:1001"
# 返回：1（表示基数估算值发生变化）

PFADD uv:2024-11-02 "user:1001"
# 返回：0（user:1001已存在，无变化）
```

**Java实现**：
```java
redisTemplate.opsForHyperLogLog().add("uv:2024-11-02", "user:1001", "user:1002");
```

---

#### 4.2 PFCOUNT（统计基数）

```bash
PFCOUNT key [key ...]
```

**单个统计**：
```bash
PFCOUNT uv:2024-11-02
# 返回：估算的UV数量
```

**合并统计**：
```bash
PFCOUNT uv:2024-11-01 uv:2024-11-02 uv:2024-11-03
# 返回：三天UV的并集基数
```

**Java实现**：
```java
Long uv = redisTemplate.opsForHyperLogLog().size("uv:2024-11-02");

// 合并统计
Long totalUv = redisTemplate.opsForHyperLogLog().size(
    "uv:2024-11-01", "uv:2024-11-02", "uv:2024-11-03"
);
```

---

#### 4.3 PFMERGE（合并HLL）

```bash
PFMERGE destkey sourcekey [sourcekey ...]
```

**示例**：
```bash
# 合并多天UV到总UV
PFMERGE uv:total uv:2024-11-01 uv:2024-11-02 uv:2024-11-03

PFCOUNT uv:total
# 返回：三天总UV
```

**Java实现**：
```java
redisTemplate.opsForHyperLogLog().union(
    "uv:total",
    "uv:2024-11-01", "uv:2024-11-02", "uv:2024-11-03"
);
```

---

### 5. 实战案例

#### 5.1 网站UV统计

```java
@Service
public class UVStatService {
    @Autowired
    private StringRedisTemplate redisTemplate;
    
    // 记录访问
    public void recordVisit(String userId) {
        String date = LocalDate.now().toString();
        String key = "uv:" + date;
        redisTemplate.opsForHyperLogLog().add(key, userId);
        // 设置过期时间（保留30天）
        redisTemplate.expire(key, 30, TimeUnit.DAYS);
    }
    
    // 获取今日UV
    public Long getTodayUV() {
        String date = LocalDate.now().toString();
        return redisTemplate.opsForHyperLogLog().size("uv:" + date);
    }
    
    // 获取最近7天UV
    public Long getWeekUV() {
        List<String> keys = new ArrayList<>();
        for (int i = 0; i < 7; i++) {
            String date = LocalDate.now().minusDays(i).toString();
            keys.add("uv:" + date);
        }
        return redisTemplate.opsForHyperLogLog().size(keys.toArray(new String[0]));
    }
    
    // 合并月度UV
    @Scheduled(cron = "0 0 1 * * ?")  // 每天凌晨1点
    public void mergeMonthUV() {
        String month = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy-MM"));
        String yesterday = LocalDate.now().minusDays(1).toString();
        
        redisTemplate.opsForHyperLogLog().union(
            "uv:month:" + month,
            "uv:month:" + month,
            "uv:" + yesterday
        );
    }
}
```

---

#### 5.2 页面访问分析

```java
// 记录页面访问
public void recordPageView(String pageId, String userId, String sessionId) {
    String today = LocalDate.now().toString();
    
    // UV（基于用户ID）
    redisTemplate.opsForHyperLogLog().add("page:" + pageId + ":uv:" + today, userId);
    
    // 会话数（基于sessionId）
    redisTemplate.opsForHyperLogLog().add("page:" + pageId + ":session:" + today, sessionId);
    
    // PV（使用String计数器）
    redisTemplate.opsForValue().increment("page:" + pageId + ":pv:" + today);
}

// 获取页面统计
public PageStats getPageStats(String pageId) {
    String today = LocalDate.now().toString();
    
    Long uv = redisTemplate.opsForHyperLogLog().size("page:" + pageId + ":uv:" + today);
    Long sessions = redisTemplate.opsForHyperLogLog().size("page:" + pageId + ":session:" + today);
    Long pv = Long.parseLong(redisTemplate.opsForValue().get("page:" + pageId + ":pv:" + today));
    
    return new PageStats(uv, sessions, pv);
}
```

---

### 6. HLL vs Set vs Bitmap

| 方案 | 内存占用 | 精确度 | 适用场景 |
|------|----------|--------|----------|
| **Set** | O(N*M)<br>N=元素数量，M=元素大小 | 100% | 需要精确结果，数据量小 |
| **Bitmap** | O(N/8)<br>N=最大ID | 100% | ID连续且范围已知 |
| **HyperLogLog** | 固定12KB | 99.19% | 海量数据，允许误差 |

**示例对比**（1亿UV）：
```bash
# Set方案
SADD uv:set "1" "2" ... "100000000"
# 内存：约1.6GB
# 精确度：100%

# Bitmap方案（假设ID范围0-1亿）
SETBIT uv:bitmap 1 1
SETBIT uv:bitmap 2 1
# 内存：100000000 / 8 = 12.5MB
# 精确度：100%
# 限制：ID必须是整数且范围已知

# HyperLogLog方案
PFADD uv:hll "1" "2" ... "100000000"
# 内存：12KB
# 精确度：99.19%
```

---

### 7. 注意事项与最佳实践

#### 7.1 误差说明

**标准误差**：0.81%
```bash
# 真实UV：100000
# HLL估算：99190 ~ 100810（概率99.7%）
```

**不适合场景**：
- 需要精确计数（如金额、库存）
- 数据量很小（如<1000，Set足够）
- 需要获取具体元素（HLL只能统计数量）

---

#### 7.2 稀疏转密集

**转换条件**：元素较多或单个桶值过大
```bash
# 初始：稀疏编码（< 3000字节）
PFADD key "1" "2" "3" ...

# 自动转换：密集编码（12KB）
PFADD key "1000" "1001" ...
```

**影响**：转换后内存突增到12KB，需注意

---

#### 7.3 性能优化

**批量添加**：
```java
// 不推荐：多次网络往返
for (String userId : userIds) {
    redisTemplate.opsForHyperLogLog().add(key, userId);
}

// 推荐：批量添加
redisTemplate.opsForHyperLogLog().add(key, userIds.toArray(new String[0]));
```

**避免频繁PFCOUNT**：
```java
// 缓存结果
@Cacheable(value = "uv", key = "#date")
public Long getUV(String date) {
    return redisTemplate.opsForHyperLogLog().size("uv:" + date);
}
```

---

### 8. 面试答题总结

**标准回答模板**：

> **HyperLogLog**是一种概率性数据结构，用于基数统计：
> 1. **核心优势**：固定12KB内存可统计2^64个元素，标准误差0.81%
> 2. **原理**：基于伯努利试验和LogLog算法，通过hash值的前导0个数估算基数，使用16384个桶（6位寄存器）分桶平均降低误差
> 3. **应用场景**：UV统计、页面去重访问、搜索词统计等海量数据基数统计
> 4. **命令**：PFADD添加元素、PFCOUNT统计基数、PFMERGE合并HLL
> 5. **相比Set**：内存占用降低99.99%，但只能统计数量，无法获取具体元素

**常见追问**：
- **为什么需要HyperLogLog？** → Set存1亿UV需1.6GB，HLL只需12KB
- **误差率0.81%如何理解？** → 真实值100000，估算值99190~100810（概率99.7%）
- **HLL的实现原理？** → hash值前导0个数估算基数，分桶调和平均降低误差
- **什么场景不适合HLL？** → 需要精确计数、数据量很小、需要获取具体元素

