---
layout: post
title: "RabbitMQ的Exchange(交换器)有哪4种类型？"
date: 2025-11-02
categories: [中间件, RabbitMQ]
tags: [RabbitMQ, Exchange, 消息路由, 中间件]
description: "详细解析RabbitMQ的4种Exchange类型：fanout、direct、topic、headers，包括路由规则、使用场景和代码示例。"
---

## 核心概念

Exchange（交换器）是 RabbitMQ 的核心路由组件，负责接收生产者的消息并根据**路由规则**分发到绑定的队列。RabbitMQ 提供 4 种 Exchange 类型，分别适用于不同的消息分发场景。

## 四种 Exchange 类型详解

### 1. Fanout Exchange（扇出交换器）

**路由规则**：忽略 routing key，将消息广播到所有绑定的队列。

**使用场景**：
- 广播通知（系统公告）
- 日志收集（同时发送到多个日志处理系统）
- 实时数据同步

**代码示例**：

```java
// 声明 fanout 交换器
channel.exchangeDeclare("logs_exchange", BuiltinExchangeType.FANOUT, true);

// 声明队列并绑定（routing key 无效，可为空）
channel.queueDeclare("queue_email", true, false, false, null);
channel.queueDeclare("queue_sms", true, false, false, null);
channel.queueBind("queue_email", "logs_exchange", "");
channel.queueBind("queue_sms", "logs_exchange", "");

// 发送消息（routing key 被忽略）
channel.basicPublish("logs_exchange", "", null, "广播消息".getBytes());
// 结果：queue_email 和 queue_sms 都会收到消息
```

**特点**：
- ✅ 性能最高（无需匹配路由键）
- ✅ 配置简单
- ❌ 无法精确控制消息分发

---

### 2. Direct Exchange（直连交换器）

**路由规则**：routing key **完全匹配** binding key 时，消息才会路由到队列。

**使用场景**：
- 日志级别分发（ERROR 日志单独处理）
- 任务优先级路由
- 精确的点对点消息

**代码示例**：

```java
// 声明 direct 交换器
channel.exchangeDeclare("direct_logs", BuiltinExchangeType.DIRECT, true);

// 绑定队列到不同的 routing key
channel.queueBind("queue_error", "direct_logs", "error");
channel.queueBind("queue_info", "direct_logs", "info");
channel.queueBind("queue_all", "direct_logs", "error");  // 一个队列可以绑定多个 key
channel.queueBind("queue_all", "direct_logs", "info");

// 发送消息
channel.basicPublish("direct_logs", "error", null, "错误日志".getBytes());
// 结果：queue_error 和 queue_all 收到消息

channel.basicPublish("direct_logs", "info", null, "普通日志".getBytes());
// 结果：queue_info 和 queue_all 收到消息
```

**特点**：
- ✅ 精确匹配，路由清晰
- ✅ 一个队列可绑定多个 routing key
- ✅ 默认交换器（AMQP default）就是 direct 类型

---

### 3. Topic Exchange（主题交换器）

**路由规则**：使用通配符进行**模式匹配**，routing key 和 binding key 都是用 `.` 分隔的单词。

**通配符规则**：
- `*`：匹配一个单词
- `#`：匹配零个或多个单词

**使用场景**：
- 多维度消息路由（地区.级别.类型）
- 日志分类（应用.模块.级别）
- 复杂的消息订阅场景

**代码示例**：

```java
// 声明 topic 交换器
channel.exchangeDeclare("topic_logs", BuiltinExchangeType.TOPIC, true);

// 绑定队列到不同的模式
channel.queueBind("queue_kern", "topic_logs", "kern.*");           // 匹配 kern.开头的
channel.queueBind("queue_critical", "topic_logs", "*.critical");   // 匹配 .critical 结尾的
channel.queueBind("queue_all", "topic_logs", "#");                 // 匹配所有消息

// 发送消息
channel.basicPublish("topic_logs", "kern.critical", null, "内核严重错误".getBytes());
// 结果：queue_kern, queue_critical, queue_all 都会收到

channel.basicPublish("topic_logs", "kern.info", null, "内核信息".getBytes());
// 结果：queue_kern, queue_all 收到

channel.basicPublish("topic_logs", "app.critical", null, "应用严重错误".getBytes());
// 结果：queue_critical, queue_all 收到
```

**实际场景示例**：

