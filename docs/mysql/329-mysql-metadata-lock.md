---
layout: default
title: "什么是MySQL的元数据锁（MDL锁）？"
parent: 数据库MySQL
nav_order: 329
description: "深入解析MySQL元数据锁的机制、作用、锁类型以及常见的死锁问题和排查方法"
author: "wuxl"
date: 2025-11-02
---
## 问题

什么是MySQL的元数据锁（字典锁）？

## 答案

### 核心概念

**元数据锁（Metadata Lock，简称MDL锁）**是MySQL用于保护表结构定义的锁机制，在MySQL 5.5.3引入。它确保在**读写数据期间表结构不被修改**，防止出现数据不一致。

### 为什么需要MDL锁？

#### 没有MDL锁的问题场景

**假设没有MDL保护：**
```sql
-- 会话1：查询用户表
SELECT id, name, age FROM users WHERE id = 1;

-- 会话2：同时删除age列
ALTER TABLE users DROP COLUMN age;

-- 结果：会话1的查询会出错（age列不存在）
-- 或返回脏数据（结构与数据不匹配）
```

**MDL锁的作用：**
- 保证**表结构的稳定性**：读写数据时，表结构不会被修改
- 保证DDL的**原子性**：表结构变更要么全部成功，要么全部失败
- 防止**数据与元数据不一致**

### MDL锁的工作原理

#### 自动加锁机制

MDL锁**无需显式加锁**，由MySQL自动管理：
```sql
-- DML操作：自动加MDL读锁
SELECT * FROM users;          -- 加MDL_SHARED_READ
INSERT INTO users VALUES (...); -- 加MDL_SHARED_WRITE
UPDATE users SET age = 20;     -- 加MDL_SHARED_WRITE
DELETE FROM users WHERE id = 1; -- 加MDL_SHARED_WRITE

-- DDL操作：自动加MDL写锁
ALTER TABLE users ADD COLUMN status INT;  -- 加MDL_EXCLUSIVE
DROP TABLE users;                         -- 加MDL_EXCLUSIVE
```

#### 锁的释放时机

MDL锁的生命周期与**事务或语句**绑定：
```sql
-- 显式事务：事务提交或回滚时释放
BEGIN;
SELECT * FROM users WHERE id = 1;  -- 加MDL读锁
-- MDL读锁持续到COMMIT或ROLLBACK
COMMIT;  -- 释放MDL锁

-- 自动提交：语句执行完立即释放
SELECT * FROM users WHERE id = 1;  -- 加锁并立即释放
```

### MDL锁的类型和兼容性

#### 锁类型层次

```
MDL锁类型（从宽松到严格）：
1. MDL_SHARED_READ (SR)      - 读操作
2. MDL_SHARED_WRITE (SW)     - 写操作
3. MDL_SHARED_UPGRADABLE (SU) - 可升级的共享锁
4. MDL_SHARED_NO_WRITE (SNW) - 允许读，禁止写
5. MDL_SHARED_NO_READ_WRITE (SNRW) - 禁止读写
6. MDL_EXCLUSIVE (X)         - 排他锁（DDL操作）
```

#### 兼容性矩阵

|  持有锁 ↓ \ 请求锁 →  | SR | SW | SU | SNW | SNRW | X |
|---------------------|----|----|----|----|------|---|
| MDL_SHARED_READ     | ✓  | ✓  | ✓  | ✓  | ✗    | ✗ |
| MDL_SHARED_WRITE    | ✓  | ✓  | ✓  | ✗  | ✗    | ✗ |
| MDL_SHARED_UPGRADABLE| ✓  | ✓  | ✗  | ✗  | ✗    | ✗ |
| MDL_SHARED_NO_WRITE | ✓  | ✗  | ✗  | ✗  | ✗    | ✗ |
| MDL_SHARED_NO_READ_WRITE | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| MDL_EXCLUSIVE       | ✗  | ✗  | ✗  | ✗  | ✗    | ✗ |

**关键规则：**
- **MDL读锁之间兼容**：多个SELECT可以并发
- **MDL读锁与写锁兼容**：SELECT和DML可以并发
- **MDL写锁（EXCLUSIVE）与所有锁不兼容**：DDL独占

### 常见的MDL锁阻塞场景

#### 场景1：长事务阻塞DDL

```sql
-- 会话1：开启事务后忘记提交（持有MDL读锁）
BEGIN;
SELECT * FROM users WHERE id = 1;
-- 未提交，MDL_SHARED_READ持续持有

-- 会话2：尝试添加列（需要MDL写锁）
ALTER TABLE users ADD COLUMN status INT;
-- 等待会话1释放MDL读锁（阻塞）

-- 会话3：普通查询
SELECT * FROM users WHERE id = 2;
-- 也被阻塞（排在会话2之后，等待MDL读锁）
```

**示意图：**
```
会话1: [MDL_SHARED_READ 持有中...]
会话2:                    [等待 MDL_EXCLUSIVE]
会话3:                                      [等待 MDL_SHARED_READ]
```

#### 场景2：DDL阻塞后续所有操作

```sql
-- 会话1：DDL执行中（持有MDL写锁）
ALTER TABLE orders ADD INDEX idx_user_id(user_id);
-- 执行耗时5分钟

-- 会话2-100：业务查询
SELECT * FROM orders WHERE id = 1000;
-- 全部被阻塞，等待会话1释放MDL写锁

-- 影响：业务大面积不可用
```

#### 场景3：表锁与MDL锁冲突

