#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查标题匹配情况"""

import yaml
import re
from pathlib import Path

def load_posts():
    """加载所有文章"""
    posts = []
    for file_path in Path('_posts').glob('*.md'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        title = frontmatter.get('title', '').strip()
                        if title:
                            posts.append({
                                'title': title,
                                'file': file_path.name
                            })
        except Exception as e:
            print(f"错误: {file_path}: {e}")
    return posts

def check_matching():
    """检查标题匹配"""
    # 加载全局顺序
    with open('_data/global_order.yml', 'r', encoding='utf-8') as f:
        global_order = yaml.safe_load(f)
    
    title_order = global_order.get('title_order', {})
    
    # 加载所有文章
    posts = load_posts()
    
    # 检查匹配情况
    matched = []
    unmatched = []
    
    for post in posts:
        title = post['title']
        if title in title_order:
            matched.append((title, title_order[title], post['file']))
        else:
            unmatched.append((title, post['file']))
    
    print(f"✅ 匹配的文章: {len(matched)}")
    print(f"❌ 未匹配的文章: {len(unmatched)}")
    
    if unmatched:
        print("\n未匹配的文章（前20个）:")
        for title, filename in unmatched[:20]:
            print(f"  - {filename}: {title}")
    
    # 检查顺序16、17
    print("\n检查序号16-17:")
    for title, order, filename in matched:
        if order in [16, 17]:
            print(f"  序号{order}: {title} ({filename})")

if __name__ == '__main__':
    check_matching()

