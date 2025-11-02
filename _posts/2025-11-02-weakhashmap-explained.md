---
layout: post
title: "WeakHashMap了解吗？"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [WeakHashMap, 弱引用, GC, 内存管理, 缓存]
description: "详解 WeakHashMap 的弱引用机制、自动回收原理以及在缓存场景中的应用，理解其与普通 HashMap 的本质区别"
---

## 核心概念

**WeakHashMap** 是一种特殊的 Map 实现，其 **key 采用弱引用（WeakReference）** 包装。当某个 key 不再被外部强引用时，该 key-value 对会在下次 GC 后自动从 Map 中移除。

```java
public class WeakHashMap<K,V> extends AbstractMap<K,V> implements Map<K,V>
```

**核心特性**：
- Key 使用弱引用，Value 使用强引用
- 自动清理不再使用的 key-value 对
- 适合实现简单的内存敏感型缓存
- **非线程安全**

---

## Java 引用类型回顾

| 引用类型 | GC 行为 | 典型应用 |
|---------|---------|---------|
| **强引用**（Strong） | 永远不会被回收 | 普通对象引用 `Object obj = new Object()` |
| **软引用**（Soft） | 内存不足时回收 | 内存敏感缓存（图片缓存） |
| **弱引用**（Weak） | 下次 GC 时回收 | WeakHashMap、ThreadLocal |
| **虚引用**（Phantom） | 任何时候都可能被回收 | 对象回收跟踪 |

**弱引用示例**：
```java
String key = new String("key");  // 强引用
WeakReference<String> weakKey = new WeakReference<>(key);

System.out.println(weakKey.get());  // 输出 "key"
key = null;  // 解除强引用
System.gc();  // 触发 GC
System.out.println(weakKey.get());  // 输出 null（已被回收）
```

---

## 实现原理

### 1. 内部结构

WeakHashMap 使用 `Entry` 继承自 `WeakReference`：

```java
private static class Entry<K,V> extends WeakReference<Object> implements Map.Entry<K,V> {
    V value;         // value 是强引用
    final int hash;
    Entry<K,V> next;

    Entry(Object key, V value, ReferenceQueue<Object> queue,
          int hash, Entry<K,V> next) {
        super(key, queue);  // key 作为弱引用传递给父类
        this.value = value;
        this.hash  = hash;
        this.next  = next;
    }
}
```

**关键点**：
- **Key 是弱引用**：存储在 `WeakReference` 的 `referent` 字段中
- **Value 是强引用**：直接存储在 Entry 的 `value` 字段中
- **ReferenceQueue**：GC 回收 key 后，Entry 会被加入此队列

---

### 2. 自动清理机制

#### 引用队列的作用

```java
public class WeakHashMap<K,V> extends AbstractMap<K,V> {
    // 引用队列：存储已被 GC 回收的 Entry
    private final ReferenceQueue<Object> queue = new ReferenceQueue<>();
}
```

**清理流程**：
1. 外部对 key 的强引用断开
2. GC 回收 key 对象，Entry 被加入 `queue`
3. 下次访问 Map 时（get/put/size 等），触发 `expungeStaleEntries()` 清理

#### 清理源码

```java
private void expungeStaleEntries() {
    // 遍历引用队列，移除已回收的 Entry
    for (Object x; (x = queue.poll()) != null; ) {
        synchronized (queue) {
            Entry<K,V> e = (Entry<K,V>) x;
            int i = indexFor(e.hash, table.length);

            Entry<K,V> prev = table[i];
            Entry<K,V> p = prev;
            while (p != null) {
                Entry<K,V> next = p.next;
                if (p == e) {
                    if (prev == e)
                        table[i] = next;  // 从桶中移除
                    else
                        prev.next = next;
                    e.value = null;  // 释放 value
                    size--;
                    break;
                }
                prev = p;
                p = next;
            }
        }
    }
}
```

---

### 3. 触发清理的时机

WeakHashMap 在以下操作前都会调用 `expungeStaleEntries()`：

```java
public V get(Object key) {
    Object k = maskNull(key);
    int h = hash(k);
    Entry<K,V>[] tab = getTable();  // 内部调用 expungeStaleEntries()
    // ...
}

private Entry<K,V>[] getTable() {
    expungeStaleEntries();  // 清理过期 Entry
    return table;
}
```

**所有触发清理的操作**：
- `get(key)`
- `put(key, value)`
- `size()`
- `isEmpty()`
- `remove(key)`
- 遍历操作

---

## 代码示例

### 示例 1：基本使用

```java
public class WeakHashMapDemo {
    public static void main(String[] args) throws InterruptedException {
        WeakHashMap<String, String> map = new WeakHashMap<>();
        
        // 使用 new String 创建对象（而非字符串常量池）
        String key1 = new String("key1");
        String key2 = new String("key2");
        
        map.put(key1, "value1");
        map.put(key2, "value2");
        System.out.println("GC 前: " + map);  // {key1=value1, key2=value2}
        
        // 解除 key1 的强引用
        key1 = null;
        
        // 触发 GC
        System.gc();
        Thread.sleep(100);
        
        // 访问 map 触发清理
        System.out.println("GC 后: " + map);  // {key2=value2}（key1 已被回收）
    }
}
```

**注意**：不要使用字符串字面量作为 key！
```java
// ❌ 错误：字符串字面量存储在常量池，永远不会被回收
map.put("key", "value");

// ✅ 正确：使用 new String 或其他对象
map.put(new String("key"), "value");
map.put(new User("张三"), "userData");
```

