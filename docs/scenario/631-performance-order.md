---
layout: default
title: "电商下单接口从520ms优化到185ms，如何做到？"
parent: 大厂项目场景实战
nav_order: 631
description: "通过电商下单场景讲解异步化、并行化、缓存优化等性能优化思路"
date: 2025-12-28
---

# 电商下单接口从520ms优化到185ms，如何做到？

## 业务场景

电商平台核心下单接口，当前响应时间P99达到520ms，影响用户体验。

**目标**：优化到200ms以内。

---

## 性能优化核心思路

```
┌─────────────────────────────────────────────────────────┐
│                   性能优化三板斧                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   1. 异步化：非核心逻辑异步执行                           │
│                                                         │
│   2. 并行化：无依赖的调用并行执行                         │
│                                                         │
│   3. 缓存：减少I/O，用空间换时间                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 优化前：串行执行

```java
public OrderResult createOrder(OrderRequest request) {
    // 1. 校验用户 - 50ms
    User user = userService.getUser(request.getUserId());
    validateUser(user);
    
    // 2. 校验库存 - 80ms
    Stock stock = stockService.checkStock(request.getProductId());
    validateStock(stock);
    
    // 3. 计算价格 - 60ms
    Price price = priceService.calculatePrice(request);
    
    // 4. 创建订单 - 100ms
    Order order = orderService.createOrder(request, price);
    
    // 5. 扣减库存 - 80ms
    stockService.deductStock(request.getProductId(), request.getQuantity());
    
    // 6. 扣减优惠券 - 50ms
    couponService.useCoupon(request.getCouponId());
    
    // 7. 发送通知 - 100ms
    notificationService.sendOrderNotification(order);
    
    return new OrderResult(order);
}
```

**总耗时**：50+80+60+100+80+50+100 = **520ms**

---

## 优化一：异步化非核心逻辑

### 分析核心与非核心

| 步骤 | 是否核心 | 原因 |
|------|----------|------|
| 校验用户/库存 | ✅ 核心 | 下单前必须校验 |
| 计算价格 | ✅ 核心 | 价格必须准确 |
| 创建订单 | ✅ 核心 | 核心业务 |
| 扣减库存 | ✅ 核心 | 必须同步扣减 |
| 扣减优惠券 | ⚠️ 准核心 | 可短暂延迟 |
| 发送通知 | ❌ 非核心 | 完全可异步 |

### 优化代码

```java
public OrderResult createOrder(OrderRequest request) {
    // 1-5: 核心逻辑（同步）
    User user = userService.getUser(request.getUserId());
    Stock stock = stockService.checkStock(request.getProductId());
    Price price = priceService.calculatePrice(request);
    Order order = orderService.createOrder(request, price);
    stockService.deductStock(request.getProductId(), request.getQuantity());
    
    // 6. 扣减优惠券（可以放入事务消息）
    couponService.useCoupon(request.getCouponId());
    
    // 7. 发送通知（异步）
    asyncExecutor.execute(() -> {
        notificationService.sendOrderNotification(order);
    });
    
    return new OrderResult(order);
}
```

**优化效果**：520 - 100 = **420ms**

---

## 优化二：并行化无依赖调用

### 分析依赖关系

```
校验用户 ─────┐
              ├──→ 创建订单 ──→ 扣减库存
校验库存 ─────┤
              │
