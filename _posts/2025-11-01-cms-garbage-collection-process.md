---
layout: post
title: "介绍下CMS的垃圾回收过程"
date: 2025-11-01
description: "深入解析CMS垃圾回收器的完整回收过程，包括初始标记、并发标记、重新标记和并发清除四个阶段"
author: "wuxl"
categories: [JVM]
tags: [JVM, 垃圾回收, CMS, 并发标记清除, 内存管理]
---

## 问题

介绍下CMS的垃圾回收过程

## 答案

### 核心概念

**CMS（Concurrent Mark Sweep）**是一种以获取最短回收停顿时间为目标的垃圾回收器，基于**并发标记清除**算法。CMS主要用于老年代的垃圾回收，强调在垃圾回收过程中最大程度地减少用户线程的停顿时间。

### CMS回收器的四个阶段

#### 1. 初始标记（Initial Mark）

**特点**：**STW（Stop-The-World）**，但时间很短

```java
// 初始标记阶段的工作内容
public class InitialMarkPhase {
    public static void initialMark() {
        // 1. 标记GC Roots直接引用的对象
        // 2. 标记新生代对象引用的老年代对象

        // 示例：需要标记的对象
        Object staticObj = staticReference;          // 静态变量引用
        Object localVar = getLocalVariable();        // 栈中局部变量
        Object threadObj = threadLocalVariable.get(); // 线程本地变量

        // 这些对象会被快速标记，通常只需要几毫秒
        System.out.println("初始标记完成，标记了GC Roots直接引用的对象");
    }

    private static Object staticReference = new Object();
    private static ThreadLocal<Object> threadLocalVariable = new ThreadLocal<>();
}
```

**初始标记过程**：
- 暂停所有应用线程（STW）
- 仅标记GC Roots直接可达的对象
- 速度很快，因为标记范围有限
- 为后续的并发标记阶段提供起始点

#### 2. 并发标记（Concurrent Mark）

**特点**：**与应用线程并发执行**，无STW

```java
// 并发标记阶段的工作内容
public class ConcurrentMarkPhase {
    public static void concurrentMark() {
        // 1. 从初始标记的对象开始，遍历整个对象图
        // 2. 跟踪对象引用链，标记所有存活对象
        // 3. 与应用线程同时进行

        // 示例：并发标记过程
        Object root = getInitialMarkedObject();
        markReachableObjects(root);

        // 在此期间，应用线程仍在运行
        System.out.println("并发标记进行中，应用线程继续执行");
    }

    private static void markReachableObjects(Object obj) {
        // 深度优先或广度优先遍历对象图
        // 标记obj引用的所有对象
        // 递归处理所有可达对象
    }
}
```

**并发标记特点**：
- **多线程并发**：使用多个GC线程并行标记
- **与应用并发**：不需要暂停应用线程
- **时间较长**：但不会影响应用响应
- **可能产生浮动垃圾**：因为应用线程在运行

#### 3. 重新标记（Remark）

**特点**：**STW**，但比初始标记时间长

```java
// 重新标记阶段的工作内容
public class RemarkPhase {
    public static void remark() {
        // 1. 处理并发标记期间应用线程产生的对象引用变化
        // 2. 标记并发标记期间新创建的对象
        // 3. 修正并发标记过程中的标记错误

        // 示例：需要重新标记的情况
        Object newObj = new Object();           // 并发标记期间创建
        existingObj.setReference(newObj);       // 引用关系变化

        System.out.println("重新标记完成，处理了并发期间的引用变化");
    }

    private static Object existingObj = new Object();
}
```

**重新标记过程**：
- 暂停所有应用线程
- 处理并发标记期间的引用变化
- 使用**卡表（Card Table）**技术来记录引用变化
- 通常采用**最终标记（Final Marking）**来确保准确性

#### 4. 并发清除（Concurrent Sweep）

**特点**：**与应用线程并发执行**，无STW

