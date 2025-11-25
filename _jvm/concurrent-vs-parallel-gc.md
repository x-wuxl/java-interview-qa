---
title: "说一说JVM的并发回收和并行回收"
date: 2025-11-01
description: "深入解析JVM中并发回收和并行回收的概念、区别和实现机制"
author: "wuxl"
categories: [JVM]
tags: [JVM, 垃圾回收, 并发回收, 并行回收, CMS, G1, 性能优化]
nav_order: 144
parent: JVM
---
## 问题

说一说JVM的并发回收和并行回收

## 答案

### 核心概念

**并发回收（Concurrent Collection）**和**并行回收（Parallel Collection）**是JVM垃圾回收的两种不同执行模式。**并行回收**指多个GC线程同时工作，但会暂停应用线程；**并发回收**指GC线程与应用线程同时工作，最大程度减少停顿时间。

### 并行回收（Parallel Collection）

#### 1. 基本概念

```java
public class ParallelCollection {
    public static void demonstrateParallelCollection() {
        /*
         * 并行回收特点：
         * 1. 多个GC线程同时工作
         * 2. 应用线程被暂停（STW - Stop-The-World）
         * 3. 充分利用多核CPU资源
         * 4. 目标：高吞吐量
         */

        System.out.println("并行回收特点：");
        System.out.println("- 多线程并行执行");
        System.out.println("- STW期间应用完全暂停");
        System.out.println("- 利用多核CPU提升效率");
        System.out.println("- 目标：最大化吞吐量");
    }

    // 并行回收工作模式
    public static void parallelWorkflow() {
        System.out.println("\n并行回收工作流程：");

        // 时间轴示意
        System.out.println("应用运行  [████████████]");
        System.out.println("STW开始   [         ]");
        System.out.println("GC线程1   [    GGG   ]");
        System.out.println("GC线程2   [    GGG   ]");
        System.out.println("GC线程3   [    GGG   ]");
        System.out.println("STW结束   [         ]");
        System.out.println("应用继续  [████████████]");

        System.out.println("\n特点：多个GC线程并行工作，但应用必须等待");
    }
}
```

#### 2. 并行回收器实现

```java
public class ParallelCollectors {
    public static void demonstrateParallelCollectors() {
        /*
         * 并行回收器类型：
         * 1. Parallel Scavenge：新生代并行回收
         * 2. Parallel Old：老年代并行回收
         * 3. Parallel GC：Parallel Scavenge + Parallel Old组合
         */

        demonstrateParallelScavenge();
        demonstrateParallelOld();
    }

    private static void demonstrateParallelScavenge() {
        System.out.println("1. Parallel Scavenge回收器：");
        System.out.println("目标：新生代并行回收");
        System.out.println("算法：复制算法");
        System.out.println("特点：多线程并行复制");
        System.out.println("适用：吞吐量优先的应用");

        // 配置示例
        String config = """
            # Parallel Scavenge配置
            -XX:+UseParallelGC                 # 启用Parallel GC组合
            -XX:ParallelGCThreads=4            # GC线程数
            -XX:MaxGCPauseMillis=200           # 最大停顿时间
            -XX:GCTimeRatio=99                 # 吞吐量目标
            """;

        System.out.println("配置示例：");
        System.out.println(config);
    }

    private static void demonstrateParallelOld() {
        System.out.println("\n2. Parallel Old回收器：");
        System.out.println("目标：老年代并行回收");
        System.out.println("算法：标记-整理算法");
        System.out.println("特点：多线程并行整理");
        System.out.println("适用：后台计算、批处理");

        // 工作流程
        System.out.println("\nParallel Old工作流程：");
        System.out.println("1. STW：暂停所有应用线程");
        System.out.println("2. 标记：多线程并行标记存活对象");
        System.out.println("3. 整理：多线程并行移动对象");
        System.out.println("4. 清理：多线程并行清理空间");
        System.out.println("5. 恢复：应用线程继续运行");
    }

    // 性能特点分析
    public static void analyzeParallelPerformance() {
        System.out.println("\n并行回收性能特点：");

        // 吞吐量优势
        System.out.println("吞吐量优势：");
        System.out.println("- 多核并行，回收效率高");
        System.out.println("- 单位时间内处理更多垃圾");
        System.out.println("- 适合计算密集型应用");

        // 延迟劣势
        System.out.println("延迟劣势：");
        System.out.println("- STW时间较长");
        System.out.println("- 应用响应时间受影响");
        System.out.println("- 不适合响应敏感场景");

        // 资源使用
        System.out.println("资源使用特点：");
        System.out.println("- CPU使用率高");
        System.out.println("- 内存占用适中");
        System.out.println("- 线程切换开销");
    }
}
```

