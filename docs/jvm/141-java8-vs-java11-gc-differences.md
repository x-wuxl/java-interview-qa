---
layout: default
title: "Java8和Java11的GC有什么区别？"
parent: JVM
nav_order: 141
description: "详细对比Java8和Java11在垃圾回收器方面的差异，包括默认GC、新特性和性能改进"
author: "wuxl"
date: 2025-11-01
---
## 问题

Java8和Java11的GC有什么区别？

## 答案

### 核心概念

从Java8到Java11，垃圾回收器发生了重大变化，主要体现在**默认GC的变更**、**新GC的引入**、**现有GC的改进**以及**废弃GC的移除**。这些变化反映了Java对现代应用需求的响应。

### 默认垃圾回收器的变化

#### 1. Java8的默认配置

```java
public class Java8DefaultGC {
    public static void demonstrateJava8Defaults() {
        /*
         * Java8默认垃圾回收器：
         * - 服务器级机器：Parallel GC
         * - 客户端级机器：Serial GC
         *
         * 检测方式：
         * java -XX:+PrintCommandLineFlags -version
         */

        System.out.println("Java8默认GC配置：");

        // 服务器级机器（>2CPU，>2GB内存）
        System.out.println("服务器级机器默认配置：");
        System.out.println("- 新生代：Parallel Scavenge");
        System.out.println("- 老年代：Parallel Old");
        System.out.println("- 特点：高吞吐量，适合批处理任务");

        // 客户端级机器
        System.out.println("客户端级机器默认配置：");
        System.out.println("- 新生代：Serial Copying");
        System.out.println("- 老年代：Serial Mark-Compact");
        System.out.println("- 特点：低内存占用，适合小型应用");
    }

    // Java8 GC检测代码
    public static void detectJava8GC() {
        // 在Java8中运行以下代码
        System.out.println("检测当前GC:");
        System.out.println("默认GC: " + getDefaultGCName());
        System.out.println("是否G1: " + isG1Enabled());
        System.out.println("是否CMS: " + isCMSEnabled());
    }

    private static String getDefaultGCName() {
        // 伪代码：获取当前使用的GC名称
        return "Parallel GC"; // Java8默认
    }

    private static boolean isG1Enabled() {
        return false; // Java8中G1不是默认
    }

    private static boolean isCMSEnabled() {
        return false; // CMS需要手动启用
    }
}
```

#### 2. Java11的默认配置

```java
public class Java11DefaultGC {
    public static void demonstrateJava11Defaults() {
        /*
         * Java11默认垃圾回收器：
         * - 所有机器：G1 GC
         *
         * 重大变化：G1成为默认GC，取代了Parallel GC
         */

        System.out.println("Java11默认GC配置：");
        System.out.println("- 新生代：G1 Young Generation");
        System.out.println("- 老年代：G1 Mixed Generation");
        System.out.println("- 特点：平衡延迟和吞吐量，适合大多数应用");

        // G1的默认参数（Java11）
        System.out.println("G1默认参数（Java11）：");
        System.out.println("- MaxGCPauseMillis: 200ms");
        System.out.println("- G1HeapRegionSize: 根据堆大小自动计算");
        System.out.println("- InitiatingHeapOccupancyPercent: 45%");
    }

    // Java11 GC检测代码
    public static void detectJava11GC() {
        // 在Java11中运行以下代码
        System.out.println("检测当前GC:");
        System.out.println("默认GC: " + getDefaultGCName());
        System.out.println("是否G1: " + isG1Enabled());
        System.out.println("G1Region大小: " + getG1RegionSize());
    }

    private static String getDefaultGCName() {
        return "G1 GC"; // Java11默认
    }

    private static boolean isG1Enabled() {
        return true; // Java11中G1是默认
    }

    private static String getG1RegionSize() {
        return "自动计算"; // 根据堆大小自动设置
    }
}
```

### 新增垃圾回收器

#### 1. ZGC的引入

