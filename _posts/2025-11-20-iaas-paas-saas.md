---
layout: post
title: "谈谈你对 IaaS、PaaS、SaaS 的理解。"
date: 2025-11-20
categories: [云计算, 架构]
tags: [IaaS, PaaS, SaaS, 云服务模型]
description: "全面对比 IaaS、PaaS、SaaS 三种云服务模型的定义、职责边界、典型产品及选型策略"
---

## 一、核心概念

**云计算三层服务模型**：从底层基础设施到上层应用的分层抽象。

```
┌─────────────────────────────────────┐
│          SaaS (软件即服务)           │  ← 用户直接使用
│      (Gmail, Salesforce, 钉钉)      │
├─────────────────────────────────────┤
│          PaaS (平台即服务)           │  ← 开发者部署应用
│   (阿里云 EDAS, AWS Elastic Beanstalk)│
├─────────────────────────────────────┤
│         IaaS (基础设施即服务)         │  ← 运维管理虚拟机
│      (阿里云 ECS, AWS EC2)          │
└─────────────────────────────────────┘
           底层物理资源
```

---

## 二、详细对比

### 1. IaaS (Infrastructure as a Service)

#### 定义
提供虚拟化的计算、存储、网络资源，用户自行管理操作系统及以上层级。

#### 职责分工

| 层级 | 云厂商负责 | 用户负责 |
|------|-----------|---------|
| **应用** | ❌ | ✅ |
| **中间件** | ❌ | ✅ |
| **操作系统** | ❌ | ✅ 安装配置 |
| **虚拟化** | ✅ | ❌ |
| **服务器/存储/网络** | ✅ | ❌ |

#### 典型产品

| 厂商 | 产品 | 说明 |
|------|------|------|
| **AWS** | EC2 + S3 + VPC | 计算 + 存储 + 网络 |
| **阿里云** | ECS + OSS + VPC | 同上 |
| **Azure** | Virtual Machines | 虚拟机 |

#### 使用示例

```bash
# 阿里云创建 ECS 实例
aliyun ecs CreateInstance \
  --InstanceType ecs.c6.large \
  --ImageId centos_7_9_x64 \
  --VSwitchId vsw-xxxxx

# 用户需要自行
ssh root@47.100.x.x
yum install -y docker
docker run -d nginx
```

#### 适用场景
- ✅ 完全控制基础设施
- ✅ 自定义网络拓扑
- ✅ 传统应用迁移上云

---

### 2. PaaS (Platform as a Service)

#### 定义
提供应用运行平台，开发者只需上传代码，平台自动处理部署、扩容、监控。

#### 职责分工

| 层级 | 云厂商负责 | 用户负责 |
|------|-----------|---------|
| **应用** | ❌ | ✅ 业务代码 |
| **中间件/运行时** | ✅ JDK、Tomcat | ❌ |
| **操作系统** | ✅ | ❌ |
| **虚拟化/硬件** | ✅ | ❌ |

#### 典型产品

| 厂商 | 产品 | 说明 |
|------|------|------|
| **阿里云** | EDAS、SAE | 应用托管（支持 Spring Cloud） |
| **AWS** | Elastic Beanstalk | 自动部署扩容 |
| **Heroku** | Dyno | 推送代码自动部署 |
| **Google** | App Engine | 无服务器应用平台 |

#### 使用示例

```bash
# Heroku 部署 Spring Boot 应用
git add .
git commit -m "deploy"
git push heroku main

# 平台自动：
# 1. 检测 pom.xml 识别为 Java 应用
# 2. 编译打包（mvn clean package）
# 3. 部署到容器并暴露端口
# 4. 提供 HTTPS 域名
```

#### 适用场景
- ✅ 快速开发迭代（Startup）
- ✅ 标准应用（Spring Boot、Node.js）
- ✅ 不想管理基础设施

---

### 3. SaaS (Software as a Service)

#### 定义
直接提供可用的软件服务，用户通过浏览器/客户端使用，无需安装维护。

#### 职责分工

| 层级 | 云厂商负责 | 用户负责 |
|------|-----------|---------|
| **应用** | ✅ 全部功能 | ❌ |
| **所有底层** | ✅ | ❌ |
| **用户** | ❌ | ✅ 配置使用 |

#### 典型产品

