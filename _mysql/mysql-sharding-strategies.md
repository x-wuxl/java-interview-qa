---
title: "MySQL分库分表方案与动态扩展策略"
date: 2025-11-02
description: "详解MySQL分库分表的方法、路由策略、扩容方案以及如何动态添加查询条件"
author: "wuxl"
categories: [数据库]
tags: [MySQL, 分库分表, 数据库架构, 分片策略, ShardingSphere, 性能优化]
nav_order: 395
parent: 数据库MySQL
---
## 问题

MySQL分库分表有哪些方法？后续需要添加一个查询条件怎么添加？

## 答案

### 1. 核心概念

**分库分表**（Sharding）是指将单个数据库或表的数据，按照一定规则**水平拆分**到多个数据库或表中，解决**单库单表性能瓶颈**。

**核心目标**：
- 突破单库**连接数限制**（默认151）
- 突破单表**数据量瓶颈**（建议500万-1000万）
- 提升**并发读写能力**

**分库分表类型**：
- **垂直分库**：按业务模块拆分
- **垂直分表**：按字段拆分
- **水平分库**：按数据行拆分到不同库
- **水平分表**：按数据行拆分到不同表

---

### 2. 垂直分库（按业务拆分）

#### 2.1 拆分策略

**拆分前**（单库）：

```
database: mall
├── orders      # 订单表
├── products    # 商品表
├── users       # 用户表
├── payments    # 支付表
└── logistics   # 物流表
```

**拆分后**（多库）：

```
database: mall_order        # 订单库
├── orders
├── order_items

database: mall_product      # 商品库
├── products
├── categories

database: mall_user         # 用户库
├── users
├── user_profiles

database: mall_payment      # 支付库
├── payments
├── payment_logs
```

#### 2.2 优缺点

**优点**：
- ✅ 业务解耦，独立维护
- ✅ 分散单库压力
- ✅ 不同业务独立扩展

**缺点**：
- ❌ 跨库事务复杂（需要分布式事务）
- ❌ 跨库JOIN困难
- ❌ 数据迁移成本高

#### 2.3 适用场景

```
适用：
- 业务模块清晰
- 跨模块查询少
- 单库成为性能瓶颈

不适用：
- 业务耦合度高
- 大量跨库关联查询
```

---

### 3. 垂直分表（按字段拆分）

#### 3.1 拆分策略

**拆分前**：

```sql
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100),         -- 常用字段
    price DECIMAL(10,2),       -- 常用字段
    stock INT,                 -- 常用字段
    description TEXT,          -- 大字段（不常用）
    detail_html LONGTEXT,      -- 大字段（不常用）
    images JSON,               -- 大字段（不常用）
    create_time DATETIME
);
```

**拆分后**：

```sql
-- 主表（常用字段）
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100),
    price DECIMAL(10,2),
    stock INT,
    create_time DATETIME
);

-- 扩展表（大字段）
CREATE TABLE products_detail (
    product_id BIGINT PRIMARY KEY,
    description TEXT,
    detail_html LONGTEXT,
    images JSON,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

#### 3.2 优缺点

**优点**：
- ✅ 减少单行数据大小
- ✅ 提升热点数据查询性能
- ✅ 减少IO和内存占用

**缺点**：
- ❌ 需要JOIN查询
- ❌ 事务管理复杂

#### 3.3 适用场景

```
适用：
- 表包含大字段（TEXT、BLOB）
- 部分字段访问频率低
- 需要优化查询性能

拆分原则：
- 常用字段放主表
- 大字段/低频字段放扩展表
```

---

### 4. 水平分库（重点）

#### 4.1 分库策略

**按用户ID取模**：

```
原始数据库：mall
拆分后：
├── mall_0：user_id % 4 = 0
├── mall_1：user_id % 4 = 1
├── mall_2：user_id % 4 = 2
└── mall_3：user_id % 4 = 3

示例：
user_id = 100 → 100 % 4 = 0 → 路由到mall_0
user_id = 101 → 101 % 4 = 1 → 路由到mall_1
```

**路由代码**：

```java
public class DatabaseRouter {
    private static final int DB_COUNT = 4;
    
    public String getDatabase(Long userId) {
        int index = (int) (userId % DB_COUNT);
        return "mall_" + index;
    }
}

// 使用
String dbName = router.getDatabase(100L); // mall_0
```

#### 4.2 分库方案对比

| 方案 | 说明 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **取模分片** | `id % N` | 数据均匀 | 扩容困难 | 数据量可预估 |
| **范围分片** | 按ID范围 | 扩容简单 | 数据不均 | 时间序列数据 |
| **一致性哈希** | 哈希环 | 扩容影响小 | 实现复杂 | 分布式缓存 |
| **地理位置** | 按地区 | 就近访问 | 数据不均 | 多地域部署 |

---

### 5. 水平分表（重点）

#### 5.1 分表策略

**按订单ID取模**：

```sql
-- 原始表
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    amount DECIMAL(10,2)
);

