---
layout: default
title: "Redis的ZSet是如何实现的？"
parent: Redis
nav_order: 409
description: "深入解析Redis ZSet的底层实现，包括ListPack/ZipList和SkipList+HashTable的双重编码机制、跳表原理及应用场景"
author: "wuxl"
date: 2025-11-02
---
## 问题

Redis的ZSet是如何实现的？

## 答案

### 1. 核心概念

Redis的ZSet（有序集合）是一个**有序、不重复**的字符串集合，每个元素关联一个**score（分数）**用于排序。底层采用**双重编码机制**：小数据量使用ListPack/ZipList，大数据量使用**SkipList（跳表）+ HashTable**的组合结构。

---

### 2. 双重编码机制

#### 2.1 编码切换条件

**配置参数**：
```bash
# Redis 7.0+ 使用ListPack
zset-max-listpack-entries 128    # 元素数量阈值
zset-max-listpack-value 64       # 单个元素大小阈值（字节）

# Redis 7.0之前使用ZipList
zset-max-ziplist-entries 128
zset-max-ziplist-value 64
```

**编码选择**：
```java
if (元素数量 <= 128 && 所有元素大小 <= 64字节) {
    使用 ListPack（或ZipList）
} else {
    使用 SkipList + HashTable
}
```

**查看编码**：
```bash
redis> ZADD rank 100 "player1" 95 "player2"
redis> OBJECT ENCODING rank
"listpack"

redis> ZADD rank 90 "这是一个超过64字节的长名字........................"
redis> OBJECT ENCODING rank
"skiplist"  # 自动转换
```

---

### 3. ListPack/ZipList实现（紧凑编码）

#### 3.1 存储结构

**ZipList存储方式**：按score升序排列，score和element交替存储

```
ZipList: [score1, element1, score2, element2, ...]
```

**示例**：
```bash
ZADD rank 100 "Alice" 95 "Bob" 90 "Charlie"
# ZipList: [90, "Charlie", 95, "Bob", 100, "Alice"]
#          按score升序存储
```

---

#### 3.2 操作特性

**查找元素**：
```java
// 伪代码：O(N)遍历
for (int i = 0; i < ziplist.length; i += 2) {
    if (ziplist[i+1].equals(target)) {
        return ziplist[i]; // 返回score
    }
}
```

**范围查询**：
```bash
ZRANGE rank 0 2  # 获取排名前3
# 由于已按score排序，直接顺序读取
```

**优缺点**：
- **优点**：内存紧凑，无额外指针开销
- **缺点**：查找O(N)，插入需移动元素保持有序

---

### 4. SkipList + HashTable实现

#### 4.1 为什么需要两种结构？

**跳表（SkipList）**：
- 按score有序排列，支持范围查询
- 查找、插入、删除平均O(log N)

**哈希表（HashTable）**：
- 通过元素快速定位score，O(1)查询
- 支持`ZSCORE`命令高效执行

**两者结合**：
```
HashTable: element -> score
SkipList:  score -> element（有序）

同一份数据，两种索引方式
```

---

#### 4.2 跳表结构详解

**核心数据结构**：
```c
// ZSet对象
typedef struct zset {
    dict *dict;       // 哈希表：element -> score
    zskiplist *zsl;   // 跳表：score -> element
} zset;

// 跳表结构
typedef struct zskiplist {
    zskiplistNode *header;  // 头节点
    zskiplistNode *tail;    // 尾节点
    unsigned long length;   // 节点数量
    int level;              // 最大层数
} zskiplist;

// 跳表节点
typedef struct zskiplistNode {
    sds ele;                // 元素值
    double score;           // 分数
    zskiplistNode *backward; // 后退指针
    struct zskiplistLevel {
        zskiplistNode *forward; // 前进指针
        unsigned long span;     // 跨度（用于计算排名）
    } level[];              // 层级数组（柔性数组）
} zskiplistNode;
```

**跳表示例**（4层）：
```
L4: header -----------------> node3 ----------> NULL
L3: header -------> node2 --> node3 ----------> NULL
L2: header -> node1 -> node2 -> node3 -> node4 -> NULL
L1: header -> node1 -> node2 -> node3 -> node4 -> NULL
          (90)    (95)    (100)   (105)
```

