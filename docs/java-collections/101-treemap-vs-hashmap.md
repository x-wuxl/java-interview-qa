---
layout: default
title: "TreeMap和HashMap有什么区别？"
parent: 集合框架
nav_order: 101
description: "深入对比 TreeMap 和 HashMap 在底层结构、性能、排序特性上的差异，理解有序 Map 与无序 Map 的适用场景"
date: 2025-11-02
---
## 核心概念

**TreeMap** 和 **HashMap** 是 Java 中最常用的两种 Map 实现，核心区别在于**数据结构**和**有序性**：

| 特性 | HashMap | TreeMap |
|------|---------|---------|
| **底层结构** | 哈希表（数组 + 链表 + 红黑树） | 红黑树（完全基于树） |
| **有序性** | **无序** | **有序**（自然顺序或 Comparator） |
| **时间复杂度** | O(1) | O(log n) |
| **null 支持** | 允许 1 个 null Key | **不允许** null Key |
| **线程安全** | 非线程安全 | 非线程安全 |
| **实现接口** | Map | Map + **NavigableMap** + SortedMap |

---

## 底层数据结构

### HashMap 的结构

```
数组 + 链表 + 红黑树
┌────┬────┬────┬────┐
│ [0]│ [1]│ [2]│ [3]│ ← 桶数组（哈希表）
└─┬──┴────┴─┬──┴────┘
  │         │
  ↓         ↓
Entry1    Entry3 → Entry4 → Entry5  ← 链表（冲突解决）
  ↓
Entry2    （链表长度≥8 转红黑树）   ← 树化优化
```

**特点**：
- 通过 `hash(key)` 计算桶位置
- 冲突时使用链表或红黑树
- **无序**：遍历顺序与插入顺序无关

---

### TreeMap 的结构

```
红黑树（平衡二叉搜索树）
         10
        /  \
       5    15
      / \   / \
     2   7 12  20

特性：
1. 左子树 < 根节点 < 右子树
2. 自平衡（保证 O(log n)）
3. 中序遍历输出有序序列
```

**特点**：
- 每个节点包含 Key、Value、左子节点、右子节点、父节点、颜色
- 通过 `Comparator` 或 Key 的 `Comparable` 比较大小
- **有序**：遍历顺序按 Key 排序

---

## 核心区别详解

### 1. 有序性

#### HashMap：无序
```java
Map<Integer, String> hashMap = new HashMap<>();
hashMap.put(3, "C");
hashMap.put(1, "A");
hashMap.put(2, "B");

for (Integer key : hashMap.keySet()) {
    System.out.println(key);  // 可能输出 1, 2, 3 或其他顺序（不确定）
}
```

#### TreeMap：有序
```java
Map<Integer, String> treeMap = new TreeMap<>();
treeMap.put(3, "C");
treeMap.put(1, "A");
treeMap.put(2, "B");

for (Integer key : treeMap.keySet()) {
    System.out.println(key);  // 必定输出 1, 2, 3（升序）
}
```

---

### 2. 性能对比

| 操作 | HashMap | TreeMap |
|------|---------|---------|
| put(key, value) | O(1) 平均，O(n) 最坏 | **O(log n)** |
| get(key) | O(1) 平均，O(n) 最坏 | **O(log n)** |
| remove(key) | O(1) 平均，O(n) 最坏 | **O(log n)** |
| containsKey(key) | O(1) 平均 | **O(log n)** |
| firstKey() / lastKey() | ❌ 不支持 | **O(1)** |
| subMap() / headMap() / tailMap() | ❌ 不支持 | **O(log n)** |

**结论**：
- 单纯的增删改查：**HashMap 更快**
- 需要排序或范围查询：**TreeMap 更合适**

---

### 3. Null Key 支持

#### HashMap：允许一个 null Key
```java
Map<String, String> map = new HashMap<>();
map.put(null, "value");
map.put(null, "value2");  // 覆盖
System.out.println(map.get(null));  // value2
```

#### TreeMap：不允许 null Key
```java
Map<String, String> map = new TreeMap<>();
map.put(null, "value");  // ❌ NullPointerException

// 原因：TreeMap 需要比较 Key 大小
// null.compareTo(otherKey) 会抛出 NPE
```

**为什么 TreeMap 不支持 null Key？**
```java
// TreeMap 内部会调用 compare 方法
int cmp = k.compareTo(p.key);  // k 为 null 时抛出 NPE

// 或者使用 Comparator
int cmp = comparator.compare(k, p.key);  // k 为 null 时可能抛出 NPE
```

---

### 4. 排序机制

#### TreeMap 的两种排序方式

