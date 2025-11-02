---
layout: post
title: "synchronized的锁升级过程是怎样的？"
date: 2025-11-02
categories: [Java, 并发编程]
tags: [synchronized, 锁升级, 偏向锁, 轻量级锁, 重量级锁]
description: "详细图解synchronized锁升级的完整过程，包括无锁、偏向锁、轻量级锁、重量级锁的转换条件和实现细节"
---

# synchronized的锁升级过程是怎样的？

## 核心概念

`synchronized` 的锁升级是 JVM 的自适应优化策略，根据**锁竞争程度**动态调整锁的实现方式，从低开销的偏向锁逐步升级到重量级锁，实现性能与线程安全的平衡。

## 锁升级路径

```
无锁 → 偏向锁 → 轻量级锁 → 重量级锁
```

**特点**：**单向升级，不可降级**（JDK 6-14，JDK 15后默认禁用偏向锁）

## 详细升级过程

### 阶段1：无锁状态

#### Mark Word 结构（64位JVM）

```
|------------------------------------------------------|
| 未使用(25bit) | hashcode(31bit) | 分代年龄(4bit) | 01 |
|------------------------------------------------------|
```

#### 特征

- 对象刚创建时的初始状态
- 标志位：`01`，且无偏向标记
- 没有线程访问

---

### 阶段2：偏向锁（Biased Lock）

#### 触发条件

- 第一个线程访问 synchronized 代码块
- JVM 参数 `-XX:+UseBiasedLocking` 开启（JDK 6-14 默认开启）
- 对象未禁用偏向（hashCode 未计算）

#### Mark Word 结构

```
|--------------------------------------------------------|
| 线程ID(54bit) | Epoch(2bit) | 分代年龄(4bit) | 偏向标记1 | 01 |
|--------------------------------------------------------|
```

#### 加锁流程

```java
synchronized(obj) {
    // 步骤1：检查 Mark Word 是否为偏向模式
    if (是偏向模式 && 线程ID == 当前线程ID) {
        // 直接进入，无需任何操作（最快路径）
        return;
    }
    
    // 步骤2：CAS 尝试将线程ID写入 Mark Word
    if (CAS成功) {
        // 偏向成功
        return;
    }
    
    // 步骤3：CAS 失败，说明有竞争，撤销偏向锁
    revokeBias();  // 升级为轻量级锁
}
```

#### 偏向锁撤销

**触发场景**：
1. 其他线程尝试获取锁
2. 调用 `wait()/notify()`
3. 调用 `System.identityHashCode()`

**撤销流程**：
```
1. 暂停拥有偏向锁的线程（STW）
2. 检查线程是否还在执行同步代码
   - 是 → 升级为轻量级锁
   - 否 → 恢复为无锁状态
3. 唤醒线程
```

---

### 阶段3：轻量级锁（Lightweight Lock）

#### 触发条件

- 偏向锁撤销后
- 有其他线程竞争，但竞争不激烈
- 锁持有时间短

#### Mark Word 结构

```
|------------------------------------------------------|
|  指向栈中Lock Record的指针 (62bit)             | 00 |
|------------------------------------------------------|
```

#### 加锁流程

```java
synchronized(obj) {
    // 步骤1：在当前线程栈帧中创建 Lock Record
    LockRecord record = new LockRecord();
    
    // 步骤2：将对象的 Mark Word 复制到 Lock Record
    record.displacedMarkWord = obj.markWord;
    
    // 步骤3：CAS 将对象 Mark Word 替换为指向 Lock Record 的指针
    if (CAS(obj.markWord, &record)) {
        // 加锁成功
        return;
    }
    
    // 步骤4：CAS 失败，进入自旋等待
    spinAcquire();
}
```

#### 自旋等待

```java
void spinAcquire() {
    int spinCount = 自适应自旋次数;  // 默认10次左右
    
    while (spinCount-- > 0) {
        if (CAS(obj.markWord, &record)) {
            return;  // 自旋成功
        }
        // 空转等待
    }
    
    // 自旋失败，膨胀为重量级锁
    inflate();
}
```

#### 解锁流程

```java
// 通过 CAS 将 Lock Record 中的 Mark Word 还原到对象头
if (CAS(obj.markWord, record.displacedMarkWord)) {
    // 解锁成功
    return;
}
// CAS 失败，说明有其他线程在自旋或已膨胀，走重量级锁释放流程
```