---

#### 4.3 跳表的关键算法

**随机层数生成**：
```c
#define ZSKIPLIST_MAXLEVEL 32
#define ZSKIPLIST_P 0.25

int zslRandomLevel(void) {
    int level = 1;
    while ((random() & 0xFFFF) < (ZSKIPLIST_P * 0xFFFF))
        level += 1;
    return (level < ZSKIPLIST_MAXLEVEL) ? level : ZSKIPLIST_MAXLEVEL;
}

// 每个节点：
// - 1层概率：100%
// - 2层概率：25%
// - 3层概率：6.25%
// - 4层概率：1.56%
```

**查找流程**：
```java
// 从最高层开始查找
Node findNode(double targetScore) {
    Node current = header;
    for (int i = currentLevel; i >= 0; i--) {
        // 在当前层向前移动
        while (current.level[i].forward != null 
               && current.level[i].forward.score < targetScore) {
            current = current.level[i].forward;
        }
    }
    // 回到第1层
    current = current.level[0].forward;
    return current;
}
```

**插入流程**：
```java
1. 查找插入位置
2. 随机生成层数
3. 更新各层指针
4. 更新span（跨度）字段
5. 同步更新HashTable
```

---

### 5. 常用操作的实现原理

#### 5.1 ZADD（添加元素）

```bash
ZADD rank 100 "Alice"
```

**流程**：
```java
1. 检查元素是否已存在（通过HashTable）
   - 存在：更新score，调整跳表位置
   - 不存在：继续下一步

2. 在跳表中查找插入位置
   - 从最高层开始向下查找

3. 随机生成层数（平均1.33层）

4. 插入节点到跳表各层

5. 更新HashTable：dict["Alice"] = 100

6. 更新span字段（用于ZRANK排名计算）
```

**时间复杂度**：O(log N)

---

#### 5.2 ZRANGE（范围查询）

```bash
ZRANGE rank 0 2  # 获取排名0-2的元素
```

**流程**：
```java
1. 通过span字段定位到起始排名节点
2. 沿着第1层forward指针顺序遍历
3. 返回指定范围的元素
```

**时间复杂度**：O(log N + M)，M为返回元素数量

---

#### 5.3 ZSCORE（查询分数）

```bash
ZSCORE rank "Alice"
```

**流程**：
```java
// 直接查询HashTable
score = dict.get("Alice");  // O(1)
```

**时间复杂度**：O(1)

---

#### 5.4 ZRANK（查询排名）

```bash
ZRANK rank "Alice"  # 返回Alice的排名
```

**流程**：
```java
1. 从HashTable获取score
2. 在跳表中查找该节点
3. 累加经过节点的span字段
4. 返回排名
```

**时间复杂度**：O(log N)

---

### 6. 应用场景与最佳实践

#### 6.1 排行榜系统

```java
// 更新玩家分数
ZADD game:rank 9500 "player:1001"
ZINCRBY game:rank 100 "player:1001"  // 加100分

// 获取Top 10
ZREVRANGE game:rank 0 9 WITHSCORES
// 结果：
// 1) "player:1001"
// 2) "9600"
// 3) "player:1002"
// 4) "9500"
// ...

// 查询玩家排名
ZREVRANK game:rank "player:1001"  // 返回：0（第1名）

// 获取某分数段玩家
ZRANGEBYSCORE game:rank 9000 9500
```

**Java实现**：
```java
// 更新分数
redisTemplate.opsForZSet().incrementScore("game:rank", "player:1001", 100);

// 获取Top 10（降序）
Set<ZSetOperations.TypedTuple<String>> top10 = 
    redisTemplate.opsForZSet().reverseRangeWithScores("game:rank", 0, 9);

for (ZSetOperations.TypedTuple<String> tuple : top10) {
    System.out.println(tuple.getValue() + ": " + tuple.getScore());
}

// 查询排名
Long rank = redisTemplate.opsForZSet().reverseRank("game:rank", "player:1001");
```

