---
title: "Redis跳表实现，hash底层实现，为什么使用ziplist，如何扩容"
date: 2025-11-02
description: "综合解析Redis跳表的实现细节、Hash的渐进式rehash扩容机制、ZipList的使用原因及编码转换策略"
author: "wuxl"
categories: [中间件]
tags: [Redis, 跳表, Hash, ZipList, rehash, 扩容]
nav_order: 411
parent: Redis
---
## 问题

Redis跳表实现，hash底层实现，为什么使用ziplist，如何扩容？

## 答案

### 1. 跳表的实现细节

#### 1.1 跳表核心结构

**数据结构定义**：
```c
// 跳表节点
typedef struct zskiplistNode {
    sds ele;                    // 元素值
    double score;               // 分数（排序依据）
    struct zskiplistNode *backward; // 后退指针
    struct zskiplistLevel {
        struct zskiplistNode *forward;  // 前进指针
        unsigned long span;             // 跨度（到下个节点的距离）
    } level[];                  // 层级数组（柔性数组）
} zskiplistNode;

// 跳表
typedef struct zskiplist {
    struct zskiplistNode *header;  // 头节点
    struct zskiplistNode *tail;    // 尾节点
    unsigned long length;          // 节点数量
    int level;                     // 当前最大层数
} zskiplist;

// ZSet结构（跳表+哈希表）
typedef struct zset {
    dict *dict;       // 哈希表：element -> score（O(1)查询score）
    zskiplist *zsl;   // 跳表：score -> element（有序，支持范围查询）
} zset;
```

---

#### 1.2 层数生成算法

**随机层数**：
```c
#define ZSKIPLIST_MAXLEVEL 32
#define ZSKIPLIST_P 0.25

int zslRandomLevel(void) {
    int level = 1;
    while ((random() & 0xFFFF) < (ZSKIPLIST_P * 0xFFFF))
        level += 1;
    return (level < ZSKIPLIST_MAXLEVEL) ? level : ZSKIPLIST_MAXLEVEL;
}
```

**概率分布**：
```
1层：100%
2层：25%（0.25概率）
3层：6.25%（0.25²）
4层：1.56%（0.25³）

平均层数 = 1 / (1 - P) = 1 / 0.75 ≈ 1.33层
```

**为什么P=0.25？**
- **太大（如0.5）**：索引层过多，内存开销大
- **太小（如0.1）**：索引效果差，查找性能下降
- **0.25**：经验值，平衡内存和性能

---

#### 1.3 插入算法实现

**核心步骤**：
```c
zskiplistNode *zslInsert(zskiplist *zsl, double score, sds ele) {
    zskiplistNode *update[ZSKIPLIST_MAXLEVEL];  // 记录每层的前驱节点
    unsigned long rank[ZSKIPLIST_MAXLEVEL];     // 记录每层的排名
    
    // 1. 查找插入位置（从最高层开始）
    zskiplistNode *x = zsl->header;
    for (int i = zsl->level - 1; i >= 0; i--) {
        rank[i] = (i == zsl->level - 1) ? 0 : rank[i + 1];
        
        // 在当前层向前移动
        while (x->level[i].forward != NULL &&
               (x->level[i].forward->score < score ||
                (x->level[i].forward->score == score &&
                 sdscmp(x->level[i].forward->ele, ele) < 0))) {
            rank[i] += x->level[i].span;
            x = x->level[i].forward;
        }
        update[i] = x;  // 记录前驱节点
    }
    
    // 2. 随机生成层数
    int level = zslRandomLevel();
    if (level > zsl->level) {
        // 新层数超过当前最大层数
        for (int i = zsl->level; i < level; i++) {
            rank[i] = 0;
            update[i] = zsl->header;
            update[i]->level[i].span = zsl->length;
        }
        zsl->level = level;
    }
    
    // 3. 创建新节点
    x = zslCreateNode(level, score, ele);
    
    // 4. 插入各层，更新指针和span
    for (int i = 0; i < level; i++) {
        x->level[i].forward = update[i]->level[i].forward;
        update[i]->level[i].forward = x;
        
        // 更新span（用于计算排名）
        x->level[i].span = update[i]->level[i].span - (rank[0] - rank[i]);
        update[i]->level[i].span = (rank[0] - rank[i]) + 1;
    }
    
    // 5. 更新高层的span
    for (int i = level; i < zsl->level; i++) {
        update[i]->level[i].span++;
    }
    
    // 6. 更新后退指针
    x->backward = (update[0] == zsl->header) ? NULL : update[0];
    if (x->level[0].forward)
        x->level[0].forward->backward = x;
    else
        zsl->tail = x;
    
    zsl->length++;
    return x;
}
```

