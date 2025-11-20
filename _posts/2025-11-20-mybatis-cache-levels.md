---
layout: post
title: "MyBatis 何时使用一级缓存？何时使用二级缓存？"
date: 2025-11-20 15:32:01 +0800
categories: [Java, MyBatis]
tags: [MyBatis, 缓存, 性能优化, 分布式]
description: "深入解析 MyBatis 一级缓存与二级缓存的工作原理、生命周期、失效机制及实际应用场景，帮助你在面试中准确回答缓存相关问题。"
---

## 一、核心概念

MyBatis 提供了两级缓存机制来减少数据库访问：

- **一级缓存（Session 级别）**：`SqlSession` 级别的缓存，**默认开启**，无法关闭
- **二级缓存（Mapper 级别）**：跨 `SqlSession` 的缓存，作用于 `Namespace`，**默认关闭**，需手动配置

**核心区别**：
- **作用域**：一级缓存仅在单个 `SqlSession` 内有效；二级缓存在多个 `SqlSession` 间共享
- **生命周期**：一级缓存随 `SqlSession` 关闭而清空；二级缓存持续存在直到应用重启或缓存失效

## 二、一级缓存（SqlSession 级别）

### 1. 工作原理

一级缓存是 MyBatis 的**默认行为**，基于 `SqlSession` 的 `HashMap` 实现：

```java
public class PerpetualCache implements Cache {
    private final String id;
    private Map<Object, Object> cache = new HashMap<>();  // 缓存容器
    
    @Override
    public void putObject(Object key, Object value) {
        cache.put(key, value);
    }
    
    @Override
    public Object getObject(Object key) {
        return cache.get(key);
    }
}
```

**缓存 Key 组成**：
```java
CacheKey = statementId + offset + limit + sql + params + environmentId
```

### 2. 生命周期

```java
// 创建 SqlSession
SqlSession session = sqlSessionFactory.openSession();

// 第一次查询：查数据库，结果放入一级缓存
User user1 = session.selectOne("selectUserById", 1);  // 执行 SQL
System.out.println(user1);

// 第二次查询：相同参数，直接从一级缓存返回
User user2 = session.selectOne("selectUserById", 1);  // 不执行 SQL
System.out.println(user2);

System.out.println(user1 == user2);  // true，同一个对象

// 关闭 SqlSession，一级缓存清空
session.close();
```

### 3. 缓存失效场景

一级缓存在以下情况下失效：

```java
// ❌ 场景 1：执行增删改操作
session.selectOne("selectUserById", 1);  // 查询，放入缓存
session.update("updateUser", user);      // 更新操作
session.selectOne("selectUserById", 1);  // 缓存失效，重新查询数据库

// ❌ 场景 2：手动清空缓存
session.selectOne("selectUserById", 1);  // 查询，放入缓存
session.clearCache();                     // 手动清空
session.selectOne("selectUserById", 1);  // 缓存失效，重新查询

// ❌ 场景 3：不同的 SqlSession
SqlSession session1 = factory.openSession();
SqlSession session2 = factory.openSession();
session1.selectOne("selectUserById", 1);  // session1 的缓存
session2.selectOne("selectUserById", 1);  // session2 没有缓存，查数据库

// ❌ 场景 4：查询参数不同
session.selectOne("selectUserById", 1);  // 查询 ID=1
session.selectOne("selectUserById", 2);  // 参数不同，缓存未命中
```

### 4. 潜在问题（脏读）

在 Spring 集成环境中，一级缓存可能导致数据不一致：

```java
// @Transactional 注解下，同一个 SqlSession
@Transactional
public void updateUser() {
    User user = userMapper.selectById(1);  // 查询，放入缓存
    System.out.println(user.getName());    // "张三"
    
    // 其他线程或服务修改了数据库
    // UPDATE user SET name = '李四' WHERE id = 1
    
    User user2 = userMapper.selectById(1); // 从缓存读取
    System.out.println(user2.getName());   // 仍然是"张三"（脏读）
}
```

