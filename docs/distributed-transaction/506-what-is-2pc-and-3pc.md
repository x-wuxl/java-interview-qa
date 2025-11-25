---
layout: default
title: "什么是2PC和3PC？"
parent: 分布式事务
nav_order: 506
description: "深入剖析两阶段提交（2PC）和三阶段提交（3PC）的原理、流程、优缺点以及在分布式事务中的应用，理解刚性事务的实现机制"
author: "wuxl"
date: 2025-11-02
---
## 问题

什么是2PC和3PC？

## 答案

### 1. 2PC（Two-Phase Commit，两阶段提交）

#### 核心概念

2PC是一种强一致性的分布式事务协议，通过**协调者（Coordinator）**和**参与者（Participant）**两种角色，分两个阶段完成分布式事务的提交。

**角色说明**：
- **协调者（TC, Transaction Coordinator）**：事务管理器，负责协调整个分布式事务
- **参与者（RM, Resource Manager）**：资源管理器，通常是数据库，执行实际的事务操作

#### 执行流程

**阶段一：准备阶段（Prepare Phase）**

```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------Prepare------------>|                        |                        |
  |------Prepare---------------------------->         |                        |
  |------Prepare------------------------------------------------>              |
  |                          |                        |                        |
  |                     [执行事务]                [执行事务]                [执行事务]
  |                     [记录Undo/Redo日志]     [记录Undo/Redo日志]     [记录Undo/Redo日志]
  |                     [锁定资源]              [锁定资源]              [锁定资源]
  |                          |                        |                        |
  |<-----Yes/No--------------|                        |                        |
  |<-----Yes/No---------------------------------      |                        |
  |<-----Yes/No------------------------------------------------               |
```

**协调者操作**：
1. 向所有参与者发送 `Prepare` 请求
2. 等待所有参与者的响应

**参与者操作**：
1. 执行事务操作（但不提交）
2. 将Undo和Redo信息写入日志
3. 锁定相关资源
4. 向协调者返回 `Yes`（准备成功）或 `No`（准备失败）

**阶段二：提交阶段（Commit Phase）**

**情况1：所有参与者都返回Yes（成功路径）**

```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------Commit------------->|                        |                        |
  |------Commit----------------------------->         |                        |
  |------Commit------------------------------------------------>              |
  |                          |                        |                        |
  |                     [提交事务]                [提交事务]                [提交事务]
  |                     [释放锁]                  [释放锁]                  [释放锁]
  |                          |                        |                        |
  |<-----ACK-----------------|                        |                        |
  |<-----ACK---------------------------------         |                        |
  |<-----ACK------------------------------------------------               |
```

**情况2：任一参与者返回No或超时（失败路径）**

```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------Rollback----------->|                        |                        |
  |------Rollback--------------------------->         |                        |
  |------Rollback----------------------------------------------->              |
  |                          |                        |                        |
  |                     [回滚事务]                [回滚事务]                [回滚事务]
  |                     [释放锁]                  [释放锁]                  [释放锁]
  |                          |                        |                        |
  |<-----ACK-----------------|                        |                        |
  |<-----ACK---------------------------------         |                        |
  |<-----ACK------------------------------------------------               |
```

#### 代码实现示例