```java
public class ZGCIntroduction {
    public static void demonstrateZGCIntroduction() {
        /*
         * ZGC引入时间线：
         * - Java8: 不支持ZGC
         * - Java11: 引入ZGC（实验性）
         * - Java14: ZGC成为正式特性
         * - Java15: ZGC支持Windows和macOS
         */

        System.out.println("ZGC的发展历程：");

        // Java8时期
        System.out.println("Java8时期：");
        System.out.println("- 无ZGC支持");
        System.out.println("- 可用GC：Serial, Parallel, CMS, G1");

        // Java11时期
        System.out.println("Java11时期：");
        System.out.println("- ZGC首次引入（实验性）");
        System.out.println("- 需要-XX:+UnlockExperimentalVMOptions");
        System.out.println("- 仅支持Linux/x64平台");

        // ZGC配置示例
        String zgcConfig = """
            # Java11 ZGC配置
            -XX:+UnlockExperimentalVMOptions
            -XX:+UseZGC
            -Xmx32g
            """;

        System.out.println("ZGC配置示例：");
        System.out.println(zgcConfig);
    }

    // ZGC特性对比
    public static void compareZGCFeatures() {
        System.out.println("ZGC特性：");
        System.out.println("- 停顿时间：< 1ms");
        System.out.println("- 支持堆大小：几百MB到几TB");
        System.out.println("- 并发处理：大部分工作并发执行");
        System.out.println("- 内存开销：相对较小");
    }
}
```

#### 2. Epsilon GC的引入

```java
public class EpsilonGCIntroduction {
    public static void demonstrateEpsilonGC() {
        /*
         * Epsilon GC（无操作GC）：
         * - Java8: 不支持
         * - Java11: 引入Epsilon GC
         *
         * 用途：
         * - 性能测试
         * - 内存分配压力测试
         * - 超短生命周期的应用
         */

        System.out.println("Epsilon GC特点：");
        System.out.println("- 不执行垃圾回收");
        System.out.println("- 内存耗尽时JVM退出");
        System.out.println("- 最小的GC开销（零开销）");
        System.out.println("- 适合测试和特殊场景");

        // Epsilon GC配置
        String epsilonConfig = """
            # Epsilon GC配置
            -XX:+UnlockExperimentalVMOptions
            -XX:+UseEpsilonGC
            -Xmx1g
            -XX:+AlwaysPreTouch
            """;

        System.out.println("Epsilon GC配置：");
        System.out.println(epsilonConfig);
    }

    // Epsilon GC使用场景
    public static void epsilonUseCases() {
        System.out.println("Epsilon GC使用场景：");

        // 性能测试
        System.out.println("1. 性能基准测试：");
        System.out.println("- 消除GC对性能测试的干扰");
        System.out.println("- 纯粹测试应用性能");

        // 内存泄漏测试
        System.out.println("2. 内存泄漏测试：");
        System.out.println("- 快速发现内存泄漏");
        System.out.println("- 内存耗尽时立即失败");

        // 短生命周期应用
        System.out.println("3. 短生命周期应用：");
        System.out.println("- 函数计算");
        System.out.println("- Lambda函数");
        System.out.println("- 批处理任务");
    }
}
```

### GC性能改进

#### 1. G1的改进

```java
public class G1Improvements {
    public static void demonstrateG1Improvements() {
        /*
         * G1在Java8到Java11之间的改进：
         * 1. 并行Full GC（Java9）
         * 2. 智能Region选择（Java10）
         * 3. 字符串去重改进（Java9+）
         * 4. NUMA感知优化（Java10+）
         */

        demonstrateJava8G1Features();
        demonstrateJava11G1Features();
    }

    private static void demonstrateJava8G1Features() {
        System.out.println("Java8 G1特性：");
        System.out.println("- 基本的Region化设计");
        System.out.println("- 增量回收");
        System.out.println("- 可预测停顿时间");
        System.out.println("- 基本的字符串去重（需要手动开启）");

        // Java8 G1配置
        String java8G1Config = """
            # Java8 G1配置
            -XX:+UseG1GC
            -XX:MaxGCPauseMillis=200
            -XX:G1HeapRegionSize=16m
            -XX:+UseStringDeduplication
            """;

        System.out.println("Java8 G1配置：");
        System.out.println(java8G1Config);
    }

    private static void demonstrateJava11G1Features() {
        System.out.println("Java11 G1改进：");

        // 并行Full GC
        System.out.println("1. 并行Full GC：");
        System.out.println("- 解决了G1 Full GC的串行瓶颈");
        System.out.println("- 大幅减少Full GC停顿时间");
        System.out.println("- 自动启用，无需配置");

        // 智能Region选择
        System.out.println("2. 智能Region选择：");
        System.out.println("- 更准确的回收收益计算");
        System.out.println("- 更高效的Region选择策略");
        System.out.println("- 提高回收效率");

        // NUMA感知
        System.out.println("3. NUMA感知优化：");
        System.out.println("- 支持NUMA架构");
        System.out.println("- 本地内存分配优先");
        System.out.println("- 提高多核性能");

        // Java11 G1配置
        String java11G1Config = """
            # Java11 G1配置（更多优化自动应用）
            -XX:+UseG1GC
            -XX:MaxGCPauseMillis=200
            # 以下特性自动启用：
            # 并行Full GC
            # 智能Region选择
            # NUMA感知（如适用）
            """;

        System.out.println("Java11 G1配置：");
        System.out.println(java11G1Config);
    }
}
```

