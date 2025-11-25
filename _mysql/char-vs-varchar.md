---
title: "CHAR与VARCHAR的区别及使用场景"
date: 2025-11-02
description: "深入对比MySQL中CHAR和VARCHAR的存储方式、性能差异、适用场景以及选择建议"
author: "wuxl"
categories: [数据库]
tags: [MySQL, CHAR, VARCHAR, 数据类型, 存储优化, 性能对比]
nav_order: 304
parent: 数据库MySQL
---
## 问题

CHAR和VARCHAR的区别？

## 答案

### 1. 核心区别

| 特性 | CHAR | VARCHAR |
|------|------|---------|
| 存储方式 | **定长**，不足部分用空格填充 | **变长**，按实际长度存储 |
| 长度范围 | 0-255字符 | 0-65535字节 |
| 存储开销 | 固定空间 | 实际内容 + 1-2字节长度前缀 |
| 尾部空格处理 | 检索时**自动删除**尾部空格 | **保留**尾部空格 |
| 性能 | 读取快（固定位置） | 灵活节省空间 |
| 适用场景 | 长度固定的数据 | 长度变化的数据 |

### 2. 存储方式详解

#### 2.1 CHAR存储机制

```
定义：CHAR(10)

存储 'abc':
实际存储：'abc       ' (补7个空格，总共10字符)
存储空间：10字节（单字节字符集）

存储 'hello world'（超过10字符）:
实际存储：'hello worl' (截断到10字符，MySQL会警告)
```

**存储结构**：
```
[固定长度数据(N字节)]
```

#### 2.2 VARCHAR存储机制

```
定义：VARCHAR(10)

存储 'abc':
实际存储：[3]['abc']
存储空间：1字节(长度) + 3字节(内容) = 4字节

存储 'hello world'（超过10字符）:
实际存储：截断或报错（取决于SQL模式）
```

**存储结构**：
```
长度 ≤ 255字节：[1字节长度前缀][实际数据]
长度 > 255字节：[2字节长度前缀][实际数据]
```

### 3. 存储空间对比

#### 3.1 实际占用空间计算

假设字符集为 `utf8mb4`（每字符最多4字节）：

```sql
-- CHAR(10)
'abc'     → 10字符 = 40字节（固定）
'hello'   → 10字符 = 40字节（固定）

-- VARCHAR(10)
'abc'     → 1字节(长度) + 3字符 = 1 + 12 = 13字节
'hello'   → 1字节(长度) + 5字符 = 1 + 20 = 21字节
```

#### 3.2 空间对比表（utf8mb4字符集）

| 实际内容 | CHAR(10) | VARCHAR(10) | 空间节省 |
|---------|---------|------------|---------|
| 'a' | 40字节 | 5字节 | **87.5%** |
| 'hello' | 40字节 | 21字节 | **47.5%** |
| 'helloworld' | 40字节 | 41字节 | -2.5% |

**结论**：内容越短，VARCHAR节省空间越多。

### 4. 尾部空格处理

#### 4.1 CHAR的空格处理

```sql
CREATE TABLE test_char (col CHAR(10));

INSERT INTO test_char VALUES ('abc   ');  -- 插入时有尾部空格

SELECT col, LENGTH(col), CHAR_LENGTH(col) FROM test_char;
-- 结果：'abc', 3, 3
-- 尾部空格被自动删除！

SELECT * FROM test_char WHERE col = 'abc';
-- 匹配成功（忽略尾部空格）

SELECT * FROM test_char WHERE col = 'abc   ';
-- 也匹配成功（忽略尾部空格）
```

#### 4.2 VARCHAR的空格处理

```sql
CREATE TABLE test_varchar (col VARCHAR(10));

INSERT INTO test_varchar VALUES ('abc   ');  -- 插入时有尾部空格

SELECT col, LENGTH(col), CHAR_LENGTH(col) FROM test_varchar;
-- 结果：'abc   ', 8, 3
-- 尾部空格被保留！

SELECT * FROM test_varchar WHERE col = 'abc';
-- 不匹配（尾部空格不同）

SELECT * FROM test_varchar WHERE col = 'abc   ';
-- 匹配成功
```

**注意**：比较时 `=` 会忽略尾部空格，但 `LIKE` 不会。

### 5. 性能对比

#### 5.1 读取性能

**CHAR优势**：
```
行记录结构：
[字段1(CHAR 10)][字段2(INT)][字段3(CHAR 20)]
  ↓              ↓            ↓
 偏移0         偏移40       偏移44

读取字段3：直接跳到偏移44，读取20字节
```

**VARCHAR劣势**：
```
行记录结构：
[字段1长度+数据][字段2(INT)][字段3长度+数据]
    ↓              ↓              ↓
  动态长度      需计算偏移     需计算偏移

读取字段3：需先读取字段1的长度，计算偏移后才能定位
```

