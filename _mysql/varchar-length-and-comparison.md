---
title: "CHAR、VARCHAR、TEXT的区别与VARCHAR长度限制详解"
date: 2025-11-02
description: "全面对比CHAR、VARCHAR、TEXT三种字符串类型的存储方式、性能差异、长度限制以及适用场景"
author: "wuxl"
categories: [数据库]
tags: [MySQL, VARCHAR, CHAR, TEXT, 数据类型, 长度限制, 存储优化]
nav_order: 305
parent: 数据库MySQL
---
## 问题

CHAR和VARCHAR，VARCHAR和TEXT的区别，VARCHAR支持的最大长度？

## 答案

### 1. 三种类型核心对比

| 特性 | CHAR | VARCHAR | TEXT |
|------|------|---------|------|
| 存储方式 | **定长**，空格填充 | **变长**，长度前缀 | **变长**，长度前缀 |
| 最大长度 | **255字符** | **65535字节** | **64KB/16MB/4GB** |
| 长度前缀 | 无 | **1-2字节** | **2-4字节** |
| 默认值 | 支持 | 支持 | **不支持** |
| 索引 | 全字段 | 全字段 | **必须前缀索引** |
| 排序/分组 | 正常 | 正常 | **受限**（max_sort_length） |
| 适用场景 | 固定长度数据 | 中等长度文本 | 长文本 |

### 2. VARCHAR的长度限制详解

#### 2.1 理论最大长度

VARCHAR的长度定义是 **65535字节**，但这是 **理论值**，实际可用长度受多种因素限制。

**核心公式**：
```
实际可用字节数 = 65535 - NULL标志位字节数 - 长度前缀字节数 - 其他字段占用
```

#### 2.2 长度前缀占用

VARCHAR需要额外的字节来存储实际长度：

```
长度 ≤ 255字节   → 1字节长度前缀
长度 > 255字节   → 2字节长度前缀
```

**示例**：
```sql
-- VARCHAR(10)：实际内容 + 1字节长度
存储 'abc' → [3]['abc'] = 4字节

-- VARCHAR(1000)：实际内容 + 2字节长度
存储 'hello' → [0x0005]['hello'] = 7字节
```

#### 2.3 实际最大长度计算

**单字节字符集（latin1）**：
```sql
-- 情况1：单个VARCHAR字段
CREATE TABLE test1 (
    content VARCHAR(65533)  -- 65535 - 2(长度前缀) = 65533 ✓
) CHARSET=latin1;

-- 情况2：有NULL字段（需要1字节NULL标志位）
CREATE TABLE test2 (
    id INT,
    content VARCHAR(65532)  -- 65535 - 2(长度) - 1(NULL) = 65532 ✓
) CHARSET=latin1;
```

**多字节字符集（utf8）**：
```sql
-- utf8：每字符最多3字节
CREATE TABLE test_utf8 (
    content VARCHAR(21845)  -- 65535 / 3 ≈ 21845字符 ✓
) CHARSET=utf8;

-- 超过会报错
CREATE TABLE test_utf8_error (
    content VARCHAR(30000)  -- 30000 * 3 = 90000 > 65535 ✗
) CHARSET=utf8;
-- ERROR 1074: Column length too big for column 'content'
```

**多字节字符集（utf8mb4）**：
```sql
-- utf8mb4：每字符最多4字节
CREATE TABLE test_utf8mb4 (
    content VARCHAR(16383)  -- 65535 / 4 ≈ 16383字符 ✓
) CHARSET=utf8mb4;

-- 实际使用推荐
CREATE TABLE users (
    nickname VARCHAR(100),   -- 100字符 = 400字节 ✓
    bio VARCHAR(500),        -- 500字符 = 2000字节 ✓
    address VARCHAR(1000)    -- 1000字符 = 4000字节 ✓
) CHARSET=utf8mb4;
```

#### 2.4 行总长度限制

InnoDB行记录还有 **总长度限制**：

```
行总长度限制（ROW_FORMAT=DYNAMIC）：
- 所有列的总长度不能超过 65535字节（不含TEXT/BLOB）
- 单行记录超过8KB时，变长字段会溢出到溢出页
```

**示例**：
```sql
-- 错误：多个VARCHAR字段总和超过65535字节
CREATE TABLE test (
    col1 VARCHAR(20000),  -- 20000 * 4 = 80000字节
    col2 VARCHAR(10000)   -- 10000 * 4 = 40000字节
) CHARSET=utf8mb4;
-- ERROR 1118: Row size too large

-- 正确：使用TEXT类型
CREATE TABLE test (
    col1 VARCHAR(5000),   -- 5000 * 4 = 20000字节
    col2 TEXT              -- TEXT不计入行长度限制
) CHARSET=utf8mb4;
```

### 3. CHAR vs VARCHAR 详细对比

#### 3.1 存储方式差异

