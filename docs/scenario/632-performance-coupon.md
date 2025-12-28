---
layout: default
title: "优惠券下发从30小时优化到20分钟，如何做到？"
parent: 大厂项目场景实战
nav_order: 632
description: "讲解大批量数据处理优化策略，包括分批处理、多线程、异步化"
date: 2025-12-28
---

# 优惠券下发从30小时优化到20分钟，如何做到？

## 业务场景

电商大促前夕，需要给1000万用户下发优惠券。

**原始方案**：单线程遍历用户列表，逐个下发。
**问题**：预估需要30+小时，无法在活动开始前完成！

---

## 性能分析

### 原始代码

```java
public void sendCoupons(Long couponId) {
    List<Long> userIds = userMapper.findAllEligibleUsers();
    
    for (Long userId : userIds) {
        // 单条处理，每条约10ms
        couponService.send(userId, couponId);
    }
}
```

### 耗时分析

```
1000万用户 × 10ms/用户 = 1亿ms = 约28小时
```

---

## 优化策略

### 策略一：批量处理

```java
// 原始：逐条插入
for (Long userId : userIds) {
    couponMapper.insert(new Coupon(userId, couponId));
}

// 优化：批量插入
List<List<Long>> batches = Lists.partition(userIds, 1000);
for (List<Long> batch : batches) {
    List<Coupon> coupons = batch.stream()
        .map(uid -> new Coupon(uid, couponId))
        .collect(Collectors.toList());
    couponMapper.batchInsert(coupons);
}
```

**效果**：1000条批量插入比逐条快10-20倍。

### 策略二：多线程并行

```java
@Async
public void sendCouponsAsync(Long couponId) {
    List<Long> userIds = userMapper.findAllEligibleUsers();
    
    // 分成100个批次
    List<List<Long>> batches = Lists.partition(userIds, 100000);
    
    // 并行处理
    List<CompletableFuture<Void>> futures = batches.stream()
        .map(batch -> CompletableFuture.runAsync(() -> 
            processBatch(batch, couponId), executor))
        .collect(Collectors.toList());
    
    // 等待全部完成
    CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
}

private void processBatch(List<Long> userIds, Long couponId) {
    List<List<Long>> subBatches = Lists.partition(userIds, 1000);
    for (List<Long> sub : subBatches) {
        couponMapper.batchInsert(buildCoupons(sub, couponId));
    }
}
```

**效果**：50线程并行，理论提升50倍。

### 策略三：分库分表并行

如果用户表已分库分表，可以按分片并行处理。

```java
public void sendCouponsBySharding(Long couponId) {
    // 获取所有分片
    int shardCount = 32;
    
    List<CompletableFuture<Void>> futures = new ArrayList<>();
    
    for (int i = 0; i < shardCount; i++) {
        int shardIndex = i;
        futures.add(CompletableFuture.runAsync(() -> {
            // 每个分片独立处理
            processShardUsers(shardIndex, couponId);
        }, executor));
    }
    
    CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
}

private void processShardUsers(int shardIndex, Long couponId) {
    // 直接查询对应分片
    List<Long> userIds = userMapper.findByShardIndex(shardIndex);
    // 批量处理
    batchSend(userIds, couponId);
}
```

### 策略四：异步消息 + 消费者扩容

```java
// 生产者：快速发送消息
public void sendCouponsViaMQ(Long couponId) {
    List<Long> userIds = userMapper.findAllEligibleUsers();
    
    List<List<Long>> batches = Lists.partition(userIds, 100);
    for (List<Long> batch : batches) {
        CouponMessage msg = new CouponMessage(batch, couponId);
        kafkaTemplate.send("coupon-send", JSON.toJSONString(msg));
    }
}

// 消费者：可水平扩容
@KafkaListener(topics = "coupon-send", concurrency = "20")
public void consume(String message) {
    CouponMessage msg = JSON.parseObject(message, CouponMessage.class);
    couponMapper.batchInsert(buildCoupons(msg.getUserIds(), msg.getCouponId()));
}
```

**优势**：消费者可以水平扩容，增加机器即可提速。

---

## 数据库优化

### 减少索引

```sql
-- 临时移除非必要索引
ALTER TABLE user_coupon DROP INDEX idx_expire_time;

-- 批量导入完成后重建
ALTER TABLE user_coupon ADD INDEX idx_expire_time (expire_time);
```

### 使用LOAD DATA

```sql
-- 比INSERT快10-20倍
LOAD DATA LOCAL INFILE '/tmp/coupons.csv'
INTO TABLE user_coupon
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\n';
```

### Java生成CSV

```java
public void exportToCsv(List<Long> userIds, Long couponId) {
    try (FileWriter writer = new FileWriter("/tmp/coupons.csv")) {
        for (Long userId : userIds) {
            writer.write(userId + "," + couponId + "," + expireTime + "\n");
        }
    }
    // 再执行LOAD DATA
}
```

---

## 最终方案

```
1000万用户
    │
    ├── 分成100个批次（每批10万）
    │
    ├── 50线程并行处理
    │       │
    │       ├── 每批再分1000条子批次
    │       │
    │       └── 批量INSERT
    │
    └── 总计约15-20分钟完成
```

---

## 优化效果

| 优化项 | 耗时 | 提升 |
|--------|------|------|
| 原始单线程 | 28小时 | - |
| +批量插入 | 3小时 | 9倍 |
| +多线程(50) | 4分钟 | 420倍 |
| +分库并行 | 更快 | - |

---

## 注意事项

### 1. 限流保护

```java
// 控制并发，保护数据库
Semaphore semaphore = new Semaphore(10);

executor.submit(() -> {
    semaphore.acquire();
    try {
        processBatch(batch, couponId);
    } finally {
        semaphore.release();
    }
});
```

### 2. 进度监控

```java
AtomicLong processed = new AtomicLong(0);

// 处理完一批后上报
processed.addAndGet(batch.size());
log.info("已处理: {}/{}", processed.get(), total);
```

### 3. 断点续传

```java
// 记录处理进度，支持中断恢复
@Transactional
public void processBatch(List<Long> userIds, Long couponId, Long batchId) {
    couponMapper.batchInsert(buildCoupons(userIds, couponId));
    progressMapper.update(batchId, "DONE");
}
```

---

## 面试答题框架

```
原始问题：1000万用户逐条处理，预估28小时

优化思路：
1. 批量处理：提升10倍
2. 多线程：提升50倍
3. 分库并行：充分利用分片
4. MQ异步：支持水平扩容

最终效果：28小时 → 15-20分钟

关键细节：
- 批量大小：1000条/批
- 线程数：根据DB承受能力调整
- 限流保护：Semaphore控制并发
- 进度监控：支持断点续传
```

---

## 总结

| 策略 | 适用场景 | 提升幅度 |
|------|----------|----------|
| 批量INSERT | 通用 | 10-20倍 |
| 多线程 | CPU/IO密集 | N倍 |
| 分库并行 | 已分库 | 分片数倍 |
| MQ消费者扩容 | 需弹性 | 水平扩展 |