### 并发回收（Concurrent Collection）

#### 1. 基本概念

```java
public class ConcurrentCollection {
    public static void demonstrateConcurrentCollection() {
        /*
         * 并发回收特点：
         * 1. GC线程与应用线程同时运行
         * 2. 最大化减少STW时间
         * 3. 部分工作需要短暂STW
         * 4. 目标：低延迟
         */

        System.out.println("并发回收特点：");
        System.out.println("- GC与应用并发执行");
        System.out.println("- 最小化STW时间");
        System.out.println("- 复杂的协调机制");
        System.out.println("- 目标：最小化延迟");
    }

    // 并发回收工作模式
    public static void concurrentWorkflow() {
        System.out.println("\n并发回收工作流程：");

        // 时间轴示意（以CMS为例）
        System.out.println("应用运行  [████████████████████]");
        System.out.println("STW1      [     ░░░     ]");
        System.out.println("并发标记  [   ░░░░░░░░░░░░░   ]");
        System.out.println("STW2      [     ░░░     ]");
        System.out.println("并发清除  [   ░░░░░░░░░░░░░   ]");
        System.out.println("应用继续  [████████████████████]");

        System.out.println("\n特点：大部分GC工作与应用并发，STW时间很短");
    }
}
```

#### 2. 并发回收器实现

```java
public class ConcurrentCollectors {
    public static void demonstrateConcurrentCollectors() {
        /*
         * 并发回收器类型：
         * 1. CMS（Concurrent Mark Sweep）：并发标记清除
         * 2. G1：部分阶段并发
         * 3. ZGC：几乎全并发
         */

        demonstrateCMS();
        demonstrateG1();
        demonstrateZGC();
    }

    private static void demonstrateCMS() {
        System.out.println("1. CMS（Concurrent Mark Sweep）回收器：");
        System.out.println("目标：老年代并发回收");
        System.out.println("算法：并发标记清除");

        // CMS工作阶段
        System.out.println("\nCMS工作阶段：");
        System.out.println("1. 初始标记（STW）：标记GC Roots直接对象");
        System.out.println("2. 并发标记：与应用并发，标记存活对象");
        System.out.println("3. 重新标记（STW）：处理并发期间的引用变化");
        System.out.println("4. 并发清除：与应用并发，回收垃圾对象");

        // 配置示例
        String config = """
            # CMS配置
            -XX:+UseConcMarkSweepGC           # 启用CMS
            -XX:+UseParNewGC                  # 新生代ParNew
            -XX:CMSInitiatingOccupancyFraction=70
            -XX:+CMSParallelRemarkEnabled     # 并行重新标记
            """;

        System.out.println("配置示例：");
        System.out.println(config);
    }

    private static void demonstrateG1() {
        System.out.println("\n2. G1回收器：");
        System.out.println("目标：平衡并发和并行");
        System.out.println("算法：Region化并发回收");

        // G1并发阶段
        System.out.println("\nG1并发阶段：");
        System.out.println("1. 初始标记（STW）：短暂，与Young GC合并");
        System.out.println("2. 并发标记：与应用并发，建立Region存活信息");
        System.out.println("3. 最终标记（STW）：短暂，完成标记");
        System.out.println("4. 筛选回收（STW）：选择Region并回收");

        System.out.println("特点：部分阶段并发，平衡延迟和吞吐量");
    }

    private static void demonstrateZGC() {
        System.out.println("\n3. ZGC回收器：");
        System.out.println("目标：全并发，超低延迟");
        System.out.println("算法：基于着色指针的并发回收");

        // ZGC并发阶段
        System.out.println("\nZGC并发阶段：");
        System.out.println("1. 暂停标记（STW）：极短，标记GC Roots");
        System.out.println("2. 并发标记：与应用并发，遍历对象图");
        System.out.println("3. 暂停标记结束（STW）：极短，处理完成");
        System.out.println("4. 并发预备重映射：选择回收Region");
        System.out.println("5. 并发重映射：移动对象到新位置");

        System.out.println("特点：几乎全并发，停顿时间<1ms");
    }
}
```

### 对比分析

#### 1. 执行模式对比

