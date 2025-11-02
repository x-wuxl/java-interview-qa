---
layout: post
title: "什么是责任链模式？"
date: 2025-11-02
description: "详解责任链模式的定义、实现原理、纯责任链与不纯责任链的区别，以及在Servlet Filter、Spring拦截器、Netty Pipeline中的实际应用"
author: "wuxl"
categories: [设计模式]
tags: [责任链模式, 设计模式, Filter, 拦截器, Netty, Servlet]
---

## 问题

什么是责任链模式？

## 答案

### 1. 核心概念

**责任链模式（Chain of Responsibility Pattern）** 是一种行为型设计模式，将请求的发送者和接收者解耦，让多个对象都有机会处理请求。这些对象组成一条链，请求沿着链传递，直到有对象处理它为止。

**核心思想**：
- 多个处理器按顺序组成链条
- 请求沿着链传递
- 每个处理器决定是否处理请求，以及是否继续传递

**典型应用场景**：
- Servlet Filter 过滤器链
- Spring 拦截器（Interceptor）
- Netty 的 ChannelPipeline
- 审批流程（员工请假审批）
- 异常处理链

### 2. 实现原理与代码示例

#### 基础实现：请假审批流程

```java
// 请假申请
class LeaveRequest {
    private String name;
    private int days;

    public LeaveRequest(String name, int days) {
        this.name = name;
        this.days = days;
    }

    public String getName() {
        return name;
    }

    public int getDays() {
        return days;
    }
}

// 抽象处理器
abstract class Approver {
    protected Approver nextApprover; // 下一个处理器

    public void setNextApprover(Approver nextApprover) {
        this.nextApprover = nextApprover;
    }

    // 抽象处理方法
    public abstract void processRequest(LeaveRequest request);
}

// 具体处理器1：组长（处理 ≤ 1 天）
class TeamLeader extends Approver {
    @Override
    public void processRequest(LeaveRequest request) {
        if (request.getDays() <= 1) {
            System.out.println("组长批准了 " + request.getName() + " 的 " + request.getDays() + " 天请假");
        } else if (nextApprover != null) {
            System.out.println("组长无权批准，转交上级");
            nextApprover.processRequest(request);
        }
    }
}

// 具体处理器2：经理（处理 ≤ 3 天）
class Manager extends Approver {
    @Override
    public void processRequest(LeaveRequest request) {
        if (request.getDays() <= 3) {
            System.out.println("经理批准了 " + request.getName() + " 的 " + request.getDays() + " 天请假");
        } else if (nextApprover != null) {
            System.out.println("经理无权批准,转交上级");
            nextApprover.processRequest(request);
        }
    }
}

// 具体处理器3：总监（处理 ≤ 7 天）
class Director extends Approver {
    @Override
    public void processRequest(LeaveRequest request) {
        if (request.getDays() <= 7) {
            System.out.println("总监批准了 " + request.getName() + " 的 " + request.getDays() + " 天请假");
        } else {
            System.out.println("请假天数过长，总监拒绝了请求");
        }
    }
}

// 使用示例
public class Client {
    public static void main(String[] args) {
        // 创建责任链
        Approver teamLeader = new TeamLeader();
        Approver manager = new Manager();
        Approver director = new Director();

        // 链接责任链
        teamLeader.setNextApprover(manager);
        manager.setNextApprover(director);

        // 发送请求
        LeaveRequest request1 = new LeaveRequest("张三", 1);
        teamLeader.processRequest(request1);

        System.out.println("---");

        LeaveRequest request2 = new LeaveRequest("李四", 5);
        teamLeader.processRequest(request2);

        System.out.println("---");

        LeaveRequest request3 = new LeaveRequest("王五", 10);
        teamLeader.processRequest(request3);
    }
}
```

**输出结果**：
```
组长批准了 张三 的 1 天请假
---
组长无权批准，转交上级
经理无权批准,转交上级
总监批准了 李四 的 5 天请假
---
组长无权批准，转交上级
经理无权批准,转交上级
请假天数过长，总监拒绝了请求
```

### 3. 纯责任链 vs 不纯责任链

#### 纯责任链（Pure Chain）
- 请求只能被一个处理器处理
- 处理后不再传递

```java
// 处理后直接返回，不再传递
if (canHandle(request)) {
    handle(request);
    return; // 终止链
}
nextHandler.handleRequest(request);
```

#### 不纯责任链（Impure Chain）
- 请求可以被多个处理器处理
- 每个处理器处理后继续传递

```java
// 处理后继续传递
if (canHandle(request)) {
    handle(request);
}
if (nextHandler != null) {
    nextHandler.handleRequest(request); // 继续传递
}
```

### 4. Servlet Filter 过滤器链（不纯责任链）

