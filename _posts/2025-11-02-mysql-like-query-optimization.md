---
layout: post
title: "MySQL中like的模糊查询如何优化？"
date: 2025-11-02
categories: [MySQL, 性能优化]
tags: [MySQL, LIKE查询, 模糊查询, 全文索引, 性能优化]
description: "详解MySQL LIKE模糊查询的性能问题及优化方案，包括索引优化、全文索引、搜索引擎等多种解决方案"
---

# MySQL中like的模糊查询如何优化？

## 核心概念

**LIKE模糊查询**在不同场景下性能差异巨大：
- `LIKE 'abc%'`（前缀匹配）：**可以使用索引**，性能好
- `LIKE '%abc'`（后缀匹配）：**无法使用索引**，性能差
- `LIKE '%abc%'`（中间匹配）：**无法使用索引**，性能极差

优化核心是**避免前缀通配符**或使用**专用搜索方案**。

---

## 一、LIKE查询性能分析

### 场景1：前缀匹配（可用索引）✅

```sql
-- ✅ 可以使用索引
SELECT * FROM users WHERE name LIKE '张%';
```

**EXPLAIN结果**：
```
type: range
key: idx_name
rows: 1000
Extra: Using index condition
```

**原理**：
- B+Tree索引是按字典序排序的
- 前缀匹配可以定位到索引范围
- 类似于 `name >= '张' AND name < '张￿'`

---

### 场景2：后缀匹配（无法用索引）❌

```sql
-- ❌ 无法使用索引
SELECT * FROM users WHERE name LIKE '%张';
```

**EXPLAIN结果**：
```
type: ALL
key: NULL
rows: 1000000   ← 全表扫描
Extra: Using where
```

**原理**：
- 不知道前缀是什么，无法定位索引起始位置
- 必须扫描所有记录逐一匹配

---

### 场景3：中间匹配（无法用索引）❌

```sql
-- ❌ 无法使用索引
SELECT * FROM users WHERE name LIKE '%张%';
```

**EXPLAIN结果**：
```
type: ALL
key: NULL
rows: 1000000   ← 全表扫描
Extra: Using where
```

**性能**：
- 100万数据，执行时间：5-10秒
- 每次都要全表扫描

---

## 二、优化方案（分场景）

### 🔥 方案1：改写为前缀匹配（最简单）

#### 适用场景
- 可以确定前缀
- 模糊部分在后面

#### 实现方式

**原始SQL**：
```sql
-- ❌ 中间匹配
SELECT * FROM products WHERE name LIKE '%iPhone%';
```

**优化SQL**：
```sql
-- ✅ 拆分为多个前缀匹配（如果可以枚举）
SELECT * FROM products WHERE name LIKE 'iPhone%'
UNION
SELECT * FROM products WHERE name LIKE 'Apple iPhone%';
```

**适用场景**：
- 搜索词可以枚举（如品牌+型号）
- 有明确的前缀规则

---

### 🔥 方案2：使用全文索引（推荐）

#### 原理
MySQL的**FULLTEXT索引**专门用于全文搜索，支持中文分词（MySQL 5.7+）。

#### 实现步骤

**1. 创建全文索引**
```sql
-- 创建全文索引
CREATE FULLTEXT INDEX ft_name ON users(name);

-- 或在建表时创建
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    FULLTEXT KEY ft_name (name)
) ENGINE=InnoDB;
```

---

**2. 使用MATCH AGAINST查询**
```sql
-- ❌ 原始LIKE查询
SELECT * FROM users WHERE name LIKE '%张三%';
-- 执行时间：5.2秒

-- ✅ 全文索引查询
SELECT * FROM users WHERE MATCH(name) AGAINST('张三' IN NATURAL LANGUAGE MODE);
-- 执行时间：0.05秒
```

**性能提升：100倍！**

---

#### 全文索引模式