```sql
-- 会话1：显式加表锁
LOCK TABLES users WRITE;
SELECT * FROM users;

-- 会话2：任何操作都被阻塞
SELECT * FROM users WHERE id = 1;  -- 阻塞
ALTER TABLE users ADD INDEX idx_age(age);  -- 阻塞

-- 解决：释放表锁
UNLOCK TABLES;
```

### MDL锁的查看和排查

#### 1. 查看MDL锁等待（MySQL 5.7+）
```sql
-- 查看正在等待的MDL锁
SELECT * FROM sys.schema_table_lock_waits;

-- 输出示例
+---------------+-------------+-------------------+-----------------+
| object_schema | object_name | waiting_thread_id | blocking_thread_id |
+---------------+-------------+-------------------+-----------------+
| mydb          | users       | 45                | 38              |
+---------------+-------------+-------------------+-----------------+
```

#### 2. 查看MDL锁持有情况（MySQL 8.0+）
```sql
SELECT
  OBJECT_SCHEMA,
  OBJECT_NAME,
  LOCK_TYPE,
  LOCK_STATUS,
  OWNER_THREAD_ID,
  OWNER_EVENT_ID
FROM performance_schema.metadata_locks
WHERE OBJECT_SCHEMA = 'mydb';

-- 输出示例
+---------------+-------------+-------------------+-------------+-----------------+
| OBJECT_SCHEMA | OBJECT_NAME | LOCK_TYPE         | LOCK_STATUS | OWNER_THREAD_ID |
+---------------+-------------+-------------------+-------------+-----------------+
| mydb          | users       | SHARED_READ       | GRANTED     | 38              |
| mydb          | users       | EXCLUSIVE         | PENDING     | 45              |
+---------------+-------------+-------------------+-------------+-----------------+
```

#### 3. 查看长时间持有MDL锁的事务
```sql
SELECT
  p.id,
  p.user,
  p.host,
  p.db,
  p.command,
  p.time,
  p.state,
  p.info,
  t.trx_started,
  t.trx_rows_locked,
  t.trx_rows_modified
FROM information_schema.PROCESSLIST p
LEFT JOIN information_schema.INNODB_TRX t ON p.id = t.trx_mysql_thread_id
WHERE t.trx_started < DATE_SUB(NOW(), INTERVAL 60 SECOND)
ORDER BY t.trx_started;

-- 找出持续超过60秒的事务
```

#### 4. 杀掉阻塞会话
```sql
-- 根据thread_id杀掉阻塞的会话
KILL 38;  -- 杀掉持有MDL锁的会话
```

### 避免MDL锁问题的最佳实践

#### 1. 避免长事务
```java
// 不好的做法：事务范围过大
@Transactional
public void processUsers() {
    List<User> users = userMapper.selectAll();  // 加MDL读锁
    // 复杂业务逻辑处理（耗时长）
    for (User user : users) {
        processComplexLogic(user);
    }
    // MDL锁持有时间过长
}

// 推荐做法：缩小事务范围
public void processUsers() {
    List<User> users = userMapper.selectAll();
    for (User user : users) {
        processInTransaction(user);  // 每个用户一个小事务
    }
}

@Transactional
public void processInTransaction(User user) {
    // 事务范围小，MDL锁快速释放
    userMapper.update(user);
}
```

#### 2. DDL前检查活跃事务
```sql
-- 检查是否有长事务
SELECT * FROM information_schema.INNODB_TRX
WHERE TIME_TO_SEC(TIMEDIFF(NOW(), trx_started)) > 10;

-- 确认无长事务后再执行DDL
ALTER TABLE users ADD INDEX idx_age(age);
```

#### 3. 设置锁等待超时
```sql
-- 会话级别设置
SET SESSION lock_wait_timeout = 5;  -- 5秒超时

-- 全局设置（生产环境谨慎）
SET GLOBAL lock_wait_timeout = 10;
```

#### 4. 使用Online DDL工具
```bash
# pt-online-schema-change避免MDL锁问题
pt-online-schema-change \
  --alter "ADD INDEX idx_age(age)" \
  --max-load="Threads_running=50" \
  --critical-load="Threads_running=100" \
  --chunk-size=1000 \
  --execute \
  D=mydb,t=users
```

#### 5. 低峰期执行DDL
```sql
-- 定时任务在凌晨执行DDL
# crontab -e
0 3 * * * /usr/local/bin/ddl_script.sh
```

### 监控和告警

```sql
-- 监控MDL锁等待数量
SELECT COUNT(*) AS mdl_wait_count
FROM performance_schema.metadata_locks
WHERE LOCK_STATUS = 'PENDING';

-- 告警阈值：> 10
-- 触发告警：发送通知给DBA

-- 监控长时间DDL
SELECT
  id,
  time,
  info
FROM information_schema.PROCESSLIST
WHERE command = 'Query'
  AND info LIKE 'ALTER%'
  AND time > 300;  -- 超过5分钟
```

### 面试答题总结

MySQL的**元数据锁（MDL锁）**用于保护表结构，在MySQL 5.5.3引入。DML操作自动加**MDL读锁**（允许并发），DDL操作自动加**MDL写锁**（独占）。MDL锁在事务提交或语句完成时释放。常见问题是**长事务持有MDL读锁，导致DDL阻塞，进而阻塞后续所有操作**，形成连锁反应。排查通过`sys.schema_table_lock_waits`或`performance_schema.metadata_locks`视图。避免方法包括：缩小事务范围、DDL前检查活跃事务、设置锁等待超时、使用pt-osc工具、低峰期执行DDL。
