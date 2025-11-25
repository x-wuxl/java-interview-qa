---
layout: default
title: "如何保证 ES 和数据库的数据一致性？"
parent: ElasticSearch
nav_order: 576
description: "深入探讨 ElasticSearch 与 MySQL 数据同步的一致性保证方案"
date: 2025-11-02
---
## 核心概念

在实际业务中，通常使用 **MySQL 作为主数据存储**，**ElasticSearch 作为搜索引擎**。由于 ES 不支持事务，且是独立的系统，如何保证两者数据一致性是常见的技术挑战。

## 一致性等级

根据业务需求，数据一致性可分为：

| 一致性级别 | 说明 | 适用场景 |
|-----------|------|---------|
| **强一致性** | 实时同步，数据完全一致 | 金融交易、库存扣减 |
| **最终一致性** | 允许短暂延迟，最终达到一致 | 电商搜索、内容检索 |
| **弱一致性** | 允许数据不一致 | 日志分析、离线统计 |

**大多数搜索场景追求最终一致性**，允许秒级或分钟级延迟。

## 方案一：同步双写（不推荐）

### 1. 实现方式

```java
@Transactional
public void createProduct(Product product) {
    // 1. 写入 MySQL
    productMapper.insert(product);
    
    // 2. 写入 ElasticSearch
    IndexRequest request = new IndexRequest("products")
        .id(product.getId().toString())
        .source(convertToJson(product), XContentType.JSON);
    esClient.index(request, RequestOptions.DEFAULT);
}
```

### 2. 问题分析

#### **问题 1：无法保证原子性**
- MySQL 事务提交后，ES 写入失败 → **数据不一致**
- ES 写入成功后，MySQL 事务回滚 → **数据不一致**

#### **问题 2：性能影响**
- ES 写入增加接口响应时间
- ES 故障会导致业务不可用

#### **问题 3：分布式事务复杂**
- 需要引入 2PC、TCC、Saga 等分布式事务方案
- 复杂度高，性能差

### 3. 适用场景
- **数据量小**，性能要求不高
- **强一致性要求**，且能接受性能损耗

---

## 方案二：异步双写（MQ）

### 1. 架构设计

```
Application → MySQL (事务提交)
           → MQ (发送消息)

MQ Consumer → ElasticSearch (异步写入)
```

### 2. 实现示例

#### **生产者（业务代码）**
```java
@Transactional
public void createProduct(Product product) {
    // 1. 写入 MySQL
    productMapper.insert(product);
    
    // 2. 发送 MQ 消息（本地事务提交后）
    ProductMessage message = new ProductMessage(product.getId(), "CREATE", product);
    mqProducer.sendMessage("product-sync-topic", message);
}
```

#### **消费者（同步服务）**
```java
@RocketMQMessageListener(topic = "product-sync-topic", consumerGroup = "es-sync-group")
public class EsSyncConsumer implements RocketMQListener<ProductMessage> {
    
    @Override
    public void onMessage(ProductMessage message) {
        try {
            switch (message.getAction()) {
                case "CREATE":
                case "UPDATE":
                    IndexRequest request = new IndexRequest("products")
                        .id(message.getId().toString())
                        .source(convertToJson(message.getProduct()), XContentType.JSON);
                    esClient.index(request, RequestOptions.DEFAULT);
                    break;
                case "DELETE":
                    DeleteRequest request = new DeleteRequest("products", message.getId().toString());
                    esClient.delete(request, RequestOptions.DEFAULT);
                    break;
            }
        } catch (Exception e) {
            // 重试或记录失败日志
            log.error("ES 同步失败: {}", message, e);
            throw new RuntimeException("ES sync failed", e); // 触发消息重试
        }
    }
}
```

### 3. 问题与优化

#### **问题 1：消息丢失**
- **解决**：使用可靠 MQ（RocketMQ、Kafka）+ 消息持久化
- **解决**：消费者 ACK 机制，失败自动重试

#### **问题 2：消息重复消费**
- **解决**：ES 操作幂等（使用文档 ID 作为唯一标识）

```java
// 使用文档 ID 保证幂等
IndexRequest request = new IndexRequest("products")
    .id(product.getId().toString())  // 指定 ID，重复写入会覆盖
    .source(convertToJson(product), XContentType.JSON);
```

#### **问题 3：顺序性问题**
- **解决**：使用消息的 Partition Key（按商品 ID 分区）
- **解决**：在 ES 文档中记录版本号

```java
// 方案一：消息分区（保证同一商品的消息顺序）
mqProducer.sendMessage("product-sync-topic", message, product.getId().toString());

// 方案二：乐观锁（ES 文档带版本号）
IndexRequest request = new IndexRequest("products")
    .id(product.getId().toString())
    .source(Map.of(
        "id", product.getId(),
        "name", product.getName(),
        "version", product.getVersion()  // 版本号
    ), XContentType.JSON);
```

