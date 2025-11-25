---
layout: default
title: "MyBatis 如何实现分页？"
parent: Spring框架
nav_order: 483
description: "深入解析 MyBatis 分页的三种实现方式：逻辑分页、物理分页和 PageHelper 插件，帮助你在面试中清晰阐述分页原理及最佳实践。"
date: 2025-11-20 15:32:01 +0800
---
## 一、核心概念

MyBatis 实现分页主要有三种方式：

1. **逻辑分页**：查询全部数据后在内存中通过 `RowBounds` 进行分页
2. **物理分页**：在 SQL 层面直接使用 `LIMIT`/`OFFSET` 等语句实现
3. **插件分页**：使用 MyBatis 拦截器（如 PageHelper）自动改写 SQL

## 二、原理与实现

### 1. 逻辑分页（RowBounds）

MyBatis 提供了 `RowBounds` 对象，可以在查询时传入分页参数：

```java
// Mapper 接口
List<User> selectUsers(RowBounds rowBounds);

// 使用示例
RowBounds rowBounds = new RowBounds(offset, limit);
List<User> users = userMapper.selectUsers(rowBounds);
```

**原理**：
- MyBatis 执行完整的 SQL 查询，获取所有结果
- 在 `DefaultResultSetHandler` 中通过 `shouldProcessMoreRows()` 方法跳过前 N 条记录
- 只保留指定范围内的数据返回

**缺点**：
- 数据量大时性能极差（查询全表数据）
- 内存占用高，可能导致 OOM
- **不推荐在生产环境使用**

### 2. 物理分页（手动编写 SQL）

直接在 SQL 中使用数据库的分页语法：

```xml
<!-- MySQL 分页 -->
<select id="selectUsersByPage" resultType="User">
    SELECT * FROM user
    WHERE status = 1
    ORDER BY create_time DESC
    LIMIT #{offset}, #{limit}
</select>

<!-- Oracle 分页（使用 ROWNUM） -->
<select id="selectUsersByPage" resultType="User">
    SELECT * FROM (
        SELECT t.*, ROWNUM rn FROM (
            SELECT * FROM user WHERE status = 1 ORDER BY create_time DESC
        ) t WHERE ROWNUM <![CDATA[<=]]> #{endRow}
    ) WHERE rn > #{startRow}
</select>
```

使用时传入分页参数：

```java
Map<String, Object> params = new HashMap<>();
params.put("offset", (pageNum - 1) * pageSize);
params.put("limit", pageSize);
List<User> users = userMapper.selectUsersByPage(params);
```

**优点**：
- 性能良好，只查询需要的数据
- 数据库层面优化，减少网络传输

**缺点**：
- 需要手动编写分页 SQL
- 不同数据库语法不同，可移植性差
- 需要额外查询 `COUNT` 获取总数

### 3. PageHelper 插件分页（推荐）

PageHelper 是 MyBatis 最流行的分页插件，通过拦截器自动改写 SQL。

**配置方式**：

```xml
<!-- Maven 依赖 -->
<dependency>
    <groupId>com.github.pagehelper</groupId>
    <artifactId>pagehelper-spring-boot-starter</artifactId>
    <version>1.4.7</version>
</dependency>

<!-- MyBatis 配置文件 -->
<plugins>
    <plugin interceptor="com.github.pagehelper.PageInterceptor">
        <property name="helperDialect" value="mysql"/>
        <property name="reasonable" value="true"/>
        <property name="supportMethodsArguments" value="true"/>
    </plugin>
</plugins>
```

**使用示例**：

```java
// 1. 开启分页（线程安全，基于 ThreadLocal）
PageHelper.startPage(pageNum, pageSize);

// 2. 执行查询（紧跟的第一个查询会被分页）
List<User> users = userMapper.selectAll();

// 3. 获取分页信息
PageInfo<User> pageInfo = new PageInfo<>(users);
System.out.println("总记录数：" + pageInfo.getTotal());
System.out.println("总页数：" + pageInfo.getPages());
```

**核心原理**：

1. **拦截器机制**：PageHelper 实现了 MyBatis 的 `Interceptor` 接口，拦截 `Executor.query()` 方法
2. **SQL 改写**：
   - 自动在原始 SQL 后追加 `LIMIT` 子句（MySQL）
   - 自动执行 `COUNT` 查询获取总记录数
3. **ThreadLocal 传参**：通过 `ThreadLocal` 存储分页参数，执行完自动清理

**拦截示例**：

```java
// 原始 SQL
SELECT * FROM user WHERE status = 1

// PageHelper 自动改写后
SELECT COUNT(0) FROM user WHERE status = 1  -- 先查总数
SELECT * FROM user WHERE status = 1 LIMIT 10, 20  -- 再分页查询
```

## 三、性能优化与注意事项

### 1. 深分页问题

当 `OFFSET` 很大时（如 `LIMIT 100000, 10`），MySQL 仍需扫描前 100000 条记录：

**优化方案**：

```sql
-- 不推荐：深分页性能差
SELECT * FROM user ORDER BY id LIMIT 100000, 10;

-- 推荐：使用子查询 + 索引覆盖
SELECT * FROM user 
WHERE id >= (SELECT id FROM user ORDER BY id LIMIT 100000, 1)
LIMIT 10;

-- 推荐：记录上次最大 ID（适合无限滚动）
SELECT * FROM user WHERE id > #{lastMaxId} ORDER BY id LIMIT 10;
```

### 2. PageHelper 使用注意点

```java
// ❌ 错误：中间有其他操作，分页参数会丢失
PageHelper.startPage(1, 10);
someOtherMethod();  // 分页参数被清理
List<User> users = userMapper.selectAll();  // 不会分页

// ✅ 正确：紧跟查询
PageHelper.startPage(1, 10);
List<User> users = userMapper.selectAll();

// ✅ 推荐：使用 Lambda 表达式确保安全
PageInfo<User> pageInfo = PageHelper.startPage(1, 10)
    .doSelectPageInfo(() -> userMapper.selectAll());
```

### 3. COUNT 查询优化

```java
// 设置不查询总数，提升性能（适合不需要显示总页数的场景）
PageHelper.startPage(pageNum, pageSize, false);
List<User> users = userMapper.selectAll();
```

## 四、面试总结

**推荐回答思路**：

1. **先说三种方式**：逻辑分页（RowBounds）、物理分页（手写 SQL）、插件分页（PageHelper）
2. **重点介绍 PageHelper**：基于拦截器自动改写 SQL，支持多数据库方言，使用 ThreadLocal 传参
3. **补充优化点**：深分页优化（子查询/记录上次位置）、COUNT 查询可选
4. **实际经验**：生产环境推荐 PageHelper + 索引优化 + 合理的分页大小（如 10-50 条）

**加分项**：
- 提到过 PageHelper 的原理（拦截 Executor、SQL 改写、ThreadLocal）
- 说出深分页的优化方案
- 了解不同数据库的分页语法差异（MySQL LIMIT、Oracle ROWNUM、PostgreSQL OFFSET）
