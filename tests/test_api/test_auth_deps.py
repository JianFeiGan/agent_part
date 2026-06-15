"""
Auth 依赖注入测试。

Description:
    测试 AuthContext、TokenPrincipal、token 提取/验证、require_auth 等。
@author ganjianfei
@version 1.0.0
2026-06-15
"""

import hashlib
import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

# ==================== Fixtures ====================


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture
def token_registry_raw() -> str:
    """合法的 token registry JSON（使用 token_hash 字段）。"""
    return json.dumps(
        [
            {
                "token_hash": _hash("sk-test-token-001"),
                "tenant_id": "tenant_a",
                "user_id": "user_1",
                "scopes": ["read", "write"],
            },
            {
                "token_hash": _hash("sk-test-token-002"),
                "tenant_id": "tenant_b",
                "user_id": "user_2",
                "scopes": ["read"],
            },
        ]
    )


@pytest.fixture
def settings_with_auth() -> MagicMock:
    """启用鉴权的 Settings mock（使用 token_hash 字段）。"""
    s = MagicMock()
    s.auth_enabled = True
    s.auth_api_tokens_json = json.dumps(
        [
            {
                "token_hash": _hash("sk-test-token-001"),
                "tenant_id": "tenant_a",
                "user_id": "user_1",
                "scopes": ["read", "write"],
            },
        ]
    )
    s.auth_allow_ws_query_token = True
    s.cors_allow_origins = "http://localhost:5173,http://localhost:3000"
    s.credentials_encryption_key = "test-key"
    return s


@pytest.fixture
def settings_no_auth() -> MagicMock:
    """禁用鉴权的 Settings mock。"""
    s = MagicMock()
    s.auth_enabled = False
    s.auth_api_tokens_json = "[]"
    s.auth_allow_ws_query_token = True
    s.cors_allow_origins = ""
    s.credentials_encryption_key = ""
    return s


# ==================== AuthContext ====================


class TestAuthContext:
    """AuthContext 单元测试。"""

    def test_create_auth_context(self) -> None:
        """测试创建 AuthContext。"""
        from src.auth.context import AuthContext

        ctx = AuthContext(
            tenant_id="tenant_a",
            user_id="user_1",
            scopes=["read", "write"],
        )
        assert ctx.tenant_id == "tenant_a"
        assert ctx.user_id == "user_1"
        assert ctx.scopes == ["read", "write"]

    def test_default_scopes_is_empty_list(self) -> None:
        """测试 AuthContext 默认 scopes 为空列表。"""
        from src.auth.context import AuthContext

        ctx = AuthContext(tenant_id="t", user_id="u")
        assert ctx.scopes == []

    def test_has_scope_true(self) -> None:
        """测试 has_scope 返回 True。"""
        from src.auth.context import AuthContext

        ctx = AuthContext(
            tenant_id="tenant_a",
            user_id="user_1",
            scopes=["read", "write"],
        )
        assert ctx.has_scope("read") is True
        assert ctx.has_scope("write") is True

    def test_has_scope_false(self) -> None:
        """测试 has_scope 返回 False。"""
        from src.auth.context import AuthContext

        ctx = AuthContext(
            tenant_id="tenant_a",
            user_id="user_1",
            scopes=["read"],
        )
        assert ctx.has_scope("admin") is False

    def test_has_scope_wildcard(self) -> None:
        """测试通配符 scope。"""
        from src.auth.context import AuthContext

        ctx = AuthContext(
            tenant_id="tenant_a",
            user_id="user_1",
            scopes=["*"],
        )
        assert ctx.has_scope("anything") is True

    def test_dev_context(self) -> None:
        """测试开发模式 AuthContext。"""
        from src.auth.context import AuthContext

        ctx = AuthContext(tenant_id="dev", user_id="dev", scopes=["*"])
        assert ctx.tenant_id == "dev"
        assert ctx.user_id == "dev"
        assert ctx.has_scope("*") is True


# ==================== TokenPrincipal ====================


class TestTokenPrincipal:
    """TokenPrincipal 单元测试。"""

    def test_create_token_principal(self) -> None:
        """测试创建 TokenPrincipal。"""
        from src.auth.context import TokenPrincipal

        tp = TokenPrincipal(
            token_hash="abc123",
            tenant_id="tenant_a",
            user_id="user_1",
            scopes=["read"],
        )
        assert tp.token_hash == "abc123"
        assert tp.tenant_id == "tenant_a"
        assert tp.user_id == "user_1"
        assert tp.scopes == ["read"]


# ==================== hash_token ====================


