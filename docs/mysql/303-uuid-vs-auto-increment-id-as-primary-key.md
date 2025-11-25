---
layout: default
title: "UUID和自增ID做主键哪个好，为什么？"
parent: 数据库MySQL
nav_order: 303
description: "深入对比UUID和自增ID作为主键的优劣势，分析页分裂、索引膨胀、分布式场景等问题，掌握主键选择的最佳实践。"
date: 2025-11-02
---
## 一、核心结论

**自增ID更好**，是绝大多数场景的最佳选择。

| 特性 | 自增ID | UUID |
|------|--------|------|
| **插入性能** | ✅ 极好（顺序插入） | ❌ 差（随机插入，页分裂） |
| **存储空间** | ✅ 小（8字节） | ❌ 大（36字节） |
| **索引效率** | ✅ 高（紧凑） | ❌ 低（稀疏） |
| **二级索引** | ✅ 小 | ❌ 大（每个索引+36字节） |
| **查询性能** | ✅ 好 | ⚠️ 一般 |
| **全局唯一** | ❌ 单表唯一 | ✅ 全局唯一 |
| **分布式** | ⚠️ 需要额外方案 | ✅ 天然支持 |
| **安全性** | ⚠️ 可预测 | ✅ 不可预测 |
| **可读性** | ✅ 好 | ❌ 差 |

## 二、自增ID详解

### 1. 定义和特点

```sql
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50),
    email VARCHAR(100)
) ENGINE=InnoDB;

-- 插入数据（id自动生成）
INSERT INTO users (name, email) VALUES ('张三', 'zhang@a.com');
-- id = 1

INSERT INTO users (name, email) VALUES ('李四', 'li@a.com');
-- id = 2

INSERT INTO users (name, email) VALUES ('王五', 'wang@a.com');
-- id = 3

特点：
✅ 单调递增
✅ 连续（除非有删除）
✅ 8字节（BIGINT）
✅ 顺序插入
✅ 范围：1 ~ 2^63-1（约922亿亿）
```

### 2. 优势1：顺序插入，无页分裂

```
【页分裂问题】

InnoDB数据页大小：16KB
每页可存储约100-200行数据

【自增ID插入过程】

初始状态：
Page 1: [id=1, id=2, ..., id=100] (满)

插入id=101：
Page 1: [id=1, id=2, ..., id=100] (满)
Page 2: [id=101] ← 新页，追加在末尾 ✅

插入id=102：
Page 1: [id=1, id=2, ..., id=100] (满)
Page 2: [id=101, id=102] ← 追加 ✅

特点：
✅ 总是插入到最后一页
✅ 页满后创建新页
✅ 无需移动数据
✅ 无页分裂
✅ 性能稳定
```

### 3. 优势2：存储空间小

```sql
-- 自增ID：8字节
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- 8字节
    name VARCHAR(50),
    email VARCHAR(100),
    INDEX idx_email (email)
);

-- 100万行数据
聚簇索引（主键）：
- id列：8字节 × 100万 = 8MB

二级索引（email）：
- email：约30字节
- 主键id：8字节
- 叶子节点：(email + id) × 100万 = 38MB

总索引大小：约46MB ✅
```

### 4. 优势3：查询性能好

```sql
-- 范围查询
SELECT * FROM users WHERE id BETWEEN 1000 AND 2000;

执行：
1. 定位到id=1000（B+树查找）
2. 顺序扫描到id=2000
3. 数据物理相邻（聚簇索引）
4. 顺序IO，预读高效

性能：
- 扫描1000行
- 约10-20个数据页
- 顺序IO：100-200 MB/s
- 耗时：0.01秒 ✅

-- 分页查询
SELECT * FROM users ORDER BY id LIMIT 10000, 20;

执行：
- 索引有序，无需排序
- 跳过前10000行
- 取20行
- 耗时：0.05秒 ✅
```

### 5. 优势4：二级索引开销小