```java
public class ExecutionModeComparison {
    public static void compareExecutionModes() {
        /*
         * 执行模式对比：
         *
         * 维度          并行回收          并发回收
         * 线程执行       GC线程并行        GC与应用并发
         * 应用状态       完全暂停          部分暂停
         * STW时间        长               短
         * 吞吐量         高               中
         * 延迟           差               好
         * 复杂度         低               高
         * CPU使用        期间很高          持续中等
         */

        printComparisonTable();
    }

    private static void printComparisonTable() {
        System.out.println("执行模式对比表：");
        System.out.println("┌─────────────┬──────────────┬──────────────┐");
        System.out.println("│ 维度         │ 并行回收      │ 并发回收      │");
        System.out.println("├─────────────┼──────────────┼──────────────┤");
        System.out.println("│ 线程执行     │ GC线程并行    │ GC与应用并发  │");
        System.out.println("│ 应用状态     │ 完全暂停      │ 部分暂停      │");
        System.out.println("│ STW时间      │ 长            │ 短            │");
        System.out.println("│ 吞吐量       │ 高            │ 中            │");
        System.out.println("│ 延迟         │ 差            │ 好            │");
        System.out.println("│ 复杂度       │ 低            │ 高            │");
        System.out.println("│ CPU使用      │ 期间很高      │ 持续中等      │");
        System.out.println("└─────────────┴──────────────┴──────────────┘");

        // 详细对比说明
        System.out.println("\n详细对比：");

        // STW时间
        System.out.println("1. STW时间：");
        System.out.println("- 并行：整个回收过程都是STW");
        System.out.println("- 并发：只有少数阶段需要STW");

        // 吞吐量 vs 延迟
        System.out.println("2. 吞吐量 vs 延迟：");
        System.out.println("- 并行：高吞吐量，但延迟差");
        System.out.println("- 并发：低延迟，但吞吐量稍低");

        // 资源使用
        System.out.println("3. 资源使用：");
        System.out.println("- 并行：STW期间CPU使用率100%");
        System.out.println("- 并发：持续占用部分CPU资源");
    }
}
```

#### 2. 适用场景对比

```java
public class UseCaseComparison {
    public static void compareUseCases() {
        System.out.println("适用场景对比：");

        // 并行回收适用场景
        demonstrateParallelUseCases();

        // 并发回收适用场景
        demonstrateConcurrentUseCases();
    }

    private static void demonstrateParallelUseCases() {
        System.out.println("1. 并行回收适用场景：");

        // 批处理应用
        System.out.println("- 批处理应用：");
        System.out.println("  * 特点：允许较长停顿");
        System.out.println("  * 需求：高吞吐量");
        System.out.println("  * 示例：数据分析、报表生成");

        // 后台服务
        System.out.println("- 后台服务：");
        System.out.println("  * 特点：用户不直接交互");
        System.out.println("  * 需求：处理能力强");
        System.out.println("  * 示例：定时任务、消息处理");

        // 科学计算
        System.out.println("- 科学计算：");
        System.out.println("  * 特点：计算密集型");
        System.out.println("  * 需求：充分利用CPU");
        System.out.println("  * 示例：模拟运算、机器学习训练");
    }

    private static void demonstrateConcurrentUseCases() {
        System.out.println("\n2. 并发回收适用场景：");

        // Web应用
        System.out.println("- Web应用：");
        System.out.println("  * 特点：用户直接交互");
        System.out.println("  * 需求：响应时间短");
        System.out.println("  * 示例：电商网站、在线服务");

        // 实时系统
        System.out.println("- 实时系统：");
        System.out.println("  * 特点：严格的延迟要求");
        System.out.println("  * 需求：低延迟、高可用");
        System.out.println("  * 示例：交易系统、游戏服务器");

        // 微服务
        System.out.println("- 微服务：");
        System.out.println("  * 特点：快速响应要求");
        System.out.println("  * 需求：稳定的服务质量");
        System.out.println("  * 示例：API服务、用户服务");
    }
}
```

### 技术实现细节

#### 1. 并行回收实现机制

