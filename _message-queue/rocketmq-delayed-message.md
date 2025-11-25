---
title: "RocketMQ的延迟消息是如何实现的？"
date: 2025-11-02
categories: [中间件, RocketMQ]
tags: [RocketMQ, 延迟消息, 定时任务, 消息队列]
description: "深入解析RocketMQ延迟消息的实现原理、调度机制及应用场景，理解如何通过18个延迟级别实现定时消息投递。"
nav_order: 551
parent: 消息队列
---
## 一、核心概念

**延迟消息（Delayed Message）**是指消息发送到 Broker 后，不会立即被消费者消费，而是在**指定的延迟时间后**才能被消费的一种消息类型。

**典型应用场景**：
- 订单超时自动取消（30分钟未支付）
- 定时任务触发（每天凌晨数据统计）
- 延迟通知（用户注册7天后发送提醒）
- 限时优惠到期处理

## 二、延迟消息的使用

### 1. 基本使用方式

```java
// 创建延迟消息
Message msg = new Message("TopicA", "TagA", "延迟消息内容".getBytes());

// 设置延迟级别（1-18，对应不同延迟时间）
// 3 表示延迟 10 秒
msg.setDelayTimeLevel(3);

// 发送消息
SendResult result = producer.send(msg);
```

### 2. 延迟级别对照表

RocketMQ **不支持任意时间的延迟**，只支持**预设的18个延迟级别**：

```java
// MessageStoreConfig.java 中的定义
private String messageDelayLevel = 
    "1s 5s 10s 30s 1m 2m 3m 4m 5m 6m 7m 8m 9m 10m 20m 30m 1h 2h";
```

| 延迟级别 | 延迟时间 | 延迟级别 | 延迟时间 |
|---------|---------|---------|---------|
| 1 | 1秒 | 10 | 6分钟 |
| 2 | 5秒 | 11 | 7分钟 |
| 3 | 10秒 | 12 | 8分钟 |
| 4 | 30秒 | 13 | 9分钟 |
| 5 | 1分钟 | 14 | 10分钟 |
| 6 | 2分钟 | 15 | 20分钟 |
| 7 | 3分钟 | 16 | 30分钟 |
| 8 | 4分钟 | 17 | 1小时 |
| 9 | 5分钟 | 18 | 2小时 |

### 3. 实际应用示例

```java
/**
 * 订单超时取消场景
 */
public void createOrder(Order order) {
    // 1. 创建订单
    orderService.save(order);
    
    // 2. 发送延迟消息（30分钟后检查订单状态）
    Message msg = new Message(
        "ORDER_TIMEOUT_TOPIC",
        "CANCEL",
        order.getId().toString().getBytes()
    );
    
    // 设置延迟级别16（30分钟）
    msg.setDelayTimeLevel(16);
    producer.send(msg);
}

/**
 * 消费者：检查并取消超时订单
 */
@Override
public ConsumeConcurrentlyStatus consumeMessage(
        List<MessageExt> msgs, ConsumeConcurrentlyContext context) {
    
    for (MessageExt msg : msgs) {
        String orderId = new String(msg.getBody());
        
        // 查询订单状态
        Order order = orderService.getById(orderId);
        
        // 如果订单仍未支付，执行取消逻辑
        if (order.getStatus() == OrderStatus.UNPAID) {
            orderService.cancelOrder(orderId);
            log.info("订单{}超时未支付，已自动取消", orderId);
        }
    }
    
    return ConsumeConcurrentlyStatus.CONSUME_SUCCESS;
}
```

## 三、延迟消息的实现原理

### 1. 核心设计思路

RocketMQ 延迟消息的实现**不是通过定时器**，而是通过**特殊的Topic + 后台调度**实现：

```
普通消息流程：
Producer → Topic-QueueId → Consumer

延迟消息流程：
Producer → SCHEDULE_TOPIC_XXXX（替换Topic）
         → 定时调度服务
         → 原始Topic-QueueId → Consumer
```

### 2. 实现步骤详解

**第一步：消息投递时的 Topic 替换**

