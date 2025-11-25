---
layout: default
title: "当 CPU 突然飙高、系统反应变慢时如何排查？"
parent: 架构设计与实战
nav_order: 613
description: 系统化讲解CPU飙高问题的排查思路与实战方法，涵盖Linux命令、JVM工具、代码定位、常见原因分析及预防措施。
date: 2025-11-20 16:00:00 +0800
---
## 一、核心概念

CPU 飙高是生产环境常见的性能问题，主要表现为：
- **系统 CPU 使用率** 持续超过 80%
- **应用响应变慢**，接口超时增多
- **服务器负载** 异常升高

**核心排查思路**：
1. **定位进程** → 2. **定位线程** → 3. **定位代码** → 4. **分析根因** → 5. **修复验证**

## 二、排查步骤与关键命令

### 2.1 快速定位问题进程

#### Step 1: 查看系统整体 CPU 使用情况

```bash
# 实时监控CPU使用率
top
```

**关键指标解读**：
```
%Cpu(s): 85.3 us,  2.1 sy,  0.0 ni, 12.1 id,  0.3 wa,  0.0 hi,  0.2 si
```
- **us (user)**：用户态 CPU 占用（业务代码消耗）
- **sy (system)**：内核态 CPU 占用（频繁系统调用）
- **wa (wait)**：IO 等待（磁盘/网络慢）
- **id (idle)**：空闲 CPU

**判断方向**：
- **us 高**：业务代码问题（死循环、计算密集）
- **sy 高**：系统调用频繁（线程创建/销毁、网络连接）
- **wa 高**：IO 瓶颈（磁盘慢、网络超时）

#### Step 2: 找出占用 CPU 最高的进程

```bash
# 按CPU使用率排序，找到PID
top -c

# 或者直接查看Java进程
ps aux | grep java | grep -v grep
```

**示例输出**：
```
PID   USER  %CPU %MEM  COMMAND
12345 root  152.3 30.2 java -jar app.jar
```

**记录进程 PID**，例如 `12345`

### 2.2 定位到具体线程

#### Step 3: 查看该进程内哪些线程占用 CPU 高

```bash
# 查看进程12345的所有线程CPU占用
top -Hp 12345
```

**示例输出**：
```
PID   %CPU  COMMAND
12367 98.5  java
12368 45.2  java
12369 8.3   java
```

**记录占用高的线程 PID**，例如 `12367`

#### Step 4: 将线程 PID 转为十六进制

```bash
# Java线程栈中的nid是十六进制格式
printf "%x\n" 12367
# 输出: 304f
```

### 2.3 定位到问题代码

#### Step 5: 导出 Java 线程栈

```bash
# 使用jstack导出线程栈快照
jstack 12345 > thread_dump.txt

# 或者使用Arthas在线分析
java -jar arthas-boot.jar
thread -n 5  # 查看CPU占用最高的5个线程
```

#### Step 6: 在线程栈中搜索十六进制线程 ID

```bash
# 搜索nid=0x304f的线程
grep -A 30 "0x304f" thread_dump.txt
```

**示例线程栈**：
```java
"http-nio-8080-exec-23" #45 daemon prio=5 os_prio=0 tid=0x00007f8a3c123000 nid=0x304f runnable [0x00007f8a28c5e000]
   java.lang.Thread.State: RUNNABLE
        at com.example.service.OrderService.calculatePrice(OrderService.java:127)
        at com.example.service.OrderService.processOrder(OrderService.java:89)
        at com.example.controller.OrderController.createOrder(OrderController.java:45)
        ...
```

**关键信息**：
- **线程名称**：`http-nio-8080-exec-23`（业务线程）
- **线程状态**：`RUNNABLE`（正在运行）
- **代码位置**：`OrderService.java:127`

### 2.4 常见 CPU 飙高场景分析

#### 场景 1：死循环或无限递归

**线程栈特征**：
```java
"business-thread-1" #12 prio=5 os_prio=0 tid=0x... nid=0x1a2b runnable
   java.lang.Thread.State: RUNNABLE
        at com.example.BuggyService.loopMethod(BuggyService.java:50)
        at com.example.BuggyService.loopMethod(BuggyService.java:50)  // 重复调用
        at com.example.BuggyService.loopMethod(BuggyService.java:50)
```

**定位代码示例**：
```java
// BuggyService.java:50
public void loopMethod() {
    while (true) {  // 死循环！
        // 业务逻辑
    }
}
```

**修复**：
```java
public void loopMethod() {
    while (!stopFlag && retryCount < MAX_RETRY) {  // 增加退出条件
        // ...
        retryCount++;
    }
}
```

#### 场景 2：正则表达式回溯

**线程栈特征**：
```java
at java.util.regex.Pattern$Loop.match(Pattern.java:...)
at java.util.regex.Pattern$GroupTail.match(Pattern.java:...)
at com.example.ValidateUtil.checkEmail(ValidateUtil.java:32)
```

**问题代码**：
```java
// 复杂正则 + 长字符串 = 灾难
String regex = "(a+)+b";
boolean matched = longString.matches(regex);  // 回溯爆炸！
```

**修复**：
- 简化正则表达式
- 限制输入长度
- 使用非回溯引擎（RE2J）

#### 场景 3：频繁 GC（Full GC）

**判断方法**：
```bash
# 查看GC情况
jstat -gcutil 12345 1000 10
# 每1秒输出一次，共10次

# 输出示例
S0     S1     E      O      M     CCS    YGC     YGCT    FGC    FGCT     GCT
0.00  95.32  78.23  99.87  96.45  92.11   1523   12.345  158   89.234  101.579
```

