---
title: "为什么HashMap有时候链表长度超过8也不树化？"
date: 2025-11-02
categories: [Java, 集合框架]
tags: [HashMap, 红黑树, 树化条件]
description: "解析HashMap树化的双重条件，理解为何链表长度达到8时不一定会转为红黑树"
nav_order: 95
parent: 集合框架
---
## 核心概念

HashMap 的树化并非仅由链表长度决定，而是需要同时满足**两个条件**：
1. 链表长度 ≥ 8
2. **数组容量 ≥ 64**

当链表长度达到 8 但数组容量小于 64 时，HashMap 会**优先扩容**而不是树化。

## 源码分析

### 树化的完整判断逻辑

```java
final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    // ...
    for (int binCount = 0; ; ++binCount) {
        if ((e = p.next) == null) {
            p.next = newNode(hash, key, value, null);
            
            // 链表长度达到阈值（8）时，尝试树化
            if (binCount >= TREEIFY_THRESHOLD - 1)  // -1 for 1st
                treeifyBin(tab, hash);  // ← 注意：这里是"尝试"树化
            break;
        }
        // ...
    }
}

final void treeifyBin(Node<K,V>[] tab, int hash) {
    int n, index; Node<K,V> e;
    
    // 关键判断：容量是否足够
    if (tab == null || (n = tab.length) < MIN_TREEIFY_CAPACITY)
        resize();  // ← 容量不足，优先扩容而不是树化
    else if ((e = tab[index = (n - 1) & hash]) != null) {
        // 容量充足，执行树化
        TreeNode<K,V> hd = null, tl = null;
        do {
            TreeNode<K,V> p = replacementTreeNode(e, null);
            // ... 构建红黑树
        } while ((e = e.next) != null);
        
        if ((tab[index] = hd) != null)
            hd.treeify(tab);
    }
}
```

### 关键常量

```java
/**
 * 树化阈值：链表长度达到 8
 */
static final int TREEIFY_THRESHOLD = 8;

/**
 * 最小树化容量：数组容量必须 ≥ 64
 */
static final int MIN_TREEIFY_CAPACITY = 64;
```

## 为什么需要容量限制？

### 1. 扩容可以有效减少冲突

**原理**：
- 容量较小时，即使 hash 分布均匀，冲突也较多
- 扩容后容量翻倍，元素重新分配，冲突自然减少
- 链表长度可能从 8 降到 4 或更少

**示例**：
```java
public class ResizeVsTreeifyTest {
    public static void main(String[] args) {
        // 场景：容量为 16，插入 16 个元素，恰好都冲突
        Map<BadHashKey, Integer> map = new HashMap<>(16);
        
        // 模拟：所有元素映射到 index = 0
        for (int i = 0; i < 16; i++) {
            map.put(new BadHashKey(i), i);
        }
        // 此时 index=0 的链表长度可能达到 16
        
        // 因为容量 16 < 64，触发扩容到 32
        // 扩容后，原来在 index=0 的元素会分散到 index=0 和 index=16
        // 链表长度可能从 16 降到 8 和 8，或其他分布
        
        // 继续触发扩容到 64
        // 元素进一步分散，冲突进一步减少
    }
    
    static class BadHashKey {
        int value;
        BadHashKey(int value) { this.value = value; }
        
        @Override
        public int hashCode() {
            return value;  // 简单的 hash
        }
        
        @Override
        public boolean equals(Object obj) {
            return obj instanceof BadHashKey 
                && this.value == ((BadHashKey) obj).value;
        }
    }
}
```

**扩容效果图**：
```
容量 16，index=0 位置冲突：
[0] → A → B → C → D → E → F → G → H (链表长度 8)

扩容到 32 后：
[0]  → A → C → E → G (链表长度 4)
[16] → B → D → F → H (链表长度 4)

扩容到 64 后：
[0]  → A → E (链表长度 2)
[16] → B → F (链表长度 2)
[32] → C → G (链表长度 2)
[48] → D → H (链表长度 2)
```

### 2. 避免过早树化浪费内存

