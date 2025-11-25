---
title: "InnoDB加索引会锁表吗？"
date: 2025-11-02
description: "深入分析InnoDB添加索引时的锁机制，包括不同MySQL版本的行为差异、MDL锁原理以及如何避免锁表影响业务"
author: "wuxl"
categories: [数据库]
tags: [MySQL, InnoDB, 索引, 锁机制, OnlineDDL]
nav_order: 336
parent: 数据库MySQL
---
## 问题

InnoDB加索引，这个时候会锁表吗?

## 答案

### 核心结论

**取决于MySQL版本和使用的DDL方式：**
- **MySQL 5.6之前**：会**长时间锁表**，阻塞所有DML操作
- **MySQL 5.6+（Online DDL）**：只在**开始和结束时短暂锁表**，其余时间不锁表
- **MySQL 8.0+**：进一步优化，某些操作甚至无需锁表

### 详细分析

#### 1. MySQL 5.5及更早版本：全程锁表

**执行方式：**
```sql
ALTER TABLE users ADD INDEX idx_age(age);
```

**锁表行为：**
```
1. 加表级写锁（Table Lock）
   ↓
2. 创建临时表，按新结构
   ↓
3. 逐行复制数据到临时表（耗时长）
   期间：所有DML操作被阻塞
   ↓
4. 重命名表，删除原表
   ↓
5. 释放锁
```

**影响：**
- 大表添加索引可能耗时数小时
- **全程阻塞业务**写入，导致服务不可用
- 生产环境基本不可用

#### 2. MySQL 5.6+：Online DDL（短暂锁表）

**执行方式：**
```sql
ALTER TABLE users ADD INDEX idx_age(age),
ALGORITHM=INPLACE, LOCK=NONE;
```

**锁表行为：**
```
阶段1：准备阶段
  - 加 MDL写锁（Metadata Lock，约1ms）
  - 初始化Online DDL结构
  - 降级为 MDL读锁

阶段2：执行阶段（主要耗时）
  - 持有 MDL读锁
  - 允许并发DML操作（SELECT、INSERT、UPDATE、DELETE）
  - 扫描主键索引，构建新索引
  - 将并发DML记录到 row log 缓冲区

阶段3：提交阶段
  - 升级为 MDL写锁（约数十ms）
  - 应用 row log 中的增量变更
  - 完成索引构建
  - 释放锁
```

**关键点：**
- **MDL读锁**：允许DML操作，仅阻止其他DDL操作
- **MDL写锁**：阻止所有DML和DDL，但仅持有极短时间
- **不锁表**的真正含义：大部分时间允许业务正常读写

**示例时间线：**
```
00:00:00.000  加MDL写锁
00:00:00.001  降级为MDL读锁
00:00:00.001  开始构建索引（业务正常运行）
00:01:30.000  索引构建完成
00:01:30.000  升级为MDL写锁
00:01:30.050  应用row log增量
00:01:30.050  释放锁，完成

总耗时：90秒
锁表时间：约51ms（0.001s + 0.050s）
```

#### 3. MDL锁的作用

**为什么需要MDL锁？**
- 保护**表结构**在DDL期间不被其他会话修改
- 保证DDL操作的**原子性**

**MDL锁的类型：**
```sql
-- MDL读锁（SHARED_READ）：允许DML，阻止DDL
SELECT * FROM users;  -- 加MDL读锁
INSERT INTO users VALUES (...);  -- 加MDL读锁

-- MDL写锁（EXCLUSIVE）：阻止所有DML和DDL
ALTER TABLE users ADD INDEX idx_age(age);  -- 开始和结束时加MDL写锁
```

**查看MDL锁：**
```sql
-- MySQL 8.0
SELECT OBJECT_SCHEMA, OBJECT_NAME, LOCK_TYPE, LOCK_STATUS, OWNER_THREAD_ID
FROM performance_schema.metadata_locks
WHERE OBJECT_SCHEMA = 'test';

-- 输出示例
+---------------+-------------+-----------+-------------+-----------------+
| OBJECT_SCHEMA | OBJECT_NAME | LOCK_TYPE | LOCK_STATUS | OWNER_THREAD_ID |
+---------------+-------------+-----------+-------------+-----------------+
| test          | users       | SHARED_NO_READ_WRITE |  GRANTED  | 48   |
+---------------+-------------+-----------+-------------+-----------------+
```

#### 4. 不同索引操作的锁表情况

