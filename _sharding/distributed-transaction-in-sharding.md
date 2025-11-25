---
title: "分库分表后如何解决分布式事务？"
date: 2025-11-02
description: "深入分析分库分表场景下分布式事务的挑战与解决方案：强一致性方案（2PC/3PC/XA）、最终一致性方案（TCC/SAGA/本地消息表）及实战选择"
author: "wuxl"
categories: [分布式]
tags: [分库分表, 分布式事务, 2PC, TCC, SAGA, 最终一致性]
nav_order: 518
parent: 分库分表
---
## 问题

分库分表后如何解决分布式事务？

## 答案

### 1. 核心挑战

分库分表后，原本在单库中通过 `BEGIN`、`COMMIT`、`ROLLBACK` 保证的事务 ACID 特性被打破：

```java
// 单库事务（简单）
@Transactional
public void transferMoney(Long fromUserId, Long toUserId, BigDecimal amount) {
    accountDao.deduct(fromUserId, amount);  // 扣款
    accountDao.add(toUserId, amount);       // 加款
}

// 分库后（复杂）：两个用户可能在不同的数据库
// db_0: user_1001 的账户
// db_1: user_2001 的账户
// 无法使用本地事务保证原子性
```

### 2. 解决方案分类

#### 2.1 强一致性方案（CP）

适用于对一致性要求极高的场景（如金融系统）

#### 2.2 最终一致性方案（AP）

适用于可以容忍短暂不一致的场景（如订单系统）

### 3. 强一致性方案

#### 3.1 XA两阶段提交（2PC）

**原理**：协调者统一协调多个参与者，分为准备阶段和提交阶段

**实现示例（使用Atomikos）**：

```java
// 配置XA数据源
@Configuration
public class XADataSourceConfig {

    @Bean
    public DataSource dataSource0() {
        MysqlXADataSource xaDataSource = new MysqlXADataSource();
        xaDataSource.setUrl("jdbc:mysql://localhost:3306/db_0");

        AtomikosDataSourceBean atomikosDataSource = new AtomikosDataSourceBean();
        atomikosDataSource.setXaDataSource(xaDataSource);
        atomikosDataSource.setUniqueResourceName("db_0");
        return atomikosDataSource;
    }

    @Bean
    public DataSource dataSource1() {
        MysqlXADataSource xaDataSource = new MysqlXADataSource();
        xaDataSource.setUrl("jdbc:mysql://localhost:3306/db_1");

        AtomikosDataSourceBean atomikosDataSource = new AtomikosDataSourceBean();
        atomikosDataSource.setXaDataSource(xaDataSource);
        atomikosDataSource.setUniqueResourceName("db_1");
        return atomikosDataSource;
    }
}

// 使用XA事务
@Service
public class TransferService {

    @Transactional  // JTA事务管理器会协调多个XA数据源
    public void transfer(Long fromUserId, Long toUserId, BigDecimal amount) {
        // 路由到db_0
        accountDao.deduct(dataSource0, fromUserId, amount);

        // 路由到db_1
        accountDao.add(dataSource1, toUserId, amount);

        // 提交或回滚由Atomikos协调
    }
}
```

**优点**：
- 强一致性保证
- 对业务代码侵入小

**缺点**：
- 性能差（两阶段通信，锁时间长）
- 存在单点故障（协调者）
- 不适合高并发场景

**适用场景**：金融支付、核心账务等强一致性要求场景

#### 3.2 Seata AT模式

**原理**：自动生成反向SQL，通过全局锁实现隔离

**实现示例**：

```java
// 1. 配置Seata
@Configuration
public class SeataConfig {
    @Bean
    public GlobalTransactionScanner globalTransactionScanner() {
        return new GlobalTransactionScanner("my-service", "my-group");
    }
}

// 2. 使用@GlobalTransactional
@Service
public class OrderService {

    @Autowired
    private AccountService accountService;

    @Autowired
    private InventoryService inventoryService;

    @GlobalTransactional  // Seata全局事务
    public void createOrder(OrderDTO dto) {
        // 1. 创建订单（db_0）
        orderDao.insert(dto);

        // 2. 扣减库存（db_1）
        inventoryService.deduct(dto.getProductId(), dto.getQuantity());

        // 3. 扣减余额（db_2）
        accountService.deduct(dto.getUserId(), dto.getAmount());

        // 任一步骤失败，Seata会自动回滚所有操作
    }
}
```

**工作流程**：
1. **一阶段**：执行业务SQL，记录undo log，提交本地事务
2. **二阶段提交**：删除undo log
3. **二阶段回滚**：根据undo log生成反向SQL并执行

