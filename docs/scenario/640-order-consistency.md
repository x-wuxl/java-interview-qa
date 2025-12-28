---
layout: default
title: "如何保障电商下单场景的数据一致性？"
parent: 大厂项目场景实战
nav_order: 640
description: "通过电商下单场景讲解Seata AT、本地消息表等数据一致性方案"
date: 2025-12-28
---

# 如何保障电商下单场景的数据一致性？

## 业务场景

电商下单流程涉及多个服务的数据变更：

```
用户下单
    │
    ├── 订单服务：创建订单
    │
    ├── 库存服务：扣减库存
    │
    ├── 账户服务：扣减余额/积分
    │
    └── 优惠券服务：核销优惠券
```

**问题**：如何保证这四个服务要么全部成功，要么全部回滚？

---

## 方案对比

| 方案 | 一致性 | 性能 | 复杂度 | 适用场景 |
|------|--------|------|--------|----------|
| Seata AT | 最终一致 | 好 | 低 | 推荐首选 |
| TCC | 最终一致 | 好 | 高 | 复杂业务 |
| 本地消息表 | 最终一致 | 好 | 中 | 简单场景 |
| 2PC/XA | 强一致 | 差 | 低 | 金融核心 |

---

## 方案一：Seata AT模式（推荐）

### 架构图

```
┌──────────────────────────────────────────────────────────┐
│                      订单服务                             │
│                                                          │
│    @GlobalTransactional                                  │
│    createOrder()                                         │
│        │                                                 │
│        ├── orderService.create()                         │
│        ├── stockService.deduct()    ← RPC                │
│        ├── accountService.deduct()  ← RPC                │
│        └── couponService.use()      ← RPC                │
│                                                          │
└──────────────────────────────────────────────────────────┘
                          │
                          ↓
          ┌───────────────────────────────┐
          │         Seata Server          │
          │       (事务协调者 TC)          │
          └───────────────────────────────┘
```

### 代码实现

**1. 主事务入口**

```java
@Service
public class OrderService {
    
    @Autowired
    private StockFeignClient stockClient;
    
    @Autowired
    private AccountFeignClient accountClient;
    
    @Autowired
    private CouponFeignClient couponClient;
    
    @GlobalTransactional(name = "create-order", rollbackFor = Exception.class)
    public Order createOrder(OrderRequest request) {
        // 1. 创建订单
        Order order = doCreateOrder(request);
        
        // 2. 扣减库存
        stockClient.deduct(request.getProductId(), request.getQuantity());
        
        // 3. 扣减余额
        accountClient.deduct(request.getUserId(), order.getTotalAmount());
        
        // 4. 核销优惠券
        if (request.getCouponId() != null) {
            couponClient.use(request.getCouponId());
        }
        
        return order;
    }
}
```

**2. 分支事务**

```java
@Service
public class StockServiceImpl implements StockService {
    
    @Transactional  // 本地事务即可
    @Override
    public void deduct(Long productId, int quantity) {
        int affected = stockMapper.deduct(productId, quantity);
        if (affected == 0) {
            throw new StockNotEnoughException();
        }
    }
}
```

### Seata配置

```yaml
seata:
  enabled: true
  application-id: order-service
  tx-service-group: my_tx_group
  service:
    vgroup-mapping:
      my_tx_group: default
    grouplist:
      default: seata-server:8091
  config:
    type: nacos
  registry:
    type: nacos
```

### 原理

```
1. TM（事务管理器）开启全局事务，生成XID
2. XID通过RPC调用传递到各分支
3. RM（资源管理器）执行本地事务前记录undo_log
4. TM发起commit/rollback
5. 如果rollback，根据undo_log反向补偿
```

---

## 方案二：本地消息表

### 适用场景
- 不想引入Seata依赖
- 对延迟不敏感（秒级）

### 实现步骤

**1. 订单服务（主事务）**

```java
@Service
public class OrderService {
    
    @Transactional
    public Order createOrder(OrderRequest request) {
        // 1. 创建订单
        Order order = doCreateOrder(request);
        
        // 2. 写入本地消息表（同一事务）
        LocalMessage message = new LocalMessage();
        message.setMessageId(UUID.randomUUID().toString());
        message.setTopic("order-created");
        message.setBody(JSON.toJSONString(order));
        message.setStatus(0);  // 待发送
        localMessageMapper.insert(message);
        
        return order;
    }
}
```

