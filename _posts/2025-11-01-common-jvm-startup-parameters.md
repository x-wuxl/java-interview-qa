---
layout: post
title: "常用的JVM启动参数有哪些"
date: 2025-11-01
description: "详细介绍Java虚拟机常用的启动参数，包括内存配置、GC相关、性能调优和调试参数"
author: "wuxl"
categories: [JVM]
tags: [JVM, 启动参数, 调优, 垃圾回收, 内存配置]
---

## 问题

常用的JVM启动参数有哪些？

## 答案

### 核心概念

JVM启动参数用于配置Java虚拟机的运行时行为，包括**内存分配**、**垃圾回收策略**、**性能调优**和**调试诊断**等方面。合理配置这些参数对应用性能至关重要。

### 主要参数分类

#### 1. 内存相关参数

**堆内存配置：**
```bash
-Xms<size>        # 初始堆大小，如 -Xms2g
-Xmx<size>        # 最大堆大小，如 -Xmx4g
-XX:NewSize=<size>    # 新生代初始大小
-XX:MaxNewSize=<size> # 新生代最大大小
-Xmn<size>        # 设置新生代大小（同时设置NewSize和MaxNewSize）
```

**非堆内存配置：**
```bash
-XX:PermSize=<size>     # 永久代初始大小（Java 7及之前）
-XX:MaxPermSize=<size>  # 永久代最大大小（Java 7及之前）
-XX:MetaspaceSize=<size>     # 元空间初始大小（Java 8+）
-XX:MaxMetaspaceSize=<size>  # 元空间最大大小（Java 8+）
-XX:MaxDirectMemorySize=<size> # 直接内存最大大小
```

**栈内存配置：**
```bash
-Xss<size>        # 线程栈大小，如 -Xss1m
```

#### 2. 垃圾回收参数

**GC算法选择：**
```bash
-XX:+UseSerialGC      # 串行GC（适用于单核CPU）
-XX:+UseParallelGC    # 并行GC（吞吐量优先）
-XX:+UseConcMarkSweepGC # CMS GC（低延迟）
-XX:+UseG1GC          # G1 GC（平衡吞吐量和延迟）
-XX:+UseZGC           # ZGC（超低延迟，Java 11+）
-XX:+UseShenandoahGC  # Shenandoah GC（Java 12+）
```

**GC调优参数：**
```bash
-XX:ParallelGCThreads=<n>     # 并行GC线程数
-XX:ConcGCThreads=<n>         # 并发GC线程数
-XX:+UseGCTimeLimit           # 限制GC时间
-XX:GCTimeLimit=<percent>     # GC时间占比限制
-XX:+UseGCLogFileRotation     # 启用GC日志轮转
-XX:NumberOfGCLogFiles=<n>    # GC日志文件数量
-XX:GCLogFileSize=<size>      # 单个GC日志文件大小
```

#### 3. 性能优化参数

**JIT编译优化：**
```bash
-XX:+UseCompressedOops        # ���缩对象指针（64位JVM）
-XX:+UseCompressedClassPointers # 压缩类指针
-XX:+TieredCompilation        # 分层编译
-XX:CompileThreshold=<invocations> # 编译阈值
-XX:+PrintCompilation         # 打印编译信息
-XX:+PrintInlining           # 打印内联信息
```

**性能监控参数：**
```bash
-XX:+PrintGC                 # 打印GC信息
-XX:+PrintGCDetails          # 打印详细GC信息
-XX:+PrintGCTimeStamps       # 打印GC时间戳
-XX:+PrintHeapAtGC           # GC时打印堆信息
-XX:+PrintGCApplicationStoppedTime # 打印GC停顿时间
```

#### 4. 调试诊断参数

**错误处理参数：**
```bash
-XX:+HeapDumpOnOutOfMemoryError     # OOM时自动生成堆转储
-XX:HeapDumpPath=<path>             # 堆转储文件路径
-XX:+PrintCommandLineFlags          # 打印命令行参数
-XX:+ErrorFile=<path>               # 错误日志文件路径
```

**JFR参数（Java 8+）：**
```bash
-XX:+FlightRecorder                 # 启用JFR
-XX:StartFlightRecording=<options>  # 启动JFR记录
-XX:FlightRecorderOptions=<options> # JFR配置选项
```

### 原理解析

**参数设置原理：**

1. **内存规划**：根据应用内存需求合理分配堆和元空间
2. **GC选择**：根据应用特性选择合适的GC算法
3. **性能平衡**：在吞吐量、延迟和内存占用间取得平衡
4. **监控诊断**：配置必要的日志和监控参数

**线程安全考量：**
- `-Xss`参数影响线程创建数量
- 直接内存配置需与堆内存协调
- GC线程数配置影响应用线程资源

### 配置示例

**高并发Web应用：**
```bash
-Xms4g -Xmx4g -Xmn2g -Xss512k
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200
-XX:+PrintGCDetails -XX:+PrintGCTimeStamps
-XX:+HeapDumpOnOutOfMemoryError
```

**批处理应用：**
```bash
-Xms8g -Xmx8g -Xmn4g
-XX:+UseParallelGC
-XX:ParallelGCThreads=8
-XX:+PrintGC -XX:+PrintGCDetails
```

**微服务应用：**
```bash
-Xms1g -Xmx1g -Xmn512m -Xss256k
-XX:+UseG1GC -XX:MaxGCPauseMillis=100
-XX:+UseStringDeduplication
-XX:+PrintGC
```

### 答题总结

常用JVM启动参数主要分为四类：
1. **内存参数**：-Xms/-Xmx（堆）、-Xss（栈）、-XX:MetaspaceSize（元空间）
2. **GC参数**：-XX:+UseG1GC（选择GC）、-XX:MaxGCPauseMillis（GC目标）
3. **性能参数**：-XX:+UseCompressedOops（压缩指针）、-XX:+TieredCompilation（分层编译）
4. **诊断参数**：-XX:+PrintGC（GC日志）、-XX:+HeapDumpOnOutOfMemoryError（OOM转储）

配置时需要根据应用特性选择合适的参数组合，平衡性能、内存使用和稳定性。生产环境建议开启GC日志和OOM自动转储。