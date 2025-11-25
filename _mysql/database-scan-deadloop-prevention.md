---
title: "数据库扫表任务如何避免出现死循环？"
date: 2025-11-02
categories: [MySQL, 数据库实战]
tags: [MySQL, 扫表任务, 死循环, 批量处理]
description: "详解数据库扫表任务中死循环产生的原因及预防方案，包括游标翻页、数据变更感知、幂等性设计等实战技巧"
nav_order: 390
parent: 数据库MySQL
---
## 一、问题背景

**扫表任务**是指需要遍历处理数据库中所有或大量数据的场景，如：
- 数据迁移
- 批量修复脏数据
- 定时统计任务
- 历史数据归档

**死循环风险**：处理逻辑不当导致反复处理相同数据，永远无法完成。

## 二、死循环产生的典型场景

### 场景1：基于LIMIT的翻页问题（最常见）

#### 错误示例1：固定OFFSET翻页

```java
@Scheduled(cron = "0 0 2 * * ?")
public void scanAndUpdateUsers() {
    int pageSize = 1000;
    int offset = 0;
    
    while (true) {
        // 查询一页数据
        List<User> users = jdbcTemplate.query(
            "SELECT * FROM users LIMIT ? OFFSET ?",
            new UserRowMapper(), pageSize, offset
        );
        
        if (users.isEmpty()) {
            break;  // 没有更多数据
        }
        
        // 处理数据（包含UPDATE操作）
        for (User user : users) {
            if (needUpdate(user)) {
                // 问题：UPDATE可能改变排序，导致重复扫描
                jdbcTemplate.update(
                    "UPDATE users SET status = ? WHERE id = ?",
                    "processed", user.getId()
                );
            }
        }
        
        offset += pageSize;  // 移动到下一页
    }
}
```

**死循环原因**：
```
初始数据（按ID排序）：
ID: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10

第1页（OFFSET 0, LIMIT 3）: 1, 2, 3
处理完成，UPDATE id=2 的某个字段（如last_update_time）

如果查询有ORDER BY last_update_time，排序变化：
ID: 1, 3, 4, 5, 6, 7, 8, 9, 10, 2

第2页（OFFSET 3, LIMIT 3）: 5, 6, 7
问题：跳过了 id=4！

或者相反，如果UPDATE导致记录前移：
可能导致 id=2 在下一页再次被扫描（重复处理）
```

---

#### 错误示例2：基于时间戳的分页

```java
public void scanByTimestamp() {
    Date lastTimestamp = null;
    int pageSize = 1000;
    
    while (true) {
        List<User> users;
        if (lastTimestamp == null) {
            users = jdbcTemplate.query(
                "SELECT * FROM users ORDER BY create_time LIMIT ?",
                new UserRowMapper(), pageSize
            );
        } else {
            users = jdbcTemplate.query(
                "SELECT * FROM users WHERE create_time > ? ORDER BY create_time LIMIT ?",
                new UserRowMapper(), lastTimestamp, pageSize
            );
        }
        
        if (users.isEmpty()) {
            break;
        }
        
        // 处理数据
        processUsers(users);
        
        // 记录最后一条的时间戳
        lastTimestamp = users.get(users.size() - 1).getCreateTime();
    }
}
```

**死循环风险**：
```
假设有1000条记录的 create_time 都是 '2025-11-02 10:00:00'

第1页：查询 LIMIT 1000 → 返回前1000条
最后一条时间戳: 2025-11-02 10:00:00

第2页：WHERE create_time > '2025-11-02 10:00:00'
→ 跳过所有相同时间戳的记录
→ 漏掉数据！

或者如果条件改为 >=：
→ 重复处理相同时间戳的记录
→ 死循环！
```

---

### 场景2：基于标记位的重复处理

```java
public void processUnprocessedOrders() {
    while (true) {
        // 查询未处理的订单
        List<Order> orders = jdbcTemplate.query(
            "SELECT * FROM orders WHERE status = 'pending' LIMIT 1000",
            new OrderRowMapper()
        );
        
        if (orders.isEmpty()) {
            break;
        }
        
        for (Order order : orders) {
            try {
                // 处理订单
                processOrder(order);
                
                // 更新状态
                jdbcTemplate.update(
                    "UPDATE orders SET status = 'processed' WHERE id = ?",
                    order.getId()
                );
            } catch (Exception e) {
                // 问题：处理失败，状态未更新，下次继续查出来
                log.error("处理失败", e);
                // 可能导致死循环：反复处理同一条失败数据
            }
        }
    }
}
```

**死循环场景**：
- 某条订单处理必然失败（如数据异常）
- 状态未更新，下次扫描继续查出
- 反复处理同一条失败记录

---

### 场景3：数据被并发修改

