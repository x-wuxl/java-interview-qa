---
layout: post
title: "乐观锁与悲观锁如何实现"
date: 2025-11-02
description: "详解数据库中乐观锁和悲观锁的实现机制、适用场景及代码示例"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 乐观锁, 悲观锁, 并发控制, CAS]
---

## 问题

乐观锁与悲观锁如何实现?

## 答案

### 核心概念

**悲观锁(Pessimistic Lock)**:假设并发冲突一定会发生,在读取数据时就加锁,其他事务必须等待锁释放。
**乐观锁(Optimistic Lock)**:假设并发冲突很少发生,读取数据时不加锁,在更新时检查数据是否被修改过,如果被修改则更新失败。

### 一、悲观锁实现

悲观锁依赖数据库的锁机制实现。

#### 1. 共享锁(S锁)

```sql
-- 读取时加共享锁,阻止其他事务修改
BEGIN;
SELECT * FROM products WHERE id = 1 LOCK IN SHARE MODE;
-- 或使用MySQL 8.0新语法
SELECT * FROM products WHERE id = 1 FOR SHARE;

-- 此时其他事务可以读,但不能写
COMMIT;
```

#### 2. 排他锁(X锁)

```sql
-- 读取时加排他锁,阻止其他事务读写
BEGIN;
SELECT * FROM products WHERE id = 1 FOR UPDATE;
-- 执行业务逻辑
UPDATE products SET stock = stock - 1 WHERE id = 1;
COMMIT;
```

#### 3. Java实现示例

```java
@Service
public class OrderService {

    @Autowired
    private ProductMapper productMapper;

    /**
     * 悲观锁:减库存
     */
    @Transactional(rollbackFor = Exception.class)
    public void reduceStockPessimistic(Long productId, Integer quantity) {
        // 1. 加排他锁查询(阻塞其他事务)
        Product product = productMapper.selectByIdForUpdate(productId);

        // 2. 校验库存
        if (product.getStock() < quantity) {
            throw new BusinessException("库存不足");
        }

        // 3. 扣减库存
        product.setStock(product.getStock() - quantity);
        productMapper.updateById(product);

        // 4. 提交事务时释放锁
    }
}
```

```xml
<!-- MyBatis Mapper -->
<select id="selectByIdForUpdate" resultType="Product">
    SELECT * FROM products WHERE id = #{id} FOR UPDATE
</select>
```

#### 4. 悲观锁的特点

**优点**:
- 数据一致性强,适合高并发冲突场景
- 简单直接,由数据库保证安全性

**缺点**:
- 性能开销大,持有锁期间阻塞其他事务
- 可能导致死锁
- 高并发下吞吐量低

### 二、乐观锁实现

乐观锁通过版本号或时间戳机制实现,不依赖数据库锁。

#### 1. 版本号机制(最常用)

```sql
-- 表结构:添加version字段
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    stock INT,
    version INT DEFAULT 0,  -- 版本号
    INDEX idx_version (version)
);

-- 乐观锁更新
-- 步骤1:查询数据(不加锁)
SELECT id, stock, version FROM products WHERE id = 1;
-- 结果: stock=100, version=5

-- 步骤2:更新时校验版本号
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;  -- 版本号必须匹配

-- 如果affected_rows=0,说明数据已被修改,更新失败
```

#### 2. Java实现示例

```java
@Service
public class OrderService {

    @Autowired
    private ProductMapper productMapper;

    /**
     * 乐观锁:减库存
     */
    @Transactional(rollbackFor = Exception.class)
    public void reduceStockOptimistic(Long productId, Integer quantity) {
        int maxRetries = 3;  // 最大重试次数
        int retries = 0;

        while (retries < maxRetries) {
            // 1. 查询数据(不加锁)
            Product product = productMapper.selectById(productId);

            // 2. 校验库存
            if (product.getStock() < quantity) {
                throw new BusinessException("库存不足");
            }

            // 3. 使用版本号更新
            int affectedRows = productMapper.updateStockWithVersion(
                productId,
                quantity,
                product.getVersion()
            );

            // 4. 判断是否更新成功
            if (affectedRows > 0) {
                return;  // 成功则返回
            }

            // 5. 失败则重试
            retries++;
            if (retries >= maxRetries) {
                throw new OptimisticLockException("并发冲突,请稍后重试");
            }
        }
    }
}
```

