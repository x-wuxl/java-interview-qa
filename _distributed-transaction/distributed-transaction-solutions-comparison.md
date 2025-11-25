---
title: "分布式事务方案对比：2PC、3PC、TCC、消息补偿"
date: 2025-11-02
description: "全面对比两阶段提交、三阶段提交、TCC、基于消息补偿的最终一致性等主流分布式事务方案，分析各方案的原理、优缺点和适用场景"
author: "wuxl"
categories: [分布式]
tags: [分布式事务, 2PC, 3PC, TCC, 消息队列, 方案对比, 技术选型]
nav_order: 505
parent: 分布式事务
---
## 问题

分布式事务方案：两阶段提交、三阶段提交、TCC、基于消息补偿的最终一致性

## 答案

### 1. 方案概览

分布式事务解决方案可以按照一致性强度分为两大类：

```
刚性事务（强一致性）           柔性事务（最终一致性）
        ↓                              ↓
    ┌───┴───┐                    ┌─────┴─────┐
    │       │                    │           │
   2PC     3PC                  TCC    消息补偿方案
   XA                           Saga   ┌──────┴──────┐
                                       │             │
                                   本地消息表    事务消息
                                               (RocketMQ)
```

### 2. 两阶段提交（2PC）

#### 原理回顾

**阶段划分**：
```
阶段1：Prepare（准备）
  - 协调者询问所有参与者是否可以提交
  - 参与者执行事务操作（但不提交）
  - 参与者锁定资源，返回Yes/No

阶段2：Commit/Rollback（提交/回滚）
  - 所有参与者返回Yes → 协调者发送Commit
  - 任一参与者返回No → 协调者发送Rollback
```

**执行时序**：
```java
// 协调者代码示例
public boolean execute2PC(Transaction tx) {
    List<Participant> participants = tx.getParticipants();
    
    // ===== 阶段1：Prepare =====
    for (Participant p : participants) {
        boolean prepared = p.prepare(tx);
        if (!prepared) {
            // 有参与者准备失败，执行回滚
            rollback(participants);
            return false;
        }
    }
    
    // ===== 阶段2：Commit =====
    for (Participant p : participants) {
        p.commit(tx);
    }
    return true;
}
```

#### 核心问题

**问题1：同步阻塞**
```
时间线：
0ms  ────→ 协调者发送Prepare
10ms ────→ 参与者锁定资源
         ↓
         [阻塞期：资源被锁定]
         ↓
100ms ───→ 协调者发送Commit
110ms ───→ 参与者释放资源

在10ms-110ms期间，资源被锁定，其他事务无法访问
```

**问题2：单点故障**
```
场景：协调者在Commit前崩溃
协调者 [崩溃] ✗
  |
  |─Prepare→ 参与者1 [资源锁定，等待...]
  |─Prepare→ 参与者2 [资源锁定，等待...]
  |─Prepare→ 参与者3 [资源锁定，等待...]
  
结果：参与者无限期等待，资源无法释放
```

**问题3：数据不一致**
```
场景：部分参与者收到Commit，部分未收到
协调者
  |─Commit→ 参与者1 [已提交] ✓
  |─Commit✗ 参与者2 [网络故障，未收到]
  |─Commit✗ 参与者3 [网络故障，未收到]
  
结果：参与者1已提交，参与者2、3不知所措
```

#### 优缺点总结

**优点**：
- ✅ 强一致性保证
- ✅ 实现相对简单
- ✅ 有成熟的实现（XA协议）

**缺点**：
- ❌ 同步阻塞，性能差
- ❌ 单点故障风险
- ❌ 可能数据不一致
- ❌ 不适合高并发场景

**适用场景**：
- 对一致性要求极高的场景（金融交易）
- 并发量不大的系统
- 短事务场景

### 3. 三阶段提交（3PC）

#### 原理回顾

**阶段划分**：
```
阶段1：CanCommit（询问）
  - 协调者询问参与者是否可以执行事务
  - 参与者只做检查，不执行事务，不锁资源

阶段2：PreCommit（预提交）
  - 参与者执行事务操作（但不提交）
  - 参与者锁定资源
  - 引入超时机制

阶段3：DoCommit（提交）
  - 参与者提交或回滚事务
  - 参与者超时后自动提交
```

