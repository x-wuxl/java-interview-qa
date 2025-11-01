---
layout: post
title: "新生代和老年代的GC算法"
date: 2025-11-01
description: "详细介绍Java虚拟机新生代和老年代使用的不同垃圾回收算法，包括复制算法、标记-清除、标记-整理等"
author: "wuxl"
categories: [JVM]
tags: [JVM, 垃圾回收, 分代收集, 新生代GC, 老年代GC, 复制算法]
---

## 问题

新生代和老年代的GC算法有什么不同？

## 答案

### 核心概念

JVM采用**分代收集**策略，根据对象生命周期不同，将堆内存分为新生代和老年代，并针对不同代的特点使用最合适的垃圾回收算法。这种设计基于**弱分代假设**：大部分对象都是朝生夕死的。

### 内存分代结构

#### 1. 堆内存结构

```java
public class HeapStructure {
    /*
     * Java堆内存结构（默认比例）：
     *
     * ┌─────────────────────────────────────┐
     * │           老年代 (Old Generation)   │  约2/3
     * ├─────────────────────────────────────┤
     * │              新生代 (Young)         │  约1/3
     * │  ┌─────────────┬─────────┬─────────┐ │
     * │  │    Eden     │ S0      │ S1      │ │
     * │  │   (8/10)    │ (1/10)  │ (1/10)  │ │
     * │  └─────────────┴─────────┴─────────┘ │
     * └─────────────────────────────────────┘
     */

    /**
     * 分代比例配置参数：
     * -XX:NewRatio=2           // 新生代:老年代 = 1:2
     * -XX:SurvivorRatio=8      // Eden:Survivor = 8:1:1
     * -XX:TargetSurvivorRatio=90 // Survivor区使用目标比例
     */
}
```

#### 2. 分代理论基础

```java
public class GenerationalTheory {
    /*
     * 弱分代假设：
     * 1. 大部分对象都是朝生夕死的
     * 2. 老对象很少引用新对象
     * 3. 跨代引用相对于同代引用来说很少
     */

    public static void main(String[] args) {
        // 短生命周期对象（大部分）
        String temp = "temporary";
        // 立即变为垃圾

        // 长生命周期对象（小部分）
        List<String> cache = new ArrayList<>();
        // 长期存活在老年代
    }
}
```

### 新生代垃圾回收算法

#### 1. 复制算法（Copying）

**算法原理：**
```java
public class YoungGenerationGC {
    /*
     * 新生代采用复制算法的原因：
     * 1. 新生代对象存活率低（通常<10%）
     * 2. 复制成本低：只复制存活对象
     * 3. 无内存碎片，分配效率高
     * 4. GC停顿时间短
     */

    private Space eden;          // 伊甸园区
    private Space survivor0;     // 幸存者区0 (From Space)
    private Space survivor1;     // 幸存者区1 (To Space)

    public void minorGC() {
        // 1. 标记Eden和From Space中的存活对象
        markLiveObjects();

        // 2. 复制存活对象到To Space
        copyLiveObjectsToToSpace();

        // 3. 清空Eden和From Space
        clearEdenAndFromSpace();

        // 4. 交换From Space和To Space
        swapSurvivorSpaces();

        // 5. 对象年龄增加
        incrementObjectAges();
    }

    private void copyLiveObjectsToToSpace() {
        Space fromSpace = getCurrentFromSpace();
        Space toSpace = getToSpace();

        for (Object obj : fromSpace.getLiveObjects()) {
            if (obj.getAge() < MAX_TENURING_AGE) {
                // 复制到To Space并增加年龄
                Object copied = toSpace.allocate(obj);
                copied.setAge(obj.getAge() + 1);
            } else {
                // 晋升到老年代
                promoteToOldGeneration(obj);
            }
        }
    }
}
```

**晋升机制：**
```java
public class PromotionMechanism {
    /*
     * 对象晋升到老年代的条件：
     * 1. 年龄达到阈值（默认15岁）
     * 2. To Space空间不足
     * 3. 大对象直接进入老年代
     */

    private static final int MAX_TENURING_AGE = 15; // CMS默认6

    public boolean shouldPromote(Object obj) {
        // 条件1：年龄检查
        if (obj.getAge() >= MAX_TENURING_AGE) {
            return true;
        }

        // 条件2：Survivor空间不足
        if (getTargetSurvivor().getAvailableSpace() < obj.size()) {
            return true;
        }

        // 条件3：动态年龄判断
        if (isPromotedByDynamicAge()) {
            return true;
        }

        return false;
    }

    private boolean isPromotedByDynamicAge() {
        // 当Survivor空间使用率达到TargetSurvivorRatio时，
        // 将年龄大于等于当前对象年龄的对象全部晋升
        return getSurvivorUsageRatio() >= TARGET_SURVIVOR_RATIO;
    }
}
```