**解决方案**：
```xml
<!-- 设置一级缓存作用域为 STATEMENT（每次查询后立即清空） -->
<setting name="localCacheScope" value="STATEMENT"/>
```

## 三、二级缓存（Mapper 级别）

### 1. 工作原理

二级缓存作用于 `Namespace`，多个 `SqlSession` 共享同一个 Mapper 的缓存：

```
SqlSession1 ──┐
              ├──> Mapper Namespace 缓存（共享）
SqlSession2 ──┘
```

**启用步骤**：

```xml
<!-- 1. MyBatis 全局配置（mybatis-config.xml） -->
<settings>
    <setting name="cacheEnabled" value="true"/>
</settings>

<!-- 2. Mapper XML 中开启二级缓存 -->
<mapper namespace="com.example.mapper.UserMapper">
    <cache 
        eviction="LRU"           <!-- 缓存回收策略：LRU/FIFO/SOFT/WEAK -->
        flushInterval="60000"    <!-- 刷新间隔：60秒 -->
        size="512"               <!-- 缓存对象数量 -->
        readOnly="false"/>       <!-- 是否只读（false 会返回缓存对象的拷贝） -->
    
    <select id="selectUserById" resultType="User" useCache="true">
        SELECT * FROM user WHERE id = #{id}
    </select>
</mapper>
```

**实体类必须实现 `Serializable`**：

```java
public class User implements Serializable {
    private static final long serialVersionUID = 1L;
    private Long id;
    private String name;
    // getters & setters
}
```

### 2. 生命周期

```java
// Session1：查询 + 提交
SqlSession session1 = factory.openSession();
User user1 = session1.selectOne("selectUserById", 1);  // 查数据库
session1.commit();  // ⚠️ 必须提交，数据才会放入二级缓存
session1.close();

// Session2：从二级缓存读取
SqlSession session2 = factory.openSession();
User user2 = session2.selectOne("selectUserById", 1);  // 命中二级缓存
session2.close();

System.out.println(user1 == user2);  // false（readOnly=false 会返回副本）
```

**关键点**：
- 必须 **提交事务**（`commit()`）或 **关闭 `SqlSession`**（`close()`）后，查询结果才会进入二级缓存
- `readOnly=false` 时，返回的是缓存对象的**深拷贝**（防止并发修改）

### 3. 缓存失效机制

```xml
<!-- 增删改操作会刷新二级缓存 -->
<update id="updateUser" flushCache="true">  <!-- 默认 true -->
    UPDATE user SET name = #{name} WHERE id = #{id}
</update>

<!-- 查询操作默认不刷新缓存 -->
<select id="selectAll" resultType="User" flushCache="false">  <!-- 默认 false -->
    SELECT * FROM user
</select>
```

### 4. 缓存回收策略

| 策略   | 说明                                          |
|--------|-----------------------------------------------|
| `LRU`  | 最近最少使用（默认）：移除最长时间不被使用的对象 |
| `FIFO` | 先进先出：按对象进入缓存的顺序移除              |
| `SOFT` | 软引用：基于 JVM 垃圾回收器和软引用规则移除    |
| `WEAK` | 弱引用：更积极地基于垃圾回收器和弱引用规则移除  |

## 四、使用场景与选择

### 1. 一级缓存使用场景

**推荐场景**：
- ✅ 单次会话内多次查询相同数据（如事务内多次读取同一用户）
- ✅ 批量操作后的关联查询（如插入订单后查询订单详情）

**不推荐场景**：
- ❌ 分布式环境（不同服务节点无法共享 `SqlSession`）
- ❌ 数据频繁变更且需要实时性的场景

**最佳实践**：
```java
// Spring 集成时，建议关闭一级缓存或设置为 STATEMENT 级别
@Configuration
public class MyBatisConfig {
    @Bean
    public SqlSessionFactory sqlSessionFactory(DataSource dataSource) throws Exception {
        SqlSessionFactoryBean factory = new SqlSessionFactoryBean();
        factory.setDataSource(dataSource);
        
        org.apache.ibatis.session.Configuration config = new org.apache.ibatis.session.Configuration();
        config.setLocalCacheScope(LocalCacheScope.STATEMENT);  // 关键配置
        factory.setConfiguration(config);
        
        return factory.getObject();
    }
}
```

