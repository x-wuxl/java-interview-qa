---
title: "数据库加密后怎么做模糊查询？"
date: 2025-11-02
categories: [MySQL, 数据安全]
tags: [MySQL, 数据加密, 模糊查询, 可搜索加密]
description: "深入解析加密数据的模糊查询实现方案，包括部分加密、哈希映射、分词索引、同态加密等技术及性能优化"
nav_order: 392
parent: 数据库MySQL
---
## 一、问题本质

**核心矛盾**：
- 加密后数据是密文（如：`aB3dF9...`），无法直接LIKE查询
- 业务需要支持模糊搜索（如：搜索手机号 `138****1234`）

**示例**：
```sql
-- 加密前（可模糊查询）
SELECT * FROM users WHERE phone LIKE '138%';

-- 加密后（无法查询）
SELECT * FROM users WHERE phone LIKE '138%';  -- phone存储的是密文，查不到
```

## 二、解决方案对比

| 方案 | 安全性 | 查询性能 | 实现复杂度 | 适用场景 |
|------|--------|----------|------------|----------|
| 部分加密 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | 手机号、身份证前缀查询 |
| 哈希映射表 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | 精确+模糊混合查询 |
| 全文分词索引 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 姓名、地址模糊搜索 |
| 可搜索加密(SSE) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 高安全要求场景 |
| 应用层解密过滤 | ⭐⭐⭐⭐ | ⭐ | ⭐ | 数据量小的场景 |

## 三、方案详解

### 方案1：部分加密（折中方案）

**核心思路**：保留前几位明文用于查询，后面部分加密。

#### 实现：手机号加密

```java
@Component
public class PartialEncryptor {
    
    @Autowired
    private AESEncryptor aesEncryptor;
    
    /**
     * 手机号加密：保留前3位和后4位，中间4位加密
     */
    public String encryptPhone(String phone) {
        if (phone == null || phone.length() != 11) {
            throw new IllegalArgumentException("无效的手机号");
        }
        
        String prefix = phone.substring(0, 3);   // 138
        String middle = phone.substring(3, 7);   // 1234
        String suffix = phone.substring(7);      // 5678
        
        // 只加密中间4位
        String encryptedMiddle = aesEncryptor.encrypt(middle);
        
        return prefix + "_" + encryptedMiddle + "_" + suffix;
        // 存储格式：138_a3bF9dK==_5678
    }
    
    public String decryptPhone(String encrypted) {
        String[] parts = encrypted.split("_");
        String prefix = parts[0];
        String encryptedMiddle = parts[1];
        String suffix = parts[2];
        
        String middle = aesEncryptor.decrypt(encryptedMiddle);
        
        return prefix + middle + suffix;  // 13812345678
    }
}
```

**SQL查询**：
```sql
-- 前缀查询（可使用索引）
SELECT * FROM users WHERE phone LIKE '138%';

-- 后缀查询（需要全表扫描）
SELECT * FROM users WHERE phone LIKE '%5678';

-- 完整号码查询
SELECT * FROM users WHERE phone = '138_a3bF9dK==_5678';
```

**表结构优化**：
```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    phone VARCHAR(500),
    phone_prefix CHAR(3) GENERATED ALWAYS AS (LEFT(phone, 3)) STORED,  -- 虚拟列
    INDEX idx_phone_prefix (phone_prefix)
);

-- 查询优化
SELECT * FROM users WHERE phone_prefix = '138';
```

**优势与劣势**：
- ✅ 实现简单
- ✅ 支持前缀查询，性能好
- ✅ 适合手机号、身份证等结构化数据
- ❌ 前缀明文存储，安全性降低
- ❌ 不支持中间部分模糊查询

---

### 方案2：哈希映射表

**核心思路**：为常用查询条件建立哈希索引表。

#### 实现：手机号搜索