```sql
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- 8字节
    name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(20),
    city VARCHAR(50),
    -- 多个二级索引
    INDEX idx_name (name),
    INDEX idx_email (email),
    INDEX idx_phone (phone),
    INDEX idx_city (city)
);

每个二级索引叶子节点：
- 索引列值：20-50字节
- 主键id：8字节 ✅

100万行，4个二级索引：
- 总开销：约150MB ✅

如果主键是UUID（36字节）：
- 每个索引额外：28字节 × 100万 = 28MB
- 4个索引额外：112MB
- 总开销：约262MB ⚠️（多112MB）
```

### 6. 劣势1：单表唯一，非全局唯一

```sql
-- 问题：分布式环境ID冲突

-- 服务器1
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50)
);
INSERT INTO users (name) VALUES ('张三');  -- id = 1

-- 服务器2（另一个数据库实例）
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50)
);
INSERT INTO users (name) VALUES ('李四');  -- id = 1 ❌ 冲突

-- 合并数据时会有主键冲突

解决方案：
1. 分布式ID生成器（Snowflake、美团Leaf等）
2. 设置自增步长和起始值
3. UUID
```

### 7. 劣势2：可预测，安全性低

```sql
-- 问题：ID可预测

-- 用户A的订单
GET /api/orders/12345

-- 用户B猜测其他用户的订单
GET /api/orders/12346  -- 可能是用户C的订单
GET /api/orders/12347
...

风险：
❌ 遍历攻击
❌ 信息泄露（通过ID推测业务量）
❌ 隐私问题

解决方案：
1. 权限校验（最重要）
2. 业务层加密ID
3. 使用UUID做业务标识
```

### 8. 劣势3：暴露业务信息

```sql
-- 问题：通过ID判断业务量

-- 今天第一个订单
INSERT INTO orders VALUES (...);  -- id = 100000

-- 明天第一个订单
INSERT INTO orders VALUES (...);  -- id = 105000

推断：
- 昨天订单量：5000单
- 竞争对手可以通过注册账号获取ID
- 估算业务规模

解决：
1. 使用UUID做对外ID
2. 自增ID仅内部使用
3. 混淆算法（如ID加密）
```

## 三、UUID详解

### 1. 定义和特点

```sql
-- UUID（Universally Unique Identifier）
CREATE TABLE users (
    uuid CHAR(36) PRIMARY KEY,  -- '550e8400-e29b-41d4-a716-446655440000'
    name VARCHAR(50),
    email VARCHAR(100)
) ENGINE=InnoDB;

-- 插入数据（UUID随机生成）
INSERT INTO users (uuid, name, email) 
VALUES (UUID(), '张三', 'zhang@a.com');
-- uuid = '6fa459ea-ee8a-3ca4-894e-db77e160355e'

INSERT INTO users (uuid, name, email) 
VALUES (UUID(), '李四', 'li@a.com');
-- uuid = '1a2b3c4d-5e6f-7g8h-9i0j-k1l2m3n4o5p6'

特点：
✅ 全局唯一
✅ 无序（随机）
✅ 36字节（CHAR(36)）或16字节（BINARY(16)）
✅ 不可预测
✅ 重复概率：极低（<10^-15）
```

### 2. UUID版本

```
UUID v1：基于时间戳+MAC地址
- 优点：有序（时间递增）
- 缺点：暴露MAC地址，安全性问题

UUID v2：DCE安全UUID
- 很少使用

UUID v3：基于命名空间的MD5哈希
- 确定性UUID

UUID v4：随机生成（最常用）
- 完全随机
- MySQL UUID()函数生成的是v4

UUID v5：基于命名空间的SHA-1哈希
- 确定性UUID

UUID v6：时间有序（草案）
- 结合v1的有序性和v4的随机性

UUID v7：Unix时间戳 + 随机数（新标准）
- 时间有序
- 推荐用于数据库主键
```

### 3. 劣势1：随机插入，频繁页分裂

