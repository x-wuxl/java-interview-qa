---
layout: default
title: "什么是策略模式？"
parent: 设计模式
nav_order: 488
description: "深入解析策略模式的定义、实现原理、与工厂模式的区别，以及在支付系统、排序算法、Spring框架中的实际应用"
author: "wuxl"
date: 2025-11-02
---
## 问题

什么是策略模式？

## 答案

### 1. 核心概念

**策略模式（Strategy Pattern）** 是一种行为型设计模式，定义一系列算法，将每个算法封装成独立的策略类，使它们可以互相替换。策略模式让算法的变化独立于使用算法的客户端。

**核心思想**：
- 将可变的行为抽象成策略接口
- 不同的策略实现不同的算法
- 运行时动态选择策略

**典型应用场景**：
- 支付方式选择（支付宝、微信、银行卡）
- 物流计费策略（按重量、按距离、包邮）
- 排序算法（冒泡、快排、归并）
- 促销活动规则（满减、折扣、赠品）

### 2. 实现原理与代码示例

#### 基础实现

```java
// 策略接口
interface PaymentStrategy {
    void pay(int amount);
}

// 具体策略：支付宝支付
class AlipayStrategy implements PaymentStrategy {
    private String account;

    public AlipayStrategy(String account) {
        this.account = account;
    }

    @Override
    public void pay(int amount) {
        System.out.println("使用支付宝账号 " + account + " 支付 " + amount + " 元");
    }
}

// 具体策略：微信支付
class WechatPayStrategy implements PaymentStrategy {
    private String openId;

    public WechatPayStrategy(String openId) {
        this.openId = openId;
    }

    @Override
    public void pay(int amount) {
        System.out.println("使用微信 OpenID " + openId + " 支付 " + amount + " 元");
    }
}

// 具体策略：银行卡支付
class BankCardStrategy implements PaymentStrategy {
    private String cardNumber;

    public BankCardStrategy(String cardNumber) {
        this.cardNumber = cardNumber;
    }

    @Override
    public void pay(int amount) {
        System.out.println("使用银行卡 " + cardNumber + " 支付 " + amount + " 元");
    }
}

// 上下文类（持有策略引用）
class PaymentContext {
    private PaymentStrategy strategy;

    public void setStrategy(PaymentStrategy strategy) {
        this.strategy = strategy;
    }

    public void executePayment(int amount) {
        if (strategy == null) {
            throw new IllegalStateException("未设置支付策略");
        }
        strategy.pay(amount);
    }
}

// 使用示例
public class Client {
    public static void main(String[] args) {
        PaymentContext context = new PaymentContext();

        // 使用支付宝支付
        context.setStrategy(new AlipayStrategy("user@alipay.com"));
        context.executePayment(100);

        // 切换到微信支付
        context.setStrategy(new WechatPayStrategy("wx123456"));
        context.executePayment(200);

        // 切换到银行卡支付
        context.setStrategy(new BankCardStrategy("6222 **** **** 1234"));
        context.executePayment(300);
    }
}
```

**输出结果**：
```
使用支付宝账号 user@alipay.com 支付 100 元
使用微信 OpenID wx123456 支付 200 元
使用银行卡 6222 **** **** 1234 支付 300 元
```

### 3. 策略模式 + 工厂模式（企业级实现）

