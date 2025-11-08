---
layout: post
title: "Redis 7 事务机制深度解析"
date: 2025-11-08
description: "详解Redis 7的事务机制，包括MULTI/EXEC、WATCH乐观锁、Lua脚本原子性及与传统数据库事务的区别"
author: "wuxl"
categories: [中间件]
tags: [Redis, 事务, 原子性, Lua脚本]
---

## 问题

Redis 7 的事务机制是如何工作的？它与传统数据库事务有什么区别？

## 答案

### 1. 核心概念

Redis事务是一组命令的**顺序执行集合**，提供了一定程度的原子性保障。但与传统关系型数据库的ACID事务不同，Redis事务更轻量，不支持回滚。

**Redis事务特点**：
- **原子性**：所有命令要么全部执行，要么全部不执行（仅限执行阶段）
- **隔离性**：事务执行期间不会被其他客户端命令打断
- **无持久性保证**：取决于持久化配置
- **无回滚机制**：命令执行失败不会回滚已执行的命令

### 2. 事务基本用法

#### 2.1 MULTI/EXEC命令

```bash
# 基本事务示例
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET account:1 100
QUEUED
127.0.0.1:6379> SET account:2 200
QUEUED
127.0.0.1:6379> INCRBY account:1 50
QUEUED
127.0.0.1:6379> DECRBY account:2 50
QUEUED
127.0.0.1:6379> EXEC
1) OK
2) OK
3) (integer) 150
4) (integer) 150
```

#### 2.2 事务执行流程

```
客户端                    Redis服务器
  |                          |
  |-- MULTI --------------> [开启事务]
  |                          |
  |-- SET key1 val1 -------> [命令入队]
  |<-- QUEUED               |
  |                          |
  |-- INCR key2 -----------> [命令入队]
  |<-- QUEUED               |
  |                          |
  |-- EXEC ---------------> [顺序执行所有命令]
  |<-- 返回结果数组          |
```

#### 2.3 DISCARD取消事务

```bash
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET key1 value1
QUEUED
127.0.0.1:6379> SET key2 value2
QUEUED
127.0.0.1:6379> DISCARD
OK
# 事务被取消，所有命令都不会执行
```

### 3. WATCH乐观锁

#### 3.1 基本原理

WATCH命令实现了**乐观锁**机制，用于解决并发修改问题：

```bash
# 客户端1：使用WATCH监控key
127.0.0.1:6379> WATCH balance
OK
127.0.0.1:6379> GET balance
"100"

# 客户端2：修改了balance
127.0.0.1:6379> SET balance 200
OK

# 客户端1：执行事务失败
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET balance 150
QUEUED
127.0.0.1:6379> EXEC
(nil)  # 返回nil表示事务执行失败
```

#### 3.2 CAS操作实现

```bash
# 实现账户余额扣减（带重试）
WATCH balance
balance = GET balance
if balance >= 50:
    MULTI
    DECRBY balance 50
    result = EXEC
    if result is None:
        # 重试
        goto WATCH
```

#### 3.3 UNWATCH取消监控

```bash
127.0.0.1:6379> WATCH key1 key2
OK
127.0.0.1:6379> UNWATCH
OK
# 取消对所有key的监控
```

### 4. 事务错误处理

#### 4.1 命令语法错误（入队阶段）

```bash
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET key1 value1
QUEUED
127.0.0.1:6379> INVALID_COMMAND
(error) ERR unknown command 'INVALID_COMMAND'
127.0.0.1:6379> SET key2 value2
QUEUED
127.0.0.1:6379> EXEC
(error) EXECABORT Transaction discarded because of previous errors.

# 结果：整个事务被放弃，所有命令都不执行
```

#### 4.2 运行时错误（执行阶段）

```bash
127.0.0.1:6379> SET key1 "string_value"
OK
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET key2 "value2"
QUEUED
127.0.0.1:6379> INCR key1  # key1是字符串，无法INCR
QUEUED
127.0.0.1:6379> SET key3 "value3"
QUEUED
127.0.0.1:6379> EXEC
1) OK
2) (error) ERR value is not an integer or out of range
3) OK

# 结果：错误命令返回错误，其他命令正常执行（无回滚）
```

### 5. 事务原子性分析

#### 5.1 Redis事务的原子性保障

```c
// Redis源码：事务执行逻辑（简化版）
void execCommand(client *c) {
    // 检查WATCH的key是否被修改
    if (isWatchedKeyModified(c)) {
        addReply(c, shared.nullarray);
        return;
    }

    // 顺序执行队列中的所有命令
    for (j = 0; j < c->mstate.count; j++) {
        struct redisCommand *cmd = c->mstate.commands[j].cmd;
        robj **argv = c->mstate.commands[j].argv;

        // 执行命令（不会被其他客户端打断）
        call(c, CMD_CALL_FULL);
    }
}
```

#### 5.2 原子性的局限性