```java
// ScheduleMessageService.java

// 1. 接收到延迟消息，获取延迟级别
int delayLevel = msg.getDelayTimeLevel();

// 2. 替换 Topic 为内部延迟主题
String topic = TopicValidator.RMQ_SYS_SCHEDULE_TOPIC; // "SCHEDULE_TOPIC_XXXX"

// 3. 计算目标 QueueId（延迟级别 - 1）
int queueId = delayLevel - 1; // delayLevel=3 → queueId=2

// 4. 保存原始 Topic 和 QueueId 到消息属性
msg.putProperty(MessageConst.PROPERTY_REAL_TOPIC, originalTopic);
msg.putProperty(MessageConst.PROPERTY_REAL_QUEUE_ID, originalQueueId);

// 5. 计算投递时间（当前时间 + 延迟时间）
long deliverTime = System.currentTimeMillis() + delayTime;
msg.putProperty(MessageConst.PROPERTY_TIMER_DELIVER_MS, deliverTime);

// 6. 写入 SCHEDULE_TOPIC_XXXX 的对应队列
commitLog.putMessage(msg);
```

**为什么要替换 Topic？**
- 避免延迟消息被消费者立即消费
- 所有延迟消息统一管理在 `SCHEDULE_TOPIC_XXXX` 中
- 每个延迟级别对应一个 ConsumeQueue（queueId = delayLevel - 1）

**第二步：后台调度服务**

```java
// ScheduleMessageService.java

public class ScheduleMessageService {
    
    // 每个延迟级别对应一个定时任务
    private final ConcurrentMap<Integer, Timer> deliverExecutorService;
    
    public void start() {
        // 为每个延迟级别创建一个定时任务
        for (int i = 1; i <= 18; i++) {
            long delayTime = delayLevelTable.get(i); // 如 level 3 = 10s
            
            Timer timer = new Timer("ScheduleMessageTimerThread_" + i);
            
            // 定时任务：每隔 delayTime/2 检查一次
            timer.schedule(new DeliverDelayedMessageTimerTask(i), 
                           delayTime / 2, 
                           delayTime / 2);
        }
    }
}

class DeliverDelayedMessageTimerTask extends TimerTask {
    
    private int delayLevel;
    
    @Override
    public void run() {
        // 1. 从 SCHEDULE_TOPIC_XXXX 的 queueId=(delayLevel-1) 中读取消息
        ConsumeQueue cq = findConsumeQueue("SCHEDULE_TOPIC_XXXX", delayLevel - 1);
        
        // 2. 遍历 ConsumeQueue，检查消息的投递时间
        for (CqUnit unit : cq) {
            long deliverTime = parseDeliverTime(unit);
            long now = System.currentTimeMillis();
            
            // 3. 如果到达投递时间，恢复原始 Topic
            if (now >= deliverTime) {
                MessageExt msg = getMessageByOffset(unit.getPhysicalOffset());
                
                // 恢复原始 Topic 和 QueueId
                String realTopic = msg.getProperty(MessageConst.PROPERTY_REAL_TOPIC);
                String realQueueId = msg.getProperty(MessageConst.PROPERTY_REAL_QUEUE_ID);
                
                msg.setTopic(realTopic);
                msg.setQueueId(Integer.parseInt(realQueueId));
                
                // 4. 重新写入 CommitLog（以原始 Topic 的身份）
                commitLog.putMessage(msg);
            } else {
                break; // 未到投递时间，后续消息也不会到
            }
        }
    }
}
```

### 3. 数据存储结构

```
CommitLog 中的延迟消息：
+------------------+
| Topic: SCHEDULE_TOPIC_XXXX
| QueueId: 2 (delayLevel=3)
| Properties:
|   - REAL_TOPIC: OrderTopic
|   - REAL_QUEUE_ID: 5
|   - TIMER_DELIVER_MS: 1699000000000
+------------------+

到期后重新写入 CommitLog：
+------------------+
| Topic: OrderTopic  ← 恢复原始Topic
| QueueId: 5         ← 恢复原始QueueId
| 消息内容不变
+------------------+
```

### 4. 关键实现细节

**1) 为什么每个延迟级别一个 Timer？**
- 不同延迟级别的消息到期时间差异大
- 独立调度避免长延迟任务阻塞短延迟任务
- 每个 Timer 只扫描自己对应的 ConsumeQueue

**2) 为什么延迟消息要重新写入 CommitLog？**
- 保持消息的顺序性和一致性
- 原始 Topic 的 Consumer 只能看到正常的消息
- 便于消息持久化和主从同步

**3) 调度精度如何保证？**
```java
// 定时任务的执行间隔 = 延迟时间 / 2
// 例如：10秒延迟级别，每5秒扫描一次

// 扫描时的时间判断
if (System.currentTimeMillis() >= deliverTime) {
    deliverMessage(); // 立即投递
}
```

