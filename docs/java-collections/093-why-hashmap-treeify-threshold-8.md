---
layout: default
title: "HashMap为什么在链表长度为8时转为红黑树？"
parent: 集合框架
nav_order: 93
description: "深入解析HashMap树化阈值设计为8的原因，包括泊松分布理论、性能权衡和空间成本分析"
date: 2025-11-02
---
## 核心概念

HashMap 在 JDK 1.8 中引入了**链表转红黑树**的优化机制：当某个桶中的链表长度达到 **8** 且数组容量 ≥ 64 时，链表会转换为红黑树，从而将查询效率从 O(n) 提升到 O(log n)。

## 源码定义

```java
public class HashMap<K,V> extends AbstractMap<K,V> {
    /**
     * 树化阈值：链表长度达到 8 时转为红黑树
     */
    static final int TREEIFY_THRESHOLD = 8;
    
    /**
     * 退化阈值：红黑树节点数降到 6 时转回链表
     */
    static final int UNTREEIFY_THRESHOLD = 6;
    
    /**
     * 最小树化容量：数组容量小于 64 时，优先扩容而不是树化
     */
    static final int MIN_TREEIFY_CAPACITY = 64;
}
```

## 树化触发条件

```java
final V putVal(int hash, K key, V value, boolean onlyIfAbsent, boolean evict) {
    // ...
    for (int binCount = 0; ; ++binCount) {
        if ((e = p.next) == null) {
            p.next = newNode(hash, key, value, null);
            
            // 链表长度达到 8-1=7 时，插入第 8 个节点后触发树化
            if (binCount >= TREEIFY_THRESHOLD - 1)  // binCount 从 0 开始
                treeifyBin(tab, hash);
            break;
        }
        // ...
    }
}

final void treeifyBin(Node<K,V>[] tab, int hash) {
    int n, index; Node<K,V> e;
    
    // 如果数组容量 < 64，优先扩容而不是树化
    if (tab == null || (n = tab.length) < MIN_TREEIFY_CAPACITY)
        resize();
    else if ((e = tab[index = (n - 1) & hash]) != null) {
        // 将链表转换为红黑树
        TreeNode<K,V> hd = null, tl = null;
        do {
            TreeNode<K,V> p = replacementTreeNode(e, null);
            if (tl == null)
                hd = p;
            else {
                p.prev = tl;
                tl.next = p;
            }
            tl = p;
        } while ((e = e.next) != null);
        
        if ((tab[index] = hd) != null)
            hd.treeify(tab);  // 构建红黑树
    }
}
```

## 为什么是 8？

### 1. 泊松分布的理论依据

**源码注释中的说明**：

```java
/**
 * Because TreeNodes are about twice the size of regular nodes, we
 * use them only when bins contain enough nodes to warrant use
 * (see TREEIFY_THRESHOLD). And when they become too small (due to
 * removal or resizing) they are converted back to plain bins.
 * 
 * In usages with well-distributed user hashCodes, tree bins are
 * rarely used. Ideally, under random hashCodes, the frequency of
 * nodes in bins follows a Poisson distribution with a parameter
 * of about 0.5 on average, given the resizing threshold of 0.75,
 * although with a large variance because of resizing granularity.
 * 
 * Ignoring variance, the expected occurrences of list size k are
 * (exp(-0.5) * pow(0.5, k) / factorial(k)).
 * 
 * 0:    0.60653066
 * 1:    0.30326533
 * 2:    0.07581633
 * 3:    0.01263606
 * 4:    0.00157952
 * 5:    0.00015795
 * 6:    0.00001316
 * 7:    0.00000094
 * 8:    0.00000006
 * more: less than 1 in ten million
 */
```

**泊松分布概率表**：

| 链表长度 | 概率 | 说明 |
|---------|------|------|
| 0 | 60.65% | 桶为空 |
| 1 | 30.33% | 只有 1 个元素 |
| 2 | 7.58% | 2 个元素 |
| 3 | 1.26% | 3 个元素 |
| 4 | 0.16% | 4 个元素 |
| 5 | 0.016% | 5 个元素 |
| 6 | 0.0013% | 6 个元素 |
| 7 | 0.00009% | 7 个元素 |
| **8** | **0.000006%** | **≈千万分之一** |

