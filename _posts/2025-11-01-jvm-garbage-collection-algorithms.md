---
layout: post
title: "JVM有哪些垃圾回收算法"
date: 2025-11-01
description: "详细介绍Java虚拟机中的垃圾回收算法，包括标记-清除、复制、标记-整理、分代收集等核心算法"
author: "wuxl"
categories: [JVM]
tags: [JVM, 垃圾回收, GC算法, 标记清除, 复制算法, 标记整理]
---

## 问题

JVM有哪些垃圾回收算法？

## 答案

### 核心概念

垃圾回收算法是JVM用于自动管理内存的核心机制，主要解决**如何判断对象是否存活**和**如何回收内存**两个问题。不同的算法在效率、空间利用率和停顿时间方面各有特点。

### 主要垃圾回收算法

#### 1. 标记-清除算法（Mark-Sweep）

**算法原理：**
```java
public class MarkSweepAlgorithm {
    /*
     * 工作流程：
     * 1. 标记阶段：从GC Roots开始遍历，标记所有可达对象
     * 2. 清除阶段：遍历堆内存，回收所有未标记对象
     */

    // 标记阶段的伪代码
    void mark(Object root) {
        if (root == null || root.isMarked()) return;

        root.setMarked(true);
        mark(root.getField1());  // 标记引用对象
        mark(root.getField2());
        // ... 标记所有引用
    }

    // 清除阶段的伪代码
    void sweep() {
        for (Object obj : heap) {
            if (!obj.isMarked()) {
                free(obj);  // 回收未标记对象
            } else {
                obj.setMarked(false);  // 清除标记位
            }
        }
    }
}
```

**优点：**
- 实现简单，基础算法
- 不移动对象，无需调整引用

**缺点：**
- **内存碎片化**：回收后产生不连续内存空间
- 标记和清除效率都不高
- 空间利用率低

#### 2. 复制算法（Copying）

**算法原理：**
```java
public class CopyingAlgorithm {
    /*
     * 工作流程：
     * 1. 将内存分为两个相等的区域：From空间和To空间
     * 2. From空间存储活跃对象，To空间为空
     * 3. GC时将From空间的存活对象复制到To空间
     * 4. 清空From空间，交换From和To的角色
     */

    public void gc() {
        // 从GC Roots开始复制存活对象
        for (Object root : gcRoots) {
            if (root != null && isInFromSpace(root)) {
                copyToToSpace(root);
            }
        }

        // 交换From和To空间
        swapSpaces();

        // 清空原From空间（现在是To空间）
        clearCurrentFromSpace();
    }

    private void copyToToSpace(Object obj) {
        Object newObj = allocateInToSpace(obj);
        // 递归复制引用对象
        copyReferences(newObj);
    }
}
```

**优点：**
- **无内存碎片**：存活对象连续存放
- 回收效率高，只需处理存活对象
- 分配速度快（指针碰撞）

**缺点：**
- **空间浪费**：只能使用一半内存
- 复制开销大，对象多时效率低

#### 3. 标记-整理算法（Mark-Compact）

**算法原理：**
```java
public class MarkCompactAlgorithm {
    /*
     * 工作流程：
     * 1. 标记阶段：标记所有存活对象（同标记-清除）
     * 2. 整理阶段：将存活对象向一端移动，保持对象间的引用关系
     * 3. 清理阶段：清理边界外的内存
     */

    public void gc() {
        // 第一阶段：标记
        markPhase();

        // 第二阶段：计算新位置
        calculateNewPositions();

        // 第三阶段：移动对象并更新引用
        compactPhase();
    }

    private void compactPhase() {
        int position = 0;
        for (Object obj : heap) {
            if (obj.isMarked()) {
                // 移动对象到新位置
                Object newPos = heap[position];
                moveObject(obj, newPos);
                updateReferences(obj, newPos);
                position += obj.size();
            }
        }
        // 更新堆的末尾位置
        updateHeapEnd(position);
    }
}
```

**优点：**
- **无内存碎片**：存活对象连续存放
- 空间利用率高（不浪费内存）

**缺点：**
- 移动对象开销大
- 需要暂停所有应用线程

#### 4. 分代收集算法（Generational Collection）

**算法原理：**
```java
public class GenerationalGC {
    /*
     * 核心思想：不同生命周期的对象采用不同回收策略
     * - 新生代：生命周期短，采用复制算法
     * - 老年代：生命周期长，采用标记-清除或标记-整理
     */

    public void minorGC() {
        // 新生代GC：使用复制算法
        copySurvivorsFromEdenToSurvivor();
        promoteOldObjects();
        cleanEdenSpace();
    }

    public void majorGC() {
        // 老年代GC：使用标记-清除或标记-整理
        markOldGeneration();
        compactOldGeneration(); // 或 sweepOldGeneration()
    }

    // 晋升��略
    private void promoteOldObjects() {
        for (Object obj : survivorSpace) {
            if (obj.getAge() >= MAX_AGE) {
                promoteToOldGeneration(obj);
            } else {
                obj.increaseAge();
            }
        }
    }
}
```

