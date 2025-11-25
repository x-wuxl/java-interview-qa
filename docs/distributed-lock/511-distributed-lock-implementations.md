---
layout: default
title: "分布式锁的实现方式有哪些？"
parent: 分布式锁
nav_order: 511
description: "全面对比分布式锁的主流实现方案：Redis、Zookeeper、数据库的原理、优缺点及适用场景"
date: 2025-11-02
---
## 核心概念

分布式锁的实现方式主要有三种：**基于数据库**、**基于 Redis**、**基于 Zookeeper**。每种方案都有各自的特点和适用场景，需要根据业务需求权衡选择。

## 一、基于数据库的分布式锁

### 实现原理

利用数据库的**唯一索引**或**排他锁**来实现互斥。

#### 方案1：唯一索引
```sql
CREATE TABLE distributed_lock (
    lock_key VARCHAR(64) NOT NULL COMMENT '锁的唯一标识',
    holder VARCHAR(64) NOT NULL COMMENT '持锁者标识',
    expire_time BIGINT NOT NULL COMMENT '过期时间戳',
    PRIMARY KEY (lock_key)
) ENGINE=InnoDB;

-- 加锁：插入记录
INSERT INTO distributed_lock (lock_key, holder, expire_time) 
VALUES ('order:123', 'server-1', 1698888888000);

-- 解锁：删除记录
DELETE FROM distributed_lock 
WHERE lock_key = 'order:123' AND holder = 'server-1';
```

#### 方案2：悲观锁（SELECT FOR UPDATE）
```sql
-- 加锁
BEGIN;
SELECT * FROM resource WHERE id = 123 FOR UPDATE;
-- 执行业务逻辑
-- ...
COMMIT; -- 释放锁
```

### 优缺点

**优点：**
- 实现简单，无需引入额外组件
- 强一致性，利用数据库事务保证

**缺点：**
- 性能较差，每次加锁都涉及数据库 IO
- 锁无法自动过期，需要额外的清理机制
- 对数据库压力大，容易成为瓶颈
- 非阻塞场景需要轮询，效率低

**适用场景：** 对性能要求不高、已有数据库依赖的小型系统。

## 二、基于 Redis 的分布式锁

### 实现原理

利用 Redis 的 **SET NX**（SET if Not eXists）命令和 **原子性操作** 实现。

#### 基础实现
```java
public class RedisDistributedLock {
    @Autowired
    private StringRedisTemplate redisTemplate;
    
    /**
     * 加锁
     * @param key 锁的key
     * @param value 锁的值（通常是UUID，用于校验持锁者）
     * @param expireTime 过期时间（秒）
     */
    public boolean tryLock(String key, String value, long expireTime) {
        // SET key value NX EX expireTime
        Boolean result = redisTemplate.opsForValue()
            .setIfAbsent(key, value, expireTime, TimeUnit.SECONDS);
        return Boolean.TRUE.equals(result);
    }
    
    /**
     * 解锁（Lua脚本保证原子性）
     */
    public boolean unlock(String key, String value) {
        String script = 
            "if redis.call('get', KEYS[1]) == ARGV[1] then " +
            "    return redis.call('del', KEYS[1]) " +
            "else " +
            "    return 0 " +
            "end";
        
        Long result = redisTemplate.execute(
            new DefaultRedisScript<>(script, Long.class),
            Collections.singletonList(key),
            value
        );
        return result != null && result == 1L;
    }
}
```

### Redisson 增强实现

Redisson 提供了完善的分布式锁解决方案，支持**可重入**、**自动续期**、**公平锁**等特性。

```java
@Autowired
private RedissonClient redissonClient;

public void businessLogic() {
    RLock lock = redissonClient.getLock("myLock");
    try {
        // 尝试加锁，最多等待10秒，锁定后30秒自动解锁
        boolean locked = lock.tryLock(10, 30, TimeUnit.SECONDS);
        if (locked) {
            // 执行业务逻辑
            doSomething();
        }
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
    } finally {
        if (lock.isHeldByCurrentThread()) {
            lock.unlock();
        }
    }
}
```

