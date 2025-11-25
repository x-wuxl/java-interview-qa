---
layout: default
title: "ArrayDeque和LinkedList作为队列的区别"
parent: 集合框架
nav_order: 105
description: "对比分析ArrayDeque和LinkedList在队列场景下的性能差异、内存开销及使用选择"
author: "wuxl"
date: 2025-11-02
---
## 问题

ArrayDeque和LinkedList作为队列的区别？

## 答案

### 1. 核心概念

`ArrayDeque` 和 `LinkedList` 都实现了 `Deque` 接口，都可以作为队列（Queue）和双端队列（Deque）使用。但两者在**底层实现、性能表现、内存占用**上存在显著差异。

**快速结论**：
- **ArrayDeque**：官方推荐的队列/双端队列实现，性能更优
- **LinkedList**：支持队列操作，但作为队列使用时性能较差

---

### 2. 底层实现差异

#### 2.1 数据结构

| 特性 | ArrayDeque | LinkedList |
|-----|-----------|-----------|
| **底层实现** | 动态循环数组 | 双向链表 |
| **存储方式** | 连续内存空间 | 分散的节点对象 |
| **容量** | 需要扩容（2倍增长） | 无容量限制 |
| **null 元素** | 不允许 | 允许 |

#### 2.2 ArrayDeque 的循环数组实现

```java
public class ArrayDeque<E> extends AbstractCollection<E> implements Deque<E> {
    transient Object[] elements;  // 存储元素的数组
    transient int head;           // 队头索引
    transient int tail;           // 队尾索引

    public ArrayDeque() {
        elements = new Object[16];  // 默认初始容量 16
    }
}
```

**循环数组原理**：
```
初始状态：[ _ _ _ _ _ _ _ _ ]
         head=0, tail=0

插入3个元素后：[a b c _ _ _ _ _ ]
              head=0, tail=3

从队头删除1个后：[ _ b c _ _ _ _ _ ]
                head=1, tail=3

循环使用：[ f g c d e _ _ _ ]
         head=2, tail=6 (逻辑上 tail 在 head 右侧)
```

#### 2.3 LinkedList 的双向链表实现

```java
public class LinkedList<E> extends AbstractSequentialList<E> implements Deque<E> {
    transient int size = 0;
    transient Node<E> first;  // 链表头节点
    transient Node<E> last;   // 链表尾节点

    private static class Node<E> {
        E item;
        Node<E> next;
        Node<E> prev;
    }
}
```

**链表节点结构**：
```
[prev|item|next] <-> [prev|item|next] <-> [prev|item|next]
  ↑                                              ↑
first                                          last
```

---

### 3. 性能对比

#### 3.1 时间复杂度

| 操作 | ArrayDeque | LinkedList | 说明 |
|-----|-----------|-----------|------|
| **添加到队尾** `offer()` | O(1) 摊销 | O(1) | ArrayDeque 可能触发扩容 |
| **从队头删除** `poll()` | O(1) | O(1) | 两者都是常量时间 |
| **查看队头** `peek()` | O(1) | O(1) | 直接访问 |
| **随机访问** `get(index)` | O(1) | O(n) | LinkedList 需要遍历 |
| **插入到中间** | O(n) | O(1)* | *需先定位到节点位置 |

#### 3.2 实际性能测试

```java
// 性能对比示例（100万次操作）
public class QueueBenchmark {
    public static void main(String[] args) {
        int n = 1_000_000;

        // ArrayDeque 测试
        long start = System.currentTimeMillis();
        Deque<Integer> arrayDeque = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            arrayDeque.offer(i);
        }
        for (int i = 0; i < n; i++) {
            arrayDeque.poll();
        }
        System.out.println("ArrayDeque: " + (System.currentTimeMillis() - start) + "ms");

        // LinkedList 测试
        start = System.currentTimeMillis();
        Deque<Integer> linkedList = new LinkedList<>();
        for (int i = 0; i < n; i++) {
            linkedList.offer(i);
        }
        for (int i = 0; i < n; i++) {
            linkedList.poll();
        }
        System.out.println("LinkedList: " + (System.currentTimeMillis() - start) + "ms");
    }
}
```

**典型结果**：
```
ArrayDeque: 45ms
LinkedList: 120ms
```

**ArrayDeque 更快的原因**：
1. **缓存友好**：连续内存访问利用 CPU 缓存
2. **无额外对象**：不需要为每个元素创建 Node 对象
3. **GC 压力小**：减少对象分配和回收

---

### 4. 内存占用对比

#### 4.1 内存开销分析

