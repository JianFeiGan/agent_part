"""
测试配置。
"""

import pytest


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟环境变量。"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test_api_key")
    monkeypatch.setenv("KLING_API_KEY", "test_kling_key")
