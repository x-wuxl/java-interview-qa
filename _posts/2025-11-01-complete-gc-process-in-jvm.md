---
layout: post
title: "JVM中一次完整的GC流程是怎样的"
date: 2025-11-01
description: "详细介绍Java虚拟机中垃圾回收的完整流程，包括Young GC和Full GC的详细步骤和执行过程"
author: "wuxl"
categories: [JVM]
tags: [JVM, 垃圾回收, GC流程, YoungGC, FullGC, 垃圾收集]
---

## 问题

JVM中一次完整的GC流程是怎样的？

## 答案

### 核心概念

JVM的垃圾回收流程是一个复杂的过程，涉及**对象标记**、**内存回收**和**引用更新**等多个步骤。完整的GC流程包括 Young GC（新生代回收）和 Full GC（整堆回收）两种主要类型。

### Young GC 流程详解

#### 1. Young GC 触发时机

```java
public class YoungGCTrigger {
    /*
     * Young GC 触发条件：
     * 1. Eden区空间不足，新对象无法分配
     * 2. TLAB（Thread Local Allocation Buffer）分配失败
     */

    private Space edenSpace;

    public Object allocate(int size) {
        if (edenSpace.getRemaining() < size) {
            // Eden区空间不足，触发Young GC
            triggerYoungGC();
        }
        return edenSpace.allocate(size);
    }

    private void triggerYoungGC() {
        System.out.println("触发Young GC");
        youngGC();
    }
}
```

#### 2. Young GC 详细流程

```java
public class YoungGCProcess {
    private Space eden;
    private Space survivorFrom;
    private Space survivorTo;

    public void youngGC() {
        // 第1步：GC Root扫描（STW开始）
        long startTime = System.currentTimeMillis();
        stopAllApplicationThreads(); // Stop-The-World

        try {
            // 第2步：标记阶段
            markYoungGenObjects();

            // 第3步：复制阶段
            copyObjectsToSurvivor();

            // 第4步：晋升阶段
            promoteObjects();

            // 第5步：清理阶段
            cleanYoungGen();

        } finally {
            // 第6步：恢复应用线程（STW结束）
            resumeAllApplicationThreads();
            long endTime = System.currentTimeMillis();
            System.out.println("Young GC完成，耗时: " + (endTime - startTime) + "ms");
        }
    }

    private void markYoungGenObjects() {
        System.out.println("第2步：标记存活对象");

        // 2.1 扫描GC Roots
        Set<Object> gcRoots = findGCRoots();

        // 2.2 从GC Roots开始标记可达对象
        Set<Object> workList = new HashSet<>(gcRoots);
        Set<Object> markedObjects = new HashSet<>();

        while (!workList.isEmpty()) {
            Object obj = workList.iterator().next();
            workList.remove(obj);

            if (isInYoungGeneration(obj) && !markedObjects.contains(obj)) {
                markedObjects.add(obj);
                // 添加对象引用的其他对象到工作列表
                workList.addAll(obj.getReferences());
            }
        }

        // 标记对象
        for (Object obj : markedObjects) {
            obj.setMarked(true);
        }
    }

    private void copyObjectsToSurvivor() {
        System.out.println("第3步：复制存活对象到Survivor区");

        // 3.1 复制Eden区的存活对象
        copyFromEden();

        // 3.2 复制From Space的存活对象
        copyFromSurvivorFrom();

        // 3.3 处理对象年龄
        updateObjectAges();
    }

    private void copyFromEden() {
        for (Object obj : eden.getObjects()) {
            if (obj.isMarked()) {
                Object copied = survivorTo.allocate(obj);
                copied.setAge(1); // 第一次进入Survivor区，年龄设为1
                obj.setForwardingPtr(copied); // 设置转发指针
            }
        }
    }

    private void copyFromSurvivorFrom() {
        for (Object obj : survivorFrom.getObjects()) {
            if (obj.isMarked()) {
                // 检查是否需要晋升
                if (shouldPromote(obj)) {
                    promoteToOldGeneration(obj);
                } else {
                    Object copied = survivorTo.allocate(obj);
                    copied.setAge(obj.getAge() + 1);
                    obj.setForwardingPtr(copied);
                }
            }
        }
    }

    private void promoteObjects() {
        System.out.println("第4步：对象晋升到老年代");

        // 检查Survivor To区的对象，处理晋升
        for (Object obj : survivorTo.getObjects()) {
            if (obj.getAge() >= MAX_TENURING_AGE) {
                // 年龄达到阈值，晋升到老年代
                promoteToOldGeneration(obj);
            }
        }

        // 检查Survivor空间是否足够
        if (survivorTo.getUsedSpace() > survivorTo.getMaxSpace() * 0.9) {
            // Survivor空间不足，提前晋升一些对象
            earlyPromotion();
        }
    }

    private void cleanYoungGen() {
        System.out.println("第5步：清理新生代");

        // 5.1 清空Eden区
        eden.clear();

        // 5.2 清空From Space
        survivorFrom.clear();

        // 5.3 清除标记位
        clearMarkBits();

        // 5.4 交换Survivor区
        swapSurvivorSpaces();
    }
}
```

