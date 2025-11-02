---
layout: post
title: "数据库怎么做加密和解密？"
date: 2025-11-02
categories: [MySQL, 数据安全]
tags: [MySQL, 数据加密, 敏感数据, 安全, AES]
description: "全面解析数据库加密解密方案，包括字段级加密、透明加密、应用层加密等，以及性能优化与合规要求"
---

## 一、加密需求与场景

### 典型敏感数据
- **用户隐私**：身份证号、手机号、邮箱、地址
- **支付信息**：银行卡号、CVV、支付密码
- **医疗数据**：病历、检查报告
- **商业机密**：客户资料、合同金额

### 合规要求
- **GDPR**（欧盟）：个人数据保护
- **HIPAA**（美国医疗）：医疗数据安全
- **PCI DSS**（支付卡行业）：持卡人数据保护
- **等保2.0**（中国）：三级以上要求敏感数据加密

## 二、加密方案分类

### 1. 应用层加密（推荐）

#### 方案A：对称加密（AES）

```java
@Component
public class AESEncryptor {
    
    private static final String ALGORITHM = "AES/CBC/PKCS5Padding";
    private static final String KEY_ALGORITHM = "AES";
    
    @Value("${encryption.secret.key}")
    private String secretKey;  // 从配置中心读取，不硬编码
    
    @Value("${encryption.iv}")
    private String iv;  // 初始化向量
    
    /**
     * 加密
     */
    public String encrypt(String plainText) {
        try {
            SecretKeySpec keySpec = new SecretKeySpec(
                secretKey.getBytes(StandardCharsets.UTF_8), 
                KEY_ALGORITHM
            );
            
            IvParameterSpec ivSpec = new IvParameterSpec(
                iv.getBytes(StandardCharsets.UTF_8)
            );
            
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, ivSpec);
            
            byte[] encrypted = cipher.doFinal(
                plainText.getBytes(StandardCharsets.UTF_8)
            );
            
            // Base64编码，方便存储
            return Base64.getEncoder().encodeToString(encrypted);
            
        } catch (Exception e) {
            throw new RuntimeException("加密失败", e);
        }
    }
    
    /**
     * 解密
     */
    public String decrypt(String encryptedText) {
        try {
            SecretKeySpec keySpec = new SecretKeySpec(
                secretKey.getBytes(StandardCharsets.UTF_8), 
                KEY_ALGORITHM
            );
            
            IvParameterSpec ivSpec = new IvParameterSpec(
                iv.getBytes(StandardCharsets.UTF_8)
            );
            
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.DECRYPT_MODE, keySpec, ivSpec);
            
            byte[] decoded = Base64.getDecoder().decode(encryptedText);
            byte[] decrypted = cipher.doFinal(decoded);
            
            return new String(decrypted, StandardCharsets.UTF_8);
            
        } catch (Exception e) {
            throw new RuntimeException("解密失败", e);
        }
    }
}
```

**使用示例**：
```java
@Service
public class UserService {
    
    @Autowired
    private AESEncryptor encryptor;
    
    @Autowired
    private JdbcTemplate jdbcTemplate;
    
    public void saveUser(User user) {
        // 加密敏感字段
        String encryptedIdCard = encryptor.encrypt(user.getIdCard());
        String encryptedPhone = encryptor.encrypt(user.getPhone());
        
        jdbcTemplate.update(
            "INSERT INTO users (name, id_card, phone) VALUES (?, ?, ?)",
            user.getName(), encryptedIdCard, encryptedPhone
        );
    }
    
    public User getUser(Long id) {
        Map<String, Object> row = jdbcTemplate.queryForMap(
            "SELECT * FROM users WHERE id = ?", id
        );
        
        User user = new User();
        user.setId((Long) row.get("id"));
        user.setName((String) row.get("name"));
        
        // 解密敏感字段
        user.setIdCard(encryptor.decrypt((String) row.get("id_card")));
        user.setPhone(encryptor.decrypt((String) row.get("phone")));
        
        return user;
    }
}
```

**表结构**：
```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    id_card VARCHAR(500),    -- 加密后长度增加，需预留空间
    phone VARCHAR(500),
    create_time DATETIME
);
```

**优势**：
- ✅ 灵活性高，业务完全可控
- ✅ 支持密钥轮换
- ✅ 可选择性加密字段
- ✅ 跨数据库兼容

