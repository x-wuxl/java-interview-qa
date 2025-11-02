---
layout: post
title: "InnoDB的页分裂和页合并机制"
date: 2025-11-02
description: "深入理解InnoDB B+树索引中的页分裂和页合并原理、触发条件以及对性能的影响"
author: "wuxl"
categories: [数据库]
tags: [MySQL, InnoDB, 页分裂, 页合并, B+树, 性能优化]
---

## 问题

什么是InnoDB的页分裂和页合并？

## 答案

### 1. 核心概念

**页分裂（Page Split）** 和 **页合并（Page Merge）** 是InnoDB在维护B+树索引结构时的两种关键操作，用于应对数据页的动态变化。

- **页分裂**：当数据页已满无法插入新记录时，将一个页拆分成两个页
- **页合并**：当相邻的两个页数据量过少时，合并成一个页

### 2. 页分裂（Page Split）

#### 2.1 触发条件
当向一个 **已满的数据页**（通常是填充率超过15/16，即15KB左右）插入新记录时，就会触发页分裂。

#### 2.2 分裂过程

假设向主键索引插入记录，页已满：

```
分裂前：
页1: [1][2][3][4][5][6]...[50] ← 已满（16KB）
         ↓ 插入记录30
分裂后：
页1: [1][2][3]...[25]         ← 保留前半部分
页2: [26][27]...[50]          ← 后半部分移到新页
```

**详细步骤**：
1. **申请新页**：从表空间中分配一个新的数据页
2. **记录移动**：将原页的部分记录移动到新页
3. **更新索引**：修改非叶子节点的指针，指向新页
4. **更新链表**：维护叶子节点之间的双向链表指针

#### 2.3 三种分裂情况

**情况1：顺序插入（最优）**
```
插入记录比当前页所有记录都大：
页1: [1][2]...[100]
           ↓ 插入101
页1: [1][2]...[100]      ← 原页不变
页2: [101]               ← 新页只有新记录
```
- **性能影响小**：原页100%利用率，新页从头开始

**情况2：随机插入（最差）**
```
插入记录在页中间：
页1: [1][2][3]...[50]
        ↓ 插入25
页1: [1][2]...[24]       ← 保留50%
页2: [25][26]...[50]     ← 移动50%
```
- **性能影响大**：两个页各50%利用率，产生碎片

**情况3：反向插入**
```
插入记录比当前页所有记录都小：
页1: [100][101]...[200]
    ↓ 插入99
页2: [99]                ← 新页
页1: [100][101]...[200]  ← 原页不变
```

#### 2.4 页分裂的代价

**性能影响**：
- **额外的I/O操作**：读取旧页、写入新页、更新索引页
- **锁争用**：分裂期间需要对页加排他锁
- **碎片化**：随机插入导致页利用率低，浪费存储空间

**监控页分裂**：
```sql
-- 查看页分裂次数
SHOW GLOBAL STATUS LIKE 'Innodb_page_splits';
```

### 3. 页合并（Page Merge）

#### 3.1 触发条件
当 **删除记录** 或 **更新导致记录变小** 时，如果页的填充率低于某个阈值（通常是50%），且相邻页可以合并，就会触发页合并。

#### 3.2 合并过程

```
合并前：
页1: [1][2][3]           ← 填充率30%
页2: [4][5][6]           ← 填充率30%
         ↓
合并后：
页1: [1][2][3][4][5][6]  ← 填充率60%
页2: (释放)
```

**详细步骤**：
1. **检查相邻页**：判断前后页是否可以合并（总记录数能否放入一个页）
2. **移动记录**：将一个页的记录移动到另一个页
3. **释放空页**：将空闲页加入Free链表
4. **更新索引**：修改非叶子节点的指针

#### 3.3 合并的阈值

```sql
-- 合并阈值由参数控制（默认50%）
innodb_merge_threshold_set_all_debug = 50
```

- 当页的填充率低于 **MERGE_THRESHOLD**（默认50%）时，尝试合并
- 避免频繁合并和分裂的循环

### 4. 页分裂与页合并的影响对比

