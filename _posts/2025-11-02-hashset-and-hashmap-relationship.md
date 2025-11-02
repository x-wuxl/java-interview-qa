---
layout: post
title: "HashSet和HashMap有什么关系？"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [HashSet, HashMap, Set, 适配器模式, 集合实现]
description: "揭秘 HashSet 基于 HashMap 实现的内部机制，理解 Set 如何复用 Map 的数据结构以及背后的设计思想"
---

## 核心概念

**HashSet 本质上是 HashMap 的一个包装类**，内部使用 HashMap 存储数据：
- **HashSet 的元素** → **HashMap 的 Key**
- **HashMap 的 Value** → **固定的占位对象**（PRESENT）

```java
public class HashSet<E> extends AbstractSet<E>
    implements Set<E>, Cloneable, java.io.Serializable {
    
    // 内部维护一个 HashMap
    private transient HashMap<E,Object> map;
    
    // 所有 Value 使用同一个占位对象
    private static final Object PRESENT = new Object();
}
```

**关键设计**：
- HashSet 复用 HashMap 的所有特性（哈希表、去重、O(1) 查找）
- 典型的**适配器模式**：将 Map 接口适配为 Set 接口
- 节省开发成本，保持代码一致性

---

## 源码实现分析

### 1. 构造方法

```java
public class HashSet<E> extends AbstractSet<E> {
    // 无参构造
    public HashSet() {
        map = new HashMap<>();  // 默认初始容量 16，负载因子 0.75
    }

    // 指定初始容量
    public HashSet(int initialCapacity) {
        map = new HashMap<>(initialCapacity);
    }

    // 指定初始容量和负载因子
    public HashSet(int initialCapacity, float loadFactor) {
        map = new HashMap<>(initialCapacity, loadFactor);
    }

    // 从集合创建
    public HashSet(Collection<? extends E> c) {
        map = new HashMap<>(Math.max((int) (c.size()/.75f) + 1, 16));
        addAll(c);
    }
}
```

---

### 2. 核心操作

#### add() 方法
```java
public boolean add(E e) {
    // 调用 HashMap.put()，Value 固定为 PRESENT
    // 返回值为 null 表示之前不存在（添加成功）
    return map.put(e, PRESENT) == null;
}
```

**逻辑解析**：
- `map.put(key, value)` 返回旧值
- 如果 key 不存在，返回 `null` → `add()` 返回 `true`
- 如果 key 已存在，返回旧的 PRESENT → `add()` 返回 `false`

#### remove() 方法
```java
public boolean remove(Object o) {
    // 调用 HashMap.remove()
    // 返回 PRESENT 表示删除成功
    return map.remove(o) == PRESENT;
}
```

#### contains() 方法
```java
public boolean contains(Object o) {
    // 调用 HashMap.containsKey()
    return map.containsKey(o);
}
```

#### size() 和 clear()
```java
public int size() {
    return map.size();
}

public void clear() {
    map.clear();
}
```

#### 遍历
```java
public Iterator<E> iterator() {
    // 返回 HashMap 的 keySet 的迭代器
    return map.keySet().iterator();
}
```

---

### 3. 为什么使用 PRESENT 对象？

**设计考虑**：
1. **节省内存**：所有 Entry 共享同一个 PRESENT 对象，而非每个 Entry 创建新对象
2. **语义明确**：表示"该 Key 存在"，而非 null（HashMap 允许 null 值）
3. **类型安全**：使用 Object 类型，避免基本类型装箱

```java
private static final Object PRESENT = new Object();

// 所有元素的 Value 都指向同一个对象
map.put("A", PRESENT);
map.put("B", PRESENT);
map.put("C", PRESENT);
// 内存中只有一个 PRESENT 对象
```

---

## 完整示例

### 示例 1：基本使用
```java
public class HashSetDemo {
    public static void main(String[] args) {
        HashSet<String> set = new HashSet<>();
        
        // 添加元素（实际调用 HashMap.put）
        System.out.println(set.add("Java"));    // true（新增）
        System.out.println(set.add("Python"));  // true
        System.out.println(set.add("Java"));    // false（重复）
        
        // 查询元素（实际调用 HashMap.containsKey）
        System.out.println(set.contains("Java"));  // true
        
        // 删除元素（实际调用 HashMap.remove）
        set.remove("Python");
        
        // 遍历元素（实际遍历 HashMap.keySet）
        for (String s : set) {
            System.out.println(s);  // Java
        }
        
        // 大小
        System.out.println(set.size());  // 1
    }
}
```

---

### 示例 2：去重应用

```java
// 快速去重
List<Integer> list = Arrays.asList(1, 2, 2, 3, 3, 3, 4);
Set<Integer> uniqueSet = new HashSet<>(list);
System.out.println(uniqueSet);  // [1, 2, 3, 4]（无序）

// 去重后转回 List
List<Integer> uniqueList = new ArrayList<>(uniqueSet);
```

---

### 示例 3：自定义对象

```java
public class User {
    private String name;
    private int age;

    // 必须重写 hashCode 和 equals
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        User user = (User) o;
        return age == user.age && Objects.equals(name, user.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(name, age);
    }
}

// 使用
HashSet<User> users = new HashSet<>();
users.add(new User("张三", 25));
users.add(new User("张三", 25));  // 重复，不会添加
System.out.println(users.size());  // 1
```

**为什么需要重写 hashCode 和 equals？**
- HashSet 依赖 HashMap 的 Key 去重
- HashMap 通过 `hashCode()` 定位桶，`equals()` 判断相等性
- 不重写会导致相同对象被视为不同元素

---

