---
layout: default
title: "MySQL主从复制详解"
parent: 数据库MySQL
nav_order: 376
description: "全面解析MySQL主从复制的架构、配置步骤、复制模式、应用场景以及常见问题排查"
author: "wuxl"
date: 2025-11-02
---
## 问题

MySQL主从复制的架构和实现方式是什么？

## 答案

### 核心概念

MySQL主从复制（Master-Slave Replication）是一种**数据同步技术**，通过将主库的数据变更复制到一个或多个从库，实现**数据备份、读写分离、高可用**等目标。

### 主从复制的架构

#### 1. 一主多从架构（最常见）
```
        主库（Master）
         /  |  \
        /   |   \
     从库1 从库2 从库3
     (Slave) (Slave) (Slave)
```

**特点：**
- 主库负责写入
- 从库负责读取（读写分离）
- 可横向扩展从库提升读性能

#### 2. 级联复制架构
```
     主库（Master）
        ↓
     从库1（Slave & Master）
      /     \
   从库2   从库3
```

**特点：**
- 减轻主库复制压力
- 从库1既是从库也是其他从库的主库
- 延迟会累加

#### 3. 双主复制（互为主从）
```
   主库A ←→ 主库B
   (互为主从)
```

**特点：**
- 两个库都可写
- 需要避免主键冲突（自增步长错开）
- 存在数据冲突风险

### 复制的完整流程

```
主库（Master）                    从库（Slave）
     |                                |
1. 执行SQL语句                        |
     ↓                                |
2. 写入binlog                         |
     ↓                                |
3. [Dump Thread] --------binlog----→ 4. [IO Thread]
                                      ↓
                                 5. 写入relay log
                                      ↓
                                 6. [SQL Thread]
                                      ↓
                                 7. 执行SQL，同步数据
```

**三个核心线程：**
1. **Binlog Dump Thread（主库）**：读取binlog并发送给从库
2. **IO Thread（从库）**：接收binlog并写入relay log
3. **SQL Thread（从库）**：读取relay log并执行SQL

### 主从复制的配置

#### 1. 主库配置

**my.cnf配置：**
```properties
[mysqld]
# 开启binlog
log-bin=mysql-bin

# 服务器唯一ID（集群内不重复）
server-id=1

# binlog格式（ROW推荐）
binlog_format=ROW

# binlog保留时间（秒）
expire_logs_days=7

# 需要复制的数据库（可选）
binlog-do-db=mydb

# 不需要复制的数据库（可选）
binlog-ignore-db=mysql
binlog-ignore-db=information_schema
```

**创建复制账号：**
```sql
-- 创建专用复制用户
CREATE USER 'repl'@'%' IDENTIFIED BY 'Repl@123456';

-- 授予复制权限
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';

-- 刷新权限
FLUSH PRIVILEGES;

-- 查看主库状态
SHOW MASTER STATUS;
-- 记录File和Position，从库需要用到
+------------------+----------+--------------+------------------+
| File             | Position | Binlog_Do_DB | Binlog_Ignore_DB |
+------------------+----------+--------------+------------------+
| mysql-bin.000003 |      154 |              |                  |
+------------------+----------+--------------+------------------+
```

#### 2. 从库配置

**my.cnf配置：**
```properties
[mysqld]
# 服务器唯一ID（与主库不同）
server-id=2

# 开启relay log
relay-log=mysql-relay-bin

# 从库只读（可选，推荐）
read_only=1

# super用户仍可写（更安全）
super_read_only=1

# relay log自动恢复
relay_log_recovery=ON

# 并行复制（MySQL 5.7+）
slave-parallel-type=LOGICAL_CLOCK
slave-parallel-workers=4
```

**配置复制关系：**
```sql
-- 停止从库（如果已启动）
STOP SLAVE;

-- 配置主库信息
CHANGE MASTER TO
  MASTER_HOST='192.168.1.100',        -- 主库IP
  MASTER_PORT=3306,                   -- 主库端口
  MASTER_USER='repl',                 -- 复制用户
  MASTER_PASSWORD='Repl@123456',      -- 复制密码
  MASTER_LOG_FILE='mysql-bin.000003', -- 主库binlog文件
  MASTER_LOG_POS=154;                 -- 主库binlog位置

-- 启动从库
START SLAVE;

-- 查看从库状态
SHOW SLAVE STATUS\G

-- 关键指标
Slave_IO_Running: Yes           -- IO线程运行正常
Slave_SQL_Running: Yes          -- SQL线程运行正常
Seconds_Behind_Master: 0        -- 延迟秒数
Last_IO_Error:                  -- IO错误信息
Last_SQL_Error:                 -- SQL错误信息
```

### 基于GTID的复制（推荐）

**GTID（Global Transaction Identifier）**是全局事务ID，MySQL 5.6+支持，简化复制配置。

#### GTID的优势
- 无需手动指定binlog文件和位置
- 主库切换更简单
- 自动跳过已执行的事务
- 更容易搭建复杂拓扑

#### 配置GTID复制

**主库配置：**
```properties
[mysqld]
server-id=1
log-bin=mysql-bin
binlog_format=ROW

# 开启GTID
gtid_mode=ON
enforce_gtid_consistency=ON
```

