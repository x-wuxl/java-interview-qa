---
layout: post
title: "什么是倒排索引？"
date: 2025-11-02
categories: [中间件, ElasticSearch]
tags: [ElasticSearch, 倒排索引, 搜索引擎, 面试]
description: "深入理解倒排索引的原理、结构和在 ElasticSearch 中的应用"
---

## 核心概念

**倒排索引（Inverted Index）** 是全文检索引擎的核心数据结构，它将文档中的每个词（Term）映射到包含该词的文档列表，实现了从**词到文档**的快速查找，与传统的**文档到词**的正向索引相反。

## 倒排索引的结构

### 1. 正排索引 vs 倒排索引

**正排索引（Forward Index）**：文档 → 词
```
Doc1 → ["Java", "ElasticSearch", "搜索引擎"]
Doc2 → ["Java", "MySQL", "数据库"]
Doc3 → ["ElasticSearch", "分布式", "搜索"]
```

**倒排索引（Inverted Index）**：词 → 文档
```
"Java"           → [Doc1, Doc2]
"ElasticSearch"  → [Doc1, Doc3]
"MySQL"          → [Doc2]
"搜索引擎"       → [Doc1]
"数据库"         → [Doc2]
"分布式"         → [Doc3]
"搜索"           → [Doc3]
```

### 2. 倒排索引的组成

倒排索引由两部分组成：

#### **词典（Term Dictionary）**
- 存储所有不重复的词（Term）
- 按字典序排序，支持快速查找
- 常用数据结构：FST（Finite State Transducer）

#### **倒排列表（Posting List）**
- 存储包含该词的文档 ID 列表
- 每个条目包含：
  - **文档 ID（Doc ID）**
  - **词频（TF，Term Frequency）**：词在文档中出现的次数
  - **位置信息（Position）**：词在文档中的位置，支持短语查询
  - **偏移量（Offset）**：词的起始和结束字符位置，支持高亮

```
Term: "ElasticSearch"
Posting List:
  - Doc1: TF=2, Positions=[5, 120], Offsets=[25-38, 560-573]
  - Doc3: TF=1, Positions=[0], Offsets=[0-13]
```

## 倒排索引的构建过程

### 1. 文档分词
```java
// 原始文档
Doc1: "ElasticSearch 是一个强大的搜索引擎"
Doc2: "搜索引擎基于倒排索引实现"

// 分词后
Doc1: ["ElasticSearch", "是", "一个", "强大", "的", "搜索", "引擎"]
Doc2: ["搜索", "引擎", "基于", "倒排", "索引", "实现"]
```

### 2. 构建倒排索引
```
Term Dictionary:
"ElasticSearch" → [Doc1]
"是"            → [Doc1]
"一个"          → [Doc1]
"强大"          → [Doc1]
"搜索"          → [Doc1, Doc2]
"引擎"          → [Doc1, Doc2]
"基于"          → [Doc2]
"倒排"          → [Doc2]
"索引"          → [Doc2]
"实现"          → [Doc2]
```

### 3. 查询过程
```java
// 查询 "搜索引擎"
Step 1: 分词 → ["搜索", "引擎"]
Step 2: 查词典 → "搜索" → [Doc1, Doc2]
                 "引擎" → [Doc1, Doc2]
Step 3: 求交集 → [Doc1, Doc2]（都包含这两个词）
Step 4: 相关性评分（TF-IDF、BM25）
Step 5: 返回排序后的结果
```

## ElasticSearch 中的优化

### 1. FST（Finite State Transducer）
- ES 使用 FST 存储词典，实现内存高效存储
- FST 既能快速查找，又能节省内存（共享前缀）

```
例如：词典中有 "cat", "cats", "dog", "dogs"
传统存储：16 字节
FST 存储：通过共享前缀和后缀，大幅减少空间
```

### 2. Frame of Reference 编码
- 倒排列表中的文档 ID 进行差值编码和压缩
- 例如：[100, 105, 110] → [100, +5, +5]

### 3. Roaring Bitmap
- 对倒排列表进行位图压缩
- 适合包含大量文档 ID 的场景

### 4. 跳表（Skip List）
- 在倒排列表中使用跳表，加速多词求交集操作
- 避免遍历整个列表

## 实际示例

### 电商商品搜索
```java
// 假设有以下商品文档
{
  "id": 1,
  "name": "Apple iPhone 15 Pro Max",
  "description": "最新款苹果手机，搭载 A17 芯片"
}
{
  "id": 2,
  "name": "Apple MacBook Pro",
  "description": "专业级苹果笔记本电脑"
}
{
  "id": 3,
  "name": "华为 Mate 60 Pro",
  "description": "旗舰手机，5G 性能强劲"
}

// 构建倒排索引（部分）
"apple"     → [1, 2]
"iphone"    → [1]
"pro"       → [1, 2, 3]
"macbook"   → [2]
"手机"      → [1, 3]
"苹果"      → [1, 2]
"华为"      → [3]

// 搜索 "苹果 Pro"
Step 1: 分词 → ["苹果", "pro"]
Step 2: 查倒排索引
        "苹果" → [1, 2]
        "pro"  → [1, 2, 3]
Step 3: 求交集 → [1, 2]
Step 4: 评分排序（考虑词频、文档长度、字段权重等）
Result: [1, 2]（iPhone 15 Pro Max 和 MacBook Pro）
```

## 倒排索引的优势

### 1. 快速全文检索
- 直接通过词定位文档，时间复杂度 O(1)
- 避免全表扫描

### 2. 支持复杂查询
- **词组查询（Phrase Query）**：利用位置信息
- **近似查询（Proximity Query）**：词的距离约束
- **前缀查询（Prefix Query）**：利用词典的有序性

### 3. 相关性评分
- 基于 TF-IDF 或 BM25 算法
- 考虑词频、逆文档频率、文档长度等因素

## 性能考量

### 1. 写入性能
- 构建倒排索引需要分词、排序，写入有一定延迟
- ES 采用 Segment 机制，批量构建索引

### 2. 磁盘占用
- 倒排索引需要额外存储空间
- ES 通过压缩算法（FST、FOR、Roaring Bitmap）优化

### 3. 更新策略
- 倒排索引不支持原地更新（Immutable）
- ES 采用**标记删除 + 后台合并**策略

## 总结

倒排索引是搜索引擎的基石，它通过**词 → 文档**的映射，实现了高效的全文检索。ElasticSearch 基于 Lucene 的倒排索引，并通过 FST、压缩算法、跳表等优化，在空间和时间上取得平衡。

**面试要点**：
- 清晰解释倒排索引的概念（词 → 文档）
- 说明词典和倒排列表的组成
- 举例说明查询过程（分词 → 查词典 → 求交集 → 评分）
- 可提及 FST、压缩算法等优化手段