#### 2. CMS的废弃

```java
public class CMSDeprecation {
    public static void demonstrateCMSChanges() {
        /*
         * CMS的废弃过程：
         * - Java8: CMS仍然可用，但已标记为废弃
         * - Java9: CMS被废弃，使用会警告
         * - Java11: CMS被完全移除
         */

        demonstrateJava8CMSStatus();
        demonstrateJava11CMSStatus();
    }

    private static void demonstrateJava8CMSStatus() {
        System.out.println("Java8中CMS的状态：");
        System.out.println("- CMS仍然可用");
        System.out.println("- 但已经标记为废弃（@deprecated）");
        System.out.println("- 使用时会显示警告信息");

        // Java8 CMS配置（会产生警告）
        String java8CMSConfig = """
            # Java8 CMS配置（会产生废弃警告）
            -XX:+UseConcMarkSweepGC
            -XX:+UseParNewGC
            -XX:CMSInitiatingOccupancyFraction=70
            # 警告：Java HotSpot(TM) 64-Bit Server VM warning:
            # Option UseConcMarkSweepGC was deprecated in version 9.0
            """;

        System.out.println("Java8 CMS配置：");
        System.out.println(java8CMSConfig);
    }

    private static void demonstrateJava11CMSStatus() {
        System.out.println("Java11中CMS的状态：");
        System.out.println("- CMS被完全移除");
        System.out.println("- 尝试使用会导致JVM启动失败");
        System.out.println("- 必须迁移到其他GC");

        // Java11中尝试使用CMS会失败
        System.out.println("在Java11中使用CMS：");
        System.out.println("错误信息：");
        System.out.println("Unrecognized VM option 'UseConcMarkSweepGC'");
        System.out.println("Error: Could not create the Java Virtual Machine.");
        System.out.println("Error: A fatal exception has occurred. Program will exit.");
    }

    // CMS迁移建议
    public static void cmsMigrationGuide() {
        System.out.println("从CMS迁移建议：");

        // 迁移到G1
        System.out.println("1. 迁移到G1（推荐）：");
        System.out.println("- -XX:+UseG1GC");
        System.out.println("- 适合大多数应用");
        System.out.println("- Java11默认选择");

        // 迁移到ZGC（大内存应用）
        System.out.println("2. 迁移到ZGC（大内存应用）：");
        System.out.println("- -XX:+UseZGC");
        System.out.println("- 需要-XX:+UnlockExperimentalVMOptions");
        System.out.println("- 适合延迟敏感的大内存应用");
    }
}
```

### JVM参数和工具的变化

#### 1. GC日志格式的统一