```java
public class ParallelImplementation {
    public static void demonstrateParallelMechanism() {
        /*
         * 并行回收实现机制：
         * 1. 工作窃取（Work Stealing）
         * 2. 任务分片（Task Partitioning）
         * 3. 同步协调（Synchronization）
         * 4. 负载均衡（Load Balancing）
         */

        demonstrateWorkStealing();
        demonstrateTaskPartitioning();
    }

    private static void demonstrateWorkStealing() {
        System.out.println("1. 工作窃取机制：");
        System.out.println("- 每个GC线程有自己的任务队列");
        System.out.println("- 完成自己任务后，窃取其他线程的任务");
        System.out.println("- 实现负载均衡，避免线程空闲");

        // 伪代码示例
        String workStealingCode = """
            // 工作窃取伪代码
            while (hasWork()) {
                Task task = getLocalTask();
                if (task == null) {
                    task = stealTaskFromOtherThread();
                }
                if (task != null) {
                    processTask(task);
                }
            }
            """;

        System.out.println("实现示例：");
        System.out.println(workStealingCode);
    }

    private static void demonstrateTaskPartitioning() {
        System.out.println("\n2. 任务分片机制：");
        System.out.println("- 将大任务分解为小任务");
        System.out.println("- 按内存区域或对象数量分片");
        System.out.println("- 提高并行度和效率");

        // 分片策略示例
        System.out.println("分片策略：");
        System.out.println("- 按Region分片（G1）");
        System.out.println("- 按内存块分片（Parallel）");
        System.out.println("- 按对象数量分片（CMS）");
    }
}
```

#### 2. 并发回收实现机制

```java
public class ConcurrentImplementation {
    public static void demonstrateConcurrentMechanism() {
        /*
         * 并发回收实现机制：
         * 1. 三色标记算法
         * 2. 写屏障（Write Barrier）
         * 3. 卡表（Card Table）
         * 4. 增量处理（Incremental Processing）
         */

        demonstrateTriColorMarking();
        demonstrateWriteBarrier();
    }

    private static void demonstrateTriColorMarking() {
        System.out.println("1. 三色标记算法：");
        System.out.println("- 白色：未标记对象（可能垃圾）");
        System.out.println("- 灰色：已标记，但引用对象未完全标记");
        System.out.println("- 黑色：已标记，引用对象也已标记");

        // 标记过程
        System.out.println("\n标记过程：");
        System.out.println("1. 初始：所有对象为白色");
        System.out.println("2. 标记：GC Roots转为灰色");
        System.out.println("3. 遍历：灰色对象转为黑色，引用对象转为灰色");
        System.out.println("4. 完成：灰色对象为空，白色为垃圾");

        // 并发标记挑战
        System.out.println("\n并发标记挑战：");
        System.out.println("- 应用线程可能修改引用关系");
        System.out.println("- 需要机制处理并发修改");
        System.out.println("- 解决方案：写屏障 + 增量标记");
    }

    private static void demonstrateWriteBarrier() {
        System.out.println("\n2. 写屏障机制：");
        System.out.println("- 拦截对象的引用写操作");
        System.out.println("- 记录引用关系变化");
        System.out.println("- 保证并发标记的正确性");

        // 写屏障伪代码
        String writeBarrierCode = """
            // 写屏障伪代码
            void writeBarrier(Object field, Object newValue) {
                // 1. 执行原始写操作
                field = newValue;

                // 2. 检查是否需要额外处理
                if (isConcurrentMarkingPhase() &&
                    isInterestingReference(field, newValue)) {
                    // 3. 记录引用变化
                    recordReferenceChange(field, newValue);

                    // 4. 可能需要重新标记
                    if (newValue != null && isWhite(newValue)) {
                        markGray(newValue);
                    }
                }
            }
            """;

        System.out.println("实现示例：");
        System.out.println(writeBarrierCode);
    }

    private static void demonstrateCardTable() {
        System.out.println("\n3. 卡表机制：");
        System.out.println("- 将堆划分为固定大小的卡片（通常512字节）");
        System.out.println("- 记录卡片内是否有对象引用变化");
        System.out.println("- 并发标记时只扫描脏卡片");

        // 卡表示例
        System.out.println("卡表工作原理：");
        System.out.println("- 堆内存：| Card0 | Card1 | Card2 | Card3 | ...");
        System.out.println("- 卡表：  [  0  ] [  1  ] [  0  ] [  1  ]");
        System.out.println("- 含义：Card0干净，Card1脏，Card2干净，Card3脏");
    }
}
```

### 性能调优策略

#### 1. 并行回收调优

