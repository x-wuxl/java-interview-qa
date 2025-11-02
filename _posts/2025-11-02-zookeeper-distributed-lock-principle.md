---
layout: post
title: "Zookeeper实现分布式锁的原理？"
date: 2025-11-02
categories: [分布式, 分布式锁, Zookeeper]
tags: [Zookeeper, 分布式锁, 临时顺序节点, Curator]
description: "深入剖析Zookeeper分布式锁的实现原理：临时顺序节点、监听机制、公平性保证及Curator框架实现"
---

## 核心概念

Zookeeper 分布式锁的核心是利用 **临时顺序节点（Ephemeral Sequential Node）** 和 **监听机制（Watcher）** 实现。相比 Redis，Zookeeper 基于 ZAB 协议提供**强一致性**保证，天然支持**公平锁**和**自动释放**，适合对可靠性要求极高的场景。

## 一、核心原理

### 1.1 Zookeeper 节点类型

```
持久节点（Persistent）
├─ 持久顺序节点（Persistent Sequential）
临时节点（Ephemeral）
└─ 临时顺序节点（Ephemeral Sequential）  ← 用于实现分布式锁
```

**临时顺序节点的特性：**
- **临时性**：客户端断开连接后，节点自动删除（避免死锁）
- **顺序性**：节点名称自动追加递增序号（如 `lock_0000000001`、`lock_0000000002`）

### 1.2 加锁流程

```
/locks (持久节点，锁的根目录)
├─ lock_0000000001 (客户端 A)  ← 序号最小，获得锁
├─ lock_0000000002 (客户端 B)  ← 监听 lock_0000000001
├─ lock_0000000003 (客户端 C)  ← 监听 lock_0000000002
```

**详细步骤：**

1. **创建临时顺序节点**
   ```java
   String nodePath = zkClient.create("/locks/lock_", 
       new byte[0], 
       ZooDefs.Ids.OPEN_ACL_UNSAFE, 
       CreateMode.EPHEMERAL_SEQUENTIAL);
   // 返回：/locks/lock_0000000001
   ```

2. **获取所有子节点并排序**
   ```java
   List<String> children = zkClient.getChildren("/locks", false);
   Collections.sort(children);
   // 结果：[lock_0000000001, lock_0000000002, lock_0000000003]
   ```

3. **判断是否获得锁**
   ```java
   String currentNode = nodePath.substring(nodePath.lastIndexOf("/") + 1);
   if (currentNode.equals(children.get(0))) {
       // 当前节点是最小的，获得锁
       return true;
   }
   ```

4. **未获得锁，监听前一个节点**
   ```java
   // 找到比自己小的前一个节点
   int index = children.indexOf(currentNode);
   String prevNode = children.get(index - 1);
   
   // 监听前一个节点的删除事件
   Stat stat = zkClient.exists("/locks/" + prevNode, new Watcher() {
       @Override
       public void process(WatchedEvent event) {
           if (event.getType() == Event.EventType.NodeDeleted) {
               // 前一个节点被删除，重新尝试获取锁
               synchronized (lock) {
                   lock.notify();
               }
           }
       }
   });
   ```

5. **阻塞等待**
   ```java
   synchronized (lock) {
       lock.wait(); // 等待被唤醒
   }
   ```

### 1.3 解锁流程

**直接删除自己创建的节点：**
```java
zkClient.delete(nodePath, -1);
// 触发下一个节点的监听器，下一个节点获得锁
```

## 二、核心特性

### 2.1 自动释放（避免死锁）

**临时节点的生命周期：**
```
客户端创建临时节点 → 客户端保持会话 → 客户端断开连接 → ZK 自动删除节点
```

**心跳机制：**
- 客户端定期向 ZK 发送心跳（默认 1/3 sessionTimeout）
- 超过 `sessionTimeout` 未收到心跳，ZK 认为客户端挂掉，删除其临时节点

```java
CuratorFramework client = CuratorFrameworkFactory.builder()
    .connectString("localhost:2181")
    .sessionTimeoutMs(30000)  // 会话超时 30 秒
    .connectionTimeoutMs(5000)
    .build();
```

### 2.2 公平性保证

**公平锁的本质：** 按照请求锁的顺序依次获得锁（先到先得）

**Zookeeper 的实现：**
- 临时顺序节点的序号严格递增
- 只有序号最小的节点持有锁
- 其他节点按序号排队等待

**对比 Redis：** Redis 默认不保证公平性（抢占式），需要额外实现队列

### 2.3 避免惊群效应

**什么是惊群效应？**

```
错误实现：所有客户端都监听锁节点
lock (客户端 A 持有)
├─ 观察者：客户端 B、C、D、E ... (数千个)
当 A 释放锁时 → 所有观察者被唤醒 → 只有一个能获得锁 → 大量无效唤醒
```

**Zookeeper 的优化：**

