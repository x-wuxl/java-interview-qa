---
layout: post
title: "父子线程之间怎么共享、传递数据？"
date: 2025-11-02
description: "深入讲解父子线程数据传递的实现方式，包括InheritableThreadLocal原理及线程池场景的注意事项"
author: "wuxl"
categories: [并发编程]
tags: [InheritableThreadLocal, 线程传递, 父子线程, ThreadLocal]
---

## 问题

父子线程之间怎么共享、传递数据？

## 答案

### 核心概念

**父子线程**指创建线程（父线程）与被创建线程（子线程）的关系。普通ThreadLocal无法在父子线程间共享数据，需要使用**InheritableThreadLocal**。

### 方案对比

| 方案 | 适用场景 | 优缺点 |
|------|---------|--------|
| **共享对象引用** | 简单场景 | ✅简单直接<br>❌需要考虑线程安全 |
| **InheritableThreadLocal** | new Thread()场景 | ✅自动继承<br>❌线程池场景失效 |
| **TransmittableThreadLocal** | 线程池场景 | ✅线程池可用<br>❌需要引入外部库 |

### 方案一：共享对象引用

**原理**：直接传递共享对象给子线程，通过锁或线程安全类保证并发安全。

```java
public class SharedDataDemo {
    public static void main(String[] args) {
        // 使用线程安全的容器
        ConcurrentHashMap<String, String> sharedMap = new ConcurrentHashMap<>();
        sharedMap.put("userId", "10001");

        // 父线程
        Thread parentThread = Thread.currentThread();
        System.out.println("父线程: " + sharedMap.get("userId"));

        // 子线程（传递引用）
        new Thread(() -> {
            System.out.println("子线程读取: " + sharedMap.get("userId"));
            sharedMap.put("userId", "10002");  // 修改共享数据
        }).start();

        // 等待子线程执行
        try { Thread.sleep(100); } catch (InterruptedException e) {}
        System.out.println("父线程读取修改后的值: " + sharedMap.get("userId"));
    }
}

// 输出：
// 父线程: 10001
// 子线程读取: 10001
// 父线程读取修改后的值: 10002
```

**缺点**：
- 需要显式传递对象引用
- 必须考虑线程安全（使用锁或并发容器）
- 不适合复杂的上下文传递

### 方案二：InheritableThreadLocal（推荐）

**原理**：子线程创建时会自动复制父线程的InheritableThreadLocal变量。

#### 基本使用

```java
public class InheritableThreadLocalDemo {
    // 使用InheritableThreadLocal替代ThreadLocal
    private static InheritableThreadLocal<String> context = new InheritableThreadLocal<>();

    public static void main(String[] args) throws InterruptedException {
        // 父线程设置值
        context.set("父线程的数据");
        System.out.println("父线程: " + context.get());

        // 创建子线程
        Thread childThread = new Thread(() -> {
            System.out.println("子线程读取: " + context.get());  // 自动继承父线程的值

            // 子线程修改不影响父线程
            context.set("子线程修改后的数据");
            System.out.println("子线程修改后: " + context.get());
        });
        childThread.start();
        childThread.join();

        System.out.println("父线程值未变: " + context.get());
    }
}

// 输出：
// 父线程: 父线程的数据
// 子线程读取: 父线程的数据
// 子线程修改后: 子线程修改后的数据
// 父线程值未变: 父线程的数据
```

#### 实现原理

**核心源码分析**：

```java
public class Thread {
    // 普通ThreadLocal存储在这里
    ThreadLocal.ThreadLocalMap threadLocals = null;

    // InheritableThreadLocal存储在这里
    ThreadLocal.ThreadLocalMap inheritableThreadLocals = null;
}

public class InheritableThreadLocal<T> extends ThreadLocal<T> {
    // 重写getMap方法，返回inheritableThreadLocals而非threadLocals
    ThreadLocalMap getMap(Thread t) {
        return t.inheritableThreadLocals;
    }

    void createMap(Thread t, T firstValue) {
        t.inheritableThreadLocals = new ThreadLocalMap(this, firstValue);
    }

    // 子类可重写此方法自定义继承逻辑（默认直接复制引用）
    protected T childValue(T parentValue) {
        return parentValue;
    }
}
```

**线程初始化时的继承逻辑**：

```java
// Thread构造方法（简化版）
public Thread(Runnable target) {
    Thread parent = currentThread();  // 获取父线程

    // 如果父线程有inheritableThreadLocals，则复制给子线程
    if (parent.inheritableThreadLocals != null) {
        this.inheritableThreadLocals =
            ThreadLocal.createInheritedMap(parent.inheritableThreadLocals);
    }
}

// ThreadLocal.createInheritedMap方法
static ThreadLocalMap createInheritedMap(ThreadLocalMap parentMap) {
    return new ThreadLocalMap(parentMap);  // 复制父线程的Map
}

// ThreadLocalMap的复制构造方法
private ThreadLocalMap(ThreadLocalMap parentMap) {
    Entry[] parentTable = parentMap.table;
    int len = parentTable.length;
    setThreshold(len);
    table = new Entry[len];

    for (int j = 0; j < len; j++) {
        Entry e = parentTable[j];
        if (e != null) {
            ThreadLocal<Object> key = (ThreadLocal<Object>) e.get();
            if (key != null) {
                // 调用childValue方法（可自定义）
                Object value = key.childValue(e.value);
                Entry c = new Entry(key, value);
                table[...] = c;  // 存入子线程的Map
            }
        }
    }
}
```

