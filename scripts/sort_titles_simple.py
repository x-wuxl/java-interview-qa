#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从学习计划中提取标题顺序，然后匹配_posts中的实际文章标题
"""

import os
import re
from pathlib import Path
from collections import defaultdict

def extract_title_from_file(file_path):
    """从Markdown文件中提取标题"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 提取front matter中的title
        front_matter_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if front_matter_match:
            front_matter = front_matter_match.group(1)
            title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', front_matter, re.MULTILINE)
            if title_match:
                return title_match.group(1).strip().strip('"\'')
        
        return None
    except Exception as e:
        return None


def extract_learning_path_titles():
    """从学习计划中提取标题顺序"""
    plan_file = Path('我的学习计划.md')
    if not plan_file.exists():
        return []
    
    titles = []
    with open(plan_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # 匹配学习文档格式：`分类/标题.md`
        pattern = r'`([^/`]+)/([^`]+)\.md`'
        matches = re.findall(pattern, content)
        
        for category, title in matches:
            # 清理标题（移除可能的前缀标记）
            title = title.strip()
            titles.append((category, title))
    
    return titles


def normalize_title(title):
    """标准化标题以便匹配"""
    # 移除标点符号、空格，转为小写
    normalized = re.sub(r'[^\w\u4e00-\u9fa5]', '', title.lower())
    return normalized


def find_matching_article(title, articles_dict):
    """在文章字典中查找匹配的标题"""
    normalized_target = normalize_title(title)
    
    # 精确匹配
    for article_title, file_path in articles_dict.items():
        if normalize_title(article_title) == normalized_target:
            return article_title
    
    # 模糊匹配（包含关系）
    for article_title, file_path in articles_dict.items():
        if normalized_target in normalize_title(article_title) or normalize_title(article_title) in normalized_target:
            return article_title
    
    return None


def main():
    print("📚 开始提取文章标题并排序...\n")
    
    # 1. 从学习计划中提取标题顺序
    print("1️⃣ 从学习计划中提取标题顺序...")
    learning_path_titles = extract_learning_path_titles()
    print(f"   ✅ 提取了 {len(learning_path_titles)} 个标题顺序\n")
    
    # 2. 读取_posts目录下的所有文章标题
    print("2️⃣ 读取_posts目录下的所有文章...")
    posts_dir = Path('_posts')
    articles_dict = {}
    category_map = defaultdict(list)
    
    for file_path in sorted(posts_dir.glob('*.md')):
        title = extract_title_from_file(file_path)
        if title:
            articles_dict[title] = str(file_path)
            
            # 尝试从文件名推断分类
            filename = file_path.stem
            if 'java' in filename.lower() or '基础' in title:
                category_map['Java基础'].append(title)
            elif 'jvm' in filename.lower():
                category_map['JVM'].append(title)
            elif '并发' in filename.lower() or 'thread' in filename.lower() or 'lock' in filename.lower():
                category_map['Java并发'].append(title)
            elif '集合' in filename.lower() or 'hashmap' in filename.lower() or 'arraylist' in filename.lower():
                category_map['集合框架'].append(title)
            elif 'mysql' in filename.lower() or '数据库' in title:
                category_map['MySQL'].append(title)
            elif 'redis' in filename.lower():
                category_map['Redis'].append(title)
            elif 'spring' in filename.lower():
                category_map['Spring框架'].append(title)
            elif '分布式' in filename.lower() or 'distributed' in filename.lower():
                category_map['分布式'].append(title)
            elif 'kafka' in filename.lower() or 'mq' in filename.lower() or 'dubbo' in filename.lower():
                category_map['中间件'].append(title)
    
    print(f"   ✅ 读取了 {len(articles_dict)} 篇文章\n")
    
    # 3. 按学习路径顺序匹配标题
    print("3️⃣ 按学习路径顺序匹配标题...")
    sorted_titles = []
    matched_titles = set()
    
    # 主要分类顺序
    main_categories = ['Java基础', 'JVM', 'Java并发', '集合框架', 'MySQL', 'Redis', 'Spring框架', '分布式', '中间件']
    
    # 按学习计划中的顺序匹配
    for category, title_from_plan in learning_path_titles:
        matched = find_matching_article(title_from_plan, articles_dict)
        if matched and matched not in matched_titles:
            sorted_titles.append(matched)
            matched_titles.add(matched)
    
    print(f"   ✅ 匹配了 {len(sorted_titles)} 篇文章\n")
    
    # 4. 添加未匹配的文章（按分类）
    print("4️⃣ 添加未匹配的文章...")
    unmatched_count = 0
    for category in main_categories:
        if category in category_map:
            for title in sorted(category_map[category]):
                if title not in matched_titles:
                    sorted_titles.append(title)
                    matched_titles.add(title)
                    unmatched_count += 1
    
    # 添加完全未分类的文章
    for title in sorted(articles_dict.keys()):
        if title not in matched_titles:
            sorted_titles.append(title)
            unmatched_count += 1
    
    print(f"   ✅ 添加了 {unmatched_count} 篇未匹配文章\n")
    
    # 5. 写入文件
    print("5️⃣ 写入排序结果...")
    output_file = '学习路径排序-文章标题.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 按学习路径排序的文章标题\n\n")
        f.write("> 本文档按照《我的学习计划.md》中的学习顺序，对所有文章标题进行了排序\n\n")
        f.write(f"**总计**: {len(sorted_titles)} 篇文章\n\n")
        f.write("---\n\n")
        
        for idx, title in enumerate(sorted_titles, 1):
            f.write(f"{idx}. {title}\n")
    
    print(f"   ✅ 已保存到: {output_file}\n")
    print(f"📊 统计: 共 {len(sorted_titles)} 篇文章")
    print(f"   - 从学习计划匹配: {len(sorted_titles) - unmatched_count} 篇")
    print(f"   - 新增未匹配: {unmatched_count} 篇")


if __name__ == '__main__':
    main()

