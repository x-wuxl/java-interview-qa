---
layout: post
title: "MySQL是如何保证唯一性索引的唯一性的？"
date: 2025-11-02
categories: [MySQL, 索引]
tags: [MySQL, 唯一索引, 并发控制, 锁机制]
description: "深入解析MySQL唯一索引的实现原理，包括插入检查机制、锁协议、并发控制等关键技术点"
---

## 一、核心概念

**唯一性索引（Unique Index）** 用于保证列值的唯一性约束。MySQL通过**插入前检查 + 行锁机制**确保即使在高并发场景下，也不会出现重复值。

核心保障机制：
1. **插入前唯一性检查**
2. **Next-Key Lock防止幻读**
3. **Insert Intention Lock优化并发**

## 二、实现原理

### 1. 插入流程与锁机制

```sql
CREATE TABLE user (
    id INT PRIMARY KEY,
    email VARCHAR(100) UNIQUE KEY
);

-- 并发插入相同email
INSERT INTO user VALUES (1, 'test@example.com');
INSERT INTO user VALUES (2, 'test@example.com'); -- 会被阻塞/失败
```

**完整流程（InnoDB）**：

#### 阶段1：唯一性检查
```
1. 事务A执行 INSERT
2. 在唯一索引树上搜索 'test@example.com'
3. 如果找到记录：
   - 若记录未删除 → 抛出 Duplicate key error
   - 若记录标记删除 → 加 Next-Key Lock
4. 如果未找到 → 继续执行插入
```

#### 阶段2：加锁协议（RC隔离级别）
```
事务A: INSERT 'test@example.com'
  ↓
  对唯一索引加 【Insert Intention Lock】（插入意向锁）
  ↓
  检查是否有冲突的锁
  ↓
  插入记录并对新记录加 【Record Lock】
```

#### 阶段3：锁冲突处理（RR隔离级别）
```
时刻T1: 事务A插入 'aaa@example.com'
        → 在索引区间 (NULL, 'aaa@example.com'] 加 Next-Key Lock

时刻T2: 事务B插入 'aaa@example.com'
        → 尝试获取 Insert Intention Lock
        → 与事务A的 Next-Key Lock 冲突
        → 进入等待状态

时刻T3: 事务A提交
        → 释放锁
        → 事务B获取锁并检查唯一性
        → 发现重复，抛出错误
```

### 2. 锁类型详解

| 锁类型 | 作用 | 加锁时机 |
|--------|------|----------|
| **Record Lock** | 锁定具体记录 | 检查到已存在记录时 |
| **Gap Lock** | 锁定索引间隙 | RR隔离级别，防止幻读 |
| **Next-Key Lock** | Record Lock + Gap Lock | 唯一索引查询+范围锁定 |
| **Insert Intention Lock** | 插入意向锁 | 插入新记录前 |

### 3. 不同隔离级别的行为差异

#### READ COMMITTED（RC）
```sql
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 会话1
BEGIN;
INSERT INTO user VALUES (1, 'test@example.com');

-- 会话2（立即执行）
INSERT INTO user VALUES (2, 'test@example.com');
-- 立即返回错误：Duplicate entry 'test@example.com' for key 'email'
```
**特点**：只对存在的记录加锁，不加Gap Lock，检查更快。

#### REPEATABLE READ（RR）
```sql
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- 会话1
BEGIN;
INSERT INTO user VALUES (1, 'test@example.com');

-- 会话2（立即执行）
INSERT INTO user VALUES (2, 'test@example.com');
-- 阻塞等待，直到会话1提交或回滚
```
**特点**：加Next-Key Lock防止幻读，会话2必须等待会话1提交。

## 三、并发场景实战

### 场景1：高并发插入相同值

```java
// 100个线程同时插入相同email
ExecutorService executor = Executors.newFixedThreadPool(100);
CountDownLatch latch = new CountDownLatch(100);

for (int i = 0; i < 100; i++) {
    final int userId = i;
    executor.submit(() -> {
        try {
            // 所有线程尝试插入相同email
            jdbcTemplate.update(
                "INSERT INTO user (id, email) VALUES (?, ?)",
                userId, "same@example.com"
            );
        } catch (DuplicateKeyException e) {
            // 预期行为：99个失败
            System.out.println("重复插入被拒绝");
        } finally {
            latch.countDown();
        }
    });
}

latch.await();
// 结果：只有1条记录插入成功
```

**保证机制**：
1. 第一个事务插入成功，对该记录加Record Lock
2. 后续99个事务检查时发现记录已存在，直接抛出异常
3. 整个过程无需应用层额外控制

### 场景2：DELETE后立即INSERT

