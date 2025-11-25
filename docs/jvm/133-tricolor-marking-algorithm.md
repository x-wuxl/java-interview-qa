---
layout: default
title: "什么是三色标记算法"
parent: JVM
nav_order: 133
description: "详细介绍三色标记算法的原理、实现、问题以及在现代垃圾收集器中的应用"
author: "wuxl"
date: 2025-11-01
---
## 问题

什么是三色标记算法？

## 答案

### 核心概念

**三色标记算法**是一种用于并发垃圾回收的标记算法，通过将对象标记为**白色**、**灰色**或**黑色**三种状态，实现垃圾回收线程与应用线程的并发执行，从而减少STW时间。

### 三色标记算法基础

#### 1. 三种颜色状态

```java
public class TricolorMarking {
    /*
     * 三色标记的三种状态：
     *
     * - 白色（White）：未被标记，可能为垃圾
     * - 灰色（Gray）：已标记但引用对象未完全标记
     * - 黑色（Black）：已标记且引用对象已完全标记
     */

    public enum ObjectColor {
        WHITE,  // 默认状态，未被访问
        GRAY,   // 已访问，但引用对象未全部访问
        BLACK   // 已访问，且引用对象全部访问
    }

    public class MarkedObject {
        private Object data;
        private ObjectColor color;
        private List<MarkedObject> references;

        public MarkedObject(Object data) {
            this.data = data;
            this.color = ObjectColor.WHITE; // 初始为白色
            this.references = new ArrayList<>();
        }

        // Getters and setters
        public ObjectColor getColor() { return color; }
        public void setColor(ObjectColor color) { this.color = color; }
        public List<MarkedObject> getReferences() { return references; }
    }
}
```

#### 2. 基本标记流程

```java
public class BasicMarkingProcess {
    private Queue<MarkedObject> grayQueue = new LinkedList<>();

    /*
     * 三色标记的基本流程：
     *
     * 1. 初始标记：将GC Roots直接引用的对象标记为灰色
     * 2. 并发标记：从灰色对象开始，标记引用对象
     * 3. 最终标记：处理并发标记期间的引用变化
     */

    public void tricolorMarking() {
        // 第1步：初始化，所有对象为白色
        initializeAllObjectsToWhite();

        // 第2步：初始标记，GC Roots引用的对象变为灰色
        initialMarking();

        // 第3步：并发标记，处理灰色队列
        concurrentMarking();

        // 第4步：最终标记，处理剩余灰色对象
        finalMarking();

        // 第5步：清理，白色对象被回收
        cleanupWhiteObjects();
    }

    private void initializeAllObjectsToWhite() {
        System.out.println("初始化：所有对象标记为白色");
        for (MarkedObject obj : getAllObjects()) {
            obj.setColor(ObjectColor.WHITE);
        }
    }

    private void initialMarking() {
        System.out.println("初始标记：GC Roots引用对象标记为灰色");

        // 扫描GC Roots
        Set<MarkedObject> gcRoots = findGCRoots();

        // 将GC Roots直接引用的对象标记为灰色
        for (MarkedObject root : gcRoots) {
            if (root.getColor() == ObjectColor.WHITE) {
                root.setColor(ObjectColor.GRAY);
                grayQueue.offer(root);
            }
        }
    }

    private Set<MarkedObject> findGCRoots() {
        Set<MarkedObject> roots = new HashSet<>();

        // 模拟GC Roots
        roots.add(getStaticVariableReference());
        roots.add(getStackLocalReference());
        roots.add(getJNIReference());

        return roots;
    }

    private void concurrentMarking() {
        System.out.println("���发标记：处理灰色对象队列");

        while (!grayQueue.isEmpty()) {
            MarkedObject grayObject = grayQueue.poll();

            // 处理灰色对象的所有引用
            for (MarkedObject ref : grayObject.getReferences()) {
                if (ref.getColor() == ObjectColor.WHITE) {
                    // 白色对象标记为灰色
                    ref.setColor(ObjectColor.GRAY);
                    grayQueue.offer(ref);
                }
            }

            // 当前对象处理完毕，标记为黑色
            grayObject.setColor(ObjectColor.BLACK);
        }
    }

    private void finalMarking() {
        System.out.println("最终标记：确保所有灰色对象被处理");

        // 处理并发标记期间可能遗漏的对象
        processConcurrentModifications();
    }

    private void cleanupWhiteObjects() {
        System.out.println("清理：回收白色对象");

        for (MarkedObject obj : getAllObjects()) {
            if (obj.getColor() == ObjectColor.WHITE) {
                // 回收白色对象
                reclaimObject(obj);
            }
        }
    }
}
```

