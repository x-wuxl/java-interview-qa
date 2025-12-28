---
layout: post
title: "每小时千万级的点赞场景如何设计？"
date: 2025-12-28
categories: [大厂项目场景实战, 高并发实战]
tags: [高并发, 点赞, Redis, 异步, 热点数据]
description: "通过学生作品点赞场景讲解千万级高并发系统设计，包括Redis缓存、异步落库等方案。"
---

# 每小时千万级的点赞场景如何设计？

## 业务场景

在线教育平台，学生可以为优秀作品点赞。

**流量特征**：
- 高峰期每小时千万级点赞
- 读多写多（查点赞数 + 点赞操作）
- 数据最终一致即可

---

## 设计挑战

| 挑战 | 说明 |
|------|------|
| 高并发写 | 每秒数千次点赞 |
| 高并发读 | 查询点赞数更频繁 |
| 数据持久化 | 需要落库 |
| 防重复点赞 | 同一用户只能点赞一次 |
| 热点问题 | 热门作品点赞集中 |

---

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                      点赞服务                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  点赞请求 → Redis（实时计数） → 异步队列 → 数据库        │
│                                                         │
│  查询请求 → Redis（直接返回）                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 核心策略

1. **Redis前置**：所有读写都走Redis
2. **异步落库**：定时批量同步到MySQL
3. **Set去重**：防止重复点赞

---

## 数据结构设计

### Redis数据结构

```
# 点赞计数（String）
work:like:count:{workId} = 1234

# 点赞用户集合（Set，用于去重和取消点赞）
work:like:users:{workId} = {user1, user2, user3...}

# 用户已赞作品（Set，用于"我的点赞"列表）
user:likes:{userId} = {work1, work2, work3...}
```

### MySQL表结构

```sql
CREATE TABLE work_likes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    work_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    status TINYINT DEFAULT 1 COMMENT '1点赞 0取消',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_work_user (work_id, user_id)
);

CREATE TABLE work_like_counts (
    work_id BIGINT PRIMARY KEY,
    like_count BIGINT DEFAULT 0,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

## 核心代码实现

### 点赞接口

```java
@Service
public class LikeService {
    
    @Autowired
    private StringRedisTemplate redis;
    
    public boolean like(Long userId, Long workId) {
        String countKey = "work:like:count:" + workId;
        String usersKey = "work:like:users:" + workId;
        String userLikesKey = "user:likes:" + userId;
        
        // 1. 检查是否已点赞（SISMEMBER O(1)）
        Boolean exists = redis.opsForSet().isMember(usersKey, userId.toString());
        if (Boolean.TRUE.equals(exists)) {
            return false;  // 已点赞
        }
        
        // 2. Lua脚本保证原子性
        String script = """
            redis.call('SADD', KEYS[1], ARGV[1])
            redis.call('SADD', KEYS[2], ARGV[2])
            redis.call('INCR', KEYS[3])
            return 1
            """;
        
        redis.execute(new DefaultRedisScript<>(script, Long.class),
            List.of(usersKey, userLikesKey, countKey),
            userId.toString(), workId.toString());
        
        // 3. 发送异步消息落库
        kafkaTemplate.send("like-topic", JSON.toJSONString(
            new LikeEvent(userId, workId, LikeAction.LIKE)));
        
        return true;
    }
    
    public boolean unlike(Long userId, Long workId) {
        String countKey = "work:like:count:" + workId;
        String usersKey = "work:like:users:" + workId;
        String userLikesKey = "user:likes:" + userId;
        
        // 检查是否已点赞
        Boolean exists = redis.opsForSet().isMember(usersKey, userId.toString());
        if (!Boolean.TRUE.equals(exists)) {
            return false;  // 未点赞
        }
        
        // Lua脚本原子取消
        String script = """
            redis.call('SREM', KEYS[1], ARGV[1])
            redis.call('SREM', KEYS[2], ARGV[2])
            redis.call('DECR', KEYS[3])
            return 1
            """;
        
        redis.execute(new DefaultRedisScript<>(script, Long.class),
            List.of(usersKey, userLikesKey, countKey),
            userId.toString(), workId.toString());
        
        kafkaTemplate.send("like-topic", JSON.toJSONString(
            new LikeEvent(userId, workId, LikeAction.UNLIKE)));
        
        return true;
    }
}
```

### 查询点赞数

```java
public Long getLikeCount(Long workId) {
    String countKey = "work:like:count:" + workId;
    String count = redis.opsForValue().get(countKey);
    return count != null ? Long.parseLong(count) : 0L;
}

public boolean isLiked(Long userId, Long workId) {
    String usersKey = "work:like:users:" + workId;
    return Boolean.TRUE.equals(
        redis.opsForSet().isMember(usersKey, userId.toString()));
}
```

### 异步落库

```java
@KafkaListener(topics = "like-topic")
public void syncToDb(List<ConsumerRecord<String, String>> records) {
    
    Map<String, LikeEvent> latestEvents = new HashMap<>();
    
    // 合并同一用户对同一作品的操作（只保留最新状态）
    for (ConsumerRecord<String, String> record : records) {
        LikeEvent event = JSON.parseObject(record.value(), LikeEvent.class);
        String key = event.getUserId() + ":" + event.getWorkId();
        latestEvents.put(key, event);
    }
    
    // 批量更新
    for (LikeEvent event : latestEvents.values()) {
        likeMapper.upsert(event);
    }
    
    // 更新计数表
    updateLikeCounts(latestEvents.values());
}
```

---

## 热点问题处理

### 问题
热门作品点赞集中，Redis单Key压力大。

### 解决方案：分片计数

```java
// 将计数分散到多个key
public void likeWithSharding(Long workId) {
    int shard = ThreadLocalRandom.current().nextInt(10);
    String key = "work:like:count:" + workId + ":" + shard;
    redis.opsForValue().increment(key);
}

// 查询时汇总
public Long getLikeCountWithSharding(Long workId) {
    long total = 0;
    for (int i = 0; i < 10; i++) {
        String key = "work:like:count:" + workId + ":" + i;
        String count = redis.opsForValue().get(key);
        total += count != null ? Long.parseLong(count) : 0;
    }
    return total;
}
```

---

## 面试答题框架

```
业务特征：高并发读写、最终一致

核心设计：
1. Redis前置所有读写
2. Set结构去重（SISMEMBER O(1)）
3. Lua脚本保证原子性
4. 异步消息落库

数据结构：
- 计数: String
- 去重: Set
- 用户已赞: Set

热点处理：
- 分片计数（10个子key）
- 本地缓存热点作品

效果：
- 点赞响应<5ms
- 支持千万级/小时
```

---

## 总结

| 设计点 | 方案 |
|--------|------|
| 实时读写 | Redis |
| 去重 | Set SISMEMBER |
| 原子性 | Lua脚本 |
| 持久化 | Kafka异步落库 |
| 热点 | 分片计数 |
