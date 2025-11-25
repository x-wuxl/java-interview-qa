---
layout: default
title: "CompletableFuture的底层是如何实现的？"
parent: 并发编程
nav_order: 248
description: "深入剖析CompletableFuture的底层实现原理，理解异步任务编排、回调链、异常处理等核心机制"
date: 2025-11-02
---
## 一、核心概念

`CompletableFuture` 是Java 8引入的异步编程工具，是对 `Future` 的增强，支持：
- **异步回调**：任务完成后自动触发回调
- **任务编排**：链式调用，组合多个异步操作
- **异常处理**：完善的异常传播机制
- **手动完成**：可以主动设置结果

---

## 二、与传统Future的对比

### 1. 传统Future的局限

```java
ExecutorService executor = Executors.newFixedThreadPool(10);

Future<String> future = executor.submit(() -> {
    Thread.sleep(2000);
    return "结果";
});

// 问题1：只能阻塞等待结果
String result = future.get();  // 阻塞2秒

// 问题2：无法设置回调
// 问题3：无法组合多个Future
// 问题4：异常处理不友好
```

### 2. CompletableFuture的优势

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    try { Thread.sleep(2000); } catch (InterruptedException e) {}
    return "结果";
});

// 优势1：非阻塞回调
future.thenAccept(result -> {
    System.out.println("收到结果：" + result);
});

// 优势2：链式调用
future
    .thenApply(r -> r + " 处理1")
    .thenApply(r -> r + " 处理2")
    .thenAccept(System.out::println);

// 优势3：异常处理
future
    .thenApply(this::process)
    .exceptionally(ex -> "默认值");

// 优势4：组合多个Future
CompletableFuture<String> future1 = ...;
CompletableFuture<String> future2 = ...;
CompletableFuture.allOf(future1, future2).join();
```

---

## 三、底层数据结构

### 1. 核心字段

```java
public class CompletableFuture<T> implements Future<T>, CompletionStage<T> {
    
    // 任务结果（成功或异常）
    volatile Object result;
    
    // 回调链表头节点
    volatile Completion stack;
    
    // 默认异步执行器
    private static final Executor asyncPool = useCommonPool ?
        ForkJoinPool.commonPool() : new ThreadPerTaskExecutor();
}
```

**关键点**：
- `result`：存储任务结果或异常（`AltResult`包装）
- `stack`：维护一个 **Completion链表**（栈结构），存储所有等待结果的回调

---

### 2. Completion 回调节点

```java
abstract static class Completion extends ForkJoinTask<Void> 
    implements Runnable, AsynchronousCompletionTask {
    
    volatile Completion next;  // 链表的下一个节点
    
    abstract CompletableFuture<?> tryFire(int mode);  // 触发回调
    abstract boolean isLive();
}

// 典型子类
static final class UniApply<T,V> extends UniCompletion<T,V> {
    Function<? super T,? extends V> fn;  // 转换函数
    
    final CompletableFuture<V> tryFire(int mode) {
        CompletableFuture<T> d = dep;
        CompletableFuture<V> f = this.src;
        
        Object r;
        if ((r = f.result) != null) {  // 依赖任务已完成
            // 执行fn.apply(r)，将结果设置到dep
            d.completeValue(fn.apply(r));
        }
        return d;
    }
}
```

**Completion类型**：
- `UniApply`：`thenApply` 的回调
- `UniAccept`：`thenAccept` 的回调
- `UniRun`：`thenRun` 的回调
- `BiApply`：`thenCombine` 的回调（依赖两个Future）
- `OrApply`：`applyToEither` 的回调（两个Future之一完成即触发）

---

### 3. 回调链表结构

```java
// 示例：future.thenApply(f1).thenApply(f2).thenAccept(f3)

CompletableFuture (原始)
    ↓
  result = null
  stack → UniApply(f1) → UniApply(f2) → UniAccept(f3) → null
                ↓              ↓              ↓
          新Future1       新Future2       新Future3

// 当原始Future完成时，依次触发stack链表中的Completion
```

---

## 四、核心方法实现原理

### 1. supplyAsync - 异步执行

```java
public static <U> CompletableFuture<U> supplyAsync(Supplier<U> supplier) {
    return asyncSupplyStage(asyncPool, supplier);
}

