---
title: "什么是Saga？"
date: 2025-11-02
description: "详细介绍Saga分布式事务模式的原理、两种实现方式（协同式和编排式）、补偿机制以及在长流程业务中的实际应用"
author: "wuxl"
categories: [分布式]
tags: [分布式事务, Saga, 编排式Saga, 协同式Saga, 柔性事务, 补偿机制]
nav_order: 508
parent: 分布式事务
---
## 问题

什么是Saga？

## 答案

### 1. 核心概念

**Saga**是一种长事务解决方案，最早由Hector Garcia-Molina和Kenneth Salem在1987年提出。Saga将一个分布式事务拆分成多个**本地事务**，每个本地事务都有对应的**补偿事务**（Compensating Transaction）。

**核心思想**：
- 将长事务拆分为多个短事务
- 每个子事务在本地提交
- 如果某个子事务失败，通过**补偿事务**回滚已完成的操作

**与TCC对比**：
- **TCC**：Try预留资源 → Confirm/Cancel
- **Saga**：直接执行 → 失败时执行补偿

### 2. Saga执行流程

#### 成功场景

```
订单服务          库存服务          账户服务          物流服务
   |                 |                 |                 |
   |---T1: 创建订单--> ✓
   |                 |
   |                 |---T2: 扣减库存--> ✓
   |                 |                 |
   |                 |                 |---T3: 扣减余额--> ✓
   |                 |                 |                 |
   |                 |                 |                 |---T4: 创建物流单--> ✓
   |                 |                 |                 |
   └─────────────────┴─────────────────┴─────────────────┘
                    所有事务成功提交
```

#### 失败场景（补偿）

```
订单服务          库存服务          账户服务          物流服务
   |                 |                 |                 |
   |---T1: 创建订单--> ✓
   |                 |
   |                 |---T2: 扣减库存--> ✓
   |                 |                 |
   |                 |                 |---T3: 扣减余额--> ✗ (失败)
   |                 |                 |
   |                 |<--C2: 恢复库存---|
   |                 |                 |
   |<--C1: 取消订单--|                 |
   |                 |                 |
   └─────────────────┴─────────────────┘
            执行补偿事务，回滚已完成的操作
```

**正向流程（Forward Recovery）**：
```
T1 → T2 → T3 → T4
```

**补偿流程（Backward Recovery）**：
```
C4 ← C3 ← C2 ← C1
```

### 3. Saga的两种实现方式

#### 方式1：协同式Saga（Choreography-based）

**原理**：每个服务监听事件，自主决定下一步操作，无中央协调器。

**架构图**：
```
订单服务 ---发布[OrderCreated]事件---> 事件总线
   ↑                                      |
   |                                      ↓
   |                                  库存服务
   |                                      |
   |                                  (监听事件)
   |                                      ↓
   |                              发布[StockDeducted]事件
   |                                      |
   |                                      ↓
   |                                  账户服务
   |                                      |
   |                                  (监听事件)
   |                                      ↓
   ←---发布[PaymentFailed]事件---   (余额不足)
```

**实现示例**：

```java
// 订单服务
@Service
public class OrderService {
    
    @Autowired
    private EventPublisher eventPublisher;
    
    /**
     * 创建订单
     */
    @Transactional
    public void createOrder(OrderDTO orderDTO) {
        // 1. 本地事务：创建订单
        Order order = new Order();
        order.setStatus(OrderStatus.PENDING);
        orderMapper.insert(order);
        
        // 2. 发布订单创建事件
        OrderCreatedEvent event = new OrderCreatedEvent(order);
        eventPublisher.publish(event);
    }
    
    /**
     * 监听支付失败事件，执行补偿
     */
    @EventListener
    @Transactional
    public void onPaymentFailed(PaymentFailedEvent event) {
        // 补偿：取消订单
        Order order = orderMapper.selectById(event.getOrderId());
        order.setStatus(OrderStatus.CANCELED);
        orderMapper.updateById(order);
        
        log.info("Order canceled due to payment failure: {}", event.getOrderId());
    }
}

// 库存服务
@Service
public class InventoryService {
    
    @Autowired
    private EventPublisher eventPublisher;
    
    /**
     * 监听订单创建事件
     */
    @EventListener
    @Transactional
    public void onOrderCreated(OrderCreatedEvent event) {
        try {
            // 本地事务：扣减库存
            inventoryMapper.deductStock(
                event.getProductId(), 
                event.getQuantity()
            );
            
            // 发布库存扣减成功事件
            StockDeductedEvent successEvent = new StockDeductedEvent(event);
            eventPublisher.publish(successEvent);
            
        } catch (InsufficientStockException e) {
            // 库存不足，发布失败事件
            StockDeductFailedEvent failEvent = new StockDeductFailedEvent(event);
            eventPublisher.publish(failEvent);
        }
    }
    
    /**
     * 监听支付失败事件，执行补偿
     */
    @EventListener
    @Transactional
    public void onPaymentFailed(PaymentFailedEvent event) {
        // 补偿：恢复库存
        inventoryMapper.restoreStock(
            event.getProductId(), 
            event.getQuantity()
        );
        
        log.info("Stock restored for order: {}", event.getOrderId());
    }
}

// 账户服务
@Service
public class AccountService {
    
    @Autowired
    private EventPublisher eventPublisher;
    
    /**
     * 监听库存扣减成功事件
     */
    @EventListener
    @Transactional
    public void onStockDeducted(StockDeductedEvent event) {
        try {
            // 本地事务：扣减余额
            accountMapper.deductBalance(
                event.getAccountId(), 
                event.getAmount()
            );
            
            // 发布支付成功事件
            PaymentSuccessEvent successEvent = new PaymentSuccessEvent(event);
            eventPublisher.publish(successEvent);
            
        } catch (InsufficientBalanceException e) {
            // 余额不足，发布失败事件（触发补偿）
            PaymentFailedEvent failEvent = new PaymentFailedEvent(event);
            eventPublisher.publish(failEvent);
        }
    }
}
```

