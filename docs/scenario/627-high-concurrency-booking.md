---
layout: default
title: "万级TPS的1v1约课场景如何设计？"
parent: 大厂项目场景实战
nav_order: 627
description: "通过在线教育约课场景讲解万级TPS的高并发系统设计"
date: 2025-12-28
---

# 万级TPS的1v1约课场景如何设计？

## 业务场景

某大型在线教育公司，1v1英语教育业务，注册学员百万量级。

**核心场景**：每周五中午12点开放预约下周课程，百万用户抢约心仪老师。

**挑战**：
- 峰值TPS达万级别
- 持续时间约10分钟
- 平时QPS仅几百

---

## 高并发解决方案概览

```
┌─────────────────────────────────────────────────────────┐
│                   高并发解决思路                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   读多写少场景:                                          │
│     • 横向扩容                                          │
│     • 引入缓存（Redis）                                  │
│     • 引入ES（复杂查询）                                 │
│                                                         │
│   写多读少场景:                                          │
│     • MQ削峰（瞬时流量）                                 │
│     • 分库分表（持续流量）                               │
│     • 单元化（超大规模）                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

约课场景属于**瞬时高并发写**，核心方案是**MQ削峰**。

---

## 方案设计

### 架构图

```
   用户请求
      │
      ↓
┌─────────────────┐     ┌─────────────┐     ┌─────────────────┐
│ 约课前置服务      │ →→→ │   Kafka     │ →→→ │    约课服务      │
│ (高吞吐生产者)    │     │  (削峰缓冲) │     │  (慢慢消费处理)   │
└─────────────────┘     └─────────────┘     └─────────────────┘
      ↓
  快速返回
 "约课已提交"
```

### 核心思路

1. **前置服务**：只做参数校验，写Kafka，快速返回
2. **Kafka**：承接峰值流量，缓冲消息
3. **约课服务**：按自身处理能力消费，执行完整业务逻辑

---

## 实现细节

### 1. 约课前置服务

```java
@RestController
public class BookingPreController {
    
    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    @PostMapping("/api/booking/submit")
    public Result submitBooking(@RequestBody BookingRequest request) {
        // 1. 参数校验
        validateRequest(request);
        
        // 2. 生成约课单号
        String bookingId = generateBookingId(request.getUserId());
        
        // 3. 写Kafka（异步高吞吐）
        BookingMessage message = new BookingMessage();
        message.setBookingId(bookingId);
        message.setUserId(request.getUserId());
        message.setTeacherId(request.getTeacherId());
        message.setSlotTime(request.getSlotTime());
        
        kafkaTemplate.send("booking-topic", 
                          request.getUserId().toString(),
                          JSON.toJSONString(message));
        
        // 4. 写Redis（用于用户查看处理中的约课）
        String key = "booking:pending:" + request.getUserId();
        redisTemplate.opsForList().leftPush(key, JSON.toJSONString(message));
        
        // 5. 快速返回
        return Result.success("约课已提交，请在'我的预约'中查看结果");
    }
}
```

### 2. Kafka生产者调优

```java
@Configuration
public class KafkaProducerConfig {
    
    @Bean
    public ProducerFactory<String, String> producerFactory() {
        Map<String, Object> config = new HashMap<>();
        config.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092");
        
        // 吞吐量优化
        config.put(ProducerConfig.ACKS_CONFIG, "0");  // 不等待确认
        config.put(ProducerConfig.BATCH_SIZE_CONFIG, 32768);  // 32KB
        config.put(ProducerConfig.LINGER_MS_CONFIG, 50);  // 等待50ms
        config.put(ProducerConfig.BUFFER_MEMORY_CONFIG, 67108864);  // 64MB
        config.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "lz4");
        config.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 100);
        
        return new DefaultKafkaProducerFactory<>(config);
    }
}
```

**说明**：牺牲可靠性换取吞吐量，因为约课场景：
- 抢购失败本来就是正常结果
- 少量消息丢失可接受（用户可重试）

### 3. 约课服务（消费者）

```java
@Service
public class BookingService {
    
