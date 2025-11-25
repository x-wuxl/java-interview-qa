---
layout: default
title: "什么是聚簇索引和非聚簇索引？"
parent: 数据库MySQL
nav_order: 276
description: "深入理解MySQL聚簇索引和非聚簇索引的区别、存储结构、查询过程、性能差异及设计考量，掌握InnoDB索引的核心原理。"
date: 2025-11-02
---
## 一、核心概念

### 聚簇索引（Clustered Index）

**定义**：索引的叶子节点直接存储完整的数据行，数据的物理存储顺序与索引顺序一致（或接近）。

```
【聚簇索引结构】

              Root
         [10, 30, 50]
        /     |      \
    [5,10] [20,30] [40,50,60]
      ↓       ↓        ↓
   完整数据行存储在叶子节点

叶子节点内容：
Page 1: [id=5, name='张三', age=25, city='北京', ...]
Page 2: [id=10, name='李四', age=30, city='上海', ...]
Page 3: [id=20, name='王五', age=22, city='广州', ...]
```

**关键特性**：
- ✅ 叶子节点 = 完整数据行
- ✅ 一张表只能有一个聚簇索引
- ✅ 数据即索引，索引即数据
- ✅ InnoDB的主键就是聚簇索引

### 非聚簇索引/二级索引（Secondary Index）

**定义**：索引的叶子节点存储索引列的值和主键值，需要通过主键回表查询完整数据。

```
【二级索引结构】

CREATE INDEX idx_name ON users(name);

              Root
         [李, 王, 赵]
        /     |      \
    [张,李] [王,吴] [赵,钱]
      ↓       ↓        ↓
   (索引列值, 主键值)

叶子节点内容：
Page 1: [name='张三', id=5], [name='李四', id=10]
Page 2: [name='王五', id=20], [name='吴六', id=25]
Page 3: [name='赵七', id=30], [name='钱八', id=35]
```

**关键特性**：
- ✅ 叶子节点 = 索引列值 + 主键值
- ✅ 一张表可以有多个二级索引
- ✅ 需要回表获取完整数据（除非覆盖索引）
- ✅ InnoDB的所有非主键索引都是二级索引

## 二、聚簇索引详解

### 1. InnoDB如何选择聚簇索引

```sql
-- 优先级1：显式定义的PRIMARY KEY
CREATE TABLE users (
    id BIGINT PRIMARY KEY,  -- ✅ 作为聚簇索引
    email VARCHAR(100),
    name VARCHAR(50)
);

-- 优先级2：第一个UNIQUE NOT NULL索引
CREATE TABLE orders (
    order_no VARCHAR(32) UNIQUE NOT NULL,  -- ✅ 作为聚簇索引
    user_id BIGINT,
    total_amount DECIMAL(10, 2)
    -- 没有显式主键
);

-- 优先级3：InnoDB自动生成隐藏的ROW_ID
CREATE TABLE logs (
    user_id BIGINT,
    action VARCHAR(50),
    create_time DATETIME
    -- 没有主键，也没有唯一非空索引
    -- InnoDB自动生成 6字节的 ROW_ID 作为聚簇索引
);

-- 隐藏列（无法直接查询，但确实存在）：
-- ROW_ID:     6字节，自增，全局计数器
-- TRX_ID:     6字节，最近修改该行的事务ID
-- ROLL_PTR:   7字节，回滚指针，指向undo log
```

### 2. 聚簇索引的存储结构

```
【表文件：users.ibd】

+----------------------+
|   Root Page          |
|   [10, 30, 50]      |
+-----+--------+-------+
      |        |       
  +---+   +----+   +---+
  |       |        |
  ↓       ↓        ↓
Page 1  Page 2   Page 3
[数据]  [数据]   [数据]

Page 1 内容（叶子节点）：
[id=5,  name='张三', age=25, email='zhang@a.com', ...]
[id=10, name='李四', age=30, email='li@a.com', ...]

Page 2 内容：
[id=20, name='王五', age=22, email='wang@a.com', ...]
[id=30, name='赵六', age=28, email='zhao@a.com', ...]

特点：
- 叶子节点包含完整行数据
- 按主键顺序存储（物理上尽量连续）
- 页之间通过双向链表连接
```