**事件定义**：
```java
// 订单创建事件
@Data
public class OrderCreatedEvent {
    private String orderId;
    private String productId;
    private Integer quantity;
    private BigDecimal amount;
    private String accountId;
    private LocalDateTime timestamp;
}

// 支付失败事件
@Data
public class PaymentFailedEvent {
    private String orderId;
    private String productId;
    private Integer quantity;
    private String reason;
}
```

**优点**：
- ✅ 服务高度解耦
- ✅ 无单点故障
- ✅ 易于扩展新服务

**缺点**：
- ❌ 流程分散，难以理解和维护
- ❌ 事件链路复杂，调试困难
- ❌ 循环依赖风险

#### 方式2：编排式Saga（Orchestration-based）

**原理**：通过中央协调器（Orchestrator）显式控制事务流程。

**架构图**：
```
                    Saga协调器
                        |
        +---------------+---------------+
        |               |               |
        ↓               ↓               ↓
    订单服务        库存服务        账户服务
        |               |               |
     创建订单        扣减库存        扣减余额
        ↓               ↓               ↓
    成功/失败       成功/失败       成功/失败
        ↓               ↓               ↓
    取消订单        恢复库存        退款余额
   (补偿操作)      (补偿操作)      (补偿操作)
```

**实现示例**：

```java
/**
 * Saga协调器
 */
@Service
public class OrderSagaOrchestrator {
    
    @Autowired
    private OrderService orderService;
    @Autowired
    private InventoryService inventoryService;
    @Autowired
    private AccountService accountService;
    @Autowired
    private ShippingService shippingService;
    @Autowired
    private SagaLogMapper sagaLogMapper;
    
    /**
     * 执行订单Saga
     */
    public void executeOrderSaga(OrderDTO orderDTO) {
        String sagaId = UUID.randomUUID().toString();
        List<SagaStep> completedSteps = new ArrayList<>();
        
        try {
            // 步骤1：创建订单
            SagaStep step1 = new SagaStep("createOrder", 
                () -> orderService.createOrder(orderDTO),
                () -> orderService.cancelOrder(orderDTO.getOrderId())
            );
            executeStep(sagaId, step1);
            completedSteps.add(step1);
            
            // 步骤2：扣减库存
            SagaStep step2 = new SagaStep("deductStock",
                () -> inventoryService.deductStock(
                    orderDTO.getProductId(), 
                    orderDTO.getQuantity()
                ),
                () -> inventoryService.restoreStock(
                    orderDTO.getProductId(), 
                    orderDTO.getQuantity()
                )
            );
            executeStep(sagaId, step2);
            completedSteps.add(step2);
            
            // 步骤3：扣减余额
            SagaStep step3 = new SagaStep("deductBalance",
                () -> accountService.deductBalance(
                    orderDTO.getAccountId(), 
                    orderDTO.getAmount()
                ),
                () -> accountService.refundBalance(
                    orderDTO.getAccountId(), 
                    orderDTO.getAmount()
                )
            );
            executeStep(sagaId, step3);
            completedSteps.add(step3);
            
            // 步骤4：创建物流单
            SagaStep step4 = new SagaStep("createShipping",
                () -> shippingService.createShipping(orderDTO),
                () -> shippingService.cancelShipping(orderDTO.getOrderId())
            );
            executeStep(sagaId, step4);
            completedSteps.add(step4);
            
            // 所有步骤成功，记录日志
            sagaLogMapper.updateStatus(sagaId, SagaStatus.COMPLETED);
            
        } catch (Exception e) {
            log.error("Saga execution failed, sagaId: {}", sagaId, e);
            
            // 执行补偿（倒序）
            compensate(sagaId, completedSteps);
            
            throw new BusinessException("订单创建失败", e);
        }
    }
    
    /**
     * 执行单个步骤
     */
    private void executeStep(String sagaId, SagaStep step) {
        try {
            // 记录步骤开始
            sagaLogMapper.insertStep(sagaId, step.getName(), StepStatus.STARTED);
            
            // 执行正向操作
            step.getAction().execute();
            
            // 记录步骤成功
            sagaLogMapper.updateStepStatus(sagaId, step.getName(), StepStatus.COMPLETED);
            
        } catch (Exception e) {
            // 记录步骤失败
            sagaLogMapper.updateStepStatus(sagaId, step.getName(), StepStatus.FAILED);
            throw e;
        }
    }
    
    /**
     * 执行补偿（倒序）
     */
    private void compensate(String sagaId, List<SagaStep> completedSteps) {
        // 倒序遍历已完成的步骤
        for (int i = completedSteps.size() - 1; i >= 0; i--) {
            SagaStep step = completedSteps.get(i);
            try {
                log.info("Compensating step: {}", step.getName());
                
                // 执行补偿操作
                step.getCompensation().execute();
                
                // 记录补偿成功
                sagaLogMapper.updateStepStatus(
                    sagaId, 
                    step.getName(), 
                    StepStatus.COMPENSATED
                );
                
            } catch (Exception e) {
                // 补偿失败，记录日志，人工介入
                log.error("Compensation failed for step: {}", step.getName(), e);
                sagaLogMapper.updateStepStatus(
                    sagaId, 
                    step.getName(), 
                    StepStatus.COMPENSATION_FAILED
                );
            }
        }
        
        sagaLogMapper.updateStatus(sagaId, SagaStatus.COMPENSATED);
    }
}

/**
 * Saga步骤定义
 */
@Data
@AllArgsConstructor
class SagaStep {
    private String name;                    // 步骤名称
    private SagaAction action;              // 正向操作
    private SagaAction compensation;        // 补偿操作
}

@FunctionalInterface
interface SagaAction {
    void execute() throws Exception;
}
```

