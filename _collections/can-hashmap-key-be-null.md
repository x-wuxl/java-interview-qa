---
title: "HashMap的key可以为null吗？"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [HashMap, Null值, 源码分析]
description: "详解HashMap对null key的支持机制，以及与其他Map实现的对比"
nav_order: 96
parent: 集合框架
---
## 核心概念

**HashMap 允许 null key**，并且最多只能有 **1 个 null key**。null key 总是被存储在数组的 **第 0 个位置**（index = 0）。

## 源码实现

### 1. hash 方法对 null 的处理

```java
static final int hash(Object key) {
    int h;
    // key 为 null 时，hash 值固定为 0
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}
```

**关键点**：
- null key 的 hash 值固定为 0
- 通过 `(n-1) & 0` 计算索引，结果永远是 0
- 因此 null key 总是存储在 `table[0]` 位置

### 2. put 方法处理 null key

```java
public V put(K key, V value) {
    return putVal(hash(key), key, value, false, true);
    //              ↑ null key 的 hash 为 0
}

final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    Node<K,V>[] tab; Node<K,V> p; int n, i;
    
    // ...
    
    // 计算索引位置
    if ((p = tab[i = (n - 1) & hash]) == null)
        //          ↑ null key: (n-1) & 0 = 0，固定在 index=0
        tab[i] = newNode(hash, key, value, null);
    else {
        Node<K,V> e; K k;
        // 检查第一个节点
        if (p.hash == hash &&
            ((k = p.key) == key || (key != null && key.equals(k))))
            //                      ↑ null key 通过 == 比较
            e = p;
        // ...
    }
    // ...
}
```

### 3. get 方法处理 null key

```java
public V get(Object key) {
    Node<K,V> e;
    return (e = getNode(hash(key), key)) == null ? null : e.value;
    //              ↑ null key 的 hash 为 0
}

final Node<K,V> getNode(int hash, Object key) {
    Node<K,V>[] tab; Node<K,V> first, e; int n; K k;
    
    if ((tab = table) != null && (n = tab.length) > 0 &&
        (first = tab[(n - 1) & hash]) != null) {
        //          ↑ null key: 直接访问 table[0]
        
        // 检查第一个节点
        if (first.hash == hash &&
            ((k = first.key) == key || (key != null && key.equals(k))))
            //                ↑ null key 通过 == 判断
            return first;
        
        // 遍历链表或树
        if ((e = first.next) != null) {
            // ...
        }
    }
    return null;
}
```

## 实际使用示例

### 基本操作

```java
public class NullKeyTest {
    public static void main(String[] args) {
        Map<String, String> map = new HashMap<>();
        
        // 1. 插入 null key
        map.put(null, "value1");
        System.out.println(map.get(null));  // 输出: value1
        
        // 2. 更新 null key 的值
        map.put(null, "value2");
        System.out.println(map.get(null));  // 输出: value2
        System.out.println(map.size());     // 输出: 1（只有一个 null key）
        
        // 3. null key 与普通 key 共存
        map.put("key1", "value3");
        map.put("key2", "value4");
        System.out.println(map.size());     // 输出: 3
        
        // 4. 判断是否包含 null key
        System.out.println(map.containsKey(null));  // true
        
        // 5. 删除 null key
        map.remove(null);
        System.out.println(map.get(null));  // 输出: null
        System.out.println(map.size());     // 输出: 2
    }
}
```

### null key 与 null value 的组合

```java
public class NullKeyAndValueTest {
    public static void main(String[] args) {
        Map<String, String> map = new HashMap<>();
        
        // 1. null key + 非 null value
        map.put(null, "value1");
        
        // 2. null key + null value
        map.put(null, null);
        
        // 3. 非 null key + null value
        map.put("key1", null);
        
        // 4. 区分"不存在"和"值为null"
        System.out.println(map.containsKey(null));   // true
        System.out.println(map.get(null));           // null
        
        System.out.println(map.containsKey("key1")); // true
        System.out.println(map.get("key1"));         // null
        
        System.out.println(map.containsKey("key2")); // false
        System.out.println(map.get("key2"));         // null
        
        // 使用 containsKey 区分"值为null"和"不存在"
        if (map.containsKey("key1")) {
            System.out.println("key1 存在，值为 null");
        }
        if (!map.containsKey("key2")) {
            System.out.println("key2 不存在");
        }
    }
}
```

### 遍历包含 null key 的 Map

