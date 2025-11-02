---
layout: post
title: "数据库死锁如何解决"
date: 2025-11-02
description: "系统讲解数据库死锁的预防、检测、解决方案及最佳实践"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 死锁, 并发控制, 事务管理, 性能优化]
---

## 问题

数据库死锁如何解决?

## 答案

### 核心思路

数据库死锁的解决分为三个层面:**预防(Prevention)**、**检测(Detection)**、**恢复(Recovery)**。重点是从设计和编码阶段预防死锁,辅以数据库自动检测和回滚机制。

### 一、预防死锁

#### 1. 统一资源访问顺序

**原理**:打破"循环等待"条件,避免事务间形成等待环路。

```sql
-- 错误:不同事务加锁顺序不一致
-- 事务A
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;  -- 锁id=1
UPDATE account SET balance = balance + 100 WHERE id = 2;  -- 锁id=2
COMMIT;

-- 事务B(并发执行)
BEGIN;
UPDATE account SET balance = balance - 50 WHERE id = 2;   -- 锁id=2
UPDATE account SET balance = balance + 50 WHERE id = 1;   -- 等待id=1
COMMIT;
-- 死锁!A等2,B等1

-- 正确:按ID顺序加锁
-- 事务A和事务B都按 id=1 → id=2 的顺序
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = LEAST(1, 2);
UPDATE account SET balance = balance + 100 WHERE id = GREATEST(1, 2);
COMMIT;
```

**应用代码示例**:
```java
public void transfer(int fromId, int toId, BigDecimal amount) {
    // 按ID排序,确保加锁顺序一致
    int firstId = Math.min(fromId, toId);
    int secondId = Math.max(fromId, toId);

    jdbcTemplate.update(
        "UPDATE account SET balance = balance - ? WHERE id = ?",
        fromId == firstId ? amount : amount.negate(), firstId
    );
    jdbcTemplate.update(
        "UPDATE account SET balance = balance + ? WHERE id = ?",
        toId == secondId ? amount : amount.negate(), secondId
    );
}
```

#### 2. 避免锁升级

```sql
-- 错误:共享锁升级排他锁
BEGIN;
SELECT * FROM account WHERE id = 1 LOCK IN SHARE MODE;  -- S锁
-- 业务逻辑...
UPDATE account SET balance = balance - 100 WHERE id = 1;  -- 等待升级X锁
COMMIT;

-- 正确:直接加排他锁
BEGIN;
SELECT * FROM account WHERE id = 1 FOR UPDATE;  -- 直接X锁
UPDATE account SET balance = balance - 100 WHERE id = 1;
COMMIT;
```

#### 3. 缩短事务时间

```sql
-- 错误:事务包含耗时操作
BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 调用外部支付API(耗时5秒)...
-- 发送邮件通知(耗时2秒)...
UPDATE orders SET status = 'paid' WHERE id = 1;
COMMIT;

-- 正确:事务外完成耗时操作
Order order = queryOrder(1);  -- 无锁查询
callPaymentAPI(order);        -- 外部操作
sendEmail(order);             -- 外部操作

BEGIN;
SELECT * FROM orders WHERE id = 1 FOR UPDATE;
-- 二次校验状态
UPDATE orders SET status = 'paid' WHERE id = 1;
COMMIT;
```

#### 4. 降低事务隔离级别

```sql
-- RR隔离级别:使用Next-Key Lock,容易死锁
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- 改为RC隔离级别:减少Gap Lock
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 配置文件
[mysqld]
transaction-isolation = READ-COMMITTED
```

**权衡**:
- RR级别:防幻读,但死锁风险高
- RC级别:减少死锁,但允许幻读

#### 5. 使用乐观锁替代悲观锁