```java
@Component
public class HashIndexService {
    
    @Autowired
    private JdbcTemplate jdbcTemplate;
    
    /**
     * 保存用户时，同时建立哈希索引
     */
    @Transactional
    public void saveUserWithIndex(User user) {
        // 1. 加密完整手机号
        String encryptedPhone = aesEncryptor.encrypt(user.getPhone());
        
        // 2. 插入用户表
        jdbcTemplate.update(
            "INSERT INTO users (name, phone) VALUES (?, ?)",
            user.getName(), encryptedPhone
        );
        Long userId = getLastInsertId();
        
        // 3. 建立前缀哈希索引
        List<String> prefixes = generatePrefixes(user.getPhone());
        for (String prefix : prefixes) {
            String hash = hash(prefix);
            
            jdbcTemplate.update(
                "INSERT INTO phone_index (hash, user_id) VALUES (?, ?)",
                hash, userId
            );
        }
    }
    
    /**
     * 生成所有可能的前缀
     */
    private List<String> generatePrefixes(String phone) {
        List<String> prefixes = new ArrayList<>();
        
        // 生成3-11位的所有前缀
        for (int i = 3; i <= phone.length(); i++) {
            prefixes.add(phone.substring(0, i));
        }
        
        return prefixes;
        // 例如：138, 1381, 13812, 138123, ..., 13812345678
    }
    
    /**
     * 哈希函数（使用HMAC-SHA256）
     */
    private String hash(String input) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec keySpec = new SecretKeySpec(
                "hash_secret_key".getBytes(), "HmacSHA256"
            );
            mac.init(keySpec);
            
            byte[] hash = mac.doFinal(input.getBytes());
            return Base64.getEncoder().encodeToString(hash);
        } catch (Exception e) {
            throw new RuntimeException("哈希失败", e);
        }
    }
    
    /**
     * 模糊查询
     */
    public List<User> searchByPhone(String phonePrefix) {
        // 1. 计算查询前缀的哈希
        String queryHash = hash(phonePrefix);
        
        // 2. 从索引表查询user_id
        List<Long> userIds = jdbcTemplate.queryForList(
            "SELECT user_id FROM phone_index WHERE hash = ?",
            Long.class, queryHash
        );
        
        if (userIds.isEmpty()) {
            return Collections.emptyList();
        }
        
        // 3. 查询用户详情
        String sql = "SELECT * FROM users WHERE id IN (" +
            userIds.stream().map(String::valueOf).collect(Collectors.joining(",")) +
            ")";
        
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql);
        
        // 4. 解密并过滤（防止哈希碰撞）
        return rows.stream()
            .map(this::mapToUser)
            .filter(user -> user.getPhone().startsWith(phonePrefix))
            .collect(Collectors.toList());
    }
    
    private User mapToUser(Map<String, Object> row) {
        User user = new User();
        user.setId((Long) row.get("id"));
        user.setName((String) row.get("name"));
        user.setPhone(aesEncryptor.decrypt((String) row.get("phone")));
        return user;
    }
}
```

**表结构**：
```sql
-- 用户表
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    phone VARCHAR(500)  -- 存储加密后的完整手机号
);

-- 哈希索引表
CREATE TABLE phone_index (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    hash VARCHAR(100),   -- 前缀的哈希值
    user_id BIGINT,
    INDEX idx_hash (hash),
    INDEX idx_user (user_id)
);
```

**优势与劣势**：
- ✅ 完整加密，安全性高
- ✅ 支持任意长度前缀查询
- ✅ 查询性能好（索引支持）
- ❌ 存储空间增加（每个手机号存9个哈希）
- ❌ 实现复杂
- ❌ 哈希可能碰撞（需二次过滤）

---

### 方案3：全文分词索引（适合中文姓名/地址）

**核心思路**：对敏感数据进行脱敏分词，建立全文索引。

#### 实现：姓名模糊搜索

```java
@Component
public class TokenizedSearchService {
    
    /**
     * 姓名分词
     */
    public List<String> tokenizeName(String name) {
        List<String> tokens = new ArrayList<>();
        
        // 单字分词
        for (int i = 0; i < name.length(); i++) {
            tokens.add(String.valueOf(name.charAt(i)));
        }
        
        // 双字分词
        for (int i = 0; i < name.length() - 1; i++) {
            tokens.add(name.substring(i, i + 2));
        }
        
        // 全名
        tokens.add(name);
        
        return tokens;
        // 例如："张三丰" → ["张", "三", "丰", "张三", "三丰", "张三丰"]
    }
    
    /**
     * 保存用户
     */
    @Transactional
    public void saveUser(User user) {
        // 1. 加密姓名
        String encryptedName = aesEncryptor.encrypt(user.getName());
        
        jdbcTemplate.update(
            "INSERT INTO users (name, name_encrypted) VALUES (?, ?)",
            user.getName(), encryptedName
        );
        Long userId = getLastInsertId();
        
        // 2. 生成搜索tokens（脱敏处理）
        List<String> tokens = tokenizeName(user.getName());
        
        for (String token : tokens) {
            // 对token进行哈希（防止明文泄露）
            String tokenHash = hash(token);
            
            jdbcTemplate.update(
                "INSERT INTO name_tokens (token_hash, user_id) VALUES (?, ?)",
                tokenHash, userId
            );
        }
    }
    
    /**
     * 模糊查询
     */
    public List<User> searchByName(String keyword) {
        String keywordHash = hash(keyword);
        
        List<Long> userIds = jdbcTemplate.queryForList(
            "SELECT DISTINCT user_id FROM name_tokens WHERE token_hash = ?",
            Long.class, keywordHash
        );
        
        // 查询并解密
        return getUsersByIds(userIds);
    }
}
```

