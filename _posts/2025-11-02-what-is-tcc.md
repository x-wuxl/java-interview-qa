---
layout: post
title: "什么是TCC？"
date: 2025-11-02
description: "深入讲解TCC分布式事务模式的原理、三个阶段的实现、幂等性设计、异常处理以及在电商等场景中的实战应用"
author: "wuxl"
categories: [分布式]
tags: [分布式事务, TCC, Try-Confirm-Cancel, 柔性事务, Seata]
---

## 问题

什么是TCC？

## 答案

### 1. 核心概念

**TCC（Try-Confirm-Cancel）**是一种柔性分布式事务解决方案，属于**业务层面的两阶段提交**。与2PC在数据库层面实现不同，TCC通过业务代码实现事务管理，将事务分为三个操作：

- **Try（尝试）**：完成所有业务检查，预留必要的业务资源
- **Confirm（确认）**：真正执行业务，使用Try阶段预留的资源
- **Cancel（取消）**：释放Try阶段预留的资源

**核心思想**：通过业务逻辑实现资源预留和补偿，而不是依赖数据库锁。

### 2. TCC原理与流程

#### 执行流程

```
主事务服务
   |
   |---(1) Try阶段--->  [检查+预留资源]
   |        |
   |        ├─> 订单服务.try()     ✓
   |        ├─> 库存服务.try()     ✓
   |        └─> 账户服务.try()     ✓
   |
   |---(2) Confirm阶段--> [确认执行]
   |        |
   |        ├─> 订单服务.confirm()  ✓
   |        ├─> 库存服务.confirm()  ✓
   |        └─> 账户服务.confirm()  ✓
   |
   |--- 事务提交成功
```

**失败场景**：
```
主事务服务
   |
   |---(1) Try阶段
   |        |
   |        ├─> 订单服务.try()     ✓
   |        ├─> 库存服务.try()     ✓
   |        └─> 账户服务.try()     ✗ (余额不足)
   |
   |---(2) Cancel阶段--> [回滚补偿]
   |        |
   |        ├─> 库存服务.cancel()   释放库存
   |        └─> 订单服务.cancel()   取消订单
   |
   |--- 事务回滚
```

### 3. 三个阶段详解

#### Try阶段（尝试）

**职责**：
1. 完成所有业务检查（一致性检查）
2. 预留必要的业务资源（准隔离性）
3. 不执行实际的业务操作

**账户扣款的Try实现**：
```java
@Service
public class AccountService {
    
    @Autowired
    private AccountMapper accountMapper;
    
    /**
     * Try阶段：冻结金额
     */
    @Transactional
    public boolean tryDeduct(String accountId, BigDecimal amount, String txId) {
        // 1. 检查账户是否存在
        Account account = accountMapper.selectById(accountId);
        if (account == null) {
            throw new BusinessException("账户不存在");
        }
        
        // 2. 检查余额是否充足
        if (account.getBalance().compareTo(amount) < 0) {
            throw new BusinessException("余额不足");
        }
        
        // 3. 检查是否重复Try（幂等性）
        TccTransaction tcc = tccMapper.selectByTxId(txId);
        if (tcc != null) {
            // 已经Try过，直接返回成功
            return true;
        }
        
        // 4. 冻结金额（预留资源）
        int updated = accountMapper.freezeAmount(
            accountId, 
            amount,
            account.getVersion() // 乐观锁
        );
        
        if (updated == 0) {
            throw new BusinessException("冻结金额失败");
        }
        
        // 5. 记录TCC事务日志
        TccTransaction tccLog = new TccTransaction();
        tccLog.setTxId(txId);
        tccLog.setAccountId(accountId);
        tccLog.setAmount(amount);
        tccLog.setStatus(TccStatus.TRYING);
        tccMapper.insert(tccLog);
        
        return true;
    }
}
```

**对应的数据库操作**：
```sql
-- 账户表结构
CREATE TABLE account (
    id VARCHAR(64) PRIMARY KEY,
    balance DECIMAL(20, 2) NOT NULL,      -- 可用余额
    frozen_amount DECIMAL(20, 2) NOT NULL, -- 冻结金额
    version INT NOT NULL                   -- 乐观锁版本号
);

-- 冻结金额SQL
UPDATE account 
SET balance = balance - #{amount},
    frozen_amount = frozen_amount + #{amount},
    version = version + 1
WHERE id = #{accountId} 
  AND balance >= #{amount}
  AND version = #{version};
```

#### Confirm阶段（确认）

**职责**：
1. 使用Try阶段预留的资源
2. 真正执行业务操作
3. Confirm操作必须保证幂等性