```java
// 电商订单消息路由：地区.业务.类型
channel.queueBind("queue_bj_order", "topic_orders", "beijing.order.*");
channel.queueBind("queue_all_payment", "topic_orders", "*.*.payment");
channel.queueBind("queue_urgent", "topic_orders", "#.urgent");

// 发送消息
channel.basicPublish("topic_orders", "beijing.order.payment", null, msg);
// queue_bj_order, queue_all_payment 收到

channel.basicPublish("topic_orders", "shanghai.order.urgent", null, msg);
// queue_urgent 收到
```

**特点**：
- ✅ 灵活的模式匹配
- ✅ 支持复杂的消息分发逻辑
- ❌ 性能略低于 direct 和 fanout

---

### 4. Headers Exchange（头交换器）

**路由规则**：根据消息的 **header 属性**（而非 routing key）进行匹配，通过 `x-match` 参数控制匹配模式。

**匹配模式**：
- `x-match = all`：所有 header 都要匹配
- `x-match = any`：任意一个 header 匹配即可

**使用场景**：
- 复杂的多条件路由
- 需要根据多个属性进行过滤的场景

**代码示例**：

```java
// 声明 headers 交换器
channel.exchangeDeclare("headers_exchange", BuiltinExchangeType.HEADERS, true);

// 绑定队列，设置匹配规则
Map<String, Object> headers1 = new HashMap<>();
headers1.put("x-match", "all");  // 需要全部匹配
headers1.put("format", "pdf");
headers1.put("type", "report");
channel.queueBind("queue_pdf_report", "headers_exchange", "", headers1);

Map<String, Object> headers2 = new HashMap<>();
headers2.put("x-match", "any");  // 匹配任意一个
headers2.put("format", "pdf");
headers2.put("format", "word");
channel.queueBind("queue_doc", "headers_exchange", "", headers2);

// 发送消息，设置 headers
AMQP.BasicProperties props = new AMQP.BasicProperties.Builder()
    .headers(Map.of("format", "pdf", "type", "report"))
    .build();
channel.basicPublish("headers_exchange", "", props, "PDF报告".getBytes());
// 结果：queue_pdf_report, queue_doc 都会收到（all 和 any 都匹配）

// 发送只有 format 的消息
props = new AMQP.BasicProperties.Builder()
    .headers(Map.of("format", "pdf"))
    .build();
channel.basicPublish("headers_exchange", "", props, "仅PDF".getBytes());
// 结果：只有 queue_doc 收到（all 模式缺少 type 属性）
```

**特点**：
- ✅ 支持复杂的多条件匹配
- ❌ 性能最低（需要解析 headers）
- ❌ 配置复杂，实际使用较少

---

## Exchange 类型对比

| Exchange 类型 | 路由依据 | 性能 | 使用频率 | 典型场景 |
|--------------|---------|------|---------|---------|
| **Fanout**   | 无（广播） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 系统通知、日志广播 |
| **Direct**   | routing key 完全匹配 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 日志分级、任务路由 |
| **Topic**    | routing key 模式匹配 | ⭐⭐⭐ | ⭐⭐⭐⭐ | 多维度消息分发 |
| **Headers**  | message headers 匹配 | ⭐⭐ | ⭐ | 复杂条件过滤 |

## 实战考量

### 1. Exchange 的持久化

```java
// 第三个参数为 durable，设置为 true 表示持久化
channel.exchangeDeclare("my_exchange", BuiltinExchangeType.DIRECT, true);
```

### 2. 默认 Exchange

- RabbitMQ 自带一个名为 `""` 的 direct exchange
- 每个队列自动绑定到默认交换器，binding key 为队列名
- 这就是为什么可以直接向队列发送消息

```java
// 使用默认交换器，routing key 为队列名
channel.basicPublish("", "queue_name", null, message.getBytes());
```

### 3. Alternate Exchange（备份交换器）

```java
// 为交换器设置备份交换器，处理无法路由的消息
Map<String, Object> args = new HashMap<>();
args.put("alternate-exchange", "backup_exchange");
channel.exchangeDeclare("main_exchange", "direct", true, false, args);
```

## 面试总结

**四种类型对比**：
1. **Fanout**：广播模式，忽略路由键，性能最高
2. **Direct**：精确匹配，最常用，默认交换器就是此类型
3. **Topic**：通配符匹配（`*` 和 `#`），灵活性高
4. **Headers**：基于消息头匹配，功能最强但性能最低

**选型建议**：
- 需要广播 → Fanout
- 精确路由 → Direct
- 多维度灵活路由 → Topic
- 复杂条件过滤 → Headers（少用）

**关键点**：
- Exchange 本身不存储消息，只负责路由
- 一个队列可以绑定到多个 Exchange
- 无法路由的消息会被丢弃（除非设置了 mandatory 参数或备份交换器）

