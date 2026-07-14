"""
刊登平台适配器基类。

Description:
    定义统一的刊登推送接口，各平台适配器实现此接口。
    支持异步操作、速率限制、重试策略和生产级错误处理。
@author ganjianfei
@version 2.0.0
2026-07-14
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    ListingTask,
    Platform,
)


@dataclass
class PushConfig:
    """推送配置。

    Attributes:
        max_retries: 最大重试次数。
        retry_base_delay: 重试基础延迟（秒）。
        rate_limit_rpm: 每分钟请求限制（0 表示无限制）。
        timeout_seconds: HTTP 请求超时时间（秒）。
    """

    max_retries: int = 3
    retry_base_delay: float = 1.0
    rate_limit_rpm: int = 60
    timeout_seconds: float = 30.0


@dataclass
class PushResult:
    """刊登推送结果。

    Attributes:
        success: 是否成功。
        platform: 目标平台。
        listing_id: 平台返回的刊登ID。
        url: 刊登页面URL。
        error: 错误信息（失败时）。
        error_code: 错误码（如 HTTP 状态码）。
        retry_count: 重试次数。
        latency_ms: 请求耗时（毫秒）。
        raw_response: 原始响应（调试用）。
    """

    success: bool
    platform: Platform
    listing_id: str | None = None
    url: str | None = None
    error: str | None = None
    error_code: str | None = None
    retry_count: int = 0
    latency_ms: float = 0.0
    raw_response: dict[str, Any] = field(default_factory=dict)


class BasePlatformAdapter(ABC):
    """刊登平台适配器基类。

    每个平台（Amazon, eBay, Shopify）实现此基类，负责：
    - 认证授权
    - 素材格式转换
    - 文案格式转换
    - 刊登推送/更新/删除

    Attributes:
        _config: 平台配置（API Key, Token 等）。
        _auth_token: 访问令牌。
        _push_config: 推送配置（重试、限流、超时）。
        _client: httpx.AsyncClient 实例（懒加载）。
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        push_config: PushConfig | None = None,
    ) -> None:
        """初始化适配器。

        Args:
            config: 平台配置（API Key, Token 等）。
            push_config: 推送配置（重试、限流、超时）。
        """
        self._config = config or {}
        self._auth_token: str | None = None
        self._push_config = push_config or PushConfig()
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """获取 httpx.AsyncClient 实例（懒加载）。

        Returns:
            httpx.AsyncClient 实例。
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._push_config.timeout_seconds)
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端连接。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def authenticate(self) -> str:
        """执行平台认证，返回访问令牌。

        Returns:
            访问令牌字符串。
        """

    @abstractmethod
    async def transform_assets(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
    ) -> dict[str, Any]:
        """将素材转换为平台要求的格式。

        Args:
            product: 源商品。
            asset_package: 优化后的素材包。

        Returns:
            平台要求的素材格式。
        """

    @abstractmethod
    async def transform_copywriting(
        self,
        copywriting: CopywritingPackage,
    ) -> dict[str, Any]:
        """将文案转换为平台要求的格式。

        Args:
            copywriting: 优化后的文案。

        Returns:
            平台要求的文案格式。
        """

    @abstractmethod
    async def push_listing(
        self,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
        task: ListingTask,
    ) -> PushResult:
        """推送新刊登到平台。

        Args:
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。
            task: 刊登任务。

        Returns:
            推送结果。
        """

    @abstractmethod
    async def update_listing(
        self,
        listing_id: str,
        product: ListingProduct,
        asset_package: AssetPackage,
        copywriting: CopywritingPackage,
    ) -> PushResult:
        """更新已有刊登。

        Args:
            listing_id: 平台刊登ID。
            product: 源商品。
            asset_package: 优化后的素材。
            copywriting: 优化后的文案。

        Returns:
            更新结果。
        """

    @abstractmethod
    async def delete_listing(self, listing_id: str) -> PushResult:
        """删除已有刊登。

        Args:
            listing_id: 平台刊登ID。

        Returns:
            删除结果。
        """

    async def health_check(self) -> bool:
        """检查平台 API 健康状态。

        默认实现尝试获取访问令牌来验证连通性。

        Returns:
            True 表示健康，False 表示不可用。
        """
        try:
            await self.authenticate()
            return True
        except Exception:
            return False

    async def get_listing_status(self, _listing_id: str) -> dict[str, Any] | None:
        """获取刊登状态。

        默认实现返回 None，子类可覆盖。

        Args:
            _listing_id: 平台刊登ID。

        Returns:
            刊登状态字典，或 None 表示不支持/未找到。
        """
        return None


class AdapterRegistry:
    """适配器注册表（单例）。

    通过平台枚举获取对应的适配器实例。
    """

    _instance: "AdapterRegistry | None" = None
    _adapters: dict[Platform, type[BasePlatformAdapter]]
    _instances: dict[Platform, BasePlatformAdapter]

    def __new__(cls) -> "AdapterRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._adapters = {}
            cls._instance._instances = {}
        return cls._instance

    def register(
        self,
        platform: Platform,
        adapter_class: type[BasePlatformAdapter],
    ) -> None:
        """注册平台适配器。

        Args:
            platform: 平台枚举。
            adapter_class: 适配器类。
        """
        self._adapters[platform] = adapter_class
        self._instances.pop(platform, None)

    def get(
        self,
        platform: Platform,
        config: dict[str, Any] | None = None,
        push_config: PushConfig | None = None,
    ) -> BasePlatformAdapter:
        """获取平台适配器实例。

        Args:
            platform: 平台枚举。
            config: 可选的平台配置。
            push_config: 可选的推送配置。

        Returns:
            适配器实例。

        Raises:
            KeyError: 平台未注册。
        """
        if platform not in self._adapters:
            raise KeyError(f"Platform {platform.value} not registered")

        if platform not in self._instances:
            adapter_class = self._adapters[platform]
            self._instances[platform] = adapter_class(config=config, push_config=push_config)

        return self._instances[platform]
