---
layout: post
title: "AT模式：Seata的自动化两阶段提交"
date: 2025-11-02
description: "深入解析Seata AT模式的原理、工作流程、与传统2PC的区别，理解如何通过自动补偿机制实现分布式事务的高性能和强一致性"
author: "wuxl"
categories: [分布式]
tags: [分布式事务, Seata, AT模式, 两阶段提交, 自动补偿, 数据快照]
---

## 问题

AT模式实际上也是两阶段提交的一种模式

## 答案

### 1. 核心概念

**AT模式（Automatic Transaction）**是Seata最主流的事务模式，是一种**改进的两阶段提交**，也被称为**自动化的TCC**。

**核心思想**：
- 基于**数据快照**和**SQL解析**实现自动补偿
- 一阶段直接提交本地事务（释放锁）
- 二阶段通过回滚日志进行补偿（如果需要回滚）

**与传统2PC的区别**：
- **传统2PC**：一阶段锁定资源，等待二阶段提交
- **AT模式**：一阶段直接提交，二阶段异步处理

### 2. AT模式的执行流程

#### 角色说明

```
TC (Transaction Coordinator)     事务协调器
  ├─ TM (Transaction Manager)    事务管理器（发起全局事务）
  └─ RM (Resource Manager)       资源管理器（管理分支事务）
```

#### 成功场景（完整流程）

```
业务服务（TM）        TC服务器          订单服务（RM）      库存服务（RM）
    |                    |                   |                   |
    |--1.开启全局事务--> |                   |                   |
    |<--返回XID----------|                   |                   |
    |                    |                   |                   |
    |--2.调用订单服务--------------------------->                 |
    |                    |<--3.注册分支------|                   |
    |                    |                   |                   |
    |                    |               [4.执行SQL]             |
    |                    |               [5.记录回滚日志]        |
    |                    |               [6.提交本地事务]        |
    |                    |               [7.释放锁]              |
    |                    |                   |                   |
    |<--8.订单创建成功----------------------|                   |
    |                    |                   |                   |
    |--9.调用库存服务------------------------------------------------>
    |                    |<--10.注册分支-------------------------|
    |                    |                                   [执行SQL]
    |                    |                                   [记录回滚日志]
    |                    |                                   [提交本地事务]
    |                    |                                   [释放锁]
    |<--11.库存扣减成功--------------------------------------------|
    |                    |                   |                   |
    |--12.提交全局事务-→ |                   |                   |
    |                    |--13.通知分支提交->|                   |
    |                    |                   [删除回滚日志]      |
    |                    |--14.通知分支提交---------------------->
    |                    |                                   [删除回滚日志]
```

#### 失败场景（回滚流程）

```
业务服务（TM）        TC服务器          订单服务（RM）      库存服务（RM）
    |                    |                   |                   |
    |--1.开启全局事务--> |                   |                   |
    |--2.订单服务--------|------------------>|                   |
    |                    |               [提交本地事务] ✓        |
    |--3.库存服务--------|---------------------------------->   |
    |                    |                               [失败] ✗
    |                    |                   |                   |
    |--4.回滚全局事务--> |                   |                   |
    |                    |--5.通知分支回滚-->|                   |
    |                    |               [使用回滚日志]          |
    |                    |               [生成反向SQL]           |
    |                    |               [执行补偿]              |
    |                    |               [删除回滚日志]          |
```

### 3. AT模式的核心机制

#### 机制1：数据快照（Undo Log）

**原理**：在执行业务SQL前后，记录数据的前镜像和后镜像。

```java
// 业务代码
@GlobalTransactional
public void updateAccount(String accountId, BigDecimal amount) {
    // 执行业务SQL
    accountMapper.update(
        "UPDATE account SET balance = balance - ? WHERE id = ?",
        amount, accountId
    );
}

// Seata自动生成的Undo Log
{
    "branchId": 123456,
    "xid": "global-tx-001",
    "tableName": "account",
    "beforeImage": {  // 前镜像
        "rows": [{
            "fields": [
                {"name": "id", "value": "A001"},
                {"name": "balance", "value": 1000.00},
                {"name": "version", "value": 1}
            ]
        }]
    },
    "afterImage": {  // 后镜像
        "rows": [{
            "fields": [
                {"name": "id", "value": "A001"},
                {"name": "balance", "value": 900.00},
                {"name": "version", "value": 2}
            ]
        }]
    },
    "sqlType": "UPDATE"
}
```