```sql
-- 会话1
BEGIN;
DELETE FROM user WHERE email = 'test@example.com';
-- 此时记录被标记删除，但锁未释放

-- 会话2
INSERT INTO user VALUES (999, 'test@example.com');
-- 会阻塞等待会话1提交
```

**原理**：
- 删除的记录依然持有锁（标记删除）
- 插入时会检查到该记录并等待锁释放
- 避免了"幻读"问题

### 场景3：REPLACE INTO的特殊处理

```sql
REPLACE INTO user VALUES (1, 'test@example.com');
-- 等价于：
-- 1. 检查唯一索引
-- 2. 若存在，先DELETE旧记录
-- 3. 再INSERT新记录
```

```java
// 内部执行流程
public void replaceInto(User user) {
    // 1. 尝试插入
    try {
        insert(user);
    } catch (DuplicateKeyException e) {
        // 2. 插入失败，执行替换逻辑
        delete(user.getEmail()); // 加排他锁
        insert(user);            // 重新插入
    }
}
```

## 四、源码级原理（简化）

### InnoDB唯一性检查伪代码
```cpp
// row_ins_scan_sec_index_for_duplicate
dberr_t check_duplicate_for_unique_index(index, entry) {
    // 1. 在B+树中搜索目标值
    cursor = btr_cur_search_to_nth_level(index, entry);
    
    // 2. 检查是否找到相同值
    if (cursor->found_record()) {
        rec = cursor->get_record();
        
        // 3. 检查记录状态
        if (!rec->is_deleted()) {
            // 记录存在且未删除 → 返回重复错误
            return DB_DUPLICATE_KEY;
        } else {
            // 记录已删除 → 加Next-Key Lock防止并发问题
            lock_rec_lock(LOCK_X | LOCK_ORDINARY, rec);
        }
    }
    
    // 4. 未找到重复 → 加Insert Intention Lock
    lock_rec_insert_intention_lock(gap_before_insert);
    
    return DB_SUCCESS;
}
```

### 关键数据结构
```cpp
// 索引记录格式
struct rec_t {
    trx_id_t trx_id;        // 创建该记录的事务ID
    roll_ptr_t roll_ptr;    // 回滚指针
    byte deleted_flag;      // 删除标记
    byte[] key_values;      // 索引键值
    byte[] primary_key;     // 主键值（二级索引）
};

// 锁信息
struct lock_t {
    ulint type;             // LOCK_REC / LOCK_TABLE
    ulint mode;             // LOCK_S / LOCK_X / LOCK_GAP...
    hash_node_t hash;       // 锁哈希表节点
    trx_t* trx;             // 持有锁的事务
};
```

## 五、性能优化建议

### 1. 选择合适的隔离级别
```sql
-- 高并发写入场景，优先使用RC
SET GLOBAL transaction_isolation = 'READ-COMMITTED';
```
**优势**：减少Gap Lock，降低锁冲突，提升并发性能。

### 2. 使用批量插入减少检查次数
```sql
-- 差：逐条插入（每次都检查唯一性）
INSERT INTO user VALUES (1, 'a@example.com');
INSERT INTO user VALUES (2, 'b@example.com');

-- 优：批量插入（MySQL会优化检查）
INSERT INTO user VALUES 
(1, 'a@example.com'),
(2, 'b@example.com'),
(3, 'c@example.com');
```

### 3. INSERT IGNORE避免异常处理
```java
// 差：捕获异常性能开销大
try {
    jdbcTemplate.update("INSERT INTO user VALUES (?, ?)", id, email);
} catch (DuplicateKeyException e) {
    // 异常处理
}

// 优：使用INSERT IGNORE
jdbcTemplate.update("INSERT IGNORE INTO user VALUES (?, ?)", id, email);
int affectedRows = ...; // 通过影响行数判断是否插入成功
```

## 六、答题总结

**面试回答模板**：

1. **机制概述**：  
   "MySQL通过在B+树索引上执行插入前检查，结合InnoDB的行锁机制保证唯一性"

2. **核心流程**：  
   "插入时先在唯一索引上搜索，若找到未删除记录直接返回错误；若未找到则加Insert Intention Lock后插入，并对新记录加Record Lock"

3. **并发保证**：  
   "在RR隔离级别下使用Next-Key Lock防止幻读；在RC级别下仅锁定记录本身，性能更高"

4. **实战经验**：  
   "生产环境建议使用RC隔离级别减少锁冲突，对于用户注册等场景可用INSERT IGNORE简化异常处理"

**关键点**：
- 理解锁的类型（Record/Gap/Next-Key/Insert Intention）
- 掌握不同隔离级别的行为差异
- 能说出完整的插入检查流程
- 了解性能优化方向（隔离级别、批量插入）