**继承时机**：
- 在`new Thread()`时触发，子线程**创建时**复制父线程的值
- 父线程后续修改不影响已创建的子线程

#### 自定义继承逻辑

**场景**：需要深拷贝对象，避免父子线程共享同一对象引用。

```java
public class CustomInheritableThreadLocal<T> extends InheritableThreadLocal<T> {
    @Override
    protected T childValue(T parentValue) {
        // 深拷贝（示例：序列化方式）
        if (parentValue instanceof Serializable) {
            return deepCopy(parentValue);
        }
        return parentValue;
    }

    private T deepCopy(T obj) {
        // 使用序列化实现深拷贝（生产环境建议使用专业库）
        try {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            ObjectOutputStream oos = new ObjectOutputStream(bos);
            oos.writeObject(obj);

            ByteArrayInputStream bis = new ByteArrayInputStream(bos.toByteArray());
            ObjectInputStream ois = new ObjectInputStream(bis);
            return (T) ois.readObject();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}

// 使用
CustomInheritableThreadLocal<User> userContext = new CustomInheritableThreadLocal<>();
userContext.set(new User("张三", 25));

new Thread(() -> {
    User user = userContext.get();  // 获取的是深拷贝对象
    user.setAge(30);  // 修改不影响父线程
}).start();
```

### 线程池场景的问题

**核心问题**：InheritableThreadLocal只在线程**创建时**复制，线程池中的线程会被复用，导致值不更新。

```java
public class ThreadPoolProblem {
    private static InheritableThreadLocal<String> context = new InheritableThreadLocal<>();

    public static void main(String[] args) throws InterruptedException {
        ExecutorService executor = Executors.newFixedThreadPool(1);

        // 第一次任务
        context.set("任务1的上下文");
        executor.execute(() -> {
            System.out.println("任务1读取: " + context.get());  // 输出: 任务1的上下文
        });

        Thread.sleep(100);

        // 第二次任务（复用同一个线程）
        context.set("任务2的上下文");
        executor.execute(() -> {
            System.out.println("任务2读取: " + context.get());  // 输出: 任务1的上下文（错误！）
        });

        executor.shutdown();
    }
}
```

**原因**：
1. 线程池中的线程在第一次创建时复制了"任务1的上下文"
2. 线程被复用执行任务2时，不会再次复制
3. 导致任务2读取到的是旧值

**解决方案**：使用TransmittableThreadLocal（阿里开源）

```java
// 引入依赖
// <dependency>
//   <groupId>com.alibaba</groupId>
//   <artifactId>transmittable-thread-local</artifactId>
// </dependency>

TransmittableThreadLocal<String> context = new TransmittableThreadLocal<>();

// 包装线程池
ExecutorService executor = TtlExecutors.getTtlExecutorService(
    Executors.newFixedThreadPool(10)
);

// 或使用装饰器包装Runnable
executor.execute(TtlRunnable.get(() -> {
    System.out.println(context.get());  // 正确获取当前任务的上下文
}));
```

### 实际应用场景

**1. 分布式追踪TraceId传递**：

```java
public class TraceContext {
    private static InheritableThreadLocal<String> traceId = new InheritableThreadLocal<>();

    public static void setTraceId(String id) {
        traceId.set(id);
    }

    public static String getTraceId() {
        return traceId.get();
    }
}

// 主线程
TraceContext.setTraceId("TRACE-12345");
logService.log("主线程操作");  // [TRACE-12345] 主线程操作

// 子线程自动继承TraceId
new Thread(() -> {
    logService.log("子线程操作");  // [TRACE-12345] 子线程操作
}).start();
```

**2. 用户上下文传递**：

```java
InheritableThreadLocal<User> userContext = new InheritableThreadLocal<>();

// 主线程
userContext.set(currentUser);

// 异步任务中访问用户信息
new Thread(() -> {
    User user = userContext.get();  // 自动获取父线程的用户信息
    orderService.createOrder(user.getId());
}).start();
```

### 注意事项

| 注意点 | 说明 |
|--------|------|
| **值的复制时机** | 子线程创建时复制，父线程后续修改不影响子线程 |
| **默认浅拷贝** | 父子线程共享同一对象引用，需要重写childValue实现深拷贝 |
| **线程池场景失效** | 线程复用导致不会重新复制，需使用TransmittableThreadLocal |
| **内存泄漏风险** | 同ThreadLocal，必须调用remove()清理 |
| **不适合频繁创建线程** | 每次创建线程都会复制Map，有一定开销 |

### 面试答题要点

1. **核心机制**：InheritableThreadLocal在子线程创建时自动复制父线程的值
2. **实现原理**：Thread对象维护inheritableThreadLocals字段，构造方法中复制父线程的Map
3. **线程池问题**：线程复用导致不会重新复制，需使用TransmittableThreadLocal
4. **适用场景**：分布式追踪TraceId传递、用户上下文传递、权限信息传递
5. **最佳实践**：new Thread()场景用InheritableThreadLocal，线程池场景用TransmittableThreadLocal