**Undo Log表结构**：
```sql
CREATE TABLE undo_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    branch_id BIGINT NOT NULL,
    xid VARCHAR(100) NOT NULL,
    context VARCHAR(128) NOT NULL,
    rollback_info LONGBLOB NOT NULL,  -- 序列化的回滚日志
    log_status INT NOT NULL,
    log_created DATETIME NOT NULL,
    log_modified DATETIME NOT NULL,
    UNIQUE KEY ux_undo_log (xid, branch_id)
);
```

#### 机制2：全局锁

**目的**：保证分布式事务的隔离性。

```
场景：两个全局事务同时修改同一行数据

事务1                          全局锁                       事务2
  |                              |                            |
  |--更新 account.id=A001----    |                            |
  |  (本地事务已提交)             |                            |
  |--获取全局锁----------------> |                            |
  |                          [锁定A001]                       |
  |                              |                            |
  |                              |  <--尝试获取全局锁---------|
  |                              |      (等待...)             |
  |                              |                            |
  |--提交全局事务--------------> |                            |
  |                          [释放A001]                       |
  |                              |  [获取A001成功]---------->|
  |                              |                            |
```

**全局锁实现**：
```sql
-- 全局锁表
CREATE TABLE lock_table (
    row_key VARCHAR(128) PRIMARY KEY,    -- 表名:主键值
    xid VARCHAR(100) NOT NULL,           -- 全局事务ID
    transaction_id BIGINT NOT NULL,
    branch_id BIGINT NOT NULL,
    resource_id VARCHAR(256) NOT NULL,
    table_name VARCHAR(64) NOT NULL,
    pk VARCHAR(128) NOT NULL,
    gmt_create DATETIME NOT NULL,
    gmt_modified DATETIME NOT NULL,
    INDEX idx_xid (xid)
);

-- 例如：account:A001 被事务 global-tx-001 锁定
INSERT INTO lock_table (row_key, xid, ...) 
VALUES ('account:A001', 'global-tx-001', ...);
```

**获取全局锁的流程**：
```java
// 分支事务提交前
public void commitBranchTransaction(BranchTransaction branch) {
    // 1. 提交本地事务（释放本地锁）
    localTransaction.commit();
    
    // 2. 向TC注册分支
    tc.branchRegister(branch);
    
    // 3. 获取全局锁（可重试）
    boolean locked = false;
    int retry = 0;
    while (!locked && retry < MAX_RETRY) {
        locked = tc.acquireGlobalLock(branch);
        if (!locked) {
            Thread.sleep(10); // 等待重试
            retry++;
        }
    }
    
    if (!locked) {
        // 获取全局锁失败，回滚本地事务
        rollbackLocalTransaction(branch);
        throw new GlobalLockException();
    }
}
```

#### 机制3：自动补偿

**回滚时的补偿流程**：

```java
// Seata自动生成的补偿逻辑
public void rollback(UndoLog undoLog) {
    // 1. 查询当前数据（校验数据一致性）
    Row currentRow = selectByPk(undoLog.getTableName(), undoLog.getPk());
    
    // 2. 数据校验
    Row afterImage = undoLog.getAfterImage();
    if (!currentRow.equals(afterImage)) {
        // 数据已被修改，可能是脏写
        throw new DataDirtyException("Data has been modified by another transaction");
    }
    
    // 3. 生成反向SQL
    Row beforeImage = undoLog.getBeforeImage();
    String reverseSql = generateReverseSql(undoLog.getSqlType(), beforeImage);
    // 例如：UPDATE account SET balance = 1000.00, version = 1 WHERE id = 'A001'
    
    // 4. 执行补偿
    executeUpdate(reverseSql);
    
    // 5. 删除Undo Log
    deleteUndoLog(undoLog.getBranchId(), undoLog.getXid());
}
```