### 老年代垃圾回收算法

#### 1. 标记-清除算法（Mark-Sweep）

**适用场景：**
```java
public class OldGenerationGC {
    /*
     * 老年代特点：
     * 1. 对象存活率高（通常>90%）
     * 2. 对象大小差异大
     * 3. 回收频率低
     *
     * 适合使用标记-清除/标记-整理算法的原因：
     * 1. 存活对象多，复制成本高
     * 2. 对GC停顿时间相对不敏感
     */

    public void markSweep() {
        // 第一步：标记存活对象
        markPhase();

        // 第二步：清除未标记对象
        sweepPhase();
    }

    private void markPhase() {
        // 从GC Roots开始标记
        Set<Object> workList = new HashSet<>();
        workList.addAll(getGCRoots());

        while (!workList.isEmpty()) {
            Object obj = workList.iterator().next();
            workList.remove(obj);

            if (!obj.isMarked()) {
                obj.setMarked(true);
                workList.addAll(obj.getReferences());
            }
        }
    }

    private void sweepPhase() {
        // 遍历老年代，回收未标记对象
        for (MemoryRegion region : oldGeneration) {
            if (!region.getObject().isMarked()) {
                freeMemory(region);
            } else {
                region.getObject().setMarked(false);
            }
        }
    }
}
```

#### 2. 标记-整理算法（Mark-Compact）

**算法实现：**
```java
public class MarkCompactGC {
    /*
     * 标记-整理算法适用于老年代：
     * 1. 解决标记-清除的内存碎片问题
     * 2. 存活对象多，整理后空间利用率高
     */

    public void markCompact() {
        // 第一步：标记阶段
        markLiveObjects();

        // 第二步：计算新位置
        calculateNewPositions();

        // 第三步：移动对象
        compactObjects();

        // 第四步：更新引用
        updateReferences();
    }

    private void calculateNewPositions() {
        int position = OLD_GEN_START;

        // 按地址顺序计算每个存活对象的新位置
        for (MemoryRegion region : oldGeneration) {
            if (region.isMarked()) {
                region.setNewPosition(position);
                position += region.getObject().size();
            }
        }

        setOldGenEnd(position);
    }

    private void compactObjects() {
        for (MemoryRegion region : oldGeneration) {
            if (region.isMarked()) {
                // 移动对象到新位置
                Object obj = region.getObject();
                Object newObj = allocateAt(obj, region.getNewPosition());
                copyObject(obj, newObj);
            }
        }
    }

    private void updateReferences() {
        // 更新所有引用到新的对象位置
        for (Object root : getAllGCRoots()) {
            updateReferencesInObject(root);
        }
    }
}
```

### 跨代引用处理

#### 1. 记忆集（Remembered Set）

```java
public class RememberedSet {
    /*
     * 记忆集用于记录老年代到新生代的引用
     * 避免在Minor GC时扫描整个老年代
     */

    private Map<OldGenRegion, Set<YoungGenRegion>> rememberedSet;

    public void addReference(OldGenRegion oldRegion, YoungGenRegion youngRegion) {
        rememberedSet.computeIfAbsent(oldRegion, k -> new HashSet<>())
                    .add(youngRegion);
    }

    public Set<YoungGenRegion> getYoungReferences(OldGenRegion oldRegion) {
        return rememberedSet.getOrDefault(oldRegion, Collections.emptySet());
    }

    // 写屏障（Write Barrier）
    public void writeBarrier(Object oldObj, Object newObj) {
        if (isInOldGeneration(oldObj) && isInYoungGeneration(newObj)) {
            // 老年代对象引用了新生代对象
            OldGenRegion oldRegion = getRegion(oldObj);
            YoungGenRegion youngRegion = getRegion(newObj);
            addReference(oldRegion, youngRegion);
        }
    }
}
```

#### 2. 卡表（Card Table）

```java
public class CardTable {
    /*
     * 卡表是记忆集的具体实现
     * 将老年代分为多个卡片（通常512字节）
     * 每个卡片记录是否有新生代引用
     */

    private byte[] cards;
    private static final int CARD_SIZE = 512;

    public void markCard(Object obj) {
        if (isInOldGeneration(obj)) {
            int cardIndex = getAddress(obj) / CARD_SIZE;
            cards[cardIndex] = 1; // 标记为脏卡片
        }
    }

    public boolean isCardDirty(int cardIndex) {
        return cards[cardIndex] == 1;
    }

    public void cleanCard(int cardIndex) {
        cards[cardIndex] = 0;
    }
}
```

