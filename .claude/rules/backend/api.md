# Project Rules

This document defines the coding standards, architectural patterns, and technical constraints for the `pa-biz-service` project. It is intended to be used as context for AI coding assistants.

## 1. Technology Stack & Environment

- **Java Version**: JDK 1.8
- **Framework**: Spring Boot 2.x, Spring Cloud (Nacos, Feign)
- **Persistence**: MyBatis Plus 3.x (with custom Repository wrapper)
- **Database**: MySQL
- **JSON Processing**: Fastjson / Jackson
- **Utilities**: Apache Commons Lang3, Hutool, Lombok
- **API Documentation**: Swagger / Knife4j
- **Excel Processing**: EasyExcel

## 2. Architecture & Layering

The project follows a strict layered architecture:

1.  **API Layer (`*-api` module)**
    - Defines Interfaces (`*Api.java`), DTOs (`*ReqDTO`, `*RespDTO`), and Enums.
    - No business logic allowed.
    - Used by Feign clients and implemented by the Biz layer.

2.  **Controller Layer (`*-biz` module - `apiimpl` package)**
    - Implements API interfaces.
    - Naming convention: `*ServiceApiImpl` (e.g., `SmsProductSaleReviewServiceApiImpl`).
    - Annotations: `@RestController`, `@RequestMapping`, `@Validated`, `@Slf4j`.
    - Returns `Result<T>`, `ListResult<T>`, or `RespPageDO<T>`.
    - Handles HTTP requests, parameter validation, and delegates to Service.

3.  **Service Layer (`*-biz` module - `service` package)**
    - Implements business logic.
    - Naming convention: `*ServiceImpl` implements `*Service`.
    - Annotations: `@Service`, `@Validated`.
    - Transaction management: `@Transactional(rollbackFor = Exception.class)`.

4.  **Repository Layer (`*-biz` module - `dao.mysql...repository` package)**
    - Abstraction over MyBatis Plus Mappers.
    - Interface: extends `BaseRepository<PO, ID>`.
    - Implementation: extends `BaseRepositoryImpl<PO, ID>` implements `*Repository`.
    - Uses `BizLambdaQueryWrapper` for type-safe queries.
    - Naming convention: `*Repository` / `*RepositoryImpl`.

5.  **Mapper Layer (`*-biz` module - `dao.mysql...mapper` package)**
    - Standard MyBatis Plus interfaces.
    - XML files located in `src/main/resources/mapper`.

6.  **PO Layer (`*-biz` module - `dao.mysql...po` package)**
    - Persistent Objects mapping to database tables.
    - Extends `BasePO`.
    - Annotations: `@TableName`, `@Data`, `@EqualsAndHashCode(callSuper = true)`, `@Builder`.

## 3. Coding Conventions

### 3.1 Naming
- **Classes**: PascalCase (e.g., `UserServiceImpl`).
- **Methods/Variables**: camelCase (e.g., `findUserById`).
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_RETRY_COUNT`).
- **Packages**: lowercase, separated by dots (e.g., `com.ux168.pa.service.sms.biz.service`).

### 3.2 Controller Patterns
- **Path**: Use plural nouns (e.g., `/sms/product-reviews`).
- **Injection**: Use `@Resource` for dependencies.
- **Exception Handling**: Use `ServiceExceptionUtil.exception(CodeConstants.ERROR_CODE, "message")`.

### 3.3 Repository Patterns
- **Query Construction**:
  ```java
  // Example of findList implementation in RepositoryImpl
  @Override
  public List<SmsProductSaleReviewPO> findList(SmsProductSaleReviewBO queryBO) {
      return findList(new BizLambdaQueryWrapper<SmsProductSaleReviewPO>()
              .eqIfPresent(SmsProductSaleReviewPO::getProductId, queryBO.getProductId())
              .likeIfPresent(SmsProductSaleReviewPO::getSalesUserName, queryBO.getSalesUserName())
              .orderByDesc(SmsProductSaleReviewPO::getUpdateTime));
  }
  ```

### 3.4 DTO/PO Mapping
- Use MapStruct or manual conversion.
- **NEVER** return POs directly from the API layer. Always convert to DTOs.
- **NEVER** accept POs as Controller parameters.

## 4. Code Examples

### 4.1 Controller Implementation
```java
@Api(tags = "Product Review Management")
@RestController
@RequestMapping("/sms/product-reviews")
@Validated
@Slf4j
public class SmsProductSaleReviewServiceApiImpl implements SmsProductSaleReviewServiceApi {

    @Resource
    private SmsProductSaleReviewService smsProductSaleReviewService;

    @Override
    @ApiOperation("Get Review Details")
    public Result<SmsProductSaleReviewRespDTO> getById(@PathVariable Long id) {
        SmsProductSaleReviewBO bo = smsProductSaleReviewService.findById(id);
        return Result.success(SmsProductSaleReviewConverter.INSTANCE.toRespDTO(bo));
    }
}
```

### 4.2 Service Implementation
```java
@Service
@Validated
public class SmsProductSaleReviewServiceImpl implements SmsProductSaleReviewService {

    @Resource
    private SmsProductSaleReviewRepository smsProductSaleReviewRepository;

    @Override
    public SmsProductSaleReviewBO findById(Long id) {
        SmsProductSaleReviewPO po = smsProductSaleReviewRepository.findById(id);
        if (po == null) {
            throw ServiceExceptionUtil.exception(CodeConstants.NOT_EXISTS);
        }
        return SmsProductSaleReviewConverter.INSTANCE.toBO(po);
    }
}
```

## 5. Constraints & Prohibitions

- **No Tab Characters**: Use 4 spaces for indentation.
- **Line Length**: Max 120 characters.
- **No System.out**: Use Slf4j for logging.
- **No Magic Numbers**: Extract constants.
- **No Raw SQL Injection**: Use `LambdaQueryWrapper` or parameterized queries.
- **Version Control**: API paths must not change destructively without versioning.
