---
title: "聊聊项目中的优秀设计与代码实践。"
date: 2025-11-20 15:56:03 +0800
categories: [项目经验, 代码规范]
tags: [设计模式, 最佳实践, 架构设计, 代码质量]
description: "总结 Java 后端项目中的优秀设计模式、架构实践、代码规范及性能优化经验，帮助候选人在面试中展示高质量的编码能力。"
nav_order: 610
parent: 架构设计与实战
---
## 一、核心概念

这道题考察候选人的**工程化能力**和**代码素养**，面试官希望了解：

1. **设计模式应用**：是否能合理运用设计模式解决实际问题
2. **架构思维**：系统设计是否具有可扩展性、可维护性
3. **代码规范**：是否遵循行业最佳实践（Clean Code、SOLID 原则）
4. **性能优化**：是否关注代码性能和资源利用率
5. **技术深度**：是否理解框架原理，而非仅会调用 API

## 二、回答框架

采用**分层次、举实例**的方式组织答案：

1. **架构设计层面**：整体架构模式、服务拆分、分层设计
2. **设计模式层面**：策略模式、责任链、工厂模式等
3. **代码规范层面**：命名规范、注释、异常处理
4. **性能优化层面**：缓存、异步、批处理
5. **工具与流程**：自动化测试、CI/CD、代码审查

## 三、架构设计层面

### 1. 分层架构（MVC + DDD）

**设计理念**：清晰的职责划分，高内聚低耦合

```
┌──────────────────────────────────────┐
│ Controller (接口层)                  │
│ - 参数校验、返回值封装               │
├──────────────────────────────────────┤
│ Service (业务层)                     │
│ - 业务编排、事务管理                 │
├──────────────────────────────────────┤
│ Domain (领域层)                      │
│ - 领域对象、业务逻辑                 │
├──────────────────────────────────────┤
│ Repository (仓储层)                  │
│ - 数据访问、持久化                   │
├──────────────────────────────────────┤
│ Infrastructure (基础设施层)          │
│ - 缓存、MQ、第三方服务               │
└──────────────────────────────────────┘
```

**优秀实践**：

```java
// ❌ 反例：Controller 直接操作 Mapper
@RestController
public class OrderController {
    @Autowired
    private OrderMapper orderMapper;
    
    @PostMapping("/order")
    public void createOrder(OrderDTO dto) {
        orderMapper.insert(dto);  // 业务逻辑写在 Controller
    }
}

// ✅ 正例：分层清晰
@RestController
public class OrderController {
    @Autowired
    private OrderService orderService;
    
    @PostMapping("/order")
    public Result<Long> createOrder(@Valid @RequestBody OrderDTO dto) {
        Long orderId = orderService.createOrder(dto);
        return Result.success(orderId);
    }
}

@Service
public class OrderService {
    @Autowired
    private OrderRepository orderRepository;
    
    @Transactional(rollbackFor = Exception.class)
    public Long createOrder(OrderDTO dto) {
        // 业务逻辑：校验库存、扣减余额、创建订单
        Order order = buildOrder(dto);
        return orderRepository.save(order);
    }
}
```

### 2. 接口防腐层（Anti-Corruption Layer）

**场景**：调用第三方服务（支付、物流），隔离外部依赖

```java
// 定义统一的支付接口
public interface PaymentGateway {
    PayResult pay(PayRequest request);
}

// 微信支付适配器
@Component
public class WechatPayAdapter implements PaymentGateway {
    @Override
    public PayResult pay(PayRequest request) {
        // 转换为微信支付格式
        WxPayRequest wxRequest = convertToWxRequest(request);
        WxPayResponse wxResponse = wechatPayClient.unifiedOrder(wxRequest);
        return convertToPayResult(wxResponse);
    }
}

// 支付宝适配器
@Component
public class AlipayAdapter implements PaymentGateway {
    @Override
    public PayResult pay(PayRequest request) {
        // 转换为支付宝格式
        AlipayRequest alipayRequest = convertToAlipayRequest(request);
        AlipayResponse alipayResponse = alipayClient.pay(alipayRequest);
        return convertToPayResult(alipayResponse);
    }
}
```

**优势**：
- 切换支付渠道时，业务代码无需改动
- 统一的异常处理和日志记录
- 便于单元测试（可 Mock）

## 四、设计模式层面

### 1. 策略模式（优惠券计算）

**场景**：不同类型优惠券（满减、折扣、立减）有不同计算规则

```java
// 优惠券策略接口
public interface CouponStrategy {
    BigDecimal calculate(BigDecimal originalPrice, Coupon coupon);
}

// 满减策略
@Component
public class FullReductionStrategy implements CouponStrategy {
    @Override
    public BigDecimal calculate(BigDecimal originalPrice, Coupon coupon) {
        if (originalPrice.compareTo(coupon.getThreshold()) >= 0) {
            return originalPrice.subtract(coupon.getAmount());
        }
        return originalPrice;
    }
}

// 折扣策略
@Component
public class DiscountStrategy implements CouponStrategy {
    @Override
    public BigDecimal calculate(BigDecimal originalPrice, Coupon coupon) {
        return originalPrice.multiply(coupon.getDiscount()).setScale(2, RoundingMode.HALF_UP);
    }
}

// 策略工厂
@Component
public class CouponStrategyFactory {
    @Autowired
    private Map<String, CouponStrategy> strategyMap;
    
    public CouponStrategy getStrategy(String couponType) {
        return strategyMap.get(couponType + "Strategy");
    }
}

// 使用
BigDecimal finalPrice = couponStrategyFactory
    .getStrategy(coupon.getType())
    .calculate(originalPrice, coupon);
```

