---
layout: post
title: "什么是观察者模式？"
date: 2025-11-02
description: "详解观察者模式的定义、实现原理、推模型与拉模型的区别，以及在Spring事件机制、JDK Observable、消息队列中的实际应用"
author: "wuxl"
categories: [设计模式]
tags: [观察者模式, 设计模式, 发布订阅, Spring事件, 事件驱动, 消息队列]
---

## 问题

什么是观察者模式？

## 答案

### 1. 核心概念

**观察者模式（Observer Pattern）** 是一种行为型设计模式，定义对象之间的一对多依赖关系，当一个对象（主题/被观察者）的状态发生改变时,所有依赖它的对象（观察者）都会得到通知并自动更新。

**别名**：发布-订阅模式（Publish-Subscribe Pattern）

**核心思想**：
- **主题（Subject）**：维护观察者列表，状态变化时通知所有观察者
- **观察者（Observer）**：定义更新接口，接收主题的状态变化通知

**典型应用场景**：
- GUI 事件监听（按钮点击、鼠标移动）
- Spring 事件机制（ApplicationEvent）
- 消息队列（RabbitMQ、Kafka）
- 数据绑定（Vue、React 的响应式更新）
- 日志监控、指标统计

### 2. 实现原理与代码示例

#### 基础实现：气象站数据发布

```java
// 观察者接口
interface Observer {
    void update(float temperature, float humidity, float pressure);
}

// 主题接口
interface Subject {
    void registerObserver(Observer observer);   // 注册观察者
    void removeObserver(Observer observer);     // 移除观察者
    void notifyObservers();                     // 通知所有观察者
}

// 具体主题：气象站
class WeatherStation implements Subject {
    private List<Observer> observers = new ArrayList<>();
    private float temperature;
    private float humidity;
    private float pressure;

    @Override
    public void registerObserver(Observer observer) {
        observers.add(observer);
    }

    @Override
    public void removeObserver(Observer observer) {
        observers.remove(observer);
    }

    @Override
    public void notifyObservers() {
        for (Observer observer : observers) {
            observer.update(temperature, humidity, pressure);
        }
    }

    // 状态改变时触发通知
    public void setMeasurements(float temperature, float humidity, float pressure) {
        this.temperature = temperature;
        this.humidity = humidity;
        this.pressure = pressure;
        notifyObservers(); // 通知所有观察者
    }
}

// 具体观察者1：当前天气显示
class CurrentConditionsDisplay implements Observer {
    private float temperature;
    private float humidity;

    @Override
    public void update(float temperature, float humidity, float pressure) {
        this.temperature = temperature;
        this.humidity = humidity;
        display();
    }

    private void display() {
        System.out.println("当前天气：温度 " + temperature + "°C，湿度 " + humidity + "%");
    }
}

// 具体观察者2：天气统计
class StatisticsDisplay implements Observer {
    private List<Float> temperatureHistory = new ArrayList<>();

    @Override
    public void update(float temperature, float humidity, float pressure) {
        temperatureHistory.add(temperature);
        display();
    }

    private void display() {
        float avg = (float) temperatureHistory.stream()
                .mapToDouble(Float::doubleValue)
                .average()
                .orElse(0.0);
        System.out.println("平均温度：" + String.format("%.1f", avg) + "°C");
    }
}

// 具体观察者3：天气预报
class ForecastDisplay implements Observer {
    private float currentPressure = 1013.0f;
    private float lastPressure;

    @Override
    public void update(float temperature, float humidity, float pressure) {
        lastPressure = currentPressure;
        currentPressure = pressure;
        display();
    }

    private void display() {
        if (currentPressure > lastPressure) {
            System.out.println("天气预报：天气转好");
        } else if (currentPressure < lastPressure) {
            System.out.println("天气预报：天气转差");
        } else {
            System.out.println("天气预报：天气稳定");
        }
    }
}

// 使用示例
public class Client {
    public static void main(String[] args) {
        // 创建主题
        WeatherStation weatherStation = new WeatherStation();

        // 创建观察者并注册
        CurrentConditionsDisplay currentDisplay = new CurrentConditionsDisplay();
        StatisticsDisplay statisticsDisplay = new StatisticsDisplay();
        ForecastDisplay forecastDisplay = new ForecastDisplay();

        weatherStation.registerObserver(currentDisplay);
        weatherStation.registerObserver(statisticsDisplay);
        weatherStation.registerObserver(forecastDisplay);

        // 更新天气数据（自动通知所有观察者）
        System.out.println("===== 第一次更新 =====");
        weatherStation.setMeasurements(25.5f, 65.0f, 1013.2f);

        System.out.println("\n===== 第二次更新 =====");
        weatherStation.setMeasurements(27.8f, 70.0f, 1012.5f);

        System.out.println("\n===== 移除统计显示后第三次更新 =====");
        weatherStation.removeObserver(statisticsDisplay);
        weatherStation.setMeasurements(23.2f, 60.0f, 1014.0f);
    }
}
```