-- 拆分为4张表
CREATE TABLE orders_0 (id BIGINT PRIMARY KEY, user_id BIGINT, amount DECIMAL(10,2));
CREATE TABLE orders_1 (id BIGINT PRIMARY KEY, user_id BIGINT, amount DECIMAL(10,2));
CREATE TABLE orders_2 (id BIGINT PRIMARY KEY, user_id BIGINT, amount DECIMAL(10,2));
CREATE TABLE orders_3 (id BIGINT PRIMARY KEY, user_id BIGINT, amount DECIMAL(10,2));

-- 路由规则
-- order_id = 1001 → 1001 % 4 = 1 → orders_1
-- order_id = 1002 → 1002 % 4 = 2 → orders_2
```

**路由代码**：

```java
public class TableRouter {
    private static final int TABLE_COUNT = 4;
    
    public String getTableName(Long orderId) {
        int index = (int) (orderId % TABLE_COUNT);
        return "orders_" + index;
    }
}

// 使用
String tableName = router.getTableName(1001L); // orders_1
```

#### 5.2 常见分表方案

##### （1）按ID取模

```java
// 分4张表
int tableIndex = orderId % 4;
String tableName = "orders_" + tableIndex;

// 优点：数据均匀
// 缺点：范围查询困难
```

##### （2）按时间范围

```java
// 按月分表
String tableName = "orders_" + yearMonth; // orders_202511

// 优点：范围查询简单，扩容方便
// 缺点：热点数据集中（当月表压力大）
```

##### （3）按用户ID取模

```java
// 按用户分表
int tableIndex = userId % 4;
String tableName = "orders_" + tableIndex;

// 优点：用户维度查询快
// 缺点：按订单ID查询需要遍历
```

---

### 6. 分库分表路由策略

#### 6.1 手写路由（基础）

```java
@Service
public class OrderService {
    @Autowired
    private JdbcTemplate jdbcTemplate;
    
    private static final int DB_COUNT = 4;
    private static final int TABLE_COUNT = 4;
    
    public void createOrder(Order order) {
        // 1. 计算库索引
        int dbIndex = (int) (order.getUserId() % DB_COUNT);
        String dbName = "mall_" + dbIndex;
        
        // 2. 计算表索引
        int tableIndex = (int) (order.getId() % TABLE_COUNT);
        String tableName = "orders_" + tableIndex;
        
        // 3. 切换数据源
        DataSourceContextHolder.setDataSource(dbName);
        
        // 4. 执行SQL
        String sql = "INSERT INTO " + tableName + " (id, user_id, amount) VALUES (?, ?, ?)";
        jdbcTemplate.update(sql, order.getId(), order.getUserId(), order.getAmount());
    }
    
    public Order getOrderById(Long orderId, Long userId) {
        // 1. 路由到具体库表
        int dbIndex = (int) (userId % DB_COUNT);
        int tableIndex = (int) (orderId % TABLE_COUNT);
        
        String dbName = "mall_" + dbIndex;
        String tableName = "orders_" + tableIndex;
        
        // 2. 查询
        DataSourceContextHolder.setDataSource(dbName);
        String sql = "SELECT * FROM " + tableName + " WHERE id = ?";
        return jdbcTemplate.queryForObject(sql, new Object[]{orderId}, new OrderRowMapper());
    }
}
```

#### 6.2 使用ShardingSphere（推荐）

**配置示例**：

```yaml
spring:
  shardingsphere:
    datasource:
      names: ds0,ds1,ds2,ds3
      ds0:
        type: com.zaxxer.hikari.HikariDataSource
        url: jdbc:mysql://localhost:3306/mall_0
        username: root
        password: password
      ds1:
        url: jdbc:mysql://localhost:3306/mall_1
      ds2:
        url: jdbc:mysql://localhost:3306/mall_2
      ds3:
        url: jdbc:mysql://localhost:3306/mall_3
    
    rules:
      sharding:
        tables:
          orders:
            actual-data-nodes: ds$->{0..3}.orders_$->{0..3}
            database-strategy:
              standard:
                sharding-column: user_id
                sharding-algorithm-name: db-mod
            table-strategy:
              standard:
                sharding-column: id
                sharding-algorithm-name: table-mod
        
        sharding-algorithms:
          db-mod:
            type: MOD
            props:
              sharding-count: 4
          table-mod:
            type: MOD
            props:
              sharding-count: 4