```java
@Scheduled(fixedRate = 60000)
public void syncDataToES() {
    Long lastSyncId = getLastSyncId();  // 从Redis获取上次同步的ID
    
    while (true) {
        List<Product> products = jdbcTemplate.query(
            "SELECT * FROM products WHERE id > ? ORDER BY id LIMIT 1000",
            new ProductRowMapper(), lastSyncId
        );
        
        if (products.isEmpty()) {
            break;
        }
        
        // 同步到ES
        for (Product product : products) {
            elasticSearchService.index(product);
            lastSyncId = product.getId();  // 更新游标
        }
        
        // 保存游标到Redis
        saveLastSyncId(lastSyncId);
    }
}
```

**并发问题**：
```
时刻T1: 任务启动，lastSyncId=1000
时刻T2: 查询 WHERE id > 1000，获取 1001-2000
时刻T3: 正在处理中...
时刻T4: 另一个实例也启动，lastSyncId=1000（Redis未及时更新）
时刻T5: 第二个实例也查询 WHERE id > 1000
→ 重复处理！

或者更严重的情况：
时刻T6: 任务A处理完 id=1500
时刻T7: 任务B从 id=1000 开始，覆盖了游标
→ 永久循环在 1000-1500 之间
```

---

## 三、正确的解决方案

### 方案1：基于主键的游标遍历（推荐）

```java
@Service
public class UserScanService {
    
    public void scanAndProcess() {
        Long lastId = 0L;  // 从0开始
        int pageSize = 1000;
        
        while (true) {
            // 使用主键作为游标
            List<User> users = jdbcTemplate.query(
                "SELECT * FROM users WHERE id > ? ORDER BY id ASC LIMIT ?",
                new UserRowMapper(), lastId, pageSize
            );
            
            if (users.isEmpty()) {
                log.info("扫描完成，共处理 {} 条", totalProcessed);
                break;
            }
            
            // 处理数据
            for (User user : users) {
                processUser(user);
            }
            
            // 更新游标：取本批次最后一条的ID
            lastId = users.get(users.size() - 1).getId();
            
            log.info("处理批次完成，当前游标: {}", lastId);
        }
    }
    
    private void processUser(User user) {
        // 即使这里UPDATE了user表的其他字段
        // 也不影响下一次查询（因为主键不变）
        jdbcTemplate.update(
            "UPDATE users SET status = ?, updated_time = NOW() WHERE id = ?",
            "processed", user.getId()
        );
    }
}
```

**优势**：
- ✅ 主键不会因UPDATE改变
- ✅ 主键有索引，查询高效
- ✅ 不会漏数据或重复扫描
- ✅ 支持断点续传

---

### 方案2：分段加锁处理

```java
@Service
public class OrderProcessService {
    
    public void processOrders() {
        Long minId = getMinUnprocessedId();
        Long maxId = getMaxUnprocessedId();
        int batchSize = 1000;
        
        for (long startId = minId; startId <= maxId; startId += batchSize) {
            long endId = Math.min(startId + batchSize - 1, maxId);
            
            // 锁定ID范围
            List<Order> orders = jdbcTemplate.query(
                "SELECT * FROM orders " +
                "WHERE id BETWEEN ? AND ? AND status = 'pending' " +
                "FOR UPDATE",
                new OrderRowMapper(), startId, endId
            );
            
            for (Order order : orders) {
                try {
                    processOrder(order);
                    updateStatus(order.getId(), "processed");
                } catch (Exception e) {
                    // 标记为失败，避免死循环
                    updateStatus(order.getId(), "failed");
                    log.error("订单处理失败: {}", order.getId(), e);
                }
            }
        }
    }
    
    private Long getMinUnprocessedId() {
        return jdbcTemplate.queryForObject(
            "SELECT MIN(id) FROM orders WHERE status = 'pending'",
            Long.class
        );
    }
    
    private Long getMaxUnprocessedId() {
        return jdbcTemplate.queryForObject(
            "SELECT MAX(id) FROM orders WHERE status = 'pending'",
            Long.class
        );
    }
}
```

**关键点**：
- 先确定处理范围（minId ~ maxId）
- 按ID段遍历，避免动态查询
- 失败记录标记为 `failed` 而非继续保持 `pending`

---

### 方案3：使用处理时间戳+ID组合游标

```java
@Service
public class DataMigrationService {
    
    public void migrateData() {
        Timestamp lastTime = new Timestamp(0);
        Long lastId = 0L;
        int pageSize = 1000;
        
        while (true) {
            List<Data> dataList = jdbcTemplate.query(
                "SELECT * FROM source_table " +
                "WHERE (create_time > ?) OR (create_time = ? AND id > ?) " +
                "ORDER BY create_time, id " +
                "LIMIT ?",
                new DataRowMapper(), lastTime, lastTime, lastId, pageSize
            );
            
            if (dataList.isEmpty()) {
                break;
            }
            
            // 批量迁移
            batchInsertToTarget(dataList);
            
            // 更新游标：取最后一条的时间戳+ID
            Data lastData = dataList.get(dataList.size() - 1);
            lastTime = lastData.getCreateTime();
            lastId = lastData.getId();
        }
    }
}
```