| 模式 | 语法 | 说明 |
|------|------|------|
| **自然语言模式** | `IN NATURAL LANGUAGE MODE` | 默认模式，返回相关性评分 |
| **布尔模式** | `IN BOOLEAN MODE` | 支持+、-、*等操作符 |
| **查询扩展模式** | `WITH QUERY EXPANSION` | 两次搜索，扩展相关词 |

---

#### 布尔模式示例
```sql
-- 必须包含"张三"
SELECT * FROM users WHERE MATCH(name) AGAINST('+张三' IN BOOLEAN MODE);

-- 包含"张三"但不包含"李四"
SELECT * FROM users WHERE MATCH(name) AGAINST('+张三 -李四' IN BOOLEAN MODE);

-- 包含"张"或"三"
SELECT * FROM users WHERE MATCH(name) AGAINST('张 三' IN BOOLEAN MODE);

-- 通配符（张开头）
SELECT * FROM users WHERE MATCH(name) AGAINST('张*' IN BOOLEAN MODE);
```

---

#### 全文索引配置

**中文分词配置**（MySQL 5.7+）：
```sql
-- 查看当前配置
SHOW VARIABLES LIKE 'ngram_token_size';  -- 默认2（2个字符为一个词）

-- 设置分词大小（my.cnf）
[mysqld]
ngram_token_size = 2

-- 创建中文全文索引（指定ngram解析器）
CREATE FULLTEXT INDEX ft_name ON users(name) WITH PARSER ngram;
```

---

#### 全文索引限制

**注意事项**：
- ⚠️ 仅支持InnoDB和MyISAM引擎
- ⚠️ 不支持前缀通配符（如`%abc`）
- ⚠️ 最小搜索词长度限制（`ft_min_word_len`，默认4）
- ⚠️ 更新索引有开销，适合读多写少场景

---

### 🔥 方案3：覆盖索引优化

#### 原理
如果查询字段都在索引中，可以避免回表，减少IO开销。

#### 实现方式

**原始SQL**：
```sql
-- ❌ 需要回表
SELECT * FROM users WHERE name LIKE '张%';
```

**优化SQL**：
```sql
-- ✅ 覆盖索引（只查询索引中的字段）
SELECT id, name FROM users WHERE name LIKE '张%';
-- 索引：idx_name(name, id)
```

**EXPLAIN结果**：
```
type: range
key: idx_name
Extra: Using where; Using index  ← 覆盖索引，无需回表
```

---

### 🔥 方案4：反向索引（适合后缀匹配）

#### 原理
存储字段的反转值，将后缀匹配转换为前缀匹配。

#### 实现步骤

**1. 添加反向字段**
```sql
ALTER TABLE users ADD COLUMN name_reverse VARCHAR(255);

-- 创建索引
CREATE INDEX idx_name_reverse ON users(name_reverse);

-- 更新反向值
UPDATE users SET name_reverse = REVERSE(name);
```

---

**2. 查询时使用反向索引**
```sql
-- ❌ 原始查询（后缀匹配）
SELECT * FROM users WHERE name LIKE '%@gmail.com';
-- 全表扫描

-- ✅ 使用反向索引
SELECT * FROM users WHERE name_reverse LIKE REVERSE('@gmail.com') + '%';
-- 即：name_reverse LIKE 'moc.liamg@%'
-- 可以使用索引
```

---

#### 适用场景
- ✅ 邮箱后缀搜索（如`%@gmail.com`）
- ✅ 文件扩展名搜索（如`%.jpg`）
- ⚠️ 需要维护额外字段

---

### 🔥 方案5：引入专业搜索引擎（推荐）

#### 适用场景
- 复杂的全文搜索需求
- 高并发搜索场景
- 需要搜索评分、高亮、拼音搜索等功能

#### 方案对比

| 方案 | 适用场景 | 性能 | 功能 | 复杂度 |
|------|---------|------|------|--------|
| **Elasticsearch** | 大规模全文搜索 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Solr** | 企业级搜索 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Sphinx** | 轻量级全文搜索 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

