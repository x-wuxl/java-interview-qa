#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import yaml
import os

# 读取学习路径排序_优化版.md文件
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
input_file = os.path.join(project_dir, '学习路径排序_优化版.md')
output_file = os.path.join(project_dir, '_data', 'home_order.yml')

if not os.path.exists(input_file):
    print(f"错误: 找不到文件 {input_file}")
    exit(1)

with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 数据结构
data = {
    'sections': [],
    'title_to_order': {},
    'title_to_category': {}
}

current_section = None
current_subsection = None

for line in content.split('\n'):
    line = line.strip()

    # 匹配大分类标题，如：## 一、Java基础（1-33）
    match = re.match(r'^##\s+(.+?)（(\d+)-(\d+)）', line)
    if match:
        section_name = match.group(1)
        start_num = int(match.group(2))
        end_num = int(match.group(3))

        current_section = {
            'name': section_name,
            'range': f"{start_num}-{end_num}",
            'subsections': [],
            'questions': []
        }
        data['sections'].append(current_section)
        current_subsection = None
        continue

    # 匹配子分类标题，如：### 3.1 内存结构（59-68）
    match = re.match(r'^###\s+(.+?)（(\d+)-(\d+)）', line)
    if match:
        subsection_name = match.group(1)
        start_num = int(match.group(2))
        end_num = int(match.group(3))

        if current_section:
            current_subsection = {
                'name': subsection_name,
                'range': f"{start_num}-{end_num}",
                'questions': []
            }
            current_section['subsections'].append(current_subsection)
        continue

    # 匹配题目，如：1. 如何理解Java中的多态？
    match = re.match(r'^(\d+)\.\s+(.+)$', line)
    if match:
        order = int(match.group(1))
        title = match.group(2).strip()

        question = {
            'order': order,
            'title': title
        }

        # 添加到当前子分类或大分类
        if current_subsection:
            current_subsection['questions'].append(question)
            data['title_to_category'][title] = current_section['name']
        elif current_section:
            current_section['questions'].append(question)
            data['title_to_category'][title] = current_section['name']

        # 建立标题到序号的映射
        data['title_to_order'][title] = order

# 写入YAML文件
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("# 自动生成的首页文章排序数据\n")
    f.write("# 从 学习路径排序_优化版.md 生成\n")
    f.write("# 请勿手动编辑此文件\n\n")
    yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

print(f"Success: Generated {output_file}")
print(f"   - Sections: {len(data['sections'])}")
print(f"   - Questions: {len(data['title_to_order'])}")