**结论**：CHAR因为固定长度，寻址更快。

#### 5.2 更新性能

**CHAR**：
- 原地更新（In-Place Update），性能较好

**VARCHAR**：
- 长度变化时可能导致行记录迁移（页分裂）
- 频繁更新可能产生碎片

#### 5.3 基准测试示例

```sql
-- 测试表
CREATE TABLE bench_char (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code CHAR(10),
    name VARCHAR(100)
);

CREATE TABLE bench_varchar (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10),
    name VARCHAR(100)
);

-- 插入100万行数据
-- CHAR表：扫描速度略快 5-10%
-- VARCHAR表：存储空间节省 30-50%（取决于数据长度分布）
```

### 6. 适用场景

#### 6.1 CHAR适用场景

**1. 长度固定的数据**
```sql
-- 身份证号（18位）
id_card CHAR(18)

-- 手机号（11位）
mobile CHAR(11)

-- 国家代码（2位）
country_code CHAR(2)

-- MD5哈希值（32位）
hash CHAR(32)

-- 状态码（固定长度）
status CHAR(1)  -- 'A', 'D', 'P'
```

**2. 频繁更新且长度不变**
```sql
-- 用户状态（频繁修改）
user_status CHAR(1)
```

#### 6.2 VARCHAR适用场景

**1. 长度变化较大的数据**
```sql
-- 用户名（1-50字符）
username VARCHAR(50)

-- 邮箱（长度不定）
email VARCHAR(255)

-- 地址（长度差异大）
address VARCHAR(500)

-- 文章摘要
summary VARCHAR(1000)
```

**2. 平均长度远小于最大长度**
```sql
-- 昵称（最大100，平均10）
nickname VARCHAR(100)
```

### 7. 选择建议

#### 7.1 决策流程

```
是否长度固定？
  ├─ 是 → CHAR
  └─ 否 → 是否平均长度接近最大长度？
           ├─ 是 → CHAR（性能优先）
           └─ 否 → VARCHAR（空间优先）
```

#### 7.2 实际推荐

```sql
-- 好的设计
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),        -- 长度变化大
    mobile CHAR(11),             -- 固定11位
    status CHAR(1),              -- 固定1位
    email VARCHAR(255),          -- 长度不定
    address VARCHAR(500)         -- 长度不定
);

-- 不好的设计
CREATE TABLE users_bad (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username CHAR(50),           -- 浪费空间（大部分用户名很短）
    mobile VARCHAR(11),          -- 长度固定，用VARCHAR多余
    email CHAR(255)              -- 浪费空间
);
```

### 8. 字符集的影响

#### 8.1 不同字符集的存储

```sql
-- latin1字符集（1字节/字符）
CHAR(10)    → 10字节固定
VARCHAR(10) → 1字节长度 + 最多10字节

-- utf8字符集（最多3字节/字符）
CHAR(10)    → 30字节固定（10字符 * 3字节）
VARCHAR(10) → 1字节长度 + 最多30字节

-- utf8mb4字符集（最多4字节/字符，支持emoji）
CHAR(10)    → 40字节固定（10字符 * 4字节）
VARCHAR(10) → 1字节长度 + 最多40字节
```

**注意**：CHAR(N) 中的 N 是**字符数**，不是字节数。

### 9. 常见误区

#### 误区1：CHAR一定比VARCHAR快
```
错误：CHAR总是更快
正确：只有在固定长度且频繁访问时，CHAR才有性能优势
     现代MySQL对VARCHAR优化很好，差距很小
```

#### 误区2：VARCHAR节省空间一定更好
```
错误：总是使用VARCHAR
正确：对于固定长度字段，CHAR避免了长度前缀开销
     当平均长度接近最大长度时，CHAR更合适
```

#### 误区3：CHAR不会产生碎片
```
错误：CHAR不会有碎片问题
正确：混合使用CHAR和VARCHAR，或者有NULL值时，仍可能产生碎片
```

### 10. 总结

**CHAR特点**：
- 定长存储，尾部空格填充，检索时删除
- 适合固定长度数据（手机号、状态码）
- 寻址快，适合频繁访问的固定长度字段

**VARCHAR特点**：
- 变长存储，节省空间
- 适合长度变化大的数据（姓名、邮箱、地址）
- 现代MySQL优化良好，性能接近CHAR

**选择原则**：
1. **长度固定** → CHAR
2. **长度变化大** → VARCHAR
3. **空间敏感** → VARCHAR
4. **性能敏感且固定长度** → CHAR

**面试要点**：能说明CHAR的定长填充机制、VARCHAR的长度前缀、尾部空格处理差异、以及各自的适用场景。

---

**扩展阅读**：对于超长文本（>65535字节），使用 **TEXT** 类型；对于二进制数据，使用 **BINARY/VARBINARY**。
