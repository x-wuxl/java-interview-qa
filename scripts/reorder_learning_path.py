#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新排序学习路径，保持461题不变，只调整顺序优化学习逻辑
"""

def reorder_learning_path():
    """重新排序学习路径"""
    
    # 读取原始文件
    with open('学习路径排序.md', 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    # 提取标题（去掉编号）
    titles = []
    for line in lines:
        if '. ' in line:
            num, title = line.split('. ', 1)
            titles.append((int(num), title))
        else:
            titles.append((0, line))
    
    # 建立标题到编号的映射
    title_to_num = {title: num for num, title in titles}
    
    # 定义优化后的顺序（使用标题）
    optimized_order = []
    
    # ========== 阶段1：Java基础 (1-30) ==========
    optimized_order.extend([
        "什么是深拷贝和浅拷贝？",
        "如何理解Java中的多态？",
        "接口和抽象类的区别，如何选择？",
        "为什么建议多用组合少用继承？",
        "Java是值传递还是引用传递？",
        "有了equals为什么还需要hashCode方法",  # 458
        "什么是反射机制？为什么反射慢？",
        # String相关
        "String、StringBuilder和StringBuffer的区别？",
        "String为什么设计成不可变的？",
        "String是如何实现不可变的？",
        "String有长度限制吗？是多少？",
        "String中intern的原理是什么？",
        "为什么JDK9中把String的char[]改成了byte[]？",
        "JDK9中对字符串的拼接做了什么优化？",
        "字符串常量是什么时候进入到字符串常量池的？",
        "String a = \"ab\"; String b = \"a\" + \"b\"; a==b吗？",  # 440
        "String str = new String(\"hollis\")创建了几个对象？",  # 441
        # 泛型
        "什么是泛型？有什么好处？",
        "什么是类型擦除",
        "泛型中K、T、V、E、Object等分别代表什么含义",
        "泛型中上下界限定符extends和super有什么区别",
        # 序列化
        "什么是序列化与反序列化",
        "Java序列化的原理是什么",  # 335
        "你知道fastjson的反序列化漏洞吗",
        "serialVersionUID有何用途？如果没定义会有什么问题？",  # 444
        # IO和函数式编程
        "什么是AIO、BIO和NIO？",
        "Lambda表达式是如何实现的",
        "Stream的并行流一定比串行流更快吗",
        # 工具类
        "Arrays.sort使用什么排序算法实现的",  # 426
        "BigDecimal(double)和BigDecimal(String)有什么区别",
        "为什么不能用BigDecimal的equals方法做等值比较",
        "为什么不能用浮点数表示金额",
        "SimpleDateFormat是线程安全的吗？使用时应该注意什么",
    ])
    
    # ========== 阶段2：设计模式 (31-37) ==========
    optimized_order.extend([
        "什么是单例模式，如何实现一个单例？",
        "什么是工厂模式？",
        "什么是策略模式？",
        "什么是模板方法模式？",
        "什么是责任链模式？",
        "什么是观察者模式？",
        "策略模式与代理模式的区别",  # 460
    ])
    
    # ========== 阶段3：集合框架 (38-78) ==========
    optimized_order.extend([
        # List相关
        "ArrayList与LinkedList有什么区别？",
        "ArrayList的扩容机制是怎样的？",
        "ArrayList扩容机制详解：初始容量与1.5倍扩容",  # 365
        "ArrayList和LinkedList的时间复杂度",  # 364
        "CopyOnWriteArrayList是如何实现的？",
        # HashMap相关
        "HashMap的底层实现原理",
        "HashMap为什么线程不安全？",
        "HashMap的容量为什么是2的幂次方？",
        "HashMap的加载因子为什么是0.75？",
        "HashMap什么时候扩容？",
        "HashMap扩容机制详解",  # 368
        "HashMap的hash方法原理",  # 369
        "HashMap为什么在链表长度为8时转为红黑树？",  # 366
        "HashMap在JDK1.7和1.8中的区别",  # 367
        "为什么HashMap有时候链表长度超过8也不树化？",  # 154
        "HashMap的key可以为null吗？",  # 155
        # 其他Map和Set
        "Hashtable、HashMap、ConcurrentHashMap的区别",  # 156
        "ConcurrentHashMap是如何实现的？",
        "ConcurrentHashMap在JDK1.7和1.8中有什么不同？",
        "LinkedHashMap是如何实现的？",  # 157
        "TreeMap和HashMap有什么区别？",
        "WeakHashMap了解吗？",  # 158
        "HashSet和HashMap有什么关系？",
        # 队列相关
        "PriorityQueue的底层实现原理",  # 159
        "ArrayDeque和LinkedList作为队列的区别",  # 160
    ])
    
    # ========== 阶段4：JVM (79-149) ==========
    optimized_order.extend([
        # 内存区域
        "JVM的运行时内存区域是怎样的？",
        "JVM为什么要把堆和栈区分出来呢？",
        "虚拟机中的堆一定是线程共享的吗？",
        "什么是方法区？是如何实现的？",
        "方法区存储什么数据？",  # 457
        "Java的堆是如何分代的？为什么分代？",
        "什么是堆外内存？如何使用堆外内存？",
        "OutOfMemory和StackOverflow的区别是什么？",
        "内存泄漏和内存溢出的区别是什么？",
        "一个Java进程占用的内存都有哪些部分？",  # 339
        "JVM内存结构全面解析",  # 340
        # 对象创建
        "JVM是如何创建对象的？",
        "一个对象的结构是什么样的？",
        "JVM如何保证给对象分配内存过程的线程安全？",
        "Java中的对象一定在堆上分配内存吗？",
        "什么是逃逸分析？",
        # 对象回收
        "JVM如何判断对象是否存活？",
        "什么是强引用、软引用、弱引用和虚引用？",
        # GC算法
        "JVM有哪些垃圾回收算法",
        "新生代和老年代的GC算法",
        "JVM中一次完整的GC流程是怎样的",
        "YoungGC和FullGC的触发条件是什么",
        "FullGC多久一次算正常",
        "什么是三色标记算法",
        "什么是跨代引用，有什么问题",
        "什么是STW（Stop-The-World）及其影响",  # 449
        "什么是安全点（Safe Point），有什么作用",  # 450
        # GC器
        "介绍下CMS的垃圾回收过程",
        "G1和CMS有什么区别？",
        "为什么G1从JDK9之后成为默认的垃圾回收器？",
        "JDK11中新出的ZGC有什么特点？",
        "Java8和Java11的GC有什么区别？",
        "新生代和老年代的垃圾回收器有何区别？",
        "项目中如何选择垃圾回收器？为啥选择这个？",
        "说一说JVM的并发回收和并行回收",
        "新生代如果只有一个Eden+一个Survivor可以吗？",
        # 类加载
        "Java中的类什么时候会被加载？",
        "Java中类加载的过程是怎么样的？",
        "Java类加载流程与过程",  # 338
        "类的生命周期是怎么样的？",
        "什么是双亲委派？如何破坏？",
        "双亲委派机制的核心思想是什么？",  # 454
        "双亲委派机制如何打破（详细补充）",  # 453
        "破坏双亲委派之后，能重写String类吗？",
        "如何判断JVM中类和其他类是不是同一个类？",
        "JDK 1.8和1.9中类加载器有哪些不同？",
        # 常量池
        "什么是Class常量池，和运行时常量池关系是什么？",
        "运行时常量池和字符串常量池的关系是什么？",
        "字符串常量池是如何实现的？",
        # 编译和执行
        "什么是编译和反编译？",
        "Java一定就是平台无关的吗？",
        "Java是如何实现平台无关的？",  # 336
        "Java是编译型还是解释型语言？",  # 337
        "什么是AOT编译？和JIT有啥区别？",
        "简单介绍一下JIT优化技术？",
        # JVM工具和调优
        "常见的JVM工具有哪些",
        "JVM调优参数详解",  # 341
        "常用的JVM启动参数有哪些",  # 342
        "Java发生了OOM一定会导致JVM退出吗",
        "什么情况会导致JVM退出",
        "对JDK进程执行kill -9有什么影响",
        # SPI
        "什么是SPI，和API有什么区别",  # 448
    ])
    
    # ========== 阶段5：线程基础 (150-158) ==========
    optimized_order.extend([
        "创建线程有几种方式？",
        "线程有几种状态，状态之间的流转是怎样的？",
        "Java是如何判断一个线程是否存活的？",
        "Thread.sleep(0)的作用是什么？",
        "什么是守护线程，和普通线程有什么区别？",
        "什么是多线程中的上下文切换？",
        "线程是如何被调度的？",
        "线程同步的方式有哪些？",
        "什么是死锁，如何解决？",
        "run、start、wait、sleep、notify、notifyAll区别",  # 354
    ])
    
    # ========== 阶段6：并发编程理论基础 (159-164) ==========
    optimized_order.extend([
        "什么是并发，什么是并行？",
        "能不能谈谈你对线程安全的理解？",
        "有哪些实现线程安全的方案",
        "并发编程中的原子性和数据库ACID的原子性一样吗？",
        "指令重排序",  # 456
        "final关键字与可见性是否有关",  # 443
    ])
    
    # ========== 阶段7：并发编程实践 (165-230) ==========
    optimized_order.extend([
        # JMM
        "什么是Java内存模型（JMM）？",
        "什么是happens-before原则？",
        "happens-before和as-if-serial有啥区别和联系？",
        "有了MESI为啥还需要JMM？",
        "什么是总线嗅探和总线风暴，和JMM有什么关系？",
        "到底啥是内存屏障？到底怎么加的？",
        "volatile能保证原子性吗？为什么？",
        "有了synchronized为什么还需要volatile",
        "volatile如何保证可见性和有序性",  # 447
        "volatile关键字与禁止重排序如何解决多线程可见性",  # 357
        # CAS
        "什么是CAS？存在什么问题？",
        "介绍下CAS",  # 451
        "CAS操作类",  # 429
        "CAS一定有自旋吗？",
        "CAS在操作系统层面是如何保证原子性的",
        "有了CAS为啥还需要volatile",
        "ABA问题",  # 423
        "什么是Unsafe？",
        # synchronized
        "synchronized是怎么实现的？",
        "synchronized锁的是什么？",
        "synchronized是如何保证原子性、可见性、有序性的？",
        "synchronized的锁优化是怎样的？",
        "synchronized的锁升级过程是怎样的？",
        "synchronized升级过程中有几次自旋？",
        "synchronized的锁能降级吗？",
        "为什么JDK15要废弃偏向锁？",
        "synchronized是否可重入",  # 445
        "synchronized是非公平锁吗，那么是如何体现的？",  # 446
        "synchronized和ReentrantLock的区别",  # 355
        "synchronized和lock区别",  # 356
        # 基础操作
        "int a = 1是原子性操作吗",
        "如何保证多线程下i++结果正确",
        # AQS和Lock
        "如何理解AQS？",
        "AQS的同步队列和条件队列原理",
        "AQS是如何实现线程的等待和唤醒的？",
        "AQS为什么采用双向链表？",
        "什么是AQS的独占模式和共享模式？",
        "AQS操作类有哪些？",  # 424
        "什么是可重入锁，怎么实现可重入锁？",
        "可重入锁的底层实现",  # 359
        "公平锁和非公平锁的区别",
        "Lock是否公平，能否实现非公平，如何实现？",  # 346
        "ReentrantLock增加了哪些高级功能？",  # 349
        # 线程池
        "什么是线程池，如何实现的？",
        "ForkJoinPool和ThreadPoolExecutor的区别是什么？",  # 344
        "线程池的拒绝策略有哪些？",
        "为什么不建议通过Executors构建线程池？",
        "线程数设定成多少更合适？",
        "如何让Java的线程池顺序执行任务？",
        "如何实现一个动态线程池？",  # 360
        "线程池多线程操作对象是否需要加volatile保障可见性？",  # 363
        # 异步编程
        "CompletableFuture的底层是如何实现的？",
        "如何对多线程进行编排？",
        # 并发工具类
        "CountDownLatch、CyclicBarrier、Semaphore区别？",
        "LongAdder和AtomicLong的区别？",
        # ThreadLocal
        "什么是ThreadLocal，如何实现的？",
        "ThreadLocalMap的数据结构",  # 352
        "ThreadLocalMap的冲突解决机制",  # 350
        "ThreadLocalMap的扩容机制",  # 351
        "ThreadLocal为什么会导致内存泄漏？如何解决？",
        "ThreadLocal的key是弱引用，在get()时发生GC后key会是null吗？",  # 353
        "ThreadLocal的应用场景有哪些？",
        "有了InheritableThreadLocal为啥还需要TransmittableThreadLocal？",
        "探测式清理和启发式清理",  # 361
        "父子线程之间怎么共享、传递数据？",  # 362
        # 异常处理
        "为什么不能在try-catch中捕获子线程的异常？",
        "如何实现主线程捕获子线程异常？",
        "Java线程出现异常，进程为啥不会退出？",
        # 并发实战
        "有三个线程T1,T2,T3如何保证顺序执行？",
        "三个线程分别顺序打印0-100",
        # 虚拟线程
        "JDK21中的虚拟线程是怎么回事？",
        "为什么虚拟线程不能用synchronized？",
        "为什么虚拟线程不要和线程池一起用？",
        "为什么虚拟线程尽量避免使用ThreadLocal？",
    ])
    
    # ========== 阶段8：MySQL (231-338) ==========
    optimized_order.extend([
        # 索引基础
        "InnoDB为什么使用B+树实现索引？",
        "InnoDB中的索引类型？",
        "什么是聚簇索引和非聚簇索引？",
        "什么是回表，怎么减少回表的次数？",
        "什么是索引覆盖、索引下推？",
        "InnoDB和MyISAM有什么区别？",
        "MyISAM的索引结构是怎么样的，它存在的问题是什么？",
        "唯一索引和主键索引的区别？",
        "MySQL是如何保证唯一性索引的唯一性的？",  # 231
        "从InnoDB索引结构分析索引Key长度限制",  # 452
        # 索引设计
        "什么是最左前缀匹配？为什么要遵守？",
        "MySQL索引一定遵循最左前缀匹配吗？",
        "A,B,C的联合索引，按照AB,AC,BC查询，能走索引吗？",
        "a,b两个单独索引，where a=xx and b=xx走哪个索引？为什么？",
        "什么是索引合并，原理是什么？",
        "什么是索引跳跃扫描？",
        "设计索引的时候有哪些原则？",
        "区分度不高的字段建索引一定没用吗？",
        "联合索引是越多越好吗？",
        "MySQL索引建立与性能影响",  # 386
        "MySQL索引存储与失效场景详解",  # 385
        "MySQL索引失效情况",  # 384
        "MySQL索引，最左匹配，索引覆盖，索引下推，索引失效情况，查询优化",  # 387
        "用了索引还是很慢，可能是什么原因？",
        "索引失效的问题如何排查？",
        "MySQL选错索引的原因及解决方案",  # 388
        "WHERE条件顺序对索引的影响",  # 442
        # 数据类型
        "UUID和自增ID做主键哪个好，为什么？",
        "CHAR与VARCHAR的区别及使用场景",  # 431
        "CHAR、VARCHAR、TEXT的区别与VARCHAR长度限制详解",  # 430
        "MySQL中BLOB与TEXT的区别及使用场景",  # 436
        # 事务
        "什么是数据库事务？",
        "MySQL事务ACID实现原理",  # 374
        "MySQL中的事务隔离级别",
        "什么是脏读、幻读、不可重复读？",
        "InnoDB如何解决脏读、不可重复读和幻读？",
        "InnoDB的RR到底有没有解决幻读？",
        "如何理解MVCC？",
        "什么是ReadView，什么样的ReadView可见？",
        "当前读和快照读有什么区别？",
        "二级索引在索引覆盖时如何使用MVCC？",
        "为什么MySQL默认使用RR隔离级别？",
        "为什么默认RR，大厂要改成RC？",
        "MySQL的select会用到事务吗",  # 383
        # 锁机制
        "介绍下InnoDB的锁机制",
        "InnoDB中的表级锁、页级锁、行级锁",
        "MySQL的行级锁锁的到底是什么",
        "什么是排他锁和共享锁",
        "什么是意向锁",
        "FOR UPDATE语句InnoDB加了哪些锁",  # 343
        "什么是MySQL的元数据锁（MDL锁）？",  # 358
        "MySQL只操作同一条记录也会发生死锁吗",
        "数据库死锁如何解决",
        "MySQL锁机制全面解析",  # 347
        "乐观锁与悲观锁如何实现",
        "数据库乐观锁的过程中完全没有加任何锁吗",
        "什么是数据库的锁升级,InnoDB支持吗",
        "InnoDB加索引会锁表吗？",  # 345
        "MySQL并发控制手段详解",  # 379
        # SQL执行和优化
        "MySQL一条SQL语句的执行过程",
        "SQL查询语句的执行顺序",  # 438
        "为什么大厂不建议使用多表JOIN",
        "ON和WHERE的区别详解",  # 437
        "SQL执行计划分析的时候，要关注哪些信息？",
        "MySQL优化器的索引成本计算",  # 375
        "如何进行SQL调优？",
        "慢SQL的问题如何排查？",
        "执行计划中，key有值，还是很慢怎么办？",
        "ORDER BY是怎么实现的？",
        "Using filesort能优化吗，怎么优化？",
        "MySQL的深度分页如何优化？",
        "limit 0,100和limit 10000000,100一样吗？",
        "MySQL的limit+orderby为什么会数据重复？",
        "MySQL中like的模糊查询如何优化？",
        "小表驱动大表的原理与性能优化",  # 455
        "MySQL慢查询优化",  # 380
        "MySQL慢查询的排除与优化",  # 381
        "MySQL优化（综合）",  # 376
        # 存储引擎
        "MySQL存储引擎详解与对比",  # 378
        "InnoDB Buffer Pool缓冲池详解",  # 432
        "Buffer Pool的读写过程详解",  # 427
        "InnoDB支持的行格式详解",  # 433
        "InnoDB的数据页与B+树的关系",  # 434
        "InnoDB的页分裂和页合并机制",  # 435
        # 事务实现
        "什么是事务的2阶段提交",
        "InnoDB的一次更新事务是怎么实现的",
        "undolog会一直存在吗？什么时候删除",
        "介绍下MySQL5.7中的组提交",
        "MySQL执行大事务会存在什么问题",
        "binlog、redolog和undolog的区别",  # 390
        # 主从复制
        "MySQL主从复制的过程",
        "MySQL的并行复制原理",
        "MySQL主从复制详解",  # 373
        "MySQL主从同步：binlog的三种模式详解",  # 372
        "MySQL三种日志、主从架构与复制原理",  # 370
        "MySQL三种日志类型综合说明",  # 371
        "什么是数据库的主从延迟，如何解决？",
        "数据库读写分离的代码实现方案",  # 391
        # 高级特性
        "MySQL是AP的还是CP的系统？",
        "什么是OnlineDDL",
        "MySQL怎么做热点数据高效更新？",
        "高并发情况下自增主键会不会重复，为什么？",
        "MySQL自增主键用完了会怎么样？",
        "什么情况会导致自增主键不连续？",
        "MySQL获取主键ID的瓶颈在哪里？如何优化？",
        "数据库扫表任务如何避免出现死循环？",
        "数据库怎么做加密和解密？",
        "数据库加密后怎么做模糊查询？",
        "MySQL支持Emoji表情存储的完整解决方案",  # 382
        "阿里的数据库能抗秒杀的原理",
        "MySQL分库分表方案与动态扩展策略",  # 377
        "MySQL驱动表概念及选择策略",  # 389
    ])
    
    # ========== 阶段9：Redis (339-365) ==========
    optimized_order.extend([
        # 数据结构
        "Redis有哪些数据结构？",
        "Redis底层结构",  # 396
        "Redis的String是如何实现的？",
        "Redis的List是如何实现的？",
        "Redis的Hash是如何实现的？",
        "Redis的Set是如何实现的？",
        "Redis的ZSet是如何实现的？",
        "什么是跳表？为什么用跳表？",
        "Redis跳表实现，hash底层实现，为什么使用ziplist，如何扩容",  # 404
        "Redis的HyperLogLog了解过吗？",
        "Redis的优势，解决了哪些问题",  # 399
        # 持久化
        "Redis的持久化机制有哪些？",
        "RDB和AOF的区别是什么？",
        "Redis AOF日志写入流程与刷盘策略",  # 392
        "Redis故障恢复：RDB和AOF的区别",  # 397
        # 高可用
        "Redis的主从复制原理",
        "Redis主从复制过程详解",  # 393
        "Redis如何实现高可用",
        "Redis的哨兵模式详解",  # 400
        "Redis哨兵模式选主策略详解",  # 395
        "Redis的集群模式详解",  # 402
        # 内存管理
        "Redis的过期策略详解",  # 401
        "Redis内存淘汰策略详解",  # 394
        # 分布式锁
        "Redis分布式锁的实现",  # 348
        # 缓存
        "Redis缓存一致性问题与解决方案",  # 403
        "Redis热点key问题如何解决",  # 398
    ])
    
    # ========== 阶段10：Spring框架 (366-396) ==========
    optimized_order.extend([
        # IOC
        "介绍一下Spring的IOC",
        "Spring IOC与AOP全面解析",  # 407
        "Spring中的Bean是线程安全的吗？",
        "SpringBean的初始化过程详解",  # 408
        "SpringBean的生命周期详解",  # 409
        "Spring中的Bean作用域详解",  # 413
        "@Lazy注解能解决循环依赖吗？",
        "Spring循环依赖问题详解",  # 415
        "Spring三级缓存机制深度解析",  # 412
        # AOP
        "介绍一下Spring的AOP",
        "AOP通知类型",  # 405
        "Spring AOP实现，动态代理",  # 406
        "Spring的AOP在什么场景下会失效？",
        # 事务
        "Spring中如何开启事务？",
        "Spring的事务传播机制有哪些？",
        "Spring事务失效可能是哪些原因？",
        "Spring事务管理全面解析",  # 414
        "Spring事务实现原理及@Transactional注解原理",  # 439
        "Spring的事务在多线程下生效吗？为什么？",
        "同时使用@Transactional与@Async时，事务会不会生效？",
        "Spring中的事务事件如何使用？",
        # 异步
        "为什么不建议直接使用Spring的@Async？",
        # SpringBoot
        "SpringBoot和Spring的区别是什么？",
        "SpringBoot核心模块有哪些？",  # 410
        "SpringBoot是如何实现自动配置的？",
        "SpringBoot的启动流程是怎么样的？",
        "SpringBoot是如何实现main方法启动Web项目的？",
        "Spring6.0和SpringBoot3.0有什么新特性？",
        "为什么SpringBoot3中移除了spring.factories？",
        "SpringBoot如何做优雅停机？",
        # SpringMVC
        "SpringMVC三层架构的好处",  # 411
        # 设计模式
        "Spring框架中用到的设计模式",  # 416
        # Starter
        "如何自定义一个SpringBoot Starter？",
        "实现一个SpringBoot Starter（实战案例）",  # 418
    ])
    
    # ========== 阶段11：微服务与SpringCloud (397-405) ==========
    optimized_order.extend([
        "什么是微服务？",
        "SpringCloud有哪些核心组件？",
        "Eureka的工作原理是什么？",
        "Ribbon的负载均衡策略有哪些？",
        "Feign的工作原理是什么？",
        "Hystrix的熔断机制是什么？",
        "Gateway的工作原理是什么？",
        "Nacos和Eureka的区别？",
        "负载均衡策略有哪些？轮询、权重、随机、最小连接数等策略详解",  # 461
    ])
    
    # ========== 阶段12：分布式理论 (406-412) ==========
    optimized_order.extend([
        "什么是CAP理论？",
        "什么是BASE理论？",
        "CAP协议、ACID理论、BASE理论、一致性模型对比详解",  # 428
        "什么是最终一致性？",
        "什么是一致性Hash？",
        "分布式ID生成方案有哪些？",
        "雪花算法是什么？",
    ])
    
    # ========== 阶段13：分布式事务 (413-419) ==========
    optimized_order.extend([
        "什么是分布式事务？",
        "分布式事务的解决方案有哪些？",
        "分布式事务方案对比：2PC、3PC、TCC、消息补偿",  # 419
        "什么是2PC和3PC？",
        "什么是TCC？",
        "什么是Saga？",
        "AT模式：Seata的自动化两阶段提交",  # 425
    ])
    
    # ========== 阶段14：分布式锁 (420-423) ==========
    optimized_order.extend([
        "什么是分布式锁？",
        "分布式锁的实现方式有哪些？",
        "Redis实现分布式锁的原理？",
        "Zookeeper实现分布式锁的原理？",
    ])
    
    # ========== 阶段15：分库分表 (424-428) ==========
    optimized_order.extend([
        "什么是分库分表？",
        "什么时候需要分库分表？",
        "分库分表的策略有哪些？",
        "分库分表后如何解决跨库查询？",
        "分库分表后如何解决分布式事务？",
        "ShardingSphere的原理是什么？",
    ])
    
    # ========== 阶段16：消息队列 (429-446) ==========
    optimized_order.extend([
        "为什么要使用消息队列？",
        "消息队列的使用场景有哪些？",  # 459
        "Kafka、ActiveMQ、RabbitMQ和RocketMQ都有哪些区别？",
        # Kafka
        "Kafka的架构是怎么样的？",
        "Kafka为什么有Topic还要用Partition？",
        "Kafka为什么这么快？",
        "Kafka消息的发送过程简单介绍一下？",
        "Kafka如何保证消息不丢失？",
        "为什么Kafka没办法100%保证消息不丢失？",
        "Kafka怎么保证消费只消费一次的？",
        "Kafka如何实现顺序消费？",
        # RocketMQ
        "RocketMQ的架构是怎么样的？",
        "RocketMQ如何保证消息不丢失？",
        "RocketMQ的延迟消息是如何实现的？",
        # RabbitMQ
        "RabbitMQ的架构是怎么样的？",
        "RabbitMQ如何保证消息的可靠性？",  # 420
        "RabbitMQ死信队列（Dead Letter Queue）详解",  # 421
        "RabbitMQ的Exchange(交换器)有哪4种类型？",  # 422
    ])
    
    # ========== 阶段17：RPC和Dubbo (447-459) ==========
    optimized_order.extend([
        "什么是RPC，和HTTP有什么区别？",
        "为什么RPC要比HTTP更快一些？",
        "什么场景只能用HTTP，不能用RPC？",
        "Dubbo的整体架构是怎么样的？",
        "Dubbo的服务调用的过程是什么样的？",
        "Dubbo如何实现像本地方法一样调用远程方法的？",
        "Dubbo支持哪些调用协议？",
        "Dubbo支持哪些序列化方式？",
        "Dubbo支持哪些负载均衡策略？",
        "Dubbo支持哪些服务治理？",
        "Dubbo服务发现与路由的概念有什么不同？",
        "Dubbo的SPI和JDK的SPI有什么区别？",
        "为什么Dubbo不用JDK的SPI？",
        "什么是Dubbo的优雅停机，怎么实现的？",
        "什么是泛化调用？",
    ])
    
    # ========== 阶段18：ElasticSearch (460-461) ==========
    optimized_order.extend([
        "为什么要使用 ElasticSearch？和传统关系数据库（如 MySQL）有什么不同？",
        "什么是倒排索引？",
        "ElasticSearch 为什么快？",
        "什么是 ElasticSearch 的深度分页问题？如何解决？",
        "如何保证 ES 和数据库的数据一致性？",
        "如何优化 ElasticSearch 搜索性能？",
    ])
    
    # 生成优化后的文件
    output_lines = []
    matched_titles = set()
    for i, title in enumerate(optimized_order, 1):
        # 尝试直接匹配
        if title in title_to_num:
            output_lines.append(f"{i}. {title}")
            matched_titles.add(title)
        else:
            # 尝试匹配转义字符（文件中的格式是 \"）
            escaped_title = title.replace('\"', '\\"')
            if escaped_title in title_to_num:
                output_lines.append(f"{i}. {escaped_title}")
                matched_titles.add(escaped_title)
            else:
                # 尝试反向匹配
                unescaped_title = title.replace('\\"', '\"')
                if unescaped_title in title_to_num:
                    output_lines.append(f"{i}. {unescaped_title}")
                    matched_titles.add(unescaped_title)
                else:
                    print(f"⚠️  警告: 标题 '{title}' 未找到对应的原始题目")
    
    # 检查是否有遗漏的题目
    all_titles = set(title_to_num.keys())
    used_titles = matched_titles
    missing_titles = all_titles - used_titles
    
    if missing_titles:
        print(f"\n⚠️  以下 {len(missing_titles)} 个题目未包含在优化后的顺序中:")
        for title in sorted(missing_titles):
            print(f"  - {title}")
        # 将遗漏的题目追加到末尾
        for title in sorted(missing_titles):
            output_lines.append(f"{len(output_lines) + 1}. {title}")
    
    # 写入文件
    with open('学习路径排序_优化版.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    
    print(f"\n✅ 优化完成!")
    print(f"   原始题目数: {len(titles)}")
    print(f"   优化后题目数: {len(output_lines)}")
    print(f"   已生成文件: 学习路径排序_优化版.md")

if __name__ == '__main__':
    reorder_learning_path()