```java
/**
 * 悲观锁:可能死锁
 */
@Transactional
public void updateStockPessimistic(Long productId, int quantity) {
    // SELECT FOR UPDATE加锁
    Product product = productMapper.selectByIdForUpdate(productId);
    if (product.getStock() < quantity) {
        throw new BusinessException("库存不足");
    }
    product.setStock(product.getStock() - quantity);
    productMapper.updateById(product);
}

/**
 * 乐观锁:避免死锁
 */
@Transactional
public void updateStockOptimistic(Long productId, int quantity) {
    Product product = productMapper.selectById(productId);  // 无锁读取
    if (product.getStock() < quantity) {
        throw new BusinessException("库存不足");
    }

    // 使用版本号更新
    int affected = productMapper.updateStockWithVersion(
        productId, quantity, product.getVersion()
    );

    if (affected == 0) {
        throw new OptimisticLockException("并发冲突,请重试");
    }
}
```

```sql
-- 乐观锁SQL
UPDATE products
SET stock = stock - #{quantity}, version = version + 1
WHERE id = #{id} AND version = #{version} AND stock >= #{quantity}
```

#### 6. 合理使用索引

```sql
-- 错误:无索引导致锁表
UPDATE orders SET status = 'cancelled' WHERE user_id = 100;  -- user_id无索引

-- 正确:添加索引减少锁范围
ALTER TABLE orders ADD INDEX idx_user_id (user_id);
UPDATE orders SET status = 'cancelled' WHERE user_id = 100;  -- 只锁相关行
```

### 二、检测死锁

#### 1. InnoDB自动死锁检测

```sql
-- 查看死锁检测配置
SHOW VARIABLES LIKE 'innodb_deadlock_detect';
-- ON:自动检测并回滚(默认)

-- 查看死锁信息
SHOW ENGINE INNODB STATUS\G

-- 输出关键部分
/*
------------------------
LATEST DETECTED DEADLOCK
------------------------
*** (1) TRANSACTION:
TRANSACTION 12345, ACTIVE 10 sec starting index read
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 10, query id 500 localhost root updating
UPDATE account SET balance = balance - 100 WHERE id = 1

*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 2 page no 3 n bits 72 index PRIMARY

*** (2) TRANSACTION:
TRANSACTION 12346, ACTIVE 8 sec starting index read
2 lock struct(s), heap size 1136, 1 row lock(s)
UPDATE account SET balance = balance + 100 WHERE id = 2

*** WE ROLL BACK TRANSACTION (1)
*/
```

#### 2. 监控锁等待

```sql
-- 查看当前锁等待
SELECT
    r.trx_id AS waiting_trx_id,
    r.trx_mysql_thread_id AS waiting_thread,
    r.trx_query AS waiting_query,
    b.trx_id AS blocking_trx_id,
    b.trx_mysql_thread_id AS blocking_thread,
    b.trx_query AS blocking_query
FROM information_schema.innodb_lock_waits w
INNER JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
INNER JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id;

-- MySQL 8.0+新方法
SELECT
    waiting_pid,
    waiting_query,
    blocking_pid,
    blocking_query
FROM sys.innodb_lock_waits;
```

#### 3. 配置死锁日志

```sql
-- 开启错误日志记录死锁
[mysqld]
log_error = /var/log/mysql/error.log
innodb_print_all_deadlocks = ON  -- 记录所有死锁到日志
```

### 三、恢复死锁

#### 1. 应用层重试机制

```java
@Service
public class AccountService {

    private static final int MAX_RETRIES = 3;

    @Transactional(rollbackFor = Exception.class)
    public void transfer(Long fromId, Long toId, BigDecimal amount) {
        int retries = 0;
        while (retries < MAX_RETRIES) {
            try {
                doTransfer(fromId, toId, amount);
                return;  // 成功则返回
            } catch (DeadlockLoserDataAccessException e) {
                retries++;
                if (retries >= MAX_RETRIES) {
                    throw new BusinessException("转账失败,请稍后重试");
                }
                // 随机延迟后重试(避免重试时再次冲突)
                sleep(100 + new Random().nextInt(200));
            }
        }
    }
}
```

#### 2. 设置锁等待超时

