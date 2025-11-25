---
layout: default
title: "ZNode 节点中存储的是什么？"
parent: ZooKeeper
nav_order: 581
description: 解析 ZNode 的内部结构，包括 Data 部分和 Stat 状态信息（zxid, version, ctime 等）。
---
## 1. 核心概念

ZNode 并不只是存储用户写入的业务数据，它包含两部分内容：
1.  **Data**：用户存储的业务数据（二进制字节数组）。
2.  **Stat**：状态信息（元数据），描述该节点的权限、版本、事务 ID 等。

## 2. 详细结构 (Stat 对象)

在 Java 客户端中，可以通过 `Stat` 对象查看 ZNode 的元数据。关键字段如下：

### 2.1 事务 ID (Zxid)
ZooKeeper 的状态改变都由事务 ID 标识，保证全局有序。
*   **cZxid** (Created Zxid)：节点被创建时的事务 ID。
*   **mZxid** (Modified Zxid)：节点最后一次被修改时的事务 ID。
*   **pZxid** (Parent Zxid)：该节点的**子节点列表**最后一次被修改时的事务 ID（注意是子节点列表变化，不是子节点内容变化）。

### 2.2 版本号 (Version)
用于实现乐观锁（CAS 机制）。
*   **version**：数据节点版本号。每次节点数据更新，version 自增。
*   **cversion**：子节点版本号。子节点增删时自增。
*   **aversion**：ACL（权限）版本号。

### 2.3 时间戳
*   **ctime** (Create Time)：节点创建时间。
*   **mtime** (Modified Time)：节点最后修改时间。

### 2.4 其他
*   **ephemeralOwner**：如果是临时节点，这里存储创建该节点的 Session ID；如果是持久节点，值为 0。
*   **dataLength**：数据内容的长度。
*   **numChildren**：当前节点的子节点数量。

## 3. 为什么需要这些元数据？

*   **乐观锁控制**：`setData(path, data, version)`。客户端更新数据时传入版本号，如果服务端版本号与传入的不一致，更新失败。这保证了并发修改的数据一致性。
*   **临时节点判断**：通过 `ephemeralOwner` 可以快速判断节点是否为临时节点，以及属于哪个 Session。
*   **顺序一致性**：`Zxid` 是 ZK 保证顺序一致性的基石，所有写操作都通过 Zxid 排序。

## 4. 总结

> **面试官**：ZNode 节点中存储的是什么？
>
> **候选人**：
> ZNode 存储的内容包含两部分：**用户数据 (Data)** 和 **状态元数据 (Stat)**。
>
> **用户数据**就是我们写入的二进制信息，通常用于存配置或地址，大小限制默认 1MB。
>
> **状态元数据 (Stat)** 非常重要，主要包含：
> 1.  **Zxid**：事务 ID（如 `cZxid`, `mZxid`），用于标识操作顺序，保证一致性。
> 2.  **Version**：版本号（`version`），用于实现 **CAS 乐观锁**，防止并发覆盖。
> 3.  **EphemeralOwner**：记录临时节点的 Session ID，用于判断节点归属。
> 4.  **时间戳**：如创建时间和修改时间。
>
> 这些元数据支撑了 ZooKeeper 的 Watch 机制、分布式锁和并发控制等核心功能。