### 并发标记的问题

#### 1. 对象消失问题

```java
public class ObjectLossProblem {
    /*
     * 对象消失问题（三色不变性破坏）：
     *
     * 当应用线程在并发标记过程中修改对象引用时，
     * 可能导致存活对象被错误标记为垃圾
     */

    public void demonstrateObjectLoss() {
        // 场景：对象消失问题
        MarkedObject objA = new MarkedObject("A");
        MarkedObject objB = new MarkedObject("B");

        // 初始状态：A 引用 B
        objA.getReferences().add(objB);

        // GC线程：A被标记为黑色，B仍为白色
        gcThreadMarking(objA, objB);

        // 应用线程：删除A对B的引用
        appThreadRemoveReference(objA, objB);

        // 结果：B变成白色且无引用，被误认为垃圾
        // 但实际上B可能被其他地方引用
    }

    private void gcThreadMarking(MarkedObject objA, MarkedObject objB) {
        // GC线程将A标记为黑色
        objA.setColor(ObjectColor.BLACK);

        // 如果此时应用线程删除A->B的引用
        // B就会变成白色且无引用
    }

    private void appThreadRemoveReference(MarkedObject objA, MarkedObject objB) {
        // 应用线程删除引用
        objA.getReferences().remove(objB);
    }

    /*
     * 对象消失问题的具体表现：
     *
     * 1. 黑色对象删除了对白色对象的引用
     * 2. 白色对象没有其他引用指向它
     * 3. 白色对象被错误回收
     * 4. 导致程序错误或崩溃
     */
}
```

#### 2. 并发修改处理策略

```java
public class ConcurrentModificationStrategies {
    /*
     * 解决并发修改问题的策略：
     *
     * 1. 写屏障（Write Barrier）
     * 2. 增量更新（Incremental Update）
     * 3. SATB（Snapshot-At-The-Beginning）
     */

    public class WriteBarrier {
        /*
         * 写屏障：在对象引用被修改时执行的额外操作
         */

        public void writeBarrier(MarkedObject obj, MarkedObject oldRef, MarkedObject newRef) {
            if (isConcurrentMarkingActive()) {
                // 策略1：增量更新
                incrementalUpdate(obj, newRef);

                // 策略2：SATB
                satbBarrier(oldRef);
            }
        }

        private void incrementalUpdate(MarkedObject obj, MarkedObject newRef) {
            /*
             * 增量更新策略：
             *
             * - 如果新引用指向白色对象，将白色对象标记为灰色
             * - 保证新引用的对象不会被遗漏
             */

            if (newRef != null && newRef.getColor() == ObjectColor.WHITE) {
                newRef.setColor(ObjectColor.GRAY);
                addToGrayQueue(newRef);
            }
        }

        private void satbBarrier(MarkedObject oldRef) {
            /*
             * SATB策略：
             *
             * - 记录被删除的引用
             * - 保证并发标记开始时的存活对象不会被回收
             */

            if (oldRef != null && oldRef.getColor() == ObjectColor.WHITE) {
                // 将被删除的白色对象标记为灰色
                oldRef.setColor(ObjectColor.GRAY);
                addToGrayQueue(oldRef);
            }
        }
    }
}
```

### 三色不变性

#### 1. 强三色不变性

```java
public class StrongTricolorInvariant {
    /*
     * 强三色不变性：
     *
     * "黑色对象不能直接引用白色对象"
     *
     * 如果满足这个不变性，就不会出现对象消失问题
     */

    public boolean checkStrongInvariant(MarkedObject blackObj, MarkedObject whiteRef) {
        // 强三色不变性检查
        if (blackObj.getColor() == ObjectColor.BLACK &&
            whiteRef.getColor() == ObjectColor.WHITE) {
            return false; // 违反强三色不变性
        }
        return true; // 满足强三色不变性
    }

    public void enforceStrongInvariant(MarkedObject obj, MarkedObject oldRef, MarkedObject newRef) {
        // 强制执行强三色不变性
        if (obj.getColor() == ObjectColor.BLACK && newRef != null) {
            if (newRef.getColor() == ObjectColor.WHITE) {
                // 将白色引用标记为灰色
                newRef.setColor(ObjectColor.GRAY);
                addToGrayQueue(newRef);
            }
        }
    }
}
```

