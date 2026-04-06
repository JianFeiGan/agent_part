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
    embedding_device: str = Field(default="cuda", description="Embedding 设备: cuda/cpu")
    chunk_size: int = Field(default=512, description="文档分块大小 (tokens)")
    chunk_overlap: int = Field(default=64, description="分块重叠大小 (tokens)")
    retrieval_top_k: int = Field(default=5, description="检索返回文档数量")
    similarity_threshold: float = Field(default=0.7, description="相似度阈值")

    # ==================== 生成配置 ====================
    default_image_width: int = Field(default=1024, description="默认图片宽度")
    default_image_height: int = Field(default=1024, description="默认图片高度")
    default_video_fps: int = Field(default=30, description="默认视频帧率")
    max_concurrent_generations: int = Field(default=5, description="最大并发生成数")

    # ==================== 模型配置 ====================
    llm_model: str = Field(default="qwen3.5-flash", description="LLM 模型名称")
    image_model: str = Field(default="wanx-v1", description="图像生成模型")
    video_model: str = Field(default="kling-v1", description="视频生成模型")

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


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（单例）。

    Returns:
        配置实例。
    """
    return Settings()