---

### 阶段4：重量级锁（Heavyweight Lock）

#### 触发条件

- 自旋失败（自旋次数超过阈值）
- 等待线程超过 CPU 核心数的一半
- 自旋线程超过 1 个
- 调用 `wait()/notify()`

#### Mark Word 结构

```
|------------------------------------------------------|
|  指向 Monitor 对象的指针 (62bit)              | 10 |
|------------------------------------------------------|
```

#### Monitor 对象结构

```java
ObjectMonitor {
    _owner       = null;      // 持有锁的线程
    _WaitSet     = [];        // 调用 wait() 的线程队列
    _EntryList   = [];        // 等待获取锁的线程队列
    _recursions  = 0;         // 重入次数
    _count       = 0;         // 计数器
}
```

#### 加锁流程

```java
monitorenter(obj) {
    Monitor* mon = obj.monitor;
    
    if (mon._owner == null) {
        // 无人持有，直接获取
        mon._owner = currentThread;
        return;
    }
    
    if (mon._owner == currentThread) {
        // 重入
        mon._recursions++;
        return;
    }
    
    // 加入 _EntryList 阻塞等待
    mon._EntryList.add(currentThread);
    park(currentThread);  // 操作系统层面阻塞
}
```

#### 解锁流程

```java
monitorexit(obj) {
    Monitor* mon = obj.monitor;
    
    if (--mon._recursions > 0) {
        // 还有重入，不释放
        return;
    }
    
    mon._owner = null;
    
    // 唤醒 _EntryList 中的一个线程（非公平）
    Thread t = mon._EntryList.removeFirst();
    unpark(t);
}
```

---

## 升级条件总结表

| 当前状态     | 升级条件                          | 目标状态     |
|-------------|----------------------------------|-------------|
| 无锁        | 第一次访问                        | 偏向锁       |
| 偏向锁      | 其他线程竞争                       | 轻量级锁     |
| 轻量级锁    | 自旋失败/竞争激烈/调用wait()        | 重量级锁     |

## 实际案例分析

### 案例1：单线程场景

```java
Object lock = new Object();
// 状态：无锁（01）

synchronized(lock) {  
    // 第一次：升级为偏向锁（01 + 偏向标记）
    // 线程ID写入 Mark Word
}

synchronized(lock) {  
    // 第二次：检查线程ID，直接进入（无 CAS）
}
```

**性能**：最优，几乎无额外开销

### 案例2：两个线程交替访问

```java
// 线程1
synchronized(lock) {  
    // 偏向线程1
}

// 线程2
synchronized(lock) {  
    // 偏向撤销 → 升级为轻量级锁（00）
    // CAS 竞争锁
}

// 线程1
synchronized(lock) {  
    // 轻量级锁，CAS 尝试获取
}
```

**性能**：较好，通过 CAS 避免阻塞

### 案例3：多线程高竞争

```java
// 10个线程同时竞争
for (int i = 0; i < 10; i++) {
    new Thread(() -> {
        synchronized(lock) {  
            // 1. 第一个线程：偏向锁
            // 2. 第二个线程：升级为轻量级锁
            // 3. 自旋失败：膨胀为重量级锁（10）
            // 4. 后续线程：直接阻塞在 _EntryList
        }
    }).start();
}
```

**性能**：下降，涉及线程阻塞/唤醒开销

## 关键代码位置（HotSpot）

```cpp
// 偏向锁撤销
BiasedLocking::revoke_and_rebias()

// 轻量级锁加锁
ObjectSynchronizer::slow_enter()

// 膨胀为重量级锁
ObjectSynchronizer::inflate()

// 重量级锁加锁
ObjectMonitor::enter()
```

## 答题总结

synchronized 锁升级的完整流程：

1. **无锁 → 偏向锁**：
   - 首次访问通过 CAS 写入线程 ID
   - 后续重入无需任何操作（最快）

2. **偏向锁 → 轻量级锁**：
   - 其他线程竞争时触发偏向撤销
   - 在栈帧中创建 Lock Record，通过 CAS 竞争

3. **轻量级锁 → 重量级锁**：
   - 自旋失败或竞争激烈时触发膨胀
   - 依赖 Monitor 对象和操作系统互斥量
   - 线程阻塞在 `_EntryList`

**设计思想**：用空间换时间，根据竞争程度自适应调整，在性能和功能之间取得平衡。

