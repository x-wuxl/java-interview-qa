---
title: "如何实现排行榜，例如高考成绩排序？"
date: 2025-11-20 15:51:36 +0800
categories: [Redis, 数据结构]
tags: [排行榜, Redis, ZSet, 数据结构, 性能优化]
description: "详解排行榜的多种实现方案，重点介绍 Redis ZSet 的原理、实现和性能优化，以及大数据量场景下的分段排行榜方案"
nav_order: 607
parent: 架构设计与实战
---
## 核心概念

**排行榜**是根据特定维度（如分数、销量、点赞数）对数据进行排序并展示Top N 的功能。典型场景包括：
- **游戏排行榜**（按积分排序）
- **高考成绩排名**（按总分排序）
- **商品销量榜**（按销量排序）
- **热搜榜**（按热度排序）

排行榜的核心需求：
1. **快速插入和更新**（用户分数变化）
2. **高效范围查询**（Top 100）
3. **实时排名查询**（某个用户的排名）
4. **分数相同时的稳定排序**

---

## 实现方案

### 1. 数据库实现（不推荐）

**方案一：ORDER BY + LIMIT**

```sql
-- 查询 Top 100
SELECT student_id, name, score 
FROM exam_scores 
ORDER BY score DESC, student_id ASC 
LIMIT 100;

-- 查询某个学生的排名
SELECT COUNT(*) + 1 AS ranking
FROM exam_scores
WHERE score > (SELECT score FROM exam_scores WHERE student_id = 'xxx')
   OR (score = (SELECT score FROM exam_scores WHERE student_id = 'xxx') 
       AND student_id < 'xxx');
```

**缺点**：
- 每次查询都需全表扫描排序（即使有索引，数据量大时仍慢）
- 排名查询需要子查询，性能差
- 并发更新时锁竞争严重

**方案二：维护排名字段**

```sql
-- 更新分数触发器，重新计算所有排名
CREATE TRIGGER update_ranking 
AFTER UPDATE ON exam_scores
FOR EACH ROW
BEGIN
    -- 重新计算排名逻辑（成本极高）
END;
```

**缺点**：每次分数变化都要更新大量记录，性能极差

**适用场景**：数据量小（千级以下）且更新不频繁的场景

---

### 2. Redis ZSet 实现（推荐）

**原理**：Redis 的有序集合（Sorted Set）底层使用 **跳表（Skip List）+ 哈希表** 实现，天然支持排序和范围查询。

#### 跳表结构简介

```
Level 3:  1 ----------------------> 7
Level 2:  1 -------> 4 ----------> 7 -------> 9
Level 1:  1 --> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
```

- 查询、插入、删除的平均时间复杂度：**O(log n)**
- 范围查询性能优异

#### 基础实现

