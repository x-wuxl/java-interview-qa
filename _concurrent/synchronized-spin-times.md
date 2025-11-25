---
title: "synchronized升级过程中有几次自旋？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [synchronized, 自旋锁, 锁优化]
description: "深入分析synchronized锁升级过程中的自旋机制，包括自旋时机、次数和自适应策略"
nav_order: 215
parent: 并发编程
---
# synchronized升级过程中有几次自旋？

## 核心概念

在 `synchronized` 的锁升级过程中，**自旋主要发生在轻量级锁阶段**，用于避免线程阻塞带来的上下文切换开销。根据 JVM 版本和实现细节，自旋可能发生在**两个关键时机**。

## 自旋发生的时机

### 1. 轻量级锁获取时自旋

#### 场景

线程尝试通过 CAS 获取轻量级锁失败后，不立即膨胀为重量级锁，而是进入**自适应自旋**。

#### 流程

```java
// 伪代码
synchronized(obj) {
    // 步骤1：CAS 尝试获取轻量级锁
    if (CAS(obj.markWord, lockRecord)) {
        return;  // 成功，直接进入
    }
    
    // 步骤2：第一次自旋（轻量级锁竞争时）
    int spinCount = getAdaptiveSpinCount();
    while (spinCount-- > 0) {
        if (CAS(obj.markWord, lockRecord)) {
            return;  // 自旋成功
        }
        // 忙等待
    }
    
    // 步骤3：自旋失败，膨胀为重量级锁
    inflate(obj);
}
```

#### 自旋次数

- **默认值**：约 10 次（`-XX:PreBlockSpin`，JDK 6 后废弃）
- **自适应**：根据上次自旋成功率动态调整
  - 上次成功 → 增加自旋次数（最多到某个阈值）
  - 上次失败 → 减少自旋次数，甚至直接阻塞

---

### 2. 重量级锁入队前自旋

#### 场景

在膨胀为重量级锁后，线程在进入 `_EntryList` 阻塞队列之前，可能会再次尝试短暂自旋。

#### 流程

```java
// 伪代码
void enter(ObjectMonitor* mon) {
    // 步骤1：尝试直接获取 Monitor
    if (tryLock(mon)) {
        return;
    }
    
    // 步骤2：第二次自旋（重量级锁入队前）
    int spinCount = getAdaptiveSpinCount();
    while (spinCount-- > 0) {
        if (tryLock(mon)) {
            return;  // 自旋成功
        }
    }
    
    // 步骤3：加入 _EntryList 阻塞
    mon._EntryList.add(currentThread);
    park(currentThread);
}
```

#### 自旋条件

- 持有锁的线程正在运行（运行在其他 CPU 核心上）
- 等待线程数量较少
- 系统 CPU 核心数大于 1（单核自旋无意义）

---

## 总结：自旋发生几次？

### 标准答案

**两次**（在 HotSpot JVM 的实现中）：

1. **轻量级锁阶段的自旋**：
   - CAS 获取锁失败后
   - 自适应自旋等待锁释放
   - 失败后升级为重量级锁

2. **重量级锁入队前的自旋**：
   - 膨胀为重量级锁后
   - 进入阻塞队列前的最后尝试
   - 失败后进入 `_EntryList` 阻塞

### 关键代码位置

```cpp
// HotSpot 源码：src/hotspot/share/runtime/objectMonitor.cpp

// 第一次自旋：轻量级锁阶段
void ObjectSynchronizer::slow_enter(Handle obj, BasicLock* lock, TRAPS) {
    // ...
    if (UseBiasedLocking) {
        // 偏向锁逻辑
    }
    // 尝试轻量级锁 + 自旋
    if (mark->is_neutral()) {
        lock->set_displaced_header(mark);
        if (mark == obj()->cas_set_mark((markOop) lock, mark)) {
            return;  // 成功
        }
        // 自旋等待...
    }
    // 膨胀为重量级锁
    inflate(THREAD, obj(), inflate_cause_monitor_enter)->enter(THREAD);
}

// 第二次自旋：重量级锁入队前
void ObjectMonitor::enter(TRAPS) {
    // 自旋尝试获取 Monitor
    if (TryLock(Self) > 0) {
        return;
    }
    
    // 自旋等待（TrySpin）
    if (TrySpin(Self) > 0) {
        return;
    }
    
    // 进入阻塞队列
    EnterI(THREAD);
}
```

