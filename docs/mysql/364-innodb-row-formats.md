---
layout: default
title: "InnoDB支持的行格式详解"
parent: 数据库MySQL
nav_order: 364
description: "全面解析InnoDB存储引擎支持的四种行格式：Compact、Redundant、Dynamic、Compressed的特点和使用场景"
author: "wuxl"
date: 2025-11-02
---
## 问题

InnoDB支持哪几种行格式？

## 答案

### 1. 核心概念

InnoDB支持 **4种行格式（Row Format）**，用于定义行记录在数据页中的物理存储方式。行格式的选择会影响存储效率、性能和大字段的处理方式。

### 2. 四种行格式详解

#### 2.1 Compact（紧凑格式）
**MySQL 5.0引入，InnoDB默认格式（5.7.9之前）**

```
行格式结构：
[变长字段长度列表][NULL标志位][记录头信息][列1数据][列2数据]...
```

**特点**：
- **变长字段长度列表**：逆序存储VARCHAR、TEXT等变长字段的实际长度
- **NULL标志位**：用位图表示哪些列为NULL，节省空间
- **溢出页处理**：当行记录超过页大小的一半（约8KB）时，会把变长字段的前768字节存在数据页，其余存在溢出页（Off-Page）

#### 2.2 Redundant（冗余格式）
**MySQL 5.0之前的格式，已废弃**

```
行格式结构：
[字段长度偏移列表][记录头信息][列1数据][列2数据]...
```

**特点**：
- **兼容性**：为了兼容旧版本MySQL
- **空间浪费**：NULL值也会占用存储空间
- **字段长度**：使用偏移量存储，占用更多空间
- **不推荐使用**

#### 2.3 Dynamic（动态格式）
**MySQL 5.7引入，5.7.9之后的默认格式**

**特点**：
- **完全溢出存储**：当行记录过大时，变长字段会 **完全存储在溢出页**，数据页只保留20字节的指针
- **更高效的存储**：数据页可以存储更多行记录，提高缓存命中率
- **支持更大的索引前缀**：最大支持3072字节（InnoDB页大小16KB时）

```
数据页存储：
[行记录头] + [定长字段] + [指向溢出页的20字节指针]
                                    ↓
                          [溢出页存储完整的变长数据]
```

#### 2.4 Compressed（压缩格式）
**基于Dynamic格式，增加了压缩功能**

**特点**：
- **数据压缩**：使用zlib算法压缩数据页
- **更小的存储空间**：适合存储大量文本数据
- **CPU开销**：压缩和解压缩会增加CPU使用
- **需配合压缩表**：使用 `ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8` 指定

### 3. 行格式对比

| 行格式 | 引入版本 | 默认 | NULL处理 | 溢出页策略 | 压缩 | 推荐 |
|--------|---------|------|---------|-----------|------|------|
| Redundant | 5.0之前 | 否 | 占用空间 | 前768字节 | 否 | ❌ |
| Compact | 5.0 | 5.7.9前 | 位图优化 | 前768字节 | 否 | ✅ |
| Dynamic | 5.7 | 5.7.9后 | 位图优化 | 完全溢出 | 否 | ✅✅ |
| Compressed | 5.7 | 否 | 位图优化 | 完全溢出 | 是 | ⚠️ |

### 4. 如何设置行格式

#### 4.1 创建表时指定
```sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    content TEXT
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;
```

#### 4.2 修改现有表
```sql
ALTER TABLE users ROW_FORMAT=DYNAMIC;
```

#### 4.3 查看表的行格式
```sql
SHOW TABLE STATUS LIKE 'users'\G

-- 或者
SELECT table_name, row_format
FROM information_schema.tables
WHERE table_name = 'users';
```

#### 4.4 设置默认行格式
```sql
-- 在my.cnf中配置
[mysqld]
innodb_default_row_format=DYNAMIC
```

### 5. 性能优化考量

#### 5.1 选择Dynamic的理由
- **更好的缓存利用率**：大字段完全溢出后，数据页可以存储更多行记录
- **范围查询更快**：减少数据页数量，减少磁盘I/O
- **现代MySQL推荐**：5.7.9之后的默认选择

#### 5.2 何时使用Compressed
- **存储空间紧张**：数据量大且以文本为主
- **读多写少**：减少解压缩开销
- **需权衡**：CPU vs 磁盘空间的取舍

#### 5.3 避免Redundant
- 已过时，空间利用率低，无优势

### 6. 总结

- InnoDB支持 **Compact、Redundant、Dynamic、Compressed** 四种行格式
- **Dynamic 是现代MySQL的默认和推荐格式**，采用完全溢出策略
- **Compact 兼容性好**，适合旧版本MySQL
- **Compressed 适合空间敏感场景**，但增加CPU开销
- **Redundant 已废弃**，不推荐使用

**面试要点**：能说出四种行格式的名称、Dynamic与Compact在溢出页处理上的区别（前768字节 vs 完全溢出）、以及为什么推荐使用Dynamic格式。
