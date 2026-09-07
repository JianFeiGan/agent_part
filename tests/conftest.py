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


@pytest.fixture(autouse=True)
def _disable_real_media_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认禁用测试中的真实外部调用（媒体 Provider 与懒加载 LLM）。

    - 图片/视频：Generator 自建会话读取 model_providers 表；本机开发库
      可能种有真实厂商配置，会导致测试发起真实网络调用。统一返回 None
      使生成器走 mock 占位路径。
    - LLM：BaseAgent._create_llm 懒加载会读本机 .env 的真实 Key 并发起
      真实调用（叠加重试后极慢）。改为直接抛 ImportError，Agent 走与
      "未配置 Provider" 一致的兜底分支。
    需要验证真实路径的用例可在测试体内自行 patch 覆盖本夹具。
    """
    from unittest.mock import AsyncMock

    from src.agents.base import BaseAgent
    from src.clients.provider_factory import ProviderFactory

    monkeypatch.setattr(
        ProviderFactory, "get_image_provider", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        ProviderFactory, "get_video_provider", AsyncMock(return_value=None)
    )

    def _no_llm(self: BaseAgent) -> None:
        raise ImportError("LLM 在测试中被禁用（conftest._disable_real_media_providers）")

    monkeypatch.setattr(BaseAgent, "_create_llm", _no_llm)


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟环境变量。"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test_api_key")
    monkeypatch.setenv("KLING_API_KEY", "test_kling_key")