class TestHashToken:
    """hash_token 函数测试。"""

    def test_hash_token_returns_sha256_hex(self) -> None:
        """测试 hash_token 返回 sha256 hex。"""
        from src.auth.api_key import hash_token

        result = hash_token("hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert result == expected

    def test_hash_token_deterministic(self) -> None:
        """测试 hash_token 确定性。"""
        from src.auth.api_key import hash_token

        assert hash_token("token") == hash_token("token")

    def test_hash_token_different_for_different_inputs(self) -> None:
        """测试不同输入产生不同哈希。"""
        from src.auth.api_key import hash_token

        assert hash_token("token_a") != hash_token("token_b")


# ==================== parse_token_registry ====================


class TestParseTokenRegistry:
    """parse_token_registry 测试。"""

    def test_parse_valid_registry(self, token_registry_raw: str) -> None:
        """测试解析合法的 registry（token_hash 字段）。"""
        from src.auth.api_key import hash_token, parse_token_registry

        registry = parse_token_registry(token_registry_raw)

        assert isinstance(registry, dict)
        assert len(registry) == 2

        hash_001 = hash_token("sk-test-token-001")
        assert hash_001 in registry
        assert registry[hash_001].tenant_id == "tenant_a"
        assert registry[hash_001].user_id == "user_1"
        assert registry[hash_001].scopes == ["read", "write"]

    def test_parse_registry_missing_token_hash_raises_503(self) -> None:
        """测试 registry entry 缺少 token_hash 时抛出 503（fail closed）。"""
        from src.auth.api_key import parse_token_registry

        raw = json.dumps(
            [
                {
                    "token": "sk-plaintext-token",
                    "tenant_id": "tenant_x",
                    "user_id": "user_x",
                    "scopes": ["read"],
                },
            ]
        )
        with pytest.raises(HTTPException) as exc_info:
            parse_token_registry(raw)
        assert exc_info.value.status_code == 503

    def test_parse_registry_empty_token_hash_raises_503(self) -> None:
        """测试 registry entry 的 token_hash 为空字符串时抛出 503。"""
        from src.auth.api_key import parse_token_registry

        raw = json.dumps(
            [
                {
                    "token_hash": "",
                    "tenant_id": "tenant_x",
                    "user_id": "user_x",
                    "scopes": ["read"],
                },
            ]
        )
        with pytest.raises(HTTPException) as exc_info:
            parse_token_registry(raw)
        assert exc_info.value.status_code == 503

    def test_parse_registry_plaintext_token_cannot_authenticate(self) -> None:
        """测试 registry 仅有明文 token 字段时 parse_token_registry 直接抛 503。"""
        from src.auth.api_key import parse_token_registry

        raw = json.dumps(
            [
                {
                    "token": "sk-plaintext-token",
                    "tenant_id": "tenant_x",
                    "user_id": "user_x",
                    "scopes": ["read"],
                },
            ]
        )
        with pytest.raises(HTTPException) as exc_info:
            parse_token_registry(raw)
        assert exc_info.value.status_code == 503

    def test_parse_invalid_json_raises_503(self) -> None:
        """测试非法 JSON 抛出 503。"""
        from src.auth.api_key import parse_token_registry

        with pytest.raises(HTTPException) as exc_info:
            parse_token_registry("not valid json")

        assert exc_info.value.status_code == 503

    def test_parse_object_not_list_raises_503(self) -> None:
        """测试合法 JSON 但顶层是对象 {} 时抛出 503。"""
        from src.auth.api_key import parse_token_registry

        with pytest.raises(HTTPException) as exc_info:
            parse_token_registry("{}")

        assert exc_info.value.status_code == 503

    def test_parse_list_of_strings_raises_503(self) -> None:
        """测试合法 JSON 但顶层是字符串列表 ["bad"] 时抛出 503。"""
        from src.auth.api_key import parse_token_registry

        with pytest.raises(HTTPException) as exc_info:
            parse_token_registry('["bad"]')

        assert exc_info.value.status_code == 503

    def test_parse_empty_registry(self) -> None:
        """测试解析空数组 registry。"""
        from src.auth.api_key import parse_token_registry

        registry = parse_token_registry("[]")
        assert registry == {}


# ==================== extract_request_token ====================


class TestExtractRequestToken:
    """extract_request_token 测试。"""

    def test_extract_bearer_token(self) -> None:
        """测试从 Authorization Bearer 头提取 token。"""
        from src.auth.api_key import extract_request_token

        request = MagicMock()
        request.headers = {"authorization": "Bearer sk-my-token"}

        token = extract_request_token(request)
        assert token == "sk-my-token"

    def test_extract_x_api_key(self) -> None:
        """测试从 X-API-Key 头提取 token。"""
        from src.auth.api_key import extract_request_token

        request = MagicMock()
        request.headers = {"x-api-key": "sk-my-api-key"}

        token = extract_request_token(request)
        assert token == "sk-my-api-key"

    def test_extract_bearer_preferred_over_x_api_key(self) -> None:
        """测试 Bearer 优先级高于 X-API-Key。"""
        from src.auth.api_key import extract_request_token

        request = MagicMock()
        request.headers = {
            "authorization": "Bearer sk-bearer-token",
            "x-api-key": "sk-api-key",
        }

        token = extract_request_token(request)
        assert token == "sk-bearer-token"

    def test_extract_no_token_returns_none(self) -> None:
        """测试无 token 头返回 None。"""
        from src.auth.api_key import extract_request_token

        request = MagicMock()
        request.headers = {}

        token = extract_request_token(request)
        assert token is None

    def test_extract_malformed_bearer_returns_none(self) -> None:
        """测试不规范的 Bearer 头返回 None。"""
        from src.auth.api_key import extract_request_token

        request = MagicMock()
        request.headers = {"authorization": "NotBearer sk-token"}

        token = extract_request_token(request)
        assert token is None


# ==================== verify_api_token ====================


class TestVerifyApiToken:
    """verify_api_token 测试。"""

    def test_verify_valid_token(
        self, token_registry_raw: str, settings_with_auth: MagicMock
    ) -> None:
        """测试验证合法 token 返回 AuthContext（token_hash registry）。"""
        from src.auth.api_key import parse_token_registry, verify_api_token

        registry = parse_token_registry(token_registry_raw)

        ctx = verify_api_token(
            raw_token="sk-test-token-001",
            registry=registry,
            settings=settings_with_auth,
        )
        assert ctx.tenant_id == "tenant_a"
        assert ctx.user_id == "user_1"
        assert ctx.scopes == ["read", "write"]

    def test_verify_invalid_token_raises_401(
        self, token_registry_raw: str, settings_with_auth: MagicMock
    ) -> None:
        """测试验证非法 token 抛出 401。"""
        from src.auth.api_key import parse_token_registry, verify_api_token

        registry = parse_token_registry(token_registry_raw)

        with pytest.raises(HTTPException) as exc_info:
            verify_api_token(
                raw_token="sk-wrong-token",
                registry=registry,
                settings=settings_with_auth,
            )
        assert exc_info.value.status_code == 401

    def test_verify_empty_registry_raises_401(self, settings_with_auth: MagicMock) -> None:
        """测试空 registry 抛出 401。"""
        from src.auth.api_key import verify_api_token

        with pytest.raises(HTTPException) as exc_info:
            verify_api_token(
                raw_token="sk-any-token",
                registry={},
                settings=settings_with_auth,
            )
        assert exc_info.value.status_code == 401


# ==================== require_auth ====================


class TestRequireAuth:
    """require_auth 依赖注入测试。"""

    @pytest.mark.asyncio
    async def test_require_auth_missing_token_raises_401(
        self, settings_with_auth: MagicMock
    ) -> None:
        """测试缺少 token 抛出 401。"""
        from unittest.mock import patch

        from src.auth.api_key import require_auth

        request = MagicMock()
        request.headers = {}

        with patch("src.auth.api_key.get_settings", return_value=settings_with_auth):
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(request=request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_auth_bearer_succeeds(self, settings_with_auth: MagicMock) -> None:
        """测试 Bearer token 鉴权成功。"""
        from unittest.mock import patch

        from src.auth.api_key import require_auth

        request = MagicMock()
        request.headers = {"authorization": "Bearer sk-test-token-001"}

        with patch("src.auth.api_key.get_settings", return_value=settings_with_auth):
            ctx = await require_auth(request=request)
            assert ctx.tenant_id == "tenant_a"
            assert ctx.user_id == "user_1"

    @pytest.mark.asyncio
    async def test_require_auth_disabled_returns_dev_context(
        self, settings_no_auth: MagicMock
    ) -> None:
        """测试鉴权禁用时返回 dev AuthContext。"""
        from unittest.mock import patch

        from src.auth.api_key import require_auth

        request = MagicMock()
        request.headers = {}

        with patch("src.auth.api_key.get_settings", return_value=settings_no_auth):
            ctx = await require_auth(request=request)
            assert ctx.tenant_id == "dev"
            assert ctx.user_id == "dev"
            assert ctx.scopes == ["*"]

    @pytest.mark.asyncio
    async def test_require_auth_invalid_registry_raises_503(
        self, settings_with_auth: MagicMock
    ) -> None:
        """测试非法 registry JSON 抛出 503。"""
        from unittest.mock import patch

        from src.auth.api_key import require_auth

        settings_with_auth.auth_api_tokens_json = "not valid json {{{"

        request = MagicMock()
        request.headers = {"authorization": "Bearer sk-test-token-001"}

        with patch("src.auth.api_key.get_settings", return_value=settings_with_auth):
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(request=request)
            assert exc_info.value.status_code == 503


# ==================== extract_websocket_token ====================


class TestExtractWebsocketToken:
    """extract_websocket_token 测试。"""

    def test_extract_ws_query_access_token(self) -> None:
        """测试从 WebSocket 查询参数 access_token 提取 token。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {"access_token": "sk-ws-access-token"}

        token = extract_websocket_token(ws, allow_query=True)
        assert token == "sk-ws-access-token"

    def test_extract_ws_query_api_key(self) -> None:
        """测试从 WebSocket 查询参数 api_key 提取 token。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {"api_key": "sk-ws-api-key"}

        token = extract_websocket_token(ws, allow_query=True)
        assert token == "sk-ws-api-key"

    def test_extract_ws_query_token(self) -> None:
        """测试从 WebSocket 查询参数 token 提取 token。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {"token": "sk-ws-token"}

        token = extract_websocket_token(ws, allow_query=True)
        assert token == "sk-ws-token"

    def test_extract_ws_query_access_token_preferred(self) -> None:
        """测试 access_token 优先级高于其他 query params。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {
            "access_token": "sk-priority",
            "api_key": "sk-other",
            "token": "sk-legacy",
        }

        token = extract_websocket_token(ws, allow_query=True)
        assert token == "sk-priority"

    def test_extract_ws_header_bearer_token(self) -> None:
        """测试从 WebSocket Authorization Bearer 头提取 token。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {"authorization": "Bearer sk-ws-header-token"}
        ws.query_params = {}

        token = extract_websocket_token(ws, allow_query=True)
        assert token == "sk-ws-header-token"

    def test_extract_ws_header_x_api_key(self) -> None:
        """测试从 WebSocket X-API-Key 头提取 token。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {"x-api-key": "sk-ws-x-api-key"}
        ws.query_params = {}

        token = extract_websocket_token(ws, allow_query=True)
        assert token == "sk-ws-x-api-key"

    def test_extract_ws_header_priority_over_query(self) -> None:
        """测试 WebSocket header Bearer 优先级高于 query params。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {"authorization": "Bearer sk-header-token"}
        ws.query_params = {"access_token": "sk-query-token"}

        token = extract_websocket_token(ws, allow_query=True)
        assert token == "sk-header-token"

    def test_extract_ws_query_disabled(self) -> None:
        """测试禁用查询参数时忽略 query token。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {"token": "sk-ws-token"}

        token = extract_websocket_token(ws, allow_query=False)
        assert token is None

    def test_extract_ws_no_token_returns_none(self) -> None:
        """测试无 token 返回 None。"""
        from src.auth.api_key import extract_websocket_token

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {}

        token = extract_websocket_token(ws, allow_query=True)
        assert token is None


# ==================== authenticate_websocket ====================


class TestAuthenticateWebsocket:
    """authenticate_websocket 测试。"""

    def test_authenticate_ws_success(self, settings_with_auth: MagicMock) -> None:
        """测试 WebSocket 鉴权成功。"""
        from unittest.mock import patch

        from src.auth.api_key import authenticate_websocket

        ws = MagicMock()
        ws.headers = {"authorization": "Bearer sk-test-token-001"}
        ws.query_params = {}

        with patch("src.auth.api_key.get_settings", return_value=settings_with_auth):
            ctx = authenticate_websocket(ws)
            assert ctx.tenant_id == "tenant_a"
            assert ctx.user_id == "user_1"

    def test_authenticate_ws_missing_token_raises_401(self, settings_with_auth: MagicMock) -> None:
        """测试 WebSocket 无 token 抛出 401。"""
        from unittest.mock import patch

        from src.auth.api_key import authenticate_websocket

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {}

        with patch("src.auth.api_key.get_settings", return_value=settings_with_auth):
            with pytest.raises(HTTPException) as exc_info:
                authenticate_websocket(ws)
            assert exc_info.value.status_code == 401

    def test_authenticate_ws_disabled_returns_dev_context(
        self, settings_no_auth: MagicMock
    ) -> None:
        """测试鉴权禁用时 WebSocket 返回 dev context。"""
        from unittest.mock import patch

        from src.auth.api_key import authenticate_websocket

        ws = MagicMock()
        ws.headers = {}
        ws.query_params = {}

        with patch("src.auth.api_key.get_settings", return_value=settings_no_auth):
            ctx = authenticate_websocket(ws)
            assert ctx.tenant_id == "dev"
            assert ctx.user_id == "dev"
            assert ctx.scopes == ["*"]
