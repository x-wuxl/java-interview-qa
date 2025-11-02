---
layout: post
title: "为什么JDK15要废弃偏向锁？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [JDK15, 偏向锁, 锁优化, JVM]
description: "深入分析JDK 15废弃偏向锁的技术背景、性能考量和现代Java应用的并发特点"
---

# 为什么JDK15要废弃偏向锁？

## 核心结论

JDK 15 默认禁用偏向锁（`-XX:-UseBiasedLocking`），JDK 18 完全移除。主要原因是：**偏向锁的设计已不适应现代 Java 应用的并发模式**，维护成本高，收益有限。

---

## 官方说明

### JEP 374: Deprecate and Disable Biased Locking

> **Summary**: Disable biased locking by default, and deprecate all related command-line options.
>
> **Motivation**: The performance gains of biased locking are no longer as significant as they once were, and the complexity of the code makes it difficult to maintain.

**关键点**：
- 性能收益不再显著
- 代码复杂度高，维护困难
- 现代应用的并发模式已改变

---

## 废弃原因详解

### 1. 现代应用的并发特点变化

#### 偏向锁的设计初衷（2004年 JDK 5）

```java
// 早期 Java 应用的典型场景
public class LegacyApp {
    public synchronized void process() {
        // 单线程反复获取同一把锁
        // 例如：Swing GUI 事件处理
    }
}
```

**设计假设**：
- 大多数锁没有竞争
- 同一线程会反复获取同一把锁
- 单线程应用居多

#### 现代 Java 应用的特点（2020+）

```java
// 现代 Java 应用的典型场景
@RestController
public class UserController {
    @Autowired
    private UserService userService;
    
    @GetMapping("/users/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);  // 每次请求不同线程处理
    }
}
```

**现实情况**：
- **线程池广泛使用**：Tomcat、Netty、Spring WebFlux
- **请求处理模型**：不同线程处理不同请求
- **对象复用**：连接池、对象池中的对象被多个线程访问
- **高并发场景**：微服务、分布式系统

**结果**：偏向锁频繁撤销，反而成为性能瓶颈！

---

### 2. 偏向锁的性能开销

#### 偏向锁撤销的代价

```java
// 典型场景：线程池 + 对象池
ExecutorService executor = Executors.newFixedThreadPool(10);
BlockingQueue<Connection> pool = new LinkedBlockingQueue<>();

// 连接对象内部有 synchronized 方法
Connection conn = pool.take();
executor.submit(() -> {
    synchronized(conn) {  // 偏向撤销！（不同线程访问）
        conn.execute(sql);
    }
});
```

**开销分析**：

| 操作                | 时间开销      |
|---------------------|--------------|
| 偏向锁加锁（重入）   | ~5 ns        |
| 轻量级锁 CAS        | ~20 ns       |
| 偏向锁撤销（STW）    | ~1-10 μs     |
| 批量重偏向          | ~100 μs      |

**问题**：
- 偏向撤销需要 **Stop-The-World**（暂停所有线程）
- 在高并发场景下，频繁 STW 严重影响吞吐量
- 批量重偏向的触发条件难以预测

#### 实际性能测试

```java
// 测试代码
public class BiasedLockBenchmark {
    private final Object lock = new Object();
    
    @Benchmark
    public void singleThread() {
        synchronized(lock) {
            // 偏向锁：5 ns
        }
    }
    
    @Benchmark
    @Threads(10)
    public void multiThread() {
        synchronized(lock) {
            // 偏向撤销 + 轻量级锁：50-100 ns
            // 比直接使用轻量级锁更慢！
        }
    }
}
```

**结论**：在多线程场景下，偏向锁的撤销开销使其性能不如直接使用轻量级锁。

---

### 3. 维护成本高

#### 代码复杂度

偏向锁的实现涉及大量复杂逻辑：

```cpp
// HotSpot 源码中的偏向锁相关代码
biasedLocking.cpp            // 核心逻辑（2000+ 行）
biasedLocking.hpp            // 头文件
synchronizer.cpp             // 锁升级逻辑
markOop.hpp                  // Mark Word 操作

// 关键机制
- Epoch 版本管理
- 批量重偏向
- 批量撤销
- STW 协调
- 多线程同步
```

#### 维护负担

1. **Bug 修复困难**：
   - 偏向锁相关 Bug 难以复现（时序相关）
   - 涉及 GC、JIT 编译器等多个子系统交互

2. **性能回归风险**：
   - 每次修改需要大量测试
   - 不同场景下的行为差异大

3. **架构演进受阻**：
   - ZGC、Shenandoah 等新 GC 需要额外适配偏向锁
   - 限制了 JVM 的优化空间

---

### 4. 轻量级锁的优化已足够

#### 自适应自旋的改进

JDK 6 之后的轻量级锁已经非常高效：

```java
// 轻量级锁的性能表现
synchronized(lock) {
    // CAS 操作：~20 ns（无竞争）
    // 自适应自旋：根据历史数据调整
    // 成功率高的场景：接近偏向锁性能
}
```

#### 性能对比（现代硬件）

| 场景              | 偏向锁    | 轻量级锁  | 优势方 |
|-------------------|----------|----------|--------|
| 单线程反复获取     | 5 ns     | 20 ns    | 偏向锁  |
| 两线程交替访问     | 50 ns    | 30 ns    | 轻量级锁 |
| 多线程低竞争       | 100 ns   | 40 ns    | 轻量级锁 |
| 线程池场景         | 200 ns   | 50 ns    | 轻量级锁 |