**时间复杂度**：平均O(log N)

---

#### 1.4 为什么同时使用跳表和哈希表？

**各自优势**：
```java
// 跳表：按score有序
ZRANGE rank 0 9            // O(log N + M)，支持范围查询
ZRANGEBYSCORE rank 90 100  // O(log N + M)

// 哈希表：快速查score
ZSCORE rank "player:1001"  // O(1)，直接查询
```

**内存代价**：
- 同一份数据存两份
- 但换来了性能提升（范围查询+快速查分）

---

### 2. Hash的底层实现与扩容

#### 2.1 Dict（字典）结构

```c
// 字典
typedef struct dict {
    dictht ht[2];           // 两个哈希表（用于渐进式rehash）
    long rehashidx;         // rehash进度（-1表示未进行）
    unsigned long iterators; // 当前运行的迭代器数量
} dict;

// 哈希表
typedef struct dictht {
    dictEntry **table;      // 哈希表数组
    unsigned long size;     // 桶数量（2^n）
    unsigned long sizemask; // 掩码（size - 1）
    unsigned long used;     // 已有节点数量
} dictht;

// 哈希节点
typedef struct dictEntry {
    void *key;
    void *val;
    struct dictEntry *next; // 链地址法解决冲突
} dictEntry;
```

---

#### 2.2 哈希算法

**计算索引**：
```c
// 1. 计算哈希值
hash = MurmurHash2(key, keylen, seed);

// 2. 计算桶索引
index = hash & sizemask;  // 等价于 hash % size
```

**MurmurHash2特点**：
- 速度快
- 分布均匀
- 雪崩效应好

---

#### 2.3 渐进式Rehash扩容机制

**触发条件**：

**扩容触发**：
```c
// 负载因子 = used / size
if (负载因子 >= 1 && 未在BGSAVE/BGREWRITEAOF) {
    扩容到 size * 2
}

if (负载因子 >= 5) {
    强制扩容（即使在BGSAVE）
}
```

**缩容触发**：
```c
if (负载因子 < 0.1) {
    缩容到第一个 >= used 的 2^n
}
```

---

#### 2.4 渐进式Rehash流程

**为什么需要渐进式？**
```java
// 假设有1000万个键
// 一次性rehash需要：
// 1. 分配新表（8MB -> 16MB）
// 2. 迁移1000万个键
// 3. 释放旧表
// 耗时：可能数百毫秒，阻塞Redis
```

**渐进式实现**：
```c
// 1. 分配ht[1]空间
ht[1].size = ht[0].size * 2;
ht[1].table = malloc(...);

// 2. 设置rehash标志
rehashidx = 0;

// 3. 每次增删改查时，迁移一个桶
void dictRehashStep(dict *d) {
    if (d->rehashidx == -1) return;
    
    // 迁移ht[0].table[rehashidx]上的所有键
    dictEntry *de = d->ht[0].table[d->rehashidx];
    while (de) {
        dictEntry *nextde = de->next;
        
        // 计算在ht[1]中的索引
        unsigned long h = dictHashKey(d, de->key) & d->ht[1].sizemask;
        de->next = d->ht[1].table[h];
        d->ht[1].table[h] = de;
        
        d->ht[0].used--;
        d->ht[1].used++;
        de = nextde;
    }
    d->ht[0].table[d->rehashidx] = NULL;
    d->rehashidx++;
    
    // 检查是否完成
    if (d->ht[0].used == 0) {
        free(d->ht[0].table);
        d->ht[0] = d->ht[1];
        _dictReset(&d->ht[1]);
        d->rehashidx = -1;
    }
}

// 4. 后台定时任务也会推进rehash
void databasesCron(void) {
    // 每次执行1ms内尽可能多迁移
    dictRehashMilliseconds(db->dict, 1);
}
```

---

#### 2.5 Rehash期间的操作策略

**查询**：
```c
// 先查ht[0]，未找到再查ht[1]
dictEntry *dictFind(dict *d, const void *key) {
    if (dictIsRehashing(d)) {
        _dictRehashStep(d);  // 顺便迁移一个桶
    }
    
    // 计算索引
    unsigned long h = dictHashKey(d, key);
    
    // 查找ht[0]
    for (dictEntry *he = d->ht[0].table[h & d->ht[0].sizemask]; 
         he != NULL; he = he->next) {
        if (key == he->key || dictCompareKeys(d, key, he->key))
            return he;
    }
    
    // 如果在rehash，还要查ht[1]
    if (dictIsRehashing(d)) {
        for (dictEntry *he = d->ht[1].table[h & d->ht[1].sizemask]; 
             he != NULL; he = he->next) {
            if (key == he->key || dictCompareKeys(d, key, he->key))
                return he;
        }
    }
    return NULL;
}
```

