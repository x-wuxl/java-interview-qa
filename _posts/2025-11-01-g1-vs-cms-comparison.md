---
layout: post
title: "G1和CMS有什么区别？"
date: 2025-11-01
description: "详细对比G1和CMS两种垃圾回收器的差异，从内存布局、回收算法、性能特点等多个维度分析"
author: "wuxl"
categories: [JVM]
tags: [JVM, 垃圾回收, G1, CMS, 性能对比, 内存管理]
---

## 问题

G1和CMS有什么区别？

## 答案

### 核心概念

**G1（Garbage-First）**和**CMS（Concurrent Mark Sweep）**都是面向老年代的并发垃圾回收器，但它们在设计理念、内存布局和回收策略上有本质区别。G1是CMS的继任者，旨在解决CMS的主要问题，同时保持低延迟的特性。

### 内存布局差异

#### 1. CMS的内存布局

```java
public class CMSMemoryLayout {
    /*
     * CMS内存布局：
     * ┌─────────────────────────────────────────────────────────┐
     * │                     新生代                               │
     * │  ┌─────────┐ ┌─────────┐ ┌─────────┐                    │
     * │  │  Eden   │ │ Survivor│ │ Survivor│                    │
     * │  │   区    │ │   0     │ │   1     │                    │
     * │  └─────────┘ └─────────┘ └─────────┘                    │
     * └─────────────────────────────────────────────────────────┘
     * ┌─────────────────────────────────────────────────────────┐
     * │                     老年代                               │
     * │                  (连续的大块空间)                        │
     * └─────────────────────────────────────────────────────────┘
     */

    public static void demonstrateCMSLayout() {
        // CMS采用传统的分代布局
        // 新生代：Eden + 2个Survivor区
        // 老年代：连续的大块内存空间

        System.out.println("CMS：传统的分代内存布局");
        System.out.println("新生代：Eden + S0 + S1");
        System.out.println("老年代：连续内存区域");
    }
}
```

#### 2. G1的内存布局

```java
public class G1MemoryLayout {
    /*
     * G1内存布局：
     * ┌─────────────────────────────────────────────────────────┐
     * │                  Region划分                             │
     * │  ┌──���──┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │
     * │  │ E   │ │ E   │ │ O   │ │ H   │ │ E   │ │ O   │        │
     * │  │     │ │     │ │     │ │     │ │     │ │     │        │
     * │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘        │
     * │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │
     * │  │ O   │ │ S   │ │ S   │ │ E   │ │ O   │ │ E   │        │
     * │  │     │ │     │ │     │ │     │ │     │ │     │        │
     * │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘        │
     * └─────────────────────────────────────────────────────────┘
     * E: Eden Region, O: Old Region, S: Survivor Region, H: Humongous Region
     */

    public static void demonstrateG1Layout() {
        // G1将整个堆划分为多个大小相等的Region
        // 每个Region可以是Eden、Survivor、Old或Humongous
        // Region大小通常是1MB到32MB之间

        System.out.println("G1：基于Region的内存布局");
        System.out.println("堆被划分为多个Region");
        System.out.println("每个Region可以扮演不同角色");
    }
}
```

### 回收算法差异

#### 1. CMS的回收算法

```java
public class CMSAlgorithm {
    // CMS使用标记-清除算法
    public static void markSweepAlgorithm() {
        /*
         * 标记-清除算法：
         * 1. 标记阶段：标记所有存活对象
         * 2. 清除阶段：回收未标记的对象
         *
         * 优点：
         * - 算法简单，实现容易
         * - 回收效率高
         *
         * 缺点：
         * - 产生内存碎片
         * - 标记和清除都需要遍历整个内存空间
         */

        // 内存碎片示例
        // 回收前：[存活][垃圾][存活][垃圾][存活]
        // 回收后：[空闲][存活][空闲][存活][空闲]
        // 问题：虽然总空闲空间很大，但无法分配连续的大对象
    }
}
```

#### 2. G1的回收算法

```java
public class G1Algorithm {
    // G1使用标记-整理算法（基于Region）
    public static void markCompactAlgorithm() {
        /*
         * G1的回收过程：
         * 1. 标记阶段：并发标记存活对象
         * 2. 回收阶段：选择收益最高的Region进行回收
         * 3. 整理阶段：将存活对象复制到新的Region
         *
         * 特点：
         * - 增量回收，每次只回收部分Region
         * - 复制算法，无内存碎片
         * - 可预测的停顿时间
         */

        // Region回收示例
        // 回收前：Region1(垃圾) Region2(存活) Region3(垃圾)
        // 回收后：Region1(空闲) Region2(存活) Region3(空闲)
        // 结果：无碎片，内存利用率高
    }
}
```

### 回收过程差异

#### 1. CMS的回收过程

