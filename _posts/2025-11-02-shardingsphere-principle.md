---
layout: post
title: "ShardingSphere的原理是什么？"
date: 2025-11-02
description: "深入剖析ShardingSphere的核心架构、SQL解析与路由原理、改写与执行流程，掌握分库分表中间件的实现机制"
author: "wuxl"
categories: [分布式]
tags: [ShardingSphere, 分库分表, 中间件, SQL路由, 结果归并]
---

## 问题

ShardingSphere的原理是什么?

## 答案

### 1. 核心概念

**Apache ShardingSphere** 是一套开源的分布式数据库中间件解决方案，提供分库分表、读写分离、数据加密、影子库等功能。它的核心目标是**让应用程序像访问单库一样访问分片后的多个数据库**。

### 2. ShardingSphere生态

ShardingSphere包含三个产品：

| 产品 | 定位 | 部署方式 | 适用场景 |
|------|------|---------|----------|
| **ShardingSphere-JDBC** | 轻量级Java框架 | 应用内嵌，jar包依赖 | 性能要求高，Java应用 |
| **ShardingSphere-Proxy** | 透明化数据库代理 | 独立进程部署 | 异构语言，多语言支持 |
| **ShardingSphere-Sidecar** | Service Mesh形态 | Kubernetes环境 | 云原生场景 |

**本文主要讨论 ShardingSphere-JDBC** 的原理。

### 3. 核心架构

```
┌─────────────────────────────────────────────────┐
│              应用程序（Application）              │
└────────────────────┬────────────────────────────┘
                     │ SQL
                     ↓
┌─────────────────────────────────────────────────┐
│           ShardingSphere-JDBC                   │
│  ┌──────────────────────────────────────────┐   │
│  │  1. SQL解析（SQL Parser）                 │   │
│  │     - 词法解析、语法解析                  │   │
│  │     - 生成SQL抽象语法树（AST）             │   │
│  └──────────────────────────────────────────┘   │
│                     ↓                            │
│  ┌──────────────────────────────────────────┐   │
│  │  2. SQL路由（SQL Router）                 │   │
│  │     - 根据分片策略计算目标库表            │   │
│  │     - 生成路由结果                        │   │
│  └──────────────────────────────────────────┘   │
│                     ↓                            │
│  ┌──────────────────────────────────────────┐   │
│  │  3. SQL改写（SQL Rewriter）               │   │
│  │     - 逻辑表名 → 真实表名                 │   │
│  │     - 补充分页、排序等信息                │   │
│  └──────────────────────────────────────────┘   │
│                     ↓                            │
│  ┌──────────────────────────────────────────┐   │
│  │  4. SQL执行（SQL Executor）               │   │
│  │     - 多线程并发执行                      │   │
│  │     - 连接池管理                          │   │
│  └──────────────────────────────────────────┘   │
│                     ↓                            │
│  ┌──────────────────────────────────────────┐   │
│  │  5. 结果归并（Result Merger）             │   │
│  │     - 聚合、排序、分页                    │   │
│  │     - 返回统一结果集                      │   │
│  └──────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────┘
                     ↓
      ┌──────────────┴──────────────┐
      ↓              ↓               ↓
   ┌────┐        ┌────┐          ┌────┐
   │DB_0│        │DB_1│          │DB_2│
   └────┘        └────┘          └────┘
```

### 4. 核心流程详解

#### 4.1 SQL解析（Parsing）

**目的**：将SQL字符串解析为抽象语法树（AST）

```java
// 原始SQL
String sql = "SELECT * FROM t_order WHERE user_id = 100 AND order_id = 1001";

// ShardingSphere内部处理
public class SQLParserEngine {

    public SQLStatement parse(String sql) {
        // 1. 词法分析：将SQL分解为token
        List<Token> tokens = lexer.tokenize(sql);
        // [SELECT, *, FROM, t_order, WHERE, user_id, =, 100, AND, order_id, =, 1001]

        // 2. 语法分析：生成抽象语法树
        SQLStatement statement = parser.parse(tokens);

        // 3. 提取关键信息
        // - 表名：t_order（逻辑表）
        // - 分片键：user_id = 100, order_id = 1001
        // - 查询列：*

        return statement;
    }
}
```

#### 4.2 SQL路由（Routing）

**目的**：根据分片策略计算SQL应该路由到哪些数据库和表