**分代假设：**
- **弱分代假设**：大部分对象都是朝生夕死的
- **分代收集假设**：跨代引用相对于同代引用来说很少

**优点：**
- **高效回收**：针对不同代采用最优算法
- **减少停顿**：MinorGC频繁但快速，MajorGC不频繁
- **空间利用率高**：整体内存使用效率高

#### 5. 增量收集算法（Incremental Collection）

**算法原理：**
```java
public class IncrementalGC {
    /*
     * 将GC工作分解为多个小步骤，与应用程序交替执行
     * 减少单次GC的停顿时间，但可能增加总体时间
     */

    private int gcPhase = 0;

    public void incrementalGC() {
        switch (gcPhase % 4) {
            case 0: markPhase1(); break;
            case 1: markPhase2(); break;
            case 2: sweepPhase1(); break;
            case 3: sweepPhase2(); break;
        }
        gcPhase++;
    }

    // 在应用线程的适当位置调用
    public void applicationLoop() {
        while (running) {
            doWork();
            if (shouldRunGC()) {
                incrementalGC();
            }
        }
    }
}
```

### 算法性能对比

#### 1. 时间复杂度对比

| 算法 | 标记时间 | 清除时间 | 移动时间 | 总体效率 |
|------|----------|----------|----------|----------|
| 标记-清除 | O(n) | O(n) | - | 中等 |
| 复制算法 | O(n) | O(n) | O(n) | 存活对象少时高 |
| 标记-整理 | O(n) | O(n) | O(n) | 存活对象多时高 |

#### 2. 空间复杂度对比

```java
public class SpaceComplexity {
    // 标记-清除：空间利用率高，但碎片化
    // 复制算法：空间利用率50%，无碎片
    // 标记-整理：空间利用率高，无碎片

    public static void main(String[] args) {
        // 实际应用中的空间考量
        int heapSize = 1024; // 1GB堆内存

        // 标记-清除：可用约1GB，但有碎片
        // 复制算法：可用约512MB，无碎片
        // 标记-整理：可用约1GB，无碎片
    }
}
```

### 线程安全考量

#### 1. 并发标记

```java
public class ConcurrentMarking {
    /*
     * 在标记阶段允许应用线程继续运行
     * 需要处理对象引用的并发修改
     */

    private final Object lock = new Object();
    private volatile boolean marking = false;

    public void concurrentMark() {
        marking = true;
        try {
            // 并发标记过程
            markFromGCRoots();
        } finally {
            marking = false;
        }
    }

    public void writeBarrier(Object oldRef, Object newRef) {
        if (marking) {
            // 标记阶段的写屏障
            synchronized (lock) {
                // 处理并发修改
                handleConcurrentModification(oldRef, newRef);
            }
        }
    }
}
```

#### 2. 并发清理

```java
public class ConcurrentSweep {
    /*
     * 在清理阶段允许应用线程继续运行
     * 使用自由列表管理回收的内存
     */

    private final ConcurrentLinkedQueue<FreeBlock> freeList =
        new ConcurrentLinkedQueue<>();

    public void concurrentSweep() {
        for (MemoryBlock block : heap) {
            if (!block.isMarked()) {
                // 将回收的内存块加入自由列表
                freeList.offer(new FreeBlock(block));
                block.clear();
            }
        }
    }

    public Object allocate(int size) {
        // 从自由列表查找合适的内存块
        for (FreeBlock block : freeList) {
            if (block.size() >= size) {
                return allocateFromBlock(block, size);
            }
        }
        return null; // 需要触发GC
    }
}
```

### 分布式场景考量

#### 1. 分布式垃圾回收

```java
public class DistributedGC {
    /*
     * 在分布式系统中，对象可能跨越多个JVM实例
     * 需要协调各个节点的垃圾回收
     */

    public void distributedGC() {
        // 1. 本地标记阶段
        localMark();

        // 2. 分布式引用处理
        handleDistributedReferences();

        // 3. 协调全局GC
        coordinateGlobalGC();
    }

    private void handleDistributedReferences() {
        // 处理远程引用
        for (RemoteReference ref : remoteReferences) {
            if (ref.isStale()) {
                deregisterRemoteReference(ref);
            }
        }
    }
}
```

### 答题总结

JVM主要垃圾回收算法：

1. **标记-清除算法**：
   - 基础算法，简单易实现
   - 缺点是产生内存碎片

2. **复制算法**：
   - 高效回收，无内存碎片
   - 空间利用率只有50%

3. **标记-整理算法**：
   - 无内存碎片，空间利用率高
   - 移动对象开销较大

4. **分代收集算法**：
   - 现代JVM的核心策略
   - 新生代用复制算法，老年代用标记-清除/整理
   - 基于弱分代假设，高效回收

5. **增量收集算法**：
   - 减少单次停顿时间
   - 适合对延迟敏感的应用

**关键点**：
- 没有完美的算法，需要根据应用特性选择
- 分代收集是现代JVM的主流方案
- 算法选择影响性能、停顿时间和空间利用率
- 实际应用中通常是多种算法的组合使用