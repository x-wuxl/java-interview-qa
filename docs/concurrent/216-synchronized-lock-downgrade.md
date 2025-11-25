---
layout: default
title: "synchronized的锁能降级吗？"
parent: 并发编程
nav_order: 216
description: "深入探讨synchronized锁能否降级的问题，分析锁降级的技术难点和JVM的设计权衡"
date: 2025-11-02
---
# synchronized的锁能降级吗？

## 核心答案

**一般情况下，synchronized 的锁不能降级**（重量级锁不会降级为轻量级锁或偏向锁）。

但需要分两种情况讨论：

1. **锁升级后不降级**（主要情况）
2. **偏向锁的特殊"重偏向"机制**（JDK 6-14）

---

## 为什么不支持锁降级？

### 1. 技术复杂性

#### 状态不可逆

```
无锁 → 偏向锁 → 轻量级锁 → 重量级锁
  ✓      ✓         ✓          ✗ 无法回退
```

**原因**：
- **Monitor 对象已创建**：重量级锁会创建 ObjectMonitor 对象，涉及系统资源分配
- **等待队列存在**：`_EntryList` 和 `_WaitSet` 中可能有阻塞线程
- **状态难以同步**：多个线程对锁状态的认知难以一致性回退

#### 降级时机难以判断

```java
// 何时降级？
synchronized(lock) {
    // 当前只有1个线程
    // 但下一秒可能有10个线程竞争
    // 是否应该降级？
}
```

**问题**：
- 无法预测未来的竞争情况
- 频繁升降级会带来额外开销
- 降级判断本身需要额外的监控成本

### 2. 安全性风险

#### 内存一致性问题

```java
// 线程1：持有重量级锁
synchronized(lock) {
    count++;  // ① 修改共享变量
}  // ② 释放锁（假设降级为轻量级锁）

// 线程2：获取轻量级锁
synchronized(lock) {
    int value = count;  // ③ 读取共享变量
}
```

**风险**：
- 重量级锁使用 Monitor 的内存屏障保证可见性
- 降级为轻量级锁后，内存屏障机制改变
- 可能导致 happens-before 关系被破坏

#### 线程唤醒问题

```java
// 重量级锁阶段
synchronized(lock) {
    lock.wait();  // 线程进入 _WaitSet
}

// 降级后 _WaitSet 中的线程如何处理？
```

### 3. 性能权衡

#### 降级成本 vs 收益

```
降级开销：
- 检查是否可降级：遍历等待队列、判断竞争状态
- 修改 Mark Word：CAS 操作
- 清理 Monitor：释放系统资源
- 同步状态：STW（Stop-The-World）

收益：
- 后续加锁稍快（但不确定是否有后续）
```

**结论**：降级的开销往往大于收益，不如维持当前状态。

---

## 偏向锁的"重偏向"机制

### 特殊情况

虽然不是严格意义的降级，但 JDK 6-14 的偏向锁有**批量重偏向**和**批量撤销**机制。

### 批量重偏向（Bulk Rebias）

#### 触发条件

同一个类的多个实例，偏向锁被撤销次数达到阈值（默认 20 次）。

#### 流程

```java
class User {
    private int id;
}

List<User> users = new ArrayList<>();
for (int i = 0; i < 100; i++) {
    users.add(new User());
}

// 线程1：偏向所有 User 对象
for (User user : users) {
    synchronized(user) {
        // 偏向线程1
    }
}

// 线程2：尝试访问
for (User user : users) {
    synchronized(user) {
        // 前20个：逐个撤销偏向，升级为轻量级锁
        // 第21个：触发批量重偏向
        //        将剩余对象的偏向线程改为线程2（Epoch机制）
        //        无需升级为轻量级锁
    }
}
```

#### Epoch 机制

```
Mark Word 中的 Epoch 字段（2bit）：
- 记录偏向锁的版本号
- 批量重偏向时递增 Epoch
- 旧 Epoch 的偏向锁失效，新线程可以重新偏向
```

**本质**：不是真正的降级，而是**批量修改偏向目标**，避免逐个升级。

### 批量撤销（Bulk Revoke）

#### 触发条件

批量重偏向后，撤销次数再次达到阈值（默认 40 次）。

#### 流程

```java
// 第40次撤销时
// JVM 认为该类对象不适合偏向锁
// 将该类标记为"不可偏向"
// 后续新创建的对象直接进入无锁状态
```

