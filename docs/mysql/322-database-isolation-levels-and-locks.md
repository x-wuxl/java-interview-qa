---
layout: default
title: "数据库隔离级别与锁之间的关系是什么？"
parent: 数据库MySQL
nav_order: 322
description: 深入解析 MySQL 四大隔离级别（RU, RC, RR, Serializable）与底层锁机制（行锁、间隙锁、Next-Key Lock）及 MVCC 的对应关系。
---
## 1. 核心概念

数据库隔离级别（Isolation Level）定义了事务之间数据可见性的规则，而锁（Lock）和 MVCC（多版本并发控制）是实现这些规则的底层手段。

MySQL InnoDB 引擎支持 SQL 标准的四种隔离级别：
1.  **Read Uncommitted (RU)**：读未提交
2.  **Read Committed (RC)**：读已提交
3.  **Repeatable Read (RR)**：可重复读（默认）
4.  **Serializable**：串行化

## 2. 隔离级别与锁的对应关系

### 2.1 Read Uncommitted (RU)
- **表现**：一个事务可以读到另一个未提交事务修改的数据（脏读）。
- **锁机制**：
    - **读**：不加锁（极不安全）。
    - **写**：加行锁（Record Lock），防止丢失更新。
- **评价**：性能提升有限，数据一致性极差，生产环境几乎不用。

### 2.2 Read Committed (RC)
- **表现**：只能读到已提交的数据。解决了脏读，但存在不可重复读（同一事务两次读结果不同）。
- **锁机制**：
    - **读**：使用 **MVCC**（快照读），每次查询都生成新的 Read View。
    - **写/当前读**：只加**记录锁（Record Lock）**，不加间隙锁（Gap Lock）。
- **特点**：因为没有间隙锁，并发度高，但无法解决幻读。很多互联网大厂（如阿里）倾向于将默认级别改为 RC。

### 2.3 Repeatable Read (RR) —— MySQL 默认
- **表现**：同一事务内多次读取结果一致。解决了不可重复读，并在很大程度上解决了幻读。
- **锁机制**：
    - **读**：使用 **MVCC**，事务启动时生成唯一的 Read View。
    - **写/当前读**：使用 **Next-Key Lock**（记录锁 + 间隙锁）。
        - **Next-Key Lock** = Record Lock + Gap Lock。
        - 它锁住了索引记录之间的“间隙”，防止其他事务插入新数据，从而解决**幻读**问题。

### 2.4 Serializable
- **表现**：事务串行执行。
- **锁机制**：
    - **读**：隐式转换为 `SELECT ... LOCK IN SHARE MODE`（加共享锁 S锁）。
    - **写**：加排他锁（X锁）。
- **评价**：并发能力急剧下降，仅用于对数据一致性要求极高的场景。

## 3. 关键原理：MVCC vs 锁

MySQL InnoDB 实际上是 **MVCC + 锁** 配合工作的：

1.  **快照读 (Snapshot Read)**：普通的 `SELECT`。
    - 依赖 **MVCC** (Undo Log + Read View)。
    - **不加锁**，性能最高。
    - 在 RC 和 RR 级别下生效。

2.  **当前读 (Current Read)**：`SELECT ... FOR UPDATE`, `UPDATE`, `DELETE`。
    - 依赖 **锁** (Record/Gap/Next-Key)。
    - 读取最新版本数据，并保证其他事务不能修改。

## 4. 总结

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 主要锁机制 (InnoDB) |
| :--- | :--- | :--- | :--- | :--- |
| **RU** | ✅ | ✅ | ✅ | 写加行锁，读无锁 |
| **RC** | ❌ | ✅ | ✅ | MVCC (每次新视图) + Record Lock |
| **RR (默认)** | ❌ | ❌ | ❌(大部分) | MVCC (单一视图) + **Next-Key Lock** |
| **Serializable** | ❌ | ❌ | ❌ | 读加 S 锁，写加 X 锁 |

**面试回答示例：**
"隔离级别是目标，锁是手段。
在 **RC** 级别下，读使用 MVCC，写只加**记录锁**，并发高但会有幻读。
在 **RR** 级别下，InnoDB 通过 **Next-Key Lock**（记录锁+间隙锁）锁住数据和间隙，防止其他事务插入，从而解决了**幻读**问题。
同时，MVCC 保证了普通查询不加锁，实现了读写分离的高并发。"