计算价格 ─────┘
```

用户校验、库存校验、价格计算**互不依赖**，可以并行！

### 使用CompletableFuture并行化

```java
public OrderResult createOrder(OrderRequest request) {
    // 1,2,3: 并行执行
    CompletableFuture<User> userFuture = CompletableFuture.supplyAsync(
        () -> userService.getUser(request.getUserId()), executor);
    
    CompletableFuture<Stock> stockFuture = CompletableFuture.supplyAsync(
        () -> stockService.checkStock(request.getProductId()), executor);
    
    CompletableFuture<Price> priceFuture = CompletableFuture.supplyAsync(
        () -> priceService.calculatePrice(request), executor);
    
    // 等待所有并行任务完成
    CompletableFuture.allOf(userFuture, stockFuture, priceFuture).join();
    
    User user = userFuture.join();
    Stock stock = stockFuture.join();
    Price price = priceFuture.join();
    
    // 校验
    validateUser(user);
    validateStock(stock);
    
    // 4. 创建订单
    Order order = orderService.createOrder(request, price);
    
    // 5. 扣减库存
    stockService.deductStock(request.getProductId(), request.getQuantity());
    
    // 6. 扣减优惠券
    couponService.useCoupon(request.getCouponId());
    
    // 7. 发送通知（异步）
    asyncExecutor.execute(() -> {
        notificationService.sendOrderNotification(order);
    });
    
    return new OrderResult(order);
}
```

**优化效果**：
- 步骤1,2,3并行：max(50, 80, 60) = 80ms
- 步骤4,5,6串行：100+80+50 = 230ms
- 总计：80+230 = **310ms**

---

## 优化三：缓存热点数据

### 用户信息缓存

```java
@Cacheable(value = "user", key = "#userId", unless = "#result == null")
public User getUser(Long userId) {
    return userMapper.findById(userId);
}
```

### 商品库存缓存

```java
public Stock checkStock(Long productId) {
    String key = "stock:" + productId;
    
    // 先查Redis
    String stockJson = redisTemplate.opsForValue().get(key);
    if (stockJson != null) {
        return JSON.parseObject(stockJson, Stock.class);
    }
    
    // 回源查库
    Stock stock = stockMapper.findByProductId(productId);
    redisTemplate.opsForValue().set(key, JSON.toJSONString(stock), 5, TimeUnit.SECONDS);
    return stock;
}
```

**优化效果**：
- 用户查询：50ms → 5ms
- 库存查询：80ms → 5ms

**步骤1,2,3并行**：max(5, 5, 60) = 60ms

---

## 优化四：数据库优化

### 批量写入

```java
// 优化前：多次单条插入
for (OrderItem item : items) {
    orderItemMapper.insert(item);
}

// 优化后：批量插入
orderItemMapper.batchInsert(items);
```

### 索引优化

```sql
-- 确保扣减库存走索引
ALTER TABLE stock ADD INDEX idx_product_id (product_id);

-- 减少查询字段
SELECT stock_count FROM stock WHERE product_id = ?;  -- 覆盖索引
```

---

## 最终代码

```java
@Service
public class OrderService {
    
    @Autowired
    private ThreadPoolExecutor parallelExecutor;
    
    @Autowired  
    private ThreadPoolExecutor asyncExecutor;
    
    public OrderResult createOrder(OrderRequest request) {
        long start = System.currentTimeMillis();
        
        // 1. 并行获取用户、库存、价格（60ms）
        CompletableFuture<User> userFuture = CompletableFuture.supplyAsync(
            () -> userService.getCachedUser(request.getUserId()), parallelExecutor);
        CompletableFuture<Stock> stockFuture = CompletableFuture.supplyAsync(
            () -> stockService.getCachedStock(request.getProductId()), parallelExecutor);
        CompletableFuture<Price> priceFuture = CompletableFuture.supplyAsync(
            () -> priceService.calculatePrice(request), parallelExecutor);
        
        CompletableFuture.allOf(userFuture, stockFuture, priceFuture).join();
        
        validateUser(userFuture.join());
        validateStock(stockFuture.join());
        Price price = priceFuture.join();
        
        // 2. 创建订单 + 扣减库存（事务内，100ms）
        Order order = doCreateOrder(request, price);
        
        // 3. 异步处理非核心逻辑
        asyncExecutor.execute(() -> {
            couponService.useCoupon(request.getCouponId());
            notificationService.sendOrderNotification(order);
        });
        
        long cost = System.currentTimeMillis() - start;
        log.info("下单耗时: {}ms", cost);  // ~185ms
        
        return new OrderResult(order);
    }
}
```

---

## 优化效果汇总

| 优化手段 | 优化前 | 优化后 | 提升 |
|----------|--------|--------|------|
| 异步化通知 | 520ms | 420ms | 100ms |
| 并行化查询 | 420ms | 310ms | 110ms |
| 缓存热点数据 | 310ms | 240ms | 70ms |
| 数据库优化 | 240ms | 185ms | 55ms |
| **总计** | **520ms** | **185ms** | **64%↓** |

---

## 面试答题框架

```
原始问题：下单接口P99=520ms

优化思路：
1. 异步化：发送通知异步处理 → 节省100ms
2. 并行化：用户/库存/价格并行查询 → 节省110ms
3. 缓存：热点数据Redis缓存 → 节省70ms
4. DB优化：批量插入、索引优化 → 节省55ms

工具选择：
- CompletableFuture实现并行化
- @Cacheable + Redis实现缓存
- 自定义线程池控制并发

最终效果：520ms → 185ms，提升64%
```

---

## 总结

| 优化手段 | 适用场景 | 注意事项 |
|----------|----------|----------|
| 异步化 | 非核心逻辑 | 异常处理、监控 |
| 并行化 | 无依赖的I/O操作 | 线程池配置 |
| 缓存 | 热点数据 | 一致性、失效策略 |
| DB优化 | 写操作多 | 批量、索引 |