| 操作 | 锁表时间 | 并发DML | 说明 |
|-----|---------|---------|-----|
| 添加普通索引 | 短暂（ms级） | 允许 | INPLACE算法 |
| 添加唯一索引 | 短暂（ms级） | 允许 | INPLACE算法 |
| 添加全文索引 | 短暂（ms级） | 允许 | INPLACE算法 |
| 删除索引 | 短暂（ms级） | 允许 | INPLACE算法 |
| 添加主键 | 较长 | 部分允许 | 需重建表 |
| 删除主键 | 较长 | 阻塞 | 需重建表，COPY算法 |

**示例：添加唯一索引**
```sql
ALTER TABLE orders ADD UNIQUE INDEX uk_order_no(order_no),
ALGORITHM=INPLACE, LOCK=NONE;

-- 执行期间允许：
INSERT INTO orders VALUES (...);  -- 成功
UPDATE orders SET status = 1 WHERE id = 100;  -- 成功

-- 但如果插入重复值：
INSERT INTO orders VALUES (..., 'ORDER_001', ...);  -- 成功
INSERT INTO orders VALUES (..., 'ORDER_001', ...);  -- 等待DDL完成后报错
```

### 实际场景分析

#### 场景1：低峰期添加索引
```sql
-- 凌晨2点执行
ALTER TABLE orders ADD INDEX idx_user_id(user_id);

-- 表现：
-- 1. 短暂阻塞（ms级）：大部分请求不会感知
-- 2. 长时间执行（分钟级）：但业务正常运行
-- 3. 磁盘IO升高：构建索引需要读取数据
```

#### 场景2：高峰期添加索引
```sql
-- 中午12点执行
ALTER TABLE orders ADD INDEX idx_create_time(create_time);

-- 风险：
-- 1. MDL写锁等待：如果有长事务持有MDL读锁，升级MDL写锁会等待
-- 2. row log溢出：高并发DML可能导致row log缓冲区不足
-- 3. 主从延迟：DDL在从库重放时也会耗时

-- 建议：设置超时保护
SET SESSION lock_wait_timeout = 5;
```

#### 场景3：有长事务阻塞DDL
```sql
-- 会话1：长事务（忘记提交）
BEGIN;
SELECT * FROM users WHERE id = 1;
-- 未提交，持有MDL读锁

-- 会话2：尝试添加索引
ALTER TABLE users ADD INDEX idx_age(age);
-- 等待会话1释放MDL读锁（阻塞）

-- 会话3：普通查询
SELECT * FROM users WHERE id = 2;
-- 也被阻塞（排在会话2之后）
```

**排查方法：**
```sql
-- 查看等待MDL锁的会话
SELECT * FROM sys.schema_table_lock_waits;

-- 杀掉长事务
KILL 12345;  -- 会话1的thread_id
```

### 避免锁表影响的最佳实践

#### 1. 使用Online DDL显式指定
```sql
-- 明确指定INPLACE和LOCK=NONE
ALTER TABLE users ADD INDEX idx_email(email),
ALGORITHM=INPLACE, LOCK=NONE;

-- 如果不支持Online DDL，会报错而不是降级为COPY
-- ERROR 1846: LOCK=NONE is not supported. Reason: ...
```

#### 2. 使用pt-online-schema-change
```bash
pt-online-schema-change \
  --alter "ADD INDEX idx_age(age)" \
  --max-load="Threads_running=50" \
  --critical-load="Threads_running=100" \
  --execute \
  D=mydb,t=users
```

**优势：**
- 分批复制数据，避免长时间持有锁
- 自动控制负载，业务影响更小
- 可随时暂停、恢复

#### 3. 低峰期执行
```sql
-- 定时任务，凌晨执行
# crontab
0 2 * * * mysql -e "ALTER TABLE mydb.users ADD INDEX idx_age(age)" >> /var/log/ddl.log 2>&1
```

#### 4. 监控和告警
```sql
-- 监控长时间DDL
SELECT * FROM information_schema.PROCESSLIST
WHERE Command = 'Query' AND Time > 60 AND Info LIKE 'ALTER%';

-- 监控MDL等待
SELECT OBJECT_NAME, LOCK_TYPE, LOCK_DURATION, LOCK_STATUS
FROM performance_schema.metadata_locks
WHERE LOCK_STATUS = 'PENDING';
```

### 面试答题总结

InnoDB添加索引**在MySQL 5.6+版本不会长时间锁表**。通过**Online DDL机制**，仅在开始和结束时短暂持有**MDL写锁**（毫秒级），大部分时间持有**MDL读锁**，允许并发DML操作。具体流程是：**短暂加MDL写锁 → 降级为MDL读锁并构建索引 → 升级为MDL写锁应用增量 → 释放锁**。需注意长事务可能阻塞MDL锁升级，生产环境建议使用`ALGORITHM=INPLACE, LOCK=NONE`显式指定，或使用pt-osc工具在低峰期执行。