**账户扣款的Confirm实现**：
```java
/**
 * Confirm阶段：确认扣款
 */
@Transactional
public void confirmDeduct(String accountId, BigDecimal amount, String txId) {
    // 1. 检查TCC事务是否存在
    TccTransaction tcc = tccMapper.selectByTxId(txId);
    if (tcc == null) {
        throw new BusinessException("TCC事务不存在");
    }
    
    // 2. 幂等性检查
    if (tcc.getStatus() == TccStatus.CONFIRMED) {
        // 已经Confirm过，直接返回
        return;
    }
    
    if (tcc.getStatus() == TccStatus.CANCELED) {
        throw new BusinessException("TCC事务已取消");
    }
    
    // 3. 扣减冻结金额（真正扣款）
    accountMapper.deductFrozenAmount(accountId, amount);
    
    // 4. 更新TCC事务状态
    tcc.setStatus(TccStatus.CONFIRMED);
    tcc.setUpdateTime(new Date());
    tccMapper.updateById(tcc);
}
```

**对应的SQL**：
```sql
-- 扣减冻结金额
UPDATE account 
SET frozen_amount = frozen_amount - #{amount}
WHERE id = #{accountId} 
  AND frozen_amount >= #{amount};
```

#### Cancel阶段（取消）

**职责**：
1. 释放Try阶段预留的资源
2. 执行补偿逻辑
3. Cancel操作必须保证幂等性

**账户扣款的Cancel实现**：
```java
/**
 * Cancel阶段：取消扣款（补偿）
 */
@Transactional
public void cancelDeduct(String accountId, BigDecimal amount, String txId) {
    // 1. 检查TCC事务是否存在
    TccTransaction tcc = tccMapper.selectByTxId(txId);
    if (tcc == null) {
        // Try阶段都没执行，无需Cancel
        return;
    }
    
    // 2. 幂等性检查
    if (tcc.getStatus() == TccStatus.CANCELED) {
        // 已经Cancel过，直接返回
        return;
    }
    
    if (tcc.getStatus() == TccStatus.CONFIRMED) {
        throw new BusinessException("TCC事务已确认，无法取消");
    }
    
    // 3. 解冻金额（释放资源）
    accountMapper.unfreezeAmount(accountId, amount);
    
    // 4. 更新TCC事务状态
    tcc.setStatus(TccStatus.CANCELED);
    tcc.setUpdateTime(new Date());
    tccMapper.updateById(tcc);
}
```

**对应的SQL**：
```sql
-- 解冻金额
UPDATE account 
SET balance = balance + #{amount},
    frozen_amount = frozen_amount - #{amount}
WHERE id = #{accountId} 
  AND frozen_amount >= #{amount};
```

### 4. 完整案例：电商下单

#### 业务场景

用户下单购买商品，需要：
1. 创建订单
2. 扣减库存
3. 扣减账户余额

#### 主事务服务

```java
@Service
public class OrderService {
    
    @Autowired
    private OrderTccService orderTccService;
    @Autowired
    private InventoryTccService inventoryTccService;
    @Autowired
    private AccountTccService accountTccService;
    @Autowired
    private TccTransactionManager tccManager;
    
    /**
     * 创建订单（TCC主事务）
     */
    public void createOrder(OrderDTO orderDTO) {
        String txId = UUID.randomUUID().toString();
        
        try {
            // ========== Try阶段 ==========
            tccManager.begin(txId);
            
            // 1. 创建订单（Try）
            orderTccService.tryCreate(orderDTO, txId);
            
            // 2. 扣减库存（Try）
            inventoryTccService.tryDeduct(
                orderDTO.getProductId(), 
                orderDTO.getQuantity(), 
                txId
            );
            
            // 3. 扣减余额（Try）
            accountTccService.tryDeduct(
                orderDTO.getAccountId(), 
                orderDTO.getAmount(), 
                txId
            );
            
            // ========== Confirm阶段 ==========
            // Try全部成功，执行Confirm
            orderTccService.confirmCreate(orderDTO.getOrderId(), txId);
            inventoryTccService.confirmDeduct(
                orderDTO.getProductId(), 
                orderDTO.getQuantity(), 
                txId
            );
            accountTccService.confirmDeduct(
                orderDTO.getAccountId(), 
                orderDTO.getAmount(), 
                txId
            );
            
            tccManager.commit(txId);
            
        } catch (Exception e) {
            // ========== Cancel阶段 ==========
            // Try失败，执行Cancel补偿
            try {
                accountTccService.cancelDeduct(
                    orderDTO.getAccountId(), 
                    orderDTO.getAmount(), 
                    txId
                );
                inventoryTccService.cancelDeduct(
                    orderDTO.getProductId(), 
                    orderDTO.getQuantity(), 
                    txId
                );
                orderTccService.cancelCreate(orderDTO.getOrderId(), txId);
                
                tccManager.rollback(txId);
            } catch (Exception cancelEx) {
                // Cancel失败，需要重试或人工介入
                log.error("Cancel failed, txId: {}", txId, cancelEx);
            }
            
            throw new BusinessException("创建订单失败", e);
        }
    }
}
```