```
正确实现：链式监听（每个节点只监听前一个节点）
lock_0000000001 (客户端 A 持有)
  ↑ 监听
lock_0000000002 (客户端 B)
  ↑ 监听
lock_0000000003 (客户端 C)
  ↑ 监听
lock_0000000004 (客户端 D)

当 A 释放锁时 → 只有 B 被唤醒 → B 获得锁
```

**效果：** 每次只唤醒一个客户端，避免大量无效唤醒

### 2.4 强一致性

**ZAB 协议保证：**
- 所有写操作（创建/删除节点）都通过 Leader 节点
- Leader 将操作同步给过半数 Follower 后才返回成功
- 读操作可以从任意节点读取（但可能有短暂延迟）

**对比 Redis：**
- Redis 主从复制是异步的，主节点宕机可能导致锁丢失
- Zookeeper 保证写操作的强一致性

## 三、Curator 框架实现

Apache Curator 是 Netflix 开源的 Zookeeper 客户端框架，封装了分布式锁的完整实现。

### 3.1 基本使用

```java
@Component
public class ZookeeperLockService {
    
    @Autowired
    private CuratorFramework curatorFramework;
    
    /**
     * 可重入排他锁
     */
    public void lockWithRetry(String lockPath) {
        InterProcessMutex lock = new InterProcessMutex(
            curatorFramework, 
            lockPath
        );
        
        try {
            // 尝试获取锁，最多等待 10 秒
            if (lock.acquire(10, TimeUnit.SECONDS)) {
                try {
                    // 执行业务逻辑
                    doBusinessLogic();
                } finally {
                    // 释放锁
                    lock.release();
                }
            } else {
                throw new RuntimeException("获取锁超时");
            }
        } catch (Exception e) {
            throw new RuntimeException("锁操作失败", e);
        }
    }
}
```

### 3.2 Curator 提供的锁类型

```java
// 1. 可重入排他锁（最常用）
InterProcessMutex mutex = new InterProcessMutex(client, "/locks/mylock");

// 2. 不可重入排他锁
InterProcessSemaphoreMutex semaphoreMutex = 
    new InterProcessSemaphoreMutex(client, "/locks/mylock");

// 3. 可重入读写锁
InterProcessReadWriteLock rwLock = 
    new InterProcessReadWriteLock(client, "/locks/mylock");
InterProcessMutex readLock = rwLock.readLock();
InterProcessMutex writeLock = rwLock.writeLock();

// 4. 信号量（限流）
InterProcessSemaphoreV2 semaphore = 
    new InterProcessSemaphoreV2(client, "/locks/semaphore", 5); // 最多 5 个并发

// 5. 多锁（同时获取多个资源的锁）
InterProcessMultiLock multiLock = new InterProcessMultiLock(
    Arrays.asList(lock1, lock2, lock3)
);
```

### 3.3 核心源码分析

**InterProcessMutex 加锁逻辑（简化）：**

```java
public boolean acquire(long time, TimeUnit unit) throws Exception {
    long startMillis = System.currentTimeMillis();
    Long millisToWait = (unit != null) ? unit.toMillis(time) : null;
    
    boolean hasTheLock = false;
    boolean isDone = false;
    int retryCount = 0;
    
    while (!isDone) {
        isDone = true;
        try {
            // 尝试创建临时顺序节点
            ourPath = driver.createsTheLock(client, path, localLockNodeBytes);
            
            // 判断是否获得锁
            hasTheLock = internalLockLoop(startMillis, millisToWait, ourPath);
        } catch (KeeperException.NoNodeException e) {
            // 父节点不存在，创建父节点后重试
            if (retryCount++ < MAX_RETRY_COUNT) {
                isDone = false;
            } else {
                throw e;
            }
        }
    }
    
    return hasTheLock;
}

private boolean internalLockLoop(long startMillis, Long millisToWait, String ourPath) 
    throws Exception {
    
    boolean haveTheLock = false;
    boolean doDelete = false;
    
    try {
        while (!haveTheLock) {
            // 获取所有子节点并排序
            List<String> children = getSortedChildren();
            String sequenceNodeName = ourPath.substring(basePath.length() + 1);
            
            // 判断是否是最小节点
            int ourIndex = children.indexOf(sequenceNodeName);
            if (ourIndex < 0) {
                throw new Exception("节点不存在: " + sequenceNodeName);
            }
            
            // 是最小节点，获得锁
            boolean isLowestNode = (ourIndex == 0);
            if (isLowestNode) {
                haveTheLock = true;
            } else {
                // 监听前一个节点
                String previousSequencePath = basePath + "/" + children.get(ourIndex - 1);
                synchronized (this) {
                    Stat stat = client.checkExists()
                        .usingWatcher(watcher)
                        .forPath(previousSequencePath);
                    
                    if (stat != null) {
                        // 前一个节点存在，等待通知
                        if (millisToWait != null) {
                            millisToWait -= (System.currentTimeMillis() - startMillis);
                            if (millisToWait <= 0) {
                                doDelete = true; // 超时，删除节点
                                break;
                            }
                            this.wait(millisToWait);
                        } else {
                            this.wait();
                        }
                    }
                    // 前一个节点不存在，重新循环检查
                }
            }
        }
    } catch (Exception e) {
        doDelete = true;
        throw e;
    } finally {
        if (doDelete) {
            deleteOurPath(ourPath);
        }
    }
    
    return haveTheLock;
}
```