```java
public class IterateNullKeyMap {
    public static void main(String[] args) {
        Map<String, String> map = new HashMap<>();
        map.put(null, "nullValue");
        map.put("key1", "value1");
        map.put("key2", null);
        
        // 方式1：entrySet 遍历
        for (Map.Entry<String, String> entry : map.entrySet()) {
            System.out.println("Key: " + entry.getKey() + 
                             ", Value: " + entry.getValue());
        }
        // 输出:
        // Key: null, Value: nullValue
        // Key: key1, Value: value1
        // Key: key2, Value: null
        
        // 方式2：keySet 遍历
        for (String key : map.keySet()) {
            System.out.println("Key: " + key + 
                             ", Value: " + map.get(key));
        }
    }
}
```

## 与其他 Map 实现的对比

### 1. HashMap vs Hashtable

```java
public class HashMapVsHashtable {
    public static void main(String[] args) {
        // HashMap：允许 null key 和 null value
        Map<String, String> hashMap = new HashMap<>();
        hashMap.put(null, "value1");  // ✓ 正常
        hashMap.put("key1", null);    // ✓ 正常
        
        // Hashtable：不允许 null key 和 null value
        Map<String, String> hashtable = new Hashtable<>();
        try {
            hashtable.put(null, "value1");  // ✗ NullPointerException
        } catch (NullPointerException e) {
            System.out.println("Hashtable 不支持 null key");
        }
        
        try {
            hashtable.put("key1", null);    // ✗ NullPointerException
        } catch (NullPointerException e) {
            System.out.println("Hashtable 不支持 null value");
        }
    }
}
```

**Hashtable 源码**：
```java
public synchronized V put(K key, V value) {
    // 不允许 null value
    if (value == null) {
        throw new NullPointerException();
    }
    
    // ...
    int hash = key.hashCode();  // key 为 null 时抛出 NullPointerException
    // ...
}
```

### 2. HashMap vs ConcurrentHashMap

```java
public class HashMapVsConcurrentHashMap {
    public static void main(String[] args) {
        // HashMap：允许 null key
        Map<String, String> hashMap = new HashMap<>();
        hashMap.put(null, "value1");  // ✓ 正常
        
        // ConcurrentHashMap：不允许 null key 和 null value
        Map<String, String> concurrentMap = new ConcurrentHashMap<>();
        try {
            concurrentMap.put(null, "value1");  // ✗ NullPointerException
        } catch (NullPointerException e) {
            System.out.println("ConcurrentHashMap 不支持 null key");
        }
        
        try {
            concurrentMap.put("key1", null);    // ✗ NullPointerException
        } catch (NullPointerException e) {
            System.out.println("ConcurrentHashMap 不支持 null value");
        }
    }
}
```

**ConcurrentHashMap 不支持 null 的原因**：
```java
// 在并发环境下，无法区分"值为null"和"key不存在"
V value = map.get(key);
if (value == null) {
    // 问题：是 key 不存在，还是 value 本身就是 null？
    // 需要再次调用 containsKey(key) 判断，但可能产生竞态条件
}
```

### 3. HashMap vs TreeMap

```java
public class HashMapVsTreeMap {
    public static void main(String[] args) {
        // HashMap：允许 null key
        Map<String, String> hashMap = new HashMap<>();
        hashMap.put(null, "value1");  // ✓ 正常
        
        // TreeMap：不允许 null key（需要比较）
        Map<String, String> treeMap = new TreeMap<>();
        try {
            treeMap.put(null, "value1");  // ✗ NullPointerException
        } catch (NullPointerException e) {
            System.out.println("TreeMap 不支持 null key（无法比较）");
        }
        
        // 但允许 null value
        treeMap.put("key1", null);  // ✓ 正常
    }
}
```

**TreeMap 不支持 null key 的原因**：
```java
// TreeMap 需要对 key 进行比较排序
public V put(K key, V value) {
    // ...
    int cmp = key.compareTo(parentKey);  // null.compareTo() 会抛出 NPE
    // ...
}
```

### 4. 对比总结

| Map 实现 | null key | null value | 说明 |
|---------|----------|------------|------|
| **HashMap** | ✓ 支持（1个） | ✓ 支持（多个） | 非线程安全 |
| **Hashtable** | ✗ 不支持 | ✗ 不支持 | 线程安全（已过时） |
| **ConcurrentHashMap** | ✗ 不支持 | ✗ 不支持 | 线程安全，并发性能高 |
| **TreeMap** | ✗ 不支持 | ✓ 支持 | 有序，基于红黑树 |
| **LinkedHashMap** | ✓ 支持（1个） | ✓ 支持（多个） | 保持插入顺序 |