---

### 示例 2：实现简单缓存

```java
public class ImageCache {
    private final WeakHashMap<String, Image> cache = new WeakHashMap<>();

    public Image getImage(String path) {
        Image img = cache.get(path);
        if (img == null) {
            img = loadImageFromDisk(path);
            cache.put(path, img);
        }
        return img;
    }

    private Image loadImageFromDisk(String path) {
        // 从磁盘加载图片
        return new Image(path);
    }
}

// 使用场景
ImageCache cache = new ImageCache();
String path = new String("/images/logo.png");
Image img = cache.getImage(path);  // 首次加载
Image img2 = cache.getImage(path); // 命中缓存

path = null;  // 解除引用
System.gc();  // 内存不足时，缓存自动清理
```

---

## WeakHashMap vs HashMap

| 特性 | WeakHashMap | HashMap |
|------|-------------|---------|
| **Key 引用类型** | 弱引用 | 强引用 |
| **GC 后行为** | Key 被回收，Entry 自动移除 | Key 不会被回收，Entry 永久存在 |
| **内存泄漏风险** | 低（自动清理） | 高（需手动清理） |
| **适用场景** | 缓存、元数据存储 | 通用 Map |
| **线程安全性** | 非线程安全 | 非线程安全 |
| **性能** | 略低（需清理 Entry） | 高 |

---

## 使用场景

### 1. 临时缓存
```java
// 场景：缓存计算结果，当 key 对象不再使用时自动释放
WeakHashMap<ComplexObject, CalculationResult> cache = new WeakHashMap<>();
```

### 2. 对象元数据存储
```java
// 场景：为对象附加元数据，对象销毁时元数据自动清理
public class ObjectMetadataRegistry {
    private static final WeakHashMap<Object, Metadata> metadataMap = new WeakHashMap<>();
    
    public static void register(Object obj, Metadata metadata) {
        metadataMap.put(obj, metadata);
    }
    
    public static Metadata getMetadata(Object obj) {
        return metadataMap.get(obj);
    }
}
```

### 3. 监听器管理
```java
// 场景：避免监听器导致的内存泄漏
public class EventSource {
    private final WeakHashMap<EventListener, Boolean> listeners = new WeakHashMap<>();
    
    public void addListener(EventListener listener) {
        listeners.put(listener, Boolean.TRUE);
    }
    
    public void fireEvent(Event e) {
        for (EventListener listener : listeners.keySet()) {
            listener.onEvent(e);
        }
    }
}
```

---

## 注意事项与陷阱

### 1. Value 不会被自动回收
```java
// ❌ 错误理解：Value 会随 Key 一起回收
WeakHashMap<Key, LargeObject> map = new WeakHashMap<>();
map.put(key, new LargeObject());  // Value 是强引用！

// 即使 key 被回收，如果 Value 还被其他地方引用，也不会释放内存
```

### 2. Key 必须是可回收对象
```java
// ❌ 字符串字面量存储在常量池，永远不会被回收
map.put("key", "value");

// ❌ 包装类的小值会被缓存（-128~127）
map.put(Integer.valueOf(100), "value");  // 不会被回收

// ✅ 使用自定义对象或 new 创建的对象
map.put(new String("key"), "value");
map.put(new Integer(100), "value");
```

### 3. 非确定性清理
```java
// GC 时机不确定，清理也不确定
key = null;
System.gc();  // 不保证立即执行
map.size();   // 可能仍包含旧 Entry，需要再次调用才能触发清理
```

### 4. 线程安全问题
```java
// WeakHashMap 非线程安全，需要外部同步
Map<K, V> syncMap = Collections.synchronizedMap(new WeakHashMap<>());
```

---

## 实际应用：ThreadLocal 的内部实现

`ThreadLocalMap` 使用了类似的弱引用机制：

```java
static class Entry extends WeakReference<ThreadLocal<?>> {
    Object value;
    Entry(ThreadLocal<?> k, Object v) {
        super(k);  // ThreadLocal 作为弱引用 key
        value = v;
    }
}
```

**优点**：ThreadLocal 对象被回收后，Entry 会在下次访问时清理，避免内存泄漏。

**注意**：Value 仍是强引用，需手动调用 `remove()` 彻底清理。

---

## 面试总结

**WeakHashMap 核心机制**：
1. **Key 使用弱引用**：外部无强引用时，GC 可回收
2. **ReferenceQueue**：回收后的 Entry 加入队列
3. **延迟清理**：下次操作时遍历队列，移除过期 Entry
4. **Value 是强引用**：需注意防止内存泄漏

**与 HashMap 的本质区别**：
- HashMap：`Entry<K,V>` 直接持有 K
- WeakHashMap：`Entry<K,V> extends WeakReference<K>`

**典型应用场景**：
- ✅ 对象元数据存储（如 ORM 框架的实体状态跟踪）
- ✅ 临时缓存（如方法调用结果缓存）
- ✅ 监听器注册表（避免监听器泄漏）
- ❌ 不适合需要精确控制生命周期的缓存（用 Guava Cache）

**记忆口诀**：
- **Weak Key**：Key 弱引用，可自动回收
- **Strong Value**：Value 强引用，需注意泄漏
- **Lazy Clean**：延迟清理，非实时
- **GC Driven**：依赖 GC，不可控