---

## 自适应自旋策略

### 算法原理

```java
int getAdaptiveSpinCount() {
    // 考虑因素：
    // 1. 上次自旋成功率
    // 2. 当前等待线程数
    // 3. 锁持有者的运行状态
    // 4. CPU 核心数
    
    if (lastSpinSucceeded && waitingThreads < cpuCount / 2) {
        return Math.min(currentSpinCount * 2, maxSpinCount);
    } else {
        return Math.max(currentSpinCount / 2, minSpinCount);
    }
}
```

### JVM 参数

```bash
# JDK 6 之前
-XX:+UseSpinning              # 开启自旋（默认开启）
-XX:PreBlockSpin=10           # 自旋次数（已废弃）

# JDK 6 之后
# 自适应自旋自动启用，无需手动配置
-XX:+UseSpinning              # 已废弃（默认开启）

# 监控自旋统计
-XX:+PrintSafepointStatistics
```

---

## 实际案例分析

### 案例1：轻量级锁自旋成功

```java
Object lock = new Object();

// 线程1 持有锁
new Thread(() -> {
    synchronized(lock) {
        sleep(5);  // 短时间持有
    }
}).start();

// 线程2 尝试获取
new Thread(() -> {
    synchronized(lock) {  
        // 1. CAS 失败（线程1持有）
        // 2. 进入自旋（第一次）
        // 3. 自旋期间线程1释放锁
        // 4. CAS 成功获取 ✅
    }
}).start();
```

**结果**：自旋成功，避免了重量级锁膨胀

### 案例2：重量级锁入队前自旋成功

```java
// 10个线程竞争
for (int i = 0; i < 10; i++) {
    new Thread(() -> {
        synchronized(lock) {
            // 线程1：获取偏向锁
            // 线程2：升级为轻量级锁
            // 线程3：自旋失败，膨胀为重量级锁
            // 线程4：重量级锁入队前自旋（第二次）
            //       如果线程3快速释放，自旋成功 ✅
            //       否则进入 _EntryList 阻塞
        }
    }).start();
}
```

### 案例3：自旋失败场景

```java
synchronized(lock) {
    sleep(1000);  // 长时间持有
}

// 其他线程
synchronized(lock) {
    // 1. 第一次自旋：失败（持有时间长）
    // 2. 膨胀为重量级锁
    // 3. 第二次自旋：失败（仍未释放）
    // 4. 进入 _EntryList 阻塞 ❌
}
```

**结果**：两次自旋都失败，最终阻塞

---

## 自旋的优缺点

### 优点

- 避免线程上下文切换（1-10微秒）
- 适用于锁持有时间短的场景（微秒级）
- 减少系统调用开销

### 缺点

- 占用 CPU 资源（空转）
- 不适合单核 CPU
- 不适合锁持有时间长的场景
- 过度自旋会降低吞吐量

---

## 面试答题模板

**问题**：synchronized 升级过程中有几次自旋？

**回答**：

在 HotSpot JVM 中，synchronized 的自旋主要发生**两次**：

1. **轻量级锁阶段的自旋**：
   - 线程通过 CAS 尝试获取轻量级锁失败后
   - 进入自适应自旋，默认 10 次左右
   - 如果自旋期间锁释放，可以直接获取
   - 失败后升级为重量级锁

2. **重量级锁入队前的自旋**：
   - 锁膨胀为重量级后，线程不立即阻塞
   - 再次尝试短暂自旋获取 Monitor
   - 失败后才加入 `_EntryList` 阻塞队列

这两次自旋都采用**自适应策略**，根据上次成功率、等待线程数、CPU 核心数等因素动态调整自旋次数，平衡 CPU 消耗和响应速度。

**适用场景**：锁持有时间短（几微秒到几十微秒）、CPU 核心数多、竞争不激烈时，自旋能显著提升性能。

