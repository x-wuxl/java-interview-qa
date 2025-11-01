---
layout: post
title: "为什么建议多用组合少用继承？"
date: 2025-11-01
description: "深入剖析组合优于继承的设计原则、继承的缺陷、组合的优势及实际应用场景对比"
author: "wuxl"
categories: [Java基础]
tags: [组合, 继承, 设计原则, 面向对象, 代码复用]
---

## 问题

为什么建议多用组合少用继承？

## 答案

### 1. 核心原则

**"组合优于继承"（Composition Over Inheritance）**是《Effective Java》和《设计模式》中的重要原则。

**组合（Composition）**：通过包含其他对象来实现功能复用
```java
class Car {
    private Engine engine;  // 组合：汽车"有一个"引擎
}
```

**继承（Inheritance）**：通过extends继承父类来实现代码复用
```java
class SportsCar extends Car {  // 继承：跑车"是一个"汽车
}
```

### 2. 继承的问题

#### 问题1：打破封装性

```java
// 父类
public class InstrumentedHashSet<E> extends HashSet<E> {
    private int addCount = 0;

    @Override
    public boolean add(E e) {
        addCount++;
        return super.add(e);
    }

    @Override
    public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return super.addAll(c);  // 问题：内部调用add()
    }

    public int getAddCount() {
        return addCount;
    }
}

// 使用
InstrumentedHashSet<String> set = new InstrumentedHashSet<>();
set.addAll(Arrays.asList("A", "B", "C"));
System.out.println(set.getAddCount());  // 期望3，实际6！
```

**问题原因：**
- `HashSet.addAll()`内部调用`add()`
- 子类重写的`add()`被调用，导致重复计数
- **父类实现细节泄露给子类**

#### 问题2：脆弱的基类问题

```java
// 初始设计
public class Bird {
    public void fly() {
        System.out.println("Flying");
    }
}

public class Penguin extends Bird {
    // 企鹅是鸟，但不会飞！
    @Override
    public void fly() {
        throw new UnsupportedOperationException("Penguins can't fly");
    }
}
```

**问题：**违反里氏替换原则（LSP），父类引用无法被子类安全替换

#### 问题3：强耦合

```java
// 父类修改影响所有子类
public class Employee {
    private double salary;

    public double getSalary() {
        return salary;
    }

    // 新增方法
    public double getBonus() {
        return salary * 0.1;  // 默认10%奖金
    }
}

// 子类被迫继承不需要的方法
public class Intern extends Employee {
    // 实习生没有奖金，但继承了getBonus()方法
    @Override
    public double getBonus() {
        return 0;  // 被迫重写
    }
}
```

#### 问题4：违反单一职责原则

```java
// 继承导致类承担多个职责
public class Stack<E> extends Vector<E> {
    // Stack继承了Vector的所有方法
    // 可以从中间插入元素，破坏栈的LIFO语义
}

Stack<String> stack = new Stack<>();
stack.push("A");
stack.add(0, "B");  // 破坏栈结构！
```

### 3. 组合的优势

#### 用组合重写InstrumentedHashSet

```java
public class InstrumentedSet<E> {
    private final Set<E> set;  // 组合：持有Set引用
    private int addCount = 0;

    public InstrumentedSet(Set<E> set) {
        this.set = set;
    }

    public boolean add(E e) {
        addCount++;
        return set.add(e);
    }

    public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return set.addAll(c);  // 委托给内部set
    }

    public int getAddCount() {
        return addCount;
    }

    // 委托其他方法
    public int size() {
        return set.size();
    }
}

// 使用
Set<String> hashSet = new HashSet<>();
InstrumentedSet<String> set = new InstrumentedSet<>(hashSet);
set.addAll(Arrays.asList("A", "B", "C"));
System.out.println(set.getAddCount());  // 正确：3
```

**优势：**
- 不依赖父类实现细节
- 可以灵活替换内部Set实现（HashSet、TreeSet等）
- 只暴露需要的方法

#### 用组合解决Bird问题