```java
@Service
public class LeaderboardService {
    @Autowired
    private StringRedisTemplate redisTemplate;
    
    private static final String LEADERBOARD_KEY = "leaderboard:exam";

    // 1. 更新学生分数
    public void updateScore(String studentId, double score) {
        redisTemplate.opsForZSet().add(LEADERBOARD_KEY, studentId, score);
    }

    // 2. 获取 Top N（降序）
    public List<StudentScore> getTopN(int n) {
        // ZREVRANGE 返回分数从高到低的前 n 个
        Set<ZSetOperations.TypedTuple<String>> topN = redisTemplate.opsForZSet()
            .reverseRangeWithScores(LEADERBOARD_KEY, 0, n - 1);
        
        return topN.stream()
            .map(tuple -> new StudentScore(
                tuple.getValue(), 
                tuple.getScore()
            ))
            .collect(Collectors.toList());
    }

    // 3. 获取学生排名（1-based）
    public Long getRanking(String studentId) {
        Long rank = redisTemplate.opsForZSet()
            .reverseRank(LEADERBOARD_KEY, studentId);  // 降序排名
        return rank == null ? null : rank + 1;  // Redis 是 0-based
    }

    // 4. 获取学生分数
    public Double getScore(String studentId) {
        return redisTemplate.opsForZSet().score(LEADERBOARD_KEY, studentId);
    }

    // 5. 获取指定排名范围（如 10-20 名）
    public List<StudentScore> getRangeByRank(int start, int end) {
        Set<ZSetOperations.TypedTuple<String>> range = redisTemplate.opsForZSet()
            .reverseRangeWithScores(LEADERBOARD_KEY, start - 1, end - 1);
        
        return range.stream()
            .map(tuple -> new StudentScore(tuple.getValue(), tuple.getScore()))
            .collect(Collectors.toList());
    }

    // 6. 获取指定分数范围（如 600-700 分的学生）
    public List<StudentScore> getRangeByScore(double minScore, double maxScore) {
        Set<ZSetOperations.TypedTuple<String>> range = redisTemplate.opsForZSet()
            .reverseRangeByScoreWithScores(LEADERBOARD_KEY, minScore, maxScore);
        
        return range.stream()
            .map(tuple -> new StudentScore(tuple.getValue(), tuple.getScore()))
            .collect(Collectors.toList());
    }
}

@Data
@AllArgsConstructor
class StudentScore {
    private String studentId;
    private Double score;
}
```

#### ZSet 常用命令

```bash
# 添加/更新成员
ZADD leaderboard:exam 650.5 student001 698.0 student002

# 获取 Top 10（降序）
ZREVRANGE leaderboard:exam 0 9 WITHSCORES

# 获取某个学生的排名（降序，0-based）
ZREVRANK leaderboard:exam student001

# 获取某个学生的分数
ZSCORE leaderboard:exam student001

# 获取排名范围
ZREVRANGE leaderboard:exam 10 20 WITHSCORES

# 获取分数范围（600-700 分）
ZREVRANGEBYSCORE leaderboard:exam 700 600 WITHSCORES

# 删除成员
ZREM leaderboard:exam student001

# 获取总人数
ZCARD leaderboard:exam

# 获取指定分数区间人数
ZCOUNT leaderboard:exam 600 700
```

---

### 3. 分数相同时的处理

**问题**：多个学生同分时，如何保证排序稳定性？

**方案一：复合 Score**

```java
// 将学号作为小数部分，确保同分时按学号排序
// 例如: 650.5 分，学号 12345 → score = 650.5 + 0.000012345
public void updateScoreWithId(String studentId, double score) {
    long idNum = Long.parseLong(studentId);
    double compositeScore = score + (idNum / 1_000_000_000.0);
    redisTemplate.opsForZSet().add(LEADERBOARD_KEY, studentId, compositeScore);
}
```

**方案二：使用时间戳**

```java
// 分数相同时，先达到该分数的排名靠前
public void updateScoreWithTime(String studentId, double score) {
    long timestamp = System.currentTimeMillis();
    double compositeScore = score - (timestamp / 1_000_000_000_000.0);
    redisTemplate.opsForZSet().add(LEADERBOARD_KEY, studentId, compositeScore);
}
```

**方案三：ZSet + Hash 组合**

```java
// ZSet 存储纯分数，Hash 存储详细信息（包括时间戳）
public void updateScore(String studentId, double score, long timestamp) {
    // ZSet 存分数
    redisTemplate.opsForZSet().add(LEADERBOARD_KEY, studentId, score);
    
    // Hash 存详细信息
    Map<String, String> info = new HashMap<>();
    info.put("score", String.valueOf(score));
    info.put("timestamp", String.valueOf(timestamp));
    redisTemplate.opsForHash().putAll("student:" + studentId, info);
}

// 查询时先从 ZSet 获取同分学生，再从 Hash 按时间戳排序
```

---

### 4. 大数据量优化方案

#### 问题：全量排行榜内存占用大

**解决方案一：分段排行榜**

