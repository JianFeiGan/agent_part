# 数据库开发规则

## 1. 数据库设计规范

### 1.1 命名规范
| 对象 | 命名规则 | 示例 |
|------|----------|------|
| 数据库 | 项目名_环境 | `pa_biz_dev`, `pa_biz_prod` |
| 表名 | 业务模块_表意，小写+下划线 | `sms_sales_order`, `ims_inventory` |
| 字段名 | 小写+下划线，见名知意 | `create_time`, `update_by` |
| 索引名 | idx_表名_字段名 | `idx_employee_name` |
| 唯一索引 | uk_表名_字段名 | `uk_employee_mobile` |
| 主键 | 表名_id 或 id | `employee_id`, `id` |

### 1.2 字段设计规范
```sql
-- 必备字段（每个表都必须包含）
CREATE TABLE sms_sales_order (
    id              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    -- 业务字段
    order_no        VARCHAR(64)         NOT NULL COMMENT '订单编号',
    customer_id     BIGINT UNSIGNED     NOT NULL COMMENT '客户ID',
    amount          DECIMAL(18, 4)      NOT NULL DEFAULT 0 COMMENT '订单金额',
    status          TINYINT UNSIGNED    NOT NULL DEFAULT 0 COMMENT '状态：0-待处理 1-处理中 2-已完成 3-已取消',

    -- 审计字段（必备）
    create_by       BIGINT UNSIGNED     NOT NULL COMMENT '创建人ID',
    create_time     DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_by       BIGINT UNSIGNED     NOT NULL COMMENT '更新人ID',
    update_time     DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted         TINYINT UNSIGNED    NOT NULL DEFAULT 0 COMMENT '删除标记：0-未删除 1-已删除',

    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    KEY idx_customer_id (customer_id),
    KEY idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='销售订单表';
```

### 1.3 字段类型规范
| 数据类型 | 使用场景 | 说明 |
|----------|----------|------|
| BIGINT | 主键、外键、ID | 无符号，AUTO_INCREMENT |
| INT | 状态、类型、计数 | TINYINT 用于小范围枚举 |
| VARCHAR(64) | 编号、编码 | 定长字符串 |
| VARCHAR(255) | 名称、标题 | 通用短文本 |
| VARCHAR(1000) | 描述、备注 | 长文本限制 |
| TEXT | 大文本内容 | 仅必要时使用 |
| DECIMAL(18,4) | 金额、价格 | 精确计算，4位小数 |
| DATETIME | 时间戳 | 默认 CURRENT_TIMESTAMP |
| DATE | 日期 | 仅日期部分 |
| JSON | 扩展字段 | 存储变长结构化数据 |

## 2. MyBatis-Plus 使用规范

### 2.1 Entity 定义
```java
/**
 * 销售订单实体
 * @author ganjianfei
 * @version 1.0.0
 * 2024-01-15
 */
@Data
@TableName("sms_sales_order")
public class SalesOrder implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 订单编号 */
    private String orderNo;

    /** 客户ID */
    private Long customerId;

    /** 订单金额 */
    private BigDecimal amount;

    /** 状态：0-待处理 1-处理中 2-已完成 3-已取消 */
    private Integer status;

    /** 创建人ID */
    @TableField(fill = FieldFill.INSERT)
    private Long createBy;

    /** 创建时间 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    /** 更新人ID */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private Long updateBy;

    /** 更新时间 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;

    /** 删除标记：0-未删除 1-已删除 */
    @TableLogic
    @TableField(fill = FieldFill.INSERT)
    private Integer deleted;
}
```

### 2.2 Mapper 接口
```java
/**
 * 销售订单 Mapper
 * @author ganjianfei
 * @version 1.0.0
 * 2024-01-15
 */
@Mapper
public interface SalesOrderMapper extends BaseMapper<SalesOrder> {

    /**
     * 根据客户ID查询订单列表（带分页）
     * @param page 分页参数
     * @param customerId 客户ID
     * @param status 状态（可选）
     * @return 分页结果
     */
    IPage<SalesOrderVO> selectByCustomerId(
        @Param("page") IPage<?> page,
        @Param("customerId") Long customerId,
        @Param("status") Integer status
    );

    /**
     * 批量插入订单
     * @param orderList 订单列表
     * @return 插入数量
     */
    int batchInsert(@Param("list") List<SalesOrder> orderList);
}
```

