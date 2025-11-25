---
title: "synchronized的锁优化是怎样的？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [synchronized, JVM优化, 锁优化, 性能优化]
description: "全面解析JVM对synchronized的各种锁优化技术，包括锁消除、锁粗化、自适应自旋、锁升级等"
nav_order: 213
parent: 并发编程
---
# synchronized的锁优化是怎样的？

## 核心概念

早期的 `synchronized` 是重量级锁，性能较差。从 JDK 6 开始，HotSpot JVM 引入了一系列**锁优化技术**，显著提升了 synchronized 的性能，使其在大多数场景下不再是性能瓶颈。

## 主要优化技术

### 1. 锁消除（Lock Elimination）

#### 原理

JIT 编译器通过**逃逸分析**，检测到某些锁对象不会被其他线程访问时，自动消除锁操作。

#### 示例

```java
public String concat(String s1, String s2) {
    StringBuffer sb = new StringBuffer();
    sb.append(s1);  // StringBuffer 内部有 synchronized
    sb.append(s2);
    return sb.toString();
}
```

**优化过程**：
- `sb` 对象是局部变量，不会逃逸到方法外
- JIT 编译器检测到没有其他线程能访问 `sb`
- 自动消除 `append()` 方法内的 synchronized

**开启方式**：
```bash
-XX:+DoEscapeAnalysis    # 开启逃逸分析（默认开启）
-XX:+EliminateLocks      # 开启锁消除（默认开启）
```

### 2. 锁粗化（Lock Coarsening）

#### 原理

将多次连续的加锁/解锁操作合并为一次，减少锁开销。

#### 示例

```java
// 优化前
public void method() {
    synchronized(lock) {
        // 操作1
    }
    synchronized(lock) {
        // 操作2
    }
    synchronized(lock) {
        // 操作3
    }
}

// 优化后（JIT自动完成）
public void method() {
    synchronized(lock) {
        // 操作1
        // 操作2
        // 操作3
    }
}
```

**适用场景**：
- 循环内的 synchronized
- 连续调用同一对象的 synchronized 方法

**反例**（过度粗化影响并发度）：
```java
// ❌ 不要手动过度粗化
public synchronized void processLargeTask() {
    // 大量无需同步的代码
    // ...
    // 少量需要同步的代码
}
```

### 3. 自适应自旋（Adaptive Spinning）

#### 原理

线程获取锁失败后，不立即阻塞，而是执行**忙循环**（自旋）等待，避免用户态/内核态切换。

#### 传统自旋 vs 自适应自旋

**传统自旋**：
```java
// 固定自旋次数（如10次）
for (int i = 0; i < 10; i++) {
    if (tryLock()) {
        return;
    }
}
// 超过次数后阻塞
park();
```

**自适应自旋**：
- 根据上次自旋的成功率动态调整次数
- 如果上次自旋成功获取锁，增加自旋次数
- 如果上次自旋失败，减少自旋次数或直接阻塞

#### 优缺点

**优点**：
- 避免线程切换开销（1-10微秒）
- 适用于锁持有时间短的场景

**缺点**：
- 占用 CPU 资源（空转）
- 不适合锁持有时间长的场景

**JVM 参数**：
```bash
-XX:+UseSpinning              # 开启自旋（JDK 6默认开启）
-XX:PreBlockSpin=10           # 自旋次数（已废弃，自适应自动调整）
```

### 4. 偏向锁（Biased Locking）

#### 原理

针对**无竞争**场景优化，锁偏向第一个获取它的线程，后续该线程再进入无需 CAS 操作。

#### Mark Word 结构

```
|-------------------------------------------------------|
| 线程ID (54bit) | Epoch (2bit) | 分代年龄(4bit) | 01 |
|-------------------------------------------------------|
```

#### 加锁流程

1. **首次获取**：通过 CAS 将线程 ID 写入 Mark Word
2. **重入**：检查 Mark Word 中的线程 ID 是否为当前线程
   - 是：直接进入，无需 CAS
   - 否：升级为轻量级锁

