---
layout: post
title: "什么是跳表？为什么用跳表？"
date: 2025-11-02
description: "深入解析跳表（SkipList）的数据结构原理、查找插入删除算法、与红黑树的对比及Redis为什么选择跳表"
author: "wuxl"
categories: [中间件]
tags: [Redis, 跳表, SkipList, 数据结构, 算法]
---

## 问题

什么是跳表？为什么用跳表？

## 答案

### 1. 核心概念

**跳表（Skip List）**是一种**基于有序链表的多层索引结构**，通过"跳跃"方式加速查找，实现了类似平衡树的性能（平均O(log N)），但实现更简单。Redis的ZSet就是基于跳表实现的。

---

### 2. 跳表的演进思想

#### 2.1 从有序链表开始

**问题**：有序链表查找慢，O(N)
```
1 -> 3 -> 5 -> 7 -> 9 -> 11 -> 13 -> 15
查找13：需要遍历8个节点
```

---

#### 2.2 添加一层索引

**优化**：每隔一个节点提取一个作为上层索引
```
L2: 1 --------> 5 --------> 9 ---------> 13
L1: 1 -> 3 -> 5 -> 7 -> 9 -> 11 -> 13 -> 15

查找13：
1. L2: 1 -> 5 -> 9 -> 13（3次跳跃）
2. 找到目标，无需下到L1
```

**效果**：查找次数从8降到3

---

#### 2.3 添加多层索引

**继续优化**：逐层提取索引
```
L3: 1 -----------------> 9
L2: 1 --------> 5 --------> 9 ---------> 13
L1: 1 -> 3 -> 5 -> 7 -> 9 -> 11 -> 13 -> 15

查找13：
1. L3: 1 -> 9（1次跳跃）
2. L2: 9 -> 13（1次跳跃）
3. 找到目标，共2次
```

**时间复杂度**：理想情况O(log N)

---

### 3. 跳表的结构设计

#### 3.1 节点结构

```c
// 跳表节点
typedef struct zskiplistNode {
    sds ele;                    // 元素值
    double score;               // 分数（排序依据）
    struct zskiplistNode *backward; // 后退指针（支持反向遍历）
    
    struct zskiplistLevel {
        struct zskiplistNode *forward;  // 前进指针
        unsigned long span;             // 跨度（到下个节点的距离）
    } level[];                  // 层级数组（柔性数组）
} zskiplistNode;

// 跳表结构
typedef struct zskiplist {
    struct zskiplistNode *header;  // 头节点
    struct zskiplistNode *tail;    // 尾节点
    unsigned long length;          // 节点数量
    int level;                     // 当前最大层数
} zskiplist;
```

---

#### 3.2 完整示例

**跳表示意图**（4层）：
```
header
  L4: [NULL] --------------------------------> [node4:100] -> NULL
                span=4

  L3: [NULL] ----------------> [node3:80] --> [node4:100] -> NULL
                span=3             span=1

  L2: [NULL] ------> [node2:60] -> [node3:80] -> [node4:100] -> NULL
                span=2    span=1       span=1

  L1: [NULL] -> [node1:50] -> [node2:60] -> [node3:80] -> [node4:100] -> NULL
         span=1    span=1       span=1         span=1

每个节点的level数组：
node1: level[1] (只有1层)
node2: level[1,2] (2层)
node3: level[1,2,3] (3层)
node4: level[1,2,3,4] (4层)
```

**span字段作用**：用于计算排名
```bash
# 计算node3的排名
从header到node3经过的span总和：3 + 0 = 3
排名 = 3（从0开始是第3位）
```

---

### 4. 跳表的核心算法

#### 4.1 随机层数生成

**Redis的实现**：
```c
#define ZSKIPLIST_MAXLEVEL 32   // 最大层数
#define ZSKIPLIST_P 0.25        // 晋升概率

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
2层：25%
3层：6.25%
4层：1.56%
5层：0.39%
...

平均层数 = 1/(1-P) = 1/0.75 ≈ 1.33
```

