---
title: "什么是OnlineDDL"
date: 2025-11-02
description: "详解MySQL的OnlineDDL机制，包括实现原理、算法类型、操作分类以及生产环境使用注意事项"
author: "wuxl"
categories: [数据库]
tags: [MySQL, OnlineDDL, DDL, 索引优化]
nav_order: 383
parent: 数据库MySQL
---
## 问题

什么是OnlineDDL？

## 答案

### 核心概念

**Online DDL**是MySQL 5.6引入的特性，允许在执行DDL操作（如加索引、修改列）时**不阻塞DML操作**（INSERT、UPDATE、DELETE），实现表结构变更期间业务的正常读写。

### 传统DDL的问题

**MySQL 5.6之前：**
```sql
ALTER TABLE users ADD INDEX idx_age(age);
```

执行过程：
1. 创建临时表，按新结构定义
2. 将原表数据**逐行复制**到临时表
3. 复制期间**锁表**，禁止DML操作
4. 替换原表

**问题：**
- **长时间锁表**：大表添加索引可能耗时数小时
- **业务中断**：锁表期间无法写入，导致业务不可用
- **双倍存储**：临时表占用额外磁盘空间

### Online DDL的改进

**核心思想：** 通过**增量日志**记录DDL期间的DML操作，最后合并应用，避免长时间锁表。

**执行流程：**
```
1. 加MDL读锁（Metadata Lock）
   ↓
2. 升级为MDL写锁（短暂）
   ↓
3. 降级为MDL读锁
   ↓
4. 执行DDL操作（如构建索引）
   同时记录DML操作到 row log
   ↓
5. 升级为MDL写锁（短暂）
   ↓
6. 应用row log中的增量DML
   ↓
7. 释放MDL锁，完成DDL
```

**关键点：**
- 大部分时间持有**MDL读锁**，允许DML并发执行
- 仅在**开始和结束时短暂持有MDL写锁**，阻塞DML
- 使用**row log**记录DDL期间的数据变更

### Online DDL的算法

MySQL支持三种DDL算法：

#### 1. COPY算法（传统方式）
```sql
ALTER TABLE users ADD COLUMN status INT,
ALGORITHM=COPY;
```
- 创建临时表，复制数据
- **全程锁表**，不允许DML
- 适用于所有DDL操作

#### 2. INPLACE算法（Online DDL）
```sql
ALTER TABLE users ADD INDEX idx_age(age),
ALGORITHM=INPLACE, LOCK=NONE;
```
- **不创建临时表**，原地修改
- 允许并发DML（取决于LOCK级别）
- 适用于大多数索引操作

#### 3. INSTANT算法（MySQL 8.0+）
```sql
ALTER TABLE users ADD COLUMN status INT DEFAULT 0,
ALGORITHM=INSTANT;
```
- **仅修改元数据**，不改数据文件
- **秒级完成**，无论表多大
- 仅适用于特定操作（如末尾加列、修改默认值）

### LOCK级别控制

通过`LOCK`子句控制DDL期间的并发行为：

```sql
-- 1. LOCK=NONE：允许并发读写（最优）
ALTER TABLE users ADD INDEX idx_age(age), LOCK=NONE;

-- 2. LOCK=SHARED：允许并发读，禁止写
ALTER TABLE users MODIFY COLUMN name VARCHAR(100), LOCK=SHARED;

-- 3. LOCK=EXCLUSIVE：禁止并发读写（等同于传统DDL）
ALTER TABLE users ADD COLUMN status INT, LOCK=EXCLUSIVE;

-- 4. LOCK=DEFAULT：由MySQL自动选择最宽松的锁级别
ALTER TABLE users ADD INDEX idx_email(email), LOCK=DEFAULT;
```

### 常见DDL操作分类

| DDL操作 | 算法支持 | 锁级别 | 是否重建表 |
|--------|---------|-------|-----------|
| 添加索引 | INPLACE | NONE | 否 |
| 删除索引 | INPLACE | NONE | 否 |
| 添加列（末尾） | INSTANT | NONE | 否（8.0） |
| 删除列 | INPLACE | EXCLUSIVE | 是 |
| 修改列类型 | COPY | EXCLUSIVE | 是 |
| 修改列默认值 | INSTANT | NONE | 否 |
| 添加主键 | INPLACE | EXCLUSIVE | 是 |
| 删除主键 | COPY | EXCLUSIVE | 是 |
| 修改字符集 | COPY | EXCLUSIVE | 是 |
| OPTIMIZE TABLE | INPLACE | NONE | 是 |