### 4. 优缺点

**优点**：
- 解耦，ES 故障不影响主业务
- 异步处理，性能好
- 支持重试和容错

**缺点**：
- 存在延迟（秒级）
- 需要引入 MQ，增加复杂度
- 需要处理消息顺序性和幂等性

---

## 方案三：Binlog 监听（推荐）

### 1. 架构设计

```
MySQL → Binlog → Canal/Debezium/Flink CDC
                     ↓
                 消息队列（可选）
                     ↓
              ElasticSearch
```

### 2. 使用 Canal 实现

#### **Canal Server 配置**
```properties
# canal.properties
canal.instance.master.address=127.0.0.1:3306
canal.instance.dbUsername=canal
canal.instance.dbPassword=canal
canal.instance.filter.regex=.*\\.products  # 监听 products 表
```

#### **Canal Client 代码**
```java
@Component
public class CanalClient {
    
    @PostConstruct
    public void start() {
        CanalConnector connector = CanalConnectors.newSingleConnector(
            new InetSocketAddress("127.0.0.1", 11111), "example", "", "");
        
        connector.connect();
        connector.subscribe(".*\\.products");
        connector.rollback();
        
        while (true) {
            Message message = connector.getWithoutAck(100); // 批量获取
            long batchId = message.getId();
            List<CanalEntry.Entry> entries = message.getEntries();
            
            if (entries.isEmpty()) {
                Thread.sleep(1000);
                continue;
            }
            
            for (CanalEntry.Entry entry : entries) {
                if (entry.getEntryType() == CanalEntry.EntryType.ROWDATA) {
                    handleRowChange(entry);
                }
            }
            
            connector.ack(batchId); // 确认消费
        }
    }
    
    private void handleRowChange(CanalEntry.Entry entry) {
        CanalEntry.RowChange rowChange = CanalEntry.RowChange.parseFrom(entry.getStoreValue());
        CanalEntry.EventType eventType = rowChange.getEventType();
        
        for (CanalEntry.RowData rowData : rowChange.getRowDatasList()) {
            switch (eventType) {
                case INSERT:
                case UPDATE:
                    Map<String, String> data = rowData.getAfterColumnsList().stream()
                        .collect(Collectors.toMap(
                            CanalEntry.Column::getName,
                            CanalEntry.Column::getValue
                        ));
                    syncToES(data.get("id"), data, "INDEX");
                    break;
                case DELETE:
                    String id = rowData.getBeforeColumnsList().stream()
                        .filter(col -> col.getName().equals("id"))
                        .findFirst()
                        .map(CanalEntry.Column::getValue)
                        .orElse(null);
                    syncToES(id, null, "DELETE");
                    break;
            }
        }
    }
    
    private void syncToES(String id, Map<String, String> data, String action) {
        try {
            if ("INDEX".equals(action)) {
                IndexRequest request = new IndexRequest("products")
                    .id(id)
                    .source(data, XContentType.JSON);
                esClient.index(request, RequestOptions.DEFAULT);
            } else if ("DELETE".equals(action)) {
                DeleteRequest request = new DeleteRequest("products", id);
                esClient.delete(request, RequestOptions.DEFAULT);
            }
        } catch (Exception e) {
            log.error("ES 同步失败: id={}, action={}", id, action, e);
            // 重试或记录失败日志
        }
    }
}
```

### 3. 使用 Flink CDC 实现（企业级）

```java
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

// 1. 创建 MySQL CDC Source
MySqlSource<Product> mySqlSource = MySqlSource.<Product>builder()
    .hostname("localhost")
    .port(3306)
    .databaseList("ecommerce")
    .tableList("ecommerce.products")
    .username("root")
    .password("password")
    .deserializer(new JsonDebeziumDeserializationSchema())
    .build();

// 2. 读取 Binlog 流
DataStreamSource<Product> stream = env.fromSource(mySqlSource, 
    WatermarkStrategy.noWatermarks(), "MySQL Source");

// 3. 写入 ElasticSearch
stream.sinkTo(ElasticsearchSink.<Product>builder()
    .setHosts(new HttpHost("localhost", 9200, "http"))
    .setEmitter((product, ctx, indexer) -> {
        indexer.add(new IndexRequest("products")
            .id(product.getId().toString())
            .source(convertToJson(product), XContentType.JSON));
    })
    .build());

env.execute("MySQL to ES Sync");
```

### 4. 优缺点

**优点**：
- **业务无侵入**，不需要修改业务代码
- **数据完整**，捕获所有数据变更（包括非业务代码触发的变更）
- **延迟低**，准实时同步（毫秒级到秒级）
- **可靠性高**，Binlog 持久化，支持断点续传

