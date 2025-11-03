#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
根据学习路径对所有文章标题进行排序
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict

# 定义学习路径的优先级顺序（基于"我的学习计划.md"）
LEARNING_PATH_ORDER = {
    # 第一周：Java基础
    "Java基础": {
        "基础语法与面向对象": [
            "深拷贝", "浅拷贝", "多态", "接口", "抽象类", "组合", "继承",
            "值传递", "引用传递", "反射"
        ],
        "String与常量池": [
            "String", "StringBuilder", "StringBuffer", "不可变", "intern",
            "字符串常量池", "JDK9", "拼接"
        ],
        "泛型与序列化": [
            "泛型", "类型擦除", "K", "T", "V", "E", "序列化", "反序列化",
            "serialVersionUID", "fastjson"
        ],
        "IO/NIO与SPI": [
            "AIO", "BIO", "NIO", "SPI", "API", "Lambda", "Stream", "并行流",
            "BigDecimal", "浮点数", "金额", "SimpleDateFormat"
        ],
    },
    # 第一周：JVM
    "JVM": {
        "内存模型": [
            "运行时内存区域", "内存区域", "堆", "栈", "方法区", "元空间",
            "永久代", "堆外内存", "OutOfMemory", "StackOverflow", "内存泄漏",
            "内存溢出", "Java进程", "内存"
        ],
        "对象创建": [
            "对象创建", "对象结构", "对象分配", "线程安全", "逃逸分析",
            "对象存活", "强引用", "软引用", "弱引用", "虚引用"
        ],
        "垃圾回收": [
            "垃圾回收算法", "GC", "新生代", "老年代", "YoungGC", "FullGC",
            "STW", "StopTheWorld", "safepoint", "三色标记", "跨代引用",
            "CMS", "G1", "ZGC", "垃圾回收器"
        ],
        "类加载": [
            "类加载", "类生命周期", "双亲委派", "类加载器", "Class常量池",
            "运行时常量池", "字符串常量池"
        ],
        "JIT编译": [
            "编译", "解释", "平台无关", "AOT", "JIT", "优化", "JVM工具",
            "启动参数", "OOM", "JVM退出", "kill-9"
        ],
    },
    # 第二周：并发编程
    "Java并发": {
        "Java内存模型": [
            "Java内存模型", "JMM", "happens-before", "as-if-serial", "MESI",
            "总线嗅探", "总线风暴", "内存屏障", "并发", "并行", "线程安全"
        ],
        "volatile与CAS": [
            "volatile", "可见性", "有序性", "原子性", "CAS", "Unsafe",
            "i++", "自旋"
        ],
        "synchronized": [
            "synchronized", "锁优化", "锁升级", "偏向锁", "轻量级锁",
            "重量级锁", "自旋", "非公平锁"
        ],
        "AQS与Lock": [
            "AQS", "ReentrantLock", "同步队列", "条件队列", "独占模式",
            "共享模式", "可重入锁", "公平锁", "非公平锁"
        ],
        "线程基础": [
            "创建线程", "线程状态", "线程存活", "run", "start", "wait",
            "sleep", "notify", "notifyAll", "守护线程", "上下文切换",
            "线程调度", "线程同步", "死锁"
        ],
        "线程池": [
            "线程池", "ThreadPoolExecutor", "拒绝策略", "Executors",
            "线程数", "顺序执行", "ForkJoinPool", "CompletableFuture",
            "多线程编排"
        ],
        "并发工具": [
            "CountDownLatch", "CyclicBarrier", "Semaphore", "LongAdder",
            "AtomicLong", "ThreadLocal", "内存泄漏", "InheritableThreadLocal",
            "TransmittableThreadLocal", "异常捕获"
        ],
        "虚拟线程": [
            "虚拟线程", "JDK21", "虚拟线程不能用synchronized"
        ],
    },
    # 第二周：集合框架
    "集合框架": {
        "List与Map": [
            "ArrayList", "LinkedList", "扩容机制", "HashMap", "线程不安全",
            "JDK1.7", "JDK1.8", "红黑树", "容量", "幂次方", "加载因子",
            "扩容"
        ],
        "并发集合": [
            "ConcurrentHashMap", "CopyOnWriteArrayList", "HashSet",
            "TreeMap", "hashCode", "equals"
        ],
        "其他集合": [
            "PriorityQueue", "ArrayDeque", "WeakHashMap", "LinkedHashMap"
        ],
    },
    # 第三周：MySQL
    "MySQL": {
        "索引原理": [
            "B+树", "索引", "聚簇索引", "非聚簇索引", "回表", "索引覆盖",
            "索引下推", "InnoDB", "MyISAM", "唯一索引", "主键索引", "uuid",
            "自增id"
        ],
        "索引优化": [
            "最左前缀", "联合索引", "索引合并", "索引跳跃扫描", "索引失效",
            "设计索引"
        ],
        "事务": [
            "事务", "隔离级别", "脏读", "幻读", "不可重复读", "MVCC",
            "ReadView", "当前读", "快照读", "RR隔离级别", "RC隔离级别"
        ],
        "锁机制": [
            "锁机制", "表级锁", "页级锁", "行级锁", "排他锁", "共享锁",
            "意向锁", "死锁", "乐观锁", "悲观锁", "锁升级"
        ],
        "执行计划": [
            "SQL执行", "优化器", "选错索引", "驱动表", "小表驱动大表",
            "多表join", "on", "where"
        ],
        "SQL调优": [
            "执行计划", "SQL调优", "慢SQL", "order by", "Using filesort",
            "深度分页", "limit", "like", "模糊查询"
        ],
        "存储结构": [
            "数据页", "行格式", "buffer pool", "页分裂", "页合并",
            "CHAR", "VARCHAR", "BLOB", "TEXT", "emoji"
        ],
        "日志": [
            "binlog", "redolog", "undolog", "两阶段提交", "组提交",
            "select", "大事务"
        ],
        "主从复制": [
            "主从复制", "并行复制", "主从延迟", "AP", "CP", "Online DDL",
            "加索引", "锁表", "字典锁"
        ],
        "实战问题": [
            "热点数据", "唯一性索引", "高并发", "自增主键", "自增主键用完",
            "自增主键不连续", "获取主键id", "扫表任务", "加密", "解密",
            "模糊查询", "抗秒杀"
        ],
    },
    # 第三周：Redis
    "Redis": {
        "数据结构": [
            "数据结构", "String", "List", "Hash", "Set", "ZSet", "跳表",
            "HyperLogLog"
        ],
        "持久化": [
            "持久化", "RDB", "AOF", "主从复制", "哨兵", "集群", "高可用",
            "过期策略", "内存淘汰策略"
        ],
    },
    # 第四周：Spring框架
    "Spring框架": {
        "Spring IOC": [
            "IOC", "Bean生命周期", "Bean初始化", "Bean作用域", "线程安全",
            "循环依赖", "三级缓存", "Lazy"
        ],
        "Spring AOP": [
            "AOP", "失效", "事务", "传播机制", "事务失效", "多线程",
            "@Transactional", "@Async", "事务事件"
        ],
        "SpringBoot": [
            "SpringBoot", "自动配置", "启动流程", "main方法", "starter",
            "Spring6.0", "SpringBoot3.0", "spring.factories", "优雅停机"
        ],
        "SpringCloud": [
            "微服务", "SpringCloud", "Eureka", "Ribbon", "负载均衡",
            "Feign", "Hystrix", "熔断", "Gateway", "Nacos"
        ],
    },
    # 第四周：分布式
    "分布式": {
        "分布式理论": [
            "CAP", "BASE", "分布式事务", "2PC", "3PC", "TCC", "Saga",
            "最终一致性"
        ],
        "分布式锁": [
            "分布式锁", "Redis", "Zookeeper"
        ],
        "分布式ID": [
            "分布式ID", "雪花算法", "一致性Hash"
        ],
    },
    # 第四周：中间件
    "中间件": {
        "Kafka": [
            "Kafka", "架构", "Topic", "Partition", "消息不丢失",
            "消息只消费一次", "顺序消费", "ActiveMQ", "RabbitMQ", "RocketMQ",
            "消息队列"
        ],
        "RocketMQ": [
            "RocketMQ", "延迟消息"
        ],
        "RabbitMQ": [
            "RabbitMQ", "死信队列", "Dead Letter Queue", "Exchange", "交换器"
        ],
        "Dubbo": [
            "Dubbo", "RPC", "HTTP", "架构", "服务调用", "调用协议",
            "序列化", "负载均衡", "服务治理", "服务发现", "路由", "SPI",
            "优雅停机", "泛化调用"
        ],
        "ElasticSearch": [
            "ElasticSearch", "倒排索引", "深度分页", "数据一致性", "搜索性能",
            "优化"
        ],
        "分库分表": [
            "分库分表", "跨库查询", "分布式事务", "ShardingSphere"
        ],
    },
}

