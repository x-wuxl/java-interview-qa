---
title: "JDK11中新出的ZGC有什么特点？"
date: 2025-11-01
description: "深入解析JDK11中引入的ZGC垃圾回收器，包括其低延迟、高扩展性和并发处理的核心特性"
author: "wuxl"
categories: [JVM]
tags: [JVM, 垃圾回收, ZGC, JDK11, 低延迟, 并发GC]
nav_order: 140
parent: JVM
---
## 问题

JDK11中新出的ZGC有什么特点？

## 答案

### 核心概念

**ZGC（Z Garbage Collector）**是JDK11中引入的一款革命性的低延迟垃圾回收器。ZGC的目标是实现**任意堆大小下的亚毫秒级停顿时间**，支持从几百MB到几TB的堆内存，同时保持高吞吐量。

### ZGC的核心特点

#### 1. 超低延迟

```java
public class ZGCLowLatency {
    public static void demonstrateLowLatency() {
        /*
         * ZGC停顿时间目标：< 1ms
         * 无论堆大小，停顿时间都稳定在亚毫秒级
         *
         * 对比其他GC的停顿时间：
         * - CMS: 几百毫秒到几秒
         * - G1: 几十毫秒到几百毫秒
         * - ZGC: < 1ms
         */

        System.out.println("ZGC的核心优势：");
        System.out.println("- 停顿时间 < 1ms");
        System.out.println("- 不受堆大小影响");
        System.out.println("- 适合对延迟极其敏感的应用");
    }

    // 实际测试示例
    public static void pauseTimeTest() {
        // 64GB堆内存下的停顿时间对比
        System.out.println("64GB堆内存下的停顿时间：");
        System.out.println("CMS: 2-10秒");
        System.out.println("G1: 200-800ms");
        System.out.println("ZGC: < 1ms");
    }
}
```

#### 2. 高扩展性

```java
public class ZGCScalability {
    public static void demonstrateScalability() {
        /*
         * ZGC支持的堆大小范围：几百MB到几TB
         * 性能不受堆大小影响
         *
         * 适用场景：
         * - 大数据分析
         * - 机器学习训练
         * - 实时数据处理
         * - 内存数据库
         */

        demonstrateHeapSizeSupport();
    }

    private static void demonstrateHeapSizeSupport() {
        System.out.println("ZGC堆大小支持范围：");

        // 小堆场景
        System.out.println("小堆（512MB）：");
        System.out.println("- 停顿时间：0.1-0.5ms");
        System.out.println("- 吞吐量：高");

        // 中等堆场景
        System.out.println("中等堆（8GB）：");
        System.out.println("- 停顿时间：0.2-0.8ms");
        System.out.println("- 吞吐量：高");

        // 大堆场景
        System.out.println("大堆（128GB）：");
        System.out.println("- 停顿时间：0.3-0.9ms");
        System.out.println("- 吞吐量：中高");

        // 超大堆场景
        System.out.println("超大堆（1TB）：");
        System.out.println("- 停顿时间：0.5-1.0ms");
        System.out.println("- 吞吐量：中等");
    }
}
```

### ZGC的核心技术

#### 1. 着色指针（Colored Pointers）

```java
public class ColoredPointers {
    public static void demonstrateColoredPointers() {
        /*
         * ZGC使用着色指针技术，在指针中存储额外信息：
         *
         * 64位指针结构：
         * [ 63- 42] [41- 4] [ 3- 2] [ 1- 0]
         *   堆地址    Finalizable    Remapped    Marked
         *
         * - Marked(1): 对象是否被标记
         * - Remapped(1): 对象是否被重映射
         * - Finalizable(1): 对象是否需要finalization
         */

        System.out.println("着色指针的优势：");
        System.out.println("- 无需额外的对象头空间");
        System.out.println("- 支持并发移动对象");
        System.out.println("- 减少内存开销");
    }

    // 着色指针示例（概念性）
    public static class ColoredPointerExample {
        // 伪代码：展示着色指针的思路
        public static long createColoredPointer(long address, boolean marked, boolean remapped) {
            long pointer = address;          // 堆地址
            if (marked) pointer |= 0x1;      // 设置Marked位
            if (remapped) pointer |= 0x2;    // 设置Remapped位
            return pointer;
        }

        public static boolean isMarked(long coloredPointer) {
            return (coloredPointer & 0x1) != 0;
        }

        public static boolean isRemapped(long coloredPointer) {
            return (coloredPointer & 0x2) != 0;
        }

        public static long getAddress(long coloredPointer) {
            return coloredPointer & ~0x3; // 清除状态位，获取地址
        }
    }
}
```

