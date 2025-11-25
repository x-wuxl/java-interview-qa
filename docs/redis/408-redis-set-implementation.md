---
layout: default
title: "Redis的Set是如何实现的？"
parent: Redis
nav_order: 408
description: "深入解析Redis Set的底层实现，包括IntSet和HashTable的双重编码机制、集合运算优化及应用场景"
author: "wuxl"
date: 2025-11-02
---
## 问题

Redis的Set是如何实现的？

## 答案

### 1. 核心概念

Redis的Set是一个**无序、不重复**的字符串集合，支持高效的增删改查和集合运算（交集、并集、差集）。底层采用**双重编码机制**：全整数时使用IntSet，其他情况使用HashTable。

---

### 2. 双重编码机制

#### 2.1 编码切换条件

**配置参数**：
```bash
set-max-intset-entries 512  # IntSet最大元素数量
```

**编码选择**：
```java
if (所有元素都是整数 && 元素数量 <= 512) {
    使用 IntSet
} else {
    使用 HashTable
}
```

**查看编码**：
```bash
redis> SADD nums 1 2 3
redis> OBJECT ENCODING nums
"intset"

redis> SADD nums "hello"  # 添加非整数
redis> OBJECT ENCODING nums
"hashtable"  # 自动转换
```

---

### 3. IntSet实现（整数集合）

#### 3.1 结构设计

```c
typedef struct intset {
    uint32_t encoding;  // 编码类型
    uint32_t length;    // 元素数量
    int8_t contents[];  // 实际存储数组（柔性数组）
} intset;
```

**编码类型**：
```c
#define INTSET_ENC_INT16 (sizeof(int16_t))  // 2字节
#define INTSET_ENC_INT32 (sizeof(int32_t))  // 4字节
#define INTSET_ENC_INT64 (sizeof(int64_t))  // 8字节
```

---

#### 3.2 自动升级机制

**示例**：
```bash
# 初始状态：所有元素都是int16范围
SADD nums 1 2 3
# encoding = INTSET_ENC_INT16
# contents = [1, 2, 3]（每个2字节）

# 添加大整数
SADD nums 65536  # 超出int16范围
# 触发升级：
# encoding = INTSET_ENC_INT32
# contents = [1, 2, 3, 65536]（每个4字节）
```

**升级步骤**：
```java
1. 计算新编码类型（int32或int64）
2. 扩展contents数组（重新分配内存）
3. 将旧元素逐个转换为新编码并复制
4. 插入新元素
5. 更新encoding字段
```

**特点**：
- **只升级不降级**：即使删除大整数，编码也不会回退
- **有序存储**：内部按升序排列，支持二分查找

---

#### 3.3 优缺点

**优点**：
- **内存紧凑**：无指针开销，连续存储
- **缓存友好**：利用CPU缓存行
- **查找快**：二分查找，O(log N)

**缺点**：
- **插入慢**：需保持有序，O(N)移动元素
- **升级开销**：类型升级需重新分配内存

**示例**：
```c
// 查找元素（二分查找）
int intsetFind(intset *is, int64_t value) {
    // 1. 判断value是否在编码范围内
    if (value < _intsetMin(is) || value > _intsetMax(is)) {
        return 0; // 不存在
    }
    
    // 2. 二分查找
    int left = 0, right = is->length - 1;
    while (left <= right) {
        int mid = (left + right) / 2;
        int64_t cur = _intsetGet(is, mid);
        if (cur == value) return 1;
        else if (cur < value) left = mid + 1;
        else right = mid - 1;
    }
    return 0;
}
```

---

### 4. HashTable实现（哈希表编码）

#### 4.1 结构设计

**核心思想**：使用HashTable，**只用key，value为NULL**

```c
// 伪代码
HashTable {
    "element1": NULL,
    "element2": NULL,
    "element3": NULL
}
```

**实现原理**：
- 复用Hash的HashTable结构
- Key存储Set元素，Value固定为NULL
- 利用哈希表的去重特性和O(1)查找

---

#### 4.2 操作特性

```bash
# 添加元素
SADD myset "apple" "banana" "cherry"
# 内部：HashTable["apple"]=NULL, HashTable["banana"]=NULL, ...

# 判断存在
SISMEMBER myset "apple"
# 内部：查找HashTable是否存在"apple"这个key

# 随机获取
SRANDMEMBER myset
# 内部：随机返回一个key

# 删除元素
SREM myset "banana"
# 内部：删除HashTable中的"banana"键
```

---

### 5. 集合运算实现

#### 5.1 交集（SINTER）

**算法**：遍历最小集合，检查其他集合是否包含

```java
// 伪代码
Set<String> sinter(Set<String>... sets) {
    // 1. 找到最小集合
    Set<String> smallest = findSmallestSet(sets);
    
    // 2. 遍历最小集合
    Set<String> result = new HashSet<>();
    for (String element : smallest) {
        boolean existsInAll = true;
        for (Set<String> set : sets) {
            if (!set.contains(element)) {
                existsInAll = false;
                break;
            }
        }
        if (existsInAll) {
            result.add(element);
        }
    }
    return result;
}
```

