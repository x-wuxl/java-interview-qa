---
layout: default
title: "JVM如何判断对象是否存活？"
parent: JVM
nav_order: 126
description: "深入解析JVM判断对象存活的两种算法：引用计数法和可达性分析法，以及垃圾回收的工作原理"
author: "wuxl"
date: 2025-11-01
---
## 问题

JVM如何判断对象是否存活？

## 答案

### 核心概念

JVM判断对象是否存活主要有两种算法：**引用计数法（Reference Counting）**和**可达性分析法（Reachability Analysis）**。现代JVM主要使用可达性分析法，因为它能够解决循环引用等复杂情况下的对象存活判断问题。

### 引用计数法

#### 1. 基本原理

**引用计数法**为每个对象维护一个引用计数器，当有引用指向对象时计数器+1，引用失效时计数器-1，计数器为0时对象可被回收。

```java
// 简化的引用计数法示例
public class ReferenceCountingExample {
    public static void main(String[] args) {
        Object obj = new Object(); // obj引用计数 = 1

        Object ref1 = obj;        // obj引用计数 = 2
        Object ref2 = obj;        // obj引用计数 = 3

        ref1 = null;             // obj引用计数 = 2
        ref2 = null;             // obj引用计数 = 1

        obj = null;              // obj引用计数 = 0，可回收
    }
}
```

#### 2. 循环引用问题

引用计数法的主要缺点是无法处理循环引用：

```java
public class CircularReferenceProblem {
    static class Node {
        Node next;
        String name;

        public Node(String name) {
            this.name = name;
        }
    }

    public static void demonstrateCircularReference() {
        Node nodeA = new Node("A"); // nodeA引用计数 = 1
        Node nodeB = new Node("B"); // nodeB引用计数 = 1

        nodeA.next = nodeB;         // nodeB引用计数 = 2
        nodeB.next = nodeA;         // nodeA引用计数 = 2

        nodeA = null;               // nodeA引用计数 = 1
        nodeB = null;               // nodeB引用计数 = 1

        // 此时两个对象都无法访问，但引用计数都不为0
        // 引用计数法无法回收这些对象，造成内存泄漏
    }
}
```

### 可达性分析法

#### 1. 基本原理

**可达性分析法**从一系列称为"**GC Roots**"的根对象开始，沿着引用链搜索，能被访问到的对象为存活对象，不可达的对象为可回收对象。

```java
public class ReachabilityAnalysisExample {
    // GC Roots 包括：
    // 1. 虚拟机栈中引用的对象
    public static void stackReferences() {
        Object localObj = new Object(); // 局部变量，GC Root
        processObject(localObj);
    }

    // 2. 方法区中静态属性引用的对象
    private static Object staticObj = new Object(); // 静态变量，GC Root

    // 3. 方法区中常量引用的对象
    private static final String CONSTANT = "Hello"; // 常量，GC Root

    // 4. JNI引用的对象
    private native Object getNativeObject(); // Native方法引用，GC Root

    public static void processObject(Object obj) {
        // obj可以被stackReferences中的localObj访问到，因此存活
    }
}
```

#### 2. GC Roots 详细说明

```java
public class GCRrootsExample {
    // 1. 静态变量引用
    private static List<Object> staticList = new ArrayList<>();

    // 2. 常量引用
    private static final String CONSTANT_STRING = "常量字符串";

    public static void main(String[] args) {
        // 3. 虚拟机栈引用（局部变量）
        Thread thread = Thread.currentThread();
        Object localVar = new Object();

        // 4. JNI引用（通过本地方法引用的对象）
        // nativeMethod(); // 调用本地方法可能创建JNI引用

        // 5. 正在运行的线程
        Runnable runnable = () -> {
            Object threadLocal = new Object(); // 线程栈中的引用
        };

        new Thread(runnable).start();

        // 从这些GC Roots开始，可达的对象都是存活的
        staticList.add(localVar); // localVar通过staticList可达
    }
}
```

#### 3. 可达性分析过程