```java
// 并发清除阶段的工作内容
public class ConcurrentSweepPhase {
    public static void concurrentSweep() {
        // 1. 遍历整个老年代空间
        // 2. 回收未标记的对象
        // 3. 与应用线程同时进行

        // 示例：并发清除过程
        sweepUnmarkedObjects();

        // 在此期间，应用线程仍在运行
        System.out.println("并发清除进行中，回收未标记对象");
    }

    private static void sweepUnmarkedObjects() {
        // 扫描老年代，回收未被标记的对象
        // 将回收的空间加入空闲列表
    }
}
```

### CMS的卡表（Card Table）机制

#### 1. 卡表的作用

```java
public class CardTableMechanism {
    // 卡表用于记录新生代到老年代的引用变化
    // 每个卡片（通常512字节）记录一个脏位

    public static void demonstrateCardTable() {
        // 当老年代对象引用了新生代对象时
        Object oldGenObj = getOldGenerationObject();
        Object newGenObj = getNewGenerationObject();

        oldGenObj.setReference(newGenObj); // 产生引用关系

        // 更新卡表，标记对应的卡片为"脏"
        updateCardTable(oldGenObj);
    }

    private static void updateCardTable(Object obj) {
        // 根据对象地址计算对应的卡表索引
        // 将该卡表位置标记为脏
        // 并发标记阶段需要重新扫描这些脏卡片
    }
}
```

#### 2. 写屏障（Write Barrier）

```java
public class WriteBarrier {
    // 写屏障用于拦截引用写操作
    public static void writeBarrier(Object field, Object newValue) {
        // 1. 执行原始的引用赋值
        field = newValue;

        // 2. 检查是否是跨代引用（新生代到老年代）
        if (isCrossGenerationReference(field, newValue)) {
            // 3. 更新卡表
            updateCardTable(field);
        }
    }

    private static boolean isCrossGenerationReference(Object field, Object newValue) {
        return isInOldGeneration(field) && isInNewGeneration(newValue);
    }
}
```

### CMS的优缺点分析

#### 1. CMS的优点

```java
public class CMSAdvantages {
    public static void main(String[] args) {
        // 1. 低延迟：STW时间短
        demonstrateLowLatency();

        // 2. 并发回收：大部分工作与应用并发
        demonstrateConcurrentCollection();

        // 3. 适合响应时间要求高的应用
        demonstrateSuitableApplications();
    }

    private static void demonstrateLowLatency() {
        // 初始标记：几毫秒
        // 重新标记：几十毫秒到几百毫秒
        // 总STW时间：通常在100ms以内
        System.out.println("CMS停顿时间短，适合对响应时间敏感的应用");
    }

    private static void demonstrateConcurrentCollection() {
        // 并发标记：几秒到几十秒（不阻塞应用）
        // 并发清除：几秒到几十秒（不阻塞应用）
        // 应用可以在GC过程中继续响应请求
        System.out.println("CMS与应用并发执行，最大化吞吐量");
    }
}
```

#### 2. CMS的缺点

```java
public class CMSDisadvantages {
    public static void main(String[] args) {
        // 1. 内存碎片问题
        demonstrateMemoryFragmentation();

        // 2. 并发模式失败
        demonstrateConcurrentModeFailure();

        // 3. CPU敏感
        demonstrateCPUSensitivity();
    }

    private static void demonstrateMemoryFragmentation() {
        // CMS使用标记-清除算法，不压缩内存
        // 导致内存碎片，可能无法分配大对象

        // 碎片示例：
        // [已使用][空闲][已使用][空闲][已使用]
        // 虽然总空闲空间足够，但无法分配连续的大内存

        System.out.println("CMS产生内存碎片，可能导致Full GC");
    }

    private static void demonstrateConcurrentModeFailure() {
        // 并发清除期间，如果应用需要分配大对象
        // 但内存碎片导致无法分配，就会发生并发模式失败
        // 此时会触发串行Full GC，导致长时间STW

        System.out.println("并发模式失败会导致长时间停顿");
    }

    private static void demonstrateCPUSensitivity() {
        // CMS需要额外的CPU资源进行并发回收
        // 在CPU资源紧张时可能影响应用性能

        System.out.println("CMS对CPU敏感，可能抢占应用资源");
    }
}
```