### 3. 聚簇索引的查询过程

```sql
SELECT * FROM users WHERE id = 20;

查询步骤：
1. 从Root页开始：[10, 30, 50]
   - 20在10和30之间
   - 走第2个指针

2. 到达叶子节点Page 2
   - 在页内二分查找找到id=20的行
   
3. 直接返回完整数据
   [id=20, name='王五', age=22, email='wang@a.com', ...]

磁盘IO：
- Root页：通常在内存中（0次IO）
- 中间层：1次IO（如果有）
- 叶子页：1次IO
- 总计：1-2次IO ✅ 非常快
```

### 4. 聚簇索引的优势

#### 优势1：主键查询极快

```sql
-- 单次查询
SELECT * FROM users WHERE id = 12345;

聚簇索引：
- 一次B+树查找即可
- 磁盘IO：2-3次
- 耗时：0.001秒

假设非聚簇索引（MyISAM）：
- B+树查找获取指针
- 根据指针回表查数据
- 磁盘IO：4-6次
- 耗时：0.003秒
```

#### 优势2：范围查询高效

```sql
-- 范围查询
SELECT * FROM users WHERE id BETWEEN 1000 AND 2000;

执行：
1. 定位到id=1000的叶子节点（2-3次IO）
2. 顺序扫描链表到id=2000（连续IO）
3. 数据物理相邻，预读机制高效

性能：
- 顺序IO：100-200 MB/s
- 随机IO：1-5 MB/s
- 性能差异：20-100倍
```

#### 优势3：排序性能好

```sql
-- 带排序的查询
SELECT * FROM users WHERE age > 20 ORDER BY id LIMIT 100;

执行计划：
- 扫描聚簇索引（数据天然按id有序）
- 无需额外排序（Extra: Using where）
- 无 Using filesort

对比：
如果ORDER BY age：
- 需要filesort（Extra: Using filesort）
- 创建临时表排序
- 性能下降明显
```

### 5. 聚簇索引的劣势

#### 劣势1：插入性能受影响

```sql
-- 问题：页分裂

-- 初始状态（Page容量：3条）
Page 1: [id=10, id=20, id=30]  -- 满

-- 插入 id=15
Page 1: [id=10, id=15]
Page 2: [id=20, id=30]  -- 分裂成两页

影响：
- 数据移动
- 页空间浪费
- 索引树调整
- 性能下降

解决：
✅ 使用自增主键（顺序插入，避免分裂）
❌ 使用UUID（随机插入，频繁分裂）
```

#### 劣势2：更新主键代价大

```sql
UPDATE users SET id = 9999 WHERE id = 1;

执行：
1. 删除id=1的行（在Page 1）
2. 插入id=9999的行（在Page N）
3. 数据物理移动
4. 更新所有二级索引的主键值

代价：
- 多次页分裂/合并
- 大量数据移动
- 所有二级索引更新
- 性能极差

建议：
⚠️ 主键尽量不要修改
✅ 如需修改，考虑逻辑删除+新增
```

#### 劣势3：二级索引膨胀

```sql
-- 主键：BIGINT（8字节）
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    name VARCHAR(50),
    email VARCHAR(100),
    INDEX idx_name (name),
    INDEX idx_email (email)
);

二级索引叶子节点：
idx_name:  (name, id)  -- 8字节主键
idx_email: (email, id) -- 8字节主键

-- 如果主键是 VARCHAR(100)（100字节）
CREATE TABLE users (
    uuid VARCHAR(100) PRIMARY KEY,  -- ❌ 太大
    name VARCHAR(50),
    INDEX idx_name (name)
);

二级索引叶子节点：
idx_name: (name, uuid)  -- 100字节主键！

问题：
- 每个二级索引增大100字节
- 索引页存储的索引数量减少
- B+树高度增加
- 查询性能下降
```

## 三、非聚簇索引（二级索引）详解