| 操作 | 触发场景 | 性能影响 | 空间影响 | 优化建议 |
|------|---------|---------|---------|---------|
| 页分裂 | 插入记录到已满页 | I/O增加、锁争用 | 产生碎片、利用率降低 | 使用自增主键、批量插入 |
| 页合并 | 删除记录导致页过空 | I/O增加、锁争用 | 回收空间、提高利用率 | 定期OPTIMIZE TABLE |

### 5. 性能优化建议

#### 5.1 避免页分裂

**1. 使用自增主键**
```sql
-- 推荐：自增主键顺序插入
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100)
);

-- 不推荐：UUID随机插入
CREATE TABLE users (
    id CHAR(36) PRIMARY KEY,  -- UUID导致随机分裂
    name VARCHAR(100)
);
```

**2. 预留空间**
- InnoDB默认保留页的1/16空间用于后续更新
- 避免页刚好满的情况下更新导致分裂

**3. 批量插入**
```sql
-- 推荐：批量插入
INSERT INTO users (name) VALUES
    ('Alice'), ('Bob'), ('Charlie');

-- 不推荐：逐条插入
INSERT INTO users (name) VALUES ('Alice');
INSERT INTO users (name) VALUES ('Bob');
```

#### 5.2 处理页合并

**1. 定期重建索引**
```sql
-- 优化表，重建索引，消除碎片
OPTIMIZE TABLE users;

-- 或者重建索引
ALTER TABLE users ENGINE=InnoDB;
```

**2. 监控碎片率**
```sql
-- 查看表的碎片情况
SELECT
    table_name,
    data_length,           -- 数据大小
    index_length,          -- 索引大小
    data_free,             -- 碎片空间
    data_free / (data_length + index_length) AS frag_ratio
FROM information_schema.tables
WHERE table_schema = 'your_database'
ORDER BY frag_ratio DESC;
```

#### 5.3 索引设计建议

**1. 主键选择**
- **优先使用自增主键**：顺序插入，避免分裂
- **避免随机主键**：UUID、无序字符串导致频繁分裂

**2. 二级索引优化**
- 避免在频繁更新的列上建索引
- 考虑使用前缀索引减少索引大小

### 6. 实战示例

#### 6.1 观察页分裂
```sql
-- 查看页分裂次数
SHOW GLOBAL STATUS LIKE 'Innodb_page_splits';

-- 执行大量随机插入
INSERT INTO test_table SELECT UUID(), RAND() FROM seq_1_to_100000;

-- 再次查看页分裂次数（会显著增加）
SHOW GLOBAL STATUS LIKE 'Innodb_page_splits';
```

#### 6.2 对比自增主键 vs UUID

```sql
-- 自增主键：页分裂少
CREATE TABLE test_auto (id BIGINT AUTO_INCREMENT PRIMARY KEY, data VARCHAR(100));
INSERT INTO test_auto (data) SELECT UUID() FROM seq_1_to_100000;

-- UUID主键：页分裂多
CREATE TABLE test_uuid (id CHAR(36) PRIMARY KEY, data VARCHAR(100));
INSERT INTO test_uuid SELECT UUID(), UUID() FROM seq_1_to_100000;

-- 对比存储空间和碎片率
SELECT table_name, data_length, data_free
FROM information_schema.tables
WHERE table_name IN ('test_auto', 'test_uuid');
```

### 7. 总结

**页分裂**：
- 插入数据到已满页时触发，将页拆分成两个
- **顺序插入性能最优**，随机插入导致频繁分裂和碎片
- 使用 **自增主键** 可以最大程度避免页分裂

**页合并**：
- 删除数据导致页利用率低于50%时触发
- 回收空间，但也会增加I/O
- 定期 **OPTIMIZE TABLE** 可以消除碎片

**核心原则**：
- **索引设计要考虑数据插入模式**
- **监控页分裂和碎片率**，及时优化
- **自增主键是最佳实践**

**面试要点**：能清晰说明页分裂的三种情况、页合并的触发条件、以及如何通过自增主键避免页分裂。