---

## HotSpot 源码解析

### 锁状态转换代码

```cpp
// src/hotspot/share/runtime/synchronizer.cpp

// 膨胀为重量级锁（单向，无降级逻辑）
ObjectMonitor* ObjectSynchronizer::inflate(Thread * Self,
                                            oop object,
                                            const InflateCause cause) {
    // 1. 检查是否已经是重量级锁
    markOop mark = object->mark();
    if (mark->has_monitor()) {
        return mark->monitor();  // 直接返回
    }
    
    // 2. 分配 ObjectMonitor 对象
    ObjectMonitor * m = omAlloc(Self);
    
    // 3. CAS 将 Mark Word 指向 Monitor
    // 4. 初始化 Monitor 状态
    
    // ⚠️ 注意：没有降级逻辑，膨胀后不可逆
    return m;
}
```

### 偏向锁重偏向代码

```cpp
// src/hotspot/share/runtime/biasedLocking.cpp

BiasedLocking::Condition BiasedLocking::revoke_and_rebias(
    Handle obj, bool attempt_rebias, TRAPS) {
    
    // Epoch 机制实现批量重偏向
    if (attempt_rebias) {
        markOop biased_value = mark;
        markOop rebiased_prototype = 
            markOopDesc::encode(THREAD, mark->age(), epoch);
        
        markOop res_mark = obj->cas_set_mark(
            rebiased_prototype, biased_value);
        
        if (res_mark == biased_value) {
            return BIAS_REVOKED_AND_REBIASED;  // 重偏向成功
        }
    }
    
    // 撤销偏向，升级为轻量级锁
    // 注意：轻量级锁无法降级回偏向锁
}
```

---

## 为什么 ReentrantLock 不支持降级？

对比 `ReentrantReadWriteLock`，它支持**写锁降级为读锁**：

```java
ReadWriteLock rwLock = new ReentrantReadWriteLock();
Lock writeLock = rwLock.writeLock();
Lock readLock = rwLock.readLock();

writeLock.lock();
try {
    // 写操作
    readLock.lock();  // ✅ 降级：先获取读锁
} finally {
    writeLock.unlock();  // 释放写锁，保持读锁
}

try {
    // 读操作
} finally {
    readLock.unlock();
}
```

**为什么可以？**
- 应用层显式控制，不是自动降级
- 写锁持有者可以安全获取读锁（不会死锁）
- 语义明确：写完成后，降级为读保护

**synchronized 不支持的原因**：
- 没有读写锁的概念
- 自动降级难以保证安全性
- 设计目标是简单易用，不是灵活性

---

## JDK 15 禁用偏向锁的影响

### 背景

JDK 15 默认禁用偏向锁（`-XX:-UseBiasedLocking`），JDK 18 完全移除。

### 原因

1. **维护成本高**：偏向锁的 STW、批量重偏向等机制复杂
2. **现代应用不适用**：线程池等场景下偏向锁反而导致频繁撤销
3. **轻量级锁优化**：自适应自旋的改进使轻量级锁足够快

### 影响

```
锁升级路径变化：
JDK 6-14:  无锁 → 偏向锁 → 轻量级锁 → 重量级锁
JDK 15+:   无锁 → 轻量级锁 → 重量级锁
```

---

## 面试答题模板

**问题**：synchronized 的锁能降级吗？

**回答**：

**主要结论**：synchronized 的锁**不支持降级**，锁升级是单向的。

**原因**：

1. **技术复杂性**：
   - 重量级锁已创建 Monitor 对象和等待队列，难以安全回退
   - 降级时机难以判断（无法预测未来竞争）
   
2. **安全性风险**：
   - 内存屏障机制改变可能破坏 happens-before 关系
   - `wait()`/`notify()` 机制依赖 Monitor，降级会导致问题

3. **性能考量**：
   - 降级的检查和状态切换成本高
   - 收益不确定（可能马上又升级）

**特殊情况**：

JDK 6-14 的偏向锁有**批量重偏向**机制（Epoch），但这不是真正的降级，而是批量修改偏向目标，避免逐个升级为轻量级锁。JDK 15 后偏向锁已被禁用，不再存在这个机制。

**对比**：`ReentrantReadWriteLock` 支持写锁降级为读锁，但那是应用层显式控制，语义明确，与 synchronized 的自动升级不同。

