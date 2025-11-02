#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 _posts 目录提取所有文章的标题和分类信息
"""

import os
import re
import yaml
from pathlib import Path
from collections import defaultdict

def extract_frontmatter(file_path):
    """从文章中提取 Front Matter"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 匹配 Front Matter (在 ---  之间)
            match = re.search(r'^---\s*\n(.*?)\n---', content, re.MULTILINE | re.DOTALL)
            if match:
                frontmatter_text = match.group(1)
                # 解析 YAML
                frontmatter = yaml.safe_load(frontmatter_text)
                return frontmatter
    except Exception as e:
        print(f"⚠️  读取文件失败: {file_path} - {e}")
    return None

def get_all_posts_info():
    """获取所有文章的信息"""
    posts_dir = Path('_posts')
    if not posts_dir.exists():
        print("❌ _posts 目录不存在")
        return {}
    
    posts_by_category = defaultdict(list)
    
    for post_file in sorted(posts_dir.glob('*.md')):
        frontmatter = extract_frontmatter(post_file)
        if frontmatter and 'title' in frontmatter and 'categories' in frontmatter:
            title = frontmatter['title']
            categories = frontmatter['categories']
            
            # categories 可能是列表或字符串
            if isinstance(categories, list):
                for category in categories:
                    posts_by_category[category].append({
                        'title': title,
                        'file': post_file.name
                    })
            else:
                posts_by_category[categories].append({
                    'title': title,
                    'file': post_file.name
                })
    
    return posts_by_category

def main():
    """主函数"""
    print("=" * 60)
    print("  从 _posts 提取文章标题")
    print("=" * 60)
    print()
    
    # 获取所有文章
    posts_by_category = get_all_posts_info()
    
    if not posts_by_category:
        print("❌ 没有找到任何文章")
        return
    
    print(f"✅ 找到 {len(posts_by_category)} 个分类")
    print()
    
    # 输出每个分类的文章
    for category in sorted(posts_by_category.keys()):
        posts = posts_by_category[category]
        print(f"📂 {category} ({len(posts)} 篇)")
        
        # 输出前5篇作为示例
        for i, post in enumerate(posts[:5], 1):
            print(f"  {i}. {post['title']}")
        
        if len(posts) > 5:
            print(f"  ... 还有 {len(posts) - 5} 篇")
        print()
    
    # 保存到JSON文件以便后续使用
    import json
    output_file = 'scripts/posts_info.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        # 转换为可序列化的格式
        json_data = {category: [p['title'] for p in posts] 
                     for category, posts in posts_by_category.items()}
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 文章信息已保存到: {output_file}")
    print()
    
    # 输出统计信息
    total_posts = sum(len(posts) for posts in posts_by_category.values())
    print("=" * 60)
    print("📊 统计信息")
    print("=" * 60)
    print(f"分类总数: {len(posts_by_category)}")
    print(f"文章总数: {total_posts}")

if __name__ == '__main__':
    main()