#### 2. 弱三色不变性

```java
public class WeakTricolorInvariant {
    /*
     * 弱三色不变性：
     *
     * "黑色对象引用的白色对象必须通过灰色对象可达"
     *
     * 允许黑色对象引用白色对象，但白色对象必须能从灰色对象到达
     */

    private Set<MarkedObject> recordedReferences = new HashSet<>();

    public boolean checkWeakInvariant(MarkedObject blackObj, MarkedObject whiteRef) {
        // 弱三色不变性检查
        if (blackObj.getColor() == ObjectColor.BLACK &&
            whiteRef.getColor() == ObjectColor.WHITE) {

            // 检查白色对象是否从灰色对象可达
            return isReachableFromGray(whiteRef);
        }
        return true;
    }

    private boolean isReachableFromGray(MarkedObject whiteObj) {
        // 检查白色对象是否可以从灰色对象到达
        // 包括记录的引用
        return recordedReferences.contains(whiteObj);
    }

    public void enforceWeakInvariant(MarkedObject obj, MarkedObject oldRef, MarkedObject newRef) {
        // 执行弱三色不变性
        if (obj.getColor() == ObjectColor.BLACK && newRef != null) {
            if (newRef.getColor() == ObjectColor.WHITE) {
                // 记录这个引用，保证白色对象可达
                recordedReferences.add(newRef);
            }
        }
    }
}
```

### 实际应用：CMS和G1中的三色标记

#### 1. CMS中的三色标记

```java
public class CMSTricolorMarking {
    /*
     * CMS（Concurrent Mark Sweep）使用三色标记：
     *
     * - 初始标记（STW）：标记GC Roots直接引用的对象
     * - 并发标记：使用三色标记算法
     * - 重新标记（STW）：处理并发标记期间的修改
     * - 并发清除：回收垃圾对象
     */

    public void cmsMarkingProcess() {
        System.out.println("=== CMS 三色标记流程 ===");

        // 1. 初始标记（STW）
        initialMarkPhase();

        // 2. 并发标记
        concurrentMarkPhase();

        // 3. 预清理
        precleanPhase();

        // 4. 重新标记（STW）
        remarkPhase();

        // 5. 并发清除
        concurrentSweepPhase();
    }

    private void initialMarkPhase() {
        System.out.println("初始标记：标记GC Roots直接引用的对象");
        stopAllApplicationThreads();

        try {
            // 将GC Roots直接引用的对象标记为灰色
            Set<MarkedObject> roots = findGCRoots();
            for (MarkedObject root : roots) {
                if (root.getColor() == ObjectColor.WHITE) {
                    root.setColor(ObjectColor.GRAY);
                    addToGrayQueue(root);
                }
            }
        } finally {
            resumeAllApplicationThreads();
        }
    }

    private void concurrentMarkPhase() {
        System.out.println("并发标记：使用三色标记算法");
        startConcurrentMarking();
    }

    private void precleanPhase() {
        System.out.println("预清理：处理部分写屏障记录");
        processWriteBarrierBuffers();
    }

    private void remarkPhase() {
        System.out.println("重新标记：处理剩余的并发修改");
        stopAllApplicationThreads();

        try {
            // 处理所有写屏障记录的对象
            processAllWriteBarrierRecords();
        } finally {
            resumeAllApplicationThreads();
        }
    }

    private void concurrentSweepPhase() {
        System.out.println("并发清除：回收白色对象");
        reclaimWhiteObjects();
    }
}
```

#### 2. G1中的三色标记

