---
layout: default
title: "InnoDB中的索引类型？"
parent: 数据库MySQL
nav_order: 275
description: "全面解析InnoDB支持的索引类型，包括主键索引、二级索引、唯一索引、联合索引、全文索引等，理解各类型的特点和使用场景。"
date: 2025-11-02
---
## 一、核心概念

InnoDB支持多种索引类型，按照不同维度可以有不同分类方式：

### 按存储结构分类
- **聚簇索引**（Clustered Index）
- **非聚簇索引/二级索引**（Secondary Index）

### 按功能分类
- **主键索引**（Primary Key）
- **唯一索引**（Unique Index）
- **普通索引**（Normal Index）
- **全文索引**（Fulltext Index）

### 按字段数量分类
- **单列索引**（Single Column Index）
- **联合索引/复合索引**（Composite Index）

## 二、按存储结构分类

### 1. 聚簇索引（Clustered Index）

#### 核心特点

```
【聚簇索引结构】

       [10, 30, 50]
      /     |     \
  [5,10]  [20,30] [40,50,60]
    ↓       ↓       ↓
  完整数据行存储在叶子节点

叶子节点：
[id=5, name='张三', age=25, ...]
[id=10, name='李四', age=30, ...]
[id=20, name='王五', age=22, ...]
...

特性：
✅ 叶子节点存储完整数据行
✅ 数据物理顺序与索引顺序一致（尽量）
✅ 一张表只能有一个聚簇索引
```

#### 聚簇索引的选择规则

```sql
-- InnoDB自动选择聚簇索引，优先级：

-- 1. 显式定义的主键
CREATE TABLE users (
    id BIGINT PRIMARY KEY,  -- ✅ 作为聚簇索引
    name VARCHAR(50)
);

-- 2. 第一个UNIQUE NOT NULL索引
CREATE TABLE orders (
    order_no VARCHAR(32) UNIQUE NOT NULL,  -- ✅ 作为聚簇索引
    user_id BIGINT,
    -- 没有显式主键
);

-- 3. InnoDB自动生成隐藏的ROW_ID（6字节）
CREATE TABLE products (
    name VARCHAR(50),
    price DECIMAL(10,2)
    -- 没有主键，也没有唯一非空索引
    -- InnoDB自动生成隐藏的 ROW_ID 作为聚簇索引
);

-- 查看隐藏字段（需要innodb_ruby等工具）
-- ROW_ID（6字节，自增）
-- TRX_ID（6字节，事务ID）
-- ROLL_PTR（7字节，回滚指针）
```

#### 聚簇索引的优缺点

**优点**：

```sql
-- 1. 主键查询极快（一次B+树查询即可获取完整数据）
SELECT * FROM users WHERE id=12345;
-- 磁盘IO：3次（无需回表）

-- 2. 范围查询高效（数据连续存储）
SELECT * FROM users WHERE id BETWEEN 1000 AND 2000;
-- 叶子节点顺序扫描，连续IO

-- 3. 排序快（数据天然有序）
SELECT * FROM users WHERE age>20 ORDER BY id;
-- 无需额外排序
```

**缺点**：

```sql
-- 1. 插入性能受影响（需要维护物理顺序）
-- 插入id=15时，可能导致页分裂
[10, 20] → [10, 15 | 20]（分裂成两页）

-- 2. 更新主键代价大（数据物理移动）
UPDATE users SET id=999 WHERE id=1;
-- 需要移动整行数据

-- 3. 二级索引开销大（叶子节点存主键值）
-- 主键太大 → 所有二级索引都变大
```

### 2. 二级索引/非聚簇索引（Secondary Index）

#### 核心特点

```
【二级索引结构】

CREATE INDEX idx_name ON users(name);

       [李, 王, 赵]
      /     |     \
  [张,李]  [王,吴]  [赵,钱]
    ↓       ↓       ↓
  存储：(name, 主键id)

叶子节点：
('张三', id=5)
('李四', id=10)
('王五', id=20)
...

特性：
✅ 叶子节点存储：索引列值 + 主键值
✅ 需要回表查询完整数据（除非覆盖索引）
✅ 一张表可以有多个二级索引
```

#### 回表查询过程

