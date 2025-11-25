---
layout: default
title: "唯一索引和主键索引的区别？"
parent: 数据库MySQL
nav_order: 281
description: "深入对比主键索引和唯一索引的区别，包括约束、唯一性、NULL值处理、存储结构、性能差异和使用场景。"
date: 2025-11-02
---
## 一、核心区别概览

| 特性 | 主键索引 (PRIMARY KEY) | 唯一索引 (UNIQUE INDEX) |
|------|----------------------|------------------------|
| **唯一性** | ✅ 必须唯一 | ✅ 必须唯一 |
| **NULL值** | ❌ 不允许 | ✅ 允许（可以有多个NULL） |
| **数量限制** | 一张表只能有1个 | 一张表可以有多个 |
| **索引类型** | 聚簇索引（InnoDB） | 二级索引 |
| **自动创建** | 定义主键时自动创建 | 定义UNIQUE时自动创建 |
| **可删除** | ❌ 不能删除 | ✅ 可以删除 |
| **性能** | 最快（无需回表） | 需要回表（非覆盖索引时） |
| **业务含义** | 唯一标识，逻辑主键 | 业务唯一约束 |

## 二、定义和创建

### 1. 主键索引

```sql
-- 方式1：建表时定义
CREATE TABLE users (
    id BIGINT PRIMARY KEY,  -- 主键
    email VARCHAR(100),
    name VARCHAR(50)
) ENGINE=InnoDB;

-- 方式2：单独定义
CREATE TABLE orders (
    id BIGINT,
    order_no VARCHAR(32),
    user_id BIGINT,
    PRIMARY KEY (id)
);

-- 方式3：复合主键
CREATE TABLE order_items (
    order_id BIGINT,
    product_id BIGINT,
    quantity INT,
    PRIMARY KEY (order_id, product_id)  -- 复合主键
);

-- 方式4：建表后添加（不推荐，影响性能）
ALTER TABLE logs ADD PRIMARY KEY (id);
```

**主键约束**：

```sql
-- 1. 非空约束
INSERT INTO users (id, name) VALUES (NULL, '张三');  
-- ❌ ERROR: Column 'id' cannot be null

-- 2. 唯一性约束
INSERT INTO users (id, name) VALUES (1, '张三');  -- ✅
INSERT INTO users (id, name) VALUES (1, '李四');  
-- ❌ ERROR: Duplicate entry '1' for key 'PRIMARY'

-- 3. 只能有一个主键
ALTER TABLE users ADD PRIMARY KEY (email);
-- ❌ ERROR: Multiple primary key defined
```

### 2. 唯一索引

```sql
-- 方式1：建表时定义
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(100) UNIQUE,  -- 唯一索引
    phone VARCHAR(20),
    name VARCHAR(50)
) ENGINE=InnoDB;

-- 方式2：单独定义
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    sku VARCHAR(50),
    name VARCHAR(200),
    UNIQUE KEY uk_sku (sku)  -- 唯一索引
);

-- 方式3：建表后添加
ALTER TABLE users ADD UNIQUE INDEX uk_phone (phone);

-- 或
CREATE UNIQUE INDEX uk_email ON users(email);

-- 方式4：复合唯一索引
CREATE TABLE user_roles (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    role_id BIGINT,
    UNIQUE KEY uk_user_role (user_id, role_id)  -- 复合唯一索引
);
```

**唯一索引约束**：

```sql
-- 1. 允许NULL
INSERT INTO users (id, email, name) VALUES (1, NULL, '张三');  -- ✅
INSERT INTO users (id, email, name) VALUES (2, NULL, '李四');  -- ✅ 允许多个NULL

-- 2. 非NULL值必须唯一
INSERT INTO users (id, email, name) VALUES (3, 'zhang@a.com', '王五');  -- ✅
INSERT INTO users (id, email, name) VALUES (4, 'zhang@a.com', '赵六');  
-- ❌ ERROR: Duplicate entry 'zhang@a.com' for key 'uk_email'

-- 3. 可以有多个唯一索引
ALTER TABLE users ADD UNIQUE INDEX uk_phone (phone);     -- ✅
ALTER TABLE users ADD UNIQUE INDEX uk_id_card (id_card); -- ✅
```

## 三、NULL值处理

### 主键索引：不允许NULL

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    name VARCHAR(50)
);

-- ❌ 不允许NULL
INSERT INTO users (id, name) VALUES (NULL, '张三');
-- ERROR: Column 'id' cannot be null