**优点**：
- 性能优于XA（一阶段直接提交）
- 对业务代码侵入小

**缺点**：
- 依赖Seata Server
- 需要额外的undo log表

### 4. 最终一致性方案

#### 4.1 TCC（Try-Confirm-Cancel）

**原理**：业务层面实现两阶段提交，分为尝试、确认、取消三个阶段

**实现示例**：

```java
// 账户服务
@Service
public class AccountService {

    // Try：预留资源
    @Transactional
    public void tryDeduct(Long userId, BigDecimal amount, String txId) {
        Account account = accountDao.selectForUpdate(userId);

        if (account.getBalance().compareTo(amount) < 0) {
            throw new InsufficientBalanceException();
        }

        // 冻结金额（不直接扣减）
        account.setFrozenAmount(account.getFrozenAmount().add(amount));
        accountDao.update(account);

        // 记录Try日志
        tryLogDao.insert(txId, userId, amount);
    }

    // Confirm：确认扣减
    @Transactional
    public void confirmDeduct(Long userId, BigDecimal amount, String txId) {
        Account account = accountDao.selectForUpdate(userId);

        // 真正扣减余额，解冻
        account.setBalance(account.getBalance().subtract(amount));
        account.setFrozenAmount(account.getFrozenAmount().subtract(amount));
        accountDao.update(account);

        // 删除Try日志
        tryLogDao.delete(txId);
    }

    // Cancel：取消，释放冻结资源
    @Transactional
    public void cancelDeduct(Long userId, BigDecimal amount, String txId) {
        Account account = accountDao.selectForUpdate(userId);

        // 解冻金额
        account.setFrozenAmount(account.getFrozenAmount().subtract(amount));
        accountDao.update(account);

        // 删除Try日志
        tryLogDao.delete(txId);
    }
}

// 订单服务（TCC事务协调者）
@Service
public class OrderService {

    @Autowired
    private TccTransactionManager tccManager;

    public void createOrder(OrderDTO dto) {
        String txId = UUID.randomUUID().toString();

        try {
            // Try阶段
            tccManager.begin(txId);

            accountService.tryDeduct(dto.getUserId(), dto.getAmount(), txId);
            inventoryService.tryDeduct(dto.getProductId(), dto.getQuantity(), txId);
            orderDao.insert(dto);

            // Confirm阶段
            tccManager.commit(txId);
            accountService.confirmDeduct(dto.getUserId(), dto.getAmount(), txId);
            inventoryService.confirmDeduct(dto.getProductId(), dto.getQuantity(), txId);

        } catch (Exception e) {
            // Cancel阶段
            tccManager.rollback(txId);
            accountService.cancelDeduct(dto.getUserId(), dto.getAmount(), txId);
            inventoryService.cancelDeduct(dto.getProductId(), dto.getQuantity(), txId);
        }
    }
}
```

**优点**：
- 性能好（没有长时间锁）
- 灵活性高

**缺点**：
- 业务侵入性强（需要实现Try/Confirm/Cancel）
- 开发工作量大

**适用场景**：对性能要求高、业务允许设计TCC接口的场景

#### 4.2 本地消息表（最终一致性）

**原理**：利用本地事务 + 消息队列实现最终一致性

**实现示例**：

```java
// 订单服务
@Service
public class OrderService {

    @Transactional  // 本地事务
    public void createOrder(OrderDTO dto) {
        // 1. 创建订单
        orderDao.insert(dto);

        // 2. 在同一个事务中插入消息表
        LocalMessage message = LocalMessage.builder()
            .id(UUID.randomUUID().toString())
            .topic("order.created")
            .content(JSON.toJSONString(dto))
            .status(MessageStatus.PENDING)
            .build();

        messageDao.insert(message);

        // 本地事务提交
    }

    // 定时任务：扫描消息表，发送到MQ
    @Scheduled(fixedDelay = 1000)
    public void sendPendingMessages() {
        List<LocalMessage> messages = messageDao.selectPending();

        for (LocalMessage msg : messages) {
            try {
                // 发送到MQ
                mqProducer.send(msg.getTopic(), msg.getContent());

                // 更新消息状态为已发送
                messageDao.updateStatus(msg.getId(), MessageStatus.SENT);
            } catch (Exception e) {
                // 发送失败，继续重试（定时任务会再次扫描）
                log.error("发送消息失败", e);
            }
        }
    }
}

// 库存服务（消费者）
@Service
public class InventoryService {

    @RabbitListener(queues = "order.created")
    public void onOrderCreated(String message) {
        OrderDTO dto = JSON.parseObject(message, OrderDTO.class);

        try {
            // 扣减库存
            inventoryDao.deduct(dto.getProductId(), dto.getQuantity());
        } catch (Exception e) {
            // 失败重试（MQ重新投递）
            throw new RuntimeException("扣减库存失败", e);
        }
    }
}
```