**缺点**：
- 需要开启 MySQL Binlog（ROW 格式）
- 增加运维复杂度（Canal/Flink CDC 集群）
- DDL 变更需要同步处理（表结构变更）

---

## 方案四：定时任务全量/增量同步

### 1. 增量同步

```java
@Scheduled(fixedDelay = 60000) // 每分钟执行一次
public void incrementalSync() {
    // 查询最近 1 分钟更新的数据
    List<Product> products = productMapper.selectByUpdateTime(
        LocalDateTime.now().minusMinutes(1)
    );
    
    // 批量写入 ES
    BulkRequest bulkRequest = new BulkRequest();
    for (Product product : products) {
        bulkRequest.add(new IndexRequest("products")
            .id(product.getId().toString())
            .source(convertToJson(product), XContentType.JSON));
    }
    esClient.bulk(bulkRequest, RequestOptions.DEFAULT);
}
```

### 2. 全量同步（兜底）

```java
@Scheduled(cron = "0 0 3 * * ?") // 每天凌晨 3 点执行
public void fullSync() {
    int pageSize = 1000;
    int offset = 0;
    
    while (true) {
        List<Product> products = productMapper.selectByPage(offset, pageSize);
        if (products.isEmpty()) {
            break;
        }
        
        // 批量写入 ES
        BulkRequest bulkRequest = new BulkRequest();
        for (Product product : products) {
            bulkRequest.add(new IndexRequest("products")
                .id(product.getId().toString())
                .source(convertToJson(product), XContentType.JSON));
        }
        esClient.bulk(bulkRequest, RequestOptions.DEFAULT);
        
        offset += pageSize;
    }
}
```

### 3. 优缺点

**优点**：
- 实现简单，适合小数据量
- 全量同步可作为兜底方案

**缺点**：
- 延迟较高（分钟级）
- 增量同步可能遗漏数据（依赖 update_time 字段）
- 全量同步消耗资源大

---

## 数据一致性保证

### 1. 幂等性保证
- ES 使用文档 ID，重复写入自动覆盖
- 消费者端去重（Redis 去重表）

### 2. 数据校验与修复
```java
// 定期校验 MySQL 和 ES 的数据一致性
@Scheduled(cron = "0 0 4 * * ?")
public void checkConsistency() {
    // 1. 查询 MySQL 数据
    List<Product> mysqlProducts = productMapper.selectAll();
    
    // 2. 查询 ES 数据
    SearchRequest request = new SearchRequest("products");
    request.source(new SearchSourceBuilder().size(10000));
    SearchResponse response = esClient.search(request, RequestOptions.DEFAULT);
    
    // 3. 对比差异，记录不一致的数据
    Set<String> esIds = Arrays.stream(response.getHits().getHits())
        .map(SearchHit::getId)
        .collect(Collectors.toSet());
    
    for (Product product : mysqlProducts) {
        if (!esIds.contains(product.getId().toString())) {
            log.warn("数据不一致，MySQL 存在但 ES 缺失: {}", product.getId());
            // 修复：重新同步到 ES
            syncToES(product);
        }
    }
}
```

### 3. 监控与告警
- 监控同步延迟（MySQL Binlog 位点 vs 消费进度）
- 监控失败数（ES 写入失败计数）
- 定期全量对账

---

## 方案选型建议

| 方案 | 适用场景 | 一致性 | 复杂度 |
|------|---------|--------|--------|
| **同步双写** | 强一致性要求、数据量小 | 强一致 | 低 |
| **异步双写（MQ）** | 最终一致性、中等数据量 | 最终一致 | 中 |
| **Binlog 监听** | 最终一致性、大数据量、企业级 | 最终一致 | 高 |
| **定时任务** | 弱一致性、小数据量、兜底 | 弱一致 | 低 |

### 推荐方案
- **中小型项目**：异步双写（MQ）
- **大型项目**：Binlog 监听（Canal/Flink CDC）+ 定时全量同步（兜底）

---

## 总结

保证 ES 和 MySQL 数据一致性的核心是：

1. **选择合适的一致性级别**：大多数搜索场景接受最终一致性
2. **保证幂等性**：使用文档 ID，重复操作不影响结果
3. **做好监控和修复**：定期对账，及时发现和修复不一致
4. **考虑业务容错**：搜索结果允许短暂不准确

**面试要点**：
- 说明 MySQL 是主数据源，ES 是从数据源
- 重点介绍 **Binlog 监听方案**（Canal/Flink CDC）
- 提及幂等性、数据校验、监控告警等保证手段
- 可结合项目实际说明方案选型（如 MQ 异步双写）