**与2PC对比**：
```
2PC:
  Prepare（执行+锁定）  →  Commit/Rollback
  
3PC:
  CanCommit（只检查）  →  PreCommit（执行+锁定）  →  DoCommit
  
改进点：
1. 拆分Prepare阶段，减少锁定时间
2. 引入超时机制，降低阻塞风险
```

#### 超时机制

```java
// 参与者超时处理
public void preCommit(Transaction tx) {
    // 执行事务
    executeTransaction(tx);
    
    // 启动超时定时器
    ScheduledFuture<?> timeout = scheduler.schedule(() -> {
        // 超时后自动提交（假设PreCommit成功说明大概率会提交）
        commit(tx);
        log.info("Auto commit after timeout");
    }, TIMEOUT_SECONDS, TimeUnit.SECONDS);
    
    // 等待DoCommit命令
    waitForDoCommit(tx, timeout);
}
```

#### 核心问题

**问题：仍无法完全避免数据不一致**
```
场景：协调者发送DoCommit时网络分区
协调者本应发送Abort，但网络分区了：
  |─DoCommit✗ 参与者1 [超时，自动提交] ✗错误
  |─DoCommit✗ 参与者2 [超时，自动提交] ✗错误
  
结果：参与者误以为应该提交，实际应该回滚
```

#### 优缺点总结

**优点**：
- ✅ 降低阻塞时间
- ✅ 降低单点故障影响

**缺点**：
- ❌ 实现复杂度更高
- ❌ 性能更差（多一次网络往返）
- ❌ 仍可能数据不一致
- ❌ 实际应用很少

**适用场景**：
- 理论意义大于实际意义
- 生产环境几乎不用

### 4. TCC（Try-Confirm-Cancel）

#### 原理回顾

**阶段划分**：
```
Try（尝试）：
  - 完成业务检查
  - 预留必要资源
  - 不执行实际业务

Confirm（确认）：
  - 使用Try阶段预留的资源
  - 真正执行业务

Cancel（取消）：
  - 释放Try阶段预留的资源
  - 执行补偿逻辑
```

#### 完整案例

**电商下单场景**：
```java
// 主事务服务
@Service
public class OrderTccService {
    
    @Autowired
    private AccountTccService accountService;
    @Autowired
    private InventoryTccService inventoryService;
    
    public void createOrder(Order order) {
        String txId = generateTxId();
        
        try {
            // ===== Try阶段 =====
            accountService.tryDeduct(order.getAccountId(), order.getAmount(), txId);
            inventoryService.tryDeduct(order.getProductId(), order.getQuantity(), txId);
            orderService.tryCreate(order, txId);
            
            // ===== Confirm阶段 =====
            accountService.confirmDeduct(order.getAccountId(), order.getAmount(), txId);
            inventoryService.confirmDeduct(order.getProductId(), order.getQuantity(), txId);
            orderService.confirmCreate(order.getOrderId(), txId);
            
        } catch (Exception e) {
            // ===== Cancel阶段 =====
            accountService.cancelDeduct(order.getAccountId(), order.getAmount(), txId);
            inventoryService.cancelDeduct(order.getProductId(), order.getQuantity(), txId);
            orderService.cancelCreate(order.getOrderId(), txId);
        }
    }
}

// 账户服务TCC实现
@Service
public class AccountTccService {
    
    // Try：冻结金额
    @Transactional
    public void tryDeduct(String accountId, BigDecimal amount, String txId) {
        // 检查余额
        Account account = accountMapper.selectById(accountId);
        if (account.getBalance().compareTo(amount) < 0) {
            throw new InsufficientBalanceException();
        }
        
        // 冻结金额
        accountMapper.freezeAmount(accountId, amount);
        
        // 记录TCC日志（幂等）
        tccLogMapper.insert(txId, "account", TccStatus.TRYING);
    }
    
    // Confirm：扣减冻结金额
    @Transactional
    public void confirmDeduct(String accountId, BigDecimal amount, String txId) {
        // 幂等性检查
        if (isAlreadyConfirmed(txId)) {
            return;
        }
        
        // 扣减冻结金额
        accountMapper.deductFrozenAmount(accountId, amount);
        
        // 更新状态
        tccLogMapper.updateStatus(txId, "account", TccStatus.CONFIRMED);
    }
    
    // Cancel：解冻金额
    @Transactional
    public void cancelDeduct(String accountId, BigDecimal amount, String txId) {
        // 幂等性检查
        if (isAlreadyCanceled(txId)) {
            return;
        }
        
        // 解冻金额
        accountMapper.unfreezeAmount(accountId, amount);
        
        // 更新状态
        tccLogMapper.updateStatus(txId, "account", TccStatus.CANCELED);
    }
}
```