## HashSet 家族的实现关系

| Set 实现 | 内部使用的 Map | 特性 |
|---------|---------------|------|
| **HashSet** | HashMap | 无序、允许 null、O(1) 查找 |
| **LinkedHashSet** | LinkedHashMap | 保持插入顺序 |
| **TreeSet** | TreeMap | 有序（自然顺序或 Comparator） |

**源码验证**：
```java
// LinkedHashSet 继承 HashSet
public class LinkedHashSet<E> extends HashSet<E> {
    public LinkedHashSet() {
        super(16, .75f, true);  // 调用父类特殊构造器
    }
}

// HashSet 的特殊构造器（包访问权限）
HashSet(int initialCapacity, float loadFactor, boolean dummy) {
    map = new LinkedHashMap<>(initialCapacity, loadFactor);  // 使用 LinkedHashMap
}
```

---

## 性能分析

| 操作 | 时间复杂度 | 说明 |
|------|-----------|------|
| add(e) | O(1) | 平均情况，最坏 O(n)（哈希冲突） |
| remove(e) | O(1) | 同上 |
| contains(e) | O(1) | 同上 |
| size() | O(1) | 直接返回 HashMap 的 size |
| iterator() | O(n) | 遍历所有元素 |

**空间复杂度**：
- 与 HashMap 相同
- 每个元素占用一个 Entry（Key + Value 引用 + 哈希值 + next 指针）
- Value 统一使用 PRESENT，额外空间开销仅 1 个对象

---

## 线程安全性

HashSet **不是线程安全**的，多线程环境需外部同步：

```java
// 方案 1：Collections.synchronizedSet（性能差）
Set<String> syncSet = Collections.synchronizedSet(new HashSet<>());

// 方案 2：ConcurrentHashMap.newKeySet()（推荐）
Set<String> concurrentSet = ConcurrentHashMap.newKeySet();

// 方案 3：CopyOnWriteArraySet（读多写少）
Set<String> cowSet = new CopyOnWriteArraySet<>();
```

---

## 面试常见追问

### Q1: 为什么不直接实现 Set 接口，而要依赖 HashMap？

**A**: 复用代码，减少重复开发
- HashMap 已实现高效的哈希表结构
- Set 只需要 Key 的去重特性，Value 无意义
- 通过适配器模式，几乎零成本实现 Set

---

### Q2: HashSet 的 add() 方法如何保证不重复？

**A**: 依赖 HashMap 的 Key 唯一性
```java
public boolean add(E e) {
    // HashMap.put() 内部逻辑：
    // 1. 计算 hash(e)
    // 2. 定位桶位置
    // 3. 遍历链表/红黑树，通过 equals() 判断是否存在
    // 4. 存在则替换 Value（返回旧值），不存在则插入（返回 null）
    return map.put(e, PRESENT) == null;
}
```

---

### Q3: HashSet 能存储 null 吗？

**A**: 可以，且只能存储一个 null
```java
HashSet<String> set = new HashSet<>();
set.add(null);  // true
set.add(null);  // false（重复）
System.out.println(set);  // [null]
```
因为 HashMap 允许一个 null Key。

---

### Q4: HashSet 的遍历顺序是什么？

**A**: **无序**，取决于哈希值和桶位置
```java
HashSet<Integer> set = new HashSet<>();
set.add(1);
set.add(2);
set.add(3);
System.out.println(set);  // 可能输出 [1, 2, 3] 或 [2, 1, 3] 等
```

需要顺序请使用：
- **LinkedHashSet**：保持插入顺序
- **TreeSet**：自然排序

---

### Q5: HashSet 与 HashMap 的内存占用对比？

**A**: 几乎相同
- HashSet 每个元素对应 HashMap 的一个 Entry
- Value 统一使用 PRESENT（单例），不额外占用内存
- HashSet 本身只多一个 `map` 引用字段（8 字节）

---

## 设计模式：适配器模式

HashSet 是**类适配器**的典型实现：

```
┌─────────────────┐
│   Set 接口      │ ← 目标接口
└─────────────────┘
         ▲
         │ 实现
┌─────────────────┐
│    HashSet      │ ← 适配器
│  - map: HashMap │
└─────────────────┘
         │ 持有
         ▼
┌─────────────────┐
│    HashMap      │ ← 被适配者
└─────────────────┘
```

**优点**：
- 复用 HashMap 的成熟实现
- 保持代码一致性（HashMap 优化会同步受益）
- 简化 Set 的实现（仅 100+ 行代码）

---

## 面试总结

**核心要点**：
1. **HashSet 内部是 HashMap**：元素存储在 Key 中，Value 为固定的 PRESENT 对象
2. **适配器模式**：将 Map 接口适配为 Set 接口
3. **去重机制**：依赖 HashMap 的 Key 唯一性（hashCode + equals）
4. **性能特性**：与 HashMap 完全一致（O(1) 操作）
5. **线程安全**：非线程安全，需外部同步或使用并发集合

**记忆技巧**：
```java
HashSet<E> = HashMap<E, PRESENT>
LinkedHashSet<E> = LinkedHashMap<E, PRESENT>
TreeSet<E> = TreeMap<E, PRESENT>
```

**面试答题模板**：
> HashSet 底层使用 HashMap 实现，元素存储为 Key，Value 统一使用占位对象 PRESENT。这种设计复用了 HashMap 的哈希表结构，通过 hashCode() 和 equals() 保证元素唯一性，时间复杂度为 O(1)。需要注意的是，HashSet 是无序的，不保证元素顺序；且非线程安全，并发场景需使用 ConcurrentHashMap.newKeySet()。