**红黑树节点的空间开销**：
```java
// 链表节点：约 28 字节
static class Node<K,V> {
    int hash;       // 4 字节
    K key;          // 8 字节（引用）
    V value;        // 8 字节（引用）
    Node<K,V> next; // 8 字节（引用）
}

// 红黑树节点：约 61 字节
static final class TreeNode<K,V> extends LinkedHashMap.Entry<K,V> {
    int hash;
    K key;
    V value;
    Node<K,V> next;
    TreeNode<K,V> parent;  // +8 字节
    TreeNode<K,V> left;    // +8 字节
    TreeNode<K,V> right;   // +8 字节
    TreeNode<K,V> prev;    // +8 字节
    boolean red;           // +1 字节
}
```

**空间对比**：
```
容量较小时，多个桶可能都达到树化条件
容量 16，假设 4 个桶需要树化，每个桶 8 个节点：
- 链表方式：4 × 8 × 28 = 896 字节
- 红黑树方式：4 × 8 × 61 = 1952 字节
- 额外开销：1952 - 896 = 1056 字节

容量 64，扩容后冲突分散，可能只有 1 个桶需要树化：
- 链表方式：1 × 8 × 28 = 224 字节
- 红黑树方式：1 × 8 × 61 = 488 字节
- 额外开销：488 - 224 = 264 字节
```

### 3. 扩容成本低于树化成本

**容量较小时的成本对比**：

| 操作 | 时间复杂度 | 说明 |
|------|-----------|------|
| 扩容 | O(n) | n 为总元素数 |
| 树化 | O(k log k) | k 为单个桶的元素数 |
| 多桶树化 | O(m × k log k) | m 为需要树化的桶数 |

**示例**：
```
场景：容量 16，总元素 64，4 个桶各有 16 个元素

方案1：扩容
- 耗时：O(64) = 64 次操作
- 效果：冲突减少，可能不再需要树化

方案2：树化 4 个桶
- 耗时：4 × O(16 log 16) = 4 × 64 = 256 次操作
- 效果：内存占用增加，且扩容时还要处理树节点
```

**结论**：容量较小时，扩容是更经济的选择。

## 详细流程演示

### 场景 1：容量不足，不会树化

```java
public class NoTreeifyWhenSmallCapacity {
    public static void main(String[] args) throws Exception {
        // 初始容量 8（小于 64）
        Map<CollisionKey, Integer> map = new HashMap<>(8);
        System.out.println("初始容量: " + getCapacity(map));
        
        // 插入 8 个 hash 冲突的元素
        for (int i = 0; i < 8; i++) {
            map.put(new CollisionKey(i), i);
            System.out.println("插入第 " + (i+1) + " 个元素，容量: " + getCapacity(map));
        }
        
        // 观察：容量会多次扩容，但不会树化
    }
    
    static class CollisionKey {
        int value;
        CollisionKey(int value) { this.value = value; }
        
        @Override
        public int hashCode() { return 1; }
        
        @Override
        public boolean equals(Object obj) {
            return obj instanceof CollisionKey 
                && this.value == ((CollisionKey) obj).value;
        }
    }
    
    static int getCapacity(Map<?, ?> map) throws Exception {
        java.lang.reflect.Field tableField = HashMap.class.getDeclaredField("table");
        tableField.setAccessible(true);
        Object[] table = (Object[]) tableField.get(map);
        return table == null ? 0 : table.length;
    }
}
```

**输出**：
```
初始容量: 0
插入第 1 个元素，容量: 8
插入第 2 个元素，容量: 8
...
插入第 7 个元素，容量: 16   ← 触发扩容（因为 8 × 0.75 = 6）
插入第 8 个元素，容量: 16
继续插入...
最终容量: 64 或更大
```

### 场景 2：容量充足，成功树化