```java
/**
 * 2PC协调者实现
 */
public class TwoPhaseCommitCoordinator {
    
    private List<Participant> participants;
    
    public boolean execute(Transaction transaction) {
        // ============ 阶段一：准备阶段 ============
        List<Boolean> prepareResults = new ArrayList<>();
        
        for (Participant participant : participants) {
            try {
                // 发送Prepare请求
                boolean result = participant.prepare(transaction);
                prepareResults.add(result);
                
                if (!result) {
                    // 有参与者准备失败，提前结束
                    break;
                }
            } catch (Exception e) {
                // 网络异常或超时，视为失败
                prepareResults.add(false);
                break;
            }
        }
        
        // 判断是否所有参与者都准备成功
        boolean allPrepared = prepareResults.size() == participants.size()
                && prepareResults.stream().allMatch(r -> r);
        
        // ============ 阶段二：提交或回滚阶段 ============
        if (allPrepared) {
            // 所有参与者准备成功，发送Commit命令
            for (Participant participant : participants) {
                try {
                    participant.commit(transaction);
                } catch (Exception e) {
                    // 提交失败，需要重试或人工介入
                    log.error("Commit failed for participant: {}", participant, e);
                }
            }
            return true;
        } else {
            // 有参与者准备失败，发送Rollback命令
            for (Participant participant : participants) {
                try {
                    participant.rollback(transaction);
                } catch (Exception e) {
                    // 回滚失败，需要重试或人工介入
                    log.error("Rollback failed for participant: {}", participant, e);
                }
            }
            return false;
        }
    }
}

/**
 * 参与者实现
 */
public class DatabaseParticipant implements Participant {
    
    private DataSource dataSource;
    private Connection connection;
    
    @Override
    public boolean prepare(Transaction transaction) {
        try {
            // 获取数据库连接
            connection = dataSource.getConnection();
            connection.setAutoCommit(false);
            
            // 执行事务操作
            PreparedStatement stmt = connection.prepareStatement(transaction.getSql());
            stmt.execute();
            
            // 事务执行成功但不提交，资源被锁定
            return true;
        } catch (Exception e) {
            // 执行失败
            try {
                if (connection != null) {
                    connection.rollback();
                }
            } catch (SQLException ex) {
                log.error("Rollback failed", ex);
            }
            return false;
        }
    }
    
    @Override
    public void commit(Transaction transaction) {
        try {
            if (connection != null) {
                connection.commit();
                connection.close();
            }
        } catch (SQLException e) {
            log.error("Commit failed", e);
            throw new RuntimeException(e);
        }
    }
    
    @Override
    public void rollback(Transaction transaction) {
        try {
            if (connection != null) {
                connection.rollback();
                connection.close();
            }
        } catch (SQLException e) {
            log.error("Rollback failed", e);
        }
    }
}
```

#### 2PC的问题

**问题1：同步阻塞**
```
时间线：
t0: 协调者发送Prepare
t1: 参与者执行事务，锁定资源
t2-t10: 等待协调者的Commit/Rollback命令
      ↑
      资源被长时间锁定，其他事务无法访问
```
参与者在准备阶段锁定资源后，需要等待协调者的最终指令，期间资源被阻塞。

**问题2：单点故障**
```
场景：协调者在发送Commit前崩溃
协调者[崩溃] X
  |
  |-----Prepare---->参与者1 [阻塞等待]
  |-----Prepare---->参与者2 [阻塞等待]
  |-----Prepare---->参与者3 [阻塞等待]
  
结果：所有参与者持续等待，资源无法释放
```

**问题3：数据不一致**
```
场景：协调者发送Commit时发生网络分区
协调者
  |-----Commit---->参与者1 [收到，提交] ✓
  |-----Commit--X  参与者2 [未收到，阻塞] ?
  |-----Commit--X  参与者3 [未收到，阻塞] ?
  
结果：参与者1已提交，参与者2、3不知是提交还是回滚
```

**问题4：容错性差**
- 协调者和参与者都可能成为单点
- 没有超时机制，故障恢复困难

### 2. 3PC（Three-Phase Commit，三阶段提交）

#### 核心概念

3PC是2PC的改进版本，将准备阶段拆分为 **CanCommit** 和 **PreCommit** 两个阶段，并引入**超时机制**。

#### 执行流程

**阶段一：CanCommit（询问阶段）**

```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------CanCommit?--------->|                        |                        |
  |------CanCommit?----------------------------->     |                        |
  |------CanCommit?------------------------------------------------>          |
  |                          |                        |                        |
  |                     [检查资源]                [检查资源]                [检查资源]
  |                     [不执行事务]              [不执行事务]              [不执行事务]
  |                          |                        |                        |
  |<-----Yes/No--------------|                        |                        |
  |<-----Yes/No---------------------------------      |                        |
  |<-----Yes/No------------------------------------------------               |
```

**特点**：
- 只是询问，不执行事务
- 参与者检查自身状态，判断是否能执行事务
- **不锁定资源**

**阶段二：PreCommit（预提交阶段）**

**情况1：所有参与者都返回Yes**
```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------PreCommit---------->|                        |                        |
  |------PreCommit----------------------------->      |                        |
  |------PreCommit------------------------------------------------>           |
  |                          |                        |                        |
  |                     [执行事务]                [执行事务]                [执行事务]
  |                     [写Undo/Redo]            [写Undo/Redo]            [写Undo/Redo]
  |                     [锁定资源]               [锁定资源]               [锁定资源]
  |                          |                        |                        |
  |<-----ACK-----------------|                        |                        |
  |<-----ACK---------------------------------         |                        |
  |<-----ACK------------------------------------------------               |
```

