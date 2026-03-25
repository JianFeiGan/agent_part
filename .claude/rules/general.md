# 通用开发规则

## 1. 代码规范与质量标准

### 1.1 基本准则
- 遵循 SOLID 原则，确保代码高内聚、低耦合
- 优先使用组合而非继承
- 避免魔法数字和硬编码字符串，使用常量或枚举
- 每个类、方法、字段必须添加 JavaDoc 注释

### 1.2 命名规范
| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | 大驼峰，名词 | `EmployeeService`, `OrderController` |
| 接口名 | 大驼峰，形容词/名词 | `UserRepository`, `Serializable` |
| 方法名 | 小驼峰，动词开头 | `getUserById()`, `validateOrder()` |
| 常量 | 全大写，下划线分隔 | `MAX_RETRY_COUNT`, `DEFAULT_PAGE_SIZE` |
| 包名 | 全小写，点分隔 | `com.ux168.pa.application.sms.biz` |
| 变量名 | 小驼峰，有意义 | `employeeList`, `orderDetail` |

### 1.3 代码格式
- 缩进：4 个空格（禁止使用 Tab）
- 行长度：最大 120 个字符
- 大括号：K&R 风格，左括号不换行
- 空行：类/方法之间留一个空行，逻辑块之间适当留白

## 2. 项目结构规范

### 2.1 模块命名
```
pa-{biz}-application     # 应用层模块
pa-{biz}-service         # 服务层模块
```

### 2.2 包结构
```
com.ux168.pa.application.{module}.biz/
├── config/              # 配置类
├── constant/            # 常量定义
├── controller/          # REST 控制器
├── dto/                 # 数据传输对象
│   ├── request/         # 请求 DTO
│   └── response/        # 响应 DTO
├── entity/              # 实体类
├── enums/               # 枚举类
├── exception/           # 自定义异常
├── job/                 # XXL-JOB 任务
├── mapper/              # MyBatis Mapper
├── service/             # 业务逻辑接口
│   └── impl/            # 业务逻辑实现
├── util/                # 工具类
└── vo/                  # 视图对象
```

## 3. 异常处理规范

### 3.1 异常分类
- **业务异常** (`BusinessException`): 可预期的业务错误，返回 200 状态码
- **系统异常** (`SystemException`): 不可预期的系统错误，返回 500 状态码
- **参数异常** (`ValidationException`): 参数校验失败，返回 400 状态码

### 3.2 异常处理原则
- 禁止捕获异常后什么都不做
- 禁止在 finally 块中使用 return
- 异常信息必须包含上下文（如："用户ID: 12345 不存在"）
- 使用 try-with-resources 自动关闭资源

## 4. 日志规范

### 4.1 日志级别使用
| 级别 | 使用场景 |
|------|----------|
| ERROR | 系统错误、需要立即处理的异常 |
| WARN | 潜在问题、可恢复的错误 |
| INFO | 关键业务流程节点、状态变更 |
| DEBUG | 调试信息、详细流程追踪 |
| TRACE | 最详细的追踪信息 |

### 4.2 日志规范
- 使用 SLF4J 接口：`private static final Logger log = LoggerFactory.getLogger(Xxx.class);`
- 禁止在生产环境使用 `System.out.println()`
- 敏感信息（密码、手机号）必须脱敏后输出
- 异常日志必须包含完整堆栈：`log.error("操作失败", exception);`

## 5. 安全规范

### 5.1 输入校验
- 所有外部输入必须进行校验（长度、类型、范围）
- 使用 JSR-303/380 注解进行参数校验
- SQL 注入防护：使用 MyBatis 参数绑定，禁止字符串拼接 SQL

### 5.2 敏感数据处理
- 密码必须使用 BCrypt 等强哈希算法
- Token 必须设置过期时间
- 接口权限必须使用注解控制（@PreAuthorize）

## 6. 性能规范

### 6.1 数据库访问
- 禁止在循环中执行 SQL（N+1 问题）
- 大批量操作使用批处理（batch size 建议 500-1000）
- 慢查询必须添加索引并优化

### 6.2 缓存使用
- 缓存必须设置过期时间
- 缓存 key 必须规范命名：`{模块}:{业务}:{标识}`
- 缓存更新必须保证最终一致性

### 6.3 并发处理
- 优先使用并发集合（ConcurrentHashMap 等）
- 锁粒度尽量小，避免大范围锁定
- 使用 ThreadLocal 时注意内存泄漏

## 7. 代码审查清单

### 7.1 提交前自检
- [ ] 代码编译通过，无警告
- [ ] 单元测试通过率 100%
- [ ] 代码覆盖率不降低
- [ ] SonarQube 无严重/阻断问题
- [ ] 代码风格符合规范

### 7.2 审查关注点
- 业务逻辑正确性
- 边界条件处理
- 异常和错误处理
- 性能影响评估
- 安全隐患排查