# 分类映射（将不同的分类名称映射到统一的学习路径）
CATEGORY_MAPPING = {
    "Java基础": ["Java基础"],
    "JVM": ["JVM"],
    "Java并发": ["Java并发编程", "并发编程", "并发"],
    "集合框架": ["集合框架", "集合类"],
    "MySQL": ["MySQL", "数据库", "索引", "索引原理", "索引优化", "性能优化"],
    "Redis": ["Redis", "持久化", "缓存"],
    "Spring框架": ["Spring框架", "IOC", "AOP", "SpringBoot", "SpringBoot原理"],
    "分布式": ["分布式", "分布式锁", "分布式ID", "分库分表"],
    "中间件": ["中间件", "Dubbo", "Kafka", "RocketMQ", "RabbitMQ", "ElasticSearch", "消息队列"],
}


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
                return title_match.group(1).strip()
        
        # 如果没有front matter，尝试提取第一个#标题
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip()
            
        return None
    except Exception as e:
        print(f"⚠️  读取文件失败: {file_path} - {str(e)}")
        return None


def get_category_from_path(file_path):
    """从文件路径推断分类"""
    filename = os.path.basename(file_path)
    # 移除日期前缀
    name = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', filename)
    name = name.replace('.md', '').replace('.mdd', '')
    
    # 简单的关键词匹配
    for category, keywords in CATEGORY_MAPPING.items():
        for keyword in keywords:
            if keyword.lower() in name.lower():
                return category
    
    return None