static <U> CompletableFuture<U> asyncSupplyStage(Executor e, Supplier<U> f) {
    CompletableFuture<U> d = new CompletableFuture<>();
    e.execute(new AsyncSupply<U>(d, f));  // 提交到线程池
    return d;
}

// AsyncSupply任务
static final class AsyncSupply<T> extends ForkJoinTask<Void> 
    implements Runnable, AsynchronousCompletionTask {
    
    CompletableFuture<T> dep;
    Supplier<T> fn;
    
    public void run() {
        try {
            T result = fn.get();  // 执行supplier
            dep.completeValue(result);  // 设置结果并触发回调链
        } catch (Throwable ex) {
            dep.completeThrowable(ex);  // 设置异常
        }
    }
}
```

**流程**：
1. 创建一个新的 `CompletableFuture` 对象
2. 将 `Supplier` 包装成 `AsyncSupply` 任务
3. 提交到线程池（默认ForkJoinPool.commonPool）
4. 任务执行完成后，调用 `completeValue` 设置结果并触发回调

---

### 2. thenApply - 转换结果

```java
public <U> CompletableFuture<U> thenApply(Function<? super T,? extends U> fn) {
    return uniApplyStage(null, fn);  // null表示在完成线程中同步执行
}

public <U> CompletableFuture<U> thenApplyAsync(Function<? super T,? extends U> fn) {
    return uniApplyStage(asyncPool, fn);  // 异步执行
}

private <V> CompletableFuture<V> uniApplyStage(
    Executor e, Function<? super T,? extends V> f) {
    
    CompletableFuture<V> d = new CompletableFuture<>();  // 新Future
    
    // 情况1：当前Future已完成
    if (result != null) {
        if (e != null) {
            e.execute(() -> d.completeValue(f.apply(result)));  // 异步执行
        } else {
            d.completeValue(f.apply(result));  // 同步执行
        }
    }
    // 情况2：当前Future未完成，添加回调到stack
    else {
        UniApply<T,V> c = new UniApply<>(e, d, this, f);
        push(c);  // 添加到回调链表
        c.tryFire(SYNC);  // 尝试立即执行（可能已完成）
    }
    
    return d;
}

// 推入回调栈
final void push(Completion c) {
    do {
        c.next = stack;  // CAS操作
    } while (!UNSAFE.compareAndSwapObject(this, STACK, c.next, c));
}
```

**关键点**：
- 如果当前Future **已完成**，直接执行转换函数
- 如果当前Future **未完成**，创建 `UniApply` 回调节点，推入 `stack` 链表
- 使用CAS操作保证线程安全（无锁）

---

### 3. complete - 设置结果并触发回调链

```java
public boolean complete(T value) {
    boolean triggered = completeValue(value);
    postComplete();  // 触发回调链
    return triggered;
}

final boolean completeValue(T t) {
    return UNSAFE.compareAndSwapObject(this, RESULT, null, 
        (t == null) ? NIL : t);  // CAS设置结果
}

// 触发回调链
final void postComplete() {
    CompletableFuture<?> f = this;
    Completion h;
    
    // 遍历stack链表，依次触发回调
    while ((h = f.stack) != null || (f != this && (h = (f = this).stack) != null)) {
        CompletableFuture<?> d;
        Completion t;
        
        // CAS移除头节点
        if (UNSAFE.compareAndSwapObject(f, STACK, h, t = h.next)) {
            if (t != null) {
                // 将next节点也加入栈（优化）
                UNSAFE.compareAndSwapObject(h, NEXT, t, null);
            }
            
            f = (d = h.tryFire(NESTED)) == null ? this : d;  // 触发回调
        }
    }
}
```

**流程**：
1. 使用CAS设置 `result` 字段
2. 遍历 `stack` 链表，依次触发每个 `Completion`
3. 每个 `Completion` 的 `tryFire` 方法会：
   - 获取依赖的Future的结果
   - 执行转换/消费函数
   - 设置新Future的结果
   - 递归触发下游回调

---

### 4. thenCombine - 组合两个Future

```java
public <U,V> CompletableFuture<V> thenCombine(
    CompletionStage<? extends U> other,
    BiFunction<? super T,? super U,? extends V> fn) {
    
    return biApplyStage(null, other, fn);
}