**情况2：任一参与者返回No或超时**
```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------Abort-------------->|                        |                        |
  |------Abort----------------------------->          |                        |
  |------Abort------------------------------------------------>               |
  |                          |                        |                        |
  |                     [中断事务]                [中断事务]                [中断事务]
```

**阶段三：DoCommit（提交阶段）**

**情况1：所有参与者PreCommit成功**
```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------DoCommit----------->|                        |                        |
  |------DoCommit--------------------------->         |                        |
  |------DoCommit----------------------------------------------->              |
  |                          |                        |                        |
  |                     [提交事务]                [提交事务]                [提交事务]
  |                     [释放资源]                [释放资源]                [释放资源]
  |                          |                        |                        |
  |<-----ACK-----------------|                        |                        |
  |<-----ACK---------------------------------         |                        |
  |<-----ACK------------------------------------------------               |
```

**情况2：PreCommit失败或超时**
```
协调者                     参与者1                  参与者2                  参与者3
  |                          |                        |                        |
  |------Abort-------------->|                        |                        |
  |------Abort----------------------------->          |                        |
  |------Abort------------------------------------------------>               |
  |                          |                        |                        |
  |                     [回滚事务]                [回滚事务]                [回滚事务]
  |                     [释放资源]                [释放资源]                [释放资源]
```

#### 3PC的超时机制

**关键改进**：参与者引入超时自动决策

```java
/**
 * 3PC参与者实现（带超时机制）
 */
public class ThreePhaseCommitParticipant {
    
    private static final long TIMEOUT = 30000; // 30秒超时
    
    @Override
    public void preCommit(Transaction transaction) throws Exception {
        // 执行事务但不提交
        executeTransaction(transaction);
        
        // 启动超时监听
        ScheduledFuture<?> timeoutTask = executor.schedule(() -> {
            // 超时后自动提交（假设PreCommit成功意味着大概率提交）
            try {
                commit(transaction);
                log.info("Auto commit due to timeout");
            } catch (Exception e) {
                log.error("Auto commit failed", e);
            }
        }, TIMEOUT, TimeUnit.MILLISECONDS);
        
        // 等待DoCommit或Abort命令
        waitForFinalDecision(transaction, timeoutTask);
    }
}
```

**超时后的行为**：
- 在CanCommit阶段超时：参与者返回No
- 在PreCommit阶段超时：参与者中断事务
- 在DoCommit阶段超时：参与者**自动提交**（假设能进入PreCommit说明大概率会提交）

#### 代码实现示例

```java
/**
 * 3PC协调者实现
 */
public class ThreePhaseCommitCoordinator {
    
    private List<Participant> participants;
    private static final long TIMEOUT = 10000; // 10秒超时
    
    public boolean execute(Transaction transaction) {
        // ============ 阶段一：CanCommit ============
        if (!canCommitPhase(transaction)) {
            return false;
        }
        
        // ============ 阶段二：PreCommit ============
        if (!preCommitPhase(transaction)) {
            abortTransaction(transaction);
            return false;
        }
        
        // ============ 阶段三：DoCommit ============
        return doCommitPhase(transaction);
    }
    
    private boolean canCommitPhase(Transaction transaction) {
        List<Future<Boolean>> futures = new ArrayList<>();
        
        for (Participant participant : participants) {
            Future<Boolean> future = executor.submit(() -> {
                try {
                    return participant.canCommit(transaction);
                } catch (Exception e) {
                    return false;
                }
            });
            futures.add(future);
        }
        
        // 等待所有参与者响应（带超时）
        for (Future<Boolean> future : futures) {
            try {
                Boolean result = future.get(TIMEOUT, TimeUnit.MILLISECONDS);
                if (!result) {
                    return false;
                }
            } catch (TimeoutException e) {
                // 超时视为失败
                return false;
            } catch (Exception e) {
                return false;
            }
        }
        return true;
    }
    
    private boolean preCommitPhase(Transaction transaction) {
        for (Participant participant : participants) {
            try {
                participant.preCommit(transaction);
            } catch (Exception e) {
                return false;
            }
        }
        return true;
    }
    
    private boolean doCommitPhase(Transaction transaction) {
        for (Participant participant : participants) {
            try {
                participant.doCommit(transaction);
            } catch (Exception e) {
                log.error("DoCommit failed", e);
                // 注意：这里提交失败很难处理
            }
        }
        return true;
    }
    
    private void abortTransaction(Transaction transaction) {
        for (Participant participant : participants) {
            try {
                participant.abort(transaction);
            } catch (Exception e) {
                log.error("Abort failed", e);
            }
        }
    }
}
```