| 场景 | 是否原子 | 说明 |
|------|---------|------|
| 入队阶段语法错误 | ✅ 是 | 整个事务不执行 |
| 执行阶段运行错误 | ❌ 否 | 错误命令失败，其他命令继续 |
| 服务器宕机 | ❌ 否 | 已执行命令不回滚 |
| WATCH冲突 | ✅ 是 | 整个事务不执行 |

### 6. Lua脚本：更强的原子性

#### 6.1 Lua脚本优势

Lua脚本在Redis中**原子执行**，且支持复杂逻辑：

```lua
-- 原子性扣减库存脚本
local key = KEYS[1]
local quantity = tonumber(ARGV[1])

local stock = tonumber(redis.call('GET', key) or 0)
if stock >= quantity then
    redis.call('DECRBY', key, quantity)
    return 1  -- 成功
else
    return 0  -- 库存不足
end
```

#### 6.2 Java调用Lua脚本

```java
@Service
public class RedisLuaService {

    @Autowired
    private StringRedisTemplate redisTemplate;

    /**
     * 原子性扣减库存
     */
    public boolean deductStock(String productId, int quantity) {
        String script =
            "local stock = tonumber(redis.call('GET', KEYS[1]) or 0) " +
            "if stock >= tonumber(ARGV[1]) then " +
            "    redis.call('DECRBY', KEYS[1], ARGV[1]) " +
            "    return 1 " +
            "else " +
            "    return 0 " +
            "end";

        DefaultRedisScript<Long> redisScript = new DefaultRedisScript<>();
        redisScript.setScriptText(script);
        redisScript.setResultType(Long.class);

        Long result = redisTemplate.execute(
            redisScript,
            Collections.singletonList("stock:" + productId),
            String.valueOf(quantity)
        );

        return result != null && result == 1;
    }

    /**
     * 分布式限流（令牌桶算法）
     */
    public boolean tryAcquire(String key, int maxTokens, int refillRate) {
        String script =
            "local tokens_key = KEYS[1] " +
            "local timestamp_key = KEYS[2] " +
            "local max_tokens = tonumber(ARGV[1]) " +
            "local refill_rate = tonumber(ARGV[2]) " +
            "local now = tonumber(ARGV[3]) " +
            "" +
            "local tokens = tonumber(redis.call('GET', tokens_key) or max_tokens) " +
            "local last_refill = tonumber(redis.call('GET', timestamp_key) or now) " +
            "" +
            "-- 计算应补充的令牌数 " +
            "local elapsed = now - last_refill " +
            "local refill_tokens = math.floor(elapsed * refill_rate) " +
            "tokens = math.min(tokens + refill_tokens, max_tokens) " +
            "" +
            "-- 尝试获取令牌 " +
            "if tokens >= 1 then " +
            "    tokens = tokens - 1 " +
            "    redis.call('SET', tokens_key, tokens) " +
            "    redis.call('SET', timestamp_key, now) " +
            "    return 1 " +
            "else " +
            "    return 0 " +
            "end";

        DefaultRedisScript<Long> redisScript = new DefaultRedisScript<>();
        redisScript.setScriptText(script);
        redisScript.setResultType(Long.class);

        Long result = redisTemplate.execute(
            redisScript,
            Arrays.asList("rate_limit:" + key + ":tokens", "rate_limit:" + key + ":timestamp"),
            String.valueOf(maxTokens),
            String.valueOf(refillRate),
            String.valueOf(System.currentTimeMillis() / 1000)
        );

        return result != null && result == 1;
    }
}
```

#### 6.3 Lua脚本最佳实践

```java
@Configuration
public class RedisScriptConfig {

    /**
     * 预加载Lua脚本（避免每次传输脚本内容）
     */
    @Bean
    public RedisScript<Long> deductStockScript() {
        String script =
            "local stock = tonumber(redis.call('GET', KEYS[1]) or 0) " +
            "if stock >= tonumber(ARGV[1]) then " +
            "    redis.call('DECRBY', KEYS[1], ARGV[1]) " +
            "    return 1 " +
            "else " +
            "    return 0 " +
            "end";

        DefaultRedisScript<Long> redisScript = new DefaultRedisScript<>();
        redisScript.setScriptText(script);
        redisScript.setResultType(Long.class);
        return redisScript;
    }

    /**
     * 使用预加载的脚本
     */
    @Service
    public class StockService {
        @Autowired
        private StringRedisTemplate redisTemplate;

        @Autowired
        private RedisScript<Long> deductStockScript;

        public boolean deductStock(String productId, int quantity) {
            Long result = redisTemplate.execute(
                deductStockScript,
                Collections.singletonList("stock:" + productId),
                String.valueOf(quantity)
            );
            return result != null && result == 1;
        }
    }
}
```

### 7. Pipeline与事务

#### 7.1 Pipeline + MULTI/EXEC

```java
/**
 * Pipeline批量执行事务
 */
public void batchTransactions() {
    redisTemplate.executePipelined(new SessionCallback<Object>() {
        @Override
        public Object execute(RedisOperations operations) throws DataAccessException {
            // 事务1
            operations.multi();
            operations.opsForValue().set("key1", "value1");
            operations.opsForValue().increment("counter1");
            operations.exec();

            // 事务2
            operations.multi();
            operations.opsForValue().set("key2", "value2");
            operations.opsForValue().increment("counter2");
            operations.exec();

            return null;
        }
    });
}
```

