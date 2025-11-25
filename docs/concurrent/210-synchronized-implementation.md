---
layout: default
title: "synchronized是怎么实现的？"
parent: 并发编程
nav_order: 210
description: "深入解析synchronized的底层实现原理，包括字节码指令、对象头结构和monitor机制"
date: 2025-11-02
---
# synchronized是怎么实现的？

## 核心概念

`synchronized` 是 Java 提供的内置锁机制，通过 JVM 底层的 **Monitor（管程）** 实现互斥访问。它在字节码层面通过 **monitorenter** 和 **monitorexit** 指令，以及对象头中的 **Mark Word** 来实现同步控制。

## 实现原理

### 1. 字节码层面

**同步代码块**：
```java
synchronized(obj) {
    // 临界区代码
}
```

编译后的字节码：
```
monitorenter  // 获取锁
// ... 业务代码
monitorexit   // 释放锁（正常退出）
monitorexit   // 释放锁（异常退出）
```

**同步方法**：
```java
public synchronized void method() {
    // 方法体
}
```

通过方法访问标志 `ACC_SYNCHRONIZED` 标识，JVM 在方法调用时隐式执行加锁/解锁。

### 2. 对象头与 Mark Word

每个 Java 对象在内存中包含：
- **Mark Word**（8字节，64位JVM）：存储锁状态、GC年龄、哈希码等
- **Class Pointer**（类型指针）
- **数组长度**（若为数组对象）

Mark Word 的锁状态标记：

| 锁状态   | 标志位 | 存储内容                    |
|----------|--------|----------------------------|
| 无锁     | 01     | 对象哈希码、GC分代年龄       |
| 偏向锁   | 01     | 线程ID、Epoch、GC分代年龄   |
| 轻量级锁 | 00     | 指向栈中锁记录的指针         |
| 重量级锁 | 10     | 指向Monitor对象的指针        |
| GC标记   | 11     | 空（不需要额外信息）         |

### 3. Monitor 对象结构

当升级为重量级锁时，依赖操作系统的 **Mutex Lock（互斥量）**：

```
ObjectMonitor {
    _owner       // 持有锁的线程
    _WaitSet     // 调用 wait() 的线程队列
    _EntryList   // 等待获取锁的线程队列
    _recursions  // 重入次数
    _count       // 计数器
}
```

## 关键实现细节

1. **monitorenter**：
   - 如果 Monitor 计数器为 0，线程进入并设置为持有者
   - 如果当前线程已持有，计数器加 1（可重入）
   - 如果被其他线程持有，进入 `_EntryList` 阻塞

2. **monitorexit**：
   - 计数器减 1
   - 当计数器为 0 时释放锁，唤醒 `_EntryList` 中的线程

3. **异常保证**：编译器生成两个 `monitorexit`，确保异常时也能释放锁

## 答题总结

- **字节码**：通过 `monitorenter`/`monitorexit` 指令或 `ACC_SYNCHRONIZED` 标志
- **对象头**：利用 Mark Word 存储锁状态和线程信息
- **Monitor**：重量级锁依赖操作系统互斥量，管理 `_owner`、`_EntryList`、`_WaitSet`
- **可重入**：通过计数器 `_recursions` 记录重入次数

这种设计既保证了线程安全，又通过锁优化（偏向锁、轻量级锁）减少性能开销。