**输出结果**：
```
===== 第一次更新 =====
当前天气：温度 25.5°C，湿度 65.0%
平均温度：25.5°C
天气预报：天气转好

===== 第二次更新 =====
当前天气：温度 27.8°C，湿度 70.0%
平均温度：26.6°C
天气预报：天气转差

===== 移除统计显示后第三次更新 =====
当前天气：温度 23.2°C，湿度 60.0%
天气预报：天气转好
```

### 3. 推模型 vs 拉模型

#### 推模型（Push Model）
主题主动将所有数据推送给观察者（上述示例采用推模型）。

```java
// 推模型：主题推送所有数据
void update(float temperature, float humidity, float pressure);
```

**特点**：
- ✅ 简单直接
- ❌ 观察者可能接收到不需要的数据
- ❌ 主题和观察者耦合度较高

#### 拉模型（Pull Model）
主题只通知观察者状态已改变，观察者自己拉取需要的数据。

```java
// 观察者接口
interface Observer {
    void update(Subject subject); // 传递主题引用
}

// 具体观察者
class CurrentConditionsDisplay implements Observer {
    @Override
    public void update(Subject subject) {
        WeatherStation station = (WeatherStation) subject;
        // 按需拉取数据
        float temperature = station.getTemperature();
        float humidity = station.getHumidity();
        display(temperature, humidity);
    }
}
```

**特点**：
- ✅ 观察者按需获取数据，灵活性高
- ✅ 降低耦合度
- ❌ 观察者需要知道主题的具体类型

### 4. JDK 内置的观察者模式

```java
import java.util.Observable;
import java.util.Observer;

// 主题（JDK 自带）
class WeatherData extends Observable {
    private float temperature;
    private float humidity;
    private float pressure;

    public void setMeasurements(float temperature, float humidity, float pressure) {
        this.temperature = temperature;
        this.humidity = humidity;
        this.pressure = pressure;

        setChanged(); // 标记状态已改变
        notifyObservers(); // 通知观察者
    }

    public float getTemperature() {
        return temperature;
    }

    public float getHumidity() {
        return humidity;
    }

    public float getPressure() {
        return pressure;
    }
}

// 观察者（JDK 自带）
class CurrentDisplay implements Observer {
    @Override
    public void update(Observable o, Object arg) {
        if (o instanceof WeatherData) {
            WeatherData data = (WeatherData) o;
            System.out.println("温度：" + data.getTemperature() + "°C");
        }
    }
}

// 使用
WeatherData weatherData = new WeatherData();
CurrentDisplay display = new CurrentDisplay();
weatherData.addObserver(display);
weatherData.setMeasurements(25.0f, 60.0f, 1013.0f);
```

**注意**：JDK 的 Observable 和 Observer 在 Java 9 中被标记为 **@Deprecated**，不推荐使用，原因：
- Observable 是类而非接口，限制了灵活性
- 违反单一职责原则（Observable 既是主题又有状态管理）
- 线程不安全（setChanged 和 notifyObservers 未同步）

### 5. Spring 事件机制（观察者模式的应用）

```java
// 自定义事件
public class OrderCreatedEvent extends ApplicationEvent {
    private String orderId;

    public OrderCreatedEvent(Object source, String orderId) {
        super(source);
        this.orderId = orderId;
    }

    public String getOrderId() {
        return orderId;
    }
}

// 事件监听器（观察者）
@Component
public class EmailNotificationListener {

    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        System.out.println("发送邮件通知：订单 " + event.getOrderId() + " 已创建");
    }
}

@Component
public class InventoryListener {

    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        System.out.println("扣减库存：订单 " + event.getOrderId());
    }
}

// 事件发布者（主题）
@Service
public class OrderService {
    @Autowired
    private ApplicationEventPublisher publisher;

    public void createOrder(String orderId) {
        // 创建订单业务逻辑
        System.out.println("创建订单：" + orderId);

        // 发布事件
        publisher.publishEvent(new OrderCreatedEvent(this, orderId));
    }
}
```