**新增**：
```c
// 直接插入ht[1]
dictEntry *dictAddRaw(dict *d, void *key) {
    if (dictIsRehashing(d)) {
        _dictRehashStep(d);
    }
    
    // 计算索引
    unsigned long index;
    dictht *ht = dictIsRehashing(d) ? &d->ht[1] : &d->ht[0];
    index = hash & ht->sizemask;
    
    // 插入链表头部
    dictEntry *entry = zmalloc(sizeof(*entry));
    entry->next = ht->table[index];
    ht->table[index] = entry;
    ht->used++;
    
    return entry;
}
```

**删除**：
```c
// 两个表都查找并删除
int dictDelete(dict *d, const void *key) {
    if (dictIsRehashing(d)) {
        _dictRehashStep(d);
    }
    
    // 在ht[0]和ht[1]中都尝试删除
    unsigned long h = dictHashKey(d, key);
    for (int table = 0; table <= 1; table++) {
        unsigned long idx = h & d->ht[table].sizemask;
        dictEntry *he = d->ht[table].table[idx];
        dictEntry *prevHe = NULL;
        
        while (he) {
            if (key == he->key || dictCompareKeys(d, key, he->key)) {
                // 找到了，删除
                if (prevHe)
                    prevHe->next = he->next;
                else
                    d->ht[table].table[idx] = he->next;
                
                dictFreeKey(d, he);
                dictFreeVal(d, he);
                zfree(he);
                d->ht[table].used--;
                return DICT_OK;
            }
            prevHe = he;
            he = he->next;
        }
        
        if (!dictIsRehashing(d)) break;
    }
    return DICT_ERR;
}
```

---

### 3. 为什么使用ZipList？

#### 3.1 ZipList的优势

**内存紧凑**：
```c
// LinkedList每个节点的开销
struct listNode {
    void *value;       // 8字节
    listNode *prev;    // 8字节
    listNode *next;    // 8字节
} // 总计24字节指针开销

// 存储100个小元素（每个1字节）
LinkedList: 100 * (24 + 1) = 2500字节

// ZipList: 紧凑存储
ZipList: 4(zlbytes) + 4(zltail) + 2(zllen) + 100 * 3(entry) + 1(zlend) 
       ≈ 311字节

内存节省：(2500 - 311) / 2500 = 87.6%
```

---

#### 3.2 缓存友好性

**连续内存 vs 离散内存**：
```
ZipList（连续）:
[entry1][entry2][entry3][entry4]...
↑ 一次可加载多个entry到CPU缓存

LinkedList（离散）:
[node1] -> [node2] -> [node3] -> [node4]
↑ 指针跳跃，缓存命中率低
```

---

#### 3.3 使用场景

**小对象场景**：
```bash
# List：元素少、单个元素小
LPUSH list "a" "b" "c"  # 3个小元素，用ZipList

# Hash：字段少、值小
HSET user:1001 name "Alice" age "25"  # 2个字段，用ZipList

# ZSet：元素少、元素小
ZADD rank 100 "player1" 95 "player2"  # 2个元素，用ZipList
```

**配置阈值**：
```bash
# List
list-max-ziplist-size -2  # 单个ZipList最大8KB

# Hash
hash-max-ziplist-entries 512
hash-max-ziplist-value 64

# ZSet
zset-max-ziplist-entries 128
zset-max-ziplist-value 64
```

---

#### 3.4 ZipList的缺点

**级联更新问题**：
```java
// ZipList: [entry1: 250字节][entry2: 250字节][entry3: 250字节]
// 每个entry的prevlen都是1字节（因为前一个<254字节）

// 插入一个260字节的元素到开头
[entry0: 260字节][entry1: 250字节][entry2: 250字节][entry3: 250字节]
//                 ↓ prevlen需从1字节扩展到5字节
//                                ↓ 后续所有entry都可能需要更新
```

**解决方案**：ListPack（Redis 7.0+）
```c
// ListPack: 不记录前一个entry的长度
entry = <encoding><data><len>  // len是自身长度
// 避免级联更新
```

---

### 4. 编码转换时机

#### 4.1 List的编码转换

**QuickList节点大小控制**：
```bash
# list-max-ziplist-size
-5: 64KB
-4: 32KB
-3: 16KB
-2: 8KB（默认）
-1: 4KB

# 超过限制会创建新QuickListNode
```

---

#### 4.2 Hash的编码转换