```java
public class G1TricolorMarking {
    /*
     * G1（Garbage First）使用改进的三色标记：
     *
     * - 使用SATB策略保证不丢失对象
     * - 分区域并发标记
     * - 支持混合回收
     */

    public void g1MarkingProcess() {
        System.out.println("=== G1 三色标记流程 ===");

        // 1. 并发标记周期
        concurrentMarkingCycle();

        // 2. 混合回收
        mixedGCPause();
    }

    private void concurrentMarkingCycle() {
        // 阶段1：并发标记
        concurrentMarking();

        // 阶段2：重新标记
        finalMarking();

        // 阶段3：筛选回收
        cleanup();
    }

    private void concurrentMarking() {
        System.out.println("G1 并发标记：使用SATB三色标记");

        // SATB（Snapshot-At-The-Beginning）策略
        // 在并发标记开始时记录所有存活对象的快照
        satbInitialSnapshot();

        // 处理标记任务
        processMarkingTasks();
    }

    private void satbInitialSnapshot() {
        System.out.println("SATB 初始快照：记录存活对象");

        // SATB 写屏障
        // 当对象引用被删除时，将被删除的对象标记为灰色
        setupSATBWriteBarrier();
    }

    private void setupSATBWriteBarrier() {
        /*
         * SATB 写屏障的实现：
         *
         * public void preWriteBarrier(Object oldRef) {
         *     if (oldRef != null && isConcurrentMarking()) {
         *         markObject(oldRef); // 将被删除的对象标记
         *     }
         * }
         */

        System.out.println("设置 SATB 写屏障");
    }

    private void finalMarking() {
        System.out.println("G1 重新标记：处理SATB缓冲区");

        // 处理SATB缓冲区中的对象
        processSATBBuffers();

        // 确保所有灰色对象被处理
        processGrayObjects();
    }

    private void cleanup() {
        System.out.println("G1 筛选回收：选择回收区域");

        // 计算每个区域的回收价值
        calculateRegionReclaimability();

        // 构建混合回收计划
        buildMixedGCPlan();
    }
}
```

### 三色标记的性能优化

#### 1. 并行化标记

```java
public class ParallelMarkingOptimization {
    /*
     * 并行化三色标记：
     *
     * - 使用多个标记线程
     * - 工作窃取算法
     * - 动态负载均衡
     */

    private int markingThreadCount = Runtime.getRuntime().availableProcessors();
    private ExecutorService markingExecutor =
        Executors.newFixedThreadPool(markingThreadCount);

    public void parallelMarking() {
        System.out.println("并行三色标记：使用 " + markingThreadCount + " 个线程");

        // 将灰色队列分割为多个工作队列
        List<Queue<MarkedObject>> workQueues = splitGrayQueue(markingThreadCount);

        // 启动并行标记任务
        List<Future<?>> futures = new ArrayList<>();
        for (int i = 0; i < markingThreadCount; i++) {
            Queue<MarkedObject> queue = workQueues.get(i);
            Future<?> future = markingExecutor.submit(
                new MarkingTask(queue, workQueues));
            futures.add(future);
        }

        // 等待所有标记任务完成
        waitForCompletion(futures);
    }

    private class MarkingTask implements Runnable {
        private Queue<MarkedObject> localQueue;
        private List<Queue<MarkedObject>> allQueues;

        public MarkingTask(Queue<MarkedObject> localQueue,
                          List<Queue<MarkedObject>> allQueues) {
            this.localQueue = localQueue;
            this.allQueues = allQueues;
        }

        @Override
        public void run() {
            while (true) {
                MarkedObject obj = localQueue.poll();
                if (obj == null) {
                    // 尝试从其他队列窃取工作
                    obj = stealWork();
                    if (obj == null) {
                        break; // 没有工作可做
                    }
                }

                processGrayObject(obj);
            }
        }

        private MarkedObject stealWork() {
            // 工作窃取算法
            for (Queue<MarkedObject> queue : allQueues) {
                if (queue != localQueue && !queue.isEmpty()) {
                    return queue.poll();
                }
            }
            return null;
        }

        private void processGrayObject(MarkedObject grayObj) {
            // 处理灰色对象的所有引用
            for (MarkedObject ref : grayObj.getReferences()) {
                if (ref.getColor() == ObjectColor.WHITE) {
                    ref.setColor(ObjectColor.GRAY);
                    localQueue.offer(ref);
                }
            }

            // 标记为黑色
            grayObj.setColor(ObjectColor.BLACK);
        }
    }
}
```

#### 2. 增量标记

```java
public class IncrementalMarkingOptimization {
    /*
     * 增量标记：
     *
     * - 将标记工作分解为小步骤
     * - 与应用线程交替执行
     * - 减少单次STW时间
     */

    private boolean incrementalMarkingActive = false;
    private int maxStepsPerCycle = 1000;

    public void incrementalMarking() {
        System.out.println("增量标记：分步骤执行标记");

        incrementalMarkingActive = true;

        while (hasGrayObjects()) {
            // 执行一小批标记工作
            executeMarkingSteps(maxStepsPerCycle);

            // 让应用线程有机会执行
            yieldToApplication();
        }

        incrementalMarkingActive = false;
    }

    private void executeMarkingSteps(int maxSteps) {
        for (int i = 0; i < maxSteps && hasGrayObjects(); i++) {
            MarkedObject grayObj = getNextGrayObject();
            if (grayObj != null) {
                processGrayObject(grayObj);
            }
        }
    }

    private void yieldToApplication() {
        // 让应用线程执行
        Thread.yield();
    }

    public void writeBarrierForIncremental(MarkedObject obj, MarkedObject oldRef, MarkedObject newRef) {
        if (incrementalMarkingActive) {
            // 在增量标记期间，记录引用变化
            recordReferenceChange(obj, oldRef, newRef);
        }
    }
}
```

