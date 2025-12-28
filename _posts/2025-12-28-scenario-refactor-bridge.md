---
layout: post
title: "如何使用桥接模式进行代码重构？"
date: 2025-12-28
categories: [大厂项目场景实战, 代码重构实战]
tags: [设计模式, 桥接模式, 代码重构, 研发提效]
description: "通过消息推送场景讲解如何使用桥接模式重构代码，实现抽象与实现的解耦。"
---

# 如何使用桥接模式进行代码重构？

## 业务场景

某系统需要向用户推送消息，有多种消息类型（普通、紧急、VIP）和多种推送渠道（短信、邮件、APP推送）。

---

## 原代码问题

### 继承爆炸

```java
// 按类型×渠道组合，类数量爆炸
public class NormalSmsMessage extends Message { }
public class NormalEmailMessage extends Message { }
public class NormalAppMessage extends Message { }
public class UrgentSmsMessage extends Message { }
public class UrgentEmailMessage extends Message { }
public class UrgentAppMessage extends Message { }
public class VipSmsMessage extends Message { }
// ... 还有更多
```

类数量 = 消息类型数 × 渠道数 = **M × N**

新增一种消息类型需要增加N个类，新增一种渠道需要增加M个类。

---

## 桥接模式解决方案

### 模式定义

将抽象部分与实现部分分离，使它们可以独立变化。

### 核心思想

```
抽象层（消息类型）
    │
    │ 组合关系
    ↓
实现层（推送渠道）
```

### 类结构

```
Message（抽象消息）
    │
    ├── send()
    │
    └── MessageSender sender  ← 桥接
    
MessageSender（发送接口）
    ├── SmsSender
    ├── EmailSender
    └── AppPushSender
```

---

## 重构后代码

### 实现层：推送渠道

```java
// 发送接口
public interface MessageSender {
    void send(String to, String content);
}

// 短信发送
@Component
public class SmsSender implements MessageSender {
    @Override
    public void send(String to, String content) {
        smsClient.send(to, content);
    }
}

// 邮件发送
@Component
public class EmailSender implements MessageSender {
    @Override
    public void send(String to, String content) {
        emailClient.send(to, "通知", content);
    }
}

// APP推送
@Component
public class AppPushSender implements MessageSender {
    @Override
    public void send(String to, String content) {
        pushClient.push(to, content);
    }
}
```

### 抽象层：消息类型

```java
// 抽象消息
public abstract class Message {
    protected MessageSender sender;  // 桥接
    
    public Message(MessageSender sender) {
        this.sender = sender;
    }
    
    public abstract void send(String to, String content);
}

// 普通消息
public class NormalMessage extends Message {
    public NormalMessage(MessageSender sender) {
        super(sender);
    }
    
    @Override
    public void send(String to, String content) {
        sender.send(to, content);
    }
}

// 紧急消息
public class UrgentMessage extends Message {
    public UrgentMessage(MessageSender sender) {
        super(sender);
    }
    
    @Override
    public void send(String to, String content) {
        // 紧急消息加前缀
        sender.send(to, "【紧急】" + content);
        // 紧急消息还要电话通知
        phoneCall(to);
    }
}

// VIP消息
public class VipMessage extends Message {
    public VipMessage(MessageSender sender) {
        super(sender);
    }
    
    @Override
    public void send(String to, String content) {
        // VIP专属格式
        sender.send(to, "尊敬的VIP用户：" + content);
    }
}
```

### 使用方式

```java
@Service
public class NotificationService {
    
    @Autowired
    private SmsSender smsSender;
    
    @Autowired
    private EmailSender emailSender;
    
    public void notifyUser(User user, String content, MessageType type) {
        MessageSender sender = chooseSender(user);
        Message message = createMessage(type, sender);
        message.send(user.getContact(), content);
    }
    
    private Message createMessage(MessageType type, MessageSender sender) {
        switch (type) {
            case NORMAL: return new NormalMessage(sender);
            case URGENT: return new UrgentMessage(sender);
            case VIP: return new VipMessage(sender);
            default: throw new IllegalArgumentException();
        }
    }
}
```

---

## 优化效果

### 类数量对比

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| 类数量 | M × N | M + N |
| 3类型×3渠道 | 9个类 | 6个类 |
| 5类型×5渠道 | 25个类 | 10个类 |

### 扩展性对比

| 操作 | 重构前 | 重构后 |
|------|--------|--------|
| 新增消息类型 | 增加N个类 | 增加1个类 |
| 新增渠道 | 增加M个类 | 增加1个类 |

---

## 桥接模式 vs 其他模式

| 模式 | 目的 | 关系 |
|------|------|------|
| 桥接模式 | 分离抽象与实现 | 组合 |
| 策略模式 | 算法可替换 | 组合 |
| 装饰器模式 | 动态添加职责 | 组合 |
| 适配器模式 | 接口转换 | 组合/继承 |

**桥接模式的特点**：两个维度都会变化，需要独立扩展。

---

## 面试答题框架

```
业务场景：消息推送，类型×渠道组合

原代码问题：
- 类数量爆炸（M×N）
- 扩展需修改多处

重构方案：桥接模式
- 抽象层：消息类型
- 实现层：推送渠道
- 通过组合关系桥接

效果：
- 类数量从M×N减为M+N
- 新增类型/渠道只需增加1个类
```

---

## 总结

| 要点 | 说明 |
|------|------|
| 适用场景 | 两个维度独立变化 |
| 核心思想 | 组合优于继承 |
| 关键实现 | 抽象层持有实现层引用 |
| 扩展性 | M×N → M+N |
