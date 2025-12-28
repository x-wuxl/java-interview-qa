"""
生成大厂项目场景面试题的docs页面文件
"""

import os
import re
from datetime import datetime

# 题目数据 (编号, 文件名slug, 标题)
questions = [
    (614, "reduce-system-failures", "如何系统性地提升可用性？减少故障次数有哪些方法？"),
    (615, "reduce-failure-duration", "系统故障后如何快速降低故障时长？"),
    (616, "reduce-failure-scope", "如何缩小系统故障的影响范围？"),
    (617, "sql-force-index", "什么是FORCE INDEX？实战中如何用它优化慢SQL？"),
    (618, "sql-straight-join", "什么是STRAIGHT_JOIN？多表JOIN如何优化？"),
    (619, "sql-analysis-methods", "面对复杂SQL慢查询，有哪些底层分析方法？"),
    (620, "jvm-local-cache", "滥用本地缓存会导致什么JVM问题？如何解决？"),
    (621, "sharding-basics", "分库分表前需要了解哪些核心知识点？"),
    (622, "sharding-ecommerce", "大型电商订单数据的分库分表方案如何设计？"),
    (623, "sharding-ridesharing", "复杂业务场景（顺风车）的分库分表如何设计？"),
    (624, "kafka-producer-tuning", "Kafka生产者如何调优提升吞吐量？关键参数有哪些？"),
    (625, "mq-fallback", "消息队列挂了，你的Plan B是什么？"),
    (626, "kafka-consumer-tuning", "Kafka消费者如何提升消息处理吞吐量？"),
    (627, "high-concurrency-booking", "万级TPS的1v1约课场景如何设计？"),
    (628, "traffic-surge", "QPS/TPS突然提升十倍甚至百倍，如何应对？"),
    (629, "high-concurrency-likes", "每小时千万级的点赞场景如何设计？"),
    (630, "seckill", "iPhone秒杀场景如何设计？"),
    (631, "performance-order", "电商下单接口从520ms优化到185ms，如何做到？"),
    (632, "performance-coupon", "优惠券下发从30小时优化到20分钟，如何做到？"),
    (633, "performance-dashboard", "数据看板从15s优化到54ms，如何做到？"),
    (634, "redis-failure", "Redis挂了，你要如何处理应对？"),
    (635, "cache-selection", "Redis和Caffeine如何选择？"),
    (636, "refactor-template-method", "如何使用模板方法模式进行代码重构？"),
    (637, "refactor-bridge", "如何使用桥接模式进行代码重构？"),
    (638, "refactor-chain", "如何使用职责链模式进行代码重构？"),
    (639, "data-consistency", "分布式系统数据一致性有哪些知识点？刚性事务和柔性事务的区别？"),
    (640, "order-consistency", "如何保障电商下单场景的数据一致性？"),
    (641, "mysql-read-write-split", "MySQL主从库的读操作有几种分配策略？"),
    (642, "scheduled-task-ha", "定时任务服务器宕机了，怎么解决？"),
    (643, "monolith-vs-microservice", "单体架构与微服务架构如何选择？"),
]

# 源文件到描述的映射
descriptions = {
    614: "讲解限流、防刷、超时设置、系统巡检、故障复盘等提升系统可用性的核心策略",
    615: "深入解析监控告警、熔断降级、快速回滚、预案演练等降低MTTR的方法",
    616: "详解服务隔离、资源隔离、流量隔离、单元化架构等缩小故障影响范围的策略",
    617: "通过实战案例讲解FORCE INDEX的使用场景、原理及MySQL优化器决策机制",
    618: "深入讲解STRAIGHT_JOIN的作用、JOIN执行原理及优化器选错驱动表的原因",
    619: "系统讲解EXPLAIN、EXPLAIN ANALYZE、Optimizer Trace、Profile等分析工具",
    620: "通过案例分析本地缓存导致的GC问题，提供Caffeine、弱引用等解决方案",
    621: "全面讲解分库分表的需求、垂直/水平拆分、Sharding Key、分布式ID等",
    622: "通过电商订单场景详细讲解分片键选择、容量规划、基因法、扩容方案",
    623: "通过顺风车场景讲解多维度查询的分库分表设计，包括主表+ES索引方案",
    624: "深入讲解Kafka生产者架构原理、核心调优参数提升吞吐量",
    625: "详细讲解MQ故障的降级方案，包括本地消息表、备用MQ切换等策略",
    626: "讲解Kafka消费者调优策略，包括多线程消费、批量处理、参数优化",
    627: "通过在线教育约课场景讲解万级TPS的高并发系统设计",
    628: "讲解流量暴增的应对策略，包括横向扩容、限流降级、缓存加速等",
    629: "通过点赞场景讲解Redis缓存、异步落库、热点分片等高并发设计",
    630: "通过秒杀场景讲解流量控制、库存预扣、防超卖等核心技术",
    631: "通过电商下单场景讲解异步化、并行化、缓存优化等性能优化思路",
    632: "讲解大批量数据处理优化策略，包括分批处理、多线程、异步化",
    633: "讲解报表查询优化，包括预计算、缓存、异步加载等策略",
    634: "讲解Redis故障的应对方案，包括本地缓存降级、熔断保护等",
    635: "从一致性、性能、容量等维度对比Redis和Caffeine缓存选型",
    636: "通过物联网设备处理场景讲解如何使用模板方法模式重构代码",
    637: "通过消息推送场景讲解如何使用桥接模式重构代码",
    638: "通过订单校验场景讲解如何使用职责链模式重构代码",
    639: "全面讲解CAP/BASE理论、刚性事务与柔性事务的对比选择",
    640: "通过电商下单场景讲解Seata AT、本地消息表等数据一致性方案",
    641: "讲解MySQL读写分离的多种策略，包括强制主库、延迟检测、半同步等",
    642: "讲解定时任务高可用方案，包括分布式调度框架、任务分片、故障转移",
    643: "分析单体架构和微服务架构的选型策略，包括团队规模、业务复杂度等",
}

# 目标目录
output_dir = "docs/scenario"
os.makedirs(output_dir, exist_ok=True)

# 生成文件
for order, slug, title in questions:
    filename = f"{order}-{slug}.md"
    filepath = os.path.join(output_dir, filename)
    
    description = descriptions.get(order, title)
    
    # 获取对应的_posts文件内容
    post_file = f"_posts/2025-12-28-scenario-{slug}.md"
    
    content = f"""---
layout: default
title: "{title}"
parent: 大厂项目场景实战
nav_order: {order}
description: "{description}"
date: 2025-12-28
---

{{% include_relative ../../_posts/2025-12-28-scenario-{slug}.md %}}
"""
    
    # 由于include不能直接用，需要读取并嵌入内容
    try:
        with open(post_file, 'r', encoding='utf-8') as f:
            post_content = f.read()
            # 移除front matter
            if post_content.startswith('---'):
                parts = post_content.split('---', 2)
                if len(parts) >= 3:
                    post_body = parts[2].strip()
                else:
                    post_body = post_content
            else:
                post_body = post_content
    except Exception as e:
        print(f"Warning: Could not read {post_file}: {e}")
        post_body = f"# {title}\n\n内容待补充..."
    
    # 生成最终内容
    final_content = f"""---
layout: default
title: "{title}"
parent: 大厂项目场景实战
nav_order: {order}
description: "{description}"
date: 2025-12-28
---

{post_body}
"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(final_content)
    
    print(f"Created: {filepath}")

print(f"\nDone! Created {len(questions)} files in {output_dir}")
