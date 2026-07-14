"""
配置管理模块。

Description:
    管理环境变量和应用配置，使用 pydantic-settings 实现类型安全的配置管理。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== API Keys ====================
    dashscope_api_key: str = Field(default="", description="阿里云 DashScope API Key")
    kling_access_key: str = Field(default="", description="可灵AI Access Key")
    kling_secret_key: str = Field(default="", description="可灵AI Secret Key")

    # ==================== 千问模型配置 ====================
    qwen_api_key: str = Field(default="", description="千问 API Key（阿里云百炼）")
    qwen_api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="千问 OpenAI 兼容端点",
    )
    llm_provider: str = Field(default="dashscope", description="LLM 提供商: dashscope/qwen")
    embedding_provider: str = Field(default="local", description="Embedding 提供商: local/qwen")
    qwen_llm_model: str = Field(default="qwen-plus", description="千问 LLM 模型名称")
    qwen_embedding_model: str = Field(
        default="text-embedding-v3", description="千问 Embedding 模型名称"
    )
    qwen_embedding_dimensions: int = Field(default=1024, description="千问 Embedding 向量维度")

    @property
    def effective_dashscope_api_key(self) -> str:
        """获取有效的 DashScope API Key。

        百炼平台的 API Key 是统一的，同一个 Key 既可用于 OpenAI 兼容模式
        也可用于 DashScope 原生协议。当 dashscope_api_key 未配置时，
        回退到 qwen_api_key。

        Returns:
            有效的 API Key。
        """
        return self.dashscope_api_key or self.qwen_api_key

    @property
    def effective_qwen_api_key(self) -> str:
        """获取有效的千问 API Key。

        当 qwen_api_key 未配置时，回退到 dashscope_api_key。

        Returns:
            有效的 API Key。
        """
        return self.qwen_api_key or self.dashscope_api_key

    # ==================== LangChain 配置 ====================
    langchain_tracing_v2: bool = Field(default=False, description="启用 LangSmith 追踪")
    langchain_api_key: str = Field(default="", description="LangSmith API Key")
    langchain_project: str = Field(
        default="product-visual-generator", description="LangSmith 项目名"
    )

    # ==================== 服务配置 ====================
    host: str = Field(default="0.0.0.0", description="服务主机")
    port: int = Field(default=8000, description="服务端口")
    debug: bool = Field(default=False, description="调试模式")

    # ==================== 存储配置 ====================
    storage_type: str = Field(default="local", description="存储类型: local/oss")
    storage_path: str = Field(default="./output", description="本地存储路径")
    oss_endpoint: str = Field(default="", description="OSS Endpoint")
    oss_bucket: str = Field(default="", description="OSS Bucket")
    oss_access_key: str = Field(default="", description="OSS Access Key")
    oss_secret_key: str = Field(default="", description="OSS Secret Key")

    # ==================== 日志配置 ====================
    log_level: str = Field(default="INFO", description="日志级别")

    # ==================== Redis 配置 ====================
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis 连接 URL")
    redis_prefix: str = Field(
        default="pvg:", description="Redis Key 前缀"
    )  # product-visual-generator

    # ==================== PostgreSQL 配置 ====================
    postgres_host: str = Field(default="localhost", description="PostgreSQL 主机")
    postgres_port: int = Field(default=5432, description="PostgreSQL 端口")
    postgres_user: str = Field(default="postgres", description="PostgreSQL 用户名")
    postgres_password: str = Field(default="", description="PostgreSQL 密码")
    postgres_db: str = Field(default="pvg", description="PostgreSQL 数据库名")

    # ==================== RAG 配置 ====================
    rag_enabled: bool = Field(default=True, description="启用 RAG 检索增强")
    embedding_model: str = Field(default="BAAI/bge-large-zh", description="Embedding 模型名称")
    embedding_device: str = Field(
        default="auto", description="Embedding 设备: auto/cuda/cpu（auto 自动探测可用设备）"
    )
    chunk_size: int = Field(default=512, description="文档分块大小 (tokens)")
    chunk_overlap: int = Field(default=64, description="分块重叠大小 (tokens)")
    retrieval_top_k: int = Field(default=5, description="检索返回文档数量")
    similarity_threshold: float = Field(default=0.7, description="相似度阈值")

    # ==================== RAG 高级配置 ====================
    query_rewriting_enabled: bool = Field(default=False, description="启用 Query 改写")
    query_rewriting_mode: str = Field(
        default="single", description="Query 改写模式: single/multi_query/hyde"
    )
    query_rewriting_max_variants: int = Field(default=3, description="MultiQuery 最大变体数")
    hyde_enabled: bool = Field(default=False, description="启用 HyDE 假设文档嵌入")
    reranker_enabled: bool = Field(default=False, description="启用 Cross-Encoder 重排序")
    reranker_model: str = Field(
        default="BAAI/bge-reranker-v2-m3", description="Cross-Encoder 重排序模型名称"
    )
    reranker_top_k: int = Field(default=5, description="重排序后保留的结果数量")
    reranker_device: str = Field(default="auto", description="重排序模型设备: auto/cuda/cpu")
    hybrid_retrieval_enabled: bool = Field(
        default=False, description="启用混合检索 (Dense+Sparse+ColBERT)"
    )
    hybrid_model: str = Field(default="BAAI/bge-m3", description="混合检索模型名称 (BGE-M3)")
    hybrid_dense_weight: float = Field(default=0.4, description="Dense 向量检索权重")
    hybrid_sparse_weight: float = Field(default=0.3, description="Sparse 稀疏检索权重")
    hybrid_colbert_weight: float = Field(default=0.3, description="ColBERT 检索权重")
    hybrid_rrf_k: int = Field(default=60, description="RRF 融合常数 K")

    # ==================== Graph RAG 配置 ====================
    graph_rag_enabled: bool = Field(default=False, description="启用 Graph RAG 知识图谱增强")
    graph_rag_auto_build: bool = Field(default=True, description="文档入库时自动构建图谱")
    graph_rag_search_mode: str = Field(
        default="local", description="Graph RAG 检索模式: local/global/hybrid"
    )
    graph_rag_max_communities: int = Field(default=10, description="社区发现最大社区数")
    graph_rag_local_search_depth: int = Field(default=2, description="Local Search 实体遍历深度")
    graph_rag_global_search_max_communities: int = Field(
        default=5, description="Global Search 最大社区摘要数"
    )

    # ==================== 分类记忆配置 ====================
    memory_enabled: bool = Field(default=False, description="启用分类记忆系统")
    memory_auto_classify: bool = Field(default=True, description="自动分类记忆")
    memory_max_per_type: int = Field(default=100, description="每类记忆最大存储数")
    memory_forget_threshold_days: int = Field(default=90, description="记忆遗忘阈值（天）")

    # ==================== 生成配置 ====================
    default_image_width: int = Field(default=1024, description="默认图片宽度")
    default_image_height: int = Field(default=1024, description="默认图片高度")
    default_video_fps: int = Field(default=30, description="默认视频帧率")
    max_concurrent_generations: int = Field(default=5, description="最大并发生成数")
    max_upload_size_mb: int = Field(default=10, description="上传文件最大大小（MB）")

    # ==================== 图片生成 RAG 配置 ====================
    image_rag_enabled: bool = Field(default=False, description="启用图片生成 RAG 增强")
    image_rag_auto_ingest: bool = Field(default=True, description="自动将高质量生成结果入库知识库")
    image_rag_quality_threshold: float = Field(default=0.7, description="自动入库的质量评分阈值")

    # ==================== 模型配置 ====================
    llm_model: str = Field(default="qwen-plus", description="LLM 模型名称")
    image_model: str = Field(default="wanx-v1", description="图像生成模型")
    video_model: str = Field(default="kling-v1", description="视频生成模型")

    # ==================== 占位资产降级配置 ====================
    allow_mock_assets: bool = Field(
        default=True,
        description=(
            "是否允许在无 API Key 或真实 Provider 失败时降级生成占位（mock）资产。"
            "占位资产会被明确标记 is_mock=True 且仅供本地/CI 便利；"
            "生产环境必须设为 False，否则会静默产出'已完成'的假图/假视频。"
        ),
    )

    # ==================== 认证配置 ====================
    auth_enabled: bool = Field(default=True, description="是否启用 API Token 鉴权")
    auth_api_tokens_json: str = Field(
        default="[]",
        description=(
            "API Token 注册表 JSON，格式: "
            '[{"token_hash":"<sha256-hex>","tenant_id":"...","user_id":"...","scopes":[...]}]'
        ),
    )
    auth_allow_ws_query_token: bool = Field(
        default=False, description="是否允许 WebSocket 查询参数传递 token"
    )
    cors_allow_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="CORS 允许的来源，逗号分隔",
    )
    credentials_encryption_key: str = Field(default="", description="凭证加密密钥")

    @property
    def is_langchain_tracing_enabled(self) -> bool:
        """检查是否启用追踪。

        Returns:
            是否启用追踪。
        """
        return self.langchain_tracing_v2 and bool(self.langchain_api_key)

    def get_storage_config(self) -> dict:
        """获取存储配置。

        Returns:
            存储配置字典。
        """
        if self.storage_type == "oss":
            return {
                "type": "oss",
                "endpoint": self.oss_endpoint,
                "bucket": self.oss_bucket,
                "access_key": self.oss_access_key,
                "secret_key": self.oss_secret_key,
            }
        return {
            "type": "local",
            "path": self.storage_path,
        }

    @property
    def postgres_url(self) -> str:
        """获取 PostgreSQL 连接 URL。

        Returns:
            PostgreSQL 连接 URL。
        """
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def postgres_url_sync(self) -> str:
        """获取同步 PostgreSQL 连接 URL。

        Returns:
            同步 PostgreSQL 连接 URL。
        """
        return f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def cors_origins(self) -> list[str]:
        """获取 CORS 允许的来源列表。

        Returns:
            CORS 来源列表，按逗号分割。
        """
        if not self.cors_allow_origins:
            return []
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（单例）。

    Returns:
        配置实例。
    """
    return Settings()