```java
// 将"飞行能力"定义为接口
public interface Flyable {
    void fly();
}

// 飞行能力的实现
public class Flight implements Flyable {
    @Override
    public void fly() {
        System.out.println("Flying");
    }
}

// 鸟类通过组合获得能力
public class Bird {
    private Flyable flyBehavior;  // 组合

    public Bird(Flyable flyBehavior) {
        this.flyBehavior = flyBehavior;
    }

    public void performFly() {
        if (flyBehavior != null) {
            flyBehavior.fly();
        } else {
            System.out.println("Cannot fly");
        }
    }
}

// 使用
Bird eagle = new Bird(new Flight());     // 老鹰会飞
Bird penguin = new Bird(null);           // 企鹅不会飞
```

### 4. 组合vs继承对比

| 维度 | 继承 | 组合 |
|------|------|------|
| **关系** | Is-A（是一个） | Has-A（有一个） |
| **耦合度** | 强耦合（白盒复用） | 弱耦合（黑盒复用） |
| **灵活性** | 编译期确定，无法运行时改变 | 运行时可动态组合 |
| **封装性** | 打破封装（需了解父类） | 保持封装（只需接口） |
| **复用性** | 垂直复用（类层次） | 水平复用（功能组合） |
| **维护性** | 父类变化影响所有子类 | 内部变化不影响外部 |

### 5. 适合继承的场景

继承并非一无是处，以下场景适合使用继承：

#### 场景1：明确的Is-A关系

```java
// 清晰的分类层次
public abstract class Shape {
    public abstract double area();
}

public class Circle extends Shape {
    private double radius;

    @Override
    public double area() {
        return Math.PI * radius * radius;
    }
}

public class Rectangle extends Shape {
    private double width, height;

    @Override
    public double area() {
        return width * height;
    }
}
```

**判断标准：**子类能完全替代父类（里氏替换原则）

#### 场景2：扩展功能而非修改行为

```java
// JDK中的例子
public class Properties extends Hashtable<Object, Object> {
    // 扩展：提供load/store等文件操作
    public void load(InputStream in) throws IOException {
        // ...
    }
}
```

#### 场景3：框架设计中的模板方法

```java
public abstract class HttpServlet {
    public final void service(HttpRequest req, HttpResponse res) {
        if ("GET".equals(req.getMethod())) {
            doGet(req, res);
        }
    }

    protected abstract void doGet(HttpRequest req, HttpResponse res);
}
```

### 6. 实际应用案例

#### 案例1：装饰器模式（组合）

```java
// InputStream家族使用组合而非继承
InputStream in = new BufferedInputStream(
    new FileInputStream("file.txt")
);

// 等价于组合结构
class BufferedInputStream {
    private InputStream in;  // 组合

    public BufferedInputStream(InputStream in) {
        this.in = in;
    }

    public int read() {
        // 增强功能：添加缓冲
        return in.read();
    }
}
```

#### 案例2：策略模式（组合）

```java
// 支付方式通过组合切换，而非继承
public class Order {
    private PaymentStrategy paymentStrategy;  // 组合

    public void setPaymentStrategy(PaymentStrategy strategy) {
        this.paymentStrategy = strategy;
    }

    public void pay(double amount) {
        paymentStrategy.pay(amount);
    }
}

// 运行时切换策略
Order order = new Order();
order.setPaymentStrategy(new AlipayStrategy());
order.pay(100);

order.setPaymentStrategy(new WeChatPayStrategy());
order.pay(200);
```

#### 案例3：Spring框架设计

```java
// Spring使用组合注入依赖
@Service
public class UserService {
    private final UserRepository userRepository;  // 组合
    private final EmailService emailService;      // 组合

    @Autowired
    public UserService(UserRepository userRepository, EmailService emailService) {
        this.userRepository = userRepository;
        this.emailService = emailService;
    }
}
```

### 7. 组合的实现模式

#### 模式1：委托（Delegation）