-- 原因：
-- 1. 主键用于唯一标识一行
-- 2. NULL表示未知，无法唯一标识
-- 3. SQL标准规定主键不能为NULL
```

### 唯一索引：允许多个NULL

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(100) UNIQUE
);

-- ✅ 允许多个NULL
INSERT INTO users (id, email) VALUES (1, NULL);  -- ✅
INSERT INTO users (id, email) VALUES (2, NULL);  -- ✅
INSERT INTO users (id, email) VALUES (3, NULL);  -- ✅

-- 查询结果
SELECT * FROM users;
+----+-------+
| id | email |
+----+-------+
|  1 | NULL  |
|  2 | NULL  |
|  3 | NULL  |
+----+-------+

-- ✅ 非NULL值必须唯一
INSERT INTO users (id, email) VALUES (4, 'test@a.com');  -- ✅
INSERT INTO users (id, email) VALUES (5, 'test@a.com');  
-- ❌ ERROR: Duplicate entry 'test@a.com' for key 'email'
```

#### 为什么允许多个NULL？

```
SQL标准定义：
- NULL表示"未知"或"不适用"
- NULL != NULL（任何值与NULL比较都是UNKNOWN）
- 因此多个NULL不违反唯一性

示例：
NULL = NULL  → UNKNOWN（不是TRUE）
NULL != NULL → UNKNOWN（不是TRUE）

所以：
- NULL和NULL不相等
- 多个NULL不冲突
- 唯一索引允许多个NULL

实际应用：
CREATE TABLE employees (
    id BIGINT PRIMARY KEY,
    work_email VARCHAR(100) UNIQUE,  -- 工作邮箱
    name VARCHAR(50)
);

-- 场景：有些员工没有工作邮箱
INSERT INTO employees VALUES (1, 'zhang@company.com', '张三');  -- 有邮箱
INSERT INTO employees VALUES (2, NULL, '李四');  -- 没有邮箱
INSERT INTO employees VALUES (3, NULL, '王五');  -- 没有邮箱
-- 都是合法的 ✅
```

## 四、存储结构差异

### 1. 主键索引（聚簇索引）

```
【InnoDB主键索引结构】

           Root
      [10, 30, 50]
     /     |      \
 [5,10]  [20,30]  [40,50]
   ↓       ↓        ↓
完整数据行（叶子节点）

叶子节点内容：
Page 1: 
[id=5, email='a@a.com', name='张三', ...]  ← 完整数据
[id=10, email='b@b.com', name='李四', ...]

Page 2:
[id=20, email='c@c.com', name='王五', ...]
[id=30, email='d@d.com', name='赵六', ...]

特点：
✅ 聚簇索引（Clustered Index）
✅ 数据即索引，索引即数据
✅ 叶子节点存储完整的数据行
✅ 数据物理存储顺序与主键顺序一致（尽量）
✅ 查询时无需回表
```

### 2. 唯一索引（二级索引）

```
【InnoDB唯一索引结构】

-- 索引：UNIQUE INDEX uk_email (email)

           Root
      [b@, d@, f@]
     /      |      \
 [a@,b@]  [c@,d@]  [e@,f@]
   ↓        ↓        ↓
(email值, 主键id)

叶子节点内容：
Page 1:
[email='a@a.com', id=5]   ← 只存email和主键
[email='b@b.com', id=10]

Page 2:
[email='c@c.com', id=20]
[email='d@d.com', id=30]

特点：
✅ 二级索引（Secondary Index）
✅ 叶子节点存储：索引列值 + 主键值
✅ 不存储完整数据
✅ 查询完整数据需要回表
```

### 3. 查询性能对比

#### 主键查询（最快）

```sql
SELECT * FROM users WHERE id = 5;

执行过程：
1. 在主键索引（聚簇索引）中查找
2. Root → 中间节点 → 叶子节点
3. 直接获取完整数据

磁盘IO：
- B+树查找：2-3次IO
- 获取数据：0次额外IO（数据在索引中）
- 总计：2-3次IO ✅

耗时：0.001-0.003秒
```

#### 唯一索引查询（需要回表）

```sql
SELECT * FROM users WHERE email = 'a@a.com';

执行过程：
1. 在唯一索引（uk_email）中查找
   - Root → 中间节点 → 叶子节点
   - 找到：[email='a@a.com', id=5]
   - 获得主键 id=5

2. 回表到主键索引（聚簇索引）
   - Root → 中间节点 → 叶子节点
   - 找到完整数据：[id=5, email='a@a.com', name='张三', ...]

磁盘IO：
- 唯一索引查找：2-3次IO
- 回表到主键索引：2-3次IO
- 总计：4-6次IO ⚠️

耗时：0.003-0.006秒（约为主键查询的2倍）
```

