---
layout: default
title: "AQS为什么采用双向链表？"
parent: 并发编程
nav_order: 227
description: "分析AQS同步队列采用双向链表而非单向链表的设计原因与优势"
author: "wuxl"
date: 2025-11-02
---
## 问题

AQS为什么采用双向链表？

## 答案

### 1. 核心原因

AQS 的同步队列采用**双向链表**（每个节点有 `prev` 和 `next` 指针）而非单向链表，主要基于以下设计考量：

1. **支持节点的快速取消**
2. **简化超时和中断的处理逻辑**
3. **保证 CAS 操作的原子性和一致性**
4. **支持从尾到头的遍历**

虽然这增加了一点内存开销，但带来了更简洁的并发控制和更好的可靠性。

### 2. 双向链表的数据结构

```java
static final class Node {
    volatile Node prev;    // 前驱指针
    volatile Node next;    // 后继指针
    volatile Thread thread;
    volatile int waitStatus;
}

// AQS 中的头尾指针
private transient volatile Node head;
private transient volatile Node tail;
```

### 3. 为什么需要双向链表

#### 3.1 节点取消需要向前查找

当一个线程由于超时或中断需要取消等待时，必须将自己从队列中移除：

```java
// 取消节点的操作（简化版）
private void cancelAcquire(Node node) {
    if (node == null)
        return;

    node.thread = null;  // 清除线程引用

    // 跳过前面已取消的节点
    Node pred = node.prev;
    while (pred.waitStatus > 0)  // CANCELLED 状态
        node.prev = pred = pred.prev;  // 需要向前遍历

    Node predNext = pred.next;

    // 设置当前节点为取消状态
    node.waitStatus = Node.CANCELLED;

    // 如果是尾节点，直接移除
    if (node == tail && compareAndSetTail(node, pred)) {
        compareAndSetNext(pred, predNext, null);
    } else {
        int ws;
        // 需要维护前驱和后继的关系
        if (pred != head &&
            ((ws = pred.waitStatus) == Node.SIGNAL ||
             (ws <= 0 && compareAndSetWaitStatus(pred, ws, Node.SIGNAL))) &&
            pred.thread != null) {
            Node next = node.next;
            if (next != null && next.waitStatus <= 0)
                compareAndSetNext(pred, predNext, next);  // 前驱跳过当前节点
        } else {
            unparkSuccessor(node);
        }

        node.next = node;  // 帮助 GC
    }
}
```

**关键点**：
- 取消节点时需要向前查找有效的前驱节点（`node.prev`）
- 单向链表无法高效向前遍历，必须从头开始搜索
- 双向链表可以直接通过 `prev` 指针快速定位

#### 3.2 唤醒后继节点时需要向前查找

当释放锁唤醒后继节点时，如果下一个节点已被取消，需要向前查找有效节点：

```java
private void unparkSuccessor(Node node) {
    int ws = node.waitStatus;
    if (ws < 0)
        compareAndSetWaitStatus(node, ws, 0);

    Node s = node.next;

    // 如果下一个节点为空或已取消
    if (s == null || s.waitStatus > 0) {
        s = null;
        // 从尾部向前查找有效节点
        for (Node t = tail; t != null && t != node; t = t.prev)
            if (t.waitStatus <= 0)
                s = t;  // 找到最靠前的有效节点
    }

    if (s != null)
        LockSupport.unpark(s.thread);
}
```

**为什么从后向前遍历？**
- **原因**：在并发环境下，节点的 `next` 指针可能尚未设置完成，但 `prev` 指针一定已经设置
- **入队过程**：
  ```java
  node.prev = pred;                        // 1. 先设置 prev（已生效）
  compareAndSetTail(pred, node);           // 2. CAS 设置尾节点
  pred.next = node;                        // 3. 后设置 next（可能延迟）
  ```
- **时间窗口问题**：在步骤 2 和步骤 3 之间，`pred.next` 可能还未设置，但 `node.prev` 已经有效
- **从后向前遍历**：使用 `tail.prev.prev...` 总能找到所有已入队的节点

#### 3.3 CAS 操作的一致性保证

双向链表配合 CAS 操作，保证入队和出队的原子性：

```java
// 入队操作
private Node enq(final Node node) {
    for (;;) {
        Node t = tail;
        if (t == null) {
            if (compareAndSetHead(new Node()))
                tail = head;
        } else {
            node.prev = t;  // 1. 先设置 prev
            if (compareAndSetTail(t, node)) {  // 2. CAS 设置 tail
                t.next = node;  // 3. 再设置 next
                return t;
            }
        }
    }
}
```