```xml
<!-- MyBatis Mapper -->
<update id="updateStockWithVersion">
    UPDATE products
    SET stock = stock - #{quantity},
        version = version + 1
    WHERE id = #{id}
      AND version = #{version}
      AND stock >= #{quantity}
</update>
```

#### 3. 时间戳机制

```sql
-- 表结构:使用update_time字段
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    stock INT,
    update_time DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
);

-- 乐观锁更新
-- 步骤1:查询数据
SELECT id, stock, update_time FROM products WHERE id = 1;
-- 结果: stock=100, update_time='2025-11-02 10:30:00.123456'

-- 步骤2:更新时校验时间戳
UPDATE products
SET stock = stock - 1, update_time = NOW(6)
WHERE id = 1 AND update_time = '2025-11-02 10:30:00.123456';
```

**注意**:时间戳方案精度要求高(微秒级),且不同服务器时间可能不一致,生产环境推荐版本号方案。

#### 4. CAS(Compare And Swap)机制

适用于简单的数值更新场景。

```sql
-- 直接基于旧值更新
-- 步骤1:查询当前库存
SELECT stock FROM products WHERE id = 1;  -- stock = 100

-- 步骤2:基于旧值更新
UPDATE products
SET stock = 99  -- 新值
WHERE id = 1 AND stock = 100;  -- 旧值必须匹配

-- 如果stock已变化,affected_rows=0
```

```java
/**
 * CAS实现
 */
@Transactional(rollbackFor = Exception.class)
public void reduceStockCAS(Long productId, Integer quantity) {
    int maxRetries = 3;
    for (int i = 0; i < maxRetries; i++) {
        // 1. 读取当前库存
        Integer currentStock = productMapper.getStock(productId);

        // 2. 计算新库存
        int newStock = currentStock - quantity;
        if (newStock < 0) {
            throw new BusinessException("库存不足");
        }

        // 3. CAS更新
        int affected = productMapper.casUpdateStock(
            productId, currentStock, newStock
        );

        if (affected > 0) {
            return;  // 成功
        }
        // 失败则重试
    }
    throw new OptimisticLockException("更新失败");
}
```

```xml
<update id="casUpdateStock">
    UPDATE products
    SET stock = #{newStock}
    WHERE id = #{id} AND stock = #{oldStock}
</update>
```

#### 5. 乐观锁的特点

**优点**:
- 无锁设计,不阻塞其他事务,并发性能高
- 不会死锁
- 适合读多写少的场景

**缺点**:
- 更新失败需要重试,增加代码复杂度
- 高并发冲突时,大量重试降低性能
- ABA问题(版本号可以解决)

### 三、性能对比与选择

| 维度         | 悲观锁                | 乐观锁                |
|--------------|----------------------|----------------------|
| 实现方式     | 数据库锁(FOR UPDATE) | 版本号/时间戳/CAS    |
| 并发性能     | 低(阻塞等待)         | 高(无锁并发)         |
| 冲突处理     | 自动排队             | 手动重试             |
| 适用场景     | 写多读少,冲突频繁    | 读多写少,冲突较少    |
| 死锁风险     | 有                   | 无                   |
| 实现复杂度   | 简单                 | 中等(需要重试逻辑)   |

### 四、实际应用场景

#### 场景1:秒杀系统