def calculate_priority(title, category):
    """根据标题内容计算优先级"""
    if category not in LEARNING_PATH_ORDER:
        return (999, 999, title)  # 未知分类排在最后
    
    title_lower = title.lower()
    category_order = LEARNING_PATH_ORDER[category]
    
    # 遍历子分类，找到匹配的优先级
    for sub_category_order, (sub_name, keywords) in enumerate(category_order.items(), start=1):
        for keyword in keywords:
            if keyword.lower() in title_lower:
                # 进一步细化：根据关键词的位置和重要性
                keyword_order = keywords.index(keyword)
                return (category_order.index(sub_name), sub_category_order, keyword_order, title)
    
    # 如果没有匹配，返回中等优先级
    return (list(LEARNING_PATH_ORDER.keys()).index(category), 50, title)


def main():
    posts_dir = Path('_posts')
    if not posts_dir.exists():
        print(f"❌ 目录不存在: {posts_dir}")
        return
    
    # 读取所有文章
    articles = []
    for file_path in sorted(posts_dir.glob('*.md')):
        title = extract_title_from_file(file_path)
        if title:
            category = get_category_from_path(file_path)
            articles.append({
                'title': title,
                'category': category,
                'file': str(file_path)
            })
    
    print(f"✅ 提取了 {len(articles)} 篇文章标题")
    
    # 定义主要学习路径的分类顺序
    main_category_order = [
        "Java基础",
        "JVM",
        "Java并发",
        "集合框架",
        "MySQL",
        "Redis",
        "Spring框架",
        "分布式",
        "中间件",
    ]
    
    # 按分类分组
    categorized = defaultdict(list)
    for article in articles:
        cat = article['category'] or "其他"
        categorized[cat].append(article)
    
    # 按学习路径排序
    sorted_titles = []
    
    # 先按主要分类顺序
    for main_cat in main_category_order:
        if main_cat in categorized:
            # 获取该分类下的子分类顺序
            if main_cat in LEARNING_PATH_ORDER:
                sub_categories = LEARNING_PATH_ORDER[main_cat]
                
                # 为每篇文章计算匹配的子分类
                articles_with_subcat = []
                for article in categorized[main_cat]:
                    title_lower = article['title'].lower()
                    matched_subcat = None
                    matched_order = 999
                    
                    for subcat_order, (subcat_name, keywords) in enumerate(sub_categories.items(), start=1):
                        for keyword in keywords:
                            if keyword.lower() in title_lower:
                                if subcat_order < matched_order:
                                    matched_order = subcat_order
                                    matched_subcat = subcat_name
                                    break
                    
                    articles_with_subcat.append((matched_order, article))
                
                # 按子分类顺序排序，然后按标题排序
                articles_with_subcat.sort(key=lambda x: (x[0], x[1]['title']))
                sorted_titles.extend([a[1]['title'] for a in articles_with_subcat])
            else:
                # 没有子分类，直接按标题排序
                titles = sorted([a['title'] for a in categorized[main_cat]])
                sorted_titles.extend(titles)
    
    # 处理其他未分类的文章
    for cat in sorted(categorized.keys()):
        if cat not in main_category_order:
            titles = sorted([a['title'] for a in categorized[cat]])
            sorted_titles.extend(titles)
    
    # 写入文件
    output_file = '学习路径排序-文章标题.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 按学习路径排序的文章标题\n\n")
        f.write("> 本文档按照《我的学习计划.md》中的学习顺序，对所有文章标题进行了排序\n\n")
        f.write(f"**总计**: {len(sorted_titles)} 篇文章\n\n")
        f.write("---\n\n")
        
        for idx, title in enumerate(sorted_titles, 1):
            f.write(f"{idx}. {title}\n")
    
    print(f"\n✅ 排序完成！已保存到: {output_file}")
    print(f"📊 统计: 共 {len(sorted_titles)} 篇文章")


if __name__ == '__main__':
    main()