## 四、实战优化

### 4.1 可重入锁实现

**原理：** 在本地维护一个线程-重入次数的映射

```java
public class ReentrantZkLock {
    private final ConcurrentMap<Thread, LockData> threadData = new ConcurrentHashMap<>();
    
    private static class LockData {
        final Thread owningThread;
        final String lockPath;
        final AtomicInteger lockCount = new AtomicInteger(1);
        
        private LockData(Thread owningThread, String lockPath) {
            this.owningThread = owningThread;
            this.lockPath = lockPath;
        }
    }
    
    public void lock() throws Exception {
        Thread currentThread = Thread.currentThread();
        LockData lockData = threadData.get(currentThread);
        
        if (lockData != null) {
            // 可重入，计数 +1
            lockData.lockCount.incrementAndGet();
            return;
        }
        
        // 首次加锁，创建 ZK 节点
        String lockPath = attemptLock();
        lockData = new LockData(currentThread, lockPath);
        threadData.put(currentThread, lockData);
    }
    
    public void unlock() throws Exception {
        Thread currentThread = Thread.currentThread();
        LockData lockData = threadData.get(currentThread);
        
        if (lockData == null) {
            throw new IllegalMonitorStateException("未持有锁");
        }
        
        int newLockCount = lockData.lockCount.decrementAndGet();
        if (newLockCount > 0) {
            // 还有重入，不释放 ZK 节点
            return;
        }
        
        if (newLockCount < 0) {
            throw new IllegalMonitorStateException("重入次数异常");
        }
        
        // 释放 ZK 节点
        try {
            zkClient.delete(lockData.lockPath, -1);
        } finally {
            threadData.remove(currentThread);
        }
    }
}
```

### 4.2 羊群效应优化（已内置）

Curator 默认使用链式监听，每个节点只监听前一个节点，避免惊群效应。

### 4.3 异常处理

```java
public void robustLock(String lockPath) {
    InterProcessMutex lock = new InterProcessMutex(curatorFramework, lockPath);
    
    try {
        if (!lock.acquire(10, TimeUnit.SECONDS)) {
            throw new TimeoutException("获取锁超时");
        }
        
        try {
            doBusinessLogic();
        } finally {
            // 确保释放锁
            lock.release();
        }
    } catch (Exception e) {
        log.error("锁操作失败", e);
        // 降级处理
        handleFallback();
    }
}
```

## 五、优缺点分析

### 优点

1. **强一致性**：基于 ZAB 协议，保证数据一致性
2. **自动释放**：临时节点机制，客户端挂掉自动释放
3. **公平性**：顺序节点保证先到先得
4. **阻塞等待**：基于监听机制，不需要轮询
5. **避免惊群**：链式监听，每次只唤醒一个客户端

### 缺点

1. **性能相对较低**：网络开销大，不如 Redis
2. **运维复杂**：需要维护 ZK 集群（至少 3 个节点）
3. **学习成本高**：ZK 本身较复杂

## 六、与 Redis 锁对比

| 特性 | Zookeeper | Redis |
|------|-----------|-------|
| **一致性** | 强一致性（CP） | 最终一致性（AP） |
| **性能** | 中等（写操作需过半数确认） | 高（内存操作） |
| **公平性** | 天然公平（顺序节点） | 默认不公平 |
| **自动释放** | 临时节点自动删除 | 需设置过期时间 |
| **阻塞等待** | 监听机制，高效 | pub/sub 或轮询 |
| **锁丢失风险** | 极低（强一致性） | 主从切换时可能丢失 |
| **运维成本** | 高（需维护集群） | 低 |
| **适用场景** | 选主、配置中心 | 高并发、秒杀 |

## 答题总结

**Zookeeper 分布式锁的核心原理：**

1. **临时顺序节点**：
   - 客户端创建 `EPHEMERAL_SEQUENTIAL` 节点
   - 临时性保证客户端断开时自动释放
   - 顺序性保证公平获取锁

2. **加锁流程**：
   - 创建临时顺序节点
   - 获取所有子节点并排序
   - 判断自己是否是最小节点（是则获得锁）
   - 否则监听前一个节点，等待其释放

3. **核心优势**：
   - **强一致性**：基于 ZAB 协议
   - **自动释放**：临时节点机制
   - **天然公平**：顺序节点排队
   - **避免惊群**：链式监听

4. **实际使用**：推荐使用 **Apache Curator** 框架，提供了完善的锁实现（InterProcessMutex）

**选择建议：**
- 性能优先、高并发 → Redis
- 可靠性优先、强一致性 → Zookeeper
- 选主、配置管理 → Zookeeper

