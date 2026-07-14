"""平台适配器基类测试。"""

import pytest

from src.agents.listing_platform_adapter import (
    AdapterRegistry,
    BasePlatformAdapter,
    PushConfig,
    PushResult,
)
from src.models.listing import Platform


class TestBasePlatformAdapter:
    """测试抽象基类。"""

    def test_cannot_instantiate_abstract(self) -> None:
        """测试抽象类不能直接实例化。"""
        with pytest.raises(TypeError):
            BasePlatformAdapter()  # type: ignore

    def test_subclass_must_implement_all(self) -> None:
        """测试不完整的子类会报错。"""

        class IncompleteAdapter(BasePlatformAdapter):
            async def authenticate(self) -> str:
                return "token"

            # 缺少其他抽象方法实现

        with pytest.raises(TypeError):
            IncompleteAdapter()


class TestPushResult:
    """测试推送结果数据类。"""

    def test_success_result(self) -> None:
        """测试成功结果。"""
        result = PushResult(
            success=True,
            platform=Platform.AMAZON,
            listing_id="B08XYZ123",
            url="https://www.amazon.com/dp/B08XYZ123",
        )
        assert result.success is True
        assert result.listing_id == "B08XYZ123"
        assert result.error is None
        assert result.error_code is None
        assert result.retry_count == 0
        assert result.latency_ms == 0.0

    def test_failure_result(self) -> None:
        """测试失败结果。"""
        result = PushResult(
            success=False,
            platform=Platform.EBAY,
            error="API timeout",
            error_code="RETRY_EXHAUSTED",
            retry_count=3,
            latency_ms=1500.0,
        )
        assert result.success is False
        assert result.listing_id is None
        assert result.error_code == "RETRY_EXHAUSTED"
        assert result.retry_count == 3
        assert result.latency_ms == 1500.0


class TestPushConfig:
    """测试推送配置数据类。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        config = PushConfig()
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.rate_limit_rpm == 60
        assert config.timeout_seconds == 30.0

    def test_custom_values(self) -> None:
        """测试自定义值。"""
        config = PushConfig(
            max_retries=5,
            retry_base_delay=2.0,
            rate_limit_rpm=120,
            timeout_seconds=60.0,
        )
        assert config.max_retries == 5
        assert config.rate_limit_rpm == 120


class TestAdapterRegistry:
    """测试适配器注册表。"""

    def test_register_and_get(self) -> None:
        """测试注册和获取适配器。"""
        registry = AdapterRegistry()
        registry._instances = {}
        registry._adapters = {}

        class TestAdapter(BasePlatformAdapter):
            async def authenticate(self) -> str:
                return "token"

            async def transform_assets(self, *_a, **_kw):  # type: ignore
                return {}

            async def transform_copywriting(self, *_a, **_kw):  # type: ignore
                return {}

            async def push_listing(self, *_a, **_kw):  # type: ignore
                return PushResult(success=True, platform=Platform.AMAZON, listing_id="1")

            async def update_listing(self, *_a, **_kw):  # type: ignore
                return PushResult(success=True, platform=Platform.AMAZON, listing_id="1")

            async def delete_listing(self, *_a, **_kw):  # type: ignore
                return PushResult(success=True, platform=Platform.AMAZON)

        registry.register(Platform.AMAZON, TestAdapter)
        adapter = registry.get(Platform.AMAZON)
        assert isinstance(adapter, TestAdapter)

    def test_get_with_push_config(self) -> None:
        """测试带 push_config 获取适配器。"""
        registry = AdapterRegistry()
        registry._instances = {}
        registry._adapters = {}

        class TestAdapter(BasePlatformAdapter):
            async def authenticate(self) -> str:
                return "token"

            async def transform_assets(self, *_a, **_kw):  # type: ignore
                return {}

            async def transform_copywriting(self, *_a, **_kw):  # type: ignore
                return {}

            async def push_listing(self, *_a, **_kw):  # type: ignore
                return PushResult(success=True, platform=Platform.SHOPIFY, listing_id="1")

            async def update_listing(self, *_a, **_kw):  # type: ignore
                return PushResult(success=True, platform=Platform.SHOPIFY, listing_id="1")

            async def delete_listing(self, *_a, **_kw):  # type: ignore
                return PushResult(success=True, platform=Platform.SHOPIFY)

        registry.register(Platform.SHOPIFY, TestAdapter)
        push_config = PushConfig(max_retries=10, rate_limit_rpm=0)
        adapter = registry.get(Platform.SHOPIFY, push_config=push_config)
        assert isinstance(adapter, TestAdapter)
        assert adapter._push_config.max_retries == 10

    def test_get_unregistered_raises(self) -> None:
        """测试获取未注册的适配器会报错。"""
        registry = AdapterRegistry()
        registry._instances = {}
        registry._adapters = {}

        with pytest.raises(KeyError):
            registry.get(Platform.AMAZON)

    def test_singleton(self) -> None:
        """测试注册表是单例。"""
        r1 = AdapterRegistry()
        r2 = AdapterRegistry()
        assert r1 is r2