#### 库存服务TCC实现

```java
@Service
public class InventoryTccService {
    
    /**
     * Try：锁定库存
     */
    @Transactional
    public void tryDeduct(String productId, int quantity, String txId) {
        // 1. 检查库存是否充足
        Inventory inventory = inventoryMapper.selectById(productId);
        if (inventory.getAvailable() < quantity) {
            throw new BusinessException("库存不足");
        }
        
        // 2. 幂等性检查
        if (tccMapper.exists(txId, "inventory")) {
            return;
        }
        
        // 3. 锁定库存
        inventoryMapper.lockStock(productId, quantity);
        
        // 4. 记录TCC日志
        tccMapper.insert(txId, "inventory", TccStatus.TRYING);
    }
    
    /**
     * Confirm：扣减锁定的库存
     */
    @Transactional
    public void confirmDeduct(String productId, int quantity, String txId) {
        // 幂等性检查
        TccLog log = tccMapper.selectByTxId(txId, "inventory");
        if (log.getStatus() == TccStatus.CONFIRMED) {
            return;
        }
        
        // 扣减锁定库存
        inventoryMapper.deductLockedStock(productId, quantity);
        
        // 更新状态
        tccMapper.updateStatus(txId, "inventory", TccStatus.CONFIRMED);
    }
    
    /**
     * Cancel：释放锁定的库存
     */
    @Transactional
    public void cancelDeduct(String productId, int quantity, String txId) {
        TccLog log = tccMapper.selectByTxId(txId, "inventory");
        if (log == null || log.getStatus() == TccStatus.CANCELED) {
            return;
        }
        
        // 释放库存
        inventoryMapper.unlockStock(productId, quantity);
        
        // 更新状态
        tccMapper.updateStatus(txId, "inventory", TccStatus.CANCELED);
    }
}
```

**库存表结构**：
```sql
CREATE TABLE inventory (
    product_id VARCHAR(64) PRIMARY KEY,
    total INT NOT NULL,            -- 总库存
    available INT NOT NULL,        -- 可用库存
    locked INT NOT NULL            -- 锁定库存
);

-- 锁定库存
UPDATE inventory 
SET available = available - #{quantity},
    locked = locked + #{quantity}
WHERE product_id = #{productId} 
  AND available >= #{quantity};

-- 扣减锁定库存
UPDATE inventory 
SET locked = locked - #{quantity}
WHERE product_id = #{productId} 
  AND locked >= #{quantity};

-- 释放库存
UPDATE inventory 
SET available = available + #{quantity},
    locked = locked - #{quantity}
WHERE product_id = #{productId};
```

### 5. TCC核心设计要点

#### 要点1：幂等性

**为什么需要幂等**：
- 网络超时重试
- 框架自动重试
- 异常恢复重试

**幂等性实现**：
```java
// 方式1：通过事务日志表
public boolean tryDeduct(String accountId, BigDecimal amount, String txId) {
    // 查询是否已经执行过
    TccLog log = tccMapper.selectByTxId(txId);
    if (log != null) {
        // 已执行，直接返回
        return log.getStatus() == TccStatus.TRYING;
    }
    
    // 首次执行
    // ...
}

// 方式2：使用唯一键约束
CREATE TABLE tcc_transaction (
    tx_id VARCHAR(64) PRIMARY KEY,  -- 事务ID作为主键
    -- ...
);
```

#### 要点2：空回滚

**场景**：Try阶段因网络超时未执行，但Cancel被调用。

```java
public void cancelDeduct(String accountId, BigDecimal amount, String txId) {
    TccLog log = tccMapper.selectByTxId(txId);
    
    // 空回滚：Try都没执行，无需Cancel
    if (log == null) {
        // 插入一条Cancel记录，防止后续Try执行
        tccMapper.insert(txId, TccStatus.CANCELED);
        return;
    }
    
    // 正常Cancel流程
    // ...
}
```

#### 要点3：悬挂

**场景**：Cancel先于Try执行。

```java
public boolean tryDeduct(String accountId, BigDecimal amount, String txId) {
    TccLog log = tccMapper.selectByTxId(txId);
    
    // 防悬挂：如果已经Cancel了，Try不能再执行
    if (log != null && log.getStatus() == TccStatus.CANCELED) {
        throw new BusinessException("事务已取消，不能执行Try");
    }
    
    // 正常Try流程
    // ...
}
```

