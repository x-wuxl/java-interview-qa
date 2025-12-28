---
layout: post
title: "如何使用模板方法模式进行代码重构？"
date: 2025-12-28
categories: [大厂项目场景实战, 代码重构实战]
tags: [设计模式, 模板方法, 代码重构, 研发提效]
description: "通过物联网设备处理场景，讲解如何使用模板方法模式重构重复代码，提升代码可维护性。"
---

# 如何使用模板方法模式进行代码重构？

## 面试场景

面试官："你在项目中做过代码重构吗？能举个例子吗？"

回答这个问题的高分框架：
1. 业务背景
2. 原代码的问题
3. 重构的思考过程
4. 具体实现
5. 可量化的效果

---

## 业务场景

某物联网系统，接入十几种设备（风机、光伏板、储能电池等），每种设备的数据处理流程相似：

```
数据采集 → 数据统计 → 阈值监控 → 异常告警 → 创建工单
```

---

## 原代码问题

**代码现状**：每种设备各自实现了完整流程，80%-90%代码重复。

```java
public class WindTurbine {
    public void process() {
        // 采集数据 - 100行代码
        collectData();
        
        // 统计汇总 - 80行代码
        statisticData();
        
        // 阈值监控 - 50行代码（各设备不同）
        monitor();
        
        // 异常告警 - 60行代码
        alarm();
        
        // 创建工单 - 70行代码
        createWorkOrder();
    }
}

public class SolarPanel {
    public void process() {
        // 几乎一样的代码，复制粘贴...
    }
}

public class Battery {
    public void process() {
        // 又是复制粘贴...
    }
}
```

**问题**：
- 通用逻辑修改需要改十几个类
- 容易遗漏、出错
- 代码臃肿，难以维护

---

## 识别Bad Smell

根据《重构》一书的"代码坏味道"：

| Bad Smell | 表现 | 危害 |
|-----------|------|------|
| 重复代码 | 相同逻辑出现多处 | 维护成本高 |
| 过长方法 | 几百行的process() | 难以理解 |
| 霰弹式修改 | 改一个功能要改多处 | 容易遗漏 |

---

## 重构方案：模板方法模式

### 模式定义

**模板方法模式**：定义一个操作的算法骨架，将某些步骤延迟到子类中实现。子类可以在不改变算法结构的情况下，重新定义算法的某些步骤。

### 类结构

```
AbstractDevice（抽象父类）
    │
    ├── process()          // 模板方法，定义流程
    ├── collectData()      // 具体方法，可复用
    ├── statisticData()    // 具体方法，可复用
    ├── monitor()          // 抽象方法，子类必须实现
    ├── alarm()            // 具体方法，可复用
    └── createWorkOrder()  // 具体方法，可复用
    
         ▲
         │
    ┌────┴────┬────────┬────────┐
    │         │        │        │
WindTurbine SolarPanel Battery  ...
   └── monitor()  // 只需实现差异部分
```

---

## 重构后代码

### 抽象父类

```java
public abstract class AbstractDevice {
    
    /**
     * 模板方法 - 定义处理流程
     */
    public final void process() {
        collectData();
        statisticData();
        monitor();
        alarm();
        createWorkOrder();
    }
    
    /**
     * 具体方法 - 通用逻辑，子类可直接复用
     */
    protected void collectData() {
        // 数据采集通用实现
        log.info("开始采集设备数据");
        // ...
    }
    
    protected void statisticData() {
        // 数据统计通用实现
        log.info("开始统计汇总");
        // ...
    }
    
    /**
     * 抽象方法 - 各设备监控逻辑不同，必须由子类实现
     */
    protected abstract void monitor();
    
    protected void alarm() {
        // 告警通用实现
        log.info("发送异常告警");
        // ...
    }
    
    protected void createWorkOrder() {
        // 创建工单通用实现
        log.info("创建处理工单");
        // ...
    }
}
```

### 具体子类

```java
// 风机设备
public class WindTurbine extends AbstractDevice {
    
    @Override
    protected void monitor() {
        // 风机特有的监控逻辑
        if (rpm > maxRpm) {
            log.warn("风机转速异常: {}", rpm);
        }
        if (temperature > maxTemperature) {
            log.warn("风机温度异常: {}", temperature);
        }
    }
}

// 光伏板设备
public class SolarPanel extends AbstractDevice {
    
    @Override
    protected void monitor() {
        // 光伏板特有的监控逻辑
        if (efficiency < minEfficiency) {
            log.warn("光伏板效率异常: {}", efficiency);
        }
    }
}

// 储能电池
public class Battery extends AbstractDevice {
    
    @Override
    protected void monitor() {
        // 电池特有的监控逻辑
        if (soc < 10 || soc > 95) {
            log.warn("电池电量异常: {}", soc);
        }
        if (temperature > 45) {
            log.warn("电池温度异常: {}", temperature);
        }
    }
}
```

---

## 钩子方法

如果某些子类需要定制非抽象方法，可以使用**钩子方法**：

```java
public abstract class AbstractDevice {
    
    public final void process() {
        collectData();
        statisticData();
        monitor();
        
        // 钩子方法 - 默认空实现，子类可选择性覆盖
        beforeAlarm();
        
        alarm();
        createWorkOrder();
        
        // 钩子方法
        afterCreateWorkOrder();
    }
    
    /**
     * 钩子方法 - 默认空实现
     */
    protected void beforeAlarm() {
        // 子类可以覆盖
    }
    
    protected void afterCreateWorkOrder() {
        // 子类可以覆盖
    }
}

// 某些设备需要特殊处理
public class SpecialDevice extends AbstractDevice {
    
    @Override
    protected void monitor() {
        // ...
    }
    
    @Override
    protected void beforeAlarm() {
        // 告警前的特殊处理
        notifyManager();
    }
}
```

---

## 模板方法 vs 策略模式

| 对比项 | 模板方法模式 | 策略模式 |
|--------|--------------|----------|
| 关系 | 继承 | 组合 |
| 变化点 | 算法的某些步骤 | 整个算法 |
| 使用时机 | 流程固定，步骤有差异 | 算法可替换 |
| 类数量 | 子类多 | 策略类多 |

---

## 重构效果

### 代码量对比

| 指标 | 重构前 | 重构后 | 减少 |
|------|--------|--------|------|
| 总方法数 | 70个 | 19个 | 73% |
| 重复代码行 | 2800行 | 0行 | 100% |
| 修改点（改告警逻辑）| 14处 | 1处 | 93% |

### 研发效率

- 新增设备类型：从3天减少到0.5天
- Bug修复：避免遗漏，质量提升

---

## 面试答题框架

```
业务背景：物联网系统，十几种设备，处理流程相似

代码问题：
- 80%代码重复
- 修改一处需改十几个类
- 容易遗漏出错

重构方案：模板方法模式
- 抽象父类定义流程（模板方法）
- 通用逻辑放父类（具体方法）
- 差异逻辑放子类（抽象方法）
- 可选扩展点（钩子方法）

重构效果：
- 方法数减少73%
- 新增设备从3天到0.5天
- 消除重复代码
```

---

## 总结

| 要点 | 说明 |
|------|------|
| 适用场景 | 流程固定，步骤有差异 |
| 核心思想 | Don't call us, we'll call you（好莱坞原则） |
| 抽象方法 | 子类必须实现 |
| 钩子方法 | 子类可选择性覆盖 |
| 具体方法 | 父类实现，子类复用 |
