#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 _posts 目录的实际文章标题重新生成 learning_paths.yml
"""

import json
import yaml
from pathlib import Path

# 加载从 _posts 提取的文章信息
def load_posts_info():
    with open('scripts/posts_info.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# 根据学习计划的顺序和实际标题生成新配置
def generate_learning_paths():
    posts_info = load_posts_info()
    
    # 新的学习路径配置（使用实际的文章标题）
    learning_paths = {}
    
    # 根据学习计划，为每个主要分类创建配置
    # 这次我们从 posts_info 中查找匹配的标题
    
    print("=" * 60)
    print("开始生成学习路径配置...")
    print("=" * 60)
    print()
    
    # 检查有哪些分类
    print(f"实际找到的分类:")
    for category in sorted(posts_info.keys()):
        print(f"  - {category} ({len(posts_info[category])} 篇)")
    print()
    
    # 为主要分类生成配置（使用实际标题）
    # Java基础
    if 'Java基础' in posts_info:
        java_basics_posts = posts_info['Java基础']
        learning_paths['Java基础'] = categorize_java_basics(java_basics_posts)
    
    # JVM
    if 'JVM' in posts_info:
        jvm_posts = posts_info['JVM']
        learning_paths['JVM'] = categorize_jvm(jvm_posts)
    
    # 集合框架
    if '集合框架' in posts_info:
        collection_posts = posts_info['集合框架']
        learning_paths['集合框架'] = categorize_collections(collection_posts)
    
    # 并发编程
    if '并发编程' in posts_info:
        concurrency_posts = posts_info['并发编程']
        learning_paths['并发编程'] = categorize_concurrency(concurrency_posts)
    
    # MySQL/数据库
    if '数据库' in posts_info:
        db_posts = posts_info['数据库']
        learning_paths['MySQL'] = categorize_mysql(db_posts)
    elif 'MySQL' in posts_info:
        mysql_posts = posts_info['MySQL']
        learning_paths['MySQL'] = categorize_mysql(mysql_posts)
    
    # Redis
    if 'Redis' in posts_info:
        redis_posts = posts_info['Redis']
        learning_paths['Redis'] = categorize_redis(redis_posts)
    
    # Spring框架
    if 'Spring框架' in posts_info:
        spring_posts = posts_info['Spring框架']
        learning_paths['Spring框架'] = categorize_spring(spring_posts)
    
    # 分布式
    if '分布式' in posts_info:
        distributed_posts = posts_info['分布式']
        learning_paths['分布式'] = categorize_distributed(distributed_posts)
    
    # 中间件
    if '中间件' in posts_info:
        middleware_posts = posts_info['中间件']
        learning_paths['中间件'] = categorize_middleware(middleware_posts)
    
    # 设计模式
    if '设计模式' in posts_info:
        pattern_posts = posts_info['设计模式']
        learning_paths['设计模式'] = {'常用设计模式': pattern_posts}
    
    return learning_paths

# 根据关键词将文章分类到主题
def categorize_by_keywords(posts, keyword_groups):
    """
    根据关键词将文章分组
    keyword_groups: {主题名: [关键词列表]}
    """
    result = {}
    used_titles = set()
    
    for topic, keywords in keyword_groups.items():
        topic_posts = []
        for title in posts:
            if title not in used_titles:
                # 检查标题是否包含任何关键词
                if any(keyword in title for keyword in keywords):
                    topic_posts.append(title)
                    used_titles.add(title)
        if topic_posts:
            result[topic] = topic_posts
    
    # 剩余的文章放到"其他"分类
    remaining = [title for title in posts if title not in used_titles]
    if remaining:
        result['其他'] = remaining
    
    return result

def categorize_java_basics(posts):
    keyword_groups = {
        '基础语法与面向对象': ['深拷贝', '浅拷贝', '多态', '接口', '抽象类', '组合', '继承', '值传递', '引用传递', '反射'],
        'String相关': ['String', 'StringBuilder', 'StringBuffer', '不可变', 'intern', '字符串', 'char', 'byte'],
        '泛型': ['泛型', '类型擦除', 'extends', 'super', 'K、T、V、E'],
        '序列化': ['序列化', '反序列化', 'serialVersionUID', 'fastjson'],
        'IO与NIO': ['AIO', 'BIO', 'NIO'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_jvm(posts):
    keyword_groups = {
        '内存模型': ['运行时内存', '进程占用', '堆和栈', '线程共享', '方法区', '分代', '堆外内存', 'OutOfMemory', 'StackOverflow', '内存泄漏', '内存溢出'],
        '对象创建与内存分配': ['创建对象', '对象的结构', '对象分配内存', '线程安全', '堆上分配', '逃逸分析', '对象是否存活', '强引用', '软引用', '弱引用', '虚引用'],
        '垃圾回收': ['垃圾回收算法', 'GC算法', 'GC流程', 'YoungGC', 'FullGC', 'STW', 'StopTheWorld', 'safepoint', '三色标记', '跨代引用'],
        '垃圾回收器': ['CMS', 'G1', 'ZGC', '垃圾回收器', '默认', 'Java8', 'Java11', '新生代', '老年代', '并发回收', '并行回收', 'Eden', 'Survivor'],
        '类加载': ['类加载', '类的生命周期', '双亲委派', '重写String', '判断', '同一个类', '类加载器', 'Class常量池', '运行时常量池', '字符串常量池'],
        'JIT编译与优化': ['编译', '解释', '反编译', '平台无关', 'AOT', 'JIT', '优化'],
        'JVM工具与调优': ['JVM工具', '启动参数', 'OOM', 'JVM退出', 'kill'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_collections(posts):
    keyword_groups = {
        'List': ['ArrayList', 'LinkedList', '扩容', '时间复杂度'],
        'HashMap': ['HashMap', '哈希', 'hash', '红黑树', '链表长度', '2的幂次方', '加载因子', '线程不安全'],
        '其他Map': ['Hashtable', 'ConcurrentHashMap', 'LinkedHashMap', 'WeakHashMap', 'HashSet', 'TreeMap'],
        '并发集合': ['Concurrent', 'CopyOnWrite'],
        '队列': ['Queue', 'PriorityQueue', 'ArrayDeque', 'Deque'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_concurrency(posts):
    keyword_groups = {
        'Java内存模型': ['内存模型', 'JMM', 'happens-before', 'as-if-serial', 'MESI', '总线嗅探', '总线风暴', '内存屏障', '并发', '并行', '线程安全', '原子性'],
        'volatile与CAS': ['volatile', 'CAS', '自旋', 'Unsafe', 'int a = 1', 'i++'],
        'synchronized': ['synchronized', '锁的是什么', '锁优化', '锁升级', '偏向锁', '轻量级锁', '重量级锁', '非公平锁'],
        'AQS与Lock': ['AQS', '同步队列', '条件队列', '双向链表', '独占模式', '共享模式', 'reentrantLock', 'Lock', '可重入锁', '公平锁'],
        '线程基础': ['创建线程', '线程状态', '线程存活', 'run', 'start', 'wait', 'sleep', 'notify', 'notifyAll', '守护线程', '上下文切换', '线程调度', '线程同步', '死锁'],
        '线程池': ['线程池', '拒绝策略', 'Executors', '线程数', '顺序执行', 'ForkJoinPool', 'ThreadPoolExecutor', 'CompletableFuture', '多线程编排'],
        '并发工具类': ['CountDownLatch', 'CyclicBarrier', 'Semaphore', 'LongAdder', 'AtomicLong', 'ThreadLocal', '内存泄漏', '父子线程', 'InheritableThreadLocal', 'TransmittableThreadLocal', 'try-catch', '捕获异常'],
        '并发编程实战': ['T1,T2,T3', '顺序执行', '打印0-100', '线程异常', '进程退出'],
        '虚拟线程': ['虚拟线程', 'JDK21', 'synchronized', '线程池', 'ThreadLocal'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_mysql(posts):
    keyword_groups = {
        '索引原理': ['B+树', '索引类型', '聚簇索引', '非聚簇索引', '回表', '索引覆盖', '索引下推', 'InnoDB', 'MyISAM', '唯一索引', '主键索引', 'uuid', '自增id'],
        '索引优化': ['最左前缀', '联合索引', 'AB,AC,BC', '单独索引', '索引合并', '索引跳跃', '设计索引', '区分度', '索引失效'],
        '事务': ['事务', '隔离级别', '脏读', '幻读', '不可重复读', 'MVCC', 'ReadView', '当前读', '快照读', '二级索引', 'RR', 'RC'],
        '锁机制': ['锁机制', '表级锁', '页级锁', '行级锁', '排他锁', '共享锁', '意向锁', '死锁', '乐观锁', '悲观锁', '锁升级'],
        'SQL执行与优化': ['SQL执行', '执行顺序', '优化器', '索引成本', '选错索引', '驱动表', '小表驱动大表', 'join', 'on', 'where'],
        '执行计划与慢SQL': ['执行计划', 'SQL调优', '慢SQL', 'key', 'orderby', 'filesort', '深度分页', 'limit', 'like'],
        '存储结构': ['数据页', 'B+树关系', '行格式', 'bufferpool', '页分裂', '页合并', 'key长度', 'char', 'varchar', 'BLOB', 'TEXT', 'emoji'],
        '日志': ['binlog', 'redolog', 'undolog', '2阶段提交', '更新事务', 'binlog格式', '组提交', 'select', '大事务'],
        '主从复制': ['主从复制', '并行复制', '主从延迟', 'AP', 'CP', 'OnlineDDL', '加索引', '锁表', '字典锁'],
        '实战问题': ['热点数据', '唯一性', '自增主键', '主键id', '扫表', '加密', '解密', '模糊查询', '秒杀'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_redis(posts):
    keyword_groups = {
        '基础与数据结构': ['数据结构', 'String', 'List', 'Hash', 'Set', 'ZSet', '跳表', 'HyperLogLog'],
        '持久化': ['持久化', 'RDB', 'AOF'],
        '高可用': ['主从复制', '哨兵', '集群', '高可用'],
        '缓存策略': ['过期策略', '淘汰策略'],
        '分布式锁与缓存一致性': ['分布式锁', '缓存一致性'],
        '实战问题': ['热点key'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_spring(posts):
    keyword_groups = {
        'Spring IOC': ['IOC', 'Bean生命周期', 'Bean初始化', 'Bean作用域', 'Bean线程安全', '循环依赖', '三级缓存', '@Lazy'],
        'Spring AOP': ['AOP', 'AOP失效'],
        'Spring事务': ['事务', '传播机制', '事务失效', '多线程', '@Transactional', '@Async', '事务事件'],
        'SpringBoot': ['SpringBoot', '自动配置', '启动流程', 'main方法', 'starter', 'Spring6.0', 'SpringBoot3.0', 'spring.factories', '优雅停机'],
        'SpringCloud': ['微服务', 'SpringCloud', 'Eureka', 'Ribbon', 'Feign', 'Hystrix', 'Gateway', 'Nacos'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_distributed(posts):
    keyword_groups = {
        '分布式理论': ['CAP', 'BASE'],
        '分布式事务': ['分布式事务', '2PC', '3PC', 'TCC', 'Saga', '最终一致性'],
        '分布式锁': ['分布式锁', 'Redis', 'Zookeeper'],
        '分布式ID': ['分布式ID', '雪花算法'],
        '分库分表': ['分库分表', '跨库查询', 'ShardingSphere'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def categorize_middleware(posts):
    keyword_groups = {
        'Kafka': ['Kafka', 'Topic', 'Partition', '消息', '发送', '不丢失', '消费一次', '顺序消费', 'ActiveMQ', 'RabbitMQ', 'RocketMQ', '消息队列'],
        'RocketMQ': ['RocketMQ'],
        'RabbitMQ': ['RabbitMQ'],
        'Dubbo': ['Dubbo', 'RPC', 'HTTP', '架构', '服务调用', '本地方法', '协议', '序列化', '负载均衡', '服务治理', '服务发现', '路由', 'SPI', 'JDK', '优雅停机', '泛化调用'],
        'ElasticSearch': ['ElasticSearch', '倒排索引', '深度分页', 'ES', '数据一致性', '搜索性能'],
    }
    return categorize_by_keywords(posts, keyword_groups)

def main():
    # 生成新的学习路径配置
    learning_paths = generate_learning_paths()
    
    # 保存到 YAML 文件
    output_file = '_data/learning_paths_new.yml'
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(learning_paths, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    print()
    print("=" * 60)
    print(f"✅ 新的学习路径配置已生成: {output_file}")
    print("=" * 60)
    print()
    
    # 输出统计信息
    total_posts = sum(len(topics) for category in learning_paths.values() 
                      for topics in category.values())
    print(f"配置的分类数: {len(learning_paths)}")
    print(f"配置的文章数: {total_posts}")
    print()
    
    # 显示每个分类的统计
    for category, topics in learning_paths.items():
        category_total = sum(len(posts) for posts in topics.values())
        print(f"  {category}: {category_total} 篇（{len(topics)} 个主题）")

if __name__ == '__main__':
    main()