### Full GC 流程详解

#### 1. Full GC 触发时机

```java
public class FullGCTrigger {
    /*
     * Full GC 触发条件：
     * 1. 老年代空间不足
     * 2. 方法区空间不足（PermGen/Metaspace）
     * 3. System.gc()调用
     * 4. Young GC晋升失败
     * 5. 分配担保失败
     */

    private Space oldGeneration;
    private Space metaspace;

    public boolean shouldTriggerFullGC() {
        return oldGeneration.getRemaining() < MIN_OLD_SPACE ||
               metaspace.getRemaining() < MIN_METASPACE ||
               systemGCCalled ||
               promotionFailed ||
               allocationFailure;
    }
}
```

#### 2. Full GC 详细流程

```java
public class FullGCProcess {
    private Space youngGeneration;
    private Space oldGeneration;
    private Space metaspace;

    public void fullGC() {
        System.out.println("触发Full GC");
        long startTime = System.currentTimeMillis();

        // STW：停止所有应用线程
        stopAllApplicationThreads();

        try {
            // 第1步：初始标记（Initial Mark）
            initialMark();

            // 第2步：并发标记（Concurrent Mark）- 可选
            concurrentMark();

            // 第3步：最终标记（Final Mark）
            finalMark();

            // 第4步：筛选回收（或标记整理）
            if (useMarkCompact()) {
                markCompact();
            } else {
                markSweep();
            }

            // 第5步：方法区回收
            collectMetaspace();

            // 第6步：引用处理
            processReferences();

        } finally {
            // 恢复应用线程
            resumeAllApplicationThreads();
            long endTime = System.currentTimeMillis();
            System.out.println("Full GC完成，耗时: " + (endTime - startTime) + "ms");
        }
    }

    private void initialMark() {
        System.out.println("第1步：初始标记");
        /*
         * 快速标记GC Roots直接可达的对象
         * 时间短，必须STW
         */
        Set<Object> gcRoots = findGCRoots();
        for (Object root : gcRoots) {
            markObject(root);
        }
    }

    private void concurrentMark() {
        System.out.println("第2步：并发标记");
        /*
         * 并发标记剩余对象
         * 应用线程可以继续运行
         * 需要处理并发修改
         */
        Set<Object> workList = getMarkedObjects();

        while (!workList.isEmpty()) {
            Object obj = workList.iterator().next();
            workList.remove(obj);

            // 标记对象引用的所有对象
            for (Object ref : obj.getReferences()) {
                if (!ref.isMarked()) {
                    ref.setMarked(true);
                    workList.add(ref);
                }
            }
        }
    }

    private void finalMark() {
        System.out.println("第3步：最终标记");
        /*
         * 处理并发标记期间发生的对象引用变化
         * 必须STW，保证标记的准确性
         */
        // 处理卡表中的脏卡片
        processDirtyCards();

        // 处理SATB缓冲区（G1GC）
        processSATBBuffers();
    }

    private void markSweep() {
        System.out.println("第4步：标记-清除");

        // 4.1 清除阶段
        for (Space space : getAllSpaces()) {
            for (MemoryRegion region : space) {
                if (!region.getObject().isMarked()) {
                    // 回收未标记的对象
                    freeRegion(region);
                } else {
                    // 清除标记位
                    region.getObject().setMarked(false);
                }
            }
        }
    }

    private void markCompact() {
        System.out.println("第4步：标记-整理");

        // 4.1 计算新位置
        calculateNewPositions();

        // 4.2 移动对象
        compactObjects();

        // 4.3 更新引用
        updateReferences();
    }

    private void calculateNewPositions() {
        int position = HEAP_START;

        // 按顺序计算存活对象的新位置
        for (Space space : getAllSpaces()) {
            for (MemoryRegion region : space) {
                if (region.getObject().isMarked()) {
                    region.setNewPosition(position);
                    position += region.getObject().size();
                }
            }
        }
        setHeapEnd(position);
    }

    private void compactObjects() {
        for (Space space : getAllSpaces()) {
            for (MemoryRegion region : space) {
                if (region.isMarked()) {
                    // 移动对象到新位置
                    Object obj = region.getObject();
                    Object newObj = allocateAt(obj, region.getNewPosition());
                    copyObject(obj, newObj);
                }
            }
        }
    }

    private void updateReferences() {
        // 更新所有引用到新的对象位置
        for (Object root : getAllGCRoots()) {
            updateReferencesInObject(root);
        }
    }

    private void collectMetaspace() {
        System.out.println("第5步：方法区回收");

        // 卸载无用的类
        Set<Class> unusedClasses = findUnusedClasses();
        for (Class cls : unusedClasses) {
            unloadClass(cls);
        }
    }

    private void processReferences() {
        System.out.println("第6步：引用处理");

        // 处理不同类型的引用
        processSoftReferences();   // 软引用
        processWeakReferences();    // 弱引用
        processPhantomReferences(); // 虚引用
        processFinalReferences();   // Final引用
    }
}
```