#### 覆盖索引优化（无需回表）

```sql
-- 只查询索引包含的字段
SELECT id, email FROM users WHERE email = 'a@a.com';

执行过程：
1. 在唯一索引（uk_email）中查找
   - 找到：[email='a@a.com', id=5]
   
2. 索引包含了所需的所有字段（email, id）
   - 无需回表 ✅

磁盘IO：
- 唯一索引查找：2-3次IO
- 回表：0次
- 总计：2-3次IO ✅

耗时：0.001-0.003秒（与主键查询相当）

EXPLAIN显示：
Extra: Using index  ← 覆盖索引
```

## 五、数量和操作限制

### 1. 主键索引

```sql
-- 一张表只能有1个主键
CREATE TABLE test (
    id BIGINT PRIMARY KEY,
    uuid VARCHAR(36),
    name VARCHAR(50)
);

-- ❌ 不能添加第二个主键
ALTER TABLE test ADD PRIMARY KEY (uuid);
-- ERROR: Multiple primary key defined

-- ❌ 不能删除主键索引（通常不允许）
ALTER TABLE test DROP PRIMARY KEY;
-- ERROR: Can't DROP 'PRIMARY'; check that column/key exists

-- 修改主键（需要先删除旧的，再添加新的）
-- 步骤1：删除主键（如果没有自增列）
ALTER TABLE test DROP PRIMARY KEY;
-- 步骤2：添加新主键
ALTER TABLE test ADD PRIMARY KEY (uuid);

-- 注意：删除主键会重建聚簇索引，代价极大
```

### 2. 唯一索引

```sql
-- 一张表可以有多个唯一索引
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(100),
    phone VARCHAR(20),
    id_card VARCHAR(18),
    -- 多个唯一索引
    UNIQUE KEY uk_email (email),
    UNIQUE KEY uk_phone (phone),
    UNIQUE KEY uk_id_card (id_card)
);

-- ✅ 可以删除唯一索引
ALTER TABLE users DROP INDEX uk_phone;

-- ✅ 可以添加唯一索引
ALTER TABLE users ADD UNIQUE INDEX uk_phone (phone);

-- ✅ 可以重命名
ALTER TABLE users RENAME INDEX uk_email TO uk_user_email;
```

## 六、业务含义和使用场景

### 1. 主键索引

**业务含义**：
- 表的唯一标识符
- 逻辑主键，代表实体的唯一性
- 永久不变（不应修改）

**使用场景**：

```sql
-- 1. 自增ID（最常用）
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- 自增主键
    name VARCHAR(50),
    email VARCHAR(100)
);

优点：
✅ 顺序插入，无页分裂
✅ 占用空间小（8字节）
✅ 查询快
✅ 二级索引开销小

-- 2. 业务主键
CREATE TABLE countries (
    country_code CHAR(2) PRIMARY KEY,  -- ISO国家代码，如'CN', 'US'
    country_name VARCHAR(100)
);

适用：
✅ 自然主键（业务固有）
✅ 不会变化
✅ 长度小

-- 3. 复合主键
CREATE TABLE user_roles (
    user_id BIGINT,
    role_id BIGINT,
    granted_at DATETIME,
    PRIMARY KEY (user_id, role_id)  -- 复合主键
);

适用：
✅ 多对多关系表
✅ 组合唯一标识
```

### 2. 唯一索引

**业务含义**：
- 业务唯一性约束
- 防止重复数据
- 可选字段（允许NULL）

**使用场景**：

```sql
-- 1. 用户邮箱/手机号
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(100),
    phone VARCHAR(20),
    UNIQUE KEY uk_email (email),
    UNIQUE KEY uk_phone (phone)
);

理由：
✅ 邮箱/手机号业务上唯一
✅ 但不适合做主键（可能改变）
✅ 可能为NULL（用户可能不提供）

-- 2. 订单号、流水号
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    order_no VARCHAR(32),
    user_id BIGINT,
    UNIQUE KEY uk_order_no (order_no)
);

理由：
✅ 业务唯一标识
✅ 但用自增ID做主键更好（性能）
✅ order_no做唯一索引保证不重复

-- 3. 身份证号、社保号
CREATE TABLE employees (
    id BIGINT PRIMARY KEY,
    id_card VARCHAR(18),
    social_security_no VARCHAR(20),
    UNIQUE KEY uk_id_card (id_card),
    UNIQUE KEY uk_ssn (social_security_no)
);

理由：
✅ 业务唯一
✅ 可能不是所有人都有（外籍员工）
✅ 允许NULL

-- 4. 复合唯一索引
CREATE TABLE course_selections (
    id BIGINT PRIMARY KEY,
    student_id BIGINT,
    course_id BIGINT,
    semester VARCHAR(10),
    UNIQUE KEY uk_student_course (student_id, course_id, semester)
);

理由：
✅ 组合唯一（同一学生不能在同一学期重复选同一门课）
✅ 但单个字段可以重复
```