### 示例说明

#### 示例1：添加索引（INPLACE + NONE）
```sql
-- 表有1000万行数据
ALTER TABLE orders ADD INDEX idx_user_id(user_id),
ALGORITHM=INPLACE, LOCK=NONE;

-- 执行过程：
-- 1. 扫描主键索引，构建新索引（可能耗时数分钟）
-- 2. 同时允许INSERT、UPDATE、DELETE操作
-- 3. row log记录增量变更
-- 4. 最后合并row log，短暂阻塞（毫秒级）
```

#### 示例2：添加列（INSTANT）
```sql
-- MySQL 8.0+
ALTER TABLE users ADD COLUMN last_login DATETIME DEFAULT NULL,
ALGORITHM=INSTANT;

-- 执行过程：
-- 1. 仅修改表的元数据（.frm文件）
-- 2. 不修改数据文件（.ibd）
-- 3. 秒级完成，业务无感知
```

#### 示例3：修改列类型（COPY）
```sql
-- 扩大VARCHAR长度
ALTER TABLE users MODIFY COLUMN name VARCHAR(200),
ALGORITHM=COPY, LOCK=EXCLUSIVE;

-- 执行过程：
-- 1. 创建临时表
-- 2. 复制全表数据（耗时长，锁表）
-- 3. 替换原表
```

### 生产环境最佳实践

#### 1. 使用pt-online-schema-change工具
```bash
# Percona Toolkit工具，实现更平滑的Online DDL
pt-online-schema-change \
  --alter "ADD INDEX idx_age(age)" \
  --execute \
  D=test,t=users

# 原理：
# 1. 创建影子表（新结构）
# 2. 创建触发器同步数据
# 3. 分批复制数据
# 4. 最后原子切换表
```

#### 2. 控制执行时间窗口
```sql
-- 低峰期执行DDL
ALTER TABLE orders ADD INDEX idx_create_time(create_time),
ALGORITHM=INPLACE, LOCK=NONE;

-- 监控执行进度
SHOW PROCESSLIST;
-- 查看State字段：altering table、committing
```

#### 3. 设置超时保护
```sql
-- 防止MDL写锁等待时间过长
SET SESSION lock_wait_timeout = 5;  -- 5秒超时

ALTER TABLE users ADD INDEX idx_email(email);
```

#### 4. 分批次执行
```sql
-- 不好的做法：一次性多个DDL
ALTER TABLE users
  ADD INDEX idx_age(age),
  ADD INDEX idx_email(email),
  ADD COLUMN status INT;

-- 推荐做法：拆分执行，观察影响
ALTER TABLE users ADD INDEX idx_age(age);
-- 观察业务指标，确认无影响后继续
ALTER TABLE users ADD INDEX idx_email(email);
```

### 注意事项

1. **磁盘空间**：INPLACE算法虽不创建临时表，但构建索引仍需额外空间（约原表大小）
2. **主从延迟**：DDL在主库执行完后，从库也要重放，可能加剧延迟
3. **外键约束**：有外键的表DDL可能退化为COPY算法
4. **版本差异**：MySQL 5.6/5.7/8.0的Online DDL能力逐步增强
5. **row log大小**：DDL期间DML过多，row log可能占满tmpdir

### 监控与排查

```sql
-- 查看当前DDL进度（MySQL 8.0+）
SELECT * FROM performance_schema.events_stages_current
WHERE EVENT_NAME LIKE 'stage/innodb/alter%';

-- 查看MDL锁等待
SELECT * FROM performance_schema.metadata_locks
WHERE OBJECT_SCHEMA = 'test' AND OBJECT_NAME = 'users';

-- 查看临时文件使用
SHOW VARIABLES LIKE 'innodb_tmpdir';
```

### 面试答题总结

Online DDL是MySQL 5.6+提供的**不锁表执行DDL**的能力，通过**INPLACE算法**和**row log增量日志**，允许DDL期间并发执行DML操作。核心是仅在开始和结束时短暂持有MDL写锁，大部分时间持有MDL读锁。支持三种算法：**COPY（全表复制）、INPLACE（原地修改）、INSTANT（元数据修改）**。生产环境建议使用`ALGORITHM=INPLACE, LOCK=NONE`，配合pt-osc工具，在低峰期执行，监控磁盘空间和主从延迟。