#### 2. 读屏障（Load Barriers）

```java
public class LoadBarriers {
    public static void demonstrateLoadBarriers() {
        /*
         * 读屏障的作用：
         * 1. 检测指针是否指向需要更新位置的对象
         * 2. 如果需要，执行指针的自愈操作
         * 3. 确保应用线程总是看到正确的对象引用
         *
         * 读屏障是ZGC实现并发对象移动的关键
         */

        System.out.println("读屏障的工作原理：");
        System.out.println("- 在每次对象引用读取时触发");
        System.out.println("- 检查对象是否需要更新");
        System.out.println("- 自动更新指针指向新位置");
        System.out.println("- 对应用线程透明");
    }

    // 读屏障伪代码示例
    public static class LoadBarrierExample {
        public static Object loadWithBarrier(Object reference) {
            // 原始引用读取
            Object obj = reference;

            // 读屏障检查
            if (needsHealing(obj)) {
                // 执行指针自愈
                obj = healReference(obj);
            }

            return obj;
        }

        private static boolean needsHealing(Object obj) {
            // 检查对象是否需要指针更新
            // 基于着色指针的状态位判断
            return false; // 简化实现
        }

        private static Object healReference(Object obj) {
            // 更新指针指向对象的新位置
            return obj; // 简化实现
        }
    }
}
```

#### 3. 并发处理

```java
public class ZGCConcurrentProcessing {
    public static void demonstrateConcurrentPhases() {
        /*
         * ZGC的并发阶段：
         * 1. 并发标记（Concurrent Mark）
         * 2. 并发预备重映射（Concurrent Prepare Relocate）
         * 3. 并发重映射（Concurrent Relocate）
         *
         * 所有耗时操作都是并发执行，不停止应用线程
         */

        System.out.println("ZGC并发阶段特点：");
        System.out.println("- 标记阶段完全并发");
        System.out.println("- 重映射阶段完全并发");
        System.out.println("- 只有极短暂的STW");
        System.out.println("- STW时间不随堆大小增长");
    }

    // ZGC工作流程示例
    public static void zgcWorkflow() {
        System.out.println("ZGC工作流程：");

        // 阶段1：暂停标记（STW，极短）
        System.out.println("1. 暂停标记（Pause Mark Start）");
        System.out.println("   - 标记GC Roots");
        System.out.println("   - 时间：< 0.1ms");

        // 阶段2：并发标记
        System.out.println("2. 并发标记（Concurrent Mark）");
        System.out.println("   - 遍历对象图");
        System.out.println("   - 与应用并发执行");

        // 阶段3：暂停标记结束（STW，极短）
        System.out.println("3. 暂停标记结束（Pause Mark End）");
        System.out.println("   - 处理标记完成");
        System.out.println("   - 时间：< 0.1ms");

        // 阶段4：并发预备重映射
        System.out.println("4. 并发预备重映射（Concurrent Prepare Relocate）");
        System.out.println("   - 选择需要重映射的Region");
        System.out.println("   - 与应用并发执行");

        // 阶段5：并发重映射
        System.out.println("5. 并发重映射（Concurrent Relocate）");
        System.out.println("   - 移动存活对象到新位置");
        System.out.println("   - 与应用并发执行");
    }
}
```

### ZGC与传统GC的对比

#### 1. 内存布局对比