### 三色标记的问题诊断

#### 1. 常见问题分析

```java
public class TricolorMarkingDiagnostics {
    /*
     * 三色标记常见问题诊断：
     *
     * 1. 标记遗漏
     * 2. 对象消失
     * 3. 内存泄漏
     * 4. 性能问题
     */

    public void diagnoseMarkingIssues() {
        // 问题1：标记遗漏诊断
        diagnoseMissingMarks();

        // 问题2：对象消失诊断
        diagnoseObjectLoss();

        // 问题3：性能问题诊断
        diagnosePerformanceIssues();
    }

    private void diagnoseMissingMarks() {
        System.out.println("标记遗漏诊断：");

        // 检查灰色队列是否为空但还有白色对象
        if (grayQueue.isEmpty() && hasWhiteObjects()) {
            System.out.println("警告：可能存在标记遗漏");

            // 分析可能原因
            System.out.println("可能原因：");
            System.out.println("1. 写屏障未正确处理");
            System.out.println("2. 并发修改未记录");
            System.out.println("3. 三色不变性被破坏");
        }
    }

    private void diagnoseObjectLoss() {
        System.out.println("对象消失诊断：");

        // 检查是否有黑色对象引用白色对象
        for (MarkedObject blackObj : getBlackObjects()) {
            for (MarkedObject ref : blackObj.getReferences()) {
                if (ref.getColor() == ObjectColor.WHITE) {
                    System.out.println("警告：黑色对象引用白色对象");
                    System.out.println("可能导致对象消失问题");
                }
            }
        }
    }

    private void diagnosePerformanceIssues() {
        System.out.println("性能问题诊断：");

        // 统计各种颜色对象的数量
        int whiteCount = countObjectsByColor(ObjectColor.WHITE);
        int grayCount = countObjectsByColor(ObjectColor.GRAY);
        int blackCount = countObjectsByColor(ObjectColor.BLACK);

        System.out.println("白色对象数量: " + whiteCount);
        System.out.println("灰色对象数量: " + grayCount);
        System.out.println("黑色对象数量: " + blackCount);

        // 分析性能指标
        if (grayCount > 0) {
            System.out.println("警告：仍有灰色对象未处理");
        }

        if (whiteCount > blackCount * 2) {
            System.out.println("警告：垃圾对象比例过高");
        }
    }
}
```

### 答题总结

**三色标记算法概念：**
- 一种并发垃圾回收的标记算法
- 将对象分为白色（未标记）、灰色（已标记但引用未全处理）、黑色（已完全标记）三种状态
- 支持GC线程与应用线程并发执行，减少STW时间

**基本流程：**
1. **初始化**：所有对象标记为白色
2. **初始标记**：GC Roots直接引用的对象标记为灰色
3. **并发标记**：从灰色对象开始，处理引用关系
4. **最终标记**：处理并发标记期间的引用变化
5. **清理**：回收白色对象

**并发标记问题：**
- **对象消失问题**：黑色对象删除白色对象引用，导致白色对象被错误回收
- **并发修改**：应用线程在标记过程中修改对象引用
- **三色不变性**：需要保证强/弱三色不变性来避免问题

**解决方案：**
- **写屏障**：在对象引用修改时执行额外操作
- **增量更新**：记录新增的引用关系
- **SATB**：保存并发标记开始时的对象快照

**实际应用：**
- **CMS**：使用三色标记 + 增量更新
- **G1**：使用三色标记 + SATB策略
- **现代GC**：都基于三色标记算法进行改进

**性能优化：**
- **并行标记**：多线程并行处理灰色对象
- **增量标记**：分步骤执行，减少单次停顿
- **工作窃取**：动态负载均衡

**关键优势：**
- 支持并发标记，减少STW时间
- 提高垃圾回收效率
- 适用于大内存、低延迟场景

三色标记算法是现代并发垃圾收集器的核心技术，通过巧妙的颜色状态管理实现了高效的并发回收。