### 4. AT模式 vs 传统2PC

#### 对比表格

| 维度 | 传统2PC | AT模式 |
|------|---------|--------|
| **锁定时间** | 一阶段锁定到二阶段 | 一阶段即释放 |
| **性能** | 差（同步阻塞） | 好（异步处理） |
| **代码侵入** | 低（数据库层面） | 低（透明） |
| **隔离性** | 强（资源锁定） | 弱（依赖全局锁） |
| **数据一致性** | 强一致 | 最终一致 |
| **补偿方式** | 数据库回滚 | 自动生成反向SQL |

#### 时序对比

**传统2PC**：
```
时间轴：
t0  ─→ Prepare（锁定资源）
       ↓
       [资源锁定期间，其他事务等待]
       ↓
t10 ─→ Commit（释放资源）

锁定时间：10个时间单位
```

**AT模式**：
```
时间轴：
t0  ─→ 执行SQL + 记录Undo Log
t1  ─→ 提交本地事务（释放本地锁）
t2  ─→ 获取全局锁
       ↓
       [只有全局锁，本地锁已释放]
       ↓
t5  ─→ 全局提交（释放全局锁）

本地锁定时间：1个时间单位
全局锁定时间：3个时间单位（但不阻塞本地事务）
```

### 5. AT模式的完整代码示例

#### 业务代码（无侵入）

```java
// 主业务服务
@Service
public class BusinessService {
    
    @Autowired
    private OrderService orderService;
    @Autowired
    private InventoryService inventoryService;
    @Autowired
    private AccountService accountService;
    
    /**
     * 创建订单（全局事务）
     */
    @GlobalTransactional(timeoutMills = 300000, name = "create-order")
    public void createOrder(OrderDTO orderDTO) {
        // 1. 创建订单（分支事务1）
        orderService.createOrder(orderDTO);
        
        // 2. 扣减库存（分支事务2）
        inventoryService.deductStock(
            orderDTO.getProductId(), 
            orderDTO.getQuantity()
        );
        
        // 3. 扣减余额（分支事务3）
        accountService.deductBalance(
            orderDTO.getAccountId(), 
            orderDTO.getAmount()
        );
        
        // Seata自动管理：
        // - 任一服务失败，自动回滚所有分支
        // - 全部成功，自动提交所有分支
    }
}

// 订单服务
@Service
public class OrderService {
    
    @Autowired
    private OrderMapper orderMapper;
    
    /**
     * 创建订单（普通业务代码，无需修改）
     */
    @Transactional
    public void createOrder(OrderDTO orderDTO) {
        Order order = new Order();
        order.setId(orderDTO.getOrderId());
        order.setUserId(orderDTO.getUserId());
        order.setAmount(orderDTO.getAmount());
        
        // 普通的CRUD操作
        orderMapper.insert(order);
        
        // Seata在背后做了：
        // 1. 拦截SQL
        // 2. 查询前镜像
        // 3. 执行业务SQL
        // 4. 查询后镜像
        // 5. 生成Undo Log
        // 6. 提交本地事务
        // 7. 注册分支到TC
        // 8. 上报分支状态
    }
}

// 库存服务
@Service
public class InventoryService {
    
    @Autowired
    private InventoryMapper inventoryMapper;
    
    @Transactional
    public void deductStock(String productId, int quantity) {
        // 普通的业务代码
        Inventory inventory = inventoryMapper.selectById(productId);
        
        if (inventory.getStock() < quantity) {
            throw new InsufficientStockException("库存不足");
        }
        
        inventory.setStock(inventory.getStock() - quantity);
        inventoryMapper.updateById(inventory);
        
        // Seata自动处理分布式事务
    }
}

// 账户服务
@Service
public class AccountService {
    
    @Autowired
    private AccountMapper accountMapper;
    
    @Transactional
    public void deductBalance(String accountId, BigDecimal amount) {
        Account account = accountMapper.selectById(accountId);
        
        if (account.getBalance().compareTo(amount) < 0) {
            throw new InsufficientBalanceException("余额不足");
            // 抛出异常后，Seata会自动回滚所有分支
        }
        
        account.setBalance(account.getBalance().subtract(amount));
        accountMapper.updateById(account);
    }
}
```