**劣势**：
- ❌ 加密后无法使用索引查询
- ❌ 无法使用LIKE模糊查询
- ❌ 应用层性能开销

---

#### 方案B：非对称加密（RSA）

```java
@Component
public class RSAEncryptor {
    
    private PrivateKey privateKey;
    private PublicKey publicKey;
    
    @PostConstruct
    public void init() throws Exception {
        // 从配置中心或密钥管理服务获取密钥对
        KeyPairGenerator keyGen = KeyPairGenerator.getInstance("RSA");
        keyGen.initialize(2048);
        KeyPair keyPair = keyGen.generateKeyPair();
        
        this.privateKey = keyPair.getPrivate();
        this.publicKey = keyPair.getPublic();
    }
    
    /**
     * 公钥加密（前端/客户端使用）
     */
    public String encryptByPublicKey(String plainText) throws Exception {
        Cipher cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding");
        cipher.init(Cipher.ENCRYPT_MODE, publicKey);
        
        byte[] encrypted = cipher.doFinal(
            plainText.getBytes(StandardCharsets.UTF_8)
        );
        
        return Base64.getEncoder().encodeToString(encrypted);
    }
    
    /**
     * 私钥解密（后端使用）
     */
    public String decryptByPrivateKey(String encryptedText) throws Exception {
        Cipher cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding");
        cipher.init(Cipher.DECRYPT_MODE, privateKey);
        
        byte[] decoded = Base64.getDecoder().decode(encryptedText);
        byte[] decrypted = cipher.doFinal(decoded);
        
        return new String(decrypted, StandardCharsets.UTF_8);
    }
}
```

**使用场景**：
- 客户端提交敏感数据时加密传输
- 后端解密后再用AES加密存储

**注意**：RSA加密性能较差，不适合大量数据加密。

---

### 2. 数据库内置加密函数

#### MySQL自带加密函数

```sql
-- AES加密
INSERT INTO users (name, id_card) 
VALUES ('张三', AES_ENCRYPT('110101199001011234', 'secret_key_123'));

-- AES解密
SELECT 
    id,
    name,
    CAST(AES_DECRYPT(id_card, 'secret_key_123') AS CHAR) AS id_card
FROM users
WHERE id = 1;
```

**问题**：
- ❌ 密钥硬编码在SQL中（安全风险）
- ❌ 每次查询都需要调用解密函数（性能差）
- ❌ 密钥轮换困难

**改进方案**：结合用户变量
```sql
SET @key = 'secret_key_from_app';

SELECT 
    id,
    name,
    CAST(AES_DECRYPT(id_card, @key) AS CHAR) AS id_card
FROM users;
```

---

### 3. 透明数据加密（TDE）

#### MySQL TDE配置

```sql
-- 1. 启用TDE（需要MySQL企业版或Percona/MariaDB）
-- 编辑 my.cnf
[mysqld]
early-plugin-load=keyring_file.so
keyring_file_data=/var/lib/mysql-keyring/keyring

-- 2. 创建加密表空间
CREATE TABLESPACE encrypted_space
ADD DATAFILE 'encrypted_space.ibd'
ENCRYPTION='Y';

-- 3. 创建加密表
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    id_card VARCHAR(100),
    phone VARCHAR(50)
) TABLESPACE encrypted_space
ENCRYPTION='Y';

-- 或对已有表开启加密
ALTER TABLE users ENCRYPTION='Y';
```

**TDE原理**：
```
数据写入流程：
用户数据 → InnoDB Buffer Pool → 加密（Master Key + Table Key）→ 写入磁盘

数据读取流程：
磁盘数据 → 解密 → InnoDB Buffer Pool → 返回明文给应用
```

**优势**：
- ✅ 对应用透明，无需改代码
- ✅ 保护磁盘数据（防止物理盗取）
- ✅ 支持索引查询
- ✅ 性能损耗小（5-10%）

**劣势**：
- ❌ 需要企业版或特定发行版
- ❌ 只保护静态数据（data-at-rest），不保护传输和内存
- ❌ 数据库备份文件需单独加密

---

### 4. 列级加密（MySQL 8.0企业版）

