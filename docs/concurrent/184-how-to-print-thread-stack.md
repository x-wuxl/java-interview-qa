---
layout: default
title: "如何打印线程栈信息？"
parent: 并发编程
nav_order: 184
description: "详细介绍在Linux和Windows环境下打印Java线程栈信息的多种方式，包括jstack命令、kill -3信号以及编程方式，并结合CPU飙高排查场景进行说明。"
date: 2025-11-19
---
### 1. 核心概念简述

**线程栈（Thread Stack）**信息是 Java 线程在某一时刻的快照。它记录了线程当前执行到哪一行代码、持有哪些锁、在等待什么锁等关键信息。这是排查**死锁（Deadlock）**、**CPU 飙高**、**线程阻塞**等线上问题的最有力工具。

### 2. 常用操作方法

#### 方法一：使用 `jstack` 命令（最常用）
JDK 自带的命令行工具。
```bash
# 1. 找到 Java 进程 ID (PID)
jps -l 
# 或
ps -ef | grep java

# 2. 打印堆栈到控制台
jstack <PID>

# 3. 导出到文件（推荐）
jstack <PID> > thread_dump.log
```

#### 方法二：使用 `kill -3`（Linux 专用）
向进程发送 SIGQUIT 信号，JVM 会将堆栈信息打印到标准输出（通常是 Tomcat/Jar 的 catalina.out 或 nohup.out 日志中），而不会杀死进程。
```bash
kill -3 <PID>
```

#### 方法三：编程方式
在代码中获取当前所有线程的堆栈，常用于构建监控端点。
```java
Map<Thread, StackTraceElement[]> allStackTraces = Thread.getAllStackTraces();
for (Map.Entry<Thread, StackTraceElement[]> entry : allStackTraces.entrySet()) {
    Thread thread = entry.getKey();
    // 打印 thread.getName() 和 entry.getValue()
}
```

### 3. 生产环境排查实战

**场景：CPU 占用率飙高（100%）怎么查？**

这是一个经典的面试组合拳：
1.  **定位进程**：`top` 找到 CPU 最高的 Java 进程 PID。
2.  **定位线程**：`top -H -p <PID>` 查看该进程下哪个**线程 ID (TID)** 占用 CPU 最高。
3.  **进制转换**：将十进制的 TID 转换为十六进制（因为 jstack 输出中使用十六进制）。例如 `printf "%x\n" <TID>`。
4.  **查找堆栈**：`jstack <PID> | grep -A 20 <十六进制TID>`。
5.  **分析代码**：在输出中找到对应的代码行，通常是死循环或复杂的计算逻辑。

### 4. 总结与示例

**回答总结：**
“打印线程栈主要有三种方式：最常用的是 JDK 自带的 **`jstack <pid>`** 命令；在 Linux 下也可以使用 **`kill -3 <pid>`** 将堆栈输出到标准日志；还可以通过代码 `Thread.getAllStackTraces()` 获取。在排查 CPU 飙高或死锁问题时，jstack 是必不可少的神器。”

**死锁排查示例：**
如果 jstack 输出中包含以下字样，说明发生了死锁：
```text
Found one Java-level deadlock:
=============================
"Thread-0":
  waiting to lock monitor 0x00007f... (object 0x00000007...)
  which is held by "Thread-1"
"Thread-1":
  waiting to lock monitor 0x00007f... (object 0x00000007...)
  which is held by "Thread-0"
```