**执行流程**：
```
创建订单：ORDER-001
发送邮件通知：订单 ORDER-001 已创建
扣减库存：订单 ORDER-001
```

**Spring 事件机制的优势**：
- ✅ 解耦业务逻辑（订单创建与邮件、库存解耦）
- ✅ 易于扩展（新增监听器无需修改发布者）
- ✅ 支持异步事件（@Async + @EventListener）
- ✅ 支持事件顺序控制（@Order 注解）

### 6. 异步观察者模式

```java
@Component
public class AsyncEventListener {

    @Async
    @EventListener
    public void handleOrderCreatedAsync(OrderCreatedEvent event) {
        System.out.println("异步处理订单：" + event.getOrderId() +
                           " (线程：" + Thread.currentThread().getName() + ")");
    }
}

// 启用异步支持
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(10);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-event-");
        executor.initialize();
        return executor;
    }
}
```

### 7. 观察者模式 vs 发布订阅模式

| 对比维度 | 观察者模式 | 发布订阅模式 |
|---------|-----------|------------|
| **通信方式** | 观察者和主题直接通信 | 通过消息中间件间接通信 |
| **耦合度** | 观察者知道主题的存在 | 发布者和订阅者互不知晓 |
| **实现复杂度** | 简单（内存中） | 复杂（需要消息中间件） |
| **典型应用** | Spring 事件、GUI 监听 | 消息队列（Kafka、RabbitMQ） |

**发布订阅模式示意**：
```
发布者 → 消息队列（Broker） → 订阅者
```

### 8. 优缺点分析

**优点**：
- ✅ 降低耦合度（主题和观察者松耦合）
- ✅ 支持广播通信（一次通知多个观察者）
- ✅ 符合开闭原则（新增观察者无需修改主题）
- ✅ 动态订阅（运行时添加/移除观察者）

**缺点**：
- ❌ 观察者过多时通知耗时（同步通知阻塞）
- ❌ 循环依赖风险（观察者触发主题状态变化）
- ❌ 内存泄漏风险（忘记移除观察者）
- ❌ 通知顺序不可控（除非特殊处理）

### 9. 实际开发中的注意事项

**防止内存泄漏**：
```java
// 务必在不需要时移除观察者
subject.removeObserver(observer);

// Spring 中使用弱引用监听器（自动回收）
@EventListener
public void handleEvent(MyEvent event) { ... }
```

**线程安全问题**：
```java
// 使用线程安全的集合
private List<Observer> observers = new CopyOnWriteArrayList<>();

// 或者在通知时加锁
public synchronized void notifyObservers() { ... }
```

**避免循环通知**：
```java
// 使用标志位防止循环
private boolean isNotifying = false;

public void notifyObservers() {
    if (isNotifying) return;
    isNotifying = true;
    try {
        // 通知逻辑
    } finally {
        isNotifying = false;
    }
}
```

### 10. 答题总结

**简洁回答模板**：

"观察者模式定义一对多的依赖关系，当主题状态改变时，所有观察者自动收到通知并更新。

**核心结构**：
1. **主题（Subject）**：维护观察者列表，状态变化时通知观察者
2. **观察者（Observer）**：定义更新接口，接收通知并作出响应

**两种模型**：
- **推模型**：主题推送所有数据给观察者（简单但耦合高）
- **拉模型**：观察者主动拉取需要的数据（灵活但需要知道主题类型）

**典型应用**：
- Spring 事件机制（ApplicationEvent + @EventListener）
- GUI 事件监听（按钮点击、数据绑定）
- 消息队列（Kafka、RabbitMQ 的发布订阅模式）

**与发布订阅的区别**：观察者模式是同步直接通信，发布订阅通过消息中间件异步解耦。

适用于对象间存在一对多依赖，状态变化需要通知多个对象的场景，能有效解耦并支持动态订阅。"