## 七、性能差异

### 1. 插入性能

```sql
-- 主键索引（自增ID）
CREATE TABLE test_pk (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    data VARCHAR(100)
);

-- 插入10000条
INSERT INTO test_pk (data) VALUES ('test'), ('test'), ...;

性能：
- 顺序插入
- 无页分裂
- 耗时：0.5秒 ✅

-- 唯一索引
CREATE TABLE test_uk (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    unique_key VARCHAR(36),
    data VARCHAR(100),
    UNIQUE KEY uk_key (unique_key)
);

-- 插入10000条（unique_key随机）
INSERT INTO test_uk (unique_key, data) VALUES (UUID(), 'test'), ...;

性能：
- 主键：顺序插入
- 唯一索引：随机插入，可能页分裂
- 需要维护2个索引
- 耗时：1.2秒 ⚠️

差距：主键插入快约2倍
```

### 2. 查询性能

```sql
-- 测试表：100万条数据
CREATE TABLE test (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100),
    name VARCHAR(50),
    UNIQUE KEY uk_email (email)
);

-- 主键查询
SELECT * FROM test WHERE id = 500000;
-- 耗时：0.002秒 ✅
-- IO：2-3次

-- 唯一索引查询
SELECT * FROM test WHERE email = 'test500000@a.com';
-- 耗时：0.005秒 ⚠️
-- IO：4-6次（需要回表）

-- 唯一索引覆盖查询
SELECT id, email FROM test WHERE email = 'test500000@a.com';
-- 耗时：0.002秒 ✅
-- IO：2-3次（无需回表）

结论：
- 主键查询最快
- 唯一索引需回表，慢2倍
- 覆盖索引可与主键相当
```

### 3. 唯一性检查性能

```sql
-- 主键唯一性检查
INSERT INTO test (id, email, name) VALUES (999999, 'new@a.com', 'New');
-- 检查id=999999是否存在
-- B+树查找：O(log n)
-- 耗时：0.001秒 ✅

-- 唯一索引唯一性检查
INSERT INTO test (id, email, name) VALUES (1000001, 'test1@a.com', 'Test');
-- 检查email='test1@a.com'是否存在
-- B+树查找：O(log n)
-- 耗时：0.001秒 ✅

结论：
- 唯一性检查性能相当（都是B+树）
- 主键稍快（聚簇索引，缓存友好）
```

## 八、最佳实践

### 1. 主键设计

```sql
-- ✅ 推荐：自增BIGINT
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ...
);

优点：
✅ 顺序插入，性能好
✅ 占用空间小（8字节）
✅ 简单，易于维护

-- ❌ 不推荐：UUID做主键
CREATE TABLE users (
    uuid CHAR(36) PRIMARY KEY,  -- 36字节
    ...
);

问题：
❌ 随机插入，页分裂频繁
❌ 占用空间大
❌ 二级索引膨胀（每个索引+36字节）
❌ 查询性能下降

-- ⚠️ 谨慎：业务字段做主键
CREATE TABLE users (
    email VARCHAR(100) PRIMARY KEY,  -- 业务字段
    ...
);

问题：
❌ 业务可能变化（邮箱可能改变）
❌ 更新主键代价大（重建聚簇索引）
❌ 长度较大（100字节）
❌ 二级索引开销大
```

### 2. 唯一索引设计

```sql
-- ✅ 推荐：业务唯一字段
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100),
    phone VARCHAR(20),
    UNIQUE KEY uk_email (email),  -- 业务唯一
    UNIQUE KEY uk_phone (phone)   -- 业务唯一
);

理由：
✅ 主键用于标识（自增ID）
✅ 唯一索引保证业务唯一性
✅ 职责分离

-- ✅ 推荐：组合唯一索引
CREATE TABLE user_follows (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    followed_user_id BIGINT,
    created_at DATETIME,
    UNIQUE KEY uk_user_follow (user_id, followed_user_id)
);

理由：
✅ 保证不重复关注
✅ 比复合主键更灵活

-- ⚠️ 注意：索引顺序
-- 查询：WHERE user_id = ? AND followed_user_id = ?
UNIQUE KEY uk_user_follow (user_id, followed_user_id)  -- ✅

-- 查询：WHERE followed_user_id = ? AND user_id = ?
-- 索引仍然有效（最左前缀）

-- 但如果查询：WHERE followed_user_id = ?（只查被关注者）
-- 考虑额外索引：
INDEX idx_followed (followed_user_id)
```