```java
// 按分数段分别维护排行榜
public class SegmentedLeaderboard {
    // 600-700: leaderboard:600-700
    // 500-600: leaderboard:500-600
    
    public void updateScore(String studentId, double score) {
        int segment = (int) (score / 100) * 100;
        String key = String.format("leaderboard:%d-%d", segment, segment + 100);
        redisTemplate.opsForZSet().add(key, studentId, score);
    }
    
    // 查询 Top N 时，从高分段依次遍历
    public List<StudentScore> getTopN(int n) {
        List<StudentScore> result = new ArrayList<>();
        for (int segment = 700; segment >= 0; segment -= 100) {
            String key = String.format("leaderboard:%d-%d", segment, segment + 100);
            Set<ZSetOperations.TypedTuple<String>> segmentTop = 
                redisTemplate.opsForZSet()
                    .reverseRangeWithScores(key, 0, n - result.size() - 1);
            
            segmentTop.forEach(tuple -> 
                result.add(new StudentScore(tuple.getValue(), tuple.getScore()))
            );
            
            if (result.size() >= n) break;
        }
        return result;
    }
}
```

**解决方案二：只保留 Top N**

```java
// 只维护 Top 10000 名
public void updateScore(String studentId, double score) {
    redisTemplate.opsForZSet().add(LEADERBOARD_KEY, studentId, score);
    
    // 保留 Top 10000，删除其他
    Long size = redisTemplate.opsForZSet().size(LEADERBOARD_KEY);
    if (size != null && size > 10000) {
        redisTemplate.opsForZSet().removeRange(LEADERBOARD_KEY, 0, size - 10001);
    }
}
```

**解决方案三：多级缓存**

```
Level 1: Redis ZSet（Top 1000）
Level 2: 数据库索引（全量数据）
Level 3: 定时任务同步（每小时从 DB 刷新 Top 1000 到 Redis）
```

---

### 5. 实时性 vs 准确性权衡

#### 场景一：秒级更新（游戏排行榜）

```java
// 使用 Redis Pipeline 批量更新
public void batchUpdateScores(Map<String, Double> scoreMap) {
    redisTemplate.executePipelined(new SessionCallback<Object>() {
        @Override
        public Object execute(RedisOperations operations) {
            scoreMap.forEach((studentId, score) -> 
                operations.opsForZSet().add(LEADERBOARD_KEY, studentId, score)
            );
            return null;
        }
    });
}
```

#### 场景二：准确性优先（高考成绩）

```java
// 使用 Lua 脚本保证原子性
private static final String UPDATE_SCORE_LUA = 
    "local currentScore = redis.call('ZSCORE', KEYS[1], ARGV[1])\n" +
    "if not currentScore or tonumber(ARGV[2]) > tonumber(currentScore) then\n" +
    "    redis.call('ZADD', KEYS[1], ARGV[2], ARGV[1])\n" +
    "    return 1\n" +
    "else\n" +
    "    return 0\n" +
    "end";

public boolean updateScoreIfHigher(String studentId, double newScore) {
    Long result = redisTemplate.execute(
        new DefaultRedisScript<>(UPDATE_SCORE_LUA, Long.class),
        Collections.singletonList(LEADERBOARD_KEY),
        studentId,
        String.valueOf(newScore)
    );
    return result != null && result == 1;
}
```

---

### 6. 完整示例：高考成绩排行榜