### CMS配置参数

#### 1. 基本配置

```bash
# 启用CMS回收器
-XX:+UseConcMarkSweepGC

# 设置老年代使用CMS回收器
-XX:+UseParNewGC  # 新生代使用ParNew回收器

# 设置并发GC线程数
-XX:ParallelGCThreads=4
-XX:ConcGCThreads=2

# 设置CMS触发阈值
-XX:CMSInitiatingOccupancyFraction=70  # 老年代使用率达到70%时触发CMS
-XX:+UseCMSInitiatingOccupancyOnly
```

#### 2. 性能调优参数

```bash
# 启用CMS并行重新标记
-XX:+CMSParallelRemarkEnabled

# 设置重新标记的并行度
-XX:ParallelCMSThreads=4

# 启用CMS并发预清理
-XX:+CMSClassUnloadingEnabled

# 设置并发清理的阈值
-XX:CMSInitiatingPermOccupancyFraction=80

# 处理碎片问题
-XX:+UseCMSCompactAtFullCollection    # Full GC时压缩
-XX:CMSFullGCsBeforeCompaction=5      # 多少次Full GC后压缩
```

### CMS的实际应用场景

#### 1. 适合的场景

```java
public class CMSSuitableScenarios {
    // 1. 互联网应用：对响应时间敏感
    public class WebApplication {
        public void handleRequest() {
            // 需要快速响应用户请求
            // CMS的低延迟特性很适合
            processRequest();
        }
    }

    // 2. 大数据应用：需要处理大量数据
    public class BigDataApplication {
        public void processData() {
            // 产生大量临时对象
            // CMS的并发回收可以减少对处理的影响
            List<Data> results = new ArrayList<>();
            for (Data item : largeDataSet) {
                results.add(process(item));
            }
        }
    }

    // 3. 缓存系统：对象生命周期长
    public class CacheSystem {
        private Map<String, Object> cache = new HashMap<>();

        public void addToCache(String key, Object value) {
            // 缓存对象生命周期较长，适合老年代
            // CMS可以高效处理这些长期存活的对象
            cache.put(key, value);
        }
    }
}
```

#### 2. 不适合的场景

```java
public class CMSUnsuitableScenarios {
    // 1. 内存密集型应用：产生大量大对象
    public class MemoryIntensiveApp {
        public void processLargeData() {
            // 创建大量大对象，容易导致内存碎片
            byte[][] largeArrays = new byte[1000][1024 * 1024];
        }
    }

    // 2. CPU资源受限的环境
    public class CPURestrictedEnvironment {
        public void backgroundProcessing() {
            // CPU资源有限时，CMS的并发回收会与应用争夺资源
            // 可能影响应用性能
        }
    }
}
```

### 面试要点总结

1. **四个阶段**：初始标记(STW) → 并发标记 → 重新标记(STW) → 并发清除
2. **核心特点**：并发标记清除，低延迟，适合响应时间敏感的应用
3. **关键机制**：卡表、写屏障、并发标记
4. **主要优势**：STW时间短，与应用并发执行
5. **主要问题**：内存碎片、并发模式失败、CPU敏感
6. **适用场景**：互联网应用、对响应时间要求高的系统

**关键理解**：
- CMS通过并发执行最大限度地减少STW时间
- 卡表机制是CMS并发标记的基础
- 内存碎片是CMS的主要缺陷
- 并发模式失败会导致严重的性能问题

**实际应用**：
- 互联网应用中广泛使用，特别是在Java 8之前
- 需要合理配置参数以避免并发模式失败
- 在Java 9之后逐渐被G1取代
- 理解CMS原理有助于理解现代GC的设计思想

CMS是现代垃圾回收器发展中的重要里程碑，其并发思想影响了后续的G1、ZGC等回收器的设计。