### 1. 二级索引的存储结构

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    name VARCHAR(50),
    age INT,
    city VARCHAR(50),
    INDEX idx_name (name),
    INDEX idx_age_city (age, city)
);
```

#### 单列二级索引

```
【idx_name索引结构】

              Root
         [李, 王, 赵]
        /     |      \
    [张,李] [王,吴] [赵,钱]
      ↓       ↓        ↓
   叶子节点

Page 1: 
[name='张三', id=5]
[name='李四', id=10]

Page 2:
[name='王五', id=20]
[name='吴六', id=25]

特点：
- 按name排序
- 叶子节点：(name, 主键id)
- name相同时按id排序
```

#### 联合二级索引

```
【idx_age_city索引结构】

              Root
         [25, 30, 35]
        /     |      \
   [20,25] [28,30] [32,35]
      ↓       ↓        ↓
   叶子节点

Page 1:
[age=20, city='北京', id=5]
[age=22, city='上海', id=8]
[age=25, city='广州', id=10]

排序规则：
- 先按age排序
- age相同按city排序
- age和city都相同按id排序
```

### 2. 回表查询过程

```sql
SELECT * FROM users WHERE name = '张三';

执行步骤：

【步骤1】在二级索引 idx_name 中查找
1. Root页：[李, 王, 赵]
   '张三'在最左侧，走第1个指针

2. 叶子节点Page 1：
   找到 [name='张三', id=5]
   获得主键 id=5

【步骤2】回表到聚簇索引查询
3. Root页：[10, 30, 50]
   5 < 10，走第1个指针

4. 叶子节点：
   找到完整数据：
   [id=5, name='张三', age=25, city='北京', ...]

【总结】
磁盘IO：
- 二级索引查询：2次IO
- 聚簇索引回表：2次IO
- 总计：4次IO

对比主键查询：
- 主键查询：2次IO
- 二级索引：4次IO
- 性能差异：约2倍
```

### 3. 多行回表查询

```sql
SELECT * FROM users WHERE age = 25;
-- 假设返回100行

执行：
1. 在 idx_age 中找到100条记录
   → 获得100个主键id

2. 回表100次到聚簇索引
   → 100次随机IO

磁盘IO：
- 二级索引扫描：2-3次IO（连续扫描）
- 回表：100次IO（随机IO）
- 总计：102-103次IO ⚠️ 很慢

优化：
- 覆盖索引（避免回表）
- 延迟关联（减少回表次数）
```

### 4. 为什么二级索引存主键而非指针？

#### 方案对比

```
【方案1】存数据指针（MyISAM方式）

二级索引叶子节点：
[name='张三', 指针=0x1A2B3C4D]
                    ↓
                数据文件物理地址

查询：
1. 二级索引查找 → 获得指针
2. 直接访问物理地址 → 获取数据

优点：
✅ 无需二次索引查找
✅ 查询快（一次回表）

缺点：
❌ 数据移动时，所有指针失效
❌ 页分裂时，需要更新所有指针
❌ 维护成本极高
❌ 数据一致性难保证

【方案2】存主键值（InnoDB方式）

二级索引叶子节点：
[name='张三', id=5]
                 ↓
            聚簇索引查询

查询：
1. 二级索引查找 → 获得主键id
2. 聚簇索引查找 → 获取数据

优点：
✅ 数据移动时，二级索引无需更新
✅ 页分裂时，二级索引不受影响
✅ 维护成本低
✅ 数据一致性好

缺点：
⚠️ 需要二次查询（回表）
⚠️ 主键大时，索引膨胀
```

#### InnoDB选择方案2的原因

```
InnoDB是事务型存储引擎：
- MVCC机制：数据频繁变化
- 页分裂/合并：数据位置经常改变
- 行锁：并发修改多

如果存指针：
- 每次页分裂 → 更新所有二级索引指针
- 每次数据移动 → 更新所有指针
- 维护成本 → 不可接受

存主键值：
- 主键不变 → 二级索引稳定
- 数据移动 → 二级索引不变
- 一致性 → 更容易保证