```java
// 分片配置
spring.shardingsphere.rules.sharding.tables.t_order.actual-data-nodes=ds_$->{0..1}.t_order_$->{0..3}
spring.shardingsphere.rules.sharding.tables.t_order.database-strategy.standard.sharding-column=user_id
spring.shardingsphere.rules.sharding.tables.t_order.database-strategy.standard.sharding-algorithm-name=db-mod
spring.shardingsphere.rules.sharding.tables.t_order.table-strategy.standard.sharding-column=order_id
spring.shardingsphere.rules.sharding.tables.t_order.table-strategy.standard.sharding-algorithm-name=table-mod

// 路由引擎
public class ShardingRouteEngine {

    public RouteResult route(SQLStatement sqlStatement) {
        // 提取分片键值
        ShardingCondition condition = new ShardingCondition();
        condition.put("user_id", 100);
        condition.put("order_id", 1001);

        // 1. 计算目标数据库
        String targetDb = dbShardingAlgorithm.doSharding(
            Arrays.asList("ds_0", "ds_1"),  // 可用数据源
            new ShardingValue("user_id", 100)
        );
        // 结果：user_id=100, 100 % 2 = 0, 路由到 ds_0

        // 2. 计算目标表
        String targetTable = tableShardingAlgorithm.doSharding(
            Arrays.asList("t_order_0", "t_order_1", "t_order_2", "t_order_3"),
            new ShardingValue("order_id", 1001)
        );
        // 结果：order_id=1001, 1001 % 4 = 1, 路由到 t_order_1

        // 返回路由结果
        return new RouteResult("ds_0", "t_order_1");
    }
}
```

**路由类型**：

| 路由类型 | 说明 | 示例 |
|---------|------|------|
| **直接路由** | 通过Hint指定 | `HintManager.setDatabaseShardingValue("ds_0")` |
| **标准路由** | 包含分片键的单表查询 | `WHERE user_id = 100` |
| **笛卡尔路由** | 多表关联且分片键不同 | `t_order JOIN t_user` |
| **广播路由** | 全库表查询 | `SELECT * FROM t_order`（无分片键） |

#### 4.3 SQL改写（Rewriting）

**目的**：将逻辑SQL改写为实际可执行的物理SQL

```java
public class SQLRewriteEngine {

    public String rewrite(String logicalSQL, RouteResult routeResult) {
        String rewrittenSQL = logicalSQL;

        // 1. 表名改写
        rewrittenSQL = rewrittenSQL.replace("t_order", "t_order_1");

        // 2. 分页改写（LIMIT优化）
        // 原SQL：SELECT * FROM t_order ORDER BY order_id LIMIT 10, 20
        // 改写：SELECT * FROM t_order_1 ORDER BY order_id LIMIT 0, 30
        // 原因：需要从每个分片取前30条，归并后再取10-30

        // 3. AVG改写
        // 原SQL：SELECT AVG(amount) FROM t_order
        // 改写：SELECT SUM(amount), COUNT(amount) FROM t_order_1
        // 原因：归并时需要重新计算平均值

        return rewrittenSQL;
    }
}

// 改写示例
// 原始SQL：
SELECT * FROM t_order WHERE user_id = 100 ORDER BY order_id LIMIT 10, 10

// 路由到：ds_0.t_order_0, ds_0.t_order_1

// 改写后的SQL：
// ds_0.t_order_0: SELECT * FROM t_order_0 WHERE user_id = 100 ORDER BY order_id LIMIT 0, 20
// ds_0.t_order_1: SELECT * FROM t_order_1 WHERE user_id = 100 ORDER BY order_id LIMIT 0, 20
```

#### 4.4 SQL执行（Execution）

**目的**：多线程并发执行改写后的SQL

```java
public class SQLExecuteEngine {

    private ExecutorService executorService;

    public List<QueryResult> execute(List<RouteUnit> routeUnits) {
        // 1. 创建执行任务
        List<Callable<QueryResult>> tasks = routeUnits.stream()
            .map(unit -> (Callable<QueryResult>) () -> {
                Connection conn = getConnection(unit.getDataSource());
                PreparedStatement ps = conn.prepareStatement(unit.getSql());
                return ps.executeQuery();
            })
            .collect(Collectors.toList());

        // 2. 并发执行
        try {
            List<Future<QueryResult>> futures = executorService.invokeAll(tasks);

            // 3. 收集结果
            return futures.stream()
                .map(future -> {
                    try {
                        return future.get();
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                })
                .collect(Collectors.toList());
        } catch (InterruptedException e) {
            throw new RuntimeException(e);
        }
    }
}
```

**执行策略**：
- **内存限制执行引擎**：默认，适合OLTP场景
- **连接限制执行引擎**：限制连接数，适合OLAP场景

#### 4.5 结果归并（Merging）

**目的**：将多个分片的结果合并为统一结果集

```java
public class ResultMergeEngine {

    public ResultSet merge(List<QueryResult> queryResults, SQLStatement sqlStatement) {
        if (sqlStatement instanceof SelectStatement) {
            SelectStatement select = (SelectStatement) sqlStatement;

            // 1. 遍历归并（无需排序）
            if (!select.hasOrderBy() && !select.hasGroupBy()) {
                return new IteratorStreamMergedResult(queryResults);
            }

            // 2. 排序归并（ORDER BY）
            if (select.hasOrderBy()) {
                return new OrderByStreamMergedResult(queryResults, select.getOrderBy());
            }

            // 3. 分组归并（GROUP BY）
            if (select.hasGroupBy()) {
                return new GroupByStreamMergedResult(queryResults, select.getGroupBy());
            }

            // 4. 聚合归并（SUM, COUNT, AVG等）
            if (select.hasAggregation()) {
                return new AggregationMergedResult(queryResults, select.getAggregations());
            }
        }

        return new TransparentMergedResult(queryResults.get(0));
    }
}
```