---

#### Elasticsearch示例

**Java集成**：
```java
@Service
public class UserSearchService {
    
    @Autowired
    private ElasticsearchTemplate esTemplate;
    
    // 搜索用户
    public List<User> search(String keyword) {
        NativeSearchQuery query = new NativeSearchQueryBuilder()
            .withQuery(QueryBuilders.matchQuery("name", keyword))
            .build();
        
        return esTemplate.queryForList(query, User.class);
    }
}
```

**优势**：
- ✅ 支持中文分词（IK分词器）
- ✅ 支持拼音搜索
- ✅ 支持搜索高亮
- ✅ 支持搜索建议（自动补全）
- ✅ 性能强大（十亿级数据）

---

### 🔥 方案6：前缀树（Trie）+ 缓存

#### 适用场景
- 搜索词前缀提示（如搜索框自动补全）
- 热门搜索词（数据量不大）

#### 实现方式

**Java实现**：
```java
@Service
public class SearchSuggestionService {
    
    private Trie trie = new Trie();
    
    @PostConstruct
    public void init() {
        // 加载热门搜索词到Trie
        List<String> hotWords = loadHotWords();
        hotWords.forEach(trie::insert);
    }
    
    // 前缀搜索
    public List<String> suggest(String prefix) {
        return trie.searchWithPrefix(prefix);
    }
}
```

**缓存优化**：
```java
@Cacheable(value = "search:suggest", key = "#prefix")
public List<String> suggest(String prefix) {
    return trie.searchWithPrefix(prefix);
}
```

---

### 🔥 方案7：数据预处理

#### 方式1：提取关键词字段
```sql
-- 原表
CREATE TABLE products (
    id INT PRIMARY KEY,
    name VARCHAR(255),  -- "Apple iPhone 14 Pro Max 256GB 深空黑"
    brand VARCHAR(50),  -- 提取：Apple
    model VARCHAR(50),  -- 提取：iPhone 14 Pro Max
    INDEX idx_brand(brand),
    INDEX idx_model(model)
);

-- 查询时分别搜索
SELECT * FROM products 
WHERE brand LIKE 'Apple%' 
   OR model LIKE 'iPhone%';
```

---

#### 方式2：标签化
```sql
-- 添加标签字段
CREATE TABLE products (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    tags VARCHAR(500),  -- "Apple,iPhone,14,Pro,Max,黑色,256GB"
    INDEX idx_tags(tags)
);

-- 使用FIND_IN_SET查询
SELECT * FROM products WHERE FIND_IN_SET('iPhone', tags);
```

---

## 三、优化方案对比

| 方案 | 性能 | 实现难度 | 适用场景 | 限制 |
|------|------|---------|---------|------|
| **前缀匹配** | ⭐⭐⭐⭐ | ⭐ | 明确前缀 | 只能前缀 |
| **全文索引** | ⭐⭐⭐⭐ | ⭐⭐ | 中文全文搜索 | 更新开销 |
| **覆盖索引** | ⭐⭐⭐ | ⭐ | 查询字段少 | 只优化IO |
| **反向索引** | ⭐⭐⭐ | ⭐⭐ | 后缀匹配 | 需维护字段 |
| **Elasticsearch** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 复杂搜索 | 架构复杂 |
| **Trie+缓存** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 自动补全 | 数据量限制 |

---

## 四、实战案例

### 案例：电商商品搜索优化

**场景**：
- 商品表100万条数据
- 用户搜索：`%iPhone%`、`%华为%` 等
- 原查询性能：5秒

---

### 优化步骤

#### 阶段1：使用全文索引（MySQL方案）

```sql
-- 创建全文索引
CREATE FULLTEXT INDEX ft_name ON products(name) WITH PARSER ngram;

-- 修改查询
-- ❌ 原始查询
SELECT * FROM products WHERE name LIKE '%iPhone%';

-- ✅ 全文索引查询
SELECT * FROM products WHERE MATCH(name) AGAINST('iPhone' IN NATURAL LANGUAGE MODE);
```

