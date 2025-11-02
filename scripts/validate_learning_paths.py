#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学习路径配置文件验证脚本

用于验证 _data/learning_paths.yml 中配置的文章标题
是否与实际的 _posts 目录中的文章匹配。
"""

import os
import yaml
import re
from pathlib import Path

def extract_title_from_post(file_path):
    """从文章文件中提取标题"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 匹配 Front Matter 中的 title
            match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
            if match:
                return match.group(1).strip('"\'')
    except Exception as e:
        print(f"⚠️  读取文件失败: {file_path} - {e}")
    return None

def load_learning_paths():
    """加载学习路径配置文件"""
    config_path = Path('_data/learning_paths.yml')
    if not config_path.exists():
        print("❌ 配置文件不存在: _data/learning_paths.yml")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ YAML 解析失败: {e}")
        return None

def get_all_posts():
    """获取所有文章及其标题"""
    posts_dir = Path('_posts')
    if not posts_dir.exists():
        print("❌ _posts 目录不存在")
        return {}
    
    posts = {}
    for post_file in posts_dir.glob('*.md'):
        title = extract_title_from_post(post_file)
        if title:
            posts[title] = post_file.name
    
    return posts

def validate_learning_paths():
    """验证学习路径配置"""
    print("🔍 开始验证学习路径配置...")
    print()
    
    # 加载配置
    learning_paths = load_learning_paths()
    if not learning_paths:
        return False
    
    # 获取所有文章
    all_posts = get_all_posts()
    if not all_posts:
        print("❌ 没有找到任何文章")
        return False
    
    print(f"✅ 找到 {len(all_posts)} 篇文章")
    print()
    
    # 验证配置
    total_configured = 0
    missing_posts = []
    
    for category, topics in learning_paths.items():
        print(f"📂 分类: {category}")
        category_count = 0
        
        for topic_name, post_titles in topics.items():
            print(f"  📑 主题: {topic_name}")
            topic_count = 0
            
            for title in post_titles:
                topic_count += 1
                total_configured += 1
                
                if title in all_posts:
                    print(f"    ✅ {title}")
                else:
                    print(f"    ❌ {title} (未找到)")
                    missing_posts.append({
                        'category': category,
                        'topic': topic_name,
                        'title': title
                    })
            
            category_count += topic_count
            print(f"  → 本主题: {topic_count} 篇")
        
        print(f"→ 本分类: {category_count} 篇")
        print()
    
    # 统计未配置的文章
    configured_titles = set()
    for topics in learning_paths.values():
        for post_titles in topics.values():
            configured_titles.update(post_titles)
    
    unconfigured_posts = [title for title in all_posts.keys() if title not in configured_titles]
    
    # 输出总结
    print("=" * 60)
    print("📊 验证结果总结")
    print("=" * 60)
    print(f"✅ 配置的文章总数: {total_configured}")
    print(f"✅ 实际存在的文章: {len(all_posts)}")
    print(f"❌ 配置但不存在的文章: {len(missing_posts)}")
    print(f"⚠️  存在但未配置的文章: {len(unconfigured_posts)}")
    print()
    
    # 详细列出问题
    if missing_posts:
        print("❌ 以下文章在配置中但不存在：")
        for item in missing_posts:
            print(f"  [{item['category']}] {item['topic']} > {item['title']}")
        print()
    
    if unconfigured_posts:
        print("⚠️  以下文章存在但未配置（前10篇）：")
        for title in unconfigured_posts[:10]:
            print(f"  - {title}")
        if len(unconfigured_posts) > 10:
            print(f"  ... 还有 {len(unconfigured_posts) - 10} 篇未列出")
        print()
    
    # 判断是否通过验证
    if missing_posts:
        print("❌ 验证失败：存在配置错误")
        return False
    elif unconfigured_posts:
        print("⚠️  验证通过但有警告：部分文章未配置")
        return True
    else:
        print("✅ 验证通过：所有配置正确！")
        return True

def main():
    """主函数"""
    print("=" * 60)
    print("  学习路径配置验证工具")
    print("=" * 60)
    print()
    
    # 检查当前目录
    if not Path('_data').exists() and not Path('_posts').exists():
        print("❌ 请在项目根目录运行此脚本")
        return
    
    # 执行验证
    success = validate_learning_paths()
    
    print()
    print("=" * 60)
    if success:
        print("🎉 验证完成！")
    else:
        print("❌ 验证失败，请检查配置")
    print("=" * 60)

if __name__ == '__main__':
    main()

