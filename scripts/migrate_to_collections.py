#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移脚本：将 _posts 中的文件移动到对应的分类目录
基于 学习路径排序_优化版.md 中的分类信息
"""

import os
import re
import shutil
from pathlib import Path

# 分类映射：中文名 -> 目录名
CATEGORY_MAPPING = {
    "一、Java基础": "java-basics",
    "二、集合框架": "collections",
    "三、JVM": "jvm",
    "四、并发编程": "concurrent",
    "五、数据库MySQL": "mysql",
    "六、Redis": "redis",
    "七、Spring框架": "spring",
    "八、设计模式": "design-patterns",
    "九、分布式理论": "distributed-theory",
    "十、分布式ID": "distributed-id",
    "十一、分布式事务": "distributed-transaction",
    "十二、分布式锁": "distributed-lock",
    "十三、分库分表": "sharding",
    "十四、微服务": "microservices",
    "十五、消息队列": "message-queue",
    "十六、RPC": "rpc",
    "十七、ElasticSearch": "elasticsearch",
    "十八、ZooKeeper": "zookeeper",
    "十九、Netty": "netty",
    "二十、架构设计与实战场景": "architecture"
}

# 英文名映射
CATEGORY_ENGLISH_NAMES = {
    "java-basics": "Java基础",
    "collections": "集合框架",
    "jvm": "JVM",
    "concurrent": "并发编程",
    "mysql": "数据库MySQL",
    "redis": "Redis",
    "spring": "Spring框架",
    "design-patterns": "设计模式",
    "distributed-theory": "分布式理论",
    "distributed-id": "分布式ID",
    "distributed-transaction": "分布式事务",
    "distributed-lock": "分布式锁",
    "sharding": "分库分表",
    "microservices": "微服务",
    "message-queue": "消息队列",
    "rpc": "RPC",
    "elasticsearch": "ElasticSearch",
    "zookeeper": "ZooKeeper",
    "netty": "Netty",
    "architecture": "架构设计与实战"
}


def parse_learning_path():
    """解析学习路径文件，获取题目到分类的映射"""
    learning_path_file = Path("_data/学习路径排序_优化版.md")
    
    if not learning_path_file.exists():
        print(f"错误: 找不到文件 {learning_path_file}")
        return {}
    
    title_to_category = {}
    current_category = None
    
    with open(learning_path_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # 匹配大分类：## 一、Java基础（1-79）
            category_match = re.match(r'^##\s+(.+?)（\d+-\d+）', line)
            if category_match:
                current_category = category_match.group(1)
                continue
            
            # 匹配题目：1. 题目标题
            question_match = re.match(r'^\d+\.\s+(.+)$', line)
            if question_match and current_category:
                title = question_match.group(1)
                title_to_category[title] = current_category
    
    print(f"✓ 解析完成: 共 {len(title_to_category)} 道题目")
    return title_to_category


def extract_front_matter(file_path):
    """提取 markdown 文件的 front matter"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 匹配 YAML front matter
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if match:
        front_matter = match.group(1)
        body = match.group(2)
        return front_matter, body
    
    return None, content


def get_title_from_front_matter(front_matter):
    """从 front matter 中提取 title"""
    if not front_matter:
        return None
    
    match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', front_matter, re.MULTILINE)
    if match:
        return match.group(1).strip('"\'')
    
    return None


def create_category_directories():
    """创建所有分类目录"""
    for dir_name in CATEGORY_MAPPING.values():
        dir_path = Path(f"_{dir_name}")
        dir_path.mkdir(exist_ok=True)
        print(f"✓ 创建目录: {dir_path}")