```sql
-- 创建加密列
CREATE TABLE credit_cards (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    card_number VARBINARY(500),  -- 存储加密数据
    KEY idx_user (user_id)
);

-- 插入时加密
INSERT INTO credit_cards (user_id, card_number)
VALUES (1001, AES_ENCRYPT('6222021234567890', UNHEX(SHA2('master_key', 256))));

-- 查询时解密
SELECT 
    id,
    user_id,
    CAST(AES_DECRYPT(card_number, UNHEX(SHA2('master_key', 256))) AS CHAR) AS card_number
FROM credit_cards
WHERE user_id = 1001;
```

---

### 5. 应用层+MyBatis拦截器（自动化）

```java
@Intercepts({
    @Signature(
        type = ParameterHandler.class,
        method = "setParameters",
        args = {PreparedStatement.class}
    )
})
public class EncryptionInterceptor implements Interceptor {
    
    @Autowired
    private AESEncryptor encryptor;
    
    @Override
    public Object intercept(Invocation invocation) throws Throwable {
        ParameterHandler parameterHandler = (ParameterHandler) invocation.getTarget();
        
        // 获取参数对象
        Object parameterObject = parameterHandler.getParameterObject();
        
        if (parameterObject != null) {
            // 反射处理带@Encrypted注解的字段
            Class<?> clazz = parameterObject.getClass();
            for (Field field : clazz.getDeclaredFields()) {
                if (field.isAnnotationPresent(Encrypted.class)) {
                    field.setAccessible(true);
                    Object value = field.get(parameterObject);
                    
                    if (value instanceof String) {
                        String encrypted = encryptor.encrypt((String) value);
                        field.set(parameterObject, encrypted);
                    }
                }
            }
        }
        
        return invocation.proceed();
    }
}

// 自定义注解
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.FIELD)
public @interface Encrypted {
}
```

**实体类使用**：
```java
@Data
public class User {
    private Long id;
    private String name;
    
    @Encrypted  // 自动加密
    private String idCard;
    
    @Encrypted  // 自动加密
    private String phone;
}
```

---

## 三、密钥管理

### 1. 密钥存储方案

#### 方案A：配置中心（Apollo/Nacos）
```yaml
# Apollo配置
encryption:
  aes:
    key: ${AES_SECRET_KEY}  # 占位符，实际值在配置中心
    iv: ${AES_IV}
```

**安全措施**：
- 配置中心开启访问控制
- 密钥配置设置为"敏感信息"不可见
- 审计密钥访问日志

---

#### 方案B：专业密钥管理服务（KMS）

```java
@Component
public class KMSEncryptor {
    
    @Autowired
    private AWSKMSClient kmsClient;
    
    @Value("${kms.key.id}")
    private String keyId;
    
    public String encrypt(String plainText) {
        EncryptRequest request = new EncryptRequest()
            .withKeyId(keyId)
            .withPlaintext(ByteBuffer.wrap(plainText.getBytes()));
        
        EncryptResult result = kmsClient.encrypt(request);
        return Base64.getEncoder().encodeToString(
            result.getCiphertextBlob().array()
        );
    }
    
    public String decrypt(String encryptedText) {
        DecryptRequest request = new DecryptRequest()
            .withCiphertextBlob(ByteBuffer.wrap(
                Base64.getDecoder().decode(encryptedText)
            ));
        
        DecryptResult result = kmsClient.decrypt(request);
        return new String(result.getPlaintext().array());
    }
}
```

**支持的KMS服务**：
- AWS KMS
- Azure Key Vault
- 阿里云KMS
- 腾讯云KMS
- HashiCorp Vault

---

### 2. 密钥轮换策略