**2. 定时任务发送消息**

```java
@Scheduled(fixedDelay = 1000)
public void sendMessages() {
    List<LocalMessage> messages = localMessageMapper.findPending(100);
    
    for (LocalMessage msg : messages) {
        try {
            kafkaTemplate.send(msg.getTopic(), msg.getBody()).get();
            localMessageMapper.updateStatus(msg.getId(), 1);  // 已发送
        } catch (Exception e) {
            log.error("消息发送失败: {}", msg.getId(), e);
        }
    }
}
```

**3. 消费者处理（幂等）**

```java
@KafkaListener(topics = "order-created")
public void processOrder(String message) {
    Order order = JSON.parseObject(message, Order.class);
    
    // 幂等检查
    if (processedOrders.contains(order.getOrderId())) {
        return;
    }
    
    try {
        // 扣库存
        stockService.deduct(order.getProductId(), order.getQuantity());
        // 扣余额
        accountService.deduct(order.getUserId(), order.getAmount());
        // 标记已处理
        processedOrders.add(order.getOrderId());
    } catch (Exception e) {
        // 失败后会重试，走补偿
        throw e;
    }
}
```

---

## 方案三：TCC

### 适用场景
- 复杂业务逻辑
- 需要精细化控制

### 库存服务TCC实现

```java
@LocalTCC
public interface StockTccService {
    
    @TwoPhaseBusinessAction(name = "deductStock", commitMethod = "confirm", rollbackMethod = "cancel")
    boolean tryDeduct(@BusinessActionContextParameter(paramName = "productId") Long productId,
                      @BusinessActionContextParameter(paramName = "quantity") int quantity);
    
    boolean confirm(BusinessActionContext context);
    
    boolean cancel(BusinessActionContext context);
}

@Service
public class StockTccServiceImpl implements StockTccService {
    
    @Override
    public boolean tryDeduct(Long productId, int quantity) {
        // Try阶段：冻结库存
        return stockMapper.freeze(productId, quantity) > 0;
    }
    
    @Override
    public boolean confirm(BusinessActionContext context) {
        // Confirm阶段：扣减冻结的库存
        Long productId = context.getActionContext("productId");
        Integer quantity = context.getActionContext("quantity");
        return stockMapper.confirmDeduct(productId, quantity) > 0;
    }
    
    @Override
    public boolean cancel(BusinessActionContext context) {
        // Cancel阶段：释放冻结的库存
        Long productId = context.getActionContext("productId");
        Integer quantity = context.getActionContext("quantity");
        return stockMapper.unfreeze(productId, quantity) > 0;
    }
}
```

---

## 异常处理

### 空回滚问题

Cancel阶段执行时，Try可能还没执行，需要防止空回滚：

```java
@Override
public boolean cancel(BusinessActionContext context) {
    Long productId = context.getActionContext("productId");
    
    // 检查是否执行过Try
    TccFreezeRecord record = freezeRecordMapper.find(context.getXid(), productId);
    if (record == null) {
        // Try没执行，直接返回成功
        return true;
    }
    
    // 正常回滚
    return stockMapper.unfreeze(productId, record.getQuantity()) > 0;
}
```

### 悬挂问题

Cancel比Try先执行，需要在Try时检查：

```java
@Override
public boolean tryDeduct(Long productId, int quantity) {
    // 检查是否已经Cancel过
    if (cancelRecordMapper.exists(context.getXid(), productId)) {
        return false;  // 拒绝执行
    }
    
    return stockMapper.freeze(productId, quantity) > 0;
}
```

---

## 面试答题框架

```
场景分析：下单涉及订单、库存、账户、优惠券四个服务

方案选型：
- 推荐Seata AT：无侵入，开箱即用
- 简单场景：本地消息表
- 复杂场景：TCC

Seata实现：
- @GlobalTransactional注解入口
- 分支事务自动记录undo_log
- 全局回滚时反向补偿

异常处理：
- 空回滚：检查Try是否执行
- 悬挂：检查Cancel是否已执行
- 幂等：业务去重
```

---

## 总结

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| Seata AT | 无侵入，简单 | 依赖Seata Server | ⭐⭐⭐⭐⭐ |
| 本地消息表 | 简单可靠 | 有延迟 | ⭐⭐⭐⭐ |
| TCC | 灵活，高性能 | 开发成本高 | ⭐⭐⭐ |