```sql
-- 设置锁等待超时时间(默认50秒)
SET innodb_lock_wait_timeout = 10;  -- 10秒超时

-- 会话级设置
SET SESSION innodb_lock_wait_timeout = 5;
```

#### 3. 手动处理阻塞

```sql
-- 查找阻塞的线程
SELECT * FROM information_schema.processlist WHERE state = 'Locked';

-- 杀掉阻塞的线程
KILL <thread_id>;
```

### 四、实际案例与最佳实践

#### 案例1:订单系统死锁优化

```java
// 优化前:死锁频发
@Transactional
public void createOrder(OrderDTO dto) {
    // 1. 锁定商品库存
    productMapper.updateStock(dto.getProductId(), dto.getQuantity());
    // 2. 锁定用户余额
    userMapper.updateBalance(dto.getUserId(), dto.getAmount());
    // 3. 创建订单
    orderMapper.insert(order);
}

// 优化后:统一加锁顺序 + 乐观锁
@Transactional
public void createOrderOptimized(OrderDTO dto) {
    // 1. 按ID排序资源
    List<LockResource> resources = Arrays.asList(
        new LockResource("product", dto.getProductId()),
        new LockResource("user", dto.getUserId())
    );
    Collections.sort(resources);

    // 2. 使用乐观锁更新库存
    int affected = productMapper.updateStockWithVersion(
        dto.getProductId(), dto.getQuantity(), product.getVersion()
    );
    if (affected == 0) {
        throw new OptimisticLockException("库存已变更");
    }

    // 3. 更新余额
    userMapper.updateBalance(dto.getUserId(), dto.getAmount());

    // 4. 创建订单
    orderMapper.insert(order);
}
```

#### 案例2:分布式锁避免死锁

```java
@Service
public class DistributedLockService {

    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    public void processWithLock(String resourceId, Runnable task) {
        String lockKey = "lock:" + resourceId;
        String lockValue = UUID.randomUUID().toString();

        try {
            // 获取分布式锁(设置过期时间避免死锁)
            Boolean success = redisTemplate.opsForValue()
                .setIfAbsent(lockKey, lockValue, 10, TimeUnit.SECONDS);

            if (Boolean.TRUE.equals(success)) {
                task.run();  // 执行业务
            } else {
                throw new BusinessException("资源被锁定");
            }
        } finally {
            // 释放锁(Lua脚本保证原子性)
            releaseLock(lockKey, lockValue);
        }
    }
}
```

### 五、配置优化

```ini
[mysqld]
# 死锁检测(默认ON)
innodb_deadlock_detect = ON

# 锁等待超时(秒)
innodb_lock_wait_timeout = 50

# 记录所有死锁到错误日志
innodb_print_all_deadlocks = ON

# 隔离级别(RC减少死锁)
transaction-isolation = READ-COMMITTED

# 并发线程数(减少并发降低死锁概率)
innodb_thread_concurrency = 0  # 0表示不限制
```

### 答题总结

数据库死锁的解决策略:

**1. 预防为主**(设计阶段):
- 统一加锁顺序(破坏循环等待)
- 避免锁升级(直接加排他锁)
- 缩短事务时间(减少持锁时长)
- 使用乐观锁(避免阻塞)

**2. 自动检测**(数据库):
- InnoDB自动检测死锁并回滚代价最小的事务
- 配置`innodb_deadlock_detect=ON`

**3. 异常处理**(应用层):
- 捕获死锁异常重试
- 设置合理的超时时间
- 记录死锁日志分析优化

**面试要点**:
- 死锁的四个必要条件:互斥、持有并等待、不可剥夺、循环等待
- 预防死锁的关键是打破循环等待条件
- 生产环境优先使用乐观锁和统一加锁顺序
- InnoDB会自动选择代价最小的事务回滚

实际开发中,应该从业务设计、数据库配置、应用代码三个层面综合考虑,建立完整的死锁预防和处理机制。