```java
@Component
public class KeyRotationManager {
    
    private static final String CURRENT_KEY_VERSION = "v2";
    
    @Autowired
    private Map<String, AESEncryptor> encryptorMap;  // key版本 -> 加密器
    
    /**
     * 加密时始终使用最新密钥
     */
    public String encrypt(String plainText) {
        AESEncryptor currentEncryptor = encryptorMap.get(CURRENT_KEY_VERSION);
        return CURRENT_KEY_VERSION + ":" + currentEncryptor.encrypt(plainText);
    }
    
    /**
     * 解密时根据版本号选择密钥
     */
    public String decrypt(String encryptedText) {
        String[] parts = encryptedText.split(":", 2);
        String version = parts[0];
        String cipherText = parts[1];
        
        AESEncryptor encryptor = encryptorMap.get(version);
        if (encryptor == null) {
            throw new RuntimeException("密钥版本不存在: " + version);
        }
        
        return encryptor.decrypt(cipherText);
    }
    
    /**
     * 批量重新加密（密钥轮换后）
     */
    @Scheduled(cron = "0 0 3 * * ?")
    public void reEncryptOldData() {
        Long lastId = 0L;
        int batchSize = 1000;
        
        while (true) {
            List<User> users = jdbcTemplate.query(
                "SELECT * FROM users WHERE id > ? AND id_card LIKE 'v1:%' LIMIT ?",
                new UserRowMapper(), lastId, batchSize
            );
            
            if (users.isEmpty()) {
                break;
            }
            
            for (User user : users) {
                // 用旧密钥解密
                String plainText = decryptWithOldKey(user.getIdCard());
                
                // 用新密钥加密
                String newEncrypted = encrypt(plainText);
                
                // 更新数据库
                jdbcTemplate.update(
                    "UPDATE users SET id_card = ? WHERE id = ?",
                    newEncrypted, user.getId()
                );
            }
            
            lastId = users.get(users.size() - 1).getId();
        }
    }
}
```

---

## 四、性能优化

### 1. 批量加解密

```java
public List<User> getUsersBatch(List<Long> ids) {
    // 1. 批量查询
    List<Map<String, Object>> rows = jdbcTemplate.queryForList(
        "SELECT * FROM users WHERE id IN (" + 
        ids.stream().map(String::valueOf).collect(Collectors.joining(",")) + ")"
    );
    
    // 2. 批量解密（并行处理）
    return rows.parallelStream()
        .map(row -> {
            User user = new User();
            user.setId((Long) row.get("id"));
            user.setName((String) row.get("name"));
            user.setIdCard(encryptor.decrypt((String) row.get("id_card")));
            user.setPhone(encryptor.decrypt((String) row.get("phone")));
            return user;
        })
        .collect(Collectors.toList());
}
```

### 2. 分级加密

```java
// 不同敏感级别使用不同策略
public class SensitiveDataHandler {
    
    // 高敏感：银行卡号 → 强加密（RSA）
    public String encryptHighSensitive(String data) {
        return rsaEncryptor.encrypt(data);
    }
    
    // 中敏感：手机号 → AES加密
    public String encryptMediumSensitive(String data) {
        return aesEncryptor.encrypt(data);
    }
    
    // 低敏感：地址 → 仅脱敏显示，不加密存储
    public String maskLowSensitive(String data) {
        return data.substring(0, 5) + "****";
    }
}
```

### 3. 缓存解密结果

```java
@Service
public class UserServiceWithCache {
    
    @Cacheable(value = "user_cache", key = "#id")
    public User getUserDecrypted(Long id) {
        // 解密后的结果缓存到Redis（注意设置过期时间）
        Map<String, Object> row = jdbcTemplate.queryForMap(
            "SELECT * FROM users WHERE id = ?", id
        );
        
        User user = new User();
        user.setId(id);
        user.setIdCard(encryptor.decrypt((String) row.get("id_card")));
        // ...
        
        return user;
    }
}
```

**注意**：缓存敏感数据需评估安全风险。

---

## 五、答题总结

**面试回答框架**：

1. **方案选择**：  
   "生产环境推荐应用层加密，使用AES对称加密，密钥存储在配置中心或KMS服务。对性能要求高的场景可选择MySQL TDE透明加密，但需要企业版"

2. **实现细节**：  
   "应用层在插入前加密、查询后解密，使用AES/CBC/PKCS5Padding模式，密文Base64编码存储。表字段长度需预留（如VARCHAR(500)），因为加密后长度增加"

3. **密钥管理**：  
   "密钥不能硬编码，应存储在配置中心并限制访问权限。支持密钥轮换，加密时带版本号（如v2:密文），解密时根据版本选择对应密钥"

4. **注意事项**：  
   "加密字段无法建索引查询，需要额外设计；LIKE模糊查询不支持，需要特殊方案；高并发场景要注意加解密性能开销，可使用批量处理和并行解密优化"

**关键点**：
- 理解应用层加密 vs 数据库TDE的差异
- 掌握AES加密的完整流程
- 强调密钥管理的重要性
- 知道加密对查询和性能的影响