```sql
SELECT * FROM users WHERE name='张三';

执行过程：
1. 在二级索引（idx_name）中查找 name='张三'
   → 找到主键 id=5
   
2. 回表：根据主键id=5到聚簇索引查找完整行
   → 获取 (id=5, name='张三', age=25, ...)

磁盘IO：
- 二级索引查询：3次IO
- 聚簇索引回表：3次IO
- 总计：6次IO（相比主键查询的3次，多一倍）
```

#### 为什么二级索引存主键而非数据指针？

```
【对比】

方案1：存数据指针（MyISAM）
索引：('张三', 0x1A2B3C4D)
         ↓
     数据文件物理地址

问题：
❌ 数据移动时，所有索引都要更新
❌ 页分裂、数据重组时，维护成本高

方案2：存主键值（InnoDB）
索引：('张三', id=5)
         ↓
     聚簇索引查询

优点：
✅ 数据移动时，二级索引无需更新
✅ 维护成本低
✅ 一致性更好

代价：
⚠️ 主键大时，所有二级索引都变大
⚠️ 需要二次查询（回表）
```

## 三、按功能分类

### 1. 主键索引（Primary Key）

```sql
-- 方式1：建表时指定
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    name VARCHAR(50)
);

-- 方式2：单独定义
CREATE TABLE orders (
    id BIGINT,
    order_no VARCHAR(32),
    PRIMARY KEY (id)
);

-- 方式3：复合主键
CREATE TABLE order_items (
    order_id BIGINT,
    product_id BIGINT,
    quantity INT,
    PRIMARY KEY (order_id, product_id)
);

特点：
✅ 自动创建聚簇索引
✅ 值唯一且非空
✅ 一张表只能有一个主键
✅ 强制约束：NOT NULL + UNIQUE
```

### 2. 唯一索引（Unique Index）

```sql
-- 创建唯一索引
CREATE UNIQUE INDEX idx_email ON users(email);

-- 或在建表时指定
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(100) UNIQUE,  -- 自动创建唯一索引
    phone VARCHAR(20),
    UNIQUE KEY uk_phone (phone)
);

特点：
✅ 索引列值必须唯一
✅ 允许NULL值（可以有多个NULL）
✅ 可以有多个唯一索引
✅ 会创建二级索引
```

**唯一索引 vs 主键索引**：

```sql
-- 主键索引
- 必须非空
- 一张表只能有一个
- 是聚簇索引
- 不能删除

-- 唯一索引
- 可以为NULL
- 一张表可以有多个
- 是二级索引
- 可以删除
```

**NULL值处理**：

```sql
-- 唯一索引允许多个NULL
CREATE TABLE test (
    id INT PRIMARY KEY,
    email VARCHAR(100) UNIQUE
);

INSERT INTO test VALUES (1, NULL);  -- ✅
INSERT INTO test VALUES (2, NULL);  -- ✅ 允许多个NULL
INSERT INTO test VALUES (3, 'a@a.com');  -- ✅
INSERT INTO test VALUES (4, 'a@a.com');  -- ❌ 唯一约束冲突

原因：SQL标准中，NULL != NULL
```

### 3. 普通索引（Normal Index）

```sql
-- 创建普通索引
CREATE INDEX idx_age ON users(age);

-- 或
ALTER TABLE users ADD INDEX idx_city (city);

特点：
✅ 最基础的索引类型
✅ 无唯一性约束
✅ 可以有多个
✅ 允许NULL值
✅ 允许重复值
```

### 4. 全文索引（Fulltext Index）

```sql
-- 创建全文索引（InnoDB支持，MySQL 5.6+）
CREATE TABLE articles (
    id BIGINT PRIMARY KEY,
    title VARCHAR(200),
    content TEXT,
    FULLTEXT INDEX ft_content (content)
);

-- 使用全文索引
SELECT * FROM articles 
WHERE MATCH(content) AGAINST('数据库优化' IN NATURAL LANGUAGE MODE);

特点：
✅ 用于文本搜索
✅ 支持中文分词（需要ngram插件）
✅ 仅支持 CHAR、VARCHAR、TEXT 类型
⚠️ 性能不如专业搜索引擎（Elasticsearch）
```

**全文索引模式**：

```sql
-- 1. 自然语言模式（默认）
SELECT * FROM articles 
WHERE MATCH(content) AGAINST('MySQL');

-- 2. 布尔模式（支持操作符）
SELECT * FROM articles 
WHERE MATCH(content) AGAINST('+MySQL -Oracle' IN BOOLEAN MODE);
-- + 必须包含
-- - 必须不包含

-- 3. 查询扩展模式
SELECT * FROM articles 
WHERE MATCH(content) AGAINST('database' WITH QUERY EXPANSION);
```