## 存储位置详解

### null key 的存储机制

```java
public class NullKeyStorageTest {
    public static void main(String[] args) throws Exception {
        Map<String, String> map = new HashMap<>(16);
        
        // 插入 null key
        map.put(null, "nullValue");
        
        // 插入其他 key
        map.put("key1", "value1");
        map.put("key2", "value2");
        
        // 通过反射查看存储位置
        java.lang.reflect.Field tableField = HashMap.class.getDeclaredField("table");
        tableField.setAccessible(true);
        Object[] table = (Object[]) tableField.get(map);
        
        System.out.println("数组容量: " + table.length);
        
        for (int i = 0; i < table.length; i++) {
            if (table[i] != null) {
                System.out.println("Index " + i + " 有元素");
                // null key 总是在 index = 0
            }
        }
    }
}
```

**输出示例**：
```
数组容量: 16
Index 0 有元素  ← null key 在这里
Index 5 有元素
Index 12 有元素
```

### null key 与哈希冲突

```java
public class NullKeyCollisionTest {
    public static void main(String[] args) {
        Map<SpecialKey, String> map = new HashMap<>(16);
        
        // 插入 null key
        map.put(null, "nullValue");
        
        // 插入一个 hash 值为 0 的 key（会与 null key 冲突）
        map.put(new SpecialKey(), "specialValue");
        
        // 两者都在 table[0]，形成链表或树
        System.out.println(map.get(null));           // nullValue
        System.out.println(map.get(new SpecialKey())); // specialValue
    }
    
    static class SpecialKey {
        @Override
        public int hashCode() {
            return 0;  // hash 为 0，与 null key 冲突
        }
        
        @Override
        public boolean equals(Object obj) {
            return obj instanceof SpecialKey;
        }
    }
}
```

**存储结构**：
```
table[0] → null key (nullValue) → SpecialKey (specialValue)
           ↑ 链表头
```

## 实战建议

### 1. 是否应该使用 null key？

**不推荐使用 null key**：
```java
// 不推荐：语义不清晰
Map<String, User> userMap = new HashMap<>();
userMap.put(null, defaultUser);  // null 代表什么？

// 推荐：使用明确的 key
Map<String, User> userMap = new HashMap<>();
userMap.put("default", defaultUser);  // 语义清晰
userMap.put("anonymous", anonymousUser);
```

### 2. 处理可能为 null 的 key

```java
public class SafeMapOperations {
    public static void main(String[] args) {
        Map<String, String> map = new HashMap<>();
        
        // 方式1：使用 Optional
        String key = null;
        map.put(Optional.ofNullable(key).orElse("default"), "value1");
        
        // 方式2：使用默认值
        String safeKey = (key != null) ? key : "default";
        map.put(safeKey, "value1");
        
        // 方式3：使用工具类
        map.put(Objects.toString(key, "default"), "value1");
    }
}
```

### 3. 迁移到不支持 null key 的 Map

```java
public class MigrateToNonNullKeyMap {
    public static void main(String[] args) {
        Map<String, String> hashMap = new HashMap<>();
        hashMap.put(null, "value1");
        hashMap.put("key1", "value2");
        
        // 迁移到 ConcurrentHashMap
        Map<String, String> concurrentMap = new ConcurrentHashMap<>();
        for (Map.Entry<String, String> entry : hashMap.entrySet()) {
            String key = entry.getKey();
            // 将 null key 替换为特殊值
            concurrentMap.put(
                key != null ? key : "NULL_KEY_PLACEHOLDER", 
                entry.getValue()
            );
        }
    }
}
```

## 面试答题总结

**答题要点**：
1. **支持 null key**：HashMap 允许 1 个 null key
2. **存储位置**：null key 的 hash 固定为 0，存储在 table[0]
3. **比较方式**：通过 `==` 判断 null key，而非 `equals()`
4. **其他 Map**：Hashtable、ConcurrentHashMap、TreeMap 不支持 null key

**加分项**：
- 解释为什么 null key 的 hash 是 0
- 说明 null key 可能与其他 hash 为 0 的 key 冲突
- 对比不同 Map 实现对 null 的支持
- 提到 ConcurrentHashMap 不支持 null 是为了避免并发歧义

**一句话总结**：HashMap 允许一个 null key，hash 值固定为 0，存储在数组的第 0 个位置，这是与 Hashtable、ConcurrentHashMap 的重要区别。

