"""平台适配器基类测试。"""

import pytest

from src.agents.listing_platform_adapter import AdapterRegistry, BasePlatformAdapter, PushResult
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
            def authenticate(self) -> str:
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

    def test_failure_result(self) -> None:
        """测试失败结果。"""
        result = PushResult(
            success=False,
            platform=Platform.EBAY,
            error="API timeout",
        )
        assert result.success is False
        assert result.listing_id is None


class TestAdapterRegistry:
    """测试适配器注册表。"""

    def test_register_and_get(self) -> None:
        """测试注册和获取适配器。"""
        registry = AdapterRegistry()

        class TestAdapter(BasePlatformAdapter):
            def authenticate(self) -> str:
                return "token"

            def transform_assets(self, *a, **k):  # type: ignore
                return {}

            def transform_copywriting(self, *a, **k):  # type: ignore
                return {}

            def push_listing(self, *a, **k):  # type: ignore
                return PushResult(success=True, platform=Platform.AMAZON, listing_id="1")

            def update_listing(self, *a, **k):  # type: ignore
                return PushResult(success=True, platform=Platform.AMAZON, listing_id="1")

            def delete_listing(self, *a, **k):  # type: ignore
                return PushResult(success=True, platform=Platform.AMAZON)

        registry.register(Platform.AMAZON, TestAdapter)
        adapter = registry.get(Platform.AMAZON)
        assert isinstance(adapter, TestAdapter)

    def test_get_unregistered_raises(self) -> None:
        """测试获取未注册的适配器会报错。"""
        # 使用一个不可能存在的 Platform 值
        class FakeRegistry:
            _adapters = {}

        reg = FakeRegistry()
        from src.models.listing import Platform

        # 直接测试逻辑：清空后获取未注册的平台
        registry = AdapterRegistry()
        # 由于单例可能被其他测试污染，直接验证 KeyError 的抛出逻辑
        # 获取一个确认未注册的平台
        for p in Platform:
            if p not in registry._adapters:
                with pytest.raises(KeyError):
                    registry.get(p)
                return
        # 如果所有平台都注册了，说明测试环境已注册全部平台
        pytest.skip("All platforms are registered")

    def test_singleton(self) -> None:
        """测试注册表是单例。"""
        r1 = AdapterRegistry()
        r2 = AdapterRegistry()
        assert r1 is r2