```java
public class ForwardingSet<E> implements Set<E> {
    private final Set<E> s;  // 组合

    public ForwardingSet(Set<E> s) {
        this.s = s;
    }

    // 委托所有方法
    public boolean add(E e) { return s.add(e); }
    public boolean remove(Object o) { return s.remove(o); }
    public int size() { return s.size(); }
    // ...
}
```

#### 模式2：适配器（Adapter）

```java
// 将旧接口适配为新接口
public class LegacyRectangle {
    public void draw(int x1, int y1, int x2, int y2) { }
}

public class RectangleAdapter implements Shape {
    private LegacyRectangle rectangle;  // 组合

    public RectangleAdapter(LegacyRectangle rectangle) {
        this.rectangle = rectangle;
    }

    @Override
    public void draw() {
        rectangle.draw(0, 0, 10, 10);
    }
}
```

### 8. 最佳实践

#### ✅ 推荐做法

```java
// 1. 优先使用接口 + 组合
public interface Engine {
    void start();
}

public class Car {
    private Engine engine;  // 组合接口

    public void start() {
        engine.start();  // 委托
    }
}

// 2. 使用抽象类时，提供钩子方法而非强制继承
public abstract class AbstractProcessor {
    public final void process() {
        beforeProcess();
        doProcess();
        afterProcess();
    }

    protected void beforeProcess() { }  // 可选钩子
    protected abstract void doProcess();
    protected void afterProcess() { }   // 可选钩子
}

// 3. 继承时确保Is-A关系成立
public class Dog extends Animal {  // 狗是动物 ✅
}
```

#### ❌ 避免做法

```java
// 1. 为了复用代码而继承
public class Utils extends ArrayList {  // ❌ Utils不是ArrayList
    public static void log(String msg) { }
}

// 2. 继承具体类（应继承抽象类或实现接口）
public class MyHashMap extends HashMap {  // ⚠️ 脆弱
}

// 3. 违反里氏替换原则
public class Square extends Rectangle {  // ❌ 正方形不能替换矩形
    @Override
    public void setWidth(int width) {
        super.setWidth(width);
        super.setHeight(width);  // 改变了Rectangle的行为
    }
}
```

### 9. 决策流程

```
是否是真正的Is-A关系？
  ├─ 否 → 使用组合
  └─ 是 ↓

子类能否完全替代父类？（LSP）
  ├─ 否 → 使用组合
  └─ 是 ↓

是否需要访问父类的protected成员？
  ├─ 是 → 可以使用继承
  └─ 否 → 优先使用组合

是否需要运行时动态改变行为？
  ├─ 是 → 必须使用组合
  └─ 否 → 可以使用继承
```

### 10. 面试答题要点

**标准回答结构：**

1. **核心原则**：组合优于继承，提供更好的灵活性和封装性

2. **继承的问题**：
   - 打破封装性（依赖父类实现细节）
   - 脆弱的基类问题（父类变化影响子类）
   - 强耦合，难以维护

3. **组合的优势**：
   - 低耦合，黑盒复用
   - 运行时动态组合
   - 保持封装性

4. **使用场景**：
   - 继承：明确的Is-A关系，符合LSP
   - 组合：Has-A关系，需要灵活性

5. **实际案例**：装饰器模式、策略模式、Spring依赖注入

**加分点：**
- 说明里氏替换原则（LSP）
- 举例JDK中的应用（InputStream、Collections）
- 了解设计模式中的应用
- 知道何时应该使用继承

### 11. 总结

**记忆口诀：**
- 继承是is-a，组合是has-a
- 继承看类型，组合看功能
- 继承强耦合，组合更灵活
- 优先组合，谨慎继承

**核心要点：**
- 继承适合：稳定的类层次，真正的Is-A关系
- 组合适合：功能复用，运行时灵活性
- 大多数情况下，组合比继承更好
- 不排斥继承，但要慎重使用

**实践建议：**
1. 默认使用组合
2. 只在确定是Is-A关系时使用继承
3. 多使用接口，少用具体类继承
4. 优先考虑设计模式中的组合方案