```sql
-- CHAR(10)
'abc'     → 'abc       ' (10字符固定，填充7个空格)
'hello'   → 'hello     ' (10字符固定，填充5个空格)

-- VARCHAR(10)
'abc'     → [3]['abc']       (1字节长度 + 3字节内容 = 4字节)
'hello'   → [5]['hello']     (1字节长度 + 5字节内容 = 6字节)
```

#### 3.2 空间对比（utf8mb4字符集）

| 实际内容 | CHAR(50) | VARCHAR(50) | 空间节省 |
|---------|----------|-------------|---------|
| 'a'(1字符) | 200字节 | 5字节 | **97.5%** |
| 'hello'(5字符) | 200字节 | 21字节 | **89.5%** |
| 'X'*50(50字符) | 200字节 | 202字节 | -1% |

**结论**：内容越短，VARCHAR节省空间越多。

#### 3.3 性能对比

**读取性能**：
```
CHAR优势：
- 固定长度，寻址快（偏移量固定）
- 适合频繁访问的固定长度字段

VARCHAR：
- 需要读取长度前缀，计算偏移
- 性能差异很小（现代MySQL优化良好）
```

**更新性能**：
```
CHAR：
- 原地更新，不需要移动记录
- 更新性能稳定

VARCHAR：
- 长度变化可能导致记录移动
- 频繁更新可能产生碎片
```

#### 3.4 适用场景对比

**CHAR适用场景**：
```sql
-- 固定长度数据
mobile CHAR(11)              -- 手机号
id_card CHAR(18)             -- 身份证号
country_code CHAR(2)         -- 国家代码 CN, US
status CHAR(1)               -- 状态码 A, D, P
md5_hash CHAR(32)            -- MD5值
```

**VARCHAR适用场景**：
```sql
-- 长度变化大的数据
username VARCHAR(50)         -- 用户名 (3-50字符)
email VARCHAR(255)           -- 邮箱
address VARCHAR(500)         -- 地址
title VARCHAR(200)           -- 标题
```

### 4. VARCHAR vs TEXT 详细对比

#### 4.1 长度范围对比

| 类型 | 最大长度 | 长度前缀 | 实际字节数（utf8mb4） |
|------|---------|---------|---------------------|
| VARCHAR | 65535字节 | 1-2字节 | 最多16383字符 |
| TINYTEXT | 255字节 | 1字节 | 最多63字符 |
| TEXT | 64KB | 2字节 | 最多16K字符 |
| MEDIUMTEXT | 16MB | 3字节 | 最多4M字符 |
| LONGTEXT | 4GB | 4字节 | 最多1G字符 |

#### 4.2 存储方式差异

**VARCHAR**：
```
存储方式：
[长度前缀(1-2字节)][实际数据]

特点：
- 数据存储在行记录内（小于768字节时）
- 大于768字节时部分溢出到溢出页（Compact/Redundant）
- Dynamic格式完全溢出
```

**TEXT**：
```
存储方式：
[长度前缀(2-4字节)][20字节指针] → [溢出页存储实际数据]

特点：
- 总是使用溢出页存储（大部分情况）
- 不计入行长度限制
- 占用更多指针空间
```

#### 4.3 功能限制对比

| 功能 | VARCHAR | TEXT |
|------|---------|------|
| 默认值 | ✅ 支持 | ❌ 不支持（MySQL 8.0前） |
| 全字段索引 | ✅ 支持 | ❌ 必须前缀索引 |
| 排序/分组 | ✅ 完整支持 | ⚠️ 受max_sort_length限制 |
| 作为主键 | ⚠️ 可以但不推荐 | ❌ 不支持 |

#### 4.4 性能对比

```sql
-- VARCHAR：查询所有列时包含在内
SELECT * FROM articles;  -- 包含VARCHAR字段

-- TEXT：可以延迟加载
SELECT * FROM articles;  -- 可能延迟加载TEXT字段

-- 查询性能
SELECT id, title FROM articles WHERE id = 1;  -- 快（无TEXT）
SELECT id, title, content FROM articles WHERE id = 1;  -- 慢（含TEXT）
```

#### 4.5 适用场景对比

**VARCHAR适用场景**：
```sql
-- 中等长度文本（< 5000字符）
CREATE TABLE products (
    name VARCHAR(200),           -- 商品名称
    description VARCHAR(2000),   -- 商品描述
    tags VARCHAR(500)            -- 标签
);
```

**TEXT适用场景**：
```sql
-- 长文本（> 5000字符）
CREATE TABLE articles (
    title VARCHAR(200),          -- 标题
    summary VARCHAR(500),        -- 摘要
    content TEXT,                -- 正文（可能很长）
    created_at TIMESTAMP
);

CREATE TABLE logs (
    log_level VARCHAR(20),
    log_message TEXT,            -- 日志内容
    stack_trace MEDIUMTEXT       -- 堆栈跟踪
);
```

### 5. 实际使用建议

#### 5.1 选择决策树

```
字段长度固定？
  ├─ 是 → CHAR
  └─ 否 → 最大长度 < 5000字符？
           ├─ 是 → VARCHAR
           └─ 否 → TEXT
```

#### 5.2 最佳实践示例

