---
layout: default
title: "MySQL中BLOB与TEXT的区别及使用场景"
parent: 数据库MySQL
nav_order: 306
description: "详细对比MySQL中BLOB和TEXT类型的存储方式、字符集处理、排序规则、适用场景等核心差异"
author: "wuxl"
date: 2025-11-02
---
## 问题

MySQL的BLOB和TEXT有什么区别？

## 答案

### 1. 核心区别

| 特性 | BLOB (Binary Large Object) | TEXT |
|------|---------------------------|------|
| 存储内容 | **二进制数据**（图片、音频、加密数据） | **文本数据**（文章、日志、JSON） |
| 字符集 | **无字符集**，按字节存储 | **有字符集**（utf8、utf8mb4等） |
| 排序/比较 | **按字节值**比较（区分大小写） | **按字符集校对规则**比较 |
| 适用场景 | 二进制文件、加密数据、原始字节 | 长文本、文章内容、HTML |
| 索引限制 | 需指定前缀长度 | 需指定前缀长度 |

### 2. 类型及容量对比

#### 2.1 BLOB家族

| 类型 | 最大长度 | 长度前缀 | 典型用途 |
|------|---------|---------|---------|
| TINYBLOB | 255字节 | 1字节 | 小图标 |
| BLOB | 64KB | 2字节 | 小文件 |
| MEDIUMBLOB | 16MB | 3字节 | 中等文件、图片 |
| LONGBLOB | 4GB | 4字节 | 大文件、视频 |

#### 2.2 TEXT家族

| 类型 | 最大长度 | 长度前缀 | 典型用途 |
|------|---------|---------|---------|
| TINYTEXT | 255字符 | 1字节 | 短摘要 |
| TEXT | 64KB | 2字节 | 文章内容 |
| MEDIUMTEXT | 16MB | 3字节 | 长文章、HTML |
| LONGTEXT | 4GB | 4字节 | 超长文本、日志 |

**注意**：TEXT的长度是 **字符数**，实际字节数取决于字符集。

### 3. 字符集与排序规则

#### 3.1 BLOB - 无字符集

```sql
CREATE TABLE files (
    id INT PRIMARY KEY,
    data BLOB
);

-- 插入二进制数据
INSERT INTO files VALUES (1, x'89504E47');  -- PNG文件头

-- 比较按字节值
SELECT * FROM files WHERE data = x'89504E47';

-- 排序按字节值（二进制排序）
SELECT * FROM files ORDER BY data;
```

#### 3.2 TEXT - 有字符集

```sql
CREATE TABLE articles (
    id INT PRIMARY KEY,
    content TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
);

-- 插入文本数据
INSERT INTO articles VALUES (1, '你好世界');

-- 比较按字符集校对规则（可能不区分大小写）
SELECT * FROM articles WHERE content LIKE '%世界%';

-- 排序按字符集规则
SELECT * FROM articles ORDER BY content;  -- 按拼音或Unicode排序
```

#### 3.3 排序规则差异示例

```sql
-- BLOB排序（按字节值）
CREATE TABLE test_blob (val BLOB);
INSERT INTO test_blob VALUES ('apple'), ('Apple'), ('APPLE');
SELECT * FROM test_blob ORDER BY val;
-- 结果：APPLE, Apple, apple（按ASCII码排序）

-- TEXT排序（按字符集校对规则）
CREATE TABLE test_text (val TEXT COLLATE utf8mb4_general_ci);
INSERT INTO test_text VALUES ('apple'), ('Apple'), ('APPLE');
SELECT * FROM test_text ORDER BY val;
-- 结果：apple, Apple, APPLE（不区分大小写排序）
```

### 4. 存储方式

#### 4.1 行内存储 vs 溢出页存储

InnoDB对BLOB和TEXT的存储方式相同，取决于数据长度：

**小数据（< 40字节）**：
```
行内存储：
[长度前缀][完整数据]
```

**大数据（> 768字节，Compact/Redundant格式）**：
```
行内存储：
[长度前缀][前768字节][20字节溢出页指针]
                              ↓
                        [溢出页存储剩余数据]
```

**大数据（Dynamic/Compressed格式，推荐）**：
```
行内存储：
[长度前缀][20字节溢出页指针]
              ↓
        [溢出页存储完整数据]
```

### 5. 使用场景详解

#### 5.1 BLOB适用场景

**1. 存储二进制文件**
```sql
CREATE TABLE images (
    id INT PRIMARY KEY,
    filename VARCHAR(255),
    file_data MEDIUMBLOB,        -- 图片文件
    file_type VARCHAR(50),       -- image/png, image/jpeg
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入图片（通常在应用层处理）
-- INSERT INTO images (filename, file_data, file_type)
-- VALUES ('avatar.png', [二进制数据], 'image/png');
```

**2. 存储加密数据**
```sql
CREATE TABLE sensitive_data (
    id INT PRIMARY KEY,
    encrypted_data BLOB          -- AES加密后的数据
);
```

**3. 存储序列化对象**
```sql
CREATE TABLE cache (
    cache_key VARCHAR(255) PRIMARY KEY,
    cache_value BLOB,            -- Java序列化对象、Protobuf数据
    expire_at TIMESTAMP
);
```

#### 5.2 TEXT适用场景

**1. 存储文章内容**
```sql
CREATE TABLE articles (
    id INT PRIMARY KEY,
    title VARCHAR(255),
    content TEXT,                -- 文章正文
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**2. 存储JSON数据**
```sql
-- 方式1：使用TEXT
CREATE TABLE configs (
    id INT PRIMARY KEY,
    config_data TEXT             -- JSON字符串
);