```java
public class CMSProcess {
    public static void cmsCollectionProcess() {
        /*
         * CMS回收过程：
         * 1. 初始标记 (STW) - 标记GC Roots直接引用的对象
         * 2. 并发标记 - 与应用并发，标记所有存活对象
         * 3. 重新标记 (STW) - 处理并发期间的引用变化
         * 4. 并发清除 - 与应用并发，回收垃圾对象
         */

        System.out.println("CMS：四个阶段，两次STW");
        System.out.println("STW时间：初始标记(短) + 重新标记(中等)");
        System.out.println("并发时间：标记(长) + 清除(长)");
    }
}
```

#### 2. G1的回收过程

```java
public class G1Process {
    public static void g1CollectionProcess() {
        /*
         * G1回收过程：
         * 1. 初始标记 (STW) - 标记GC Roots直接引用的对象
         * 2. 并发标记 - 与应用并发，建立Region存活信息
         * 3. 最终标记 (STW) - 完成存活对象标记
         * 4. 筛选回收 (STW) - 选择Region进行回收和复制
         */

        System.out.println("G1：三个主要阶段，多次STW");
        System.out.println("STW时间：Young GC(短) + Mixed GC(中等)");
        System.out.println("并发时间：标记过程(长)");
    }
}
```

### 性能特点对比

#### 1. 内存碎片处理

```java
public class MemoryFragmentationComparison {
    public static void compareFragmentation() {
        // CMS的内存碎片问题
        demonstrateCMSFragmentation();

        // G1的内存整理能力
        demonstrateG1Compaction();
    }

    private static void demonstrateCMSFragmentation() {
        /*
         * CMS内存碎片问题：
         * - 使用标记-清除算法，不移动对象
         * - 随着时间推移，内存碎片越来越多
         * - 可能无法分配大对象，触发Full GC
         * - Full GC会导致长时间停顿
         */

        // 示例：CMS碎片化场景
        // 老年代空间：[占用10MB][空闲1MB][占用10MB][空闲1MB][占用10MB]
        // 需要分配：8MB对象
        // 结果：分配失败，虽然总空闲空间为2MB > 8MB
    }

    private static void demonstrateG1Compaction() {
        /*
         * G1内存整理能力：
         * - 使用复制算法，自动整理内存
         * - 每次回收都选择完整的Region进行清理
         * - 将存活对象复制到新的Region
         * - 从根本上避免内存碎片
         */

        // 示例：G1内存整理
        // 回收前：Region1(碎片化) Region2(碎片化)
        // 回收后：Region1(空) Region2(整理后，内存连续)
    }
}
```

#### 2. 停顿时间控制

```java
public class PauseTimeComparison {
    public static void comparePauseTimes() {
        // CMS的停顿时间特点
        demonstrateCMSPauseTimes();

        // G1的停顿时间控制
        demonstrateG1PauseTimeControl();
    }

    private static void demonstrateCMSPauseTimes() {
        /*
         * CMS停顿时间：
         * - Young GC：可预测，较短（几十毫秒）
         * - CMS GC：初始标记(短) + 重新标记(中等)
         * - Full GC：不可预测，可能很长（数秒）
         * - 问题：Full GC的停顿时间不可控
         */

        System.out.println("CMS停顿时间特点：");
        System.out.println("优点：大部分停顿时间较短");
        System.out.println("缺点：Full GC停顿时间不可控");
    }

    private static void demonstrateG1PauseTimeControl() {
        /*
         * G1停顿时间控制：
         * - 可通过参数设置最大停顿时间目标
         * - -XX:MaxGCPauseMillis=200 (200ms)
         * - G1会根据停顿目标调整回收策略
         * - 增量回收，避免长时间停顿
         */

        System.out.println("G1停顿时间特点：");
        System.out.println("优点：停顿时间可预测、可控");
        System.out.println("特点：增量回收，分批处理");
    }
}
```

### 大对象处理差异

#### 1. CMS的大对象处理

```java
public class CMSLargeObjectHandling {
    public static void demonstrateCMSLargeObjects() {
        /*
         * CMS大对象处理：
         * - 大对象直接在老年代分配
         * - 如果老年代空间不足且碎片化，可能分配失败
         * - 分配失败会触发Full GC进行内存整理
         * - Full GC会导致长时间停顿
         */

        // 示例：CMS大对象分配
        allocateLargeObject(); // 可能触发Full GC
    }

    private static void allocateLargeObject() {
        // 8MB大对象
        byte[] largeArray = new byte[8 * 1024 * 1024];
        // 在CMS中，如果老年代碎片化，可能无法分配
    }
}
```

#### 2. G1的大对象处理