```java
public class MemoryLayoutComparison {
    public static void compareMemoryLayouts() {
        /*
         * 传统GC内存布局：
         * CMS/G1: 分代布局（新生代+老年代）
         *
         * ZGC内存布局：
         * - 不分代设计
         * - 基于Region的布局
         * - 小Region（2MB-512MB）
         * - 支持NUMA架构优化
         */

        demonstrateLayoutDifferences();
    }

    private static void demonstrateLayoutDifferences() {
        System.out.println("内存布局对比：");

        // CMS/G1布局
        System.out.println("CMS/G1布局：");
        System.out.println("┌─────────────────────────────────┐");
        System.out.println("│           新生代               │");
        System.out.println("│  Eden + S0 + S1               │");
        System.out.println("├─────────────────────────────────┤");
        System.out.println("│           老年代               │");
        System.out.println("│        连续内存区域            │");
        System.out.println("└─────────────────────────────────┘");

        // ZGC布局
        System.out.println("ZGC布局：");
        System.out.println("┌─────────────────────────────────┐");
        System.out.println("│        Region 0 (2MB)          │");
        System.out.println("├─────────────────────────────────┤");
        System.out.println("│        Region 1 (2MB)          │");
        System.out.println("├─────────────────────────────────┤");
        System.out.println("│        Region 2 (2MB)          │");
        System.out.println("│           ...                   │");
        System.out.println("└─────────────────────────────────┘");
    }
}
```

#### 2. 性能特征对比

```java
public class PerformanceComparison {
    public static void comparePerformance() {
        /*
         * 性能对比（16GB堆）：
         *
         * 指标         CMS      G1       ZGC
         * 停顿时间     200ms    50ms     0.5ms
         * 吞吐量       95%      97%      90%
         * 内存开销     15%      10%      15%
         * CPU使用率    中等      中等      较高
         */

        demonstratePerformanceMetrics();
    }

    private static void demonstratePerformanceMetrics() {
        System.out.println("不同GC的性能特征：");

        // 延迟敏感型应用
        System.out.println("延迟敏感型应用（如交易系统）：");
        System.out.println("- ZGC: 最佳选择，亚毫秒级延迟");
        System.out.println("- G1: 可接受，几十毫秒延迟");
        System.out.println("- CMS: 不推荐，几百毫秒延迟");

        // 大内存应用
        System.out.println("大内存应用（>32GB）：");
        System.out.println("- ZGC: 最佳选择，延迟稳定");
        System.out.println("- G1: 可接受，但延迟随堆增长");
        System.out.println("- CMS: 不推荐，Full GC时间长");

        // 高吞吐量应用
        System.out.println("高吞吐量应用：");
        System.out.println("- Parallel GC: 最高吞吐量");
        System.out.println("- G1: 平衡的选择");
        System.out.println("- ZGC: 吞吐量稍低但延迟优秀");
    }
}
```

### ZGC的配置和使用

#### 1. 基本配置

```java
public class ZGCConfiguration {
    public static void basicConfiguration() {
        /*
         * ZGC基本配置：
         * -XX:+UnlockExperimentalVMOptions
         * -XX:+UseZGC
         * -Xmx<size>
         *
         * 注意：ZGC需要较新的JDK版本和操作系统支持
         */

        String zgcConfig = """
            # ZGC基本配置
            -XX:+UnlockExperimentalVMOptions
            -XX:+UseZGC
            -Xmx32g  # 设置堆大小

            # 推荐配置
            -XX:+UseLargePages  # 使用大页面
            -XX:+UseTransparentHugePages  # 使用透明大页面
            """;

        System.out.println("ZGC配置示例：");
        System.out.println(zgcConfig);
    }

    // 性能调优参数
    public static void performanceTuning() {
        String tuningConfig = """
            # ZGC性能调优
            -XX:ZAllocationSpikeTolerance=5  # 分配峰值容忍度
            -XX:ZCollectionInterval=10       # GC间隔（毫秒）
            -XX:ZFragmentationLimit=25       # 碎片限制
            -XX:ZMarkStackSpaceLimit=8G      # 标记栈空间限制
            """;

        System.out.println("ZGC调优参数：");
        System.out.println(tuningConfig);
    }
}
```

#### 2. 监控和诊断

```java
public class ZGCMonitoring {
    public static void demonstrateMonitoring() {
        /*
         * ZGC监控工具：
         * 1. JMX监控
         * 2. GC日志
         * 3. 性能计数器
         * 4. JVM诊断命令
         */

        provideMonitoringExamples();
    }

    private static void provideMonitoringExamples() {
        // GC日志配置
        String gcLogConfig = """
            # ZGC GC日志配置
            -Xlog:gc*:file=/var/log/zgc.log:time,level,tags
            -Xlog:gc+heap=debug
            -Xlog:gc+ref=debug
            -Xlog:gc+init=info
            """;

        System.out.println("ZGC监控配置：");
        System.out.println(gcLogConfig);

        // 关键监控指标
        System.out.println("关键监控指标：");
        System.out.println("- GC停顿时间");
        System.out.println("- GC频率");
        System.out.println("- 堆内存使用");
        System.out.println("- 分配速率");
        System.out.println("- CPU使用率");
    }
}
```

