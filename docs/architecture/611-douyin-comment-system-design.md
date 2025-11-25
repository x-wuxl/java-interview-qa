---
layout: default
title: "如何设计抖音评论系统？如果加入好友关系该怎么做？"
parent: 架构设计与实战
nav_order: 611
description: 深入探讨抖音评论系统的设计思路，包括海量数据存储、高并发读写、热点视频处理，以及如何结合好友关系实现优先展示等功能的系统架构方案。
date: 2025-11-20 16:00:00 +0800
---
## 一、核心概念

抖音评论系统是一个典型的**高并发、海量数据、读多写多**的场景，需要重点考虑：

1. **亿级用户、千万级视频**的评论数据存储
2. **热点视频**可能瞬间产生百万级评论的写入压力
3. **评论列表加载**需要支持分页、排序（时间/热度）、嵌套回复
4. **好友关系**引入后要优先展示好友评论，涉及多维度查询

## 二、原理与设计关键点

### 2.1 基础评论系统设计

#### 核心表结构

```sql
-- 评论表（分库分表）
CREATE TABLE t_comment (
    id BIGINT PRIMARY KEY,           -- 雪花ID
    video_id BIGINT NOT NULL,        -- 视频ID
    user_id BIGINT NOT NULL,         -- 用户ID
    parent_id BIGINT DEFAULT 0,      -- 父评论ID（0表示根评论）
    root_id BIGINT DEFAULT 0,        -- 根评论ID（用于快速查询某评论的所有回复）
    content VARCHAR(500) NOT NULL,   -- 评论内容
    like_count INT DEFAULT 0,        -- 点赞数
    reply_count INT DEFAULT 0,       -- 回复数
    status TINYINT DEFAULT 1,        -- 状态（1正常 0删除）
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL,
    INDEX idx_video_root (video_id, root_id, create_time),
    INDEX idx_user (user_id, create_time)
) ENGINE=InnoDB;
```

#### 分库分表策略

**按 `video_id` 取模分表**（因为评论查询通常是"查某视频下的评论"）：

```java
// 分表路由示例
public class CommentShardingStrategy {
    private static final int TABLE_COUNT = 256;
    
    public String getTableName(Long videoId) {
        int tableIdx = (int) (videoId % TABLE_COUNT);
        return "t_comment_" + String.format("%03d", tableIdx);
    }
}
```

#### 读取优化

1. **一级评论+二级评论分离**
   - 一次请求只加载根评论（`parent_id=0`）+ 每条根评论的前 3 条回复
   - "查看更多回复"时再按 `root_id` 分页加载

2. **Redis 缓存热点视频评论**
   ```java
   // 缓存结构示例
   // Key: comment:video:{videoId}:page:{page}
   // Value: List<CommentDTO> (JSON序列化)
   String cacheKey = "comment:video:" + videoId + ":page:" + page;
   List<CommentDTO> comments = redisTemplate.opsForValue().get(cacheKey);
   if (comments == null) {
       comments = loadFromDB(videoId, page);
       redisTemplate.opsForValue().set(cacheKey, comments, 5, TimeUnit.MINUTES);
   }
   ```

3. **异步写入**
   - 评论提交后先写 MQ（Kafka/RocketMQ），快速返回
   - 消费者批量写入 MySQL + 更新缓存

### 2.2 热点视频处理

#### 问题场景
热门视频可能在短时间内产生**数十万评论写入**，导致：
- DB 写入热点分片压力过大
- 缓存频繁失效（缓存击穿）

#### 解决方案

1. **写入削峰**
   ```java
   // 使用消息队列缓冲
   @Service
   public class CommentService {
       @Autowired
       private KafkaTemplate<String, CommentEvent> kafkaTemplate;
       
       public void submitComment(CommentDTO dto) {
           // 前置校验（限流、敏感词）
           validateComment(dto);
           
           // 发送到MQ，异步处理
           CommentEvent event = new CommentEvent(dto);
           kafkaTemplate.send("comment-topic", event);
           
           // 立即返回成功（实际写入异步完成）
       }
   }
   ```

2. **缓存双层设计**
   - **本地缓存**（Caffeine）：存储超热视频的评论列表（1分钟过期）
   - **Redis**：存储热门视频评论（5分钟过期）
   - 读取顺序：本地缓存 → Redis → DB

3. **分布式限流**
   ```java
   // 基于Redis令牌桶限流
   @RateLimiter(key = "comment:video:#{videoId}", rate = 1000, capacity = 5000)
   public void submitComment(Long videoId, CommentDTO dto) {
       // ...
   }
   ```

### 2.3 加入好友关系的设计