### 2.3 XML 映射文件
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
    "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.ux168.pa.application.sms.mapper.SalesOrderMapper">

    <resultMap id="BaseResultMap" type="com.ux168.pa.application.sms.entity.SalesOrder">
        <id column="id" property="id"/>
        <result column="order_no" property="orderNo"/>
        <result column="customer_id" property="customerId"/>
        <result column="amount" property="amount"/>
        <result column="status" property="status"/>
        <result column="create_by" property="createBy"/>
        <result column="create_time" property="createTime"/>
        <result column="update_by" property="updateBy"/>
        <result column="update_time" property="updateTime"/>
        <result column="deleted" property="deleted"/>
    </resultMap>

    <select id="selectByCustomerId" resultType="com.ux168.pa.application.sms.vo.SalesOrderVO">
        SELECT
            o.id,
            o.order_no,
            o.amount,
            o.status,
            o.create_time,
            c.name as customer_name
        FROM sms_sales_order o
        LEFT JOIN sms_customer c ON o.customer_id = c.id
        WHERE o.deleted = 0
          AND o.customer_id = #{customerId}
        <if test="status != null">
            AND o.status = #{status}
        </if>
        ORDER BY o.create_time DESC
    </select>

    <insert id="batchInsert">
        INSERT INTO sms_sales_order (
            order_no, customer_id, amount, status,
            create_by, create_time, update_by, update_time, deleted
        ) VALUES
        <foreach collection="list" item="item" separator=",">
            (
                #{item.orderNo}, #{item.customerId}, #{item.amount}, #{item.status},
                #{item.createBy}, #{item.createTime}, #{item.updateBy}, #{item.updateTime}, 0
            )
        </foreach>
    </insert>
</mapper>
```

## 3. Service 层数据访问规范

### 3.1 Service 接口
```java
/**
 * 销售订单服务接口
 * @author ganjianfei
 * @version 1.0.0
 * 2024-01-15
 */
public interface SalesOrderService extends IService<SalesOrder> {

    /**
     * 创建订单
     * @param request 创建请求
     * @return 订单ID
     */
    Long createOrder(CreateOrderRequest request);

    /**
     * 分页查询订单
     * @param query 查询条件
     * @return 分页结果
     */
    PageResult<OrderVO> pageOrders(OrderQuery query);
}
```

### 3.2 Service 实现
```java
/**
 * 销售订单服务实现
 * @author ganjianfei
 * @version 1.0.0
 * 2024-01-15
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class SalesOrderServiceImpl extends ServiceImpl<SalesOrderMapper, SalesOrder>
    implements SalesOrderService {

    private final SalesOrderMapper salesOrderMapper;
    private final CustomerService customerService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long createOrder(CreateOrderRequest request) {
        // 1. 校验客户
        Customer customer = customerService.getById(request.getCustomerId());
        Assert.notNull(customer, "客户不存在");

        // 2. 构建实体
        SalesOrder order = new SalesOrder();
        order.setOrderNo(generateOrderNo());
        order.setCustomerId(request.getCustomerId());
        order.setAmount(request.getAmount());
        order.setStatus(OrderStatus.PENDING.getCode());

        // 3. 保存
        this.save(order);

        log.info("订单创建成功: orderNo={}, customerId={}", order.getOrderNo(), order.getCustomerId());

        return order.getId();
    }

    @Override
    public PageResult<OrderVO> pageOrders(OrderQuery query) {
        Page<OrderVO> page = new Page<>(query.getCurrent(), query.getSize());

        LambdaQueryWrapper<SalesOrder> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(query.getCustomerId() != null, SalesOrder::getCustomerId, query.getCustomerId())
               .eq(query.getStatus() != null, SalesOrder::getStatus, query.getStatus())
               .ge(query.getStartTime() != null, SalesOrder::getCreateTime, query.getStartTime())
               .le(query.getEndTime() != null, SalesOrder::getCreateTime, query.getEndTime())
               .orderByDesc(SalesOrder::getCreateTime);

        Page<SalesOrder> entityPage = this.page(page, wrapper);

        // 转换为 VO
        List<OrderVO> voList = entityPage.getRecords().stream()
            .map(this::convertToVO)
            .collect(Collectors.toList());

        PageResult<OrderVO> result = new PageResult<>();
        result.setRecords(voList);
        result.setTotal(entityPage.getTotal());
        result.setCurrent(entityPage.getCurrent());
        result.setSize(entityPage.getSize());
        result.setPages(entityPage.getPages());

        return result;
    }

    private String generateOrderNo() {
        return "SO" + DateUtil.format(new Date(), "yyyyMMddHHmmss") + RandomUtil.randomNumbers(6);
    }

    private OrderVO convertToVO(SalesOrder order) {
        // 转换逻辑
        return new OrderVO();
    }
}
```

## 4. 查询优化规范

### 4.1 索引设计原则
- 主键必须建立索引
- 外键字段必须建立索引
- 高频查询条件字段建立索引
- 排序字段考虑建立索引
- 联合索引遵循最左前缀原则
- 单表索引数量不超过 5 个

### 4.2 SQL 编写规范
```sql
-- 推荐：使用索引覆盖查询
SELECT id, order_no, amount
FROM sms_sales_order
WHERE customer_id = 12345
  AND status = 1
ORDER BY create_time DESC
LIMIT 20;

-- 避免：SELECT * 导致回表
-- 避免：在索引字段上使用函数 WHERE DATE(create_time) = '2024-01-01'
-- 避免：隐式类型转换 WHERE customer_id = '12345'
-- 避免：OR 条件导致索引失效（使用 UNION 替代）
```

### 4.3 分页查询优化
```java
// 深度分页优化：使用游标/延迟关联
public List<OrderVO> queryLargeOffset(OrderQuery query) {
    // 方式1：限制分页深度
    if (query.getCurrent() > 1000) {
        throw new BusinessException("分页页码不能超过1000");
    }

    // 方式2：使用上次查询的最大ID
    // WHERE id > #{lastId} ORDER BY id LIMIT 20

    // 方式3：延迟关联
    // 先查ID，再关联详情
}
```

## 5. ShardingSphere 分库分表规范

### 5.1 分片键选择
- 选择查询频率高的字段作为分片键
- 选择数据分布均匀的字段作为分片键
- 避免使用单调递增字段（导致热点）

### 5.2 分片策略配置
```yaml
spring:
  shardingsphere:
    rules:
      sharding:
        tables:
          sms_sales_order:
            actual-data-nodes: ds$->{0..1}.sms_sales_order_$->{0..15}
            table-strategy:
              standard:
                sharding-column: customer_id
                sharding-algorithm-name: order-table-hash
            database-strategy:
              standard:
                sharding-column: customer_id
                sharding-algorithm-name: order-db-hash
        sharding-algorithms:
          order-table-hash:
            type: INLINE
            props:
              algorithm-expression: sms_sales_order_$->{customer_id % 16}
          order-db-hash:
            type: INLINE
            props:
              algorithm-expression: ds$->{customer_id % 2}
```

### 5.3 分表查询规范
```java
/**
 * 分表查询注意事项：
 * 1. 必须携带分片键，否则全表扫描
 * 2. 分页查询需要在内存中归并结果
 * 3. 排序字段需要包含分片键或全局有序
 */