### ZGC的适用场景

#### 1. 理想使用场景

```java
public class ZGCUseCases {
    public static void idealUseCases() {
        /*
         * ZGC的理想使用场景：
         * 1. 对延迟极其敏感的应用
         * 2. 大内存应用（>16GB）
         * 3. 实时数据处理
         * 4. 金融交易系统
         * 5. 游戏服务器
         */

        demonstrateIdealScenarios();
    }

    private static void demonstrateIdealScenarios() {
        // 金融交易系统
        System.out.println("金融交易系统：");
        System.out.println("- 要求：< 1ms的GC停顿");
        System.out.println("- 大内存需求");
        System.out.println("- ZGC是理想选择");

        // 大数据分析
        System.out.println("大数据分析：");
        System.out.println("- 大堆内存（>64GB）");
        System.out.println("- 对GC延迟敏感");
        System.out.println("- ZGC提供稳定性能");

        // 实时游戏
        System.out.println("实时游戏服务器：");
        System.out.println("- 严格的延迟要求");
        System.out.println("- 高并发对象分配");
        System.out.println("- ZGC保证流畅体验");
    }
}
```

#### 2. 不适合的场景

```java
public class ZGCLimitations {
    public static void limitations() {
        /*
         * ZGC的限制：
         * 1. CPU使用率较高
         * 2. JDK版本要求（JDK11+）
         * 3. 操作系统支持要求
         * 4. 小内存应用收益有限
         */

        demonstrateLimitations();
    }

    private static void demonstrateLimitations() {
        System.out.println("ZGC的局限性：");

        // CPU密集型应用
        System.out.println("CPU密集型应用：");
        System.out.println("- ZGC需要较多CPU资源");
        System.out.println("- 可能与应用竞争CPU");
        System.out.println("- 需要合理配置CPU资源");

        // 小内存应用
        System.out.println("小内存应用（<4GB）：");
        System.out.println("- G1或Parallel GC可能更合适");
        System.out.println("- ZGC的优势不明显");
        System.out.println("- 内存开销相对较大");

        // 兼容性问题
        System.out.println("兼容性要求：");
        System.out.println("- 需要JDK11+");
        System.out.println("- 需要现代操作系统支持");
        System.out.println("- 某些平台可能不支持");
    }
}
```

### ZGC的发展趋势

#### 1. 版本演进

```java
public class ZGCEvolution {
    public static void versionEvolution() {
        /*
         * ZGC版本演进：
         * JDK 11: 首次引入（实验性）
         * JDK 12: 改进性能，增加平台支持
         * JDK 13: 优化内存分配，减少碎片
         * JDK 14: 正式发布，性能进一步提升
         * JDK 15+: 持续优化，增加新特性
         */

        System.out.println("ZGC版本演进：");
        System.out.println("JDK 11: 实验性版本，初步可用");
        System.out.println("JDK 12: 性能优化，平台扩展");
        System.out.println("JDK 13: 内存分配优化");
        System.out.println("JDK 14: 正式版本，生产就绪");
        System.out.println("JDK 15+: 持续改进，稳定性提升");
    }
}
```

### 面试要点总结

1. **核心特点**：亚毫秒级停顿时间，不受堆大小影响
2. **关键技术**：着色指针、读屏障、并发处理
3. **内存布局**：不分代，基于Region设计
4. **性能优势**：超低延迟、高扩展性、并发处理
5. **适用场景**：延迟敏感、大内存、实时应用
6. **局限性**：CPU使用率高、版本要求、兼容性

**关键理解**：
- ZGC是革命性的低延迟垃圾回收器
- 通过着色指针和读屏障实现并发对象移动
- 适合对延迟极其敏感的大型应用
- 代表了Java GC技术的发展方向

**实际意义**：
- 为Java在超低延迟场景中的应用提供了可能
- 使得Java可以胜任更多实时性要求高的场景
- 推动了Java生态系统的现代化进程
- 为未来的GC技术发展奠定了基础

ZGC代表了垃圾回收技术的最新发展，是理解现代JVM高级特性的重要知识点。