### GC Root 类型详解

#### 1. GC Roots 分类

```java
public class GCRooTypes {
    /*
     * GC Roots 是垃圾回收的起点，包括：
     *
     * 1. 虚拟机栈（栈帧中的本地变量表）
     * 2. 方法区中的类静态属性引用的对象
     * 3. 方法区中的常量引用的对象
     * 4. 本地方法栈中JNI引用的对象
     * 5. Java虚拟机内部的引用
     * 6. 所有被同步锁持有的对象
     * 7. 反映Java虚拟机内部情况的GC Roots
     */

    public void findGCRoots() {
        Set<Object> roots = new HashSet<>();

        // 1. 虚拟机栈中的引用
        roots.addAll(getStackLocalVariables());

        // 2. 静态变量引用
        roots.addAll(getStaticVariableReferences());

        // 3. 常量引用
        roots.addAll(getConstantReferences());

        // 4. JNI引用
        roots.addAll(getJNIReferences());

        // 5. 同步锁对象
        roots.addAll(getSynchronizedObjects());

        return roots;
    }
}
```

### 并发标记与写屏障

#### 1. 写屏障机制

```java
public class WriteBarrier {
    /*
     * 写屏障用于处理并发标记期间的对象引用变化
     * 保证标记过程的一致性
     */

    private final Object lock = new Object();
    private Set<Object> modifiedObjects = new HashSet<>();

    // 写屏障：在对象引用被修改时调用
    public void writeBarrier(Object obj, Object oldRef, Object newRef) {
        if (isConcurrentMarkingActive()) {
            synchronized (lock) {
                // SATB（Snapshot-At-The-Beginning）策略
                if (oldRef != null && !oldRef.isMarked()) {
                    // 记录旧的引用，保证其不会被回收
                    markObject(oldRef);
                }

                // 记录修改的对象
                modifiedObjects.add(obj);
            }
        }
    }

    // 增量更新策略
    public void incrementalUpdate(Object obj, Object newRef) {
        if (newRef != null && !newRef.isMarked()) {
            // 标记新的引用
            markObject(newRef);
        }
    }
}
```