**效果**：
- 执行时间：5秒 → 0.2秒
- 性能提升：25倍

---

#### 阶段2：引入Elasticsearch（终极方案）

**架构**：
```
MySQL（主库）
    ↓ 数据同步（Canal/Logstash）
Elasticsearch（搜索库）
    ↓ 查询
Java应用
```

**实现**：
```java
@Service
public class ProductSearchService {
    
    @Autowired
    private ElasticsearchClient esClient;
    
    public PageResult<Product> search(String keyword, int page, int size) {
        // Elasticsearch搜索
        SearchRequest request = SearchRequest.of(s -> s
            .index("products")
            .query(q -> q.multiMatch(m -> m
                .query(keyword)
                .fields("name", "brand", "model")
            ))
            .from(page * size)
            .size(size)
        );
        
        SearchResponse<Product> response = esClient.search(request, Product.class);
        return convertToPageResult(response);
    }
}
```

**效果**：
- 执行时间：0.2秒 → 0.01秒
- 支持拼音搜索、高亮、排序
- 支持千万级数据

---

## 五、常见误区

### 误区1：以为加了索引就能优化所有LIKE

```sql
-- ❌ 即使有索引，前缀通配符仍无法使用
CREATE INDEX idx_name ON users(name);
SELECT * FROM users WHERE name LIKE '%张%';
-- 仍然全表扫描
```

**正确理解**：只有前缀匹配（`LIKE 'abc%'`）可以用索引。

---

### 误区2：盲目使用全文索引

```sql
-- ❌ 对于单纯的前缀匹配，全文索引反而更慢
SELECT * FROM users WHERE name LIKE '张%';
-- 普通索引：0.01秒
-- 全文索引：0.05秒
```

**正确做法**：
- 前缀匹配：普通索引
- 中间匹配：全文索引或搜索引擎

---

### 误区3：忽视业务场景

```sql
-- 实际上用户很少输入非常模糊的关键词
-- 可以要求用户至少输入2个字符
```

**业务优化**：
- 限制最小搜索词长度
- 提供热门搜索词
- 提供搜索建议

---

## 六、面试答题要点

1. **问题根源**：前缀通配符无法利用B+Tree索引的有序性
2. **简单方案**：改写为前缀匹配，或使用覆盖索引减少IO
3. **中等方案**：MySQL全文索引（FULLTEXT），支持中文分词
4. **高级方案**：Elasticsearch等专业搜索引擎
5. **特殊场景**：反向索引（后缀匹配）、Trie树（自动补全）

---

## 七、最佳实践

### 选择决策树

```
是否可以改为前缀匹配？
├─ 是 → 使用普通索引 + LIKE 'abc%'
└─ 否
   ├─ 数据量 < 10万 → MySQL全文索引
   ├─ 数据量 10万-100万 → MySQL全文索引 + 读写分离
   └─ 数据量 > 100万 → Elasticsearch
```

---

### 通用优化规范

```sql
-- 1. 尽量使用前缀匹配
WHERE name LIKE '张%'

-- 2. 必须中间匹配时，使用全文索引
WHERE MATCH(name) AGAINST('张三')

-- 3. 复杂搜索场景，使用Elasticsearch

-- 4. 限制最小搜索词长度
if (keyword.length() < 2) {
    return "请至少输入2个字符";
}

-- 5. 提供搜索建议
List<String> suggestions = searchService.suggest(prefix);
```

---

## 总结

MySQL LIKE模糊查询优化的核心是**避免前缀通配符**或使用**专用搜索方案**。简单场景可改写为前缀匹配或使用覆盖索引；中等规模使用MySQL全文索引；大规模复杂搜索推荐Elasticsearch。特殊场景可使用反向索引（后缀匹配）或Trie树（自动补全）。面试中能根据数据量和业务场景选择合适方案，体现对搜索技术栈的全面理解。