**配置中文分词**：

```sql
-- 创建支持中文的全文索引
CREATE TABLE articles (
    id BIGINT PRIMARY KEY,
    content TEXT,
    FULLTEXT INDEX ft_content (content) WITH PARSER ngram
);

-- 设置分词大小（默认2，即二元分词）
SET GLOBAL ngram_token_size=2;

-- 示例：'数据库' → ['数据', '据库']
```

## 四、按字段数量分类

### 1. 单列索引

```sql
-- 单列索引
CREATE INDEX idx_age ON users(age);
CREATE INDEX idx_city ON users(city);
CREATE INDEX idx_create_time ON users(create_time);

特点：
- 只包含一个列
- 简单直观
- 适合单一条件查询
```

### 2. 联合索引/复合索引

```sql
-- 联合索引
CREATE INDEX idx_city_age_name ON users(city, age, name);

特点：
✅ 包含多个列
✅ 遵循最左前缀原则
✅ 可以覆盖多种查询场景
✅ 比多个单列索引更高效
```

**最左前缀原则**：

```sql
-- 索引：INDEX(city, age, name)

-- ✅ 可以使用
WHERE city='北京'  -- 使用city
WHERE city='北京' AND age=25  -- 使用city, age
WHERE city='北京' AND age=25 AND name='张三'  -- 全部使用

-- ❌ 无法使用或部分使用
WHERE age=25  -- 不使用（跳过了city）
WHERE name='张三'  -- 不使用（跳过了city和age）
WHERE city='北京' AND name='张三'  -- 只使用city
```

**联合索引 vs 多个单列索引**：

```sql
-- 方案1：多个单列索引
CREATE INDEX idx_city ON users(city);
CREATE INDEX idx_age ON users(age);
CREATE INDEX idx_name ON users(name);

-- 查询
SELECT * FROM users WHERE city='北京' AND age=25;

执行：
- 可能使用idx_city或idx_age（优化器选择）
- 或触发索引合并（Index Merge）
- 效率一般

-- 方案2：联合索引
CREATE INDEX idx_city_age_name ON users(city, age, name);

-- 同样查询
执行：
- 直接使用联合索引
- 一次B+树遍历
- 效率更高

结论：
- 对于组合查询，联合索引更优
- 索引维护成本更低（一个索引vs三个）
- 存储空间更小
```

## 五、特殊索引类型

### 1. 前缀索引（Prefix Index）

```sql
-- 对长字符串字段建立前缀索引
CREATE INDEX idx_email_prefix ON users(email(10));

-- 只索引email的前10个字符

特点：
✅ 减少索引大小
✅ 提高索引效率
⚠️ 无法覆盖索引（必须回表）
⚠️ 无法用于ORDER BY、GROUP BY

适用场景：
- VARCHAR(200+) 字段
- 前缀区分度高（如email、URL）
```

**前缀长度选择**：

```sql
-- 计算前缀区分度
SELECT 
    COUNT(DISTINCT email) / COUNT(*) AS full_selectivity,
    COUNT(DISTINCT LEFT(email, 5)) / COUNT(*) AS prefix5,
    COUNT(DISTINCT LEFT(email, 10)) / COUNT(*) AS prefix10,
    COUNT(DISTINCT LEFT(email, 15)) / COUNT(*) AS prefix15
FROM users;

结果：
full_selectivity: 1.0000  -- 完整字段
prefix5:          0.7234  -- 前5个字符
prefix10:         0.9567  -- 前10个字符 ✅ 区分度接近1
prefix15:         0.9891  -- 前15个字符

选择：prefix10（区分度够用，索引更小）
```

### 2. 空间索引（Spatial Index）

```sql
-- 用于地理位置数据（GIS）
CREATE TABLE locations (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    coordinate POINT NOT NULL,
    SPATIAL INDEX idx_coordinate (coordinate)
);

-- 查询附近的点
SELECT name FROM locations
WHERE MBRContains(
    ST_Buffer(ST_GeomFromText('POINT(116.404 39.915)'), 0.01),
    coordinate
);

特点：
- 用于 GEOMETRY、POINT、LINESTRING 等类型
- 支持空间查询（距离、包含、相交等）
- 使用R-Tree索引结构（非B+树）
```