代价：
- 回表开销 → 可通过覆盖索引优化
- 主键膨胀 → 使用小主键（BIGINT）
```

## 四、聚簇索引 vs 非聚簇索引对比

### 1. 核心差异

| 特性 | 聚簇索引 | 非聚簇索引 |
|------|---------|-----------|
| **叶子节点存储** | 完整数据行 | 索引列值+主键值 |
| **数量** | 一张表只能有1个 | 一张表可以有多个 |
| **回表** | 不需要 | 需要（除非覆盖索引） |
| **查询性能** | 快（一次查询） | 较慢（需要回表） |
| **范围查询** | 非常快（顺序IO） | 较慢（随机回表） |
| **插入性能** | 受影响（页分裂） | 影响较小 |
| **存储空间** | 包含完整数据 | 仅索引列+主键 |
| **InnoDB实现** | 主键索引 | 所有非主键索引 |

### 2. 查询性能对比

```sql
-- 测试表（100万条数据）
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    name VARCHAR(50),
    age INT,
    email VARCHAR(100),
    INDEX idx_name (name)
);
```

#### 场景1：主键查询

```sql
SELECT * FROM users WHERE id = 500000;

聚簇索引：
- B+树查找：3次IO
- 获取完整数据
- 耗时：0.003秒

总结：✅ 最快
```

#### 场景2：二级索引等值查询

```sql
SELECT * FROM users WHERE name = '张三';

二级索引 + 回表：
- 二级索引查找：3次IO
- 回表到聚簇索引：3次IO
- 总计：6次IO
- 耗时：0.006秒

总结：⚠️ 比主键查询慢2倍
```

#### 场景3：二级索引范围查询

```sql
SELECT * FROM users WHERE name BETWEEN '张三' AND '张九';
-- 返回1000行

二级索引 + 回表：
- 二级索引扫描：3-5次IO（连续）
- 回表：1000次IO（随机）
- 总计：1003-1005次IO
- 耗时：1-10秒 ⚠️

总结：❌ 非常慢（大量随机IO）

优化：
- 覆盖索引
- 延迟关联
- 使用主键范围
```

#### 场景4：覆盖索引

```sql
-- 索引：INDEX idx_name_age (name, age)

SELECT name, age FROM users WHERE name = '张三';

覆盖索引：
- 只需查询二级索引
- 无需回表
- 磁盘IO：3次
- 耗时：0.003秒

总结：✅ 与主键查询性能相当
```

### 3. 存储空间对比

```sql
-- 假设：
-- 主键：BIGINT (8字节)
-- name: VARCHAR(50)，平均20字节
-- age: INT (4字节)
-- 其他字段：100字节
-- 总行大小：132字节

【聚簇索引】
- 叶子节点：完整行 132字节/行
- 非叶子节点：键+指针 14字节
- 100万行数据：≈132MB

【二级索引 idx_name】
- 叶子节点：name + id = 28字节/行
- 非叶子节点：name + 指针 = 26字节
- 100万行数据：≈28MB

【二级索引 idx_age】
- 叶子节点：age + id = 12字节/行
- 非叶子节点：age + 指针 = 10字节
- 100万行数据：≈12MB

【总计】
- 聚簇索引：132MB
- 2个二级索引：40MB
- 总存储：172MB
- 索引开销：40MB / 132MB = 30%
```

## 五、实战优化技巧

### 1. 选择合适的主键

```sql
-- ✅ 推荐：自增BIGINT
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ...
);

优点：
✅ 顺序插入，无页分裂
✅ 占用空间小（8字节）
✅ 二级索引开销小

-- ❌ 不推荐：UUID
CREATE TABLE users (
    uuid VARCHAR(36) PRIMARY KEY,  -- 36字节
    ...
);

缺点：
❌ 随机插入，频繁页分裂
❌ 占用空间大
❌ 二级索引膨胀（每个索引+36字节）
❌ 查询性能下降
```

### 2. 利用覆盖索引避免回表

```sql
-- 原查询（需要回表）
SELECT id, name, age FROM users WHERE name = '张三';