#### 需求分析
- 用户希望**优先看到好友的评论**
- 评论列表需要**混合展示**：好友评论在前 + 普通评论补充

#### 实现方案

**方案一：客户端聚合**（推荐中小规模）

```java
@Service
public class CommentWithFriendService {
    
    public CommentListVO getComments(Long videoId, Long currentUserId, int page) {
        // 1. 查询用户的好友列表（走缓存）
        Set<Long> friendIds = friendService.getFriendIds(currentUserId);
        
        // 2. 分别查询好友评论和普通评论
        List<CommentDTO> friendComments = queryFriendComments(videoId, friendIds, page);
        List<CommentDTO> normalComments = queryNormalComments(videoId, page);
        
        // 3. 合并：好友评论在前，去重
        List<CommentDTO> result = mergeComments(friendComments, normalComments, 20);
        return new CommentListVO(result);
    }
    
    private List<CommentDTO> queryFriendComments(Long videoId, Set<Long> friendIds, int page) {
        // 从评论表中筛选 user_id IN friendIds
        return commentMapper.selectByVideoAndUsers(videoId, friendIds, page);
    }
}
```

**方案二：索引优化**（大规模场景）

1. **建立倒排索引**（Elasticsearch）
   ```json
   {
     "comment_id": "123456789",
     "video_id": "987654321",
     "user_id": "111222333",
     "is_friend": true,        // 冗余好友标识（异步更新）
     "content": "太棒啦！",
     "create_time": "2025-11-20T10:00:00",
     "like_count": 100
   }
   ```

2. **查询时按好友关系加权排序**
   ```java
   // ES查询示例
   SearchQuery query = new NativeSearchQueryBuilder()
       .withQuery(QueryBuilders.termQuery("video_id", videoId))
       .withSort(SortBuilders.scriptSort(
           new Script("doc['is_friend'].value ? 1000000 : doc['like_count'].value"),
           ScriptSortBuilder.ScriptSortType.NUMBER
       ).order(SortOrder.DESC))
       .withPageable(PageRequest.of(page, 20))
       .build();
   ```

**方案三：预计算好友评论**（超大规模）

- 用户发表评论时，通过 MQ 触发异步任务
- 将评论推送到该用户所有好友的"好友评论 Feed 流"（类似朋友圈）
- 读取时优先从 Feed 流读取

```java
// 伪代码示例
@Async
public void pushToFriendsFeed(CommentDTO comment) {
    Set<Long> friendIds = friendService.getFriendIds(comment.getUserId());
    for (Long friendId : friendIds) {
        String feedKey = "friend_comment_feed:" + friendId + ":" + comment.getVideoId();
        redisTemplate.opsForZSet().add(feedKey, comment, System.currentTimeMillis());
    }
}
```

## 三、性能与分布式考量

### 3.1 性能优化

| 优化点 | 方案 |
|--------|------|
| DB 查询 | 覆盖索引、只查必要字段、Limit 限制 |
| 缓存命中 | 多级缓存（本地+Redis）、预热热点数据 |
| 网络IO | 批量查询、CDN 加速用户头像 / 昵称 |
| 序列化 | Protobuf 替代 JSON（RPC 场景）|

### 3.2 一致性保证

1. **评论计数**：通过 MQ 异步更新 `reply_count` / `like_count`（最终一致性）
2. **缓存与 DB**：删除评论时先删 DB 再删缓存（Cache-Aside）
3. **分布式事务**：评论写入 + 消息发送使用**本地消息表**或 **Seata AT 模式**

### 3.3 线程安全

- **点赞计数**：使用 Redis `INCR` 原子操作，定期同步到 MySQL
- **热点评论更新**：分布式锁（Redisson）防止缓存击穿

```java
RLock lock = redissonClient.getLock("comment:lock:" + videoId);
try {
    if (lock.tryLock(100, 10, TimeUnit.SECONDS)) {
        // 重建缓存
        rebuildCache(videoId);
    }
} finally {
    lock.unlock();
}
```

## 四、答题总结

**核心设计要点**：
1. **存储**：MySQL 按 `video_id` 分库分表，热点数据 Redis 缓存
2. **写入**：MQ 削峰异步写入，分布式限流防止热点视频打爆
3. **读取**：多级缓存 + 分页懒加载（根评论 + 少量回复）
4. **好友关系**：
   - 小规模：客户端查询好友列表后聚合排序
   - 大规模：ES 建索引加权排序，或预计算 Feed 流

**面试加分项**：
- 提及**敏感词过滤**（DFA 算法本地缓存词库）
- 提及**审核机制**（AI 识别 + 人工复审的异步流程）
- 提及**数据归档**（冷数据定期迁移到对象存储）