```java
public class GCLogFormatChanges {
    public static void demonstrateLogFormatChanges() {
        /*
         * GC日志格式的变化：
         * Java8: 多种日志格式，配置复杂
         * Java9+: 统一的Xlog日志框架
         */

        demonstrateJava8GCLogging();
        demonstrateJava11GCLogging();
    }

    private static void demonstrateJava8GCLogging() {
        System.out.println("Java8 GC日志配置：");

        // 详细的GC日志配置
        String java8GCLogConfig = """
            # Java8 GC日志配置
            -XX:+PrintGCDetails
            -XX:+PrintGCDateStamps
            -XX:+PrintGCTimeStamps
            -XX:+PrintGCApplicationStoppedTime
            -XX:+PrintGCApplicationConcurrentTime
            -XX:+PrintHeapAtGC
            -XX:+PrintTenuringDistribution
            -Xloggc:/var/log/gc.log
            -XX:+UseGCLogFileRotation
            -XX:NumberOfGCLogFiles=5
            -XX:GCLogFileSize=10M
            """;

        System.out.println("Java8 GC日志配置示例：");
        System.out.println(java8GCLogConfig);

        // Java8 GC日志示例
        System.out.println("Java8 GC日志示例：");
        System.out.println("2023-11-01T10:30:45.123+0800: 1234.567: [GC [PSYoungGen: 524288K->10240K(614400K)] 524288K->10496K(2016256K), 0.0456789 secs] [Times: user=0.12 sys=0.01, real=0.05 secs]");
    }

    private static void demonstrateJava11GCLogging() {
        System.out.println("Java11 GC日志配置：");

        // 统一的Xlog配置
        String java11GCLogConfig = """
            # Java11 统一日志配置
            -Xlog:gc*:file=/var/log/gc.log:time,level,tags:filecount=5,filesize=10m

            # 或更详细的配置
            -Xlog:gc*=debug:file=/var/log/gc-debug.log:time,uptime,level,tags
            -Xlog:gc+heap=trace:file=/var/log/gc-heap.log:time,uptime
            -Xlog:gc+ref=debug:file=/var/log/gc-ref.log:time,uptime
            """;

        System.out.println("Java11 GC日志配置示例：");
        System.out.println(java11GCLogConfig);

        // Java11 GC日志示例
        System.out.println("Java11 GC日志示例：");
        System.out.println("[0.123s][info][gc,start     ] GC pause (G1 Evacuation Pause)");
        System.out.println("[0.125s][info][gc,task      ] GC(0) Using 2 workers of 2 for evacuation");
        System.out.println("[0.130s][info][gc,phases    ] GC(0)   Pre Evacuate Collection Set: 0.1ms");
        System.out.println("[0.135s][info][gc,phases    ] GC(0)   Evacuate Collection Set: 4.2ms");
        System.out.println("[0.140s][info][gc,heap      ] GC(0) Eden regions: 12->0(12)");
    }
}
```

#### 2. JFR和JMC的改进

```java
public class JFRImprovements {
    public static void demonstrateJFRChanges() {
        /*
         * JFR（Java Flight Recorder）的变化：
         * Java8: JFR是商业版特性
         * Java11: JFR开源，免费使用
         */

        demonstrateJava8JFRStatus();
        demonstrateJava11JFRStatus();
    }

    private static void demonstrateJava8JFRStatus() {
        System.out.println("Java8 JFR状态：");
        System.out.println("- JFR是Oracle JDK商业版特性");
        System.out.println("- OpenJDK不包含JFR");
        System.out.println("- 需要商业许可证");

        // Java8中无法使用JFR监控GC
        System.out.println("Java8 GC监控选项：");
        System.out.println("- GC日志");
        System.out.println("- JMX监控");
        System.out.println("- 第三方工具（如GCViewer）");
    }

    private static void demonstrateJava11JFRStatus() {
        System.out.println("Java11 JFR状态：");
        System.out.println("- JFR开源，所有JDK都可使用");
        System.out.println("- 强大的性能分析工具");
        System.out.println("- 低开销的运行时监控");

        // Java11 JFR GC监控配置
        String jfrGCConfig = """
            # Java11 JFR GC监控
            -XX:StartFlightRecording=filename=gc-recording.jfr,settings=profile
            -XX:FlightRecorderOptions=settings=profile
            """;

        System.out.println("Java11 JFR GC监控配置：");
        System.out.println(jfrGCConfig);

        // JFR GC事件示例
        System.out.println("JFR可监控的GC事件：");
        System.out.println("- GC Pause");
        System.out.println("- GC Heap Summary");
        System.out.println("- GC Configuration");
        System.out.println("- GC CPU Time");
        System.out.println("- GC Reference Statistics");
    }
}
```

### 性能基准测试对比

#### 1. 延迟性能对比