**优势**：
- 避免大量 `if-else`
- 新增优惠类型只需新增策略类，符合开闭原则
- 易于单元测试

### 2. 责任链模式（订单校验）

**场景**：订单提交前需要多重校验（库存、价格、用户资格等）

```java
// 校验处理器抽象类
public abstract class OrderCheckHandler {
    protected OrderCheckHandler next;
    
    public void setNext(OrderCheckHandler next) {
        this.next = next;
    }
    
    public abstract void check(OrderContext context);
    
    protected void checkNext(OrderContext context) {
        if (next != null) {
            next.check(context);
        }
    }
}

// 库存校验
@Component
public class StockCheckHandler extends OrderCheckHandler {
    @Override
    public void check(OrderContext context) {
        if (stockService.getStock(context.getProductId()) < context.getQuantity()) {
            throw new BizException("库存不足");
        }
        checkNext(context);
    }
}

// 价格校验
@Component
public class PriceCheckHandler extends OrderCheckHandler {
    @Override
    public void check(OrderContext context) {
        BigDecimal actualPrice = priceService.getPrice(context.getProductId());
        if (!actualPrice.equals(context.getSubmittedPrice())) {
            throw new BizException("价格已变动");
        }
        checkNext(context);
    }
}

// 组装责任链
@Configuration
public class OrderCheckChainConfig {
    @Bean
    public OrderCheckHandler checkChain(StockCheckHandler stockCheck,
                                         PriceCheckHandler priceCheck,
                                         UserCheckHandler userCheck) {
        stockCheck.setNext(priceCheck);
        priceCheck.setNext(userCheck);
        return stockCheck;
    }
}
```

### 3. 模板方法模式（导出通用逻辑）

**场景**：Excel 导出（订单、用户、商品），流程一致，数据来源不同

```java
public abstract class AbstractExportService<T> {
    
    public void export(ExportRequest request, HttpServletResponse response) {
        // 1. 查询数据
        List<T> dataList = queryData(request);
        
        // 2. 数据转换
        List<List<String>> rows = convertToRows(dataList);
        
        // 3. 写入 Excel
        writeExcel(rows, response);
        
        // 4. 记录日志
        logExport(request);
    }
    
    // 子类实现具体查询逻辑
    protected abstract List<T> queryData(ExportRequest request);
    
    // 子类实现数据转换
    protected abstract List<List<String>> convertToRows(List<T> dataList);
    
    // 通用逻辑
    private void writeExcel(List<List<String>> rows, HttpServletResponse response) {
        // EasyExcel 写入...
    }
    
    private void logExport(ExportRequest request) {
        log.info("Export completed: {}", request);
    }
}

// 订单导出服务
@Service
public class OrderExportService extends AbstractExportService<Order> {
    @Override
    protected List<Order> queryData(ExportRequest request) {
        return orderMapper.selectByCondition(request.getCondition());
    }
    
    @Override
    protected List<List<String>> convertToRows(List<Order> orders) {
        return orders.stream()
            .map(order -> Arrays.asList(
                order.getId().toString(),
                order.getUserName(),
                order.getAmount().toString()
            ))
            .collect(Collectors.toList());
    }
}
```

## 五、代码规范层面

### 1. 统一返回结果封装

```java
@Data
@AllArgsConstructor
public class Result<T> {
    private Integer code;
    private String message;
    private T data;
    
    public static <T> Result<T> success(T data) {
        return new Result<>(200, "success", data);
    }
    
    public static <T> Result<T> fail(String message) {
        return new Result<>(500, message, null);
    }
}

// 全局异常处理
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(BizException.class)
    public Result<?> handleBizException(BizException e) {
        log.error("Business exception: {}", e.getMessage());
        return Result.fail(e.getMessage());
    }
    
    @ExceptionHandler(Exception.class)
    public Result<?> handleException(Exception e) {
        log.error("System error", e);
        return Result.fail("系统异常，请稍后重试");
    }
}
```

### 2. 参数校验（JSR-303）

```java
@Data
public class CreateOrderDTO {
    @NotNull(message = "用户 ID 不能为空")
    private Long userId;
    
    @NotNull(message = "商品 ID 不能为空")
    private Long productId;
    
    @Min(value = 1, message = "购买数量至少为 1")
    @Max(value = 100, message = "购买数量最多为 100")
    private Integer quantity;
    
    @DecimalMin(value = "0.01", message = "金额必须大于 0")
    private BigDecimal amount;
}

// Controller 使用 @Valid 自动校验
@PostMapping("/order")
public Result<Long> createOrder(@Valid @RequestBody CreateOrderDTO dto) {
    return Result.success(orderService.createOrder(dto));
}
```