```java
/**
 * 秒杀场景:使用乐观锁+Redis预减库存
 */
@Service
public class SeckillService {

    @Autowired
    private RedisTemplate<String, Integer> redisTemplate;

    @Autowired
    private ProductMapper productMapper;

    public void seckill(Long productId, Long userId) {
        // 1. Redis预减库存(原子操作)
        String stockKey = "seckill:stock:" + productId;
        Long remaining = redisTemplate.opsForValue().decrement(stockKey);

        if (remaining < 0) {
            // 库存不足,Redis回滚
            redisTemplate.opsForValue().increment(stockKey);
            throw new BusinessException("商品已售罄");
        }

        // 2. 异步处理订单(消息队列)
        rabbitTemplate.convertAndSend("seckill.queue", new SeckillMessage(productId, userId));

        // 3. 异步扣减数据库库存(乐观锁)
        // 在消息消费者中执行:productMapper.updateStockWithVersion(...)
    }
}
```

#### 场景2:账户余额扣减

```java
/**
 * 账户扣款:使用悲观锁保证强一致性
 */
@Transactional(rollbackFor = Exception.class)
public void deduct(Long accountId, BigDecimal amount) {
    // 金融场景必须保证强一致性,使用悲观锁
    Account account = accountMapper.selectByIdForUpdate(accountId);

    if (account.getBalance().compareTo(amount) < 0) {
        throw new BusinessException("余额不足");
    }

    account.setBalance(account.getBalance().subtract(amount));
    accountMapper.updateById(account);
}
```

#### 场景3:库存系统

```java
/**
 * 电商库存:混合使用乐观锁+分段锁
 */
@Service
public class InventoryService {

    /**
     * 正常下单:乐观锁
     */
    @Transactional(rollbackFor = Exception.class)
    public void reduceStock(Long productId, Integer quantity) {
        int affected = productMapper.updateStockWithVersion(productId, quantity, version);
        if (affected == 0) {
            throw new OptimisticLockException("库存已变更");
        }
    }

    /**
     * 库存盘点:悲观锁
     */
    @Transactional(rollbackFor = Exception.class)
    public void inventory(Long productId, Integer actualStock) {
        // 盘点时需要阻止其他操作,使用悲观锁
        Product product = productMapper.selectByIdForUpdate(productId);
        product.setStock(actualStock);
        productMapper.updateById(product);
    }
}
```

### 五、MyBatis-Plus集成

```java
/**
 * 实体类:添加@Version注解
 */
@Data
@TableName("products")
public class Product {
    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    private Integer stock;

    @Version  // MyBatis-Plus自动处理乐观锁
    private Integer version;
}

/**
 * 配置乐观锁插件
 */
@Configuration
public class MybatisPlusConfig {

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        // 添加乐观锁插件
        interceptor.addInnerInterceptor(new OptimisticLockerInnerInterceptor());
        return interceptor;
    }
}

/**
 * 使用(自动处理版本号)
 */
@Service
public class ProductService extends ServiceImpl<ProductMapper, Product> {

    public void reduceStock(Long productId, Integer quantity) {
        Product product = getById(productId);
        product.setStock(product.getStock() - quantity);
        // MyBatis-Plus自动拼接: WHERE version = #{version}
        boolean success = updateById(product);
        if (!success) {
            throw new OptimisticLockException("更新失败");
        }
    }
}
```

### 答题总结

**悲观锁实现**:
- 使用`SELECT FOR UPDATE`加排他锁
- 适合冲突频繁的场景
- 简单但性能较低

**乐观锁实现**:
- 版本号机制(推荐):`UPDATE ... WHERE version = ?`
- 时间戳机制:`UPDATE ... WHERE update_time = ?`
- CAS机制:`UPDATE ... WHERE old_value = ?`
- 适合冲突较少的场景,需要实现重试逻辑

**选择原则**:
- 读多写少 → 乐观锁
- 写多读少 → 悲观锁
- 金融场景 → 悲观锁(强一致性)
- 秒杀场景 → 乐观锁+缓存

**面试要点**:能够说清楚版本号的实现机制,理解乐观锁和悲观锁的适用场景,以及如何处理乐观锁的重试逻辑。
