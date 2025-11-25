---
title: "MyBatis 配置中的 #{} 与 ${} 有何区别？"
date: 2025-11-20 15:32:01 +0800
categories: [Java, MyBatis]
tags: [MyBatis, SQL注入, 预编译, 安全]
description: "详细对比 MyBatis 中 #{} 与 ${} 的区别，深入理解预编译原理、SQL 注入风险及实际使用场景。"
nav_order: 484
parent: Spring框架
---
## 一、核心概念

MyBatis 中的 `#{}` 和 `${}` 都是参数占位符，但**处理方式完全不同**：

- **`#{}`**：预编译占位符，使用 `PreparedStatement`，参数会经过预编译处理
- **`${}`**：字符串替换占位符，直接进行文本替换，存在 **SQL 注入风险**

## 二、原理与区别

### 1. #{} 预编译占位符

**原理**：使用 JDBC 的 `PreparedStatement` 进行预编译：

```xml
<!-- MyBatis SQL -->
<select id="findUserById" resultType="User">
    SELECT * FROM user WHERE id = #{id}
</select>
```

**底层执行流程**：

```java
// 1. MyBatis 生成预编译 SQL
String sql = "SELECT * FROM user WHERE id = ?";

// 2. 创建 PreparedStatement
PreparedStatement ps = connection.prepareStatement(sql);

// 3. 设置参数（自动类型转换）
ps.setInt(1, 123);  // 或 setString/setLong 等

// 4. 执行查询
ResultSet rs = ps.executeQuery();
```

**特点**：
- **参数类型安全**：自动进行类型转换和校验
- **防止 SQL 注入**：参数被视为纯数据，不会被解析为 SQL 语句
- **性能优化**：数据库可缓存执行计划，多次执行同一 SQL 时性能更好
- **自动处理特殊字符**：如单引号、双引号等会自动转义

### 2. ${} 字符串替换占位符

**原理**：直接进行字符串拼接：

```xml
<!-- MyBatis SQL -->
<select id="findUserByColumn" resultType="User">
    SELECT * FROM user ORDER BY ${columnName}
</select>
```

**底层执行流程**：

```java
// 假设传入参数 columnName = "name"

// 1. MyBatis 直接替换（字符串拼接）
String sql = "SELECT * FROM user ORDER BY " + columnName;
// 结果：SELECT * FROM user ORDER BY name

// 2. 创建 Statement（非预编译）
Statement stmt = connection.createStatement();

// 3. 执行 SQL
ResultSet rs = stmt.executeQuery(sql);
```

**特点**：
- **纯文本替换**：类似于字符串拼接，参数直接嵌入 SQL
- **存在 SQL 注入风险**：恶意参数可能改变 SQL 语义
- **无类型检查**：不会进行类型转换
- **无法利用预编译缓存**：每次生成的 SQL 可能不同

## 三、SQL 注入风险演示

### 危险示例（使用 ${}）

```xml
<!-- ❌ 危险：使用 ${} 接收用户输入 -->
<select id="findUserByName" resultType="User">
    SELECT * FROM user WHERE name = '${name}'
</select>
```

**攻击场景**：

```java
// 正常输入
userMapper.findUserByName("张三");
// 生成 SQL: SELECT * FROM user WHERE name = '张三'

// 恶意输入（SQL 注入）
userMapper.findUserByName("' OR '1'='1");
// 生成 SQL: SELECT * FROM user WHERE name = '' OR '1'='1'
// 结果：返回所有用户数据！

// 更危险的攻击
userMapper.findUserByName("'; DROP TABLE user; --");
// 生成 SQL: SELECT * FROM user WHERE name = ''; DROP TABLE user; --'
// 结果：删除整个 user 表！
```

### 安全示例（使用 #{}）

```xml
<!-- ✅ 安全：使用 #{} -->
<select id="findUserByName" resultType="User">
    SELECT * FROM user WHERE name = #{name}
</select>
```

**防注入效果**：

```java
// 恶意输入被当作普通字符串
userMapper.findUserByName("' OR '1'='1");

// 预编译 SQL: SELECT * FROM user WHERE name = ?
// 参数值: "' OR '1'='1"（整体作为字符串）
// 实际执行: SELECT * FROM user WHERE name = '\' OR \'1\'=\'1\''
// 结果：查不到数据，不会返回所有用户
```