**关键指标**：
- **O (老年代)**：接近 100% → 内存不足
- **FGC (Full GC次数)**：频繁增长 → Full GC 风暴
- **FGCT (Full GC耗时)**：占比过高 → GC 占用 CPU

**查看堆内存**：
```bash
# 导出堆快照
jmap -dump:live,format=b,file=heap.hprof 12345

# 使用MAT/JProfiler分析大对象
```

**常见原因**：
- 内存泄漏（缓存未清理、ThreadLocal 未 remove）
- 堆内存配置过小
- 大对象频繁创建

#### 场景 4：线程竞争（锁等待）

**查看线程状态**：
```bash
jstack 12345 | grep -A 5 BLOCKED
```

**线程栈示例**：
```java
"thread-pool-1" #23 prio=5 os_prio=0 tid=0x... nid=0x1f2e waiting for monitor entry
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.example.SyncService.process(SyncService.java:45)
        - waiting to lock <0x00000000e1234567> (a java.lang.Object)
```

**定位到**：
```java
public synchronized void process() {  // 粗粒度锁
    // 耗时操作
    longRunningTask();
}
```

**优化**：
```java
// 细化锁粒度
public void process() {
    // 非同步操作
    prepareData();
    
    synchronized(lockObject) {  // 只锁关键代码
        criticalSection();
    }
}
```

### 2.5 使用 Arthas 在线诊断

**Arthas 是阿里开源的 Java 诊断工具**，无需重启应用：

```bash
# 启动Arthas
java -jar arthas-boot.jar

# 1. 查看CPU最高的线程
thread -n 3

# 2. 反编译运行时代码
jad com.example.service.OrderService

# 3. 监控方法调用耗时
monitor -c 5 com.example.service.OrderService processOrder

# 4. 查看方法调用栈
trace com.example.service.OrderService processOrder

# 5. 热更新代码（紧急修复）
redefine /tmp/OrderService.class
```

**Arthas 输出示例**：
```
ID    NAME                   CPU%   DELTA_TIME  TIME     STATE
12367 http-nio-8080-exec-23  98.5%  0.985       10:32:15 RUNNABLE
  at com.example.service.OrderService.calculatePrice(OrderService.java:127)
```

## 三、性能优化与预防措施

### 3.1 代码层面优化

| 问题类型 | 优化方案 |
|---------|----------|
| **循环嵌套** | 降低时间复杂度，使用哈希表替代嵌套循环 |
| **字符串拼接** | 大量拼接改用 `StringBuilder` |
| **反射调用** | 缓存 Method 对象，或使用 MethodHandle |
| **序列化** | Jackson 替换 JDK 序列化，考虑 Protobuf |

### 3.2 JVM 调优

```bash
# 优化GC配置（使用G1收集器）
-XX:+UseG1GC 
-XX:MaxGCPauseMillis=200        # 期望最大停顿时间200ms
-XX:InitiatingHeapOccupancyPercent=45  # 老年代占用45%触发Mixed GC
-XX:+HeapDumpOnOutOfMemoryError  # OOM时自动dump
-XX:HeapDumpPath=/var/log/heap_dump.hprof
```

### 3.3 监控告警

**部署监控指标**：
- **Prometheus + Grafana**：采集 JVM 指标（`micrometer`）
- **告警规则**：
  - CPU 持续 5 分钟 > 80%
  - GC 耗时占比 > 10%
  - 接口 P99 延迟 > 1s

**日志采集**：
```java
// 记录慢接口
@Aspect
public class PerformanceLogAspect {
    @Around("@annotation(Monitored)")
    public Object logPerformance(ProceedingJoinPoint pjp) {
        long start = System.currentTimeMillis();
        Object result = pjp.proceed();
        long cost = System.currentTimeMillis() - start;
        if (cost > 1000) {
            log.warn("慢方法: {} 耗时: {}ms", pjp.getSignature(), cost);
        }
        return result;
    }
}
```

### 3.4 应急预案

**临时止血措施**：
1. **限流降级**：Sentinel 限制流量
2. **扩容**：K8s 临时增加 Pod 副本数
3. **重启**：清理堆内存（治标不治本）

**根本解决**：
- 定位根因代码并修复
- 回归测试 + 压测验证
- 发布修复版本

## 四、答题总结

**标准排查流程**：
1. **top** 查看系统 CPU，判断 us/sy/wa 占比
2. **top -c** 定位到具体进程 PID
3. **top -Hp PID** 找出占用高的线程 ID
4. **printf "%x"** 转为十六进制
5. **jstack** 导出线程栈，搜索 nid 定位代码
6. **分析根因**：死循环/正则回溯/频繁 GC/锁竞争
7. **优化代码** + **JVM 调优** + **监控告警**

**面试加分项**：
- 提及 **Arthas** 在线诊断工具的使用
- 提及 **火焰图**（perf + FlameGraph）可视化 CPU 热点
- 提及 **异步化改造**：CPU 密集任务放到线程池异步处理
- 提及 **缓存预热**：避免启动时大量计算

**典型面试问答**：
> **面试官**："如果是 sy 高而不是 us 高怎么办？"  
> **回答**："说明系统调用频繁，可能原因：
> - 频繁创建销毁线程 → 改用线程池
> - 网络连接未复用 → 使用连接池（Hikari/Jedis Pool）
> - 大量磁盘 IO → 检查日志输出频率、数据库慢查询"

**工具清单**：
- **系统层**：top, htop, vmstat, pidstat
- **JVM 层**：jstack, jmap, jstat, jcmd
- **进阶工具**：Arthas, async-profiler, JProfiler
