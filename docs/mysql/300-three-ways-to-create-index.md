---
layout: default
title: "创建索引的三种方式"
parent: 数据库MySQL
nav_order: 300
description: 详解 MySQL 中创建索引的三种方式（CREATE INDEX、ALTER TABLE、CREATE TABLE）及其区别与适用场景。
---
## 1. 核心概念

在 MySQL 中，索引是提高查询效率的重要数据结构。创建索引本质上是在存储引擎层构建 B+ 树（或其他类型索引）结构，并将其与表数据关联。合理创建索引可以大幅减少扫描行数，提升查询性能。

## 2. 创建方式与原理

MySQL 提供了三种主要的创建索引方式，它们在语法和适用场景上略有不同。

### 2.1 使用 `CREATE INDEX` 语句

这是最基础的创建普通索引或唯一索引的方式，但**不能用于创建主键索引**。

```sql
-- 创建普通索引
CREATE INDEX idx_username ON users(username);

-- 创建唯一索引
CREATE UNIQUE INDEX idx_email ON users(email);
```

### 2.2 使用 `ALTER TABLE` 语句

这是最常用的方式，功能比 `CREATE INDEX` 更强大，支持创建包括主键在内的所有类型索引。

```sql
-- 添加主键索引
ALTER TABLE users ADD PRIMARY KEY (id);

-- 添加普通索引
ALTER TABLE users ADD INDEX idx_username (username);

-- 添加唯一索引
ALTER TABLE users ADD UNIQUE INDEX idx_email (email);

-- 添加全文索引
ALTER TABLE articles ADD FULLTEXT INDEX idx_content (content);
```

### 2.3 建表时定义 (`CREATE TABLE`)

在设计表结构时直接指定索引，这是最推荐的初始化方式。

```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT,
    username VARCHAR(50),
    email VARCHAR(100),
    PRIMARY KEY (id),
    INDEX idx_username (username),
    UNIQUE INDEX idx_email (email)
);
```

## 3. 关键区别与考量

### 3.1 功能差异
- **CREATE INDEX**：是 `ALTER TABLE` 的一个语法糖，但在底层实现上，它无法处理主键（PRIMARY KEY）。
- **ALTER TABLE**：更加灵活，可以同时添加多个索引，修改列定义等。在底层执行时，MySQL 通常会将 `CREATE INDEX` 映射为 `ALTER TABLE` 操作。

### 3.2 性能与生产环境考量 (Online DDL)
在 MySQL 5.6 之前，创建索引会锁表（Table Lock），导致业务不可写。
从 MySQL 5.6 开始，引入了 **Online DDL** 特性，允许在创建索引期间不阻塞 DML 操作（增删改）。

**生产环境最佳实践：**
```sql
-- 显式指定算法和锁策略，确保不锁表
ALTER TABLE users ADD INDEX idx_age (age), ALGORITHM=INPLACE, LOCK=NONE;
```
- **ALGORITHM=INPLACE**：不需要重建整张表，直接在原表空间进行修改（部分操作仍需重建，但不需要拷贝数据到临时表）。
- **LOCK=NONE**：允许并发读写。

## 4. 总结

| 方式 | 语法关键字 | 主键支持 | 多索引支持 | 适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **CREATE INDEX** | `CREATE INDEX` | ❌ | ❌ (单条语句只能建一个) | 后期补充普通/唯一索引 |
| **ALTER TABLE** | `ADD INDEX` | ✅ | ✅ | 维护表结构、添加主键、批量添加索引 |
| **CREATE TABLE** | `INDEX`/`KEY` | ✅ | ✅ | 表结构初始化设计 |

**面试回答示例：**
"MySQL 创建索引主要有三种方式：一是建表时直接定义；二是使用 `ALTER TABLE`，它功能最全，支持主键；三是 `CREATE INDEX`，它不能建主键。在生产环境中，我们主要关注 Online DDL，尽量使用 `ALGORITHM=INPLACE, LOCK=NONE` 来避免长时间锁表影响业务。"
