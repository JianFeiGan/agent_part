"""
刊登平台适配器基类。

Description:
    定义统一的刊登推送接口，各平台适配器实现此接口。
    Phase 3-5 使用模拟实现，后续接入真实平台 API。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    ListingTask,
    Platform,
)


@dataclass
class PushResult:
    """刊登推送结果。

    Attributes:
        success: 是否成功。
        platform: 目标平台。
        listing_id: 平台返回的刊登ID。
        url: 刊登页面URL。
        error: 错误信息（失败时）。
        raw_response: 原始响应（调试用）。
    """

    success: bool
    platform: Platform
    listing_id: str | None = None
    url: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class BasePlatformAdapter(ABC):
    """刊登平台适配器基类。

    每个平台（Amazon, eBay, Shopify）实现此基类，负责：
    - 认证授权
    - 素材格式转换
    - 文案格式转换
    - 刊登推送/更新/删除
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """初始化适配器。

        Args:
            config: 平台配置（API Key, Token 等）。
        """
        self._config = config or {}
        self._auth_token: str | None = None

    @abstractmethod
    def authenticate(self) -> str:
        """执行平台认证，返回访问令牌。

        Returns:
            访问令牌字符串。
        """

    @abstractmethod
    def transform_assets(
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
    def transform_copywriting(
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
    def push_listing(
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
    def update_listing(
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
    def delete_listing(self, listing_id: str) -> PushResult:
        """删除已有刊登。

        Args:
            listing_id: 平台刊登ID。

        Returns:
            删除结果。
        """


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

    def get(self, platform: Platform, config: dict[str, Any] | None = None) -> BasePlatformAdapter:
        """获取平台适配器实例。

        Args:
            platform: 平台枚举。
            config: 可选的平台配置。

        Returns:
            适配器实例。

        Raises:
            KeyError: 平台未注册。
        """
        if platform not in self._adapters:
            raise KeyError(f"Platform {platform.value} not registered")

        if platform not in self._instances:
            adapter_class = self._adapters[platform]
            self._instances[platform] = adapter_class(config=config)

        return self._instances[platform]
