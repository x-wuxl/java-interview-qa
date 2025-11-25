---
layout: default
title: "百万级及以上数据如何安全删除？"
parent: 数据库MySQL
nav_order: 397
description: 探讨在 MySQL 中删除百万级海量数据的安全策略，避免锁表和主从延迟。
---
## 1. 核心概念

在 MySQL 中直接执行 `DELETE FROM table WHERE ...` 删除大量数据（如百万级）是非常危险的操作。这会导致：
1.  **大事务锁表**：长时间占用锁，甚至升级为表锁，阻塞其他业务的读写。
2.  **Undo Log 暴涨**：事务回滚段急剧膨胀，占用磁盘空间。
3.  **主从延迟**：大事务同步到从库回放时，会导致从库长时间延迟。
4.  **Buffer Pool 污染**：大量数据加载到内存，挤占热点数据。

## 2. 安全删除策略

### 2.1 分批删除（推荐）

将一个大 `DELETE` 拆分为多个小 `DELETE`，每次删除少量数据（如 1000-5000 行），并在中间短暂 `sleep`，释放资源。

```java
// 伪代码示例
while (true) {
    // 每次删除 5000 条，通过主键范围或 Limit 控制
    int affectedRows = execute("DELETE FROM logs WHERE create_time < '2023-01-01' LIMIT 5000");
    if (affectedRows == 0) {
        break;
    }
    // 暂停 50ms，让出 CPU 和 IO，允许其他事务执行
    Thread.sleep(50);
}
```

**关键点：**
- 务必加 `LIMIT`。
- 尽量利用主键索引删除（如 `WHERE id < X`），避免全表扫描。

### 2.2 换表策略（删除全表或绝大部分数据）

如果需要删除表中 **90% 以上** 的数据，或者直接清空表，使用 `DELETE` 效率极低。

**方案 A：TRUNCATE（全表清空）**
```sql
TRUNCATE TABLE logs;
```
- **优点**：速度极快，直接释放磁盘空间。
- **缺点**：不可回滚，不记录单行 binlog。

**方案 B：保留数据迁移 + RENAME（删除大部分）**
如果只需保留少量数据（如最近 1 个月），可以：
1.  创建新表 `logs_new` (结构同 `logs`)。
2.  将需要保留的数据插入新表：`INSERT INTO logs_new SELECT * FROM logs WHERE date > '...'`。
3.  原子重命名：
    ```sql
    RENAME TABLE logs TO logs_old, logs_new TO logs;
    ```
4.  删除旧表：`DROP TABLE logs_old;`

### 2.3 硬删除 vs 软删除

在业务设计层面，通常建议 **软删除**（逻辑删除）：
```sql
UPDATE users SET is_deleted = 1 WHERE id = 100;
```
- **优点**：数据可恢复，操作快（索引更新）。
- **缺点**：表数据量持续增长，查询需带 `is_deleted=0`。
- **配合**：定期归档历史数据到历史库（HBase/TiDB/冷备库），然后物理删除主库旧数据。

## 3. 总结

| 场景 | 推荐方案 | 风险点 |
| :--- | :--- | :--- |
| **删除少量数据** | 直接 `DELETE` | 需命中索引 |
| **删除海量数据 (部分)** | **分批 DELETE + Sleep** | 循环次数多，需控制批次大小 |
| **删除海量数据 (大部分)** | **数据迁移 + RENAME** | 切换瞬间可能有短暂影响 |
| **清空全表** | `TRUNCATE` | 不可回滚 |

**面试回答示例：**
"处理百万级数据删除时，绝对不能直接执行不带 Limit 的 Delete 语句。这会引发长事务、锁表和主从延迟。
我的常用方案是：
1.  **分批删除**：写脚本循环 `DELETE ... LIMIT 5000`，每次执行后 Sleep 几十毫秒，释放锁资源。
2.  **换表法**：如果删除的数据占比很高（如只保留最近一月），我会把保留数据导入新表，然后 `RENAME` 切换，最后 `DROP` 旧表，这样效率最高且不产生碎片。"