| 类别 | 产品 | 说明 |
|------|------|------|
| **CRM** | Salesforce | 客户关系管理 |
| **协作** | 钉钉、企业微信、Slack | 即时通讯 |
| **邮件** | Gmail、腾讯企业邮 | 邮箱服务 |
| **文档** | Google Docs、WPS 云文档 | 在线文档 |
| **财务** | 用友云、金蝶云 | ERP 系统 |

#### 使用示例

```
用户操作: 
1. 访问 https://mail.google.com
2. 登录账号
3. 直接收发邮件

无需关心:
- 邮件服务器部署
- 数据库维护
- 软件升级
```

#### 适用场景
- ✅ 标准业务需求（CRM、OA）
- ✅ 快速启用（开箱即用）
- ✅ 零运维成本

---

## 三、三层模型对比

### 比萨类比（经典）

```
传统 IT (自己做):
🏠 厨房 + 🍕 原材料 + 👨‍🍳 厨师 + 🍽️ 餐桌

IaaS (外卖):
🏠 厨房 + 🍕 原材料 + 👨‍🍳 厨师
(厂商提供厨房，你自己做)

PaaS (半成品):
🍕 半成品披萨
(厂商提供面团，你加料烘烤)

SaaS (餐厅):
🍕 成品披萨
(直接吃，啥都不管)
```

### 控制力 vs 易用性

```
控制力高 ←──────────────────────→ 易用性高
         IaaS    PaaS    SaaS
         │       │       │
灵活性   ████    ███     █
运维成本 ████    ██      ─
上手速度 █       ███     ████
成本     低       中       高
```

---

## 四、技术实现对比

### IaaS 实现

```python
# OpenStack (开源 IaaS 平台)
from novaclient import client

# 创建虚拟机
nova = client.Client(version=2, session=sess)
server = nova.servers.create(
    name="web-server",
    image="ubuntu-20.04",
    flavor="m1.small"
)
```

### PaaS 实现

```yaml
# Cloud Foundry Manifest
applications:
- name: my-app
  memory: 512M
  instances: 2
  path: target/app.jar
  buildpacks:
  - java_buildpack
```

### SaaS 使用

```javascript
// Salesforce API 调用
sf.sobject("Account")
  .create({ Name: "Acme Corp" })
  .then(result => console.log(result.id));
```

---

## 五、选型决策

### 决策树

```
需要完全控制基础设施？
 ├─ 是 → IaaS (如自建 K8s 集群)
 └─ 否
     ├─ 需要定制应用？
     │   ├─ 是 → PaaS (如托管 Spring Cloud)
     │   └─ 否 → SaaS (如钉钉、Salesforce)
```

### 实际案例

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| **电商系统** | IaaS + 自建 K8s | 高定制化需求 |
| **企业官网** | PaaS (Serverless) | 流量低，按需付费 |
| **客服系统** | SaaS (Zendesk) | 标准化需求 |
| **大数据平台** | PaaS (阿里云 MaxCompute) | 免运维，专注业务 |

---

## 六、混合使用

### 典型架构

```
┌──────────────────────────────────┐
│  SaaS: 钉钉（内部协作）           │
├──────────────────────────────────┤
│  PaaS: SAE 部署微服务             │
│  (Spring Cloud Alibaba)          │
├──────────────────────────────────┤
│  IaaS: ECS 运行数据库             │
│  (MySQL/Redis 自建)              │
└──────────────────────────────────┘
```

**原因**：
- 数据库用 IaaS：完全控制（性能调优）
- 应用用 PaaS：托管运维（快速迭代）
- 办公用 SaaS：开箱即用（降低成本）

---

## 七、答题总结

**2 分钟框架**：

### 1. 定义（30秒）

| 模型 | 关键词 | 类比 |
|------|--------|------|
| IaaS | 虚拟机 | 租厨房 |
| PaaS | 托管平台 | 买半成品 |
| SaaS | 在线软件 | 去餐厅 |

### 2. 职责边界（1分钟）

```
用户管理范围:
IaaS: 操作系统 + 应用
PaaS: 应用代码
SaaS: 配置使用

厂商负责:
IaaS: 虚拟化 + 硬件
PaaS: 运行时 + 虚拟化 + 硬件
SaaS: 全栈
```

### 3. 选型建议（30秒）

- **IaaS**：传统应用上云、需要完全控制
- **PaaS**：标准应用（微服务、容器）、快速迭代
- **SaaS**：标准业务（OA、CRM）、零运维

**加分点**：
- 提及混合使用场景
- 对比控制力与易用性权衡
- 实际产品举例（AWS、阿里云）
