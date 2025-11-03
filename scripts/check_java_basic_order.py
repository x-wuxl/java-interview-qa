#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查Java基础分类的排序"""

import yaml

with open('_data/global_order.yml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

java_basic = data['sorted_by_category'].get('Java基础', [])
print(f'Java基础分类共 {len(java_basic)} 篇文章\n')
print('前35个:')
for i, p in enumerate(java_basic[:35], 1):
    print(f'{i}. 序号{p["order"]}: {p["title"]}')