```java
public class ReachabilityAnalysisProcess {
    static class Node {
        String name;
        List<Node> children = new ArrayList<>();

        public Node(String name) {
            this.name = name;
        }

        public void addChild(Node child) {
            children.add(child);
        }
    }

    public static void analyzeReachability() {
        // 构建对象引用图
        Node root = new Node("Root");           // GC Root
        Node child1 = new Node("Child1");
        Node child2 = new Node("Child2");
        Node grandChild = new Node("GrandChild");

        // 建立引用关系
        root.addChild(child1);
        root.addChild(child2);
        child1.addChild(grandChild);

        // 设置引用为null，断开某些可达路径
        child2 = null; // child2仍通过root可达，不会被回收

        // 可达性分析结果：
        // Root -> Child1 -> GrandChild (可达)
        // Root -> Child2 (可达)
        // 所有对象都可达，不会被回收
    }

    public static void unreachableObjects() {
        Node root = new Node("Root");
        Node isolated = new Node("Isolated"); // 未被任何GC Root引用

        // 可达性分析结果：
        // Root: 可达 (GC Root直接引用)
        // Isolated: 不可达 (没有任何引用路径到达GC Root)
        // Isolated将被标记为可回收
    }
}
```

### 垃圾回收算法详解

#### 1. 标记-清除算法（Mark-Sweep）

```java
public class MarkSweepAlgorithm {
    public static void demonstrateMarkSweep() {
        // 第一阶段：标记
        // 1. 从GC Roots开始遍历，标记所有可达对象
        List<Object> reachableObjects = new ArrayList<>();
        markReachableObjects(getGCRoots(), reachableObjects);

        // 第二阶段：清除
        // 2. 遍历堆内存，回收未标记的对象
        sweepUnmarkedObjects(reachableObjects);
    }

    private static void markReachableObjects(List<Object> roots, List<Object> reachable) {
        // 深度优先搜索或广度优先搜索
        for (Object root : roots) {
            if (!reachable.contains(root)) {
                reachable.add(root);
                // 递归标记root引用的所有对象
                markReferences(root, reachable);
            }
        }
    }

    private static void markReferences(Object obj, List<Object> reachable) {
        // 标记对象引用的所有子对象
        // 实际实现会遍历对象的字段，递归标记引用的对象
    }

    private static void sweepUnmarkedObjects(List<Object> reachable) {
        // 回收所有不在reachable列表中的对象
    }
}
```

#### 2. 复制算法（Copying）

```java
public class CopyingAlgorithm {
    public static void demonstrateCopying() {
        // 将内存分为两个区域：From Space和To Space
        MemorySpace fromSpace = new MemorySpace("From");
        MemorySpace toSpace = new MemorySpace("To");

        // 只在From Space中分配对象
        allocateInFromSpace(fromSpace);

        // GC过程：
        // 1. 从GC Roots开始，标记存活对象
        List<Object> liveObjects = findLiveObjects();

        // 2. 将存活对象复制到To Space
        for (Object obj : liveObjects) {
            Object copied = copyObject(toSpace, obj);
            updateReference(obj, copied); // 更新引用
        }

        // 3. 交换From Space和To Space
        swapSpaces(fromSpace, toSpace);

        // 4. 清空原来的From Space（现在是To Space）
        toSpace.clear();
    }
}
```

#### 3. 标记-整理算法（Mark-Compact）

```java
public class MarkCompactAlgorithm {
    public static void demonstrateMarkCompact() {
        // 第一阶段：标记（与标记-清除相同）
        List<Object> liveObjects = markLiveObjects();

        // 第二阶段：整理
        // 1. 计算每个存活对象的新位置
        Map<Object, Address> newPositions = calculateNewPositions(liveObjects);

        // 2. 移动对象到新位置
        for (Object obj : liveObjects) {
            Address newPos = newPositions.get(obj);
            moveObject(obj, newPos);
        }

        // 3. 更新所有引用指向新位置
        updateAllReferences(newPositions);

        // 4. 更新内存分配指针
        updateAllocationPointer();
    }
}
```

### 对象的最终状态

#### 1. 对象的死亡过程

