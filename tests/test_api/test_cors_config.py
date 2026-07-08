"""
CORS 配置测试。

测试 CORS 来源解析和 CORS 配置验证逻辑。
"""

import pytest

from src.config.settings import Settings


class TestCorsOrigins:
    """CORS 来源解析测试。"""

    def test_cors_origins_parses_comma_separated(self) -> None:
        """测试逗号分隔的 CORS 来源正确解析为列表。"""
        settings = Settings(cors_allow_origins="http://localhost:3000,https://app.example.com")
        assert settings.cors_origins == [
            "http://localhost:3000",
            "https://app.example.com",
        ]

    def test_cors_origins_empty_string_returns_empty_list(self) -> None:
        """测试空字符串返回空列表。"""
        settings = Settings(cors_allow_origins="")
        assert settings.cors_origins == []

    def test_cors_origins_trims_whitespace(self) -> None:
        """测试来源值去除首尾空格。"""
        settings = Settings(cors_allow_origins=" http://localhost:3000 , https://app.example.com ")
        assert settings.cors_origins == [
            "http://localhost:3000",
            "https://app.example.com",
        ]


class TestValidateCorsSettings:
    """CORS 配置验证测试。"""

    def test_wildcard_raises_runtime_error(self) -> None:
        """测试通配符 '*' 触发 RuntimeError，错误消息包含 'CORS wildcard'。"""
        from main import validate_cors_settings

        settings = Settings(cors_allow_origins="*")
        with pytest.raises(RuntimeError, match="CORS wildcard"):
            validate_cors_settings(settings)

    def test_wildcard_among_others_raises_runtime_error(self) -> None:
        """测试来源列表中包含 '*' 时触发 RuntimeError。"""
        from main import validate_cors_settings

        settings = Settings(cors_allow_origins="http://localhost:3000,*")
        with pytest.raises(RuntimeError):
            validate_cors_settings(settings)

    def test_empty_origins_raises_runtime_error(self) -> None:
        """测试空来源列表触发 RuntimeError。"""
        from main import validate_cors_settings

        settings = Settings(cors_allow_origins="")
        with pytest.raises(RuntimeError):
            validate_cors_settings(settings)

    def test_localhost_whitelist_passes(self) -> None:
        """测试 localhost 白名单配置通过验证。"""
        from main import validate_cors_settings

        settings = Settings(cors_allow_origins="http://localhost:3000,http://localhost:5173")
        # 不应抛出异常
        validate_cors_settings(settings)

    def test_production_domains_passes(self) -> None:
        """测试生产域名配置通过验证。"""
        from main import validate_cors_settings

        settings = Settings(cors_allow_origins="https://app.example.com,https://admin.example.com")
        # 不应抛出异常
        validate_cors_settings(settings)