### 3. 日志规范

```java
@Slf4j
@Service
public class OrderService {
    
    public Long createOrder(OrderDTO dto) {
        // ✅ 关键操作记录日志（带业务标识）
        log.info("Creating order, userId={}, productId={}, amount={}", 
                 dto.getUserId(), dto.getProductId(), dto.getAmount());
        
        try {
            // 业务逻辑...
            Long orderId = saveOrder(order);
            
            log.info("Order created successfully, orderId={}", orderId);
            return orderId;
        } catch (Exception e) {
            // ✅ 异常日志记录详细信息
            log.error("Failed to create order, dto={}", dto, e);
            throw new BizException("创建订单失败");
        }
    }
}
```

## 六、性能优化层面

### 1. 批量操作替代循环查询

```java
// ❌ 反例：N+1 查询
List<Order> orders = orderMapper.selectAll();
for (Order order : orders) {
    User user = userMapper.selectById(order.getUserId());  // N 次查询
    order.setUserName(user.getName());
}

// ✅ 正例：批量查询
List<Order> orders = orderMapper.selectAll();
List<Long> userIds = orders.stream()
    .map(Order::getUserId)
    .distinct()
    .collect(Collectors.toList());

Map<Long, User> userMap = userMapper.selectByIds(userIds).stream()
    .collect(Collectors.toMap(User::getId, Function.identity()));

orders.forEach(order -> {
    User user = userMap.get(order.getUserId());
    order.setUserName(user.getName());
});
```

### 2. 缓存优化（多级缓存）

```java
@Service
public class ProductService {
    
    @Autowired
    private LoadingCache<Long, Product> localCache;  // Caffeine
    
    @Autowired
    private StringRedisTemplate redisTemplate;
    
    public Product getProduct(Long productId) {
        // 1. 查询本地缓存
        Product product = localCache.getIfPresent(productId);
        if (product != null) {
            return product;
        }
        
        // 2. 查询 Redis
        String key = "product:" + productId;
        String json = redisTemplate.opsForValue().get(key);
        if (json != null) {
            product = JSON.parseObject(json, Product.class);
            localCache.put(productId, product);
            return product;
        }
        
        // 3. 查询数据库
        product = productMapper.selectById(productId);
        if (product != null) {
            redisTemplate.opsForValue().set(key, JSON.toJSONString(product), 1, TimeUnit.HOURS);
            localCache.put(productId, product);
        }
        
        return product;
    }
}
```

### 3. 异步化处理

```java
@Service
public class OrderService {
    
    @Autowired
    private ThreadPoolExecutor asyncExecutor;
    
    @Transactional(rollbackFor = Exception.class)
    public Long createOrder(OrderDTO dto) {
        // 1. 创建订单（同步）
        Order order = buildOrder(dto);
        Long orderId = orderMapper.insert(order);
        
        // 2. 发送通知（异步）
        asyncExecutor.execute(() -> {
            sendOrderNotification(orderId);
        });
        
        // 3. 记录日志（异步）
        asyncExecutor.execute(() -> {
            logOrderEvent(orderId);
        });
        
        return orderId;
    }
}

// 线程池配置
@Configuration
public class ThreadPoolConfig {
    @Bean
    public ThreadPoolExecutor asyncExecutor() {
        return new ThreadPoolExecutor(
            10, 50, 60, TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(1000),
            new ThreadFactoryBuilder().setNameFormat("async-pool-%d").build(),
            new ThreadPoolExecutor.CallerRunsPolicy()
        );
    }
}
```

## 七、工具与流程

### 1. 单元测试（JUnit + Mockito）

```java
@SpringBootTest
class OrderServiceTest {
    
    @InjectMocks
    private OrderService orderService;
    
    @Mock
    private OrderMapper orderMapper;
    
    @Test
    void testCreateOrder_success() {
        OrderDTO dto = new OrderDTO();
        dto.setUserId(1L);
        dto.setProductId(100L);
        
        when(orderMapper.insert(any())).thenReturn(1L);
        
        Long orderId = orderService.createOrder(dto);
        
        assertNotNull(orderId);
        verify(orderMapper, times(1)).insert(any());
    }
}
```

### 2. 代码审查清单

- [ ] 是否有硬编码（魔法值）？
- [ ] 异常是否正确处理？
- [ ] 是否有内存泄漏风险（Stream 未关闭、连接未释放）？
- [ ] 是否有 SQL 注入风险？
- [ ] 日志级别是否合理？
- [ ] 是否通过单元测试？

## 八、总结

**优秀设计与代码实践的核心**：

1. **架构层面**：分层清晰、接口防腐、依赖倒置
2. **设计模式**：策略模式、责任链、模板方法（避免大量 if-else）
3. **代码规范**：统一返回值、参数校验、异常处理、日志规范
4. **性能优化**：批量查询、多级缓存、异步化
5. **工程化**：单元测试、代码审查、CI/CD

**面试回答要点**：
- 每个点举一个真实案例
- 说明为什么这样设计（解决了什么问题）
- 量化效果（性能提升、代码减少行数等）