**数据库设计**：
```sql
-- 账户表（支持资源预留）
CREATE TABLE account (
    id VARCHAR(64) PRIMARY KEY,
    balance DECIMAL(20, 2) NOT NULL,         -- 可用余额
    frozen_amount DECIMAL(20, 2) NOT NULL    -- 冻结金额
);

-- TCC事务日志表
CREATE TABLE tcc_transaction (
    tx_id VARCHAR(64) PRIMARY KEY,
    service_name VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- TRYING, CONFIRMED, CANCELED
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL
);
```

#### 关键设计点

**设计点1：幂等性**
```java
// 通过唯一键保证幂等
public void tryDeduct(String accountId, BigDecimal amount, String txId) {
    // 查询是否已执行
    if (tccLogMapper.exists(txId)) {
        return; // 已执行，直接返回
    }
    
    // 首次执行
    // ...
}
```

**设计点2：空回滚**
```java
// Cancel时Try可能还没执行
public void cancelDeduct(String accountId, BigDecimal amount, String txId) {
    TccLog log = tccLogMapper.selectByTxId(txId);
    if (log == null) {
        // Try未执行，记录Cancel状态，防止后续Try
        tccLogMapper.insert(txId, TccStatus.CANCELED);
        return;
    }
    
    // 正常Cancel流程
    // ...
}
```

**设计点3：防悬挂**
```java
// Try时检查是否已经Cancel
public void tryDeduct(String accountId, BigDecimal amount, String txId) {
    TccLog log = tccLogMapper.selectByTxId(txId);
    if (log != null && log.getStatus() == TccStatus.CANCELED) {
        // 已经Cancel过，不能再Try
        throw new BusinessException("Transaction already canceled");
    }
    
    // 正常Try流程
    // ...
}
```

#### 优缺点总结

**优点**：
- ✅ 性能好（不长时间锁定资源）
- ✅ 数据一致性强
- ✅ 无单点故障

**缺点**：
- ❌ 实现复杂（需实现Try、Confirm、Cancel）
- ❌ 对业务侵入大
- ❌ 需要设计资源预留机制

**适用场景**：
- 对一致性和性能都有要求
- 能够设计资源预留机制
- 典型应用：电商下单、支付

### 5. 基于消息补偿的最终一致性

#### 方案1：本地消息表

**原理**：利用本地事务保证业务操作和消息发送的原子性。

```java
@Service
public class OrderService {
    
    @Autowired
    private OrderMapper orderMapper;
    @Autowired
    private LocalMessageMapper messageMapper;
    
    /**
     * 创建订单
     */
    @Transactional
    public void createOrder(Order order) {
        // 1. 创建订单（业务操作）
        orderMapper.insert(order);
        
        // 2. 插入本地消息表（同一个本地事务）
        LocalMessage message = new LocalMessage();
        message.setId(UUID.randomUUID().toString());
        message.setContent(JSON.toJSONString(order));
        message.setStatus(MessageStatus.PENDING);
        messageMapper.insert(message);
        
        // 本地事务保证以上两步的原子性
    }
}

// 定时任务发送待发送的消息
@Component
public class MessageSender {
    
    @Scheduled(fixedDelay = 1000)
    public void sendPendingMessages() {
        // 查询待发送的消息
        List<LocalMessage> messages = messageMapper.selectPending();
        
        for (LocalMessage message : messages) {
            try {
                // 发送到MQ
                mqProducer.send("order-topic", message.getContent());
                
                // 更新消息状态
                message.setStatus(MessageStatus.SENT);
                messageMapper.updateById(message);
                
            } catch (Exception e) {
                // 发送失败，下次重试
                log.error("Failed to send message", e);
            }
        }
    }
}
```