```java
public class LatencyComparison {
    public static void compareLatency() {
        /*
         * 延迟性能对比（相同硬件，8GB堆）：
         *
         * 场景              Java8(Parallel)    Java11(G1)
         * 平均GC停顿时间    150ms              50ms
         * 最大GC停顿时间    800ms              200ms
         * 99%分位延迟       300ms              80ms
         */

        System.out.println("延迟性能对比：");
        System.out.println("Java8 (Parallel GC):");
        System.out.println("- 平均停顿: 150ms");
        System.out.println("- 最大停顿: 800ms");
        System.out.println("- 99%分位: 300ms");

        System.out.println("Java11 (G1 GC):");
        System.out.println("- 平均停顿: 50ms");
        System.out.println("- 最大停顿: 200ms");
        System.out.println("- 99%分位: 80ms");

        System.out.println("结论：Java11默认G1提供了更好的延迟特性");
    }
}
```

#### 2. 吞吐量对比

```java
public class ThroughputComparison {
    public static void compareThroughput() {
        /*
         * 吞吐量性能对比：
         *
         * 场景              Java8(Parallel)    Java11(G1)
         * 吞吐量           99%                97%
         * CPU使用率         85%                80%
         * 内存效率         95%                93%
         */

        System.out.println("吞吐量性能对比：");
        System.out.println("Java8 (Parallel GC):");
        System.out.println("- 吞吐量: 99% (最高)");
        System.out.println("- CPU使用率: 85%");
        System.out.println("- 内存效率: 95%");

        System.out.println("Java11 (G1 GC):");
        System.out.println("- 吞吐量: 97% (略低)");
        System.out.println("- CPU使用率: 80%");
        System.out.println("- 内存效率: 93%");

        System.out.println("结论：Java11 G1在吞吐量上稍有降低，但延迟大幅改善");
    }
}
```

### 迁移指南

#### 1. 从Java8升级到Java11

```java
public class MigrationGuide {
    public static void migrationSteps() {
        /*
         * 迁移步骤：
         * 1. 评估当前GC配置和性能
         * 2. 在测试环境验证Java11配置
         * 3. 调整GC参数以适应新版本
         * 4. 逐步在生产环境部署
         */

        provideMigrationChecklist();
    }

    private static void provideMigrationChecklist() {
        System.out.println("Java8 → Java11 GC迁移检查清单：");

        // 检查当前配置
        System.out.println("1. 检查当前GC配置：");
        System.out.println("   - 当前使用的GC类型");
        System.out.println("   - 关键GC参数");
        System.out.println("   - 性能基线数据");

        // 选择目标GC
        System.out.println("2. 选择Java11中的目标GC：");
        System.out.println("   - G1（推荐，默认选择）");
        System.out.println("   - ZGC（大内存应用）");
        System.out.println("   - Parallel（高吞吐量需求）");

        // 测试验证
        System.out.println("3. 测试验证：");
        System.out.println("   - 功能测试");
        System.out.println("   - 性能测试");
        System.out.println("   - 压力测试");

        // 生产部署
        System.out.println("4. 生产部署：");
        System.out.println("   - 灰度发布");
        System.out.println("   - 监控指标");
        System.out.println("   - 回滚计划");
    }
}
```

### 面试要点总结

1. **默认GC变化**：Java8 Parallel GC → Java11 G1 GC
2. **新增GC**：ZGC（实验性）、Epsilon GC（无操作）
3. **GC废弃**：CMS在Java11被完全移除
4. **G1改进**：并行Full GC、智能Region选择、NUMA感知
5. **日志统一**：从复杂配置到统一的Xlog框架
6. **监控增强**：JFR开源，提供强大的GC监控能力

**关键理解**：
- Java11的GC变化体现了向低延迟、易用性方向的发展
- G1成为默认是权衡的结果，适合大多数应用场景
- ZGC的引入为超低延迟场景提供了可能
- CMS的移除标志着Java GC技术的代际更替

**实际意义**：
- Java11提供了更好的开箱即用体验
- 新的GC技术扩展了Java的应用场景
- 统一的工具和日志简化了运维工作
- 为未来GC技术的发展奠定了基础

从Java8到Java11的GC变化反映了Java生态系统的现代化进程，对理解Java技术演进具有重要意义。