### GC触发条件对比

#### 1. 新生代GC触发条件

```java
public class YoungGCTriggers {
    /*
     * Minor GC触发条件：
     * 1. Eden区空间不足
     * 2. 新对象分配失败
     */

    public boolean shouldTriggerYoungGC() {
        return edenSpace.getUsedSpace() >= edenSpace.getMaxSpace();
    }

    // Young GC的特点
    public void youngGCCharacteristics() {
        /*
         * 频率：高（几分钟一次）
         * 停顿：短（几十毫秒）
         * 回收对象：主要是Eden区
         * 回收效率：高（存活率<10%）
         */
    }
}
```

#### 2. 老年代GC触发条件

```java
public class OldGCTriggers {
    /*
     * Major GC/Full GC触发条件：
     * 1. 老年代空间不足
     * 2. 方法区空间不足（Java 8前为永久代）
     * 3. System.gc()调用
     * 4. Minor GC晋升失败
     */

    public boolean shouldTriggerOldGC() {
        return oldGeneration.getUsedSpace() >= oldGeneration.getMaxSpace() ||
               methodSpace.getUsedSpace() >= methodSpace.getMaxSpace() ||
               promotionFailed;
    }

    // Old GC的特点
    public void oldGCCharacteristics() {
        /*
         * 频率：低（几小时一次）
         * 停顿：长（几百毫秒到几秒）
         * 回收对象：整个堆
         * 回收效率：低（存活率>90%）
         */
    }
}
```

### 性能优化配置

#### 1. 分代大小调优

```bash
# 分代大小配置示例
-XX:NewRatio=3                    # 新生代:老年代 = 1:3
-XX:SurvivorRatio=8               # Eden:Survivor = 8:1:1
-XX:MaxTenuringThreshold=15       # 晋升年龄阈值
-XX:TargetSurvivorRatio=90        # Survivor目标使用率

# 针对不同应用的调优
# Web应用（响应时间优先）
-Xms2g -Xmx2g -Xmn1g -XX:SurvivorRatio=6

# 批处理应用（吞吐量优先）
-Xms8g -Xmx8g -Xmn6g -XX:SurvivorRatio=8

# 缓存应用
-Xms16g -Xmx16g -Xmn4g -XX:MaxTenuringThreshold=6
```

#### 2. GC策略选择

```java
public class GCStrategySelection {
    /*
     * 不同场景的GC策略：
     *
     * 1. 高并发Web应用：
     *    - 较小的新生代，减少Minor GC时间
     *    - 使用G1GC，控制停顿时间
     *
     * 2. 大数据处理：
     *    - 较大的新生代，减少Full GC频率
     *    - 使用Parallel GC，优化吞吐量
     *
     * 3. 微服务：
     *    - 适中的分代大小，平衡内存和性能
     *    - 使用G1GC，适合容器化环境
     */

    public void chooseGCStrategy(ApplicationType type) {
        switch (type) {
            case WEB_APPLICATION:
                // 低延迟策略
                configureLowLatencyGC();
                break;
            case BATCH_PROCESSING:
                // 高吞吐量策略
                configureHighThroughputGC();
                break;
            case MICROSERVICE:
                // 平衡策略
                configureBalancedGC();
                break;
        }
    }
}
```

### 答题总结

新生代和老年代的GC算法差异：

1. **新生代GC算法（复制算法）**：
   - 原因：对象存活率低，复制成本低
   - 流程：Eden + S0 → S1，清理Eden和S0
   - 特点：速度快，无内存碎片，停顿时间短
   - 触发：Eden区空间不足

2. **老年代GC算法（标记-清除/标记-整理）**：
   - 原因：对象存活率高，不适合复制
   - 算法：标记-清除产生碎片，标记-整理消除碎片
   - 特点：速度慢，停顿时间长，回收频率低
   - 触发：老年代空间不足

3. **跨代引用处理**：
   - 记忆集（Remembered Set）记录老年代到新生代的引用
   - 卡表（Card Table）是记忆集的具体实现
   - 写屏障（Write Barrier）维护跨代引用信息

4. **性能考量**：
   - Minor GC频繁但快速
   - Major GC不频繁但耗时
   - 分代设计基于弱分代假设，整体效率高

**关键点**：
- 不同的代采用不同算法是基于对象生命周期的差异
- 跨代引用通过记忆集和卡表高效处理
- 合理的分代大小配置对性能至关重要
- 现代GC收集器在分代基础上进行了优化和扩展