private <U,V> CompletableFuture<V> biApplyStage(
    Executor e, CompletionStage<U> o, BiFunction<T,U,V> f) {
    
    CompletableFuture<V> d = new CompletableFuture<>();
    CompletableFuture<U> other = o.toCompletableFuture();
    
    // 情况1：两个Future都已完成
    if (result != null && other.result != null) {
        d.completeValue(f.apply(result, other.result));
    }
    // 情况2：至少一个未完成，创建BiApply回调
    else {
        BiApply<T,U,V> c = new BiApply<>(e, d, this, other, f);
        
        // 同时添加到两个Future的回调链
        this.push(c);
        other.push(c);
        
        c.tryFire(SYNC);
    }
    
    return d;
}

// BiApply回调节点
static final class BiApply<T,U,V> extends BiCompletion<T,U,V> {
    BiFunction<? super T,? super U,? extends V> fn;
    
    final CompletableFuture<V> tryFire(int mode) {
        Object r, s;
        
        // 必须两个依赖都完成
        if ((r = src.result) != null && (s = snd.result) != null) {
            V result = fn.apply(r, s);  // 执行组合函数
            dep.completeValue(result);
        }
        
        return dep;
    }
}
```

**关键点**：
- `BiApply` 会被同时添加到两个Future的回调链
- 任一Future完成时，都会尝试触发 `tryFire`
- 只有当两个Future **都完成** 时，才真正执行组合函数

---

### 5. exceptionally - 异常处理

```java
public CompletableFuture<T> exceptionally(Function<Throwable, ? extends T> fn) {
    return uniExceptionallyStage(fn);
}

private CompletableFuture<T> uniExceptionallyStage(Function<Throwable, ? extends T> f) {
    CompletableFuture<T> d = new CompletableFuture<>();
    
    // 已完成
    if (result != null) {
        if (result instanceof AltResult) {  // 异常结果
            Throwable ex = ((AltResult) result).ex;
            try {
                d.completeValue(f.apply(ex));  // 执行异常处理函数
            } catch (Throwable ex2) {
                d.completeThrowable(ex2);
            }
        } else {
            d.completeValue(result);  // 正常结果，直接传递
        }
    }
    // 未完成，添加回调
    else {
        UniExceptionally<T> c = new UniExceptionally<>(d, this, f);
        push(c);
    }
    
    return d;
}

// 异常结果包装类
static final class AltResult {
    final Throwable ex;  // 存储异常
}
```

**异常传播机制**：
- 任务执行出现异常时，包装成 `AltResult` 存储在 `result`
- 后续的 `thenApply`、`thenAccept` 等不会执行，直接传递异常
- 遇到 `exceptionally` 或 `handle` 时，才处理异常

---

## 五、线程模型

### 1. 默认执行器

```java
private static final boolean useCommonPool =
    (ForkJoinPool.getCommonPoolParallelism() > 1);

private static final Executor asyncPool = useCommonPool ?
    ForkJoinPool.commonPool() : new ThreadPerTaskExecutor();

// 备用执行器（单核机器）
static final class ThreadPerTaskExecutor implements Executor {
    public void execute(Runnable r) {
        new Thread(r).start();  // 每个任务一个线程
    }
}
```

**执行模式**：
- `supplyAsync()` / `thenApplyAsync()`：使用 `asyncPool` 执行
- `thenApply()` / `thenAccept()`：在 **完成任务的线程** 中同步执行
- 可以自定义 `Executor`

### 2. 执行模式对比

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    System.out.println("Task: " + Thread.currentThread().getName());
    return "result";
});

// 同步模式：在完成future的线程中执行（可能是ForkJoinPool线程）
future.thenApply(r -> {
    System.out.println("ThenApply: " + Thread.currentThread().getName());
    return r.toUpperCase();
});

// 异步模式：提交到线程池异步执行
future.thenApplyAsync(r -> {
    System.out.println("ThenApplyAsync: " + Thread.currentThread().getName());
    return r.toUpperCase();
});

// 自定义执行器
Executor customExecutor = Executors.newFixedThreadPool(5);
future.thenApplyAsync(r -> {
    System.out.println("Custom: " + Thread.currentThread().getName());
    return r.toUpperCase();
}, customExecutor);
```

---

## 六、关键实现技巧

### 1. CAS无锁操作

```java
// 设置结果
UNSAFE.compareAndSwapObject(this, RESULT, null, value)

// 修改回调栈
UNSAFE.compareAndSwapObject(this, STACK, c.next, c)
```