**数据库设计**：
```sql
-- 本地消息表
CREATE TABLE local_message (
    id VARCHAR(64) PRIMARY KEY,
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- PENDING, SENT, CONSUMED
    retry_count INT DEFAULT 0,
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL,
    INDEX idx_status (status)
);
```

**流程图**：
```
订单服务                              MQ                      库存服务
   |                                  |                          |
   |--[本地事务]-------------------   |                          |
   |  1. 创建订单                     |                          |
   |  2. 插入消息表                   |                          |
   |--[本地事务结束]---------------   |                          |
   |                                  |                          |
   |--[定时任务扫描]---------------   |                          |
   |--发送消息------------------->    |                          |
   |                                  |--消费消息------------->  |
   |                                  |                     [扣减库存]
```

**优点**：
- ✅ 实现简单
- ✅ 利用本地事务保证可靠性
- ✅ 最终一致性

**缺点**：
- ❌ 与业务耦合（需要消息表）
- ❌ 消息可能重复（需要下游幂等）

#### 方案2：RocketMQ事务消息

**原理**：RocketMQ提供的半消息机制。

```java
@Service
public class OrderService {
    
    @Autowired
    private TransactionMQProducer producer;
    
    /**
     * 创建订单
     */
    public void createOrder(Order order) {
        // 发送事务消息
        producer.sendMessageInTransaction(
            new Message("order-topic", JSON.toJSONString(order).getBytes()),
            order
        );
    }
}

// 事务监听器
@Component
class OrderTransactionListener implements TransactionListener {
    
    /**
     * 执行本地事务
     */
    @Override
    public LocalTransactionState executeLocalTransaction(Message msg, Object arg) {
        try {
            Order order = (Order) arg;
            
            // 执行本地事务：创建订单
            orderMapper.insert(order);
            
            // 本地事务成功，提交消息
            return LocalTransactionState.COMMIT_MESSAGE;
            
        } catch (Exception e) {
            // 本地事务失败，回滚消息
            return LocalTransactionState.ROLLBACK_MESSAGE;
        }
    }
    
    /**
     * 回查本地事务状态
     */
    @Override
    public LocalTransactionState checkLocalTransaction(MessageExt msg) {
        // MQ回查：本地事务是否执行成功？
        String orderId = extractOrderId(msg);
        Order order = orderMapper.selectById(orderId);
        
        if (order != null) {
            // 订单存在，提交消息
            return LocalTransactionState.COMMIT_MESSAGE;
        } else {
            // 订单不存在，回滚消息
            return LocalTransactionState.ROLLBACK_MESSAGE;
        }
    }
}
```

**流程图**：
```
订单服务              RocketMQ Broker           库存服务
   |                        |                       |
   |--1.发送半消息--------> |                       |
   |<--2.半消息已存储-------|                       |
   |                        |                       |
   |--3.执行本地事务        |                       |
   |  (创建订单)            |                       |
   |                        |                       |
   |--4.提交/回滚消息-----> |                       |
   |                        |                       |
   |                        |--5.可见消息---------> |
   |                        |                  [扣减库存]
   |                        |                       |
   |<--6.回查本地事务-------|                       |
   |--7.返回本地事务状态--> |                       |
```

**优点**：
- ✅ RocketMQ原生支持
- ✅ 实现相对简单
- ✅ 可靠性高

**缺点**：
- ❌ 依赖RocketMQ
- ❌ 只能保证最终一致性

#### 方案3：最大努力通知

**原理**：主动通知+定期对账。

