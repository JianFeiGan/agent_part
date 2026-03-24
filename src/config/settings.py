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
    dashscope_api_key: str = Field(
        default="", description="阿里云 DashScope API Key"
    )
    kling_api_key: str = Field(default="", description="可灵AI API Key")

    # ==================== LangChain 配置 ====================
    langchain_tracing_v2: bool = Field(
        default=False, description="启用 LangSmith 追踪"
    )
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

    # ==================== 生成配置 ====================
    default_image_width: int = Field(default=1024, description="默认图片宽度")
    default_image_height: int = Field(default=1024, description="默认图片高度")
    default_video_fps: int = Field(default=30, description="默认视频帧率")
    max_concurrent_generations: int = Field(
        default=5, description="最大并发生成数"
    )

    # ==================== 模型配置 ====================
    llm_model: str = Field(
        default="qwen-max", description="LLM 模型名称"
    )
    image_model: str = Field(
        default="wanx-v1", description="图像生成模型"
    )
    video_model: str = Field(
        default="kling-v1", description="视频生成模型"
    )

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


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（单例）。

    Returns:
        配置实例。
    """
    return Settings()