**Redisson 的核心特性：**
- **看门狗机制（WatchDog）**：自动续期，默认每 10 秒检查一次，续期到 30 秒
- **可重入**：基于 Redis Hash 结构记录重入次数
- **RedLock 算法**：针对 Redis 集群的更可靠实现

### 优缺点

**优点：**
- 性能高，基于内存操作
- 支持自动过期，避免死锁
- 原生支持发布订阅，可以实现阻塞等待
- 成熟框架（如 Redisson）功能完善

**缺点：**
- Redis 主从架构存在锁丢失风险（主节点宕机时，从节点可能未同步锁数据）
- RedLock 算法复杂度高，需要部署多个独立 Redis 实例

**适用场景：** 高并发、对性能要求高、允许短暂的不一致性的场景（如秒杀、抢购）。

## 三、基于 Zookeeper 的分布式锁

### 实现原理

利用 Zookeeper 的**临时顺序节点**和**监听机制**实现。

#### 加锁流程
1. 客户端在指定路径下创建**临时顺序节点**（如 `/locks/lock_0000000001`）
2. 获取 `/locks` 下的所有子节点，判断自己创建的节点是否是序号最小的
3. 如果是最小的，则获取锁成功
4. 如果不是，则监听比自己序号小的前一个节点，等待其释放

#### 解锁流程
- 删除自己创建的临时节点，触发后续节点的监听回调

```java
public class ZookeeperDistributedLock {
    private CuratorFramework client;
    
    public void lock() throws Exception {
        InterProcessMutex lock = new InterProcessMutex(client, "/locks/mylock");
        try {
            // 尝试加锁，最多等待10秒
            if (lock.acquire(10, TimeUnit.SECONDS)) {
                try {
                    // 执行业务逻辑
                    doSomething();
                } finally {
                    lock.release(); // 释放锁
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("Lock failed", e);
        }
    }
}
```

### 核心特性

1. **临时节点**：客户端断开连接后，节点自动删除，避免死锁
2. **顺序节点**：按创建顺序排列，天然实现公平锁
3. **监听机制**：避免惊群效应（每个节点只监听前一个节点）

### 优缺点

**优点：**
- **高可靠性**：基于 Paxos/ZAB 协议，强一致性保证
- **自动释放**：临时节点机制，客户端挂掉自动释放锁
- **天然公平**：顺序节点保证先到先得
- **阻塞等待**：基于监听机制，无需轮询

**缺点：**
- 性能相对较低（比 Redis 差）
- 需要维护 Zookeeper 集群
- 复杂度较高，学习成本大

**适用场景：** 对可靠性要求极高、需要公平锁、允许性能损耗的场景（如配置中心选主、分布式任务调度）。

## 三种方案对比

| 特性 | 数据库锁 | Redis 锁 | Zookeeper 锁 |
|------|---------|----------|--------------|
| **性能** | 低 | 高 | 中 |
| **可靠性** | 高 | 中（主从切换有风险） | 极高（强一致性） |
| **实现复杂度** | 低 | 中 | 高 |
| **自动过期** | 需手动实现 | 支持 | 自动（临时节点） |
| **阻塞等待** | 需轮询 | 可基于pub/sub | 原生支持（监听） |
| **公平性** | 不保证 | 不保证 | 保证（顺序节点） |
| **运维成本** | 低 | 低 | 高 |
| **适用场景** | 小型系统 | 高并发场景 | 高可靠性场景 |

## 答题总结

分布式锁主要有三种实现方式：

1. **数据库锁**：利用唯一索引或悲观锁，简单但性能差，适合小型系统
2. **Redis 锁**：基于 SET NX 命令，性能高但主从架构有丢失风险，适合高并发场景（推荐 Redisson）
3. **Zookeeper 锁**：基于临时顺序节点，可靠性最高且天然公平，但性能和复杂度较高，适合选主等强一致场景

**实际选择建议：**
- 性能优先 → Redis（Redisson）
- 可靠性优先 → Zookeeper
- 简单场景 → 数据库

大部分互联网公司在高并发场景下会优先选择 **Redis + Redisson**，因为它在性能和功能完善度之间取得了较好的平衡。

