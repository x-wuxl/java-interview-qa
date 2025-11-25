---
title: "MySQL是AP的还是CP的系统？"
date: 2025-11-02
description: "从CAP定理角度分析MySQL在不同架构下的特性，深入理解单机、主从、MGR的一致性与可用性权衡"
author: "wuxl"
categories: [数据库]
tags: [MySQL, CAP定理, 分布式, 一致性]
nav_order: 382
parent: 数据库MySQL
---
## 问题

MySQL是AP的还是CP的系统？

## 答案

### 核心概念回顾：CAP定理

CAP定理指分布式系统无法同时满足三个特性：
- **C (Consistency)**：一致性，所有节点同一时刻看到的数据相同
- **A (Availability)**：可用性，系统始终能响应请求
- **P (Partition Tolerance)**：分区容错性，网络分区时系统仍能工作

分布式系统必须容忍分区（P），因此只能在**CP（一致性优先）**或**AP（可用性优先）**之间选择。

### MySQL的CAP特性分析

**结论：MySQL的CAP特性取决于具体架构**

#### 1. 单机MySQL：不涉及CAP

单机MySQL不是分布式系统，不存在网络分区问题，因此**CAP定理不适用**。

- 支持ACID事务，保证单机强一致性
- 单点故障会导致不可用

#### 2. MySQL主从架构：AP系统

**默认配置（异步复制）：**

```
主库  ----异步复制---->  从库1
                  \---->  从库2
```

**特性分析：**
- **可用性优先（A）**：主库宕机后，可快速将从库提升为主库，继续服务
- **放弃强一致性（C）**：存在主从延迟，从库数据可能落后主库
- **最终一致性**：延迟消除后，数据最终一致

**网络分区场景：**
```
网络分区发生：
  分区1: 主库（继续写入）
  分区2: 从库（停止同步，但可读）

结果：
- 主库和从库都可用（A）
- 数据不一致（丧失C）
- 属于AP系统
```

**实际表现：**
```sql
-- 主库写入
INSERT INTO orders VALUES (1, 'order_1');  -- 成功

-- 从库查询（延迟1秒）
SELECT * FROM orders WHERE id = 1;  -- 查不到（数据不一致）
```

#### 3. MySQL半同步复制：弱CP

**配置半同步：**
```properties
# 主库
rpl_semi_sync_master_enabled=1
rpl_semi_sync_master_timeout=1000  -- 1秒超时

# 从库
rpl_semi_sync_slave_enabled=1
```

**工作流程：**
```
主库提交事务 → 至少一个从库确认接收binlog → 主库返回成功
```

**特性分析：**
- **部分一致性（弱C）**：保证至少一个从库有最新数据
- **部分可用性（弱A）**：超时后降级为异步复制，保证可用性
- **属于AP偏向CP的中间态**

**网络分区场景：**
```
分区发生，主库无法联系从库：
- 超时前：写入阻塞（偏向C）
- 超时后：降级为异步复制（偏向A）
```

#### 4. MySQL Group Replication（MGR）：CP系统

**MGR架构：**
```
节点1 ←→ 节点2 ←→ 节点3
   ↖       ↑       ↗
     Paxos共识协议
```

**配置示例：**
```properties
plugin-load-add=group_replication.so
group_replication_group_name="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
group_replication_start_on_boot=off
group_replication_bootstrap_group=off
```

**特性分析：**
- **强一致性（C）**：基于Paxos协议，多数节点确认后才提交
- **牺牲可用性（A）**：网络分区时，少数派分区不可写（只读）
- **属于CP系统**

**网络分区场景：**
```
3节点分裂为 [节点1] 和 [节点2, 节点3]：
- 多数派（节点2、3）：继续提供读写服务（保持C）
- 少数派（节点1）：自动切换为只读模式（牺牲A）
```

**实际表现：**
```sql
-- 多数派节点：写入成功
INSERT INTO orders VALUES (1, 'order_1');  -- OK

-- 少数派节点：写入失败
INSERT INTO orders VALUES (2, 'order_2');
-- ERROR: The MySQL server is running with the --super-read-only option
```

### 对比总结表

| 架构模式 | CAP特性 | 一致性级别 | 可用性 | 适用场景 |
|---------|--------|-----------|-------|---------|
| 单机MySQL | N/A | 强一致 | 低 | 小型应用 |
| 异步复制 | **AP** | 最终一致 | 高 | 读多写少、容忍延迟 |
| 半同步复制 | 弱CP/AP | 准强一致 | 中高 | 对数据可靠性有一定要求 |
| MGR | **CP** | 强一致 | 中 | 金融、支付等强一致场景 |

### 业务选型建议

**选择AP（异步/半同步复制）：**
```java
// 适用场景
- 社交媒体内容浏览（点赞数延迟几秒无影响）
- 商品列表查询（库存稍有延迟可接受）
- 日志分析、报表统计

// 代码示例：读写分离
@Service
public class OrderService {
    @Autowired
    private MasterDataSource master;

    @Autowired
    private SlaveDataSource slave;

    public void createOrder(Order order) {
        master.insert(order);  // 写主库
    }

    public List<Order> listOrders() {
        return slave.query();  // 读从库（容忍延迟）
    }
}
```

**选择CP（MGR）：**
```java
// 适用场景
- 账户余额扣减（不能出现数据不一致）
- 订单支付状态（必须强一致）
- 库存扣减（超卖会造成损失）

// 代码示例：强一致性保证
@Transactional
public void deductBalance(Long userId, BigDecimal amount) {
    // MGR保证多节点强一致，不会出现数据分歧
    accountMapper.updateBalance(userId, amount);
}
```

### 实践中的权衡

大多数互联网应用采用**混合架构**：
```
核心业务（账户、支付） → MySQL MGR（CP）
非核心业务（浏览、评论） → 主从复制（AP） + 缓存
```

### 面试答题总结

MySQL不是天然的AP或CP系统，**取决于部署架构**：
- **主从异步复制**：AP系统，优先可用性，最终一致性，适合读多写少场景
- **半同步复制**：介于AP和CP之间，超时降级保证可用性
- **MGR（组复制）**：CP系统，基于Paxos保证强一致性，网络分区时少数派不可写，适合金融等强一致场景

实际应用中需要根据业务特点（强一致 vs 高可用）选择合适的架构方案。