**为什么P=0.25？**
- 太大（如0.5）：索引层占用内存多
- 太小（如0.1）：索引效果不明显
- 0.25是经验值，平衡内存和性能

---

#### 4.2 查找算法

```java
Node search(double targetScore) {
    Node current = header;
    
    // 从最高层开始
    for (int i = currentLevel; i >= 1; i--) {
        // 在当前层向右移动
        while (current.level[i].forward != null 
               && current.level[i].forward.score < targetScore) {
            current = current.level[i].forward;
        }
        // 下降到下一层
    }
    
    // 到达第1层，获取目标节点
    current = current.level[1].forward;
    
    if (current != null && current.score == targetScore) {
        return current;
    }
    return null;
}
```

**时间复杂度**：平均O(log N)，最坏O(N)

---

#### 4.3 插入算法

```java
void insert(double score, String element) {
    Node[] update = new Node[MAXLEVEL];  // 记录每层的前驱节点
    int[] rank = new int[MAXLEVEL];      // 记录每层的排名
    
    // 1. 查找插入位置
    Node current = header;
    for (int i = currentLevel; i >= 1; i--) {
        rank[i] = (i == currentLevel) ? 0 : rank[i+1];
        
        while (current.level[i].forward != null 
               && current.level[i].forward.score < score) {
            rank[i] += current.level[i].span;
            current = current.level[i].forward;
        }
        update[i] = current;  // 记录前驱
    }
    
    // 2. 随机生成层数
    int newLevel = randomLevel();
    if (newLevel > currentLevel) {
        for (int i = currentLevel + 1; i <= newLevel; i++) {
            rank[i] = 0;
            update[i] = header;
            update[i].level[i].span = length;
        }
        currentLevel = newLevel;
    }
    
    // 3. 创建新节点
    Node newNode = new Node(score, element, newLevel);
    
    // 4. 插入各层，更新指针和span
    for (int i = 1; i <= newLevel; i++) {
        newNode.level[i].forward = update[i].level[i].forward;
        update[i].level[i].forward = newNode;
        
        // 更新span
        newNode.level[i].span = update[i].level[i].span - (rank[1] - rank[i]);
        update[i].level[i].span = (rank[1] - rank[i]) + 1;
    }
    
    // 5. 更新高层的span
    for (int i = newLevel + 1; i <= currentLevel; i++) {
        update[i].level[i].span++;
    }
    
    // 6. 更新后退指针
    newNode.backward = (update[1] == header) ? null : update[1];
}
```

**时间复杂度**：平均O(log N)

---

#### 4.4 删除算法

```java
void delete(double score, String element) {
    Node[] update = new Node[MAXLEVEL];
    
    // 1. 查找节点
    Node current = header;
    for (int i = currentLevel; i >= 1; i--) {
        while (current.level[i].forward != null 
               && (current.level[i].forward.score < score 
                   || (current.level[i].forward.score == score 
                       && current.level[i].forward.element.compareTo(element) < 0))) {
            current = current.level[i].forward;
        }
        update[i] = current;
    }
    
    current = current.level[1].forward;
    if (current != null && current.score == score && current.element.equals(element)) {
        // 2. 删除节点（更新各层指针）
        for (int i = 1; i <= currentLevel; i++) {
            if (update[i].level[i].forward == current) {
                update[i].level[i].span += current.level[i].span - 1;
                update[i].level[i].forward = current.level[i].forward;
            } else {
                update[i].level[i].span--;
            }
        }
        
        // 3. 更新后退指针
        if (current.level[1].forward != null) {
            current.level[1].forward.backward = current.backward;
        }
        
        // 4. 更新最大层数
        while (currentLevel > 1 && header.level[currentLevel].forward == null) {
            currentLevel--;
        }
    }
}
```

**时间复杂度**：平均O(log N)

---

### 5. 跳表 vs 红黑树