**优化策略**：
```bash
# 两个集合：一个100万元素，一个10元素
SINTER bigset smallset

# Redis会自动选择遍历smallset（10次循环）
# 而不是遍历bigset（100万次循环）
```

---

#### 5.2 并集（SUNION）

**算法**：遍历所有集合，合并元素

```java
Set<String> sunion(Set<String>... sets) {
    Set<String> result = new HashSet<>();
    for (Set<String> set : sets) {
        result.addAll(set);  // HashSet自动去重
    }
    return result;
}
```

---

#### 5.3 差集（SDIFF）

**算法**：从第一个集合中移除其他集合的元素

```java
Set<String> sdiff(Set<String> first, Set<String>... others) {
    Set<String> result = new HashSet<>(first);
    for (Set<String> set : others) {
        result.removeAll(set);
    }
    return result;
}
```

---

### 6. 应用场景与最佳实践

#### 6.1 标签系统

```java
// 用户标签
SADD user:1001:tags "Java" "Redis" "分布式"
SADD user:1002:tags "Python" "Redis" "机器学习"

// 查找共同标签（交集）
SINTER user:1001:tags user:1002:tags
// 结果：["Redis"]

// 推荐系统：找到有相同标签的用户
SINTER tag:Redis:users tag:Java:users
```

**Java实现**：
```java
// 添加标签
redisTemplate.opsForSet().add("user:1001:tags", "Java", "Redis", "分布式");

// 获取共同标签
Set<String> commonTags = redisTemplate.opsForSet()
    .intersect("user:1001:tags", "user:1002:tags");
```

---

#### 6.2 好友关系

```java
// 用户A的关注列表
SADD following:A "B" "C" "D"
// 用户B的关注列表
SADD following:B "A" "C" "E"

// 共同关注（交集）
SINTER following:A following:B
// 结果：["C"]

// A关注但B不关注（差集）
SDIFF following:A following:B
// 结果：["D"]

// 可能认识的人（B的关注 - A已关注）
SDIFF following:B following:A
// 结果：["E"]
```

---

#### 6.3 唯一性去重

```java
// 统计网站独立访客（UV）
SADD uv:2024-11-02 "user:1001" "user:1002" "user:1001"
// 自动去重

// 获取UV数量
SCARD uv:2024-11-02
// 结果：2
```

**优化**：大量UV数据使用HyperLogLog更省内存
```bash
PFADD uv:2024-11-02 "user:1001" "user:1002"
PFCOUNT uv:2024-11-02  # 近似统计
```

---

#### 6.4 抽奖系统

```java
// 参与抽奖的用户
SADD lottery:1001 "user:1001" "user:1002" ... "user:10000"

// 抽取3个中奖用户（不重复）
SPOP lottery:1001 3
// 结果：["user:3344", "user:7788", "user:1122"]
// SPOP会移除元素，确保不重复中奖

// 或使用SRANDMEMBER（不移除）
SRANDMEMBER lottery:1001 3
```

---

### 7. 性能优化建议

#### 7.1 IntSet优化
- **整数场景**：ID、标签ID等尽量使用整数
- **控制数量**：保持在512以下享受IntSet的内存优势

```bash
# 优化前：字符串ID
SADD user:tags "tag_1001" "tag_1002"  # 使用HashTable

# 优化后：整数ID
SADD user:tags 1001 1002  # 使用IntSet
```

---

#### 7.2 避免大Set
- **问题**：百万级Set的集合运算会阻塞Redis
- **解决**：
  - 拆分为多个小Set
  - 使用Scan命令分批获取：`SSCAN key 0 COUNT 100`
  - 集合运算考虑在应用层完成

---

#### 7.3 集合运算优化
```bash
# 不推荐：每次都计算
SINTER set1 set2 set3  # 实时计算

# 推荐：预计算并缓存
SINTERSTORE result set1 set2 set3  # 结果存储到result
EXPIRE result 3600  # 缓存1小时
```

---

### 8. 面试答题总结

**标准回答模板**：

> Redis的Set采用**双重编码**机制：
> 1. **IntSet编码**：当所有元素都是整数且数量≤512时使用，有序存储，支持自动升级（int16→int32→int64），内存紧凑，查找O(log N)
> 2. **HashTable编码**：其他情况使用，只用key存元素（value为NULL），查找O(1)
>
> Set支持高效的集合运算，交集运算会自动选择最小集合遍历，优化性能。

**常见追问**：
- **IntSet的升级机制？** → 添加大整数时自动升级到更大编码，只升级不降级
- **为什么IntSet有序？** → 支持二分查找，提升查找效率
- **集合运算如何优化？** → 交集选择最小集合遍历，大Set考虑预计算或应用层计算
- **Set和List的区别？** → Set无序不重复，List有序可重复；Set支持集合运算

