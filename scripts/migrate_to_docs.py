#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整迁移脚本：将题目迁移到 docs/ 目录结构
使用 parent 和 nav_order 组织导航
"""

import os
import re
import shutil
from pathlib import Path

# 分类映射
CATEGORY_MAPPING = {
    "一、Java基础": "java-basics",
    "二、集合框架": "java-collections",  # 避免与 collections 关键字冲突
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

CATEGORY_ENGLISH_NAMES = {
    "java-basics": "Java基础",
    "java-collections": "集合框架",
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
    """解析学习路径文件"""
    learning_path_file = Path("_data/学习路径排序_优化版.md")
    
    if not learning_path_file.exists():
        print(f"错误: 找不到文件 {learning_path_file}")
        return {}, {}
    
    title_to_category = {}
    title_to_order = {}
    current_category = None
    
    with open(learning_path_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # 匹配大分类
            category_match = re.match(r'^##\s+(.+?)（\d+-\d+）', line)
            if category_match:
                current_category = category_match.group(1)
                continue
            
            # 匹配题目
            question_match = re.match(r'^(\d+)\.\s+(.+)$', line)
            if question_match and current_category:
                order = int(question_match.group(1))
                title = question_match.group(2)
                title_to_category[title] = current_category
                title_to_order[title] = order
    
    print(f"✓ 解析完成: 共 {len(title_to_category)} 道题目")
    return title_to_category, title_to_order


def extract_front_matter(file_path):
    """提取 front matter"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, content


def get_title_from_front_matter(front_matter):
    """提取 title"""
    if not front_matter:
        return None
    
    match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', front_matter, re.MULTILINE)
    if match:
        return match.group(1).strip('"\'')
    return None


def create_docs_structure():
    """创建 docs 目录结构"""
    docs_path = Path("docs")
    if docs_path.exists():
        print(f"  清理现有 docs 目录...")
        shutil.rmtree(docs_path)
    
    docs_path.mkdir(exist_ok=True)
    print(f"✓ 创建 docs/ 目录")
    
    # 创建每个分类的子目录
    for dir_name in CATEGORY_MAPPING.values():
        category_path = docs_path / dir_name
        category_path.mkdir(exist_ok=True)
        print(f"  创建: docs/{dir_name}/")
    
    return docs_path


def create_category_index_pages(docs_path):
    """创建分类索引页"""
    learning_path_file = Path("_data/学习路径排序_优化版.md")
    category_ranges = {}
    
    with open(learning_path_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            category_match = re.match(r'^##\s+(.+?)（(\d+)-(\d+)）', line)
            if category_match:
                category_name = category_match.group(1)
                start = category_match.group(2)
                end = category_match.group(3)
                category_ranges[category_name] = (start, end)
    
    for chinese_name, dir_name in CATEGORY_MAPPING.items():
        index_path = docs_path / dir_name / "index.md"
        
        range_text = ""
        if chinese_name in category_ranges:
            start, end = category_ranges[chinese_name]
            count = int(end) - int(start) + 1
            range_text = f"\n题目范围：第 {start}-{end} 题，共 {count} 道题目\n"
        
        english_name = CATEGORY_ENGLISH_NAMES[dir_name]
        nav_order = list(CATEGORY_MAPPING.keys()).index(chinese_name) + 1
        
        content = f"""---
layout: default
title: {english_name}
nav_order: {nav_order}
has_children: true
permalink: /docs/{dir_name}/
---

# {english_name}
{range_text}
本分类包含 Java 后端开发中关于 **{english_name}** 的核心面试题。

题目按照循序渐进的学习路径组织，建议按顺序学习。

---

💡 **提示**: 使用左侧导航栏浏览本分类下的所有题目，或使用页面顶部的搜索功能快速查找。
"""
        
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"  ✓ {index_path}")


def migrate_posts_to_docs(docs_path, title_to_category, title_to_order):
    """迁移所有题目到 docs 目录"""
    posts_dir = Path("_posts")
    
    if not posts_dir.exists():
        print(f"错误: 找不到 _posts 目录")
        return
    
    migrated_count = 0
    not_found_count = 0
    not_found_titles = []
    
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
        nav_order = title_to_order.get(title, 999)
        
        # 创建新文件名（添加序号前缀）
        new_filename = f"{nav_order:03d}-" + re.sub(r'^\d{4}-\d{2}-\d{2}-', '', post_file.name)
        target_path = docs_path / dir_name / new_filename
        
        # 更新 front matter
        new_front_matter_lines = []
        new_front_matter_lines.append("layout: default")
        
        # 保留原有的 title
        new_front_matter_lines.append(f'title: "{title}"')
        
        # 添加 parent 和 nav_order
        parent_name = CATEGORY_ENGLISH_NAMES[dir_name]
        new_front_matter_lines.append(f"parent: {parent_name}")
        new_front_matter_lines.append(f"nav_order: {nav_order}")
        
        # 保留其他有用的字段
        for field in ['description', 'author', 'date']:
            match = re.search(rf'^{field}:\s*(.+)$', front_matter, re.MULTILINE)
            if match:
                new_front_matter_lines.append(f"{field}: {match.group(1)}")
        
        new_front_matter = "\n".join(new_front_matter_lines)
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
        print(f"\n未找到分类的题目（前10个）:")
        for title in not_found_titles[:10]:
            print(f"  - {title}")


