---
layout: post
title: "如何使用职责链模式进行代码重构？"
date: 2025-12-28
categories: [大厂项目场景实战, 代码重构实战]
tags: [设计模式, 职责链, 代码重构, 研发提效]
description: "通过订单校验场景讲解如何使用职责链模式重构代码，实现流程解耦和灵活扩展。"
---

# 如何使用职责链模式进行代码重构？

## 业务场景

电商下单前需要进行一系列校验：用户状态、商品库存、优惠券、限购规则、风控等。

---

## 原代码问题

```java
public class OrderValidator {
    
    public void validate(OrderRequest request) {
        // 1. 用户校验
        User user = userService.getUser(request.getUserId());
        if (user == null || user.getStatus() != 1) {
            throw new ValidationException("用户状态异常");
        }
        
        // 2. 库存校验
        Stock stock = stockService.getStock(request.getProductId());
        if (stock.getCount() < request.getQuantity()) {
            throw new ValidationException("库存不足");
        }
        
        // 3. 优惠券校验
        if (request.getCouponId() != null) {
            Coupon coupon = couponService.getCoupon(request.getCouponId());
            if (coupon.isExpired() || coupon.isUsed()) {
                throw new ValidationException("优惠券不可用");
            }
        }
        
        // 4. 限购校验
        int purchased = orderService.countUserOrders(request);
        if (purchased >= 5) {
            throw new ValidationException("超出限购数量");
        }
        
        // 5. 风控校验
        RiskResult risk = riskService.check(request);
        if (risk.isBlocked()) {
            throw new ValidationException("风控拦截");
        }
        
        // 还有更多...
    }
}
```

**问题**：
- 校验逻辑全部堆在一起，违反**单一职责**
- 新增/修改校验需要修改核心类
- 无法灵活调整校验顺序
- 难以复用单个校验逻辑

---

## 职责链模式解决方案

### 模式定义

将请求沿着处理者链传递，每个处理者决定是否处理请求以及是否传递给下一个处理者。

### 设计结构

```
请求 → Handler1 → Handler2 → Handler3 → ... → 完成
           │           │           │
        处理/拒绝    处理/拒绝    处理/拒绝
```

---

## 重构后代码

### 抽象处理器

```java
public abstract class OrderValidationHandler {
    
    protected OrderValidationHandler next;
    
    public void setNext(OrderValidationHandler next) {
        this.next = next;
    }
    
    public void validate(OrderRequest request) {
        doValidate(request);
        if (next != null) {
            next.validate(request);
        }
    }
    
    protected abstract void doValidate(OrderRequest request);
}
```

### 具体处理器

```java
// 用户校验
@Component
@Order(1)
public class UserValidationHandler extends OrderValidationHandler {
    
    @Autowired
    private UserService userService;
    
    @Override
    protected void doValidate(OrderRequest request) {
        User user = userService.getUser(request.getUserId());
        if (user == null || user.getStatus() != 1) {
            throw new ValidationException("用户状态异常");
        }
    }
}

// 库存校验
@Component
@Order(2)
public class StockValidationHandler extends OrderValidationHandler {
    
    @Autowired
    private StockService stockService;
    
    @Override
    protected void doValidate(OrderRequest request) {
        Stock stock = stockService.getStock(request.getProductId());
        if (stock.getCount() < request.getQuantity()) {
            throw new ValidationException("库存不足");
        }
    }
}

// 优惠券校验
@Component
@Order(3)
public class CouponValidationHandler extends OrderValidationHandler {
    
    @Autowired
    private CouponService couponService;
    
    @Override
    protected void doValidate(OrderRequest request) {
        if (request.getCouponId() == null) {
            return;  // 无优惠券直接跳过
        }
        Coupon coupon = couponService.getCoupon(request.getCouponId());
        if (coupon.isExpired() || coupon.isUsed()) {
            throw new ValidationException("优惠券不可用");
        }
    }
}

// 限购校验
@Component
@Order(4)
public class LimitValidationHandler extends OrderValidationHandler {
    
    @Override
    protected void doValidate(OrderRequest request) {
        int purchased = orderService.countUserOrders(request);
        if (purchased >= 5) {
            throw new ValidationException("超出限购数量");
        }
    }
}

// 风控校验
@Component
@Order(5)
public class RiskValidationHandler extends OrderValidationHandler {
    
    @Autowired
    private RiskService riskService;
    
    @Override
    protected void doValidate(OrderRequest request) {
        RiskResult risk = riskService.check(request);
        if (risk.isBlocked()) {
            throw new ValidationException("风控拦截: " + risk.getReason());
        }
    }
}
```

### 链构建与使用

```java
@Configuration
public class ValidationChainConfig {
    
    @Autowired
    private List<OrderValidationHandler> handlers;
    
    @Bean
    public OrderValidationHandler validationChain() {
        // 按@Order排序
        handlers.sort(Comparator.comparingInt(
            h -> h.getClass().getAnnotation(Order.class).value()));
        
        // 构建链
        for (int i = 0; i < handlers.size() - 1; i++) {
            handlers.get(i).setNext(handlers.get(i + 1));
        }
        
        return handlers.get(0);
    }
}

@Service
public class OrderService {
    
    @Autowired
    private OrderValidationHandler validationChain;
    
    public Order createOrder(OrderRequest request) {
        // 执行校验链
        validationChain.validate(request);
        
        // 校验通过，创建订单
        return doCreateOrder(request);
    }
}
```

---

## 进阶：动态配置校验规则

### 通过配置控制校验开关

```yaml
order:
  validation:
    user: true
    stock: true
    coupon: true
    limit: false  # 大促期间关闭限购
    risk: true
```

```java
@Component
@Order(4)
@ConditionalOnProperty(name = "order.validation.limit", havingValue = "true")
public class LimitValidationHandler extends OrderValidationHandler {
    // ...
}
```

### 通过数据库配置规则

```java
@Component
public class DynamicValidationChain {
    
    @Autowired
    private Map<String, OrderValidationHandler> handlerMap;
    
    public void validate(OrderRequest request) {
        // 从数据库读取启用的规则
        List<String> enabledRules = configService.getEnabledRules();
        
        for (String rule : enabledRules) {
            OrderValidationHandler handler = handlerMap.get(rule);
            if (handler != null) {
                handler.doValidate(request);
            }
        }
    }
}
```

---

## 优化效果

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 核心类代码行 | 150行 | 10行 |
| 新增校验改动点 | 1处核心类 | 新增1个类 |
| 校验逻辑复用 | 不可复用 | 可独立复用 |
| 顺序调整 | 需改代码 | 改@Order注解 |
| 动态开关 | 不支持 | 支持 |

---

## 面试答题框架

```
业务场景：下单前多步骤校验

原代码问题：
- 违反单一职责
- 扩展需改核心类
- 无法灵活调整顺序

重构方案：职责链模式
- 抽象Handler定义校验接口
- 具体Handler实现各校验逻辑
- 链式调用，逐个校验

扩展能力：
- @Order控制顺序
- 配置中心动态开关
- 新增校验只需增加类
```

---

## 总结

| 要点 | 说明 |
|------|------|
| 适用场景 | 多步骤处理，顺序可变 |
| 核心思想 | 请求沿链传递 |
| 优点 | 解耦、可扩展、可配置 |
| 变体 | 拦截器链、过滤器链 |