**ZipList -> HashTable**：
```bash
# 触发条件（满足任一）
1. 元素数量 > 512
2. 单个value大小 > 64字节

# 示例
HSET user:1001 name "Alice"  # 1个字段，用ZipList
HSET user:1001 field1 "v1" ... field600 "v600"  # 超过512，转HashTable
HSET user:1001 bio "很长的文本........................"  # 超过64字节，转HashTable
```

**Java观察**：
```java
// 查看编码
redisTemplate.execute((RedisCallback<String>) connection -> {
    return new String(connection.execute("OBJECT", "ENCODING", "user:1001".getBytes()));
});
```

---

#### 4.3 Set的编码转换

**IntSet -> HashTable**：
```bash
# 触发条件（满足任一）
1. 元素数量 > 512
2. 出现非整数元素

# 示例
SADD nums 1 2 3           # 3个整数，用IntSet
SADD nums 4 5 ... 600     # 超过512，转HashTable
SADD nums "hello"         # 出现非整数，转HashTable
```

---

#### 4.4 ZSet的编码转换

**ZipList -> SkipList**：
```bash
# 触发条件（满足任一）
1. 元素数量 > 128
2. 单个元素大小 > 64字节

# 示例
ZADD rank 100 "p1" 95 "p2"  # 2个元素，用ZipList
ZADD rank 90 "很长的名字........................"  # 超过64字节，转SkipList
```

---

### 5. 性能优化建议

#### 5.1 控制对象大小

**享受紧凑编码**：
```java
// 优化前：大Hash
Map<String, String> bigUser = new HashMap<>();
for (int i = 0; i < 1000; i++) {
    bigUser.put("field" + i, "value" + i);
}
redisTemplate.opsForHash().putAll("user:1001", bigUser);  // 1000个字段，HashTable

// 优化后：拆分小Hash
Map<String, String> basicInfo = new HashMap<>();
basicInfo.put("name", "Alice");
basicInfo.put("age", "25");
redisTemplate.opsForHash().putAll("user:1001:basic", basicInfo);  // 2个字段，ZipList

Map<String, String> extInfo = new HashMap<>();
extInfo.put("city", "Beijing");
redisTemplate.opsForHash().putAll("user:1001:ext", extInfo);  // ZipList
```

---

#### 5.2 避免大Value

**问题**：
```bash
HSET user:1001 profile "超过64字节的长文本........................"
# 触发转换为HashTable，内存占用增加
```

**优化**：
```bash
# 大文本单独存储
SET user:1001:profile "长文本........................"
HSET user:1001 name "Alice" age "25" profile_id "user:1001:profile"
# Hash保持ZipList编码
```

---

#### 5.3 监控编码变化

**脚本监控**：
```bash
# 批量检查编码
redis-cli --scan --pattern "user:*" | while read key; do
    encoding=$(redis-cli OBJECT ENCODING "$key")
    echo "$key: $encoding"
done
```

**Java监控**：
```java
@Scheduled(fixedRate = 60000)
public void monitorEncoding() {
    Set<String> keys = redisTemplate.keys("user:*");
    for (String key : keys) {
        String encoding = redisTemplate.execute((RedisCallback<String>) connection -> 
            new String(connection.execute("OBJECT", "ENCODING", key.getBytes()))
        );
        if ("hashtable".equals(encoding)) {
            log.warn("Key {} converted to hashtable", key);
        }
    }
}
```

---

### 6. 面试答题总结

**标准回答模板**：

> **跳表实现**：
> - 多层索引结构，每个节点随机1-32层（P=0.25，平均1.33层）
> - 配合哈希表使用：跳表支持范围查询，哈希表支持O(1)查score
> - 插入、删除、查找平均O(log N)
>
> **Hash扩容（渐进式rehash）**：
> - 触发条件：负载因子≥1（未BGSAVE）或≥5（强制）
> - 流程：分配ht[1]，设置rehashidx，每次操作迁移一个桶，后台定时推进
> - 期间策略：查询两个表，新增写ht[1]，删除两个表都查
>
> **为什么用ZipList**：
> - 内存紧凑：无指针开销，节省87%+内存
> - 缓存友好：连续内存，CPU缓存命中率高
> - 适合小对象：元素少且小时性能和内存都优
> - Redis 7.0+改用ListPack，解决级联更新问题

**常见追问**：
- **渐进式rehash为什么不一次性完成？** → 大表一次性迁移会阻塞Redis数百毫秒
- **rehash期间如何查询？** → 先查ht[0]，未找到再查ht[1]
- **ZipList的缺点？** → 级联更新问题，ListPack已解决
- **如何避免频繁编码转换？** → 控制元素数量和大小在阈值以下

