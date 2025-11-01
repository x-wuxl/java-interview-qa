# Java 后端开发面试题库

基于 Jekyll + GitHub Pages 的 Java 后端开发面试题知识库，收录数百道经典面试题及详细答案。

## 项目简介

本项目旨在帮助 Java 后端开发者系统地准备技术面试，涵盖以下主题：

- ☕ **Java 基础**：语法、面向对象、异常处理、IO 流等
- 📦 **集合框架**：List、Set、Map 及其实现类的原理与应用
- 🔀 **并发编程**：线程、锁、并发工具类、线程池等
- 🎯 **JVM**：内存模型、垃圾回收、类加载机制、性能调优
- 🌱 **Spring 框架**：IOC、AOP、SpringBoot、SpringCloud 等
- 💾 **数据库**：MySQL、Redis、事务、索引优化等
- 🚀 **中间件**：消息队列（RabbitMQ、Kafka）、缓存等
- 🌐 **分布式**：分布式事务、一致性算法、微服务架构
- 🎨 **设计模式**：常用设计模式及其应用场景
- 🧮 **算法与数据结构**：常见算法题解析

## 在线访问

访问网站：[https://x-wuxl.github.io/java-interview-qa](https://x-wuxl.github.io/java-interview-qa)

## 项目结构

```
java-interview-qa/
├── _config.yml           # Jekyll 配置文件
├── _layouts/             # 页面布局模板
│   ├── default.html      # 基础布局
│   ├── home.html         # 首页布局
│   └── post.html         # 文章布局
├── _includes/            # 可复用的组件
│   ├── header.html       # 页头
│   └── footer.html       # 页脚
├── _posts/               # 面试题文章（Markdown 格式）
│   ├── 2024-01-01-hashmap-principle.md
│   ├── 2024-01-02-java-memory-model.md
│   └── ...
├── assets/               # 静态资源
│   └── css/
│       ├── style.css     # 主样式文件
│       └── syntax.css    # 代码高亮样式
├── index.md              # 首页
├── categories.html       # 分类页面
├── about.html            # 关于页面
└── README.md             # 项目说明
```

## 本地开发

### 前置要求

- Ruby >= 2.5
- RubyGems
- GCC 和 Make

### 安装 Jekyll

```bash
# 安装 Bundler 和 Jekyll
gem install bundler jekyll

# 创建 Gemfile（如果不存在）
bundle init

# 添加 Jekyll 到 Gemfile
echo "gem 'jekyll'" >> Gemfile
echo "gem 'webrick'" >> Gemfile  # Ruby 3.0+ 需要

# 安装依赖
bundle install
```

### 本地运行

```bash
# 启动本地服务器
bundle exec jekyll serve

# 或使用简写
jekyll serve

# 访问 http://localhost:4000
```

### 实时预览

Jekyll 支持实时预览，修改文件后会自动重新生成：

```bash
jekyll serve --livereload
```

## 添加新面试题

### 1. 创建新文件

在 `_posts` 目录下创建新的 Markdown 文件，文件名格式：

```
YYYY-MM-DD-title.md
```

例如：`2024-01-06-thread-pool.md`

### 2. 添加 Front Matter

每个文件开头需要包含 YAML 格式的元数据：

```markdown
---
layout: post
title: "Java 线程池原理详解"
date: 2024-01-06
categories: [并发编程]
tags: [线程池, ThreadPoolExecutor, 并发]
---

## 问题

请详细说明 Java 线程池的原理和使用方法。

## 答案

...
```

### 3. 编写内容

使用 Markdown 语法编写内容，支持：

- 标题、列表、表格
- 代码块（支持语法高亮）
- 引用、链接、图片
- 数学公式（需配置 MathJax）

**代码块示例：**

````markdown
```java
public class Example {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
```
````

### 4. 分类规范

建议使用以下分类名称以保持一致性：

- `Java基础`
- `集合框架`
- `并发编程`
- `JVM`
- `Spring框架`
- `数据库`
- `中间件`
- `分布式`
- `设计模式`
- `算法与数据结构`

## 部署到 GitHub Pages

### 1. 创建 GitHub 仓库

在 GitHub 上创建名为 `java-interview-qa` 的仓库。

### 2. 推送代码

```bash
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/x-wuxl/java-interview-qa.git
git push -u origin main
```

### 3. 启用 GitHub Pages

1. 进入仓库 Settings
2. 找到 Pages 选项
3. Source 选择 `main` 分支
4. 点击 Save

几分钟后，网站将在 `https://x-wuxl.github.io/java-interview-qa` 上线。

## 自定义配置

### 修改网站信息

编辑 `_config.yml`：

```yaml
title: "你的网站标题"
description: "网站描述"
url: "https://yourusername.github.io/repo-name"
author: "你的名字"
```

### 修改主题样式

编辑 `assets/css/style.css` 来自定义样式。

### 添加 Google Analytics

在 `_config.yml` 中添加：

```yaml
google_analytics: UA-XXXXXXXXX-X
```

## 技术栈

- **Jekyll**：静态网站生成器
- **Liquid**：模板引擎
- **Markdown**：内容编写格式
- **GitHub Pages**：免费托管服务
- **Rouge**：代码语法高亮

## 贡献指南

欢迎贡献！你可以通过以下方式参与：

1. **提交 Issue**：报告错误或提出建议
2. **提交 Pull Request**：
   - Fork 本项目
   - 创建特性分支（`git checkout -b feature/AmazingFeature`）
   - 提交更改（`git commit -m 'Add some AmazingFeature'`）
   - 推送到分支（`git push origin feature/AmazingFeature`）
   - 提交 Pull Request

### 内容规范

- 答案要详细、准确
- 包含代码示例
- 注重原理解析
- 提供相关问题链接

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 联系方式

- 作者：wuxl
- GitHub：[@x-wuxl](https://github.com/x-wuxl)

## 致谢

感谢所有贡献者的付出！

---

⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！