**表结构**：
```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),           -- 明文或脱敏（如"张**"）
    name_encrypted VARCHAR(500), -- 完整加密
    INDEX idx_name (name)        -- 脱敏字段可建索引
);

CREATE TABLE name_tokens (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    token_hash VARCHAR(100),
    user_id BIGINT,
    INDEX idx_token (token_hash),
    INDEX idx_user (user_id)
);
```

**使用ElasticSearch增强**：
```java
@Document(indexName = "users_search")
public class UserSearchDoc {
    @Id
    private String id;
    
    private String nameHash;  // 姓名哈希（用于精确匹配）
    
    @Field(type = FieldType.Text, analyzer = "ik_smart")
    private String nameTokens;  // 姓名分词（用于模糊搜索）
}

// 搜索
public List<User> search(String keyword) {
    // 1. 从ES搜索
    List<String> userIds = elasticsearchTemplate.search(
        NativeSearchQueryBuilder
            .withQuery(QueryBuilders.matchQuery("nameTokens", keyword))
            .build(),
        UserSearchDoc.class
    ).stream()
        .map(SearchHit::getContent)
        .map(UserSearchDoc::getId)
        .collect(Collectors.toList());
    
    // 2. 从数据库查询完整数据并解密
    return getUsersByIds(userIds);
}
```

---

### 方案4：应用层全表解密过滤（小数据量）

```java
@Service
public class BruteForceSearchService {
    
    /**
     * 适合数据量 < 10万的场景
     */
    public List<User> searchByPhoneSuffix(String suffix) {
        // 1. 查询所有用户
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
            "SELECT id, name, phone FROM users"
        );
        
        // 2. 并行解密并过滤
        return rows.parallelStream()
            .map(row -> {
                User user = new User();
                user.setId((Long) row.get("id"));
                user.setName((String) row.get("name"));
                user.setPhone(aesEncryptor.decrypt((String) row.get("phone")));
                return user;
            })
            .filter(user -> user.getPhone().contains(suffix))
            .collect(Collectors.toList());
    }
}
```

**优化：分页查询**：
```java
public List<User> searchByPhoneSuffixPaged(String suffix) {
    Long lastId = 0L;
    int batchSize = 1000;
    List<User> results = new ArrayList<>();
    
    while (results.size() < 100) {  // 最多返回100条
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
            "SELECT * FROM users WHERE id > ? ORDER BY id LIMIT ?",
            lastId, batchSize
        );
        
        if (rows.isEmpty()) {
            break;
        }
        
        // 解密并过滤
        List<User> batch = rows.parallelStream()
            .map(this::mapToUser)
            .filter(user -> user.getPhone().endsWith(suffix))
            .collect(Collectors.toList());
        
        results.addAll(batch);
        lastId = (Long) rows.get(rows.size() - 1).get("id");
    }
    
    return results.stream().limit(100).collect(Collectors.toList());
}
```

---

### 方案5：可搜索加密（SSE）

**原理**：使用确定性加密（Deterministic Encryption）。

```java
@Component
public class DeterministicEncryptor {
    
    /**
     * 确定性加密：相同明文 → 相同密文
     */
    public String encryptDeterministic(String plainText, String searchKey) {
        try {
            // 使用ECB模式（不推荐用于一般场景，但适合可搜索加密）
            Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
            SecretKeySpec keySpec = new SecretKeySpec(
                searchKey.getBytes(), "AES"
            );
            cipher.init(Cipher.ENCRYPT_MODE, keySpec);
            
            byte[] encrypted = cipher.doFinal(plainText.getBytes());
            return Base64.getEncoder().encodeToString(encrypted);
            
        } catch (Exception e) {
            throw new RuntimeException("加密失败", e);
        }
    }
    
    /**
     * 模糊查询实现
     */
    public List<User> searchByPhonePrefix(String prefix) {
        // 生成前缀的所有可能补全（如果可枚举）
        List<String> candidates = generateCandidates(prefix);
        
        // 对每个候选进行确定性加密
        List<String> encryptedCandidates = candidates.stream()
            .map(c -> encryptDeterministic(c, "search_key"))
            .collect(Collectors.toList());
        
        // 批量查询
        String sql = "SELECT * FROM users WHERE phone IN (" +
            encryptedCandidates.stream()
                .map(c -> "'" + c + "'")
                .collect(Collectors.joining(",")) +
            ")";
        
        return jdbcTemplate.query(sql, new UserRowMapper());
    }
    
    private List<String> generateCandidates(String prefix) {
        // 示例：13812 → 138120, 138121, ..., 138129, 1381200, ...
        // 实际场景需根据业务规则限制枚举范围
        return IntStream.range(0, 10000)
            .mapToObj(i -> prefix + String.format("%04d", i))
            .collect(Collectors.toList());
    }
}
```