```sql
-- 推荐设计
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),        -- 用户名（中等长度）
    mobile CHAR(11),             -- 手机号（固定长度）
    email VARCHAR(255),          -- 邮箱（中等长度）
    status CHAR(1),              -- 状态（固定长度）
    bio VARCHAR(1000),           -- 个人简介（中等长度）
    created_at TIMESTAMP
) CHARSET=utf8mb4;

CREATE TABLE posts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    title VARCHAR(200),          -- 标题（中等长度）
    summary VARCHAR(500),        -- 摘要（中等长度）
    content TEXT,                -- 正文（长文本）
    created_at TIMESTAMP,
    INDEX idx_title (title(50))  -- 前缀索引
) CHARSET=utf8mb4;

-- 不推荐设计
CREATE TABLE users_bad (
    username CHAR(50),           -- 浪费空间（应该用VARCHAR）
    mobile VARCHAR(11),          -- 多余（应该用CHAR）
    bio TEXT                     -- 多余（应该用VARCHAR）
);
```

#### 5.3 索引设计建议

```sql
-- VARCHAR：可以全字段索引（注意长度）
CREATE INDEX idx_username ON users (username);  -- ✅

-- VARCHAR过长：使用前缀索引
CREATE INDEX idx_email ON users (email(50));    -- ✅

-- TEXT：必须使用前缀索引
CREATE INDEX idx_content ON posts (content(100)); -- ✅

-- 错误示例
CREATE INDEX idx_content ON posts (content);    -- ❌ TEXT不支持全字段索引
```

### 6. 常见陷阱与注意事项

#### 6.1 VARCHAR(N)中的N是字符数

```sql
-- 错误理解：VARCHAR(100) = 100字节
-- 正确理解：VARCHAR(100) = 100字符

-- utf8mb4字符集
VARCHAR(100)  → 最多100字符 = 最多400字节
VARCHAR(1000) → 最多1000字符 = 最多4000字节
```

#### 6.2 行长度超限问题

```sql
-- 错误：多个VARCHAR总和超过限制
CREATE TABLE test (
    col1 VARCHAR(10000),
    col2 VARCHAR(10000),
    col3 VARCHAR(10000)
) CHARSET=utf8mb4;
-- ERROR 1118: Row size too large

-- 解决方案1：减少VARCHAR长度
CREATE TABLE test (
    col1 VARCHAR(5000),
    col2 VARCHAR(5000),
    col3 VARCHAR(5000)
) CHARSET=utf8mb4;

-- 解决方案2：部分字段使用TEXT
CREATE TABLE test (
    col1 VARCHAR(5000),
    col2 TEXT,
    col3 TEXT
) CHARSET=utf8mb4;
```

#### 6.3 TEXT不支持默认值（MySQL 8.0前）

```sql
-- MySQL 5.7及之前：不支持TEXT默认值
CREATE TABLE test (
    content TEXT DEFAULT 'default value'
);
-- ERROR 1101: BLOB/TEXT column 'content' can't have a default value

-- 解决方案：使用VARCHAR
CREATE TABLE test (
    content VARCHAR(5000) DEFAULT 'default value'
);

-- MySQL 8.0.13+：支持TEXT默认值（表达式形式）
CREATE TABLE test (
    content TEXT DEFAULT (_utf8mb4'default value')
);
```

### 7. 性能优化建议

#### 7.1 避免SELECT *

```sql
-- 不好：查询所有列（包括TEXT）
SELECT * FROM articles;

-- 好：只查询需要的列
SELECT id, title, created_at FROM articles;

-- 需要内容时单独查询
SELECT content FROM articles WHERE id = 1;
```

#### 7.2 分表设计

```sql
-- 主表：频繁访问的字段
CREATE TABLE articles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200),
    summary VARCHAR(500),
    author_id BIGINT,
    created_at TIMESTAMP
);

-- 内容表：不频繁访问的长文本
CREATE TABLE article_contents (
    article_id BIGINT PRIMARY KEY,
    content TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
```

### 8. 总结

**CHAR vs VARCHAR**：
- **CHAR**：定长，空格填充，适合固定长度数据（手机号、状态码）
- **VARCHAR**：变长，节省空间，适合中等长度变化数据（姓名、邮箱）

**VARCHAR vs TEXT**：
- **VARCHAR**：最大65535字节（实际更小），支持默认值，适合中等长度文本
- **TEXT**：最大4GB，不支持默认值，适合长文本

**VARCHAR最大长度**：
- **理论**：65535字节
- **实际**：取决于字符集和其他字段
  - `latin1`：最多65532字符
  - `utf8`：最多21845字符
  - `utf8mb4`：最多16383字符

**选择原则**：
1. **固定长度** → CHAR
2. **< 5000字符** → VARCHAR
3. **> 5000字符** → TEXT
4. **空间敏感** → VARCHAR/TEXT
5. **性能敏感且固定长度** → CHAR

**面试要点**：能清晰说明三者的长度范围、存储方式差异、VARCHAR的实际长度限制（与字符集相关），以及各自的适用场景。
