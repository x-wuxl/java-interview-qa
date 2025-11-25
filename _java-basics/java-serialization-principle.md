---
title: "Java序列化的原理是什么"
date: 2025-11-01
description: "深入剖析Java序列化的底层机制、实现原理及源码关键点"
author: "wuxl"
categories: [Java基础]
tags: [序列化, ObjectOutputStream, 源码分析]
nav_order: 65
parent: Java基础
---
## 问题

Java序列化的原理是啥？

## 答案

### 核心机制

Java序列化通过 `ObjectOutputStream` 和 `ObjectInputStream` 实现，基于**反射机制**和**特定协议格式**将对象状态转换为字节流。

### 实现原理

#### 1. 序列化过程

```java
// 1. 创建输出流
ObjectOutputStream oos = new ObjectOutputStream(new FileOutputStream("obj.ser"));

// 2. 写入对象
oos.writeObject(user);
```

**内部执行流程**：

1. **检查接口**：验证对象是否实现 `Serializable` 或 `Externalizable`
2. **写入元数据**：写入序列化协议魔数（`0xACED`）、版本号（`0x0005`）
3. **写入类描述符**：
   - 类名
   - `serialVersionUID`
   - 字段描述信息（字段名、类型）
4. **写入对象数据**：
   - 遍历对象的非 `transient`、非 `static` 字段
   - 递归序列化引用类型字段
   - 处理父类字段（如果父类可序列化）

#### 2. 关键源码分析

```java
// ObjectOutputStream.writeObject() 核心逻辑
public final void writeObject(Object obj) throws IOException {
    // 1. 检查对象是否为null
    if (obj == null) {
        writeNull();
        return;
    }

    // 2. 检查是否已序列化（处理循环引用）
    if (handles.lookup(obj) != -1) {
        writeHandle(handles.lookup(obj));
        return;
    }

    // 3. 检查是否实现Serializable
    Class<?> cl = obj.getClass();
    ObjectStreamClass desc = ObjectStreamClass.lookup(cl, true);
    if (desc == null) {
        throw new NotSerializableException(cl.getName());
    }

    // 4. 写入类描述符
    writeClassDesc(desc, false);

    // 5. 写入对象数据
    writeOrdinaryObject(obj, desc, false);
}
```

#### 3. 自定义序列化

可以通过以下方法控制序列化行为：

```java
public class User implements Serializable {
    private static final long serialVersionUID = 1L;

    private String username;
    private String password;

    // 自定义序列化逻辑
    private void writeObject(ObjectOutputStream oos) throws IOException {
        oos.defaultWriteObject(); // 先执行默认序列化

        // 加密密码后再写入
        String encryptedPassword = encrypt(password);
        oos.writeObject(encryptedPassword);
    }

    // 自定义反序列化逻辑
    private void readObject(ObjectInputStream ois)
            throws IOException, ClassNotFoundException {
        ois.defaultReadObject(); // 先执行默认反序列化

        // 读取并解密密码
        String encryptedPassword = (String) ois.readObject();
        this.password = decrypt(encryptedPassword);
    }

    // 控制序列化时替换对象
    private Object writeReplace() throws ObjectStreamException {
        return new UserProxy(this);
    }

    // 控制反序列化时解析对象
    private Object readResolve() throws ObjectStreamException {
        return this; // 可用于实现单例模式
    }
}
```

### 序列化协议格式

```
STREAM_MAGIC (魔数)     : 0xACED
STREAM_VERSION (版本)   : 0x0005
TC_OBJECT (对象标识)    : 0x73
TC_CLASSDESC (类描述)   : 0x72
  类名长度 + 类名
  serialVersionUID (8字节)
  字段数量
  字段描述 (类型 + 名称)
TC_ENDBLOCKDATA         : 0x78
对象数据 (按字段顺序)
```

### 性能与安全考量

#### 性能问题

1. **反射开销**：频繁使用反射获取字段信息
2. **元数据冗余**：每次都写入完整类描述符
3. **不支持跨语言**：协议仅Java专用

**优化建议**：
- 使用 `Externalizable` 接口完全自定义序列化
- 使用高性能框架（Kryo、FST）
- 标记不必要字段为 `transient`

#### 安全问题

1. **反序列化漏洞**：恶意构造对象触发代码执行
2. **数据篡改**：字节流可被拦截修改

**防护措施**：
```java
// 使用ObjectInputFilter过滤危险类
ObjectInputStream ois = new ObjectInputStream(fis);
ois.setObjectInputFilter(info -> {
    if (info.serialClass() != null) {
        // 只允许白名单类
        return info.serialClass() == User.class
            ? ObjectInputFilter.Status.ALLOWED
            : ObjectInputFilter.Status.REJECTED;
    }
    return ObjectInputFilter.Status.UNDECIDED;
});
```

### 答题总结

Java序列化通过 `ObjectOutputStream` 基于**反射机制**读取对象字段，按照特定协议格式（魔数+类描述符+对象数据）写入字节流。可通过 `writeObject/readObject` 方法自定义序列化逻辑。关键要注意**性能开销**（反射、元数据冗余）和**安全风险**（反序列化漏洞），生产环境建议使用JSON或Protobuf等更安全高效的方案。