**Saga日志表**：
```sql
-- Saga主表
CREATE TABLE saga_log (
    saga_id VARCHAR(64) PRIMARY KEY,
    saga_type VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- STARTED, COMPLETED, COMPENSATED, FAILED
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL
);

-- Saga步骤表
CREATE TABLE saga_step_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    saga_id VARCHAR(64) NOT NULL,
    step_name VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- STARTED, COMPLETED, FAILED, COMPENSATED, COMPENSATION_FAILED
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL,
    INDEX idx_saga_id (saga_id)
);
```

**优点**：
- ✅ 流程清晰，易于理解和维护
- ✅ 集中管理，便于监控和调试
- ✅ 易于实现复杂的业务逻辑

**缺点**：
- ❌ 协调器可能成为单点
- ❌ 协调器逻辑复杂
- ❌ 服务耦合度相对较高

### 4. 补偿设计原则

#### 原则1：补偿操作必须幂等

```java
/**
 * 恢复库存（补偿操作）
 */
@Transactional
public void restoreStock(String productId, int quantity, String sagaId) {
    // 幂等性检查：是否已经补偿过
    CompensationLog log = logMapper.selectBySagaId(sagaId, "restoreStock");
    if (log != null && log.getStatus() == CompensationStatus.COMPLETED) {
        log.info("Stock already restored for sagaId: {}", sagaId);
        return;
    }
    
    // 执行补偿
    inventoryMapper.restoreStock(productId, quantity);
    
    // 记录补偿日志
    logMapper.insert(sagaId, "restoreStock", CompensationStatus.COMPLETED);
}
```

#### 原则2：补偿操作应该是可重试的

```java
/**
 * 退款（补偿操作，支持重试）
 */
@Transactional
@Retryable(maxAttempts = 3, backoff = @Backoff(delay = 1000))
public void refundBalance(String accountId, BigDecimal amount, String sagaId) {
    // 幂等性检查
    if (isAlreadyRefunded(sagaId)) {
        return;
    }
    
    // 执行退款
    accountMapper.addBalance(accountId, amount);
    
    // 记录退款
    refundMapper.insert(sagaId, accountId, amount);
}
```

#### 原则3：考虑补偿失败的情况

```java
private void compensate(String sagaId, List<SagaStep> completedSteps) {
    for (int i = completedSteps.size() - 1; i >= 0; i--) {
        SagaStep step = completedSteps.get(i);
        
        // 最多重试3次
        int maxRetry = 3;
        boolean compensated = false;
        
        for (int retry = 0; retry < maxRetry; retry++) {
            try {
                step.getCompensation().execute();
                compensated = true;
                break;
            } catch (Exception e) {
                log.error("Compensation failed, retry {}/{}", retry + 1, maxRetry, e);
                Thread.sleep(1000 * (retry + 1)); // 递增延迟
            }
        }
        
        if (!compensated) {
            // 补偿失败，记录到失败表，触发告警
            alertService.sendCompensationFailedAlert(sagaId, step.getName());
            compensationFailureMapper.insert(sagaId, step.getName());
        }
    }
}
```