```java
@Service
public class OrderNotificationService {
    
    /**
     * 创建订单后通知下游
     */
    @Transactional
    public void createOrder(Order order) {
        // 1. 创建订单
        orderMapper.insert(order);
        
        // 2. 异步通知下游（最大努力）
        asyncNotify(order);
    }
    
    /**
     * 异步通知（重试机制）
     */
    private void asyncNotify(Order order) {
        executor.execute(() -> {
            int maxRetry = 3;
            for (int i = 0; i < maxRetry; i++) {
                try {
                    // 调用下游接口
                    restTemplate.postForObject(
                        "http://inventory-service/api/deduct",
                        order,
                        String.class
                    );
                    return; // 成功则返回
                } catch (Exception e) {
                    log.error("Notify failed, retry {}/{}", i + 1, maxRetry, e);
                    sleep(1000 * (i + 1)); // 递增延迟
                }
            }
            
            // 重试失败，记录到失败表
            notificationFailureMapper.insert(order.getId());
        });
    }
    
    /**
     * 定期对账
     */
    @Scheduled(cron = "0 0 2 * * ?")
    public void reconcile() {
        // 查询昨天的订单
        List<Order> orders = orderMapper.selectYesterday();
        
        // 查询下游的库存扣减记录
        List<String> deductedOrderIds = inventoryService.getDeductedOrders();
        
        // 找出差异
        Set<String> diff = orders.stream()
            .map(Order::getId)
            .filter(id -> !deductedOrderIds.contains(id))
            .collect(Collectors.toSet());
        
        // 补偿通知
        for (String orderId : diff) {
            Order order = orderMapper.selectById(orderId);
            asyncNotify(order);
        }
    }
}
```

**优点**：
- ✅ 实现简单
- ✅ 对下游系统要求低

**缺点**：
- ❌ 可靠性最低
- ❌ 需要定期对账

### 6. 方案对比总结

#### 对比表格

| 方案 | 一致性 | 性能 | 复杂度 | 业务侵入 | 适用场景 |
|------|--------|------|--------|----------|----------|
| **2PC/XA** | 强一致 | ★☆☆ | ★★☆ | ★☆☆ | 金融交易、对一致性要求极高 |
| **3PC** | 强一致 | ★☆☆ | ★★★ | ★☆☆ | 理论研究，实际几乎不用 |
| **TCC** | 最终一致 | ★★★ | ★★★ | ★★★ | 电商下单、对性能和一致性都有要求 |
| **本地消息表** | 最终一致 | ★★★ | ★★☆ | ★★☆ | 简单场景、可接受最终一致 |
| **事务消息** | 最终一致 | ★★★ | ★★☆ | ★☆☆ | 使用RocketMQ的系统 |
| **最大努力通知** | 弱一致 | ★★★ | ★☆☆ | ★☆☆ | 通知类场景、对一致性要求低 |

#### 选型决策树

```
是否需要强一致性？
  ├─ 是 → 是否能接受性能损失？
  │      ├─ 是 → 2PC/XA
  │      └─ 否 → 考虑TCC或优化业务逻辑
  │
  └─ 否 → 可以接受最终一致性
         ├─ 是否使用RocketMQ？
         │   ├─ 是 → 事务消息
         │   └─ 否 → 继续
         │
         ├─ 是否需要业务补偿？
         │   ├─ 是 → TCC
         │   └─ 否 → 继续
         │
         ├─ 对可靠性要求高？
         │   ├─ 是 → 本地消息表
         │   └─ 否 → 最大努力通知
```

### 7. 实际应用建议

**场景1：金融支付**
```
选择：2PC/XA
原因：对一致性要求极高，可接受性能损失
```

**场景2：电商下单**
```
选择：TCC 或 Seata AT模式
原因：对性能和一致性都有要求
```

**场景3：订单通知**
```
选择：事务消息 或 本地消息表
原因：可接受最终一致性，实现简单
```

**场景4：日志同步**
```
选择：最大努力通知
原因：对一致性要求不高，允许丢失
```

### 8. 总结

**核心要点**：
- 没有完美的方案，只有合适的方案
- 刚性事务保证强一致性，但性能差
- 柔性事务保证最终一致性，性能好
- 根据业务特性选择合适的一致性级别

**最佳实践**：
1. 优先考虑避免分布式事务（业务拆分、异步化）
2. 能用消息解决的，不用TCC
3. 能用TCC解决的，不用2PC
4. 互联网系统优先选择柔性事务

**面试要点**：
- 能清晰对比各方案的优缺点
- 理解不同方案的适用场景
- 掌握方案选型的决策依据
- 了解实际项目中的应用