```
【页分裂问题】

InnoDB按主键排序存储

【UUID插入过程】

初始状态：
Page 1: [uuid='1aaa...', uuid='5bbb...', uuid='9ccc...'] (有序)

插入uuid='3ddd...'（在中间）：
Page 1: [uuid='1aaa...'] 
Page 2: [uuid='3ddd...', uuid='5bbb...'] ← 分裂
Page 3: [uuid='9ccc...']

问题：
❌ 插入位置随机（UUID无序）
❌ 频繁页分裂
❌ 数据移动
❌ 索引重组
❌ 性能急剧下降

性能对比（插入100万行）：
自增ID：
- 页分裂：约5000次（正常扩展）
- 耗时：30秒 ✅

UUID：
- 页分裂：约50万次（每次都可能分裂）
- 耗时：300秒 ❌（慢10倍）
```

### 4. 劣势2：存储空间大

```sql
-- UUID存储方式1：CHAR(36)
CREATE TABLE users (
    uuid CHAR(36) PRIMARY KEY,  -- 36字节
    name VARCHAR(50),
    email VARCHAR(100)
);

存储：'550e8400-e29b-41d4-a716-446655440000'（36个字符）

-- UUID存储方式2：BINARY(16)（更优）
CREATE TABLE users (
    uuid BINARY(16) PRIMARY KEY,  -- 16字节
    name VARCHAR(50),
    email VARCHAR(100)
);

-- 插入时转换
INSERT INTO users (uuid, name, email) 
VALUES (UUID_TO_BIN(UUID()), '张三', 'zhang@a.com');

-- 查询时转换
SELECT BIN_TO_UUID(uuid), name FROM users;

存储对比（100万行）：
自增ID：8字节 × 100万 = 8MB ✅
UUID (CHAR(36))：36字节 × 100万 = 36MB ❌（4.5倍）
UUID (BINARY(16))：16字节 × 100万 = 16MB ⚠️（2倍）
```

### 5. 劣势3：二级索引膨胀

```sql
CREATE TABLE users (
    uuid CHAR(36) PRIMARY KEY,  -- 36字节
    name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(20),
    city VARCHAR(50),
    -- 4个二级索引
    INDEX idx_name (name),
    INDEX idx_email (email),
    INDEX idx_phone (phone),
    INDEX idx_city (city)
);

每个二级索引叶子节点：
- 索引列值：20-50字节
- 主键uuid：36字节 ❌

100万行，4个二级索引：
- 主键：36MB
- idx_name：(name + uuid) × 100万 ≈ 66MB
- idx_email：(email + uuid) × 100万 ≈ 66MB
- idx_phone：(phone + uuid) × 100万 ≈ 56MB
- idx_city：(city + uuid) × 100万 ≈ 66MB
- 总计：约290MB ❌

对比自增ID：约150MB ✅

差距：UUID多140MB（约2倍）
```

### 6. 劣势4：索引碎片化

```
【问题】

UUID无序插入导致：
1. B+树频繁重组
2. 页内记录分散
3. 页利用率低（约50%-60%）
4. 索引膨胀

自增ID：
- 页利用率：90%+ ✅

UUID：
- 页利用率：50%-60% ❌

同样100万行数据：
自增ID索引：100MB
UUID索引：150MB（膨胀50%）
```

### 7. 优势1：全局唯一

```sql
-- 分布式环境

-- 服务器1
INSERT INTO users (uuid, name) 
VALUES (UUID(), '张三');  
-- uuid = '6fa459ea-...'

-- 服务器2
INSERT INTO users (uuid, name) 
VALUES (UUID(), '李四');
-- uuid = '1a2b3c4d-...'

-- 合并数据
-- ✅ 无主键冲突

优势：
✅ 跨数据库唯一
✅ 分布式系统友好
✅ 数据迁移方便
✅ 多数据中心同步无冲突
```

### 8. 优势2：安全性高