---

#### 6.2 延时队列

```java
// 添加任务（score为执行时间戳）
long executeTime = System.currentTimeMillis() + 60000; // 1分钟后执行
ZADD delay:queue <executeTime> "task:1001"

// 定时扫描到期任务
long now = System.currentTimeMillis();
ZRANGEBYSCORE delay:queue 0 <now> LIMIT 0 10
// 获取10个到期任务

// 删除已处理任务
ZREM delay:queue "task:1001"
```

**Java实现**：
```java
public class DelayQueue {
    @Scheduled(fixedDelay = 1000)
    public void processTasks() {
        long now = System.currentTimeMillis();
        // 获取到期任务
        Set<String> tasks = redisTemplate.opsForZSet()
            .rangeByScore("delay:queue", 0, now, 0, 10);
        
        for (String task : tasks) {
            // 处理任务
            processTask(task);
            // 删除任务
            redisTemplate.opsForZSet().remove("delay:queue", task);
        }
    }
}
```

---

#### 6.3 时间线/事件流

```java
// 存储用户动态（score为时间戳）
ZADD timeline:1001 <timestamp> "post:2001"

// 获取最新20条动态
ZREVRANGE timeline:1001 0 19

// 获取某时间段动态
ZRANGEBYSCORE timeline:1001 <startTime> <endTime>

// 删除7天前的动态
long sevenDaysAgo = System.currentTimeMillis() - 7 * 24 * 3600 * 1000;
ZREMRANGEBYSCORE timeline:1001 0 <sevenDaysAgo>
```

---

#### 6.4 自动补全/搜索建议

```java
// 存储搜索词（score为热度）
ZADD search:suggestions 1000 "redis"
ZADD search:suggestions 800 "redis cluster"
ZADD search:suggestions 500 "redis sentinel"

// 增加搜索热度
ZINCRBY search:suggestions 1 "redis"

// 获取热门搜索词
ZREVRANGE search:suggestions 0 9  // Top 10
```

---

### 7. 性能优化建议

#### 7.1 控制ZSet大小
- **小对象优化**：保持在128个元素以下，享受ListPack的内存优势
- **大ZSet拆分**：按时间、分类等维度拆分（如`rank:2024-11`、`rank:2024-12`）

#### 7.2 避免大范围查询
```bash
# 不推荐：获取全部元素
ZRANGE rank 0 -1  # 百万级数据会阻塞

# 推荐：分页查询
ZRANGE rank 0 99     # 第1页
ZRANGE rank 100 199  # 第2页
```

#### 7.3 定期清理过期数据
```java
// 只保留Top 1000
ZREMRANGEBYRANK rank 1000 -1

// 删除低分数据
ZREMRANGEBYSCORE rank 0 100

// 删除N天前的数据
ZREMRANGEBYSCORE timeline:1001 0 <timestamp>
```

#### 7.4 合理使用WITHSCORES
```bash
# 不需要score时省略
ZRANGE rank 0 9

# 需要score时才加
ZRANGE rank 0 9 WITHSCORES
```

---

### 8. 面试答题总结

**标准回答模板**：

> Redis的ZSet采用**双重编码**机制：
> 1. **小对象**（≤128个元素且每个≤64字节）：使用**ListPack**（或ZipList），按score升序存储，内存紧凑但查找O(N)
> 2. **大对象**：使用**SkipList + HashTable**组合
>    - **SkipList**：按score有序，支持范围查询，平均O(log N)
>    - **HashTable**：通过元素查score，O(1)
>
> 跳表通过多层索引加速查找，每个节点随机1-32层（平均1.33层），概率P=0.25。

**常见追问**：
- **为什么用跳表而不是红黑树？** → 实现简单、支持范围查询、内存局部性好
- **为什么需要HashTable？** → 快速通过元素查score（如ZSCORE命令），O(1)
- **跳表的层数如何确定？** → 随机生成，每层晋升概率25%，平均1.33层
- **ZSet的内存占用？** → 同一数据存两份（跳表+哈希表），但换来了性能提升