-- 优化：创建覆盖索引
CREATE INDEX idx_name_age ON users(name, age);

-- 现在查询无需回表
EXPLAIN SELECT id, name, age FROM users WHERE name = '张三';
-- Extra: Using index ✅

性能提升：
- 回表：6次IO
- 覆盖索引：3次IO
- 提升：2倍
```

### 3. 延迟关联优化大量回表

```sql
-- 问题：深度分页 + 大量回表
SELECT * FROM users 
WHERE age > 20 
ORDER BY create_time 
LIMIT 100000, 20;

执行：
- 扫描100020行
- 回表100020次
- 耗时：10秒 ❌

-- 优化：延迟关联
SELECT u.* 
FROM users u
INNER JOIN (
    SELECT id FROM users
    WHERE age > 20
    ORDER BY create_time
    LIMIT 100000, 20
) t ON u.id = t.id;

执行：
- 子查询：覆盖索引，无回表
- 只对最终20行回表
- 回表：20次
- 耗时：0.5秒 ✅

提升：20倍
```

### 4. 强制使用主键（避免二级索引）

```sql
-- 如果已知主键范围
SELECT * FROM users WHERE id BETWEEN 1000 AND 2000;
-- 走聚簇索引，性能最优

-- 避免
SELECT * FROM users WHERE name IN (...) AND other_conditions;
-- 优化器可能选择错误的索引
-- 使用FORCE INDEX强制
SELECT * FROM users FORCE INDEX (PRIMARY) WHERE ...;
```

## 六、MyISAM的非聚簇索引

### MyISAM的索引结构

```
【MyISAM】所有索引都是非聚簇索引

数据文件：users.MYD
[row1 at 0x0000]
[row2 at 0x0100]
[row3 at 0x0200]
...

主键索引：users.MYI
[id=1, 指针=0x0000]
[id=2, 指针=0x0100]
[id=3, 指针=0x0200]

二级索引：users_name.MYI
[name='张三', 指针=0x0000]
[name='李四', 指针=0x0100]

特点：
- 主键索引和二级索引结构相同
- 都存储数据文件的物理指针
- 数据和索引完全分离
```

### InnoDB vs MyISAM

| 特性 | InnoDB | MyISAM |
|------|--------|--------|
| 主键索引 | 聚簇索引 | 非聚簇索引 |
| 二级索引叶子节点 | 主键值 | 数据指针 |
| 数据存储 | 索引文件中 | 单独数据文件 |
| 主键查询 | 快（一次查询） | 一般（指针访问） |
| 二级索引查询 | 慢（回表） | 快（直接指针） |
| 数据移动 | 二级索引不变 | 所有索引失效 |
| 事务支持 | ✅ | ❌ |

## 七、面试要点总结

### 定义区别

**聚簇索引**：
- 叶子节点存完整数据行
- 数据即索引，索引即数据
- 一表只能一个
- InnoDB的主键就是聚簇索引

**非聚簇索引**：
- 叶子节点存索引列值+主键值
- 需要回表查询完整数据
- 一表可以多个
- InnoDB的所有非主键索引都是非聚簇索引

### 性能差异

```
主键查询：3次IO
二级索引单行查询：6次IO（2倍慢）
二级索引范围查询：N+3次IO（N为返回行数，极慢）
覆盖索引：3次IO（与主键相当）
```

### 设计建议

1. **主键选择**
   - ✅ 自增BIGINT（顺序插入，小主键）
   - ❌ UUID（随机插入，大主键）

2. **覆盖索引**
   - 常查字段加到索引末尾
   - 避免SELECT *

3. **延迟关联**
   - 大量回表时使用
   - 性能提升10-100倍

### 一句话总结

**聚簇索引的叶子节点直接存储完整数据行，查询无需回表，InnoDB的主键即聚簇索引；非聚簇索引的叶子节点存储索引列值和主键值，需要回表到聚簇索引查询完整数据，InnoDB的所有非主键索引都是非聚簇索引，这种设计保证了数据移动时二级索引的稳定性，但代价是回表开销，可通过覆盖索引优化。**