**关键点**：
- 现代 CPU 的 CAS 性能提升（缓存一致性协议优化）
- 轻量级锁的自适应自旋更智能
- 避免了 STW 的全局影响

---

### 5. 实际应用场景分析

#### 场景1：Tomcat 请求处理

```java
// Tomcat 线程池处理 HTTP 请求
public class Servlet {
    private final DataSource ds = ...;  // 连接池
    
    protected void doGet(HttpServletRequest req, ...) {
        Connection conn = ds.getConnection();  // 不同线程获取同一连接
        synchronized(conn) {  // ❌ 偏向锁频繁撤销
            // ...
        }
    }
}
```

**问题**：连接池对象被多个线程访问，偏向锁无法生效。

#### 场景2：Spring Bean

```java
@Service
public class UserService {
    @Autowired
    private UserRepository repo;  // 单例 Bean
    
    public synchronized void updateUser(User user) {
        // 多个线程调用同一个 Bean
        // 偏向锁撤销 → 轻量级锁
    }
}
```

**问题**：单例 Bean 被多个请求线程访问，偏向锁退化。

#### 场景3：真正受益的场景（罕见）

```java
// 单线程 GUI 应用（已不常见）
public class SwingApp {
    private final Object lock = new Object();
    
    // EDT 线程反复调用
    public synchronized void paintComponent(Graphics g) {
        // 偏向锁有效 ✓
    }
}
```

**现实**：这类应用在现代 Java 生态中占比极小。

---

## 迁移策略

### 如何应对偏向锁废弃？

#### 1. 大多数应用：无需改动

```java
// 原有代码无需修改
public synchronized void method() {
    // JVM 自动使用轻量级锁
    // 性能可能更好
}
```

#### 2. 性能敏感场景：评估和优化

```bash
# 测试禁用偏向锁的影响
java -XX:-UseBiasedLocking -jar app.jar

# 对比性能
jmh-benchmark.jar
```

#### 3. 如果确实需要偏向锁（JDK 15-17）

```bash
# 手动开启（不推荐）
java -XX:+UseBiasedLocking -jar app.jar

# 监控偏向锁统计
-XX:+PrintBiasedLockingStatistics
```

#### 4. 长期方案：优化锁设计

```java
// ❌ 避免不必要的 synchronized
public synchronized void getAllUsers() {
    return new ArrayList<>(users);  // 防御性拷贝不需要锁
}

// ✅ 使用并发集合
private final ConcurrentHashMap<Long, User> users = ...;

public User getUser(Long id) {
    return users.get(id);  // 无锁读取
}
```

---

## 其他 JVM 的实践

| JVM              | 偏向锁支持        | 说明                     |
|------------------|------------------|--------------------------|
| HotSpot JDK 15+  | 默认禁用          | JEP 374                  |
| OpenJ9           | 从未实现          | 认为收益有限              |
| GraalVM          | 不支持           | 专注于 AOT 编译优化       |
| Azul Zing        | 已废弃           | 使用更高效的锁算法         |

**趋势**：主流 JVM 都在放弃偏向锁。

---

## 总结对比

### 偏向锁的历史使命

```
2004年（JDK 5）：
- 单线程应用为主
- GUI、Applet 流行
- 锁竞争少
→ 偏向锁效果显著

2020年（JDK 15）：
- 微服务、云原生架构
- 线程池、对象池普及
- 高并发成为常态
→ 偏向锁已过时
```

### 废弃原因总结

1. **现代应用的并发模式改变**：线程池 + 对象池 → 偏向锁频繁撤销
2. **性能收益有限**：轻量级锁 + 自适应自旋已足够快
3. **维护成本高**：代码复杂、Bug 多、阻碍 JVM 演进
4. **STW 影响大**：偏向撤销的全局暂停影响吞吐量
5. **硬件进步**：现代 CPU 的 CAS 性能大幅提升

---

## 面试答题模板

**问题**：为什么 JDK 15 要废弃偏向锁？

**回答**：

JDK 15 通过 JEP 374 默认禁用偏向锁，主要有以下几个原因：

1. **现代应用并发模式改变**：
   - 早期偏向锁设计假设单线程反复获取锁（如 Swing 应用）
   - 现代应用大量使用线程池、对象池，导致偏向锁频繁撤销
   - 例如 Tomcat 线程池处理请求，每个连接被不同线程访问

2. **性能收益降低**：
   - 偏向撤销需要 Stop-The-World，开销 1-10 微秒
   - 频繁撤销导致性能不如直接用轻量级锁
   - 现代 CPU 的 CAS 性能大幅提升，轻量级锁已足够快

3. **维护成本高**：
   - 偏向锁代码复杂（Epoch、批量重偏向、STW 协调）
   - 相关 Bug 难以修复，阻碍 JVM 演进
   - 新 GC（ZGC、Shenandoah）需要额外适配

4. **替代方案成熟**：
   - 轻量级锁的自适应自旋已经很高效
   - 并发工具类（ConcurrentHashMap、LockSupport）更适合现代场景

因此，JDK 15 废弃偏向锁，直接从无锁升级到轻量级锁，简化了 JVM 实现，同时在大多数场景下性能反而更好。