```java
public class ObjectFinalization {
    static class ResourceHolder {
        private Resource resource;

        public ResourceHolder(Resource resource) {
            this.resource = resource;
        }

        // finalize()方法（已废弃，不推荐使用）
        @Override
        protected void finalize() throws Throwable {
            try {
                System.out.println("Finalizing ResourceHolder");
                if (resource != null) {
                    resource.close();
                    resource = null;
                }
            } finally {
                super.finalize();
            }
        }
    }

    public static void demonstrateFinalization() {
        ResourceHolder holder = new ResourceHolder(new Resource());

        holder = null; // 对象变为不可达

        // 1. 对象被标记为不可达
        // 2. 如果对象有finalize()方法，会被加入F-Queue队列
        // 3. Finalizer线程执行finalize()方法
        // 4. 如果finalize()执行后对象仍不可达，对象被真正回收
    }
}
```

#### 2. 引用队列与软引用、弱引用

```java
public class ReferenceTypes {
    public static void demonstrateReferenceTypes() {
        // 软引用：内存不足时才回收
        ReferenceQueue<Object> softQueue = new ReferenceQueue<>();
        SoftReference<Object> softRef = new SoftReference<>(new Object(), softQueue);

        // 弱引用：下次GC时就回收
        ReferenceQueue<Object> weakQueue = new ReferenceQueue<>();
        WeakReference<Object> weakRef = new WeakReference<>(new Object(), weakQueue);

        // 虚引用：无法通过虚引用获取对象，用于跟踪对象回收
        ReferenceQueue<Object> phantomQueue = new ReferenceQueue<>();
        PhantomReference<Object> phantomRef = new PhantomReference<>(new Object(), phantomQueue);

        // 可以通过引用队列监控对象回收状态
        monitorReferenceQueues(softQueue, weakQueue, phantomQueue);
    }
}
```

### 性能优化考虑

#### 1. 减少GC压力的编程技巧

```java
public class GCOptimization {
    // 1. 避免创建不必要的对象
    public String badPractice(String prefix, String suffix) {
        StringBuilder sb = new StringBuilder(); // 每次调用都创建新对象
        sb.append(prefix).append(suffix);
        return sb.toString();
    }

    public String goodPractice(String prefix, String suffix) {
        return prefix + suffix; // 可能被编译器优化，减少对象创建
    }

    // 2. 重用对象
    private static final DateFormat DATE_FORMAT = new SimpleDateFormat("yyyy-MM-dd");

    public String formatDate(Date date) {
        return DATE_FORMAT.format(date); // 重用DateFormat对象
    }

    // 3. 使用对象池
    private static final ObjectPool<StringBuilder> BUILDER_POOL = new ObjectPool<>();

    public String processWithPool(List<String> items) {
        StringBuilder builder = BUILDER_POOL.acquire();
        try {
            for (String item : items) {
                builder.append(item);
            }
            return builder.toString();
        } finally {
            BUILDER_POOL.release(builder); // 重用StringBuilder
        }
    }
}
```

### 面试要点总结

1. **两种算法**：引用计数法（有循环引用问题）vs 可达性分析法（现代JVM使用）
2. **GC Roots**：虚拟机栈、静态变量、常量、JNI引用、运行线程等
3. **垃圾回收算法**：标记-清除、复制算法、标记-整理
4. **对象死亡过程**：不可达 → 标记 → 回收（可能经过finalize）
5. **优化技巧**：减少对象创建、重用对象、合理使用引用类型
6. **性能影响**：STW（Stop-The-World）、内存碎片、复制开销

**关键理解**：
- 可达性分析是判断对象存活的根本方法
- GC Roots确定分析起点，避免回收正在使用的对象
- 不同GC算法有不同的性能特征和适用场景
- 合理的编程实践可以显著减少GC压力

**实际应用**：
- 理解GC原理有助于编写内存友好的代码
- 可以通过GC日志分析内存使用情况
- 选择合适的GC策略提升应用性能
- 避免内存泄漏和过度创建对象

这个知识点是JVM内存管理的核心，对于性能调优和问题诊断都非常重要。