```java
// Filter 接口
public interface Filter {
    void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException;
}

// 具体过滤器1：编码过滤器
public class EncodingFilter implements Filter {
    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        System.out.println("设置请求编码为 UTF-8");
        request.setCharacterEncoding("UTF-8");
        response.setCharacterEncoding("UTF-8");

        // 继续传递给下一个过滤器
        chain.doFilter(request, response);

        System.out.println("编码过滤器处理响应");
    }
}

// 具体过滤器2：登录验证过滤器
public class AuthFilter implements Filter {
    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest req = (HttpServletRequest) request;

        System.out.println("验证用户登录状态");
        if (req.getSession().getAttribute("user") == null) {
            System.out.println("用户未登录，拒绝访问");
            return; // 终止链
        }

        // 继续传递
        chain.doFilter(request, response);

        System.out.println("登录过滤器处理响应");
    }
}

// FilterChain 简化实现
public class ApplicationFilterChain implements FilterChain {
    private List<Filter> filters = new ArrayList<>();
    private int pos = 0; // 当前处理位置

    public void addFilter(Filter filter) {
        filters.add(filter);
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response)
            throws IOException, ServletException {
        if (pos < filters.size()) {
            Filter filter = filters.get(pos++);
            filter.doFilter(request, response, this);
        } else {
            // 所有过滤器执行完毕，调用 Servlet
            System.out.println("执行目标 Servlet");
        }
    }
}
```

**执行流程**：
```
设置请求编码为 UTF-8
验证用户登录状态
执行目标 Servlet
登录过滤器处理响应
编码过滤器处理响应
```

### 5. Spring 拦截器（HandlerInterceptor）

```java
public interface HandlerInterceptor {
    // 前置处理
    boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler);

    // 后置处理
    void postHandle(HttpServletRequest request, HttpServletResponse response,
                    Object handler, ModelAndView modelAndView);

    // 完成后处理
    void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                         Object handler, Exception ex);
}

// 自定义拦截器
@Component
public class LogInterceptor implements HandlerInterceptor {
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        System.out.println("请求路径：" + request.getRequestURI());
        return true; // 返回 true 继续执行，false 中断
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        System.out.println("请求完成");
    }
}

// 注册拦截器
@Configuration
public class WebConfig implements WebMvcConfigurer {
    @Autowired
    private LogInterceptor logInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(logInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns("/login", "/static/**");
    }
}
```

### 6. Netty 的 ChannelPipeline

```java
// Netty 的责任链实现
ChannelPipeline pipeline = channel.pipeline();

// 添加处理器到责任链
pipeline.addLast("decoder", new HttpRequestDecoder());
pipeline.addLast("encoder", new HttpResponseEncoder());
pipeline.addLast("aggregator", new HttpObjectAggregator(512 * 1024));
pipeline.addLast("handler", new HttpServerHandler());

// 每个 Handler 处理完后调用 ctx.fireChannelRead(msg) 传递给下一个
public class MyHandler extends ChannelInboundHandlerAdapter {
    @Override
    public void channelRead(ChannelHandlerContext ctx, Object msg) {
        // 处理消息
        System.out.println("处理消息：" + msg);

        // 传递给下一个处理器
        ctx.fireChannelRead(msg);
    }
}
```

### 7. 责任链模式的优化实现

#### 使用建造者模式构建责任链

```java
// 责任链构建器
public class HandlerChainBuilder {
    private List<Handler> handlers = new ArrayList<>();

    public HandlerChainBuilder addHandler(Handler handler) {
        handlers.add(handler);
        return this;
    }

    public HandlerChain build() {
        // 链接所有处理器
        for (int i = 0; i < handlers.size() - 1; i++) {
            handlers.get(i).setNextHandler(handlers.get(i + 1));
        }
        return new HandlerChain(handlers.get(0));
    }
}

// 使用
HandlerChain chain = new HandlerChainBuilder()
    .addHandler(new ValidationHandler())
    .addHandler(new AuthHandler())
    .addHandler(new LogHandler())
    .build();

chain.execute(request);
```

### 8. 优缺点分析

**优点**：
- ✅ 降低耦合度（发送者和接收者解耦）
- ✅ 动态组合处理器（灵活配置责任链）
- ✅ 符合单一职责原则（每个处理器专注一个功能）
- ✅ 符合开闭原则（新增处理器无需修改现有代码）

**缺点**：
- ❌ 性能问题（请求需要遍历整条链）
- ❌ 调试困难（请求的处理路径不明确）
- ❌ 可能请求无法被处理（链末端未处理）

### 9. 答题总结

**简洁回答模板**：

"责任链模式将请求发送者和接收者解耦，让多个处理器对象按顺序组成链条，请求沿链传递直到被处理。

**核心结构**：
1. **抽象处理器**：定义处理接口，持有下一个处理器的引用
2. **具体处理器**：实现具体的处理逻辑，决定是否继续传递
3. **客户端**：构建责任链并发起请求

**两种形式**：
- **纯责任链**：请求只被一个处理器处理后终止
- **不纯责任链**：请求可被多个处理器处理（如 Filter）

**典型应用**：
- Servlet Filter 过滤器链（编码、鉴权、日志）
- Spring 拦截器（preHandle → Controller → postHandle → afterCompletion）
- Netty 的 ChannelPipeline（编解码、业务处理）

**优势**：降低耦合、动态组合、易于扩展。适用于多个对象都可能处理请求，且处理顺序需要灵活配置的场景。"