#### 要点4：资源预留的设计

**方式1：冻结模式（推荐）**
```sql
-- 账户表有冻结字段
balance: 1000       -- 可用余额
frozen_amount: 0    -- 冻结金额

-- Try: 冻结100
balance: 900
frozen_amount: 100

-- Confirm: 扣减冻结金额
balance: 900
frozen_amount: 0

-- Cancel: 解冻
balance: 1000
frozen_amount: 0
```

**方式2：扣减+补偿模式**
```sql
-- Try: 直接扣减
balance: 900

-- Confirm: 无操作
balance: 900

-- Cancel: 补偿回来
balance: 1000
```

### 6. 异常场景处理

#### 场景1：Try阶段超时

```java
// Try超时，不确定是否成功
try {
    accountService.tryDeduct(accountId, amount, txId);
} catch (TimeoutException e) {
    // 不知道Try是否成功，执行Cancel（Cancel需要幂等）
    accountService.cancelDeduct(accountId, amount, txId);
}
```

#### 场景2：Confirm失败

```java
// Confirm失败需要重试
@Retryable(maxAttempts = 3)
public void confirmDeduct(String accountId, BigDecimal amount, String txId) {
    // Confirm逻辑（必须幂等）
}

// 或者通过定时任务补偿
@Scheduled(fixedDelay = 60000)
public void retryFailedConfirm() {
    List<TccLog> failedList = tccMapper.selectFailedConfirm();
    for (TccLog log : failedList) {
        try {
            confirmDeduct(log.getAccountId(), log.getAmount(), log.getTxId());
        } catch (Exception e) {
            log.error("Retry confirm failed", e);
        }
    }
}
```

#### 场景3：Cancel失败

```java
// Cancel失败也需要重试
@Retryable(maxAttempts = 3)
public void cancelDeduct(String accountId, BigDecimal amount, String txId) {
    // Cancel逻辑（必须幂等）
}
```

### 7. TCC框架：Seata

**Seata TCC模式使用**：
```java
// 定义TCC接口
@LocalTCC
public interface AccountTccAction {
    
    @TwoPhaseBusinessAction(
        name = "accountTccAction",
        commitMethod = "confirm",
        rollbackMethod = "cancel"
    )
    boolean try(@BusinessActionContextParameter(paramName = "accountId") String accountId,
                @BusinessActionContextParameter(paramName = "amount") BigDecimal amount);
    
    boolean confirm(BusinessActionContext context);
    
    boolean cancel(BusinessActionContext context);
}

// 实现
@Service
public class AccountTccActionImpl implements AccountTccAction {
    
    @Override
    public boolean try(String accountId, BigDecimal amount) {
        // Try逻辑
        return accountService.tryDeduct(accountId, amount);
    }
    
    @Override
    public boolean confirm(BusinessActionContext context) {
        String accountId = context.getActionContext("accountId");
        BigDecimal amount = context.getActionContext("amount");
        // Confirm逻辑
        accountService.confirmDeduct(accountId, amount);
        return true;
    }
    
    @Override
    public boolean cancel(BusinessActionContext context) {
        String accountId = context.getActionContext("accountId");
        BigDecimal amount = context.getActionContext("amount");
        // Cancel逻辑
        accountService.cancelDeduct(accountId, amount);
        return true;
    }
}

// 使用
@Service
public class OrderService {
    
    @Autowired
    private AccountTccAction accountTccAction;
    
    @GlobalTransactional
    public void createOrder(Order order) {
        // Seata会自动管理TCC流程
        accountTccAction.try(order.getAccountId(), order.getAmount());
        // ...其他操作
    }
}
```

### 8. TCC优缺点

**优点**：
- ✅ **性能较好**：不长时间锁定数据库资源
- ✅ **数据一致性强**：通过补偿机制保证最终一致性
- ✅ **灵活性高**：业务层面控制，可自定义补偿逻辑

**缺点**：
- ❌ **实现复杂**：需要实现Try、Confirm、Cancel三个方法
- ❌ **对业务侵入大**：需要修改业务代码
- ❌ **资源预留成本**：需要设计预留资源的字段和逻辑

### 9. 总结

**核心要点**：
- TCC是业务层面的两阶段提交
- Try预留资源，Confirm确认执行，Cancel释放资源
- 必须保证Confirm和Cancel的幂等性
- 需要处理空回滚和悬挂问题

**适用场景**：
- 对一致性和性能都有要求的场景
- 能够明确设计补偿逻辑的业务
- 典型应用：电商下单、支付场景

**面试要点**：
- 能清晰描述TCC三个阶段的职责
- 理解幂等性、空回滚、悬挂的概念和处理
- 能设计TCC事务的表结构
- 了解Seata等TCC框架的使用