### 3. 降序索引（Descending Index，MySQL 8.0+）

```sql
-- MySQL 8.0+ 支持真正的降序索引
CREATE INDEX idx_create_time_desc ON orders(create_time DESC);

-- 或混合升降序
CREATE INDEX idx_city_time ON orders(city ASC, create_time DESC);

特点：
✅ 优化 ORDER BY ... DESC 查询
✅ 避免 filesort
⚠️ MySQL 8.0之前的DESC是忽略的
```

### 4. 函数索引（Generated Column Index，MySQL 8.0+）

```sql
-- MySQL 8.0+ 支持函数索引
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    total_amount DECIMAL(10, 2),
    create_time DATETIME,
    -- 函数索引
    INDEX idx_year ((YEAR(create_time))),
    INDEX idx_amount_floor ((FLOOR(total_amount)))
);

-- 查询会使用函数索引
SELECT * FROM orders WHERE YEAR(create_time) = 2025;

-- 5.7及之前的替代方案：虚拟列
ALTER TABLE orders ADD COLUMN create_year INT AS (YEAR(create_time)) VIRTUAL;
CREATE INDEX idx_create_year ON orders(create_year);
```

## 六、索引使用建议

### 1. 选择合适的索引类型

```sql
-- 场景1：主键字段
PRIMARY KEY (id)  -- 聚簇索引

-- 场景2：唯一性约束
UNIQUE INDEX (email)  -- 唯一索引

-- 场景3：频繁查询的字段
INDEX (user_id, status, create_time)  -- 联合索引

-- 场景4：长字符串字段
INDEX (url(50))  -- 前缀索引

-- 场景5：全文搜索
FULLTEXT INDEX (content)  -- 全文索引

-- 场景6：地理位置
SPATIAL INDEX (location)  -- 空间索引
```

### 2. 联合索引设计原则

```sql
-- 原则1：区分度高的列放前面
INDEX (user_id, status, create_time)  -- user_id区分度最高

-- 原则2：等值查询列放前面
INDEX (status, create_time)  -- status等值，create_time范围

-- 原则3：覆盖常用查询
-- 查询：SELECT id, status, create_time WHERE user_id=?
INDEX (user_id, status, create_time)  -- 覆盖索引
```

### 3. 避免过多索引

```sql
-- ❌ 不好：索引过多
CREATE INDEX idx_a ON t(a);
CREATE INDEX idx_b ON t(b);
CREATE INDEX idx_c ON t(c);
CREATE INDEX idx_ab ON t(a, b);
CREATE INDEX idx_ac ON t(a, c);
CREATE INDEX idx_abc ON t(a, b, c);

问题：
- 写入性能下降（每次INSERT/UPDATE需要维护6个索引）
- 存储空间浪费
- 优化器选择困难

-- ✅ 好：合并索引
CREATE INDEX idx_abc ON t(a, b, c);  -- 覆盖大部分查询
CREATE INDEX idx_b ON t(b);  -- 只在b单独查询频繁时创建
```

## 七、面试要点总结

### 索引类型分类

**按存储结构**：
- **聚簇索引**：叶子节点存完整数据，一表一个，主键即聚簇索引
- **二级索引**：叶子节点存主键值，需要回表

**按功能**：
- **主键索引**：唯一非空，聚簇索引
- **唯一索引**：值唯一，允许NULL
- **普通索引**：无约束
- **全文索引**：文本搜索

**按字段数量**：
- **单列索引**：一个字段
- **联合索引**：多个字段，遵循最左前缀

### 关键特性对比

| 索引类型 | 唯一性 | 允许NULL | 数量限制 | 存储结构 |
|---------|--------|----------|---------|---------|
| 主键索引 | ✅ | ❌ | 1个 | 聚簇索引 |
| 唯一索引 | ✅ | ✅ | 多个 | 二级索引 |
| 普通索引 | ❌ | ✅ | 多个 | 二级索引 |
| 全文索引 | ❌ | ✅ | 多个 | 特殊结构 |

### 一句话总结

**InnoDB支持聚簇索引（主键索引）和二级索引（唯一、普通、全文索引等），其中聚簇索引的叶子节点存储完整数据行，一表仅一个；二级索引叶子节点存储主键值，需要回表查询，可有多个；联合索引遵循最左前缀原则，比多个单列索引更高效。**

