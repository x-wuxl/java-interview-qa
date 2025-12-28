---
layout: default
title: "大型电商订单数据的分库分表方案如何设计？"
parent: 大厂项目场景实战
nav_order: 622
description: "通过电商订单场景详细讲解分片键选择、容量规划、基因法、扩容方案"
date: 2025-12-28
---

# 大型电商订单数据的分库分表方案如何设计？

## 业务场景

大型电商平台，日均订单量500万，历史订单超过10亿条。

**痛点**：
- 订单表太大，查询性能下降
- 单库连接数不足，写入吞吐上不去
- 备份恢复时间过长

---

## 方案设计

### 第一步：确定分片键

**候选字段分析**：

| 字段 | 优点 | 缺点 |
|------|------|------|
| order_id | 分布均匀 | 用户查订单需要扫全库 |
| user_id | 用户查询方便 | 大卖家数据倾斜 |
| create_time | 按时间归档 | 热点写入集中 |

**最终选择**：`user_id`

原因：
1. 80%的查询是用户查看自己的订单
2. 可以配合**基因法**解决order_id查询问题

### 第二步：容量规划

**当前数据量**：10亿订单
**年增长**：18亿/年
**容量规划**：支撑3年 = 10 + 18*3 = 64亿

**分片数计算**：
- 单表建议不超过2000万
- 分片数 = 640亿 / 2000万 = 32
- 考虑扩展性，选择 **32库 × 32表 = 1024个分片**

### 第三步：分片策略

```
分库：user_id % 32 = db_index
分表：(user_id / 32) % 32 = table_index
```

**ShardingSphere配置**：
```yaml
spring:
  shardingsphere:
    rules:
      sharding:
        tables:
          orders:
            actual-data-nodes: ds_$->{0..31}.orders_$->{0..31}
            database-strategy:
              standard:
                sharding-column: user_id
                sharding-algorithm-name: db-hash-mod
            table-strategy:
              standard:
                sharding-column: user_id
                sharding-algorithm-name: table-hash-mod
        sharding-algorithms:
          db-hash-mod:
            type: MOD
            props:
              sharding-count: 32
          table-hash-mod:
            type: INLINE
            props:
              algorithm-expression: orders_$->{(user_id.intdiv(32)) % 32}
```

---

## 订单ID设计：基因法

### 问题
用user_id分片后，如何通过order_id定位分片？

### 基因法解决方案

将user_id的分片信息"注入"到order_id中：

```java
public long generateOrderId(long userId) {
    // 1. 生成雪花ID（64位）
    long snowflakeId = snowflake.nextId();
    
    // 2. 计算user_id对应的分片基因（低10位）
    int gene = (int) (userId % 1024);
    
    // 3. 将雪花ID低10位替换为基因
    //    保留高54位，拼接10位基因
    return (snowflakeId >> 10 << 10) | gene;
}
```

**解析order_id获取分片信息**：
```java
public int getShardIndex(long orderId) {
    int gene = (int) (orderId & 1023);  // 取低10位
    int dbIndex = gene & 31;            // 低5位 = 库
    int tableIndex = (gene >> 5) & 31;  // 高5位 = 表
    return dbIndex * 32 + tableIndex;
}
```

**效果**：
- 通过user_id可以定位分片 ✅
- 通过order_id也可以定位分片 ✅

---

## 关联表处理

### 订单明细表（order_items）

**策略**：跟随主表，使用相同的分片策略

```yaml
tables:
  order_items:
    actual-data-nodes: ds_$->{0..31}.order_items_$->{0..31}
    database-strategy:
      standard:
        sharding-column: user_id
        sharding-algorithm-name: db-hash-mod
    table-strategy:
      standard:
        sharding-column: user_id
        sharding-algorithm-name: table-hash-mod
```

**关键**：冗余user_id字段到order_items表

```sql
CREATE TABLE order_items (
  id BIGINT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,  -- 冗余字段
  product_id BIGINT NOT NULL,
  quantity INT NOT NULL,
  -- ...
  KEY idx_order_id (order_id),
  KEY idx_user_id (user_id)
);
```

---

## 查询场景优化

### 场景1：用户查询自己的订单（高频）
```sql
SELECT * FROM orders WHERE user_id = 123 ORDER BY create_time DESC LIMIT 20;
```
✅ 精准路由到单库单表

### 场景2：运营按时间查询订单（低频）
```sql
SELECT * FROM orders WHERE create_time > '2024-01-01' AND status = 1;
```
**问题**：需要扫描所有分片！

**解决方案**：
1. **ES双写**：订单数据同步到ES，复杂查询走ES
2. **聚合表**：建立运营查询用的汇总表

### 场景3：根据order_id查询
```sql
SELECT * FROM orders WHERE order_id = 123456789;
```
✅ 通过基因法从order_id解析分片信息，精准路由

---

## 数据迁移方案

### 双写迁移

```
1. 新旧库双写
   │
2. 存量数据迁移
   │
3. 数据一致性校验
   │
4. 流量切换到新库
   │
5. 停止双写，下线旧库
```

**双写代码示例**：
```java
@Transactional
public void createOrder(Order order) {
    // 写旧库
    oldOrderMapper.insert(order);
    
    // 写新库（分库分表）
    newOrderMapper.insert(order);
}
```

### 数据校验

```java
public void verify() {
    // 1. 全量对比
    compareAllData();
    
    // 2. 增量对比
    compareIncrementalData();
    
    // 3. 抽样校验
    sampleCompare();
}
```

---

## 扩容方案

### 问题
从32库扩容到64库，如何迁移数据？

### 方案：成倍扩容

```
原分片规则：user_id % 32
新分片规则：user_id % 64

扩容策略：每个分片裂变为2个
  - 原分片0 → 新分片0 + 新分片32
  - 原分片1 → 新分片1 + 新分片33
  - ...
```

**迁移数据量**：只需迁移50%的数据

### 操作步骤

```
1. 新增32个库，同步数据
2. 切换分片规则
3. 清理迁移走的数据
```

---

## 生产环境配置参考

```yaml
spring:
  shardingsphere:
    datasource:
      names: ds_0,ds_1,...,ds_31
      ds_0:
        type: com.zaxxer.hikari.HikariDataSource
        driver-class-name: com.mysql.cj.jdbc.Driver
        jdbc-url: jdbc:mysql://order-db-0:3306/order
        username: ${DB_USER}
        password: ${DB_PASSWORD}
        maximum-pool-size: 20
        minimum-idle: 5
        connection-timeout: 30000
        
    props:
      sql-show: true  # 生产环境设为false
      max-connections-size-per-query: 1
```

---

## 面试答题框架

```
分片键选择：user_id（查询高频、分布均匀）
分片策略：32库×32表，Hash取模
订单ID：基因法，支持order_id直接路由
关联表：冗余user_id，同分片策略
查询优化：
  - 用户查询：精准路由
  - 运营查询：ES辅助
扩容方案：成倍扩容，50%数据迁移
```

---

## 总结

| 设计点 | 方案 |
|--------|------|
| 分片键 | user_id |
| 分片策略 | 32库×32表 |
| 订单ID | 雪花ID + 基因法 |
| 关联表 | 冗余分片键，绑定分片 |
| 复杂查询 | ES双写 |
| 扩容 | 成倍扩容策略 |