### 3. 2PC vs 3PC 对比

| 维度 | 2PC | 3PC |
|------|-----|-----|
| **阶段数** | 2个（Prepare、Commit） | 3个（CanCommit、PreCommit、DoCommit） |
| **是否有超时** | 无 | 有 |
| **阻塞问题** | 严重（准备后一直等待） | 减轻（超时自动决策） |
| **单点故障** | 严重（协调者故障导致阻塞） | 减轻（超时可自行决策） |
| **数据一致性** | 可能不一致 | 可能不一致（但概率更低） |
| **性能** | 较差 | 更差（多一次网络往返） |
| **复杂度** | 中等 | 高 |
| **实际应用** | XA协议使用 | 几乎不用 |

### 4. 存在的问题与局限

#### 共同问题

**问题1：性能开销大**
- 多次网络往返（2PC:2次，3PC:3次）
- 资源长时间锁定
- 同步阻塞

**问题2：无法完全避免数据不一致**
```
场景：3PC在DoCommit阶段网络分区
协调者
  |-----DoCommit---->参与者1 [提交] ✓
  |-----DoCommit--X  参与者2 [超时自动提交] ✓
  |-----DoCommit--X  参与者3 [超时自动提交] ✓

看似正常，但如果协调者本应发送Abort呢？
参与者会因为超时而错误地提交！
```

**问题3：不适合高并发场景**
- 锁定资源时间过长
- 吞吐量低

### 5. 实际应用

#### XA协议（2PC的实现）

```java
// 使用JTA进行分布式事务
@Transactional
public void transfer() throws Exception {
    // 获取XA数据源
    XADataSource xaDS1 = getXADataSource1();
    XADataSource xaDS2 = getXADataSource2();
    
    XAConnection xaConn1 = xaDS1.getXAConnection();
    XAConnection xaConn2 = xaDS2.getXAConnection();
    
    XAResource xaRes1 = xaConn1.getXAResource();
    XAResource xaRes2 = xaConn2.getXAResource();
    
    Xid xid = new MyXid();
    
    try {
        // 阶段1：Prepare
        xaRes1.start(xid, XAResource.TMNOFLAGS);
        xaConn1.getConnection().createStatement()
               .executeUpdate("UPDATE account SET balance = balance - 100");
        xaRes1.end(xid, XAResource.TMSUCCESS);
        
        xaRes2.start(xid, XAResource.TMNOFLAGS);
        xaConn2.getConnection().createStatement()
               .executeUpdate("UPDATE account SET balance = balance + 100");
        xaRes2.end(xid, XAResource.TMSUCCESS);
        
        int ret1 = xaRes1.prepare(xid);
        int ret2 = xaRes2.prepare(xid);
        
        // 阶段2：Commit
        if (ret1 == XAResource.XA_OK && ret2 == XAResource.XA_OK) {
            xaRes1.commit(xid, false);
            xaRes2.commit(xid, false);
        }
    } catch (Exception e) {
        xaRes1.rollback(xid);
        xaRes2.rollback(xid);
    }
}
```

### 6. 总结

**2PC核心要点**：
- 两个阶段：Prepare（准备）、Commit/Rollback（提交/回滚）
- 强一致性保证，但存在同步阻塞、单点故障、数据不一致风险
- 实际应用：XA协议、JTA

**3PC核心要点**：
- 三个阶段：CanCommit（询问）、PreCommit（预提交）、DoCommit（提交）
- 引入超时机制，降低阻塞风险
- 性能更差，理论意义大于实际意义

**面试建议**：
- 能够清晰描述2PC和3PC的流程
- 理解两者的问题和局限
- 知道为什么实际生产中很少用3PC
- 了解XA协议是2PC的实际应用
- 理解为什么互联网公司更倾向柔性事务（TCC、Saga等）