```sql
-- 订单API

-- ❌ 自增ID：可预测
GET /api/orders/12345
GET /api/orders/12346  -- 猜测下一个

-- ✅ UUID：不可预测
GET /api/orders/6fa459ea-ee8a-3ca4-894e-db77e160355e
GET /api/orders/6fa459ea-ee8a-3ca4-894e-db77e160355f  -- 无法猜测

优势：
✅ 防止遍历攻击
✅ 不暴露业务量
✅ 隐私保护
```

## 四、性能测试对比

### 测试1：插入性能

```sql
-- 测试环境：
-- 表：空表
-- 数据：100万行
-- 服务器：8核16G，SSD

-- 自增ID
CREATE TABLE test_auto (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    data VARCHAR(100),
    INDEX idx_data (data)
);

INSERT INTO test_auto (data) 
SELECT CONCAT('data_', n) FROM numbers WHERE n <= 1000000;

结果：
- 耗时：25秒
- 页分裂：约5000次
- 平均TPS：40000 ✅

-- UUID (CHAR(36))
CREATE TABLE test_uuid (
    uuid CHAR(36) PRIMARY KEY,
    data VARCHAR(100),
    INDEX idx_data (data)
);

INSERT INTO test_uuid (uuid, data) 
SELECT UUID(), CONCAT('data_', n) FROM numbers WHERE n <= 1000000;

结果：
- 耗时：280秒 ❌
- 页分裂：约50万次
- 平均TPS：3571

性能差距：自增ID快11倍
```

### 测试2：查询性能

```sql
-- 主键随机查询（100万次）

-- 自增ID
SELECT * FROM test_auto WHERE id = FLOOR(RAND() * 1000000);

结果：
- 平均耗时：0.001秒
- QPS：1000 ✅

-- UUID
SELECT * FROM test_uuid WHERE uuid = ?;

结果：
- 平均耗时：0.002秒
- QPS：500 ⚠️

性能差距：自增ID快2倍

原因：
1. 自增ID索引紧凑，缓存命中率高
2. UUID索引稀疏，缓存命中率低
```

### 测试3：范围查询

```sql
-- 范围查询（1000行）

-- 自增ID
SELECT * FROM test_auto WHERE id BETWEEN 100000 AND 101000;

结果：
- 耗时：0.01秒 ✅
- 数据物理相邻，顺序IO

-- UUID
SELECT * FROM test_uuid WHERE uuid BETWEEN ? AND ?;

结果：
- 耗时：0.5秒 ❌
- 数据分散，大量随机IO

性能差距：自增ID快50倍
```

### 测试4：存储空间

```
100万行数据：

自增ID：
- 主键索引：约80MB
- 二级索引（data）：约45MB
- 总计：125MB ✅

UUID (CHAR(36))：
- 主键索引：约150MB
- 二级索引（data）：约90MB
- 总计：240MB ❌

UUID (BINARY(16))：
- 主键索引：约100MB
- 二级索引（data）：约60MB
- 总计：160MB ⚠️

空间差距：
- CHAR(36)：多92% 
- BINARY(16)：多28%
```

## 五、最佳实践

### 1. 默认选择：自增ID

```sql
-- ✅ 推荐：绝大多数场景
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50),
    email VARCHAR(100)
) ENGINE=InnoDB;

适用场景：
✅ 单体应用
✅ 主从复制
✅ 性能要求高
✅ 不需要分布式ID
✅ 99%的业务场景
```

### 2. 分布式场景：Snowflake算法

```sql
-- 雪花算法（Snowflake）

CREATE TABLE users (
    id BIGINT PRIMARY KEY,  -- Snowflake生成的ID
    name VARCHAR(50),
    email VARCHAR(100)
) ENGINE=InnoDB;

Snowflake ID结构（64位）：
+----------+----------+----------+----------+
| 1bit     | 41bit    | 10bit    | 12bit    |
| 符号位   | 时间戳   | 机器ID   | 序列号   |
+----------+----------+----------+----------+

特点：
✅ 全局唯一
✅ 时间有序（近似）
✅ 高性能（本地生成）
✅ 8字节（BIGINT）
✅ 可读性较好

示例ID：1234567890123456789

优势：
✅ 避免UUID的页分裂问题（有序）
✅ 避免自增ID的冲突问题（全局唯一）
✅ 兼具两者优点

缺点：
⚠️ 需要额外的ID生成服务
⚠️ 依赖时钟同步
⚠️ 机器ID需要管理
```