```java
public class ParallelTuning {
    public static void tuneParallelGC() {
        /*
         * 并行回收调优策略：
         * 1. 调整GC线程数
         * 2. 设置停顿时间目标
         * 3. 优化吞吐量目标
         * 4. 平衡新生代和老年代
         */

        provideParallelTuningGuidelines();
    }

    private static void provideParallelTuningGuidelines() {
        System.out.println("并行回收调优指南：");

        // 线程数调优
        System.out.println("1. GC线程数调优：");
        String threadTuning = """
            # GC线程数配置
            -XX:ParallelGCThreads=8           # 设置GC线程数
            -XX:ConcGCThreads=4               # 并发GC线程数（CMS）

            # 线程数建议：
            # - CPU核心数 <= 8：GC线程数 = CPU核心数
            # - CPU核心数 > 8：GC线程数 = 8 + (CPU核心数 - 8) * 5/8
            """;

        System.out.println(threadTuning);

        // 停顿时间调优
        System.out.println("2. 停顿时间调优：");
        String pauseTuning = """
            # 停顿时间配置
            -XX:MaxGCPauseMillis=200         # 最大停顿时间目标
            -XX:GCPauseIntervalMillis=0      # 停顿间隔（0=自动）

            # 注意：Parallel GC中这只是软目标，可能无法保证
            """;

        System.out.println(pauseTuning);

        // 吞吐量调优
        System.out.println("3. 吞吐量调优：");
        String throughputTuning = """
            # 吞吐量配置
            -XX:GCTimeRatio=99               # 吞吐量目标
            # 含义：GC时间占总时间的 (1/99) ≈ 1%

            -XX:+UseAdaptiveSizePolicy       # 自适应大小调整
            """;

        System.out.println(throughputTuning);
    }
}
```

#### 2. 并发回收调优

```java
public class ConcurrentTuning {
    public static void tuneConcurrentGC() {
        /*
         * 并发回收调优策略：
         * 1. 调整触发阈值
         * 2. 优化并发线程数
         * 3. 平衡并发阶段
         * 4. 处理并发失败
         */

        provideConcurrentTuningGuidelines();
    }

    private static void provideConcurrentTuningGuidelines() {
        System.out.println("并发回收调优指南：");

        // 触发阈值调优
        System.out.println("1. 触发阈值调优：");
        String thresholdTuning = """
            # CMS触发阈值
            -XX:CMSInitiatingOccupancyFraction=70    # 老年代使用70%时触发
            -XX:+UseCMSInitiatingOccupancyOnly       # 严格按阈值触发

            # G1触发阈值
            -XX:InitiatingHeapOccupancyPercent=45   # 堆使用45%时触发并发标记
            -XX:+G1UseAdaptiveIHOP                   # 自适应阈值调整
            """;

        System.out.println(thresholdTuning);

        // 并发线程调优
        System.out.println("2. 并发线程调优：");
        String concurrentTuning = """
            # 并发线程数配置
            -XX:ParallelGCThreads=8          # 并行GC线程数
            -XX:ConcGCThreads=4              # 并发GC线程数

            # 建议值：
            # - ConcGCThreads = ParallelGCThreads / 4
            # - 留出CPU资源给应用线程
            """;

        System.out.println(concurrentTuning);

        // 并发失败处理
        System.out.println("3. 并发失败处理：");
        String failureHandling = """
            # CMS并发失败处理
            -XX:CMSMaxAbortablePrecleanTime=5000     # 最大预清理时间
            -XX:+CMSClassUnloadingEnabled            # 并发类卸载
            -XX:+CMSParallelRemarkEnabled            # 并行重新标记

            # G1并发失败处理
            -XX:G1ReservePercent=10                  # 预留空间百分比
            -XX:G1MixedGCCountTarget=8               # Mixed GC目标次数
            """;

        System.out.println(failureHandling);
    }
}
```

### 面试要点总结

1. **核心区别**：并行回收是多线程并行但STW，并发回收是GC与应用并发执行
2. **执行模式**：并行关注吞吐量，并发关注延迟
3. **技术实现**：并行用工作窃取和任务分片，并发用三色标记和写屏障
4. **适用场景**：并行适合批处理，并发适合Web应用和实时系统
5. **性能特征**：并行吞吐量高但延迟差，并发延迟好但吞吐量稍低
6. **调优策略**：并行调优线程数和吞吐量，并发调优触发阈值和并发线程

**关键理解**：
- 并行和并发不是互斥的，现代GC通常结合两者
- 并行回收简单高效，适合吞吐量优先的场景
- 并发回收复杂但延迟友好，适合响应敏感的场景
- 选择哪种模式取决于应用的具体需求

**实际意义**：
- 理解并行并发的差异有助于选择合适的GC
- 掌握调优策略可以优化GC性能
- 了解实现机制有助于问题诊断
- 这两个概念是理解现代GC的基础

并行回收和并发回收代表了垃圾回收的两种不同设计哲学，理解它们的差异对于掌握JVM垃圾回收机制至关重要。