```

**使用代码**：

```java
@Service
public class OrderService {
    @Autowired
    private OrderMapper orderMapper;
    
    // 无需关心路由，ShardingSphere自动处理
    public void createOrder(Order order) {
        orderMapper.insert(order);
    }
    
    public Order getOrderById(Long orderId) {
        return orderMapper.selectById(orderId);
    }
    
    // 按用户ID查询（单库单表）
    public List<Order> getOrdersByUserId(Long userId) {
        return orderMapper.selectByUserId(userId);
    }
}
```

---

### 7. 后续添加查询条件的方案

#### 7.1 问题场景

**原始分片键**：`user_id`

```java
// 可以高效查询
SELECT * FROM orders WHERE user_id = 100; // ✅ 路由到单库单表
```

**新增查询需求**：按订单号查询

```java
// 无法路由（order_no不是分片键）
SELECT * FROM orders WHERE order_no = 'ON123456'; // ❌ 需要遍历所有库表
```

#### 7.2 解决方案

##### 方案1：映射表（推荐）

**建立映射关系**：

```sql
-- 映射表（单独库或Redis）
CREATE TABLE order_mapping (
    order_no VARCHAR(32) PRIMARY KEY,
    user_id BIGINT,
    order_id BIGINT,
    INDEX idx_user_id (user_id)
);

-- 查询流程：
-- 1. 查询映射表，获取user_id
SELECT user_id FROM order_mapping WHERE order_no = 'ON123456';
-- 2. 根据user_id路由到目标库表
SELECT * FROM orders WHERE user_id = 100 AND order_no = 'ON123456';
```

**代码实现**：

```java
public Order getOrderByOrderNo(String orderNo) {
    // 1. 查询映射表
    OrderMapping mapping = mappingMapper.selectByOrderNo(orderNo);
    if (mapping == null) {
        return null;
    }
    
    // 2. 根据user_id路由查询（ShardingSphere自动路由）
    return orderMapper.selectByUserIdAndOrderNo(mapping.getUserId(), orderNo);
}
```

**优点**：
- ✅ 精准路由，性能高
- ✅ 实现简单

**缺点**：
- ❌ 需要维护映射表
- ❌ 写入时需要双写

##### 方案2：在order_no中编码user_id

**设计order_no格式**：

```
order_no格式：用户ID后4位 + 时间戳 + 随机数
示例：1001234567890123456
       ^^^^ 
       user_id的后4位（用于路由）
```

**路由代码**：

```java
public Order getOrderByOrderNo(String orderNo) {
    // 1. 从order_no中提取user_id后4位
    String userIdSuffix = orderNo.substring(0, 4);
    // 假设需要遍历所有可能的user_id（可优化）
    
    // 2. 使用部分信息路由（需要配合其他策略）
    // 实际使用时需要更完善的设计
}
```

**优点**：
- ✅ 无需额外表
- ✅ 自包含

**缺点**：
- ❌ 编码复杂
- ❌ 可能泄露用户信息

##### 方案3：使用ES建立二级索引（推荐）

**架构设计**：

```
MySQL（主数据）        ElasticSearch（索引）
├── mall_0            ├── orders索引
├── mall_1            │   ├── order_no
├── mall_2            │   ├── user_id
└── mall_3            │   └── order_id
                      
查询流程：
1. 在ES中查询order_no，获取user_id
2. 根据user_id路由到MySQL查询详细数据
```

**代码实现**：

```java
@Service
public class OrderSearchService {
    @Autowired
    private ElasticsearchRestTemplate esTemplate;
    
    @Autowired
    private OrderMapper orderMapper;
    
    public Order getOrderByOrderNo(String orderNo) {
        // 1. ES查询获取user_id
        SearchQuery query = new NativeSearchQueryBuilder()
            .withQuery(QueryBuilders.termQuery("order_no", orderNo))
            .build();
        
        SearchHit<OrderIndex> hit = esTemplate.searchOne(query, OrderIndex.class);
        if (hit == null) {
            return null;
        }
        
        Long userId = hit.getContent().getUserId();
        
        // 2. MySQL精准查询
        return orderMapper.selectByUserIdAndOrderNo(userId, orderNo);
    }
}

// ES索引模型
@Document(indexName = "orders")
public class OrderIndex {
    @Id
    private Long orderId;
    
    @Field(type = FieldType.Keyword)
    private String orderNo;
    
    @Field(type = FieldType.Long)
    private Long userId;
    