#### 适用场景

- 单线程或无竞争的多线程场景
- 同一线程频繁获取同一把锁

**注意**：JDK 15 后默认禁用（`-XX:-UseBiasedLocking`）

### 5. 轻量级锁（Lightweight Locking）

#### 原理

在**低竞争**场景下，通过 CAS 操作在栈帧中建立锁记录，避免使用重量级 Monitor。

#### Mark Word 结构

```
|-------------------------------------------------------|
|    指向栈中锁记录的指针 (62bit)              | 00 |
|-------------------------------------------------------|
```

#### 加锁流程

1. 在栈帧中创建**锁记录（Lock Record）**
2. 将对象的 Mark Word 复制到锁记录
3. 通过 CAS 尝试将对象 Mark Word 替换为指向锁记录的指针
   - 成功：获取轻量级锁
   - 失败：自旋重试，多次失败后升级为重量级锁

#### 解锁流程

通过 CAS 将锁记录中的 Mark Word 还原到对象头
- 成功：释放锁
- 失败：说明有竞争，膨胀为重量级锁后释放

### 6. 重量级锁（Heavyweight Locking）

#### 原理

在**高竞争**场景下，依赖操作系统的 **Mutex Lock**，未获取锁的线程进入阻塞状态。

#### Mark Word 结构

```
|-------------------------------------------------------|
|    指向 Monitor 对象的指针 (62bit)           | 10 |
|-------------------------------------------------------|
```

#### 特点

- 涉及用户态/内核态切换（开销大）
- 线程进入 `_EntryList` 阻塞（不占用 CPU）
- 支持 `wait()/notify()` 机制

## 锁升级路径

```
无锁 → 偏向锁 → 轻量级锁 → 重量级锁
```

**单向升级**：锁只能升级，不能降级（JDK 15 前，偏向锁在 GC 后可能重偏向）

## 优化效果对比

| 锁类型     | 适用场景            | 性能  | 是否阻塞 | CAS次数 |
|-----------|---------------------|------|---------|---------|
| 偏向锁     | 无竞争，单线程反复获取 | 最高  | 否      | 1次（首次）|
| 轻量级锁   | 低竞争，锁持有时间短   | 较高  | 否（自旋）| 多次    |
| 重量级锁   | 高竞争，锁持有时间长   | 较低  | 是      | 1次（膨胀时）|

## 实战建议

### 1. 合理设置锁粒度

```java
// ❌ 锁粒度过大
public synchronized void process() {
    doSomething1();  // 不需要同步
    doSomething2();  // 需要同步
    doSomething3();  // 不需要同步
}

// ✅ 精细化锁控制
public void process() {
    doSomething1();
    synchronized(this) {
        doSomething2();
    }
    doSomething3();
}
```

### 2. 避免锁竞争

```java
// 使用分段锁降低竞争
public class SegmentLock {
    private final Object[] locks = new Object[16];
    
    public void operate(int key) {
        int index = key % locks.length;
        synchronized(locks[index]) {
            // 操作
        }
    }
}
```

### 3. 监控锁性能

```bash
# 查看偏向锁统计
-XX:+PrintBiasedLockingStatistics

# 查看 JIT 编译日志
-XX:+PrintCompilation
-XX:+UnlockDiagnosticVMOptions
-XX:+PrintInlining
```

## 答题总结

JVM 对 synchronized 的主要优化：

1. **锁消除**：逃逸分析消除不必要的锁
2. **锁粗化**：合并连续的加锁操作
3. **自适应自旋**：短时间忙等待，避免线程切换
4. **偏向锁**：无竞争场景，偏向首个线程
5. **轻量级锁**：低竞争场景，CAS + 自旋
6. **锁升级**：根据竞争程度自动升级（无锁 → 偏向 → 轻量 → 重量）

这些优化使 synchronized 在大多数场景下性能接近甚至超过 `ReentrantLock`，成为首选的同步方式。