```java
public class TreeifyWhenCapacityEnough {
    public static void main(String[] args) {
        // 初始容量 64（足够大）
        Map<CollisionKey, Integer> map = new HashMap<>(64);
        
        // 插入 8 个 hash 冲突的元素
        for (int i = 0; i < 8; i++) {
            map.put(new CollisionKey(i), i);
        }
        
        // 此时会树化：链表 → 红黑树
        System.out.println("已树化，查询性能提升");
        
        // 性能测试
        long start = System.nanoTime();
        for (int i = 0; i < 10000; i++) {
            map.get(new CollisionKey(7));  // 查询最后一个
        }
        long end = System.nanoTime();
        
        System.out.println("平均查询耗时: " + (end - start) / 10000 + " ns");
        // 红黑树：O(log 8) = 3 次比较
        // 链表：O(8) = 最多 8 次比较
    }
    
    static class CollisionKey {
        int value;
        CollisionKey(int value) { this.value = value; }
        
        @Override
        public int hashCode() { return 1; }
        
        @Override
        public boolean equals(Object obj) {
            return obj instanceof CollisionKey 
                && this.value == ((CollisionKey) obj).value;
        }
    }
}
```

## 完整树化判断流程

```
插入元素，链表长度达到 8
    ↓
调用 treeifyBin()
    ↓
判断：容量 >= 64？
    ↓               ↓
   是              否
    ↓               ↓
  树化           扩容
    ↓               ↓
转为红黑树      容量翻倍
    ↓               ↓
查询 O(log n)   元素重新分配
                    ↓
                链表长度可能减少
                    ↓
                  继续判断...
```

## 设计思想总结

### 1. 渐进式优化

```
阶段1：容量小，元素少
→ 使用链表，简单高效

阶段2：容量小，冲突多
→ 扩容，减少冲突

阶段3：容量大，局部冲突严重
→ 树化，优化极端情况
```

### 2. 性能与空间的权衡

```
容量 < 64：
- 扩容成本低
- 冲突减少效果好
- 内存开销小

容量 ≥ 64：
- 扩容成本高（元素多）
- 冲突可能是数据本身问题
- 树化是更好的选择
```

### 3. 双阈值机制

```java
// 树化条件
if (链表长度 >= 8 && 容量 >= 64) {
    树化;
}

// 退化条件
if (树节点数 <= 6) {
    退化为链表;
}
```

## 实战建议

### 1. 预估容量，避免频繁扩容

```java
// 错误：容量太小，可能频繁扩容
Map<String, Object> map1 = new HashMap<>(8);

// 正确：预估数据量，一次性分配足够空间
int expectedSize = 100;
Map<String, Object> map2 = new HashMap<>((int)(expectedSize / 0.75 + 1));
```

### 2. 理解树化的触发条件

```java
// 场景1：容量不足，不会树化
Map<Key, Value> map1 = new HashMap<>(16);  // 容量 < 64
// 即使某个桶的链表长度达到 8，也会先扩容

// 场景2：容量充足，可能树化
Map<Key, Value> map2 = new HashMap<>(128);  // 容量 >= 64
// 某个桶的链表长度达到 8 时，会树化
```

### 3. 优化 hashCode 实现

```java
// 避免大量 hash 冲突
public class GoodHashKey {
    private final int id;
    private final String name;
    
    @Override
    public int hashCode() {
        // 使用多个字段计算 hash，减少冲突
        return Objects.hash(id, name);
    }
    
    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (!(obj instanceof GoodHashKey)) return false;
        GoodHashKey other = (GoodHashKey) obj;
        return id == other.id && Objects.equals(name, other.name);
    }
}
```

## 面试答题总结

**答题要点**：
1. **双重条件**：链表长度 ≥ 8 **且** 数组容量 ≥ 64
2. **优先扩容**：容量 < 64 时，优先扩容而不是树化
3. **设计原因**：
   - 扩容可以有效减少冲突
   - 避免过早树化浪费内存
   - 小容量时扩容成本更低

**加分项**：
- 画图说明扩容后元素重新分配的效果
- 对比扩容和树化的时间/空间成本
- 提到红黑树节点是链表节点的 2 倍大小
- 说明为什么容量阈值选择 64

**一句话总结**：链表长度达到 8 只是树化的必要条件，还需要容量 ≥ 64 才会树化，否则优先通过扩容来减少冲突。