```java
@RestController
@RequestMapping("/api/leaderboard")
public class LeaderboardController {
    @Autowired
    private LeaderboardService leaderboardService;

    // 提交/更新成绩
    @PostMapping("/score")
    public ResponseEntity<Void> submitScore(@RequestBody ScoreDTO dto) {
        leaderboardService.updateScore(dto.getStudentId(), dto.getScore());
        return ResponseEntity.ok().build();
    }

    // 查询 Top 100
    @GetMapping("/top/{n}")
    public ResponseEntity<List<StudentRankVO>> getTop(@PathVariable int n) {
        List<StudentScore> topN = leaderboardService.getTopN(n);
        
        List<StudentRankVO> result = new ArrayList<>();
        for (int i = 0; i < topN.size(); i++) {
            StudentScore student = topN.get(i);
            result.add(new StudentRankVO(
                i + 1,  // 排名
                student.getStudentId(),
                student.getScore()
            ));
        }
        return ResponseEntity.ok(result);
    }

    // 查询个人排名
    @GetMapping("/rank/{studentId}")
    public ResponseEntity<PersonalRankVO> getMyRank(@PathVariable String studentId) {
        Long rank = leaderboardService.getRanking(studentId);
        Double score = leaderboardService.getScore(studentId);
        
        if (rank == null || score == null) {
            return ResponseEntity.notFound().build();
        }
        
        return ResponseEntity.ok(new PersonalRankVO(studentId, score, rank));
    }

    // 查询周边排名（如前后各 5 名）
    @GetMapping("/around/{studentId}")
    public ResponseEntity<List<StudentRankVO>> getAroundRank(
            @PathVariable String studentId,
            @RequestParam(defaultValue = "5") int range) {
        Long myRank = leaderboardService.getRanking(studentId);
        if (myRank == null) {
            return ResponseEntity.notFound().build();
        }
        
        int start = Math.max(1, (int) (myRank - range));
        int end = (int) (myRank + range);
        
        return ResponseEntity.ok(convertToVO(
            leaderboardService.getRangeByRank(start, end),
            start
        ));
    }
}
```

---

## 性能对比

| 方案 | 插入 | 查询 Top N | 查询排名 | 内存占用 | 适用场景 |
|------|------|-----------|---------|---------|---------|
| MySQL ORDER BY | O(n log n) | O(n log n) | O(n) | 低 | 小数据量 |
| MySQL 排名字段 | O(n) | O(1) | O(1) | 低 | 不更新或少更新 |
| **Redis ZSet** | **O(log n)** | **O(log n + m)** | **O(log n)** | 中 | **推荐** |
| 分段 ZSet | O(log n) | O(k log n) | O(log n) | 低 | 超大数据量 |

> m 为返回元素数量，k 为分段数量

---

## 线程安全与分布式考量

### 1. 并发更新安全

Redis 单线程模型保证了命令的原子性，ZSet 操作天然线程安全。

### 2. 数据一致性

**问题**：Redis 和数据库双写不一致

**方案**：
```java
@Transactional
public void updateScore(String studentId, double score) {
    // 1. 先更新数据库
    examScoreMapper.updateScore(studentId, score);
    
    // 2. 再更新 Redis（失败可通过定时任务补偿）
    try {
        redisTemplate.opsForZSet().add(LEADERBOARD_KEY, studentId, score);
    } catch (Exception e) {
        log.error("Redis update failed: {}", studentId, e);
        // 发送消息到 MQ，异步补偿
    }
}
```

### 3. 热 Key 问题

**问题**：Top 1 频繁被查询

**方案**：
- 本地缓存 Top 100（Caffeine），1 秒过期
- 多级缓存：Redis + Caffeine
- 读写分离：Redis 主从 + Sentinel

---

## 面试答题总结

**核心考点**：
1. Redis ZSet 的底层数据结构（跳表 + 哈希表）
2. 时间复杂度分析（插入、查询 Top N、查询排名）
3. 分数相同时的处理方案（复合 Score、时间戳）
4. 大数据量优化（分段排行榜、只保留 Top N）
5. Redis 与 DB 的数据一致性

**回答框架**：
- 先说场景（高考成绩、游戏排行榜）
- 对比方案：MySQL（慢）→ Redis ZSet（推荐）
- 讲 ZSet 原理：跳表 O(log n)，支持范围查询
- 说明分数相同的处理（复合 Score）
- 补充大数据量优化（分段、Top N 截断）
- 结合项目经验（如"我们游戏排行榜用 Redis ZSet，每秒千级更新"）