```java
public class G1LargeObjectHandling {
    public static void demonstrateG1LargeObjects() {
        /*
         * G1大对象处理：
         * - 大对象分配在Humongous Region中
         * - 一个大对象可能占用多个连续的Region
         * - 回收时会考虑Humongous Region的回收收益
         * - 避免了老年代的碎片化问题
         */

        // 示例：G1大对象分配
        allocateHumongousObject(); // 分配到Humongous Region
    }

    private static void allocateHumongousObject() {
        // 8MB大对象，假设Region大小为1MB
        byte[] largeArray = new byte[8 * 1024 * 1024];
        // 会占用8个连续的Humongous Region
    }
}
```

### 适用场景对比

#### 1. CMS适用场景

```java
public class CMSSuitableScenarios {
    /*
     * CMS适用场景：
     * 1. 对响应时间敏感的应用
     * 2. 内存占用较大的应用
     * 3. CPU资源充足的环境
     * 4. Java 8及之前的版本
     */

    public static void cmsBestPractices() {
        // 适合互联网Web应用
        WebApplication webApp = new WebApplication();

        // 适合缓存系统
        CacheSystem cache = new CacheSystem();

        // 需要配置合理的参数避免Full GC
        configureCMSParameters();
    }

    private static void configureCMSParameters() {
        // -XX:CMSInitiatingOccupancyFraction=70
        // -XX:+UseCMSInitiatingOccupancyOnly
        // -XX:+CMSParallelRemarkEnabled
    }
}
```

#### 2. G1适用场景

```java
public class G1SuitableScenarios {
    /*
     * G1适用场景：
     * 1. 需要可预测停顿时间的应用
     * 2. 内存占用较大的应用（>4GB）
     * 3. 大内存服务器应用
     * 4. Java 9+的推荐选择
     */

    public static void g1BestPractices() {
        // 适合大数据处理应用
        BigDataApplication bigDataApp = new BigDataApplication();

        // 适合微服务架构
        MicroService microservice = new MicroService();

        // 需要配置停顿时间目标
        configureG1Parameters();
    }

    private static void configureG1Parameters() {
        // -XX:MaxGCPauseMillis=200
        // -XX:G1HeapRegionSize=16m
        // -XX:InitiatingHeapOccupancyPercent=45
    }
}
```

### 配置参数对比

#### 1. CMS关键参数

```bash
# 启用CMS
-XX:+UseConcMarkSweepGC

# CMS触发阈值
-XX:CMSInitiatingOccupancyFraction=70
-XX:+UseCMSInitiatingOccupancyOnly

# 并发参数
-XX:ParallelGCThreads=4
-XX:ConcGCThreads=2

# 内存整理
-XX:+UseCMSCompactAtFullCollection
-XX:CMSFullGCsBeforeCompaction=5
```

#### 2. G1关键参数

```bash
# 启用G1
-XX:+UseG1GC

# 停顿时间目标
-XX:MaxGCPauseMillis=200

# Region大小
-XX:G1HeapRegionSize=16m

# 触发阈值
-XX:InitiatingHeapOccupancyPercent=45

# 大对象阈值
-XX:G1HumongousObjectThreshold=2m
```

### 迁移建议

#### 1. 从CMS迁移到G1

```java
public class CMS2G1Migration {
    public static void migrationSteps() {
        /*
         * 迁移步骤：
         * 1. 评估当前应用特点
         * 2. 在测试环境中验证G1性能
         * 3. 调整G1参数以匹配性能要求
         * 4. 逐步在生产环境中部署
         */

        System.out.println("迁移建议：");
        System.out.println("1. Java 9+环境推荐使用G1");
        System.out.println("2. 大内存应用（>8GB）优先选择G1");
        System.out.println("3. 需要可预测停顿时间选择G1");
        System.out.println("4. 传统应用可继续使用CMS");
    }
}
```

### 面试要点总结

1. **内存布局**：CMS传统分代 vs G1基于Region
2. **回收算法**：CMS标记-清除 vs G1标记-整理（复制）
3. **碎片处理**：CMS有碎片问题 vs G1自动整理
4. **停顿控制**：CMS不可控 vs G1可预测
5. **大对象**：CMS老年代 vs G1 Humongous Region
6. **适用场景**：CMS响应敏感 vs G1大内存+可预测停顿

**关键理解**：
- G1是CMS的进化版本，解决了CMS的主要问题
- Region化设计是G1的核心创新
- 可预测停顿时间是G1的最大优势
- 从CMS到G1是Java GC发展的趋势

**选择建议**：
- Java 9+：优先选择G1
- 大内存应用（>4GB）：选择G1
- 需要可预测停顿时间：选择G1
- 传统小内存应用：可考虑CMS
- 重点关注应用的性能需求和JVM版本

G1代表了现代垃圾回收器的发展方向，是理解Java GC演进的重要知识点。