**从库配置：**
```properties
[mysqld]
server-id=2
relay-log=mysql-relay-bin

# 开启GTID
gtid_mode=ON
enforce_gtid_consistency=ON
```

**从库配置复制：**
```sql
-- 基于GTID的复制配置（无需指定binlog文件和位置）
CHANGE MASTER TO
  MASTER_HOST='192.168.1.100',
  MASTER_PORT=3306,
  MASTER_USER='repl',
  MASTER_PASSWORD='Repl@123456',
  MASTER_AUTO_POSITION=1;  -- 使用GTID自动定位

START SLAVE;
```

**查看GTID信息：**
```sql
-- 主库查看已执行的GTID集合
SHOW MASTER STATUS;
-- Executed_Gtid_Set: 3e11fa47-71ca-11e5-9e11-fa163e6dd4e8:1-20

-- 从库查看已接收和已执行的GTID
SHOW SLAVE STATUS\G
-- Retrieved_Gtid_Set: 3e11fa47-71ca-11e5-9e11-fa163e6dd4e8:1-20
-- Executed_Gtid_Set: 3e11fa47-71ca-11e5-9e11-fa163e6dd4e8:1-20
```

### 三种复制模式

#### 1. 异步复制（默认）
```
主库 --写入binlog--> 立即返回
           ↓
        从库（异步拉取）
```

**特点：**
- 性能最高
- 主库宕机可能丢数据
- 存在主从延迟

#### 2. 半同步复制
```
主库 --写入binlog--> 等待至少1个从库确认 --> 返回
           ↓
        从库（确认接收）
```

**配置：**
```sql
-- 主库安装插件
INSTALL PLUGIN rpl_semi_sync_master SONAME 'semisync_master.so';

-- 启用半同步
SET GLOBAL rpl_semi_sync_master_enabled = 1;
SET GLOBAL rpl_semi_sync_master_timeout = 1000;  -- 超时1秒降级

-- 从库安装插件
INSTALL PLUGIN rpl_semi_sync_slave SONAME 'semisync_slave.so';
SET GLOBAL rpl_semi_sync_slave_enabled = 1;
```

**特点：**
- 更高的数据可靠性
- 轻微性能损失
- 超时后自动降级为异步

#### 3. 全同步复制（MGR）
```
主库 --写入binlog--> 等待多数节点确认 --> 返回
           ↓
    多数派从库（Paxos共识）
```

**特点：**
- 强一致性
- 性能损失较大
- 适合金融等高一致场景

### 应用场景

#### 1. 读写分离
```java
@Configuration
public class DataSourceConfig {
    @Bean
    public DataSource masterDataSource() {
        // 主库：写操作
        return DataSourceBuilder.create()
            .url("jdbc:mysql://master:3306/db")
            .build();
    }

    @Bean
    public DataSource slaveDataSource() {
        // 从库：读操作
        return DataSourceBuilder.create()
            .url("jdbc:mysql://slave:3306/db")
            .build();
    }
}

@Service
public class UserService {
    @Master  // 自定义注解，路由到主库
    public void createUser(User user) {
        userMapper.insert(user);
    }

    @Slave  // 路由到从库
    public List<User> listUsers() {
        return userMapper.selectAll();
    }
}
```

#### 2. 数据备份
```bash
# 从库备份不影响主库
mysqldump -h slave -u backup -p --single-transaction mydb > backup.sql
```

#### 3. 高可用切换
```
主库宕机 → MHA/Orchestrator检测 → 提升从库为主库 → 应用切换连接
```

### 常见问题排查

#### 1. 复制中断
```sql
SHOW SLAVE STATUS\G

-- IO线程停止
Slave_IO_Running: No
Last_IO_Error: error connecting to master

-- 解决：检查网络、主库状态、账号权限

-- SQL线程停止
Slave_SQL_Running: No
Last_SQL_Error: Error 'Duplicate entry' on query

-- 解决：跳过错误事务或修复数据
SET GLOBAL SQL_SLAVE_SKIP_COUNTER = 1;
START SLAVE;
```

#### 2. 主从数据不一致
```bash
# 使用pt-table-checksum检测
pt-table-checksum --host=master --replicate=percona.checksums

# 使用pt-table-sync修复
pt-table-sync --execute --sync-to-master slave
```

#### 3. 主从延迟过大
```sql
-- 查看延迟
SHOW SLAVE STATUS\G
-- Seconds_Behind_Master: 120

-- 解决方案：
-- 1. 启用并行复制
-- 2. 升级从库硬件
-- 3. 优化慢SQL
-- 4. 使用半同步复制
```

### 面试答题总结

MySQL主从复制通过**binlog记录、relay log中继、SQL线程重放**三步实现数据同步。架构上常用**一主多从**实现读写分离。复制方式包括**异步复制（默认）、半同步复制（更可靠）、全同步复制（强一致）**。MySQL 5.6+推荐使用**GTID模式**，简化配置和主从切换。关键配置是主库开启binlog，从库指定主库信息并启动IO和SQL线程。生产环境需监控`Slave_IO_Running`、`Slave_SQL_Running`、`Seconds_Behind_Master`等指标，及时发现和处理复制中断、延迟等问题。