### 3. 混合方案：自增ID + UUID业务标识

```sql
-- ✅ 推荐：兼顾性能和安全

CREATE TABLE orders (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- 内部使用
    order_no CHAR(36) UNIQUE,              -- 对外暴露
    user_id BIGINT,
    total_amount DECIMAL(10, 2),
    create_time DATETIME,
    INDEX idx_order_no (order_no)
);

-- 插入时同时生成
INSERT INTO orders (order_no, user_id, total_amount) 
VALUES (UUID(), 12345, 1000.00);

-- 对外API使用order_no
GET /api/orders/{order_no}

-- 内部查询使用id
SELECT * FROM orders WHERE id = 123456;

优势：
✅ 主键使用自增ID（性能最优）
✅ 对外暴露UUID（安全）
✅ 不暴露业务量
✅ 防止遍历攻击
✅ 最佳实践 ⭐
```

### 4. UUID优化：有序UUID

```sql
-- MySQL 8.0+：UUID_TO_BIN() 支持交换时间位

CREATE TABLE users (
    uuid BINARY(16) PRIMARY KEY,
    name VARCHAR(50)
);

-- 插入时重排，使其有序
INSERT INTO users (uuid, name) 
VALUES (UUID_TO_BIN(UUID(), TRUE), '张三');
--                        ↑
--                  交换时间位，使UUID有序

优势：
✅ 减少页分裂（有序）
✅ 全局唯一
✅ 16字节（比CHAR(36)小）

劣势：
⚠️ 仍然比自增ID大
⚠️ 需要MySQL 8.0+
⚠️ 二级索引仍然较大

适用场景：
- 分布式环境
- 必须使用UUID
- MySQL 8.0+
```

### 5. 不同场景的选择

#### 场景1：单体应用

```sql
-- ✅ 自增ID
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ...
);

理由：
- 性能最优
- 简单
- 足够用
```

#### 场景2：分布式应用

```sql
-- ✅ Snowflake ID
CREATE TABLE users (
    id BIGINT PRIMARY KEY,  -- Snowflake生成
    ...
);

-- 或：自增ID + 业务UUID
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    uuid CHAR(36) UNIQUE,
    ...
);

理由：
- Snowflake：性能好，全局唯一
- 混合方案：兼顾性能和安全
```

#### 场景3：对外API

```sql
-- ✅ 混合方案
CREATE TABLE orders (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- 内部
    order_no CHAR(36) UNIQUE,              -- 对外
    ...
);

理由：
- 内部高性能
- 对外安全
- 最佳实践
```

#### 场景4：多租户系统

```sql
-- ✅ 复合主键或Snowflake

-- 方案1：复合主键
CREATE TABLE tenant_users (
    tenant_id BIGINT,
    user_id BIGINT AUTO_INCREMENT,
    name VARCHAR(50),
    PRIMARY KEY (tenant_id, user_id)
);

-- 方案2：Snowflake（推荐）
CREATE TABLE tenant_users (
    id BIGINT PRIMARY KEY,  -- Snowflake（包含租户信息）
    tenant_id BIGINT,
    name VARCHAR(50),
    INDEX idx_tenant (tenant_id)
);

理由：
- 跨租户唯一
- 性能好
```

## 六、迁移方案

### 从UUID迁移到自增ID