@Service
public class ShardingOrderService {

    /**
     * 根据客户ID查询（携带分片键，路由到单表）
     */
    public List<SalesOrder> queryByCustomer(Long customerId) {
        LambdaQueryWrapper<SalesOrder> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(SalesOrder::getCustomerId, customerId); // 分片键
        return orderMapper.selectList(wrapper);
    }

    /**
     * 分页查询（广播到所有表，性能较差）
     */
    public Page<SalesOrder> pageAllOrders(Page<SalesOrder> page) {
        // 无分片键条件，ShardingSphere 会路由到所有表
        return orderMapper.selectPage(page, null);
    }
}
```

## 6. 事务管理规范

### 6.1 事务传播行为
```java
@Service
public class OrderService {

    /**
     * 主业务方法：创建订单
     * REQUIRED: 必须有事务，没有则新建
     */
    @Transactional(rollbackFor = Exception.class)
    public Long createOrder(CreateOrderRequest request) {
        // 保存订单
        saveOrder(request);
        // 扣减库存
        inventoryService.deduct(request.getItems());
        // 发送消息
        messageService.sendOrderCreatedMessage(orderId);
    }

    /**
     * 查询方法：不需要事务
     */
    @Transactional(readOnly = true, propagation = Propagation.SUPPORTS)
    public OrderVO getOrderDetail(Long orderId) {
        // 查询逻辑
    }

    /**
     * 独立事务方法：记录日志
     * REQUIRES_NEW: 挂起当前事务，新建独立事务
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void saveOperationLog(Long orderId, String operation) {
        // 日志记录不受外层事务回滚影响
    }
}
```

### 6.2 事务注意事项
- 事务方法必须是 public
- 避免在事务中进行远程调用
- 避免事务嵌套过深
- 长事务考虑拆分或使用异步
- 事务内异常必须抛出，不能被捕获吞掉

## 7. 数据迁移与变更规范

### 7.1 Flyway 脚本规范
```sql
-- V2024.01.15.001__create_sales_order_table.sql
-- 创建销售订单表

CREATE TABLE sms_sales_order (
    id              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    order_no        VARCHAR(64)         NOT NULL COMMENT '订单编号',
    customer_id     BIGINT UNSIGNED     NOT NULL COMMENT '客户ID',
    amount          DECIMAL(18, 4)      NOT NULL DEFAULT 0 COMMENT '订单金额',
    status          TINYINT UNSIGNED    NOT NULL DEFAULT 0 COMMENT '状态',
    create_by       BIGINT UNSIGNED     NOT NULL COMMENT '创建人ID',
    create_time     DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_by       BIGINT UNSIGNED     NOT NULL COMMENT '更新人ID',
    update_time     DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted         TINYINT UNSIGNED    NOT NULL DEFAULT 0 COMMENT '删除标记',
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    KEY idx_customer_id (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='销售订单表';
```

### 7.2 数据变更原则
- 所有 DDL 必须通过 Flyway 脚本执行
- 脚本必须可重复执行（幂等性）
- 大表变更使用 pt-online-schema-change
- 生产环境变更需要审批流程