-- 方式2：使用JSON类型（更推荐）
CREATE TABLE configs (
    id INT PRIMARY KEY,
    config_data JSON             -- 原生JSON类型（MySQL 5.7+）
);
```

**3. 存储日志**
```sql
CREATE TABLE system_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    log_level VARCHAR(20),
    log_message TEXT,            -- 日志内容
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6. 性能考量

#### 6.1 索引限制

BLOB和TEXT **不能直接建立全字段索引**，必须使用前缀索引：

```sql
-- 错误：不能对TEXT/BLOB全字段建索引
CREATE INDEX idx_content ON articles (content);
-- ERROR 1170: BLOB/TEXT column 'content' used in key specification without a key length

-- 正确：使用前缀索引
CREATE INDEX idx_content ON articles (content(100));  -- 索引前100字符
```

#### 6.2 查询优化

**避免SELECT ***：
```sql
-- 不好：查询所有列（包括BLOB/TEXT）
SELECT * FROM articles;  -- 加载大量数据到内存

-- 好：只查询需要的列
SELECT id, title FROM articles;  -- 跳过content字段

-- 需要内容时再单独查询
SELECT content FROM articles WHERE id = 1;
```

**原因**：
- BLOB/TEXT数据量大，查询时会增加内存和网络开销
- MySQL的临时表不能存储BLOB/TEXT，会导致使用磁盘临时表

#### 6.3 排序和分组限制

```sql
-- 排序和分组受max_sort_length限制（默认1024字节）
SELECT * FROM articles ORDER BY content;  -- 只使用前1024字节排序

-- 查看限制
SHOW VARIABLES LIKE 'max_sort_length';

-- 临时修改
SET SESSION max_sort_length = 2048;
```

### 7. 实际应用建议

#### 7.1 是否应该将文件存入数据库？

**优点**：
- 事务一致性：文件和元数据在同一个事务中
- 备份简单：数据库备份即可
- 权限控制：统一的数据库权限管理

**缺点**：
- 数据库体积膨胀，备份恢复慢
- 查询性能下降（即使不查询BLOB/TEXT列，表扫描也会受影响）
- 不适合频繁读取的大文件（CDN分发更高效）

**推荐方案**：
```sql
-- 存储文件路径，实际文件存储在对象存储（OSS、S3）
CREATE TABLE files (
    id INT PRIMARY KEY,
    filename VARCHAR(255),
    file_path VARCHAR(500),      -- https://cdn.example.com/files/xxx.jpg
    file_size BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 7.2 BLOB vs VARBINARY

```sql
-- VARBINARY：小二进制数据（< 65KB）
CREATE TABLE tokens (
    id INT PRIMARY KEY,
    token VARBINARY(255)         -- 加密token
);

-- BLOB：大二进制数据（> 65KB）
CREATE TABLE files (
    id INT PRIMARY KEY,
    file_data MEDIUMBLOB         -- 图片、文档
);
```

#### 7.3 TEXT vs VARCHAR

```sql
-- VARCHAR：中等长度文本（< 65535字节）
CREATE TABLE users (
    id INT PRIMARY KEY,
    bio VARCHAR(1000)            -- 个人简介
);

-- TEXT：长文本（> 65535字节或不确定长度）
CREATE TABLE posts (
    id INT PRIMARY KEY,
    content TEXT                 -- 博客内容
);
```

### 8. 字符集陷阱

```sql
-- 使用utf8mb4存储emoji
CREATE TABLE comments (
    id INT PRIMARY KEY,
    content TEXT CHARACTER SET utf8mb4  -- 支持emoji
);

-- 错误：使用utf8（最多3字节，不支持emoji）
CREATE TABLE comments (
    id INT PRIMARY KEY,
    content TEXT CHARACTER SET utf8     -- 不支持emoji，插入会报错
);
```

### 9. 监控与优化

```sql
-- 查看表中BLOB/TEXT字段占用空间
SELECT
    table_name,
    data_length,           -- 数据大小
    index_length,          -- 索引大小
    (data_length + index_length) / 1024 / 1024 AS total_mb
FROM information_schema.tables
WHERE table_schema = 'your_database'
  AND table_name = 'your_table';

-- 查看行数和平均行大小
SELECT
    table_name,
    table_rows,
    avg_row_length
FROM information_schema.tables
WHERE table_schema = 'your_database';
```

### 10. 总结

**BLOB（二进制大对象）**：
- 存储二进制数据（图片、文件、加密数据）
- 无字符集，按字节比较
- 适合存储非文本数据

**TEXT（文本大对象）**：
- 存储文本数据（文章、日志、JSON）
- 有字符集和排序规则
- 适合存储长文本内容

**核心差异**：
- **字符集**：BLOB无字符集，TEXT有字符集
- **比较方式**：BLOB按字节值，TEXT按校对规则
- **使用场景**：BLOB存二进制，TEXT存文本

**选择原则**：
1. **二进制数据** → BLOB
2. **文本数据** → TEXT
3. **小文件（< 1MB）** → 考虑存数据库
4. **大文件（> 1MB）** → 存对象存储（OSS、S3），数据库存路径

**面试要点**：能清晰说明BLOB和TEXT在字符集、排序规则、使用场景上的区别，以及为什么大文件不建议直接存数据库。