**归并类型**：

| 归并类型 | 说明 | 实现方式 |
|---------|------|---------|
| **遍历归并** | 简单遍历所有结果 | Iterator模式 |
| **排序归并** | ORDER BY场景 | 优先队列（堆排序） |
| **分组归并** | GROUP BY场景 | 先排序后分组 |
| **聚合归并** | SUM/COUNT/AVG等 | 内存计算 |
| **分页归并** | LIMIT场景 | 跳过+限制 |

### 5. 配置示例

#### 5.1 基于YAML的配置

```yaml
spring:
  shardingsphere:
    # 数据源配置
    datasource:
      names: ds-0,ds-1
      ds-0:
        type: com.zaxxer.hikari.HikariDataSource
        driver-class-name: com.mysql.cj.jdbc.Driver
        jdbc-url: jdbc:mysql://localhost:3306/db_0
        username: root
        password: root
      ds-1:
        type: com.zaxxer.hikari.HikariDataSource
        driver-class-name: com.mysql.cj.jdbc.Driver
        jdbc-url: jdbc:mysql://localhost:3306/db_1
        username: root
        password: root

    # 分片规则
    rules:
      sharding:
        tables:
          t_order:
            # 实际节点
            actual-data-nodes: ds-$->{0..1}.t_order_$->{0..3}

            # 分库策略
            database-strategy:
              standard:
                sharding-column: user_id
                sharding-algorithm-name: db-mod

            # 分表策略
            table-strategy:
              standard:
                sharding-column: order_id
                sharding-algorithm-name: table-mod

        # 分片算法
        sharding-algorithms:
          db-mod:
            type: MOD
            props:
              sharding-count: 2

          table-mod:
            type: MOD
            props:
              sharding-count: 4

    # 显示SQL
    props:
      sql-show: true
```

#### 5.2 编程式配置

```java
@Configuration
public class ShardingConfiguration {

    @Bean
    public DataSource dataSource() {
        // 1. 配置数据源
        Map<String, DataSource> dataSourceMap = new HashMap<>();
        dataSourceMap.put("ds_0", createDataSource("db_0"));
        dataSourceMap.put("ds_1", createDataSource("db_1"));

        // 2. 配置分片规则
        ShardingRuleConfiguration shardingRuleConfig = new ShardingRuleConfiguration();

        // 2.1 配置t_order表规则
        ShardingTableRuleConfiguration orderTableRuleConfig =
            new ShardingTableRuleConfiguration("t_order", "ds_$->{0..1}.t_order_$->{0..3}");

        // 2.2 配置分库策略
        orderTableRuleConfig.setDatabaseShardingStrategy(
            new StandardShardingStrategyConfiguration("user_id", "dbShardingAlgorithm")
        );

        // 2.3 配置分表策略
        orderTableRuleConfig.setTableShardingStrategy(
            new StandardShardingStrategyConfiguration("order_id", "tableShardingAlgorithm")
        );

        shardingRuleConfig.getTables().add(orderTableRuleConfig);

        // 3. 配置分片算法
        Properties dbProps = new Properties();
        dbProps.setProperty("sharding-count", "2");
        shardingRuleConfig.getShardingAlgorithms().put("dbShardingAlgorithm",
            new AlgorithmConfiguration("MOD", dbProps));

        Properties tableProps = new Properties();
        tableProps.setProperty("sharding-count", "4");
        shardingRuleConfig.getShardingAlgorithms().put("tableShardingAlgorithm",
            new AlgorithmConfiguration("MOD", tableProps));

        // 4. 创建ShardingSphere数据源
        return ShardingSphereDataSourceFactory.createDataSource(
            dataSourceMap,
            Collections.singleton(shardingRuleConfig),
            new Properties()
        );
    }
}
```

### 6. 核心要点总结

1. **ShardingSphere-JDBC的核心是SQL拦截和改写**，通过解析-路由-改写-执行-归并五个流程实现分库分表
2. **SQL解析基于ANTLR**，支持MySQL、PostgreSQL、Oracle等多种数据库方言
3. **路由策略灵活**：支持标准路由、复合路由、Hint路由等多种方式
4. **SQL改写是关键**：逻辑表转物理表、分页优化、聚合函数改写
5. **并发执行提升性能**：多线程并行查询多个分片
6. **结果归并实现复杂**：需要处理排序、分组、聚合、分页等多种场景
7. **对应用透明**：应用无需关心底层分片逻辑，像操作单库一样使用
8. **性能优于Proxy模式**：JDBC模式直接在应用内执行,减少网络开销