def create_category_index_pages():
    """为每个分类创建索引页面"""
    # 统计每个分类的题目范围
    learning_path_file = Path("_data/学习路径排序_优化版.md")
    category_ranges = {}
    
    with open(learning_path_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 匹配大分类：## 一、Java基础（1-79）
            category_match = re.match(r'^##\s+(.+?)（(\d+)-(\d+)）', line)
            if category_match:
                category_name = category_match.group(1)
                start = category_match.group(2)
                end = category_match.group(3)
                category_ranges[category_name] = (start, end)
    
    for chinese_name, dir_name in CATEGORY_MAPPING.items():
        index_path = Path(f"_{dir_name}/index.md")
        
        # 获取题目范围
        range_text = ""
        if chinese_name in category_ranges:
            start, end = category_ranges[chinese_name]
            count = int(end) - int(start) + 1
            range_text = f"题目范围：第 {start}-{end} 题，共 {count} 道题目"
        
        english_name = CATEGORY_ENGLISH_NAMES[dir_name]
        
        # 确定 nav_order（按照学习路径顺序）
        nav_order = list(CATEGORY_MAPPING.keys()).index(chinese_name) + 1
        
        content = f"""---
layout: default
title: {english_name}
nav_order: {nav_order}
has_children: true
permalink: /{dir_name}/
---

# {english_name}

{range_text}

本分类包含 Java 后端开发中关于 {english_name} 的核心面试题。题目按照循序渐进的学习路径组织，建议按顺序学习。

---

## 快速导航

使用左侧导航栏查看本分类下的所有题目，或使用页面顶部的搜索功能快速查找特定问题。
"""
        
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ 创建索引页: {index_path}")


def migrate_posts():
    """迁移所有 posts 到对应的分类目录"""
    title_to_category = parse_learning_path()
    posts_dir = Path("_posts")
    
    if not posts_dir.exists():
        print(f"错误: 找不到 _posts 目录")
        return
    
    migrated_count = 0
    not_found_count = 0
    not_found_titles = []
    
    # 获取题目序号映射
    learning_path_file = Path("_data/学习路径排序_优化版.md")
    title_to_order = {}
    
    with open(learning_path_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            question_match = re.match(r'^(\d+)\.\s+(.+)$', line)
            if question_match:
                order = int(question_match.group(1))
                title = question_match.group(2)
                title_to_order[title] = order
    
    for post_file in posts_dir.glob("*.md"):
        front_matter, body = extract_front_matter(post_file)
        title = get_title_from_front_matter(front_matter)
        
        if not title:
            print(f"⚠ 警告: 无法提取标题 - {post_file.name}")
            continue
        
        if title not in title_to_category:
            print(f"⚠ 警告: 未找到分类 - {title}")
            not_found_count += 1
            not_found_titles.append(title)
            continue
        
        category = title_to_category[title]
        dir_name = CATEGORY_MAPPING[category]
        
        # 获取题目序号
        nav_order = title_to_order.get(title, 999)
        
        # 创建新的文件名（移除日期前缀）
        new_filename = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', post_file.name)
        
        # 目标路径
        target_path = Path(f"_{dir_name}/{new_filename}")
        
        # 更新 front matter，添加 nav_order 和 parent
        new_front_matter = front_matter
        
        # 添加 nav_order（如果不存在）
        if 'nav_order:' not in new_front_matter:
            new_front_matter += f"\nnav_order: {nav_order}"
        
        # 添加 parent（如果不存在）
        parent_name = CATEGORY_ENGLISH_NAMES[dir_name]
        if 'parent:' not in new_front_matter:
            new_front_matter += f"\nparent: {parent_name}"
        
        # 移除 layout: post，使用默认的 layout: default
        new_front_matter = re.sub(r'^layout:\s*post\s*$', '', new_front_matter, flags=re.MULTILINE)
        new_front_matter = new_front_matter.strip()
        
        # 写入新文件
        new_content = f"---\n{new_front_matter}\n---\n{body}"
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        migrated_count += 1
        
        if migrated_count % 50 == 0:
            print(f"  已迁移 {migrated_count} 个文件...")
    
    print(f"\n✓ 迁移完成!")
    print(f"  - 成功迁移: {migrated_count} 个文件")
    print(f"  - 未找到分类: {not_found_count} 个文件")
    
    if not_found_titles:
        print(f"\n未找到分类的题目:")
        for title in not_found_titles[:10]:  # 只显示前10个
            print(f"  - {title}")
        if len(not_found_titles) > 10:
            print(f"  ... 还有 {len(not_found_titles) - 10} 个")


def update_index_page():
    """更新首页"""
    index_path = Path("index.md")
    
    content = """---
layout: default
title: 首页
nav_order: 0
description: "Java 后端开发面试题库 - 613 道精选题目，按学习路径循序渐进"
permalink: /
---

# Java 后端开发面试题库

{: .fs-9 }

精选 613 道 Java 后端面试题，按照学习路径循序渐进组织
{: .fs-6 .fw-300 }

[开始学习](#学习路径){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[GitHub 仓库](https://github.com/x-wuxl/java-interview-qa){: .btn .fs-5 .mb-4 .mb-md-0 }

---

## 关于本站

本站收录了 613 道精心整理的 Java 后端开发面试题，涵盖从基础到高级的各个技术领域。所有题目按照**循序渐进的学习路径**组织，帮助你系统性地掌握 Java 后端技术栈。

### 特色功能

- 📚 **系统化学习路径**: 从 Java 基础到分布式架构，由浅入深
- 🔍 **强大的搜索功能**: 快速查找你需要的题目
- 🎯 **分类清晰**: 20 个技术分类，定位精准
- 📱 **响应式设计**: 支持手机、平板等多种设备

---

## 学习路径

本站遵循 **"Java语言基础 → 核心底层原理 → 数据存储与中间件 → 主流开发框架 → 分布式架构与微服务"** 的深度递进逻辑。

### 基础篇（1-281 题）

| 分类 | 题目数 | 描述 |
|:-----|:------|:-----|
| [Java基础](java-basics/) | 79 题 | 面向对象、泛型、反射、IO 等 |
| [集合框架](collections/) | 27 题 | ArrayList、HashMap、ConcurrentHashMap 等 |
| [JVM](jvm/) | 67 题 | 内存结构、垃圾回收、类加载等 |
| [并发编程](concurrent/) | 109 题 | 线程、锁、JMM、线程池等 |

### 数据层篇（282-445 题）

| 分类 | 题目数 | 描述 |
|:-----|:------|:-----|
| [数据库MySQL](mysql/) | 125 题 | 索引、事务、锁、SQL优化等 |
| [Redis](redis/) | 47 题 | 数据结构、持久化、高可用等 |

### 框架篇（446-492 题）

| 分类 | 题目数 | 描述 |
|:-----|:------|:-----|
| [Spring框架](spring/) | 37 题 | IOC、AOP、事务、SpringBoot 等 |
| [设计模式](design-patterns/) | 7 题 | 单例、工厂、策略、责任链等 |

### 分布式篇（493-571 题）

| 分类 | 题目数 | 描述 |
|:-----|:------|:-----|
| [分布式理论](distributed-theory/) | 8 题 | CAP、BASE、幂等、一致性Hash 等 |
| [分布式ID](distributed-id/) | 2 题 | 分布式ID生成方案、雪花算法 |
| [分布式事务](distributed-transaction/) | 7 题 | 2PC、TCC、Saga、Seata 等 |
| [分布式锁](distributed-lock/) | 4 题 | Redis锁、ZooKeeper锁等 |
| [分库分表](sharding/) | 6 题 | ShardingSphere、分库分表策略 |
| [微服务](microservices/) | 15 题 | SpringCloud、Nacos、负载均衡 |
| [消息队列](message-queue/) | 22 题 | Kafka、RocketMQ、RabbitMQ 等 |
| [RPC](rpc/) | 15 题 | Dubbo、服务治理、SPI 等 |

### 中间件与架构篇（572-613 题）

| 分类 | 题目数 | 描述 |
|:-----|:------|:-----|
| [ElasticSearch](elasticsearch/) | 6 题 | 倒排索引、搜索优化等 |
| [ZooKeeper](zookeeper/) | 13 题 | ZNode、选举机制、ZAB协议 |
| [Netty](netty/) | 7 题 | Reactor模式、零拷贝等 |
| [架构设计与实战](architecture/) | 16 题 | 微服务设计、秒杀、系统优化 |

---

## 快速开始

1. **浏览分类**: 使用左侧导航栏选择感兴趣的技术分类
2. **搜索题目**: 使用顶部搜索框快速查找特定问题
3. **按序学习**: 每个分类内的题目都按照学习路径排序，建议顺序学习

---

## 贡献

发现错误或有改进建议？欢迎到 [GitHub](https://github.com/x-wuxl/java-interview-qa) 提交 Issue 或 Pull Request！

---

{: .fs-3 }
最后更新：2025年11月
"""
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 更新首页: {index_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("开始迁移到 Just the Docs 主题")
    print("=" * 60)
    
    print("\n[1/4] 创建分类目录...")
    create_category_directories()
    
    print("\n[2/4] 创建分类索引页...")
    create_category_index_pages()
    
    print("\n[3/4] 迁移文章到分类目录...")
    migrate_posts()
    
    print("\n[4/4] 更新首页...")
    update_index_page()
    
    print("\n" + "=" * 60)
    print("✓ 迁移完成！")
    print("=" * 60)
    print("\n接下来的步骤:")
    print("1. 运行 'bundle install' 安装依赖")
    print("2. 运行 'bundle exec jekyll serve' 启动本地服务器")
    print("3. 访问 http://localhost:4000/java-interview-qa/ 查看效果")
    print("\n注意: 原 _posts 目录保持不变，可以在验证无误后手动删除")


if __name__ == "__main__":
    main()