def create_main_index(docs_path):
    """创建主索引页"""
    index_content = """---
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

本站收录了 **613 道**精心整理的 Java 后端开发面试题，涵盖从基础到高级的各个技术领域。

### ✨ 特色功能

- 📚 **系统化学习路径** - 从 Java 基础到分布式架构，由浅入深
- 🔍 **强大的搜索功能** - 快速查找你需要的题目
- 🎯 **分类清晰** - 20 个技术分类，定位精准
- 📱 **响应式设计** - 支持手机、平板等多种设备

---

## 学习路径

本站遵循 **"Java语言基础 → 核心底层原理 → 数据存储与中间件 → 主流开发框架 → 分布式架构与微服务"** 的深度递进逻辑。

### 📖 基础篇（1-281 题）

| 分类 | 题目数 |
|:-----|:------|
| [Java基础](docs/java-basics/) | 79 题 |
| [集合框架](docs/java-collections/) | 27 题 |
| [JVM](docs/jvm/) | 67 题 |
| [并发编程](docs/concurrent/) | 109 题 |

### 💾 数据层篇（282-445 题）

| 分类 | 题目数 |
|:-----|:------|
| [数据库MySQL](docs/mysql/) | 125 题 |
| [Redis](docs/redis/) | 47 题 |

### 🔧 框架篇（446-492 题）

| 分类 | 题目数 |
|:-----|:------|
| [Spring框架](docs/spring/) | 37 题 |
| [设计模式](docs/design-patterns/) | 7 题 |

### 🌐 分布式篇（493-613 题）

| 分类 | 题目数 |
|:-----|:------|
| [分布式理论](docs/distributed-theory/) | 8 题 |
| [分布式ID](docs/distributed-id/) | 2 题 |
| [分布式事务](docs/distributed-transaction/) | 7 题 |
| [分布式锁](docs/distributed-lock/) | 4 题 |
| [分库分表](docs/sharding/) | 6 题 |
| [微服务](docs/microservices/) | 15 题 |
| [消息队列](docs/message-queue/) | 22 题 |
| [RPC](docs/rpc/) | 15 题 |
| [ElasticSearch](docs/elasticsearch/) | 6 题 |
| [ZooKeeper](docs/zookeeper/) | 13 题 |
| [Netty](docs/netty/) | 7 题 |
| [架构设计与实战](docs/architecture/) | 16 题 |

---

## 🚀 快速开始

1. **浏览分类** - 使用左侧导航栏选择感兴趣的技术分类
2. **搜索题目** - 使用顶部搜索框快速查找特定问题
3. **按序学习** - 每个分类内的题目都按照学习路径排序

---

## 🤝 贡献

发现错误或有改进建议？欢迎到 [GitHub](https://github.com/x-wuxl/java-interview-qa) 提交 Issue 或 Pull Request！

---

*最后更新：2025年11月*
"""
    
    index_path = Path("index.md")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"✓ 创建主页: index.md")


def main():
    """主函数"""
    print("=" * 60)
    print("开始迁移到 docs/ 目录结构")
    print("=" * 60)
    
    print("\n[1/5] 解析学习路径...")
    title_to_category, title_to_order = parse_learning_path()
    
    print("\n[2/5] 创建 docs 目录结构...")
    docs_path = create_docs_structure()
    
    print("\n[3/5] 创建分类索引页...")
    create_category_index_pages(docs_path)
    
    print("\n[4/5] 迁移题目到 docs 目录...")
    migrate_posts_to_docs(docs_path, title_to_category, title_to_order)
    
    print("\n[5/5] 创建主索引页...")
    create_main_index(docs_path)
    
    print("\n" + "=" * 60)
    print("✓ 迁移完成！")
    print("=" * 60)
    print("\n文件结构:")
    print("  index.md (首页)")
    print("  docs/")
    print("    ├── java-basics/")
    print("    │   ├── index.md")
    print("    │   ├── 001-xxx.md")
    print("    │   └── ...")
    print("    ├── java-collections/")
    print("    └── (其他18个分类...)")
    print("\n下一步:")
    print("  1. git add index.md docs/ _config.yml")
    print("  2. git commit -m '迁移到 docs 目录结构'")
    print("  3. git push origin main")
    print("\n等待 2-5 分钟后访问网站查看效果！")


if __name__ == "__main__":
    main()