**ArrayDeque**：
- 只存储元素数组 + 两个索引（head/tail）
- 额外开销：`16 bytes`（对象头） + `8 bytes`（数组引用） + `8 bytes`（head + tail）
- 每个元素：`8 bytes`（引用）

**LinkedList**：
- 每个元素需要一个 Node 对象
- 每个 Node：`16 bytes`（对象头） + `8 bytes`（item） + `16 bytes`（prev + next）= `40 bytes`
- **内存开销是 ArrayDeque 的 5 倍**

#### 4.2 空间效率示例

存储 1000 个 Integer 对象：

```
ArrayDeque:
- 数组：1000 * 8 bytes = 8KB
- 总开销：约 8KB

LinkedList:
- 节点：1000 * 40 bytes = 40KB
- 总开销：约 40KB
```

---

### 5. 功能差异

| 特性 | ArrayDeque | LinkedList |
|-----|-----------|-----------|
| **实现接口** | Deque | List + Deque |
| **支持 null** | ❌ | ✅ |
| **随机访问** | 不支持（无 get(index)） | 支持（但效率低） |
| **线程安全** | ❌ | ❌ |
| **Iterator 删除** | 快速失败（fail-fast） | 快速失败（fail-fast） |

---

### 6. 使用场景选择

#### 6.1 优先使用 ArrayDeque 的场景

```java
// ✅ 场景1：纯队列/栈操作
Deque<String> queue = new ArrayDeque<>();
queue.offer("任务1");
queue.offer("任务2");
String task = queue.poll();

// ✅ 场景2：双端队列（滑动窗口算法）
Deque<Integer> window = new ArrayDeque<>();
window.offerLast(1);
window.offerFirst(0);
window.pollLast();

// ✅ 场景3：栈操作（替代 Stack）
Deque<Integer> stack = new ArrayDeque<>();
stack.push(1);
stack.push(2);
int top = stack.pop();
```

#### 6.2 使用 LinkedList 的场景

```java
// ✅ 场景1：需要存储 null 元素
Queue<String> queue = new LinkedList<>();
queue.offer(null);  // ArrayDeque 不支持

// ✅ 场景2：需要频繁在中间插入/删除（结合 ListIterator）
LinkedList<String> list = new LinkedList<>();
ListIterator<String> it = list.listIterator();
while (it.hasNext()) {
    if (condition) {
        it.add("新元素");  // 在当前位置插入
    }
}

// ✅ 场景3：需要同时实现 List 和 Queue 接口
List<String> list = new LinkedList<>();
Queue<String> queue = (Queue<String>) list;  // 同一个对象
```

---

### 7. 性能优化建议

#### 7.1 ArrayDeque 优化

```java
// 1. 预估容量，减少扩容次数
Deque<Integer> deque = new ArrayDeque<>(1024);  // 初始容量 2^n

// 2. 批量操作时复用对象
Deque<Task> taskQueue = new ArrayDeque<>();
// ... 使用后清空
taskQueue.clear();  // 复用数组，避免重新分配
```

#### 7.2 避免误用 LinkedList

```java
// ❌ 错误：用 LinkedList 做随机访问
List<String> list = new LinkedList<>();
for (int i = 0; i < list.size(); i++) {
    System.out.println(list.get(i));  // O(n²) 复杂度！
}

// ✅ 正确：使用迭代器
for (String s : list) {  // 使用迭代器，O(n)
    System.out.println(s);
}
```

---

### 8. 线程安全方案

```java
// 方案1：使用同步包装器
Queue<String> syncQueue = Collections.synchronizedDeque(new ArrayDeque<>());

// 方案2：使用并发队列
Queue<String> concurrentQueue = new ConcurrentLinkedQueue<>();  // 无界
BlockingQueue<String> blockingQueue = new LinkedBlockingQueue<>();  // 阻塞队列
```

---

### 答题总结

| 维度 | ArrayDeque | LinkedList |
|-----|-----------|-----------|
| **性能** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **内存** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **功能** | 队列/栈/双端队列 | List + 队列 |
| **推荐度** | ✅ 官方推荐 | ⚠️ 特定场景 |

**核心要点**：
1. **作为队列使用，优先选择 ArrayDeque**：性能更好（约 2-3 倍），内存占用更少
2. **LinkedList 的优势在于中间插入和存储 null**，但作为纯队列使用时无明显优势
3. **ArrayDeque 不支持 null 元素**，这是唯一的功能限制
4. 两者都非线程安全，并发场景需使用 `ConcurrentLinkedQueue` 或 `LinkedBlockingQueue`