**结论**：
- 在理想情况下（hashCode 分布均匀、负载因子 0.75），链表长度达到 8 的概率极低（千万分之一）
- 如果真的达到 8，说明可能出现了严重的哈希冲突，需要树化优化
- 8 是一个**极小概率事件**和**性能优化需求**的平衡点

### 2. 时间复杂度的权衡

**链表 vs 红黑树的查询性能**：

| 链表长度 | 链表查询 (O(n)) | 红黑树查询 (O(log n)) | 性能提升 |
|---------|----------------|---------------------|---------|
| 2 | 2 次 | 1 次 | 提升不明显 |
| 4 | 4 次 | 2 次 | 提升 50% |
| 8 | 8 次 | 3 次 | **提升 62.5%** |
| 16 | 16 次 | 4 次 | 提升 75% |
| 32 | 32 次 | 5 次 | 提升 84% |

**为什么不选更小的值（如 4 或 6）？**
- 红黑树节点占用空间约是链表节点的 **2 倍**
- 链表短时，转红黑树的性能提升不明显，但空间开销增加
- 8 是性能提升和空间开销的**最佳平衡点**

### 3. 节点空间开销对比

**链表节点（Node）**：
```java
static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;     // 4 字节
    final K key;        // 引用 8 字节（64位系统）
    V value;            // 引用 8 字节
    Node<K,V> next;     // 引用 8 字节
    // 总计：约 28 字节（不含对象头）
}
```

**红黑树节点（TreeNode）**：
```java
static final class TreeNode<K,V> extends LinkedHashMap.Entry<K,V> {
    final int hash;
    final K key;
    V value;
    Node<K,V> next;     // 继承的链表指针
    TreeNode<K,V> parent;  // 父节点 8 字节
    TreeNode<K,V> left;    // 左子节点 8 字节
    TreeNode<K,V> right;   // 右子节点 8 字节
    TreeNode<K,V> prev;    // 前驱节点 8 字节
    boolean red;           // 颜色 1 字节
    // 总计：约 61 字节（不含对象头）
}
```

**空间对比**：
```
8 个链表节点：8 × 28 = 224 字节
8 个树节点：8 × 61 = 488 字节
空间开销增加：488 / 224 ≈ 2.18 倍
```

**结论**：链表长度较短时（如 ≤ 4），转树带来的空间开销不值得。

### 4. 转换成本

**链表 → 红黑树的成本**：
- 需要遍历链表，构建树结构
- 需要进行红黑树的平衡操作（旋转、变色）
- 时间复杂度：O(n log n)

**示例代码**：
```java
final void treeify(Node<K,V>[] tab) {
    TreeNode<K,V> root = null;
    for (TreeNode<K,V> x = this, next; x != null; x = next) {
        next = (TreeNode<K,V>)x.next;
        x.left = x.right = null;
        if (root == null) {
            x.parent = null;
            x.red = false;
            root = x;
        }
        else {
            // 插入节点并维护红黑树性质
            // 包括旋转、变色等操作
        }
    }
    // ...
}
```

**权衡**：
- 链表长度为 2-4 时，转树的成本 > 收益
- 链表长度为 8 时，转树的成本 < 收益（查询性能提升显著）

## 为什么退化阈值是 6？

**退化条件**：
```java
final void split(HashMap<K,V> map, Node<K,V>[] tab, int index, int bit) {
    // ...
    if (loHead != null) {
        if (lc <= UNTREEIFY_THRESHOLD)  // lc <= 6
            tab[index] = loHead.untreeify(map);  // 转回链表
        else {
            // 保持红黑树
        }
    }
    // ...
}
```

**为什么是 6 而不是 8？**

1. **避免频繁转换**：
   - 如果树化阈值和退化阈值都是 8
   - 在 7-8 之间反复插入删除，会频繁触发转换
   - 造成性能抖动