#### 原则4：并非所有操作都能补偿

**无法补偿的场景**：
```java
// 例1：发送短信/邮件（无法撤回）
public void sendNotification(Order order) {
    smsService.send(order.getUserPhone(), "订单已创建");
    // 无法补偿：短信已发出，无法撤回
}

// 例2：第三方支付（需要走退款流程）
public void pay(Order order) {
    alipayService.pay(order);
    // 补偿不是简单回滚，而是发起退款
}

// 处理方式：将无法补偿的操作放在最后
public void executeOrderSaga(Order order) {
    // 可补偿的操作
    createOrder(order);
    deductStock(order);
    deductBalance(order);
    
    // 无法补偿的操作放最后
    sendNotification(order);
}
```

### 5. Saga vs TCC 对比

| 维度 | Saga | TCC |
|------|------|-----|
| **资源锁定** | 无资源锁定 | Try阶段锁定资源 |
| **隔离性** | 弱（无法保证） | 较强（资源已预留） |
| **实现复杂度** | 中等 | 高 |
| **性能** | 高（无资源锁定） | 中等 |
| **补偿设计** | 事后补偿 | 预留资源 |
| **适用场景** | 长流程、跨多服务 | 短流程、对一致性要求高 |
| **典型案例** | 旅游订单（机票+酒店） | 电商下单 |

### 6. 实际应用案例

#### 案例：旅游订单Saga

**业务流程**：
1. 预订机票
2. 预订酒店
3. 预订门票
4. 扣款

```java
@Service
public class TravelOrderSaga {
    
    public void bookTravel(TravelOrderDTO dto) {
        String sagaId = UUID.randomUUID().toString();
        
        try {
            // 步骤1：预订机票
            Flight flight = flightService.bookFlight(dto.getFlightInfo());
            
            // 步骤2：预订酒店
            Hotel hotel = hotelService.bookHotel(dto.getHotelInfo());
            
            // 步骤3：预订门票
            Ticket ticket = ticketService.bookTicket(dto.getTicketInfo());
            
            // 步骤4：扣款
            accountService.deduct(dto.getAccountId(), dto.getTotalAmount());
            
            // 所有步骤成功
            travelOrderService.confirm(dto.getOrderId());
            
        } catch (Exception e) {
            // 补偿：倒序取消
            try {
                accountService.refund(dto.getAccountId(), dto.getTotalAmount());
            } catch (Exception ex) {}
            
            try {
                ticketService.cancelTicket(dto.getTicketInfo());
            } catch (Exception ex) {}
            
            try {
                hotelService.cancelHotel(dto.getHotelInfo());
            } catch (Exception ex) {}
            
            try {
                flightService.cancelFlight(dto.getFlightInfo());
            } catch (Exception ex) {}
            
            throw new BusinessException("旅游订单预订失败", e);
        }
    }
}
```

### 7. Saga框架：Apache Camel Saga

```java
@Component
public class OrderSagaRoute extends RouteBuilder {
    
    @Override
    public void configure() throws Exception {
        // 定义Saga
        from("direct:createOrder")
            .saga()
                .compensation("direct:cancelOrder")
            .to("bean:orderService?method=createOrder")
            
            .saga()
                .compensation("direct:restoreStock")
            .to("bean:inventoryService?method=deductStock")
            
            .saga()
                .compensation("direct:refundBalance")
            .to("bean:accountService?method=deductBalance");
        
        // 补偿路由
        from("direct:cancelOrder")
            .to("bean:orderService?method=cancelOrder");
            
        from("direct:restoreStock")
            .to("bean:inventoryService?method=restoreStock");
            
        from("direct:refundBalance")
            .to("bean:accountService?method=refundBalance");
    }
}
```

### 8. 总结

**Saga核心要点**：
- 将长事务拆分为多个本地短事务
- 通过补偿事务回滚已完成的操作
- 两种实现方式：协同式（事件驱动）和编排式（中央协调）

**补偿设计要点**：
- 补偿操作必须幂等
- 补偿操作应该可重试
- 考虑补偿失败的情况
- 将无法补偿的操作放在最后

**适用场景**：
- 长流程业务（如旅游订单）
- 跨多个服务的业务
- 对一致性要求不是极高的场景

**面试要点**：
- 能清晰描述Saga的原理和流程
- 理解协同式和编排式的区别
- 知道如何设计补偿操作
- 能够对比Saga和TCC的差异