**优势与劣势**：
- ✅ 支持等值查询
- ✅ 安全性较高
- ❌ 仍存在频率分析攻击风险
- ❌ 模糊查询需要枚举候选（开销大）

---

## 四、方案选型建议

### 场景1：手机号查询
**推荐方案**：部分加密 或 哈希映射表

```java
// 示例：保留前3位+后4位明文
String phone = "13812345678";
String stored = "138_" + encrypt("1234") + "_5678";

// 查询
SELECT * FROM users WHERE phone LIKE '138%' AND phone LIKE '%5678';
```

### 场景2：身份证号查询
**推荐方案**：部分加密（保留前6位地区码）

```sql
-- 存储格式：110101_encrypted_1234
SELECT * FROM users WHERE id_card LIKE '110101%';  -- 按地区查询
```

### 场景3：姓名模糊搜索
**推荐方案**：全文分词索引 + ElasticSearch

```java
// 1. 数据库存储加密数据
// 2. ES存储姓名哈希的分词
// 3. ES搜索 → 返回ID → 数据库查询 → 解密
```

### 场景4：地址模糊搜索
**推荐方案**：分级存储

```java
@Data
public class Address {
    private String province;   // 明文（可查询）
    private String city;       // 明文（可查询）
    private String district;   // 明文（可查询）
    private String detail;     // 加密（详细地址）
}

// 查询
SELECT * FROM addresses 
WHERE province = '北京' AND city = '海淀区'
AND detail LIKE ...;  // 应用层解密后过滤
```

### 场景5：极高安全要求
**推荐方案**：完全加密 + 应用层解密过滤

```java
// 不支持数据库层模糊查询
// 通过其他维度（时间、类型）缩小范围后，应用层解密过滤
public List<User> searchUsers(String keyword, Date startDate, Date endDate) {
    // 1. 按时间范围查询
    List<User> users = getUsersByDateRange(startDate, endDate);
    
    // 2. 应用层解密并过滤
    return users.stream()
        .map(this::decryptUser)
        .filter(user -> user.getName().contains(keyword) || 
                        user.getPhone().contains(keyword))
        .collect(Collectors.toList());
}
```

---

## 五、性能优化

### 1. 混合索引策略

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    phone_encrypted VARCHAR(500),   -- 完整加密
    phone_prefix CHAR(3),           -- 前缀明文（用于查询）
    phone_hash VARCHAR(100),        -- 完整哈希（用于精确匹配）
    
    INDEX idx_prefix (phone_prefix),
    INDEX idx_hash (phone_hash)
);
```

### 2. 缓存热点解密结果

```java
@Cacheable(value = "user_phone", key = "#userId", ttl = 300)
public String getDecryptedPhone(Long userId) {
    String encrypted = getEncryptedPhoneFromDb(userId);
    return aesEncryptor.decrypt(encrypted);
}
```

### 3. 异步预加载

```java
@Scheduled(fixedRate = 60000)
public void preloadFrequentData() {
    // 预加载热点数据并解密，缓存到Redis
    List<Long> hotUserIds = getHotUserIds();
    
    for (Long userId : hotUserIds) {
        User user = getUserAndDecrypt(userId);
        cacheService.set("user:" + userId, user, 600);
    }
}
```

---

## 六、答题总结

**面试回答框架**：

1. **问题识别**：  
   "加密后数据是密文，无法直接使用LIKE模糊查询。需要根据业务场景选择合适方案"

2. **常用方案**：  
   "手机号等结构化数据推荐部分加密，保留前3位明文用于前缀查询，中间部分加密；或使用哈希映射表，为常用前缀建立哈希索引"

3. **高安全方案**：  
   "若要求完全加密，可建立分词哈希索引表，查询时先从索引表找ID，再查主表解密；或应用层解密后过滤，适合小数据量"

4. **生产实践**：  
   "实际项目中手机号使用部分加密+前缀索引，姓名使用ES分词搜索+数据库存完整加密，兼顾安全和性能"

**关键点**：
- 理解加密与查询的矛盾
- 掌握部分加密、哈希映射等多种方案
- 能根据数据类型选择合适方案
- 强调安全性与性能的平衡

