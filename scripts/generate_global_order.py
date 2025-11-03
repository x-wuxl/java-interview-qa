#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从学习路径排序_优化版.md 生成全局文章顺序配置
"""

import re
import yaml
from pathlib import Path

def parse_learning_path():
    """解析学习路径排序文件"""
    file_path = Path('学习路径排序_优化版.md')
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return None
    
    titles_order = {}
    order = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 匹配 "数字. 标题" 格式
            match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if match:
                order = int(match.group(1))
                title = match.group(2).strip().strip('"')
                # 去除转义符：将 \" 转换为 "
                title = title.replace('\\"', '"').replace('\\\\"', '"')
                titles_order[title] = order
    
    print(f"✅ 解析了 {len(titles_order)} 篇文章的全局顺序")
    return titles_order

def load_all_posts():
    """加载所有文章信息"""
    posts_dir = Path('_posts')
    posts = []
    
    for file_path in posts_dir.glob('*.md'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 解析 frontmatter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        import yaml
                        frontmatter = yaml.safe_load(parts[1])
                        title = frontmatter.get('title', '').strip()
                        categories = frontmatter.get('categories', [])
                        if title and categories:
                            # categories 可能是列表或字符串
                            if isinstance(categories, str):
                                categories = [categories]
                            posts.append({
                                'title': title,
                                'categories': categories,
                                'url': file_path.stem
                            })
        except Exception as e:
            print(f"⚠️  读取文件失败 {file_path}: {e}")
    
    return posts

def generate_global_order_yaml():
    """生成全局顺序 YAML 文件"""
    titles_order = parse_learning_path()
    
    if not titles_order:
        return
    
    # 加载所有文章
    all_posts = load_all_posts()
    
    # 按分类组织文章
    posts_by_category = {}
    for post in all_posts:
        for category in post['categories']:
            if category not in posts_by_category:
                posts_by_category[category] = []
            posts_by_category[category].append(post)
    
    # 构建数据结构
    data = {
        'title_order': titles_order,
        'sorted_by_category': {}
    }
    
    # 为每个分类生成排序后的文章列表
    for category in sorted(posts_by_category.keys()):
        category_posts = posts_by_category[category]
        # 按全局顺序排序
        sorted_category_posts = []
        for post in category_posts:
            order = titles_order.get(post['title'], 999999)
            sorted_category_posts.append({
                'title': post['title'],
                'order': order,
                'url': post['url']
            })
        
        sorted_category_posts.sort(key=lambda x: x['order'])
        data['sorted_by_category'][category] = sorted_category_posts
    
    # 使用 YAML 库保存，确保格式正确
    output_path = Path('_data/global_order.yml')
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# ========================================\n")
        f.write("# 全局文章学习路径顺序配置\n")
        f.write("# 从学习路径排序_优化版.md 自动生成\n")
        f.write("# ========================================\n\n")
        
        # 使用 yaml.dump 确保正确的转义
        import yaml
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    print(f"✅ 已生成全局顺序配置文件: {output_path}")
    print(f"   共 {len(titles_order)} 篇文章的全局顺序")
    print(f"   共 {len(posts_by_category)} 个分类的排序列表")

if __name__ == '__main__':
    generate_global_order_yaml()