**优势**：
- 解决时间戳重复问题（通过ID辅助）
- 支持按时间范围筛选
- 适合增量同步场景

**索引要求**：
```sql
CREATE INDEX idx_time_id ON source_table (create_time, id);
```

---

### 方案4：基于快照的扫描

```java
@Service
public class SnapshotScanService {
    
    public void scanWithSnapshot() {
        // 1. 创建待处理ID快照表
        jdbcTemplate.update(
            "CREATE TEMPORARY TABLE tmp_scan_ids AS " +
            "SELECT id FROM users WHERE status = 'pending'"
        );
        
        Long lastId = 0L;
        int batchSize = 1000;
        
        while (true) {
            // 2. 从快照表中取ID
            List<Long> ids = jdbcTemplate.queryForList(
                "SELECT id FROM tmp_scan_ids " +
                "WHERE id > ? ORDER BY id LIMIT ?",
                Long.class, lastId, batchSize
            );
            
            if (ids.isEmpty()) {
                break;
            }
            
            // 3. 根据ID列表处理
            List<User> users = jdbcTemplate.query(
                "SELECT * FROM users WHERE id IN (" +
                ids.stream().map(String::valueOf).collect(Collectors.joining(",")) +
                ")",
                new UserRowMapper()
            );
            
            for (User user : users) {
                processUser(user);
            }
            
            lastId = ids.get(ids.size() - 1);
        }
        
        // 4. 清理快照表
        jdbcTemplate.update("DROP TEMPORARY TABLE tmp_scan_ids");
    }
}
```

**优势**：
- 完全避免数据变更影响
- 处理范围固定，必然终止
- 适合复杂条件筛选

---

### 方案5：幂等性设计+重试上限

```java
@Service
public class IdempotentProcessService {
    
    public void processWithRetryLimit() {
        int maxRetry = 3;
        
        while (true) {
            List<Task> tasks = jdbcTemplate.query(
                "SELECT * FROM tasks " +
                "WHERE status = 'pending' AND retry_count < ? " +
                "LIMIT 1000",
                new TaskRowMapper(), maxRetry
            );
            
            if (tasks.isEmpty()) {
                break;
            }
            
            for (Task task : tasks) {
                try {
                    // 幂等性处理
                    processTask(task);
                    
                    jdbcTemplate.update(
                        "UPDATE tasks SET status = 'success', retry_count = 0 WHERE id = ?",
                        task.getId()
                    );
                } catch (Exception e) {
                    // 增加重试次数
                    jdbcTemplate.update(
                        "UPDATE tasks SET retry_count = retry_count + 1 WHERE id = ?",
                        task.getId()
                    );
                    
                    log.error("任务处理失败，当前重试次数: {}", task.getRetryCount() + 1, e);
                    
                    // 达到重试上限，标记为失败
                    if (task.getRetryCount() + 1 >= maxRetry) {
                        jdbcTemplate.update(
                            "UPDATE tasks SET status = 'failed' WHERE id = ?",
                            task.getId()
                        );
                    }
                }
            }
        }
    }
    
    private void processTask(Task task) {
        // 幂等性实现：重复执行结果一致
        // 例如：使用唯一键约束防止重复插入
        jdbcTemplate.update(
            "INSERT INTO result_table (task_id, result) VALUES (?, ?) " +
            "ON DUPLICATE KEY UPDATE result = VALUES(result)",
            task.getId(), calculateResult(task)
        );
    }
}
```

**表结构**：
```sql
CREATE TABLE tasks (
    id BIGINT PRIMARY KEY,
    status VARCHAR(20),     -- pending/success/failed
    retry_count INT DEFAULT 0,
    create_time DATETIME,
    INDEX idx_status_retry (status, retry_count)
);
```

---

### 方案6：分布式锁防止并发执行

```java
@Service
public class DistributedScanService {
    
    @Autowired
    private RedissonClient redissonClient;
    
    @Scheduled(cron = "0 0 2 * * ?")
    public void scheduledScan() {
        RLock lock = redissonClient.getLock("scan_task_lock");
        
        try {
            // 尝试获取锁，最多等待0秒，锁自动释放时间10分钟
            boolean acquired = lock.tryLock(0, 600, TimeUnit.SECONDS);
            
            if (!acquired) {
                log.warn("扫表任务已在其他实例执行，跳过");
                return;
            }
            
            log.info("获取锁成功，开始扫表");
            scanAndProcess();
            
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
    
    private void scanAndProcess() {
        // 使用方案1的主键游标遍历
        // ...
    }
}
```