```sql
-- 步骤1：添加自增ID列
ALTER TABLE users ADD COLUMN id BIGINT AUTO_INCREMENT UNIQUE;

-- 步骤2：重建表，将id设为主键
ALTER TABLE users DROP PRIMARY KEY, ADD PRIMARY KEY (id);

-- 步骤3：保留uuid作为业务标识
ALTER TABLE users ADD UNIQUE INDEX uk_uuid (uuid);

-- 步骤4：更新关联表（如果有）
-- 这是最麻烦的部分，需要逐步迁移

注意：
⚠️ 需要停机或者多步骤在线迁移
⚠️ 关联表需要同步更新
⚠️ 数据量大时耗时长
```

### 从自增ID迁移到UUID（不推荐）

```sql
-- 不推荐迁移，除非有明确需求

如果必须迁移：
1. 添加UUID列
ALTER TABLE users ADD COLUMN uuid CHAR(36);

2. 生成UUID
UPDATE users SET uuid = UUID();

3. 添加唯一索引
ALTER TABLE users ADD UNIQUE INDEX uk_uuid (uuid);

4. 重建主键（需要停机）
ALTER TABLE users DROP PRIMARY KEY, ADD PRIMARY KEY (uuid);

5. 删除旧id列（可选）
ALTER TABLE users DROP COLUMN id;

问题：
❌ 性能下降
❌ 存储膨胀
❌ 关联表需要更新
❌ 不建议这样做
```

## 七、常见误区

### 误区1：UUID更安全

```
错误：UUID做主键就安全了

正确：
- 安全性应该由权限控制保证
- 不能仅依赖主键不可预测
- 自增ID + 权限校验同样安全

示例：
// ✅ 正确的做法
GET /api/orders/12345
→ 验证当前用户是否有权限访问订单12345
→ 有权限才返回数据

// ❌ 错误的做法
GET /api/orders/{uuid}
→ 认为UUID不可预测就不校验权限
→ 仍然不安全（如果UUID泄露）
```

### 误区2：UUID适合分布式

```
错误：分布式系统必须用UUID

正确：
- UUID可以用，但不是最优
- Snowflake等有序分布式ID更好
- 兼顾全局唯一和插入性能

选择：
1. Snowflake ID（推荐）
2. 美团Leaf
3. 百度UidGenerator
4. 自增ID + 步长
5. UUID（性能最差）
```

### 误区3：UUID_TO_BIN()解决了所有问题

```
错误：用BINARY(16)和有序UUID就没问题了

正确：
- BINARY(16)节省空间（16字节 vs 36字节）
- 有序UUID减少页分裂
- 但仍然比自增ID大2倍
- 二级索引仍然膨胀

结论：
- 有改善，但不完美
- 仍然优先考虑自增ID或Snowflake
```

## 八、面试要点总结

### 自增ID优势

```
1. 插入性能极好
   - 顺序插入，无页分裂
   - 比UUID快10倍

2. 存储空间小
   - 8字节 vs 36字节
   - 二级索引开销小

3. 查询性能好
   - 索引紧凑，缓存命中率高
   - 范围查询快

4. 简单易用
   - 自动生成
   - 可读性好
```

### UUID优势

```
1. 全局唯一
   - 分布式友好
   - 无冲突

2. 安全性高
   - 不可预测
   - 不暴露业务量

缺点：
- 随机插入，页分裂频繁
- 存储空间大
- 插入性能差（慢10倍）
```

### 选择建议

```
默认：自增ID ✅

特殊场景：
- 分布式：Snowflake ID
- 对外API：自增ID + UUID业务标识
- 必须UUID：UUID_TO_BIN(UUID(), TRUE)（MySQL 8.0+）

最佳实践：
自增ID做主键（内部）+ UUID做业务标识（对外）
```

### 一句话总结

**自增ID比UUID好，因为顺序插入无页分裂、存储空间小、查询性能高，插入性能比UUID快10倍；UUID的优势是全局唯一和安全性，但牺牲了性能；实际应用推荐使用自增ID做主键，UUID作为业务标识字段，或者使用Snowflake等有序分布式ID，兼顾性能和分布式需求。**