```java
// 策略接口
interface PaymentStrategy {
    void pay(int amount);
    String getType(); // 标识策略类型
}

// 具体策略实现
@Component
class AlipayStrategy implements PaymentStrategy {
    public void pay(int amount) {
        System.out.println("支付宝支付：" + amount);
    }

    public String getType() {
        return "ALIPAY";
    }
}

@Component
class WechatPayStrategy implements PaymentStrategy {
    public void pay(int amount) {
        System.out.println("微信支付：" + amount);
    }

    public String getType() {
        return "WECHAT";
    }
}

// 策略工厂（Spring 管理）
@Component
public class PaymentStrategyFactory {
    private final Map<String, PaymentStrategy> strategyMap = new ConcurrentHashMap<>();

    // 构造注入所有策略实现
    @Autowired
    public PaymentStrategyFactory(List<PaymentStrategy> strategies) {
        strategies.forEach(strategy ->
            strategyMap.put(strategy.getType(), strategy)
        );
    }

    public PaymentStrategy getStrategy(String type) {
        PaymentStrategy strategy = strategyMap.get(type);
        if (strategy == null) {
            throw new IllegalArgumentException("不支持的支付类型：" + type);
        }
        return strategy;
    }
}

// 业务服务
@Service
public class OrderService {
    @Autowired
    private PaymentStrategyFactory strategyFactory;

    public void processOrder(String paymentType, int amount) {
        PaymentStrategy strategy = strategyFactory.getStrategy(paymentType);
        strategy.pay(amount);
    }
}
```

### 4. 策略模式 vs 工厂模式

| 对比维度 | 策略模式 | 工厂模式 |
|---------|---------|---------|
| **模式类型** | 行为型模式 | 创建型模式 |
| **关注点** | 算法的选择与替换 | 对象的创建 |
| **客户端关系** | 客户端知道所有策略并主动选择 | 客户端不关心对象如何创建 |
| **运行时切换** | 支持运行时动态切换策略 | 一般创建后不再更换 |
| **使用场景** | 多种算法可互换 | 封装复杂的对象创建逻辑 |

**组合使用**：
- 工厂模式创建策略对象
- 策略模式管理和使用这些对象

### 5. Spring 中的策略模式应用

#### Resource 资源访问策略

```java
// Resource 接口是策略接口
Resource resource1 = new ClassPathResource("config.xml");
Resource resource2 = new FileSystemResource("/data/config.xml");
Resource resource3 = new UrlResource("http://example.com/config.xml");

// 不同的资源访问策略
InputStream is = resource.getInputStream();
```

#### InstantiationStrategy Bean 创建策略

```java
// Spring 内部使用策略模式决定如何实例化 Bean
public interface InstantiationStrategy {
    Object instantiate(RootBeanDefinition bd, ...);
}

// 简单实例化策略
class SimpleInstantiationStrategy implements InstantiationStrategy { ... }

// CGLIB 实例化策略
class CglibSubclassingInstantiationStrategy implements InstantiationStrategy { ... }
```

### 6. 实际开发中的优化技巧

#### 使用注解标识策略

```java
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
public @interface PaymentType {
    String value();
}

@Component
@PaymentType("ALIPAY")
class AlipayStrategy implements PaymentStrategy { ... }

// 工厂类通过反射扫描注解自动注册
```

#### 策略枚举（简单场景）

```java
public enum DiscountStrategy {
    NONE {
        public double apply(double price) {
            return price;
        }
    },
    PERCENT_10 {
        public double apply(double price) {
            return price * 0.9;
        }
    },
    FIXED_50 {
        public double apply(double price) {
            return price - 50;
        }
    };

    public abstract double apply(double price);
}

// 使用
double finalPrice = DiscountStrategy.PERCENT_10.apply(200);
```

### 7. 答题总结

**简洁回答模板**：

"策略模式是行为型设计模式，将不同的算法封装成独立的策略类，使它们可以相互替换。

**核心结构**：
1. **策略接口**：定义算法规范
2. **具体策略**：实现不同的算法
3. **上下文**：持有策略引用并调用

**典型应用**：支付方式选择、物流计费、促销规则等。

**与工厂模式的区别**：
- 策略模式关注算法的选择和替换（行为型）
- 工厂模式关注对象的创建（创建型）
- 实际开发常组合使用：工厂创建策略，上下文使用策略

**Spring 应用**：Resource 资源访问、Bean 实例化策略、AOP 代理策略等。

使用策略模式可以消除大量 if-else，符合开闭原则，提高代码的可维护性和扩展性。"