### 性能监控与调优

#### 1. GC日志分析

```java
public class GCMonitoring {
    /*
     * GC日志格式分析
     *
     * Young GC日志示例：
     * [GC (Allocation Failure) [PSYoungGen: 65536K->1072K(76288K)] 65536K->1072K(251392K), 0.0035672 secs]
     *
     * Full GC日志示例：
     * [Full GC (System.gc()) [PSYoungGen: 1072K->0K(76288K)] [ParOldGen: 1408K->1408K(175104K)] 2480K->1408K(251392K), [Metaspace: 3458K->3458K(1056768K)], 0.0075672 secs]
     */

    public void analyzeGCLog(String logLine) {
        if (logLine.contains("GC (Allocation Failure)")) {
            // Young GC
            parseYoungGCLog(logLine);
        } else if (logLine.contains("Full GC")) {
            // Full GC
            parseFullGCLog(logLine);
        }
    }

    private void parseYoungGCLog(String logLine) {
        // 解析Young GC信息
        // [PSYoungGen: 前大小->后大小(总大小)]
        // 总堆：前大小->后大小(总大小)
        // 耗时：xxx secs
    }
}
```

#### 2. GC性能指标

```java
public class GCPerformanceMetrics {
    /*
     * GC性能关键指标：
     *
     * 1. 吞吐量（Throughput）
     *    = 应用运行时间 / (应用运行时间 + GC时间)
     *
     * 2. 停顿时间（Pause Time）
     *    单次GC的最大停顿时间
     *
     * 3. GC频率
     *    单位时间内GC的次数
     *
     * 4. 内存使用率
     *    堆内存的使用情况
     */

    private long totalGCTime;
    private long totalRunTime;
    private long maxPauseTime;

    public double getThroughput() {
        return (double) totalRunTime / (totalRunTime + totalGCTime);
    }

    public long getMaxPauseTime() {
        return maxPauseTime;
    }

    public void recordGCPause(long pauseTime) {
        totalGCTime += pauseTime;
        maxPauseTime = Math.max(maxPauseTime, pauseTime);
    }
}
```

### 答题总结

JVM中一次完整的GC流程：

**Young GC 流程：**
1. **触发阶段**：Eden区空间不足
2. **标记阶段**：从GC Roots标记存活对象（STW）
3. **复制阶段**：将存活对象复制到Survivor区
4. **晋升阶段**：符合条件的对象晋升到老年代
5. **清理阶段**：清空Eden区和From Space
6. **恢复阶段**：恢复应用线程执行

**Full GC 流程：**
1. **触发阶段**：老年代空间不足等条件
2. **初始标记**：快速标记GC Roots直接可达对象（STW）
3. **并发标记**：标记剩余对象（允许并发）
4. **最终标记**：处理并发期间的引用变化（STW）
5. **筛选回收**：执行标记-清除或标记-整理
6. **方法区回收**：回收无用的类信息
7. **引用处理**：处理软、弱、虚引用

**关键特点：**
- Young GC频繁但快速，主要回收新生代
- Full GC不频繁但耗时，回收整个堆
- STW是GC过程中不可避免的停顿
- 现代GC算法尽量减少STW时间，提高并发性
- 写屏障和卡表机制支持并发标记

理解完整的GC流程对于JVM调优和问题诊断具有重要意义。