**方式 1：自然顺序（Key 实现 Comparable）**
```java
public class User implements Comparable<User> {
    private String name;
    private int age;

    @Override
    public int compareTo(User o) {
        return Integer.compare(this.age, o.age);  // 按年龄排序
    }
}

TreeMap<User, String> map = new TreeMap<>();
map.put(new User("张三", 25), "data1");
map.put(new User("李四", 20), "data2");
// 自动按年龄升序排序
```

**方式 2：自定义 Comparator**
```java
// 按 Key 降序
TreeMap<Integer, String> map = new TreeMap<>(Comparator.reverseOrder());
map.put(1, "A");
map.put(3, "C");
map.put(2, "B");
System.out.println(map.keySet());  // [3, 2, 1]

// 按字符串长度排序
TreeMap<String, Integer> map = new TreeMap<>((s1, s2) -> 
    Integer.compare(s1.length(), s2.length()));
map.put("Java", 1);
map.put("Python", 2);
map.put("Go", 3);
System.out.println(map.keySet());  // [Go, Java, Python]
```

---

### 5. 红黑树特性（TreeMap 底层）

**红黑树的 5 条性质**：
1. 每个节点是红色或黑色
2. 根节点是黑色
3. 所有叶子节点（NIL）是黑色
4. 红色节点的子节点必须是黑色（不能连续两个红色）
5. 从根到叶子的所有路径，黑色节点数量相同

**优点**：
- 保证最坏情况下 O(log n) 性能
- 自平衡，避免退化为链表

**TreeMap 节点定义**：
```java
static final class Entry<K,V> implements Map.Entry<K,V> {
    K key;
    V value;
    Entry<K,V> left;      // 左子节点
    Entry<K,V> right;     // 右子节点
    Entry<K,V> parent;    // 父节点
    boolean color = BLACK; // 节点颜色
}
```

---

## NavigableMap 扩展功能

TreeMap 实现了 **NavigableMap** 接口，提供丰富的导航方法：

```java
TreeMap<Integer, String> map = new TreeMap<>();
map.put(1, "A");
map.put(3, "C");
map.put(5, "E");
map.put(7, "G");

// 1. 获取边界
map.firstKey();     // 1（最小 Key）
map.lastKey();      // 7（最大 Key）
map.firstEntry();   // 1=A
map.lastEntry();    // 7=G

// 2. 查找相邻元素
map.lowerKey(5);    // 3（< 5 的最大 Key）
map.floorKey(4);    // 3（≤ 4 的最大 Key）
map.higherKey(5);   // 7（> 5 的最小 Key）
map.ceilingKey(4);  // 5（≥ 4 的最小 Key）

// 3. 范围视图
map.subMap(2, 6);   // {3=C, 5=E}（2 ≤ key < 6）
map.headMap(5);     // {1=A, 3=C}（key < 5）
map.tailMap(5);     // {5=E, 7=G}（key ≥ 5）

// 4. 逆序视图
NavigableMap<Integer, String> descendingMap = map.descendingMap();
System.out.println(descendingMap.keySet());  // [7, 5, 3, 1]
```

---

## 使用场景对比

### HashMap 适用场景

```java
// 1. 缓存（快速查找）
Map<String, User> userCache = new HashMap<>();

// 2. 计数器
Map<String, Integer> wordCount = new HashMap<>();
for (String word : words) {
    wordCount.put(word, wordCount.getOrDefault(word, 0) + 1);
}

// 3. 配置项（无序）
Map<String, String> config = new HashMap<>();
config.put("host", "localhost");
config.put("port", "8080");
```

---

### TreeMap 适用场景

```java
// 1. 需要排序的场景
Map<Integer, String> scoreboard = new TreeMap<>();
scoreboard.put(95, "Alice");
scoreboard.put(87, "Bob");
// 按分数自动排序

// 2. 范围查询
TreeMap<LocalDate, Order> orders = new TreeMap<>();
// 查询某个时间段的订单
Map<LocalDate, Order> weekOrders = orders.subMap(startDate, endDate);

// 3. TopK 问题
TreeMap<Integer, String> topK = new TreeMap<>(Comparator.reverseOrder());
// 保持前 K 个最大值

// 4. 优先级队列（需要动态修改优先级）
TreeMap<Integer, Task> priorityQueue = new TreeMap<>();

// 5. 滑动窗口中位数
TreeMap<Integer, Integer> window = new TreeMap<>();
```

---

## 实战示例

### 示例 1：实现 TopK

```java
public class TopKFinder {
    public static List<Integer> findTopK(int[] nums, int k) {
        // 使用 TreeMap 维护前 K 个最大值
        TreeMap<Integer, Integer> map = new TreeMap<>();
        
        for (int num : nums) {
            map.put(num, map.getOrDefault(num, 0) + 1);
            if (map.size() > k) {
                map.remove(map.firstKey());  // 移除最小值
            }
        }
        
        return new ArrayList<>(map.keySet());
    }
}
```

---

### 示例 2：区间合并

```java
public class IntervalMerger {
    public static List<int[]> merge(int[][] intervals) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        
        for (int[] interval : intervals) {
            int start = interval[0], end = interval[1];
            
            // 查找重叠区间
            Integer floorKey = map.floorKey(end);
            if (floorKey != null && map.get(floorKey) >= start) {
                // 合并区间
                start = Math.min(start, floorKey);
                end = Math.max(end, map.get(floorKey));
                map.remove(floorKey);
            }
            
            map.put(start, end);
        }
        
        List<int[]> result = new ArrayList<>();
        for (Map.Entry<Integer, Integer> entry : map.entrySet()) {
            result.add(new int[]{entry.getKey(), entry.getValue()});
        }
        return result;
    }
}
```

---

### 示例 3：LeetCode 时间范围查询

```java
class TimeMap {
    // key -> TreeMap<timestamp, value>
    private Map<String, TreeMap<Integer, String>> map;

    public TimeMap() {
        map = new HashMap<>();
    }

    public void set(String key, String value, int timestamp) {
        map.putIfAbsent(key, new TreeMap<>());
        map.get(key).put(timestamp, value);
    }

    public String get(String key, int timestamp) {
        if (!map.containsKey(key)) return "";
        TreeMap<Integer, String> treeMap = map.get(key);
        // 查找 ≤ timestamp 的最大时间戳
        Integer floorKey = treeMap.floorKey(timestamp);
        return floorKey == null ? "" : treeMap.get(floorKey);
    }
}
```

---

## 线程安全方案

### HashMap
```java
// 方案 1：Collections.synchronizedMap（性能差）
Map<K, V> syncMap = Collections.synchronizedMap(new HashMap<>());

// 方案 2：ConcurrentHashMap（推荐）
Map<K, V> concurrentMap = new ConcurrentHashMap<>();
```

### TreeMap
```java
// 方案 1：Collections.synchronizedSortedMap
SortedMap<K, V> syncMap = Collections.synchronizedSortedMap(new TreeMap<>());

// 方案 2：ConcurrentSkipListMap（推荐，基于跳表）
NavigableMap<K, V> concurrentMap = new ConcurrentSkipListMap<>();
```

---

## 性能测试对比

```java
public class MapPerformanceTest {
    public static void main(String[] args) {
        int n = 1000000;
        
        // HashMap 测试
        Map<Integer, Integer> hashMap = new HashMap<>();
        long start = System.currentTimeMillis();
        for (int i = 0; i < n; i++) {
            hashMap.put(i, i);
        }
        System.out.println("HashMap put: " + (System.currentTimeMillis() - start) + "ms");
        
        // TreeMap 测试
        Map<Integer, Integer> treeMap = new TreeMap<>();
        start = System.currentTimeMillis();
        for (int i = 0; i < n; i++) {
            treeMap.put(i, i);
        }
        System.out.println("TreeMap put: " + (System.currentTimeMillis() - start) + "ms");
    }
}

// 输出示例：
// HashMap put: 150ms
// TreeMap put: 800ms（TreeMap 约为 HashMap 的 5 倍）
```

---

## 面试总结

### 核心要点对比表

| 维度 | HashMap | TreeMap |
|------|---------|---------|
| **数据结构** | 哈希表 | 红黑树 |
| **有序性** | 无序 | 有序（Key 排序） |
| **null Key** | ✅ 允许 1 个 | ❌ 不允许 |
| **时间复杂度** | O(1) 平均 | O(log n) |
| **适用场景** | 快速查找、缓存 | 排序、范围查询 |
| **实现接口** | Map | Map + NavigableMap |
| **线程安全** | ❌（用 ConcurrentHashMap） | ❌（用 ConcurrentSkipListMap） |

---

### 记忆口诀

**HashMap**：
- **Hash 快**：O(1) 性能
- **Hash 乱**：无序存储
- **Hash 散**：分布在桶数组中

**TreeMap**：
- **Tree 稳**：O(log n) 稳定性能
- **Tree 序**：有序存储（Key 排序）
- **Tree 查**：支持范围查询

---

### 面试答题模板

> **HashMap** 基于哈希表实现，查找性能 O(1)，但无序；**TreeMap** 基于红黑树实现，查找性能 O(log n)，但保证 Key 有序。HashMap 适合快速查找和缓存场景，TreeMap 适合需要排序或范围查询的场景。需要注意的是，TreeMap 不支持 null Key（因为需要比较大小），而 HashMap 允许一个 null Key。在并发场景下，HashMap 对应 ConcurrentHashMap，TreeMap 对应 ConcurrentSkipListMap。