---

## 四、生产环境最佳实践

### 1. 完整的扫表任务模板

```java
@Service
public class ProductionScanTemplate {
    
    @Autowired
    private JdbcTemplate jdbcTemplate;
    
    @Autowired
    private RedissonClient redissonClient;
    
    public ScanResult scanAndProcess(ScanConfig config) {
        RLock lock = redissonClient.getLock("scan:" + config.getTaskName());
        
        try {
            // 1. 获取分布式锁
            if (!lock.tryLock(0, config.getLockTimeout(), TimeUnit.SECONDS)) {
                return ScanResult.skipped("任务已在执行");
            }
            
            // 2. 恢复上次游标
            Long lastId = getLastCursor(config.getTaskName());
            
            int totalProcessed = 0;
            int failedCount = 0;
            
            while (true) {
                // 3. 批量查询
                List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    config.getQuerySql(), lastId, config.getBatchSize()
                );
                
                if (rows.isEmpty()) {
                    break;
                }
                
                // 4. 批量处理
                for (Map<String, Object> row : rows) {
                    try {
                        config.getProcessor().accept(row);
                        totalProcessed++;
                    } catch (Exception e) {
                        failedCount++;
                        log.error("处理失败: {}", row, e);
                        
                        if (failedCount > config.getMaxFailures()) {
                            throw new RuntimeException("失败次数超过阈值，任务中止");
                        }
                    }
                }
                
                // 5. 更新游标
                lastId = (Long) rows.get(rows.size() - 1).get("id");
                saveCursor(config.getTaskName(), lastId);
                
                // 6. 速率限制
                if (config.getRateLimitMs() > 0) {
                    Thread.sleep(config.getRateLimitMs());
                }
            }
            
            return ScanResult.success(totalProcessed, failedCount);
            
        } catch (Exception e) {
            return ScanResult.failed(e.getMessage());
        } finally {
            if (lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
    
    private Long getLastCursor(String taskName) {
        String key = "scan_cursor:" + taskName;
        String value = redisTemplate.opsForValue().get(key);
        return value != null ? Long.parseLong(value) : 0L;
    }
    
    private void saveCursor(String taskName, Long cursor) {
        String key = "scan_cursor:" + taskName;
        redisTemplate.opsForValue().set(key, cursor.toString(), 7, TimeUnit.DAYS);
    }
}
```

**使用示例**：
```java
ScanConfig config = ScanConfig.builder()
    .taskName("update_user_level")
    .querySql("SELECT * FROM users WHERE id > ? ORDER BY id LIMIT ?")
    .batchSize(1000)
    .processor(row -> updateUserLevel((Long) row.get("id")))
    .maxFailures(100)
    .rateLimitMs(100)  // 每批次间隔100ms
    .lockTimeout(600)
    .build();

ScanResult result = scanTemplate.scanAndProcess(config);
```

---

### 2. 监控与告警

```java
@Component
public class ScanTaskMonitor {
    
    @Scheduled(fixedRate = 60000)
    public void checkStuckTasks() {
        List<TaskMetric> metrics = jdbcTemplate.query(
            "SELECT task_name, last_cursor, update_time " +
            "FROM scan_task_progress",
            new TaskMetricRowMapper()
        );
        
        for (TaskMetric metric : metrics) {
            long idleMinutes = Duration.between(
                metric.getUpdateTime(), Instant.now()
            ).toMinutes();
            
            if (idleMinutes > 30) {
                // 30分钟未更新，可能死循环或卡死
                alertService.send(String.format(
                    "扫表任务 %s 超过30分钟未更新游标，请检查！当前游标: %d",
                    metric.getTaskName(), metric.getLastCursor()
                ));
            }
        }
    }
}
```

---

## 五、答题总结

**面试回答框架**：

1. **问题识别**：  
   "扫表任务死循环主要由三类原因导致：一是基于OFFSET或时间戳翻页时，UPDATE改变排序导致重复扫描；二是处理失败但状态未更新，反复查出同一条数据；三是并发执行时游标冲突"

2. **核心方案**：  
   "最可靠的方法是使用主键作为游标，WHERE id > ? ORDER BY id LIMIT ?，主键不会因UPDATE改变且有索引，既高效又不会漏数据"

3. **异常处理**：  
   "处理失败的记录要标记为failed或增加retry_count，设置重试上限，避免永远停留在pending状态造成死循环"

4. **生产实践**：  
   "生产环境还需要加分布式锁防并发、保存游标支持断点续传、监控任务进度，发现长时间未更新要告警"

**关键点**：
- 理解基于OFFSET翻页的问题
- 掌握主键游标遍历方案
- 强调幂等性和重试上限设计
- 能说出完整的异常处理策略