## 四、延迟消息的限制与优化

### 1. 主要限制

**① 不支持任意时间延迟**
```java
// ❌ 不支持：延迟 25 分钟
msg.setDelayTime(25, TimeUnit.MINUTES); // 无此API

// ✅ 只能用预设级别（20分钟或30分钟）
msg.setDelayTimeLevel(15); // 20分钟
```

**② 延迟时间不可修改**
- 消息一旦发送，延迟时间无法更改
- 需要取消延迟消息，只能消费后不处理

**③ 最大延迟时间 2 小时**
- 默认最大延迟级别 18 = 2小时
- 可通过修改配置扩展，但不建议设置过长

### 2. 自定义延迟级别

```properties
# broker.conf
messageDelayLevel=1s 5s 10s 30s 1m 2m 3m 4m 5m 6m 7m 8m 9m 10m 20m 30m 1h 2h 6h 12h

# 重启 Broker 后生效
```

### 3. 长延迟时间的替代方案

如果需要**超长延迟**（如7天后提醒），建议：

**方案1：数据库 + 定时任务**
```java
// 将延迟任务存入数据库
@Scheduled(cron = "0 */5 * * * ?") // 每5分钟扫描
public void scanDelayedTasks() {
    List<Task> tasks = taskMapper.selectDueTasks(new Date());
    for (Task task : tasks) {
        sendMessage(task); // 发送即时消息
        taskMapper.updateStatus(task.getId(), "SENT");
    }
}
```

**方案2：多级延迟**
```java
// 第一次：延迟2小时
msg.setDelayTimeLevel(18);

// 消费者收到后，判断是否需要继续延迟
if (remainingTime > 0) {
    Message newMsg = new Message(topic, body);
    newMsg.setDelayTimeLevel(calculateLevel(remainingTime));
    producer.send(newMsg); // 递归延迟
} else {
    processTask(); // 真正执行任务
}
```

**方案3：RocketMQ 5.0 定时消息**（推荐）
```java
// RocketMQ 5.0+ 支持任意时间延迟
Message msg = new Message("TopicA", "Body".getBytes());

// 指定精确的投递时间戳
long deliverTime = System.currentTimeMillis() + TimeUnit.DAYS.toMillis(7);
msg.setDeliverTimeMs(deliverTime);

producer.send(msg);
```

## 五、性能与监控

### 1. 性能考量

- **延迟消息不影响普通消息**：独立的 Topic 和调度线程
- **大量延迟消息**：注意磁盘占用（延迟期间消息一直在 CommitLog）
- **调度开销**：18个定时线程，CPU 开销较小

### 2. 监控指标

```bash
# 查看延迟消息堆积情况
sh mqadmin topicstatus -n localhost:9876 -t SCHEDULE_TOPIC_XXXX

# 查看各延迟级别的消息数量
sh mqadmin consumerProgress -n localhost:9876 -g SCHEDULE_GROUP
```

## 六、面试总结

### 核心原理

1. **Topic 替换**：延迟消息先发到 `SCHEDULE_TOPIC_XXXX`
2. **按级别分队列**：18个延迟级别对应18个队列
3. **定时扫描**：每个级别一个 Timer，定时检查到期消息
4. **重新投递**：到期后恢复原始 Topic，重新写入 CommitLog

### 关键代码流程

```java
// 1. 发送时：替换 Topic，保存原始信息
msg.setTopic("SCHEDULE_TOPIC_XXXX");
msg.setQueueId(delayLevel - 1);
msg.setProperty("REAL_TOPIC", originalTopic);

// 2. 定时任务：检查到期时间
if (now >= deliverTime) {
    // 恢复原始 Topic，重新投递
    msg.setTopic(realTopic);
    commitLog.putMessage(msg);
}
```

### 答题要点

1. **不支持任意延迟**：只有18个固定级别
2. **实现机制**：临时 Topic + 定时扫描 + 重新投递
3. **性能隔离**：不影响普通消息的吞吐量
4. **应用场景**：订单超时、定时任务、延迟通知
5. **长延迟方案**：数据库 + 定时任务，或 RocketMQ 5.0

---

**延伸问题**：
- RocketMQ 延迟消息和 RabbitMQ 的 TTL + 死信队列有什么区别？
- 如果要实现任意时间的延迟消息，该如何设计？
- RocketMQ 5.0 的定时消息是如何优化的？