**优势**：
- 避免加锁，提升性能
- 多线程安全地修改 `result` 和 `stack`

---

### 2. 栈式回调链（LIFO）

```java
// 添加回调时：后添加的在栈顶
push(completion1);  // stack → completion1 → null
push(completion2);  // stack → completion2 → completion1 → null

// 触发回调时：从栈顶开始（LIFO）
postComplete();  // 先触发completion2，再触发completion1
```

**原因**：
- 简化实现（栈的push/pop比队列简单）
- 回调顺序对大多数场景无影响

---

### 3. 复用ForkJoinTask

```java
abstract static class Completion extends ForkJoinTask<Void> {
    // Completion继承ForkJoinTask
}
```

**优势**：
- 可以直接提交到 `ForkJoinPool` 执行
- 复用 `ForkJoinTask` 的调度机制

---

## 七、使用示例

### 1. 基本使用

```java
// 异步计算
CompletableFuture<Integer> future = CompletableFuture.supplyAsync(() -> {
    return 100;
});

// 转换结果
CompletableFuture<String> result = future
    .thenApply(num -> num * 2)       // 200
    .thenApply(num -> "结果: " + num); // "结果: 200"

// 消费结果
result.thenAccept(System.out::println);
```

### 2. 组合多个Future

```java
CompletableFuture<String> future1 = CompletableFuture.supplyAsync(() -> "Hello");
CompletableFuture<String> future2 = CompletableFuture.supplyAsync(() -> "World");

// 等待两个都完成
CompletableFuture<String> combined = future1.thenCombine(future2, (s1, s2) -> {
    return s1 + " " + s2;  // "Hello World"
});

// 任一完成即返回
CompletableFuture<String> either = future1.applyToEither(future2, s -> s);
```

### 3. 异常处理

```java
CompletableFuture.supplyAsync(() -> {
    if (Math.random() > 0.5) {
        throw new RuntimeException("出错了");
    }
    return "成功";
})
.thenApply(s -> s + " 处理")
.exceptionally(ex -> {
    System.out.println("捕获异常：" + ex.getMessage());
    return "默认值";
})
.thenAccept(System.out::println);
```

### 4. 批量任务

```java
List<CompletableFuture<String>> futures = urls.stream()
    .map(url -> CompletableFuture.supplyAsync(() -> httpClient.get(url)))
    .collect(Collectors.toList());

// 等待所有完成
CompletableFuture<Void> allOf = CompletableFuture.allOf(
    futures.toArray(new CompletableFuture[0])
);

allOf.thenRun(() -> {
    List<String> results = futures.stream()
        .map(CompletableFuture::join)
        .collect(Collectors.toList());
    
    System.out.println("所有请求完成：" + results);
});
```

---

## 八、面试答题总结

**简洁版回答**：

CompletableFuture 的底层实现基于以下核心机制：

**1. 数据结构**
- `result`：存储任务结果或异常（使用 `AltResult` 包装异常）
- `stack`：维护一个 **Completion回调链表**（栈结构），存储所有等待结果的回调

**2. 回调机制**
- 调用 `thenApply` 等方法时，创建对应的 `Completion` 节点（如 `UniApply`）
- 使用 **CAS操作** 将节点推入 `stack` 链表（无锁）
- 任务完成时，遍历 `stack` 链表，依次触发每个 `Completion` 的 `tryFire` 方法

**3. 线程模型**
- 默认使用 `ForkJoinPool.commonPool()` 作为执行器
- `supplyAsync` / `thenApplyAsync`：异步执行（提交到线程池）
- `thenApply` / `thenAccept`：同步执行（在完成任务的线程中执行）

**4. 核心流程**
```
提交任务 → 执行 → 设置结果(CAS) → 触发回调链(postComplete)
                                  ↓
                        遍历stack，依次执行Completion
                                  ↓
                        每个Completion触发下游回调
```

**5. 关键技术**
- **CAS无锁操作**：保证 `result` 和 `stack` 的线程安全
- **栈式回调链**：简化实现，LIFO顺序触发
- **复用ForkJoinTask**：`Completion` 继承 `ForkJoinTask`，复用调度机制

**6. 异常处理**
- 异常包装成 `AltResult` 存储
- 异常会沿着回调链传播，直到遇到 `exceptionally` 或 `handle` 处理

**典型应用**：异步任务编排、并行处理、非阻塞IO等场景。