| 特性 | 跳表 | 红黑树 |
|------|------|--------|
| **查找** | O(log N) | O(log N) |
| **插入** | O(log N) | O(log N) |
| **删除** | O(log N) | O(log N) |
| **范围查询** | 顺序遍历，简单高效 | 需中序遍历，复杂 |
| **实现复杂度** | 简单（约200行） | 复杂（需处理旋转、变色） |
| **内存占用** | 额外1.33倍指针 | 额外1倍指针+颜色位 |
| **缓存友好性** | 差（指针跳跃） | 差（指针跳跃） |
| **并发性** | 易实现无锁化 | 困难 |

---

### 6. Redis为什么选择跳表？

#### 6.1 实现简单

**跳表**：核心代码约200行
```c
// 主要函数
zslCreate()      // 创建
zslInsert()      // 插入
zslDelete()      // 删除
zslFirstInRange() // 范围查询
```

**红黑树**：需处理复杂的旋转和变色逻辑
```c
// 需要实现
leftRotate()     // 左旋
rightRotate()    // 右旋
insertFixup()    // 插入后修复
deleteFixup()    // 删除后修复
// 代码量500+行，且难以理解和调试
```

---

#### 6.2 范围查询友好

**跳表**：
```bash
ZRANGE rank 0 9  # 获取前10名

# 实现：找到起始节点后，沿着第1层forward指针顺序遍历即可
```

**红黑树**：
```java
// 需要中序遍历
void inorderTraversal(Node root) {
    if (root == null) return;
    inorderTraversal(root.left);
    visit(root);
    inorderTraversal(root.right);
}
// 需要递归或栈，且代码复杂
```

---

#### 6.3 支持反向遍历

**跳表**：通过backward指针
```bash
ZREVRANGE rank 0 9  # 倒序获取前10名

# 从tail开始，沿着backward指针反向遍历
```

**红黑树**：需要额外的父指针或栈

---

#### 6.4 灵活的概率平衡

**跳表**：
- 插入删除时只需更新局部节点
- 概率平衡，无需全局调整

**红黑树**：
- 插入删除可能触发多次旋转
- 影响范围不可控

---

#### 6.5 易于调试和维护

**跳表**：
```bash
# 可视化简单
L3: 1 -> 9 -> NULL
L2: 1 -> 5 -> 9 -> 13 -> NULL
L1: 1 -> 3 -> 5 -> 7 -> 9 -> 11 -> 13 -> 15 -> NULL
```

**红黑树**：
```
      (B)7
     /    \
   (R)3   (R)11
   / \     /  \
 (B)1 (B)5 (B)9 (B)13
```
需检查颜色、旋转状态，调试困难

---

### 7. 跳表的优缺点

#### 7.1 优点
- **实现简单**：核心逻辑清晰，易于理解和实现
- **性能稳定**：平均O(log N)，最坏O(N)但概率极低
- **范围查询**：天然支持，性能优秀
- **并发友好**：易实现无锁化（ConcurrentSkipListMap）
- **内存可控**：通过调整P值平衡内存和性能

#### 7.2 缺点
- **内存开销**：额外1.33倍指针（平均）
- **缓存不友好**：指针跳跃访问，不如数组连续
- **不严格平衡**：概率保证，极端情况性能退化

---

### 8. 面试答题总结

**标准回答模板**：

> **跳表**是一种基于有序链表的多层索引结构，通过"跳跃"加速查找：
> 1. **原理**：在有序链表上构建多层索引，每层节点是下一层的子集，查找时从高层开始逐层下降
> 2. **性能**：查找、插入、删除平均O(log N)，通过随机层数（概率P=0.25）实现概率平衡
> 3. **Redis选择跳表的原因**：
>    - 实现简单（约200行代码）
>    - 范围查询友好（顺序遍历第1层）
>    - 支持反向遍历（backward指针）
>    - 易于调试和维护
> 4. **相比红黑树**：性能相当但实现简单得多，适合Redis的应用场景

**常见追问**：
- **跳表的层数如何确定？** → 随机生成，每层晋升概率25%，平均1.33层
- **为什么不用红黑树？** → 实现复杂，范围查询需中序遍历，调试困难
- **跳表的时间复杂度？** → 平均O(log N)，最坏O(N)但概率极低
- **跳表的空间复杂度？** → O(N)，额外1/(1-P) ≈ 1.33倍指针