    // 其他可搜索字段
}
```

**优点**：
- ✅ 支持复杂查询
- ✅ 性能好（ES专为搜索优化）
- ✅ 扩展性强

**缺点**：
- ❌ 需要维护数据一致性
- ❌ 架构复杂度增加

##### 方案4：广播查询 + 合并结果

**实现思路**：

```java
public Order getOrderByOrderNo(String orderNo) {
    // 并发查询所有分片
    List<CompletableFuture<Order>> futures = new ArrayList<>();
    
    for (int db = 0; db < 4; db++) {
        for (int table = 0; table < 4; table++) {
            int finalDb = db;
            int finalTable = table;
            
            CompletableFuture<Order> future = CompletableFuture.supplyAsync(() -> {
                // 指定库表查询
                return orderMapper.selectByOrderNoFromShard(orderNo, finalDb, finalTable);
            });
            
            futures.add(future);
        }
    }
    
    // 合并结果
    return futures.stream()
        .map(CompletableFuture::join)
        .filter(Objects::nonNull)
        .findFirst()
        .orElse(null);
}
```

**优点**：
- ✅ 实现简单
- ✅ 不依赖外部系统

**缺点**：
- ❌ 性能差（需要查询所有分片）
- ❌ 数据库压力大

#### 7.3 方案对比

| 方案 | 性能 | 复杂度 | 一致性 | 推荐度 |
|------|------|--------|--------|--------|
| **映射表** | ⭐⭐⭐⭐ | ⭐⭐ | 强 | ⭐⭐⭐⭐⭐ |
| **编码user_id** | ⭐⭐⭐⭐ | ⭐⭐⭐ | 强 | ⭐⭐⭐ |
| **ES二级索引** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 最终一致 | ⭐⭐⭐⭐⭐ |
| **广播查询** | ⭐ | ⭐ | 强 | ⭐ |

---

### 8. 分库分表扩容方案

#### 8.1 翻倍扩容（推荐）

**扩容策略**：从4个库扩到8个库

```
原始：mall_0, mall_1, mall_2, mall_3
扩容后：mall_0, mall_1, mall_2, mall_3, mall_4, mall_5, mall_6, mall_7

数据迁移：
- mall_0 → 保留偶数数据，迁移奇数数据到mall_4
- mall_1 → 保留偶数数据，迁移奇数数据到mall_5
- ...
```

**迁移步骤**：

```sql
-- 1. 创建新库表
CREATE DATABASE mall_4;
CREATE TABLE mall_4.orders_0 LIKE mall_0.orders_0;

-- 2. 数据迁移（需要停机或双写）
INSERT INTO mall_4.orders_0
SELECT * FROM mall_0.orders_0
WHERE user_id % 8 = 4;

-- 3. 删除旧数据
DELETE FROM mall_0.orders_0 WHERE user_id % 8 = 4;
```

#### 8.2 一致性哈希（平滑扩容）

**原理**：新增节点只影响部分数据

```
哈希环：0 - 2^32
节点：db0(0), db1(2^30), db2(2^31), db3(2^31 + 2^30)

新增db4：只需迁移db1的部分数据
```

**优点**：
- ✅ 扩容影响小
- ✅ 支持平滑扩容

**缺点**：
- ❌ 实现复杂
- ❌ 数据分布可能不均

---

### 9. 总结

#### 9.1 分库分表方案

| 类型 | 场景 | 优点 | 缺点 |
|------|------|------|------|
| **垂直分库** | 业务拆分 | 解耦 | 跨库事务 |
| **垂直分表** | 大字段拆分 | 减少IO | 需要JOIN |
| **水平分库** | 单库瓶颈 | 分散压力 | 路由复杂 |
| **水平分表** | 单表数据量大 | 提升性能 | 跨表查询难 |

#### 9.2 添加查询条件方案

**推荐方案**：
1. **小规模**：映射表
2. **大规模**：ES二级索引
3. **实时性要求高**：映射表
4. **复杂查询**：ES二级索引

**实施建议**：
- 提前规划分片键（尽量使用主要查询条件）
- 避免跨库JOIN（在应用层合并）
- 使用中间件（ShardingSphere、MyCat）
- 建立监控和回滚机制

#### 9.3 面试答题思路

1. **先说明4种分库分表类型**：垂直分库、垂直分表、水平分库、水平分表
2. **重点讲水平分库分表**：取模、范围、哈希等策略
3. **说明添加查询条件的方案**：映射表、ES二级索引、编码user_id、广播查询
4. **补充扩容方案**：翻倍扩容、一致性哈希
5. **结合实际经验**：使用ShardingSphere等中间件，提前规划分片键

**核心要点**：理解分库分表的本质是**水平拆分**，关键是设计好**分片键**和**路由策略**，后续添加查询条件可通过**映射表**或**ES二级索引**解决。