**关键点**：
- `prev` 指针先设置，保证 `compareAndSetTail` 成功后，新节点一定有有效的前驱
- 即使 `next` 指针设置延迟，通过 `prev` 也能完整遍历队列
- 这是双向链表的核心优势：**在并发环境下提供更强的一致性保证**

#### 3.4 超时和中断处理

线程在等待锁时可能被中断或超时：

```java
// 可中断获取锁
public final void acquireInterruptibly(int arg) throws InterruptedException {
    if (Thread.interrupted())
        throw new InterruptedException();
    if (!tryAcquire(arg))
        doAcquireInterruptibly(arg);  // 可能需要取消节点
}

// 超时获取锁
public final boolean tryAcquireNanos(int arg, long nanosTimeout)
        throws InterruptedException {
    if (Thread.interrupted())
        throw new InterruptedException();
    return tryAcquire(arg) ||
           doAcquireNanos(arg, nanosTimeout);  // 可能需要取消节点
}
```

这些场景都需要：
1. 快速定位前驱节点
2. 将自己从队列中移除
3. 维护前驱和后继的链接关系

**单向链表的问题**：无法快速定位前驱，只能从头遍历，效率低且实现复杂。

### 4. 单向链表的问题

如果使用单向链表，会面临以下问题：

```java
// 假设只有 next 指针
static final class Node {
    volatile Node next;  // 只有后继指针
    volatile Thread thread;
    volatile int waitStatus;
}
```

**问题 1：取消节点时无法快速定位前驱**
```java
// 需要从 head 开始遍历找到前驱
Node pred = head;
while (pred.next != node) {
    pred = pred.next;  // O(n) 复杂度
}
pred.next = node.next;  // 移除节点
```

**问题 2：并发环境下链表可能断裂**
- 多个线程同时取消节点时，`next` 指针的修改可能相互覆盖
- 缺少 `prev` 指针的反向验证机制，难以保证一致性

**问题 3：无法从尾到头遍历**
- `unparkSuccessor` 中无法从 `tail` 向前查找有效节点
- 必须从 `head` 开始遍历，效率低下

### 5. 双向链表的优势总结

| 特性 | 双向链表 | 单向链表 |
|------|---------|---------|
| **节点取消** | O(1) 定位前驱 | O(n) 从头遍历 |
| **唤醒后继** | 可从尾部向前查找有效节点 | 只能从头部向后查找 |
| **并发一致性** | `prev` 指针先设置，提供强一致性 | 并发环境下易出错 |
| **超时/中断处理** | 快速移除节点并维护链表 | 实现复杂且效率低 |
| **内存开销** | 每个节点多一个指针（约 8 字节） | 节省 8 字节 |

### 6. CLH 队列变体

AQS 的同步队列是 **CLH（Craig, Landin, and Hagersten）队列的变体**：

**原始 CLH 队列**：
- 单向链表，每个节点自旋检查前驱节点的状态
- 适用于共享内存的自旋锁

**AQS 的改进**：
- **双向链表**：支持节点取消和反向遍历
- **结合阻塞**：自旋 + LockSupport.park() 降低 CPU 消耗
- **显式前驱指针**：简化并发控制逻辑

### 7. 性能考量

**内存开销**：
- 每个 Node 多一个 `prev` 指针，约增加 8 字节（64 位 JVM）
- 但考虑到等待队列通常不会很长，且节点会快速释放，这点开销可以接受

**操作效率**：
- 节点取消：从 O(n) 优化到 O(1)
- 唤醒后继：在并发环境下更可靠
- 超时/中断处理：更简洁高效

### 8. 总结

AQS 采用双向链表的核心原因：

1. **支持节点取消**：通过 `prev` 快速定位前驱节点，O(1) 时间复杂度移除节点
2. **保证并发一致性**：`prev` 指针先设置，即使 `next` 指针延迟，也能完整遍历队列
3. **支持反向遍历**：唤醒后继节点时，从 `tail` 向前查找有效节点，避免遗漏
4. **简化超时和中断处理**：快速维护队列结构，实现简洁可靠

虽然双向链表增加了少量内存开销，但极大地简化了并发控制逻辑，提高了系统的健壮性和性能，是 AQS 设计的精妙之处。

**面试要点**：
- 强调节点取消需要快速定位前驱（`prev` 指针）
- 说明并发环境下 `prev` 先设置的一致性保证
- 对比单向链表在取消和唤醒场景下的不足
- 提及 CLH 队列变体的设计思想