**优点**：
- 实现简单
- 性能好（异步）
- 可靠性高（消息持久化）

**缺点**：
- 只能保证最终一致性
- 需要定时任务扫描

**适用场景**：允许短暂不一致的业务（如订单-库存-积分）

#### 4.3 SAGA模式

**原理**：将长事务拆分为多个本地短事务，定义正向操作和补偿操作

**实现示例**：

```java
// 使用Apache Camel或Spring State Machine实现
@Configuration
public class OrderSagaConfig {

    @Bean
    public StateMachine<States, Events> buildSagaMachine() {
        StateMachineBuilder.Builder<States, Events> builder =
            StateMachineBuilder.builder();

        builder.configureStates()
            .withStates()
            .initial(States.START)
            .state(States.ORDER_CREATED)
            .state(States.INVENTORY_DEDUCTED)
            .state(States.PAYMENT_COMPLETED)
            .end(States.SUCCESS)
            .end(States.FAILED);

        builder.configureTransitions()
            // 正向流程
            .withExternal()
                .source(States.START).target(States.ORDER_CREATED)
                .event(Events.CREATE_ORDER)
                .action(createOrderAction())
            .and()
            .withExternal()
                .source(States.ORDER_CREATED).target(States.INVENTORY_DEDUCTED)
                .event(Events.DEDUCT_INVENTORY)
                .action(deductInventoryAction())
            .and()
            // 补偿流程
            .withExternal()
                .source(States.INVENTORY_DEDUCTED).target(States.FAILED)
                .event(Events.PAYMENT_FAILED)
                .action(compensateInventoryAction());

        return builder.build();
    }

    // 正向操作
    private Action<States, Events> createOrderAction() {
        return context -> orderService.createOrder();
    }

    // 补偿操作
    private Action<States, Events> compensateInventoryAction() {
        return context -> inventoryService.compensate();
    }
}
```

**优点**：
- 适合长流程业务
- 无需锁资源

**缺点**：
- 需要设计补偿操作
- 实现复杂

### 5. 方案对比与选择

| 方案 | 一致性 | 性能 | 复杂度 | 适用场景 |
|------|--------|------|--------|----------|
| **XA/2PC** | 强一致 | ⭐⭐ | ⭐⭐⭐ | 金融支付 |
| **Seata AT** | 强一致 | ⭐⭐⭐ | ⭐⭐ | 一般业务 |
| **TCC** | 最终一致 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 高并发核心业务 |
| **本地消息表** | 最终一致 | ⭐⭐⭐⭐⭐ | ⭐⭐ | 异步解耦场景 |
| **SAGA** | 最终一致 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 长流程业务 |

### 6. 实际应用建议

```java
// 推荐的决策树
public class TransactionSolutionSelector {

    public Solution select(BusinessScenario scenario) {
        // 1. 强一致性要求？
        if (scenario.requireStrongConsistency()) {
            // 1.1 性能要求不高？
            if (!scenario.requireHighPerformance()) {
                return Solution.XA_2PC;
            }
            // 1.2 性能要求高？
            return Solution.SEATA_AT;
        }

        // 2. 最终一致性可接受
        // 2.1 业务简单，异步即可？
        if (scenario.canAsync()) {
            return Solution.LOCAL_MESSAGE_TABLE;
        }

        // 2.2 需要同步返回结果？
        if (scenario.needSyncResponse()) {
            return Solution.TCC;
        }

        // 2.3 长流程，多步骤？
        if (scenario.isLongProcess()) {
            return Solution.SAGA;
        }

        return Solution.LOCAL_MESSAGE_TABLE;  // 默认推荐
    }
}
```

### 7. 核心要点总结

1. **优先考虑业务设计避免分布式事务**：通过合理的分片策略（如ER分片）将相关数据放在同一分片
2. **强一致性首选Seata AT**：比XA性能好，比TCC实现简单
3. **最终一致性首选本地消息表**：实现简单，性能好，可靠性高
4. **TCC适合高并发核心业务**：虽然复杂，但性能最优
5. **根据CAP定理权衡**：大多数业务场景选择AP（最终一致性）即可
6. **做好幂等性和补偿机制**：分布式事务必须考虑重试和补偿
7. **监控和告警很重要**：及时发现事务异常，人工介入处理