#### 配置文件

```yaml
# application.yml
seata:
  enabled: true
  application-id: order-service
  tx-service-group: my_tx_group
  
  config:
    type: nacos
    nacos:
      server-addr: 127.0.0.1:8848
      namespace: seata
      group: SEATA_GROUP
      
  registry:
    type: nacos
    nacos:
      application: seata-server
      server-addr: 127.0.0.1:8848
      namespace: seata
      group: SEATA_GROUP

spring:
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://localhost:3306/seata_order?useSSL=false
    username: root
    password: root
```

#### 数据库准备

```sql
-- 1. 业务表
CREATE TABLE `order` (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    product_id VARCHAR(64) NOT NULL,
    quantity INT NOT NULL,
    amount DECIMAL(20, 2) NOT NULL,
    create_time DATETIME NOT NULL
);

-- 2. Undo Log表（每个业务库都需要）
CREATE TABLE undo_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    branch_id BIGINT NOT NULL,
    xid VARCHAR(100) NOT NULL,
    context VARCHAR(128) NOT NULL,
    rollback_info LONGBLOB NOT NULL,
    log_status INT NOT NULL,
    log_created DATETIME NOT NULL,
    log_modified DATETIME NOT NULL,
    UNIQUE KEY ux_undo_log (xid, branch_id)
);
```

### 6. AT模式的优缺点

#### 优点

**优点1：性能好**
```
对比2PC：
- 本地事务立即提交，不阻塞
- 资源锁定时间短
- 吞吐量高
```

**优点2：无代码侵入**
```java
// 无需像TCC那样实现Try、Confirm、Cancel
// 只需加@GlobalTransactional注解
@GlobalTransactional
public void businessMethod() {
    // 正常的业务代码
}
```

**优点3：自动补偿**
```
不需要手写补偿逻辑
Seata自动：
1. 记录数据快照
2. 生成反向SQL
3. 执行补偿操作
```

#### 缺点

**缺点1：不保证隔离性**
```
场景：全局事务未提交前，本地事务已提交

事务A（全局事务）：
  t1: 扣减余额100（本地事务提交）
  t2: 其他操作...
  t3: 全局事务回滚

事务B（普通事务）：
  t2: 读到扣减后的余额（脏读）

解决：
- 使用@GlobalLock注解
- 或业务层面避免
```

**缺点2：依赖回滚日志**
```
- 需要额外的undo_log表
- 增加存储开销
- 回滚日志可能被误删
```

**缺点3：SQL解析限制**
```
- 不支持所有SQL语法
- 复杂SQL可能解析失败
- 批量操作性能较差
```

### 7. AT模式 vs TCC

| 维度 | AT模式 | TCC |
|------|--------|-----|
| **实现复杂度** | 低（自动化） | 高（手动实现三个方法） |
| **代码侵入** | 低（加注解） | 高（改业务代码） |
| **性能** | 好 | 好 |
| **资源锁定** | 短（依赖全局锁） | 短（业务预留） |
| **隔离性** | 弱 | 强 |
| **补偿方式** | 自动生成反向SQL | 手动编写Cancel |
| **适用场景** | 通用场景 | 需要强隔离性 |

### 8. 总结

**AT模式核心要点**：
- 是一种改进的两阶段提交
- 一阶段直接提交本地事务（释放锁）
- 通过数据快照和全局锁实现分布式事务
- 二阶段异步处理（提交或回滚）

**与传统2PC的区别**：
- 锁定时间更短（性能更好）
- 补偿方式不同（自动生成反向SQL）
- 代码无侵入（透明化）

**适用场景**：
- 大多数分布式事务场景
- 对性能有要求
- 不希望修改业务代码
- 能接受弱隔离性

**面试要点**：
- 能清晰描述AT模式的两阶段流程
- 理解数据快照和全局锁的作用
- 掌握AT模式与2PC、TCC的区别
- 了解AT模式的优缺点和适用场景