    @KafkaListener(topics = "booking-topic", concurrency = "10")
    public void processBooking(ConsumerRecord<String, String> record) {
        BookingMessage message = JSON.parseObject(record.value(), BookingMessage.class);
        
        try {
            // 1. 检查时间槽是否可用
            boolean available = checkSlotAvailable(message.getTeacherId(), 
                                                   message.getSlotTime());
            
            if (!available) {
                // 时间槽已被占用
                saveBookingResult(message, BookingStatus.FAILED, "该时间段已被预约");
                return;
            }
            
            // 2. 锁定时间槽（分布式锁）
            String lockKey = "slot:lock:" + message.getTeacherId() + ":" + message.getSlotTime();
            boolean locked = redisLock.tryLock(lockKey, 10, TimeUnit.SECONDS);
            
            if (!locked) {
                saveBookingResult(message, BookingStatus.FAILED, "系统繁忙，请重试");
                return;
            }
            
            try {
                // 3. 再次检查（双重检查）
                if (!checkSlotAvailable(message.getTeacherId(), message.getSlotTime())) {
                    saveBookingResult(message, BookingStatus.FAILED, "该时间段已被预约");
                    return;
                }
                
                // 4. 执行业务逻辑
                doBooking(message);
                
                // 5. 保存成功结果
                saveBookingResult(message, BookingStatus.SUCCESS, "预约成功");
                
            } finally {
                redisLock.unlock(lockKey);
            }
            
        } catch (Exception e) {
            log.error("处理约课失败", e);
            saveBookingResult(message, BookingStatus.FAILED, "系统异常");
        }
        
    }
    
    private void doBooking(BookingMessage message) {
        // 1. 占用老师时间槽
        teacherSlotMapper.occupy(message.getTeacherId(), message.getSlotTime());
        
        // 2. 扣减课时
        userCourseMapper.deductHours(message.getUserId(), 1);
        
        // 3. 创建课程记录
        lessonMapper.insert(createLesson(message));
        
        // 4. 发送通知
        notifyService.sendBookingNotification(message);
    }
}
```

---

## 用户查询处理中的约课

### 问题

Kafka消费有延迟，用户提交后几分钟内看不到约课结果。

### 解决方案：Kafka + Redis List

```java
@RestController
public class BookingQueryController {
    
    @GetMapping("/api/booking/my")
    public Result getMyBookings(@RequestParam Long userId) {
        // 1. 从MySQL获取已处理的约课
        List<Booking> completedBookings = bookingMapper.findByUserId(userId);
        
        // 2. 从Redis获取处理中的约课
        String key = "booking:pending:" + userId;
        List<String> pendingJson = redisTemplate.opsForList().range(key, 0, -1);
        List<BookingVO> pendingBookings = pendingJson.stream()
            .map(json -> JSON.parseObject(json, BookingVO.class))
            .collect(Collectors.toList());
        
        // 3. 合并返回
        return Result.success(merge(completedBookings, pendingBookings));
    }
}
```

### 处理完成后清理Redis

```java
private void saveBookingResult(BookingMessage message, BookingStatus status, String msg) {
    // 1. 保存到MySQL
    Booking booking = new Booking();
    booking.setBookingId(message.getBookingId());
    booking.setUserId(message.getUserId());
    booking.setStatus(status);
    booking.setMessage(msg);
    bookingMapper.insert(booking);
    
    // 2. 从Redis的pending列表中移除
    String key = "booking:pending:" + message.getUserId();
    redisTemplate.opsForList().remove(key, 1, JSON.toJSONString(message));
}
```

---

## 性能数据

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 峰值TPS | 500（系统崩溃） | 15000+ |
| 用户响应时间 | 超时 | 100ms内 |
| 约课结果延迟 | - | 2-5分钟 |
| 系统稳定性 | 宕机 | 稳定运行 |

---

## 面试答题框架

```
业务场景：每周五12点约课高峰，TPS达万级

核心方案：MQ削峰
  - 前置服务：参数校验 + 写Kafka + 快速返回
  - Kafka：缓冲峰值流量
  - 约课服务：按自身能力处理

关键优化：
  - 生产者调优：acks=0, batch.size=32KB, linger.ms=50
  - Redis List：处理中订单实时展示
  - 分布式锁：防止时间槽超卖

效果：TPS从500提升到15000+
```

---

## 总结

| 设计点 | 方案 |
|--------|------|
| 流量入口 | 约课前置服务（轻量级） |
| 削峰 | Kafka缓冲 |
| 生产者 | 高吞吐配置 |
| 用户体验 | Redis List暂存处理中数据 |
| 防超卖 | 分布式锁 + 双重检查 |