### 8. 与传统数据库事务对比

| 特性 | Redis事务 | MySQL事务 |
|------|----------|----------|
| **原子性** | 部分支持（无回滚） | 完全支持（可回滚） |
| **一致性** | 不保证 | 保证 |
| **隔离性** | 串行执行 | 多种隔离级别 |
| **持久性** | 取决于配置 | 保证（WAL日志） |
| **回滚** | ❌ 不支持 | ✅ 支持 |
| **嵌套事务** | ❌ 不支持 | ✅ 支持（Savepoint） |
| **性能** | 极高 | 相对较低 |
| **适用场景** | 简单原子操作 | 复杂业务逻辑 |

### 9. 实战案例

#### 9.1 秒杀场景（WATCH + 事务）

```java
@Service
public class SeckillService {

    @Autowired
    private StringRedisTemplate redisTemplate;

    /**
     * 秒杀抢购（使用WATCH实现乐观锁）
     */
    public boolean seckill(String productId, String userId) {
        String stockKey = "seckill:stock:" + productId;
        String orderKey = "seckill:order:" + productId;

        // 最多重试3次
        for (int i = 0; i < 3; i++) {
            // 监控库存key
            redisTemplate.watch(stockKey);

            // 检查库存
            String stockStr = redisTemplate.opsForValue().get(stockKey);
            int stock = stockStr != null ? Integer.parseInt(stockStr) : 0;

            if (stock <= 0) {
                redisTemplate.unwatch();
                return false;  // 库存不足
            }

            // 开启事务
            redisTemplate.multi();
            redisTemplate.opsForValue().decrement(stockKey);
            redisTemplate.opsForSet().add(orderKey, userId);

            // 执行事务
            List<Object> results = redisTemplate.exec();

            if (results != null && !results.isEmpty()) {
                return true;  // 秒杀成功
            }

            // 事务失败，重试
        }

        return false;  // 重试3次后仍失败
    }
}
```

#### 9.2 转账场景（Lua脚本）

```java
@Service
public class TransferService {

    @Autowired
    private StringRedisTemplate redisTemplate;

    /**
     * 原子性转账（使用Lua脚本）
     */
    public boolean transfer(String fromAccount, String toAccount, int amount) {
        String script =
            "local from_balance = tonumber(redis.call('GET', KEYS[1]) or 0) " +
            "if from_balance >= tonumber(ARGV[1]) then " +
            "    redis.call('DECRBY', KEYS[1], ARGV[1]) " +
            "    redis.call('INCRBY', KEYS[2], ARGV[1]) " +
            "    return 1 " +
            "else " +
            "    return 0 " +
            "end";

        DefaultRedisScript<Long> redisScript = new DefaultRedisScript<>();
        redisScript.setScriptText(script);
        redisScript.setResultType(Long.class);

        Long result = redisTemplate.execute(
            redisScript,
            Arrays.asList("account:" + fromAccount, "account:" + toAccount),
            String.valueOf(amount)
        );

        return result != null && result == 1;
    }
}
```

### 10. 注意事项

#### 10.1 事务中避免的操作

```bash
# ❌ 错误：事务中使用阻塞命令
MULTI
BLPOP queue 10  # 会导致整个事务阻塞
SET key value
EXEC

# ❌ 错误：事务中使用WATCH
MULTI
WATCH key  # WATCH必须在MULTI之前
SET key value
EXEC

# ✅ 正确：WATCH在MULTI之前
WATCH key
MULTI
SET key value
EXEC
```

#### 10.2 性能考虑

```java
// ❌ 避免：事务中包含大量命令
redisTemplate.multi();
for (int i = 0; i < 10000; i++) {
    redisTemplate.opsForValue().set("key" + i, "value" + i);
}
redisTemplate.exec();  // 会占用大量内存

// ✅ 推荐：使用Pipeline分批处理
List<String> keys = ...;
int batchSize = 1000;
for (int i = 0; i < keys.size(); i += batchSize) {
    List<String> batch = keys.subList(i, Math.min(i + batchSize, keys.size()));
    redisTemplate.executePipelined(new SessionCallback<Object>() {
        @Override
        public Object execute(RedisOperations operations) {
            for (String key : batch) {
                operations.opsForValue().set(key, "value");
            }
            return null;
        }
    });
}
```

### 答题总结

Redis 7事务提供了**轻量级的原子性保障**：

1. **基本机制**：MULTI/EXEC实现命令队列顺序执行
2. **乐观锁**：WATCH实现CAS操作，解决并发修改问题
3. **错误处理**：语法错误整体放弃，运行错误不回滚
4. **Lua脚本**：提供更强的原子性和复杂逻辑支持
5. **适用场景**：简单原子操作、秒杀、库存扣减、限流等

**与MySQL事务的核心区别**：Redis事务不支持回滚，更适合简单的原子操作；复杂业务逻辑建议使用Lua脚本或在应用层实现补偿机制。