### 3. 主键 vs 唯一索引选择

```
选择主键的标准：
✅ 永久不变
✅ 非空
✅ 唯一标识
✅ 简单（短、数值型）

选择唯一索引的场景：
✅ 业务唯一性约束
✅ 可能为NULL
✅ 可能变化（虽然不推荐）
✅ 长度较大

示例：

用户表：
- 主键：id（自增）✅
- 唯一索引：email, phone ✅

订单表：
- 主键：id（自增）✅
- 唯一索引：order_no ✅
（虽然order_no唯一，但用ID做主键性能更好）

配置表：
- 主键：config_key（业务键）✅
- 如：'max_upload_size', 'session_timeout'
（键值对场景，业务键作为主键很合理）
```

## 九、常见问题

### 1. 为什么不用业务字段做主键？

```sql
-- ❌ 不好：用邮箱做主键
CREATE TABLE users (
    email VARCHAR(100) PRIMARY KEY,
    name VARCHAR(50),
    age INT
);

问题：

1. 更新邮箱代价巨大
UPDATE users SET email = 'new@a.com' WHERE email = 'old@a.com';
-- 需要：
-- - 删除聚簇索引旧记录
-- - 插入聚簇索引新记录
-- - 更新所有二级索引（如果有）
-- - 数据物理移动
-- 耗时：数秒到数分钟

2. 主键较大
- email长度：100字节
- 每个二级索引都包含主键
- 二级索引膨胀

3. 关联表性能差
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_email VARCHAR(100),  -- 外键
    FOREIGN KEY (user_email) REFERENCES users(email)
);
-- user_email 占用100字节，而id只需8字节

-- ✅ 好：用自增ID做主键
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100),
    name VARCHAR(50),
    UNIQUE KEY uk_email (email)
);

优势：
✅ 主键小（8字节）
✅ 更新email只需更新二级索引
✅ 关联表性能好（user_id只需8字节）
```

### 2. NULL在唯一索引中的应用

```sql
-- 场景：用户可选信息
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    work_email VARCHAR(100),
    work_phone VARCHAR(20),
    UNIQUE KEY uk_work_email (work_email),
    UNIQUE KEY uk_work_phone (work_phone)
);

-- 有些用户有工作邮箱，有些没有
INSERT INTO users VALUES (1, 'zhang@company.com', '13800138000');  -- ✅
INSERT INTO users VALUES (2, NULL, NULL);  -- ✅ 没有工作联系方式
INSERT INTO users VALUES (3, NULL, '13900139000');  -- ✅ 只有手机
INSERT INTO users VALUES (4, 'li@company.com', NULL);  -- ✅ 只有邮箱

-- 合法性检查
INSERT INTO users VALUES (5, 'zhang@company.com', '13700137000');
-- ❌ ERROR: Duplicate entry for 'uk_work_email'

优势：
✅ 灵活：可选字段可以为NULL
✅ 唯一：非NULL值保证唯一
```

## 十、面试要点总结

### 核心区别

1. **NULL值**
   - 主键：不允许NULL
   - 唯一索引：允许多个NULL

2. **数量**
   - 主键：一张表只能有1个
   - 唯一索引：一张表可以有多个

3. **索引类型**
   - 主键：聚簇索引（InnoDB）
   - 唯一索引：二级索引

4. **性能**
   - 主键查询：最快（2-3次IO，无需回表）
   - 唯一索引查询：较慢（4-6次IO，需要回表）

5. **业务含义**
   - 主键：逻辑主键，唯一标识
   - 唯一索引：业务唯一性约束

### 设计建议

```
主键：
✅ 使用自增BIGINT
✅ 简单、短小、数值型
❌ 避免使用业务字段
❌ 避免使用UUID（随机）

唯一索引：
✅ 业务唯一字段（email、phone）
✅ 可能为NULL的唯一字段
✅ 订单号、流水号等业务标识

职责分离：
- 主键：标识作用（id）
- 唯一索引：业务约束（email）
```

### 一句话总结

**主键索引是聚簇索引，一表只能有一个，不允许NULL，查询最快；唯一索引是二级索引，一表可有多个，允许多个NULL值（因为NULL != NULL），查询需要回表，性能略慢；设计时推荐用自增ID做主键，业务唯一字段用唯一索引约束，职责分离。**