### 2. 二级缓存使用场景

**推荐场景**：
- ✅ 查询频繁、更新较少的数据（如字典表、配置表）
- ✅ 读多写少的业务场景（如商品分类、地区信息）
- ✅ 单体应用且数据一致性要求不高

**不推荐场景**：
- ❌ **分布式/微服务架构**（缓存无法跨服务同步，容易脏读）
- ❌ 数据实时性要求高（如库存、订单状态）
- ❌ 存在多表关联查询（更新一张表无法刷新关联表缓存）

**典型问题示例**：

```java
// 问题：多表关联查询的缓存一致性
<select id="selectOrderWithUser" resultType="Order">
    SELECT o.*, u.name AS userName 
    FROM order o 
    LEFT JOIN user u ON o.user_id = u.id
    WHERE o.id = #{id}
</select>

// 如果只更新了 user 表，order 的二级缓存不会失效
userMapper.updateUser(user);  // 更新用户名
orderMapper.selectOrderWithUser(1);  // 返回旧的用户名（脏数据）
```

### 3. 实际生产环境建议

**现代架构推荐方案**：

```java
// ❌ 不推荐：使用 MyBatis 二级缓存
// 原因：分布式环境无法保证一致性

// ✅ 推荐：使用专业缓存中间件
@Service
public class UserService {
    @Autowired
    private UserMapper userMapper;
    
    @Autowired
    private RedisTemplate<String, User> redisTemplate;
    
    public User getUserById(Long id) {
        // 1. 先查 Redis
        String key = "user:" + id;
        User user = redisTemplate.opsForValue().get(key);
        
        if (user == null) {
            // 2. Redis 未命中，查数据库
            user = userMapper.selectById(id);
            
            // 3. 写入 Redis，设置过期时间
            redisTemplate.opsForValue().set(key, user, 30, TimeUnit.MINUTES);
        }
        
        return user;
    }
    
    @Transactional
    public void updateUser(User user) {
        // 1. 更新数据库
        userMapper.updateUser(user);
        
        // 2. 删除 Redis 缓存（保证一致性）
        redisTemplate.delete("user:" + user.getId());
    }
}
```

**优势**：
- 支持分布式部署（多服务节点共享缓存）
- 灵活的过期策略（TTL、LRU、LFU）
- 更强大的数据结构（String、Hash、List、Set、ZSet）
- 缓存预热、缓存穿透/击穿/雪崩的解决方案

## 五、面试总结

### 推荐回答思路

1. **先说两级缓存的定义**：
   - 一级缓存：`SqlSession` 级别，默认开启，无法关闭
   - 二级缓存：`Namespace` 级别，默认关闭，需配置

2. **对比作用域和生命周期**：
   - 一级缓存：单个 `SqlSession` 内有效，关闭即清空
   - 二级缓存：多个 `SqlSession` 共享，应用级别持久化

3. **说明使用场景**：
   - 一级缓存：事务内多次查询相同数据，Spring 环境建议设为 `STATEMENT` 级别
   - 二级缓存：读多写少的字典表，但**不推荐在分布式环境使用**

4. **补充现代方案**：
   - 生产环境推荐 Redis/Caffeine 等专业缓存中间件
   - 提供更好的分布式支持、过期策略和监控能力

### 加分项

- 能说出一级缓存 Key 的组成（statementId + params）
- 提到 Spring 集成时事务内的一级缓存可能导致脏读
- 了解二级缓存的 `readOnly` 参数（性能 vs 安全性）
- 说出多表关联查询时二级缓存的一致性问题
- 推荐使用 Redis 等分布式缓存替代二级缓存

### 核心记忆点

> **一级缓存**：默认开启，`SqlSession` 级别，适合事务内重复查询  
> **二级缓存**：手动开启，`Namespace` 级别，适合读多写少的单体应用  
> **生产环境**：优先使用 Redis/Caffeine，避免 MyBatis 二级缓存在分布式场景的一致性问题