2. **缓冲区设计**：
   ```
   链表 ←─ [6] ─── 缓冲区 ─── [8] ─→ 红黑树
   
   插入：6 → 7 → 8 → 树化
   删除：树 → 7 → 6 → 退化
   ```

3. **性能平滑过渡**：
   - 6-8 之间是一个"缓冲区"
   - 避免了临界点的抖动问题

**示例**：
```java
public class TreeifyTest {
    public static void main(String[] args) {
        Map<CollisionKey, Integer> map = new HashMap<>();
        
        // 插入 8 个冲突的 key
        for (int i = 0; i < 8; i++) {
            map.put(new CollisionKey(i), i);
        }
        // 此时已树化
        
        // 删除 2 个元素，剩余 6 个
        map.remove(new CollisionKey(0));
        map.remove(new CollisionKey(1));
        // 此时退化为链表
        
        // 再插入 1 个，变为 7 个
        map.put(new CollisionKey(10), 10);
        // 仍然是链表，不会立即树化
        
        // 再插入 1 个，变为 8 个
        map.put(new CollisionKey(11), 11);
        // 重新树化
    }
    
    static class CollisionKey {
        int value;
        CollisionKey(int value) { this.value = value; }
        
        @Override
        public int hashCode() { return 1; }  // 故意制造冲突
        
        @Override
        public boolean equals(Object obj) {
            return obj instanceof CollisionKey 
                && this.value == ((CollisionKey) obj).value;
        }
    }
}
```

## 实战场景

### 场景 1：构造哈希冲突测试

```java
public class HashMapTreeifyDemo {
    public static void main(String[] args) {
        Map<BadHashKey, String> map = new HashMap<>(64);
        
        // 插入 8 个 hash 冲突的元素
        for (int i = 0; i < 8; i++) {
            map.put(new BadHashKey(i), "value" + i);
        }
        
        // 查询性能测试
        long start = System.nanoTime();
        for (int i = 0; i < 10000; i++) {
            map.get(new BadHashKey(7));  // 查询最后一个
        }
        long end = System.nanoTime();
        
        System.out.println("查询耗时: " + (end - start) / 10000 + " ns/次");
        // 树化后查询更快
    }
    
    static class BadHashKey {
        int value;
        BadHashKey(int value) { this.value = value; }
        
        @Override
        public int hashCode() {
            return 1;  // 所有对象的 hash 都相同，制造冲突
        }
        
        @Override
        public boolean equals(Object obj) {
            return obj instanceof BadHashKey 
                && this.value == ((BadHashKey) obj).value;
        }
    }
}
```

### 场景 2：容量不足时的处理

```java
public class TreeifyCapacityTest {
    public static void main(String[] args) {
        // 初始容量只有 16
        Map<CollisionKey, Integer> map = new HashMap<>(16);
        
        // 插入 8 个冲突元素
        for (int i = 0; i < 8; i++) {
            map.put(new CollisionKey(i), i);
        }
        
        // 虽然链表长度达到 8，但容量 < 64
        // 所以触发扩容而不是树化
        // capacity: 16 → 32 → 64
        
        // 容量达到 64 后，再次发生冲突才会树化
    }
}
```

## 面试答题总结

**答题要点**：
1. **阈值**：链表长度 ≥ 8 且数组容量 ≥ 64 时树化
2. **理论依据**：泊松分布显示，链表长度达到 8 的概率极低（千万分之一）
3. **性能权衡**：O(n) → O(log n)，8 时性能提升明显（62.5%）
4. **空间成本**：红黑树节点是链表节点的 2 倍大小，8 是平衡点
5. **退化阈值 6**：避免在 7-8 之间频繁转换，设置缓冲区

**加分项**：
- 引用源码注释中的泊松分布数据
- 说明为什么退化阈值是 6 而不是 8
- 提到容量 < 64 时优先扩容
- 对比链表和红黑树的空间开销

**一句话总结**：8 是基于泊松分布理论、性能提升和空间开销综合考虑的最优阈值，既保证了极端情况下的性能，又控制了内存开销。