## 四、使用场景

### 1. 必须使用 #{} 的场景（绝大多数）

```xml
<!-- ✅ WHERE 条件参数 -->
<select id="findUser" resultType="User">
    SELECT * FROM user WHERE id = #{id} AND status = #{status}
</select>

<!-- ✅ INSERT 参数 -->
<insert id="insertUser">
    INSERT INTO user (name, age, email) 
    VALUES (#{name}, #{age}, #{email})
</insert>

<!-- ✅ UPDATE 参数 -->
<update id="updateUser">
    UPDATE user SET name = #{name}, age = #{age} WHERE id = #{id}
</update>
```

### 2. 适合使用 ${} 的场景（需严格控制）

**仅在以下场景使用，且参数必须来自可信来源（如代码常量、白名单）**：

```xml
<!-- ✅ 动态表名（参数来自代码常量） -->
<select id="selectFromTable" resultType="Map">
    SELECT * FROM ${tableName} WHERE id = #{id}
</select>

<!-- ✅ 动态列名（参数来自预定义枚举） -->
<select id="selectByColumn" resultType="User">
    SELECT * FROM user ORDER BY ${orderColumn} ${orderDirection}
</select>

<!-- ✅ IN 子句（MyBatis 3.5+ 推荐用 foreach） -->
<select id="findUserByIds" resultType="User">
    SELECT * FROM user WHERE id IN (${ids})
</select>
```

**安全使用示例**：

```java
// ❌ 危险：直接接收用户输入
String tableName = request.getParameter("tableName");  // 用户可输入任意值
mapper.selectFromTable(tableName);

// ✅ 安全：使用白名单验证
enum AllowedTables {
    USER("user"), ORDER("order"), PRODUCT("product");
    private final String tableName;
}

String userInput = request.getParameter("tableName");
AllowedTables table = AllowedTables.valueOf(userInput.toUpperCase());
mapper.selectFromTable(table.getTableName());  // 只允许预定义的表名
```

### 3. MyBatis 3.5+ 推荐的替代方案

对于动态 IN 子句，推荐使用 `foreach`：

```xml
<!-- ✅ 推荐：使用 foreach 替代 ${} -->
<select id="findUserByIds" resultType="User">
    SELECT * FROM user WHERE id IN
    <foreach collection="ids" item="id" open="(" separator="," close=")">
        #{id}
    </foreach>
</select>
```

## 五、对比总结

| 对比项          | `#{}`                          | `${}`                       |
|-----------------|--------------------------------|-----------------------------|
| **处理方式**    | 预编译（PreparedStatement）    | 字符串替换（Statement）     |
| **SQL 注入**    | ✅ 安全（自动转义）            | ❌ 不安全（可被注入）       |
| **类型处理**    | ✅ 自动类型转换                | ❌ 无类型检查               |
| **性能**        | ✅ 可利用预编译缓存            | ❌ 每次都需解析 SQL         |
| **特殊字符**    | ✅ 自动转义（如单引号）        | ❌ 不转义                   |
| **使用场景**    | **所有参数值**（WHERE/INSERT 等）| **动态 SQL 结构**（表名/列名/关键字） |
| **推荐度**      | ⭐⭐⭐⭐⭐（默认首选）            | ⚠️ 谨慎使用（仅在必要时）   |

## 六、面试总结

**推荐回答思路**：

1. **先说核心区别**：`#{}` 是预编译占位符，`${}` 是字符串替换
2. **强调 SQL 注入风险**：`${}` 直接拼接，可能被注入；`#{}` 参数化查询，安全
3. **说明使用场景**：
   - `#{}`：所有参数值（WHERE 条件、INSERT/UPDATE 的值）
   - `${}`：动态 SQL 结构（表名、列名、ORDER BY），且需严格验证
4. **补充原理**：`#{}` 使用 PreparedStatement 预编译，`${}` 使用 Statement 拼接

**加分项**：
- 能举例说明 SQL 注入攻击（如 `' OR '1'='1`）
- 提到白名单验证、枚举限制等安全措施
- 了解 `foreach` 等 MyBatis 动态 SQL 标签
- 知道 `#{}` 底层使用 `PreparedStatement.setXxx()` 方法

**核心记忆点**：
> **能用 `#{}` 就用 `#{}`，必须用 `${}` 时务必验证参数来源（白名单/枚举/常量）！**
