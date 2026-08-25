"""
测试配置。
"""

import pytest


@pytest.fixture(autouse=True)
def _test_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """将测试环境与代码默认值对齐，屏蔽本机 .env 的偶然覆盖。

    - ALLOW_MOCK_ASSETS=true：生产默认 fail-closed，测试保留占位降级行为
    - RAG_ENABLED=true：与代码默认一致，避免本机 .env 关闭 RAG 影响 Agent 判断
    - AUTH_ENABLED=false：API 测试按免鉴权设计（鉴权行为由专门的结构/单测覆盖）
    实际环境变量优先于 .env 文件；清除缓存保证重新读取。
    """
    from src.config.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ALLOW_MOCK_ASSETS", "true")
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟环境变量。"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test_api_key")
    monkeypatch.setenv("KLING_API_KEY", "test_kling_key")
