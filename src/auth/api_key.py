"""
API Token 校验模块。

Description:
    提供 token 注册表解析、哈希、提取与验证功能。
    支持 HTTP Bearer Token、X-API-Key 头以及 WebSocket 查询参数/头鉴权。
@author ganjianfei
@version 1.0.0
2026-06-15
"""

import hashlib
import json
import secrets

from fastapi import HTTPException, Request, WebSocket

from src.auth.context import AuthContext, TokenPrincipal
from src.config.settings import Settings, get_settings


def hash_token(raw_token: str) -> str:
    """对原始 token 进行 sha256 哈希，返回 hex 字符串。

    Args:
        raw_token: 原始 token 字符串。

    Returns:
        sha256 hex 摘要。
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def parse_token_registry(raw_json: str) -> dict[str, TokenPrincipal]:
    """解析 token 注册表 JSON 字符串。

    注册表 entries 必须包含 ``token_hash`` 字段（sha256 hex），不接受明文 ``token``。
    非法 JSON 会 fail closed：抛出 HTTP 503。

    Args:
        raw_json: JSON 格式的 token 注册表字符串。

    Returns:
        token_hash -> TokenPrincipal 的映射字典。

    Raises:
        HTTPException: 503 当 JSON 解析失败时。
    """
    try:
        entries = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=503,
            detail="Token registry is unavailable",
        ) from e

    if not isinstance(entries, list):
        raise HTTPException(
            status_code=503,
            detail="Token registry is unavailable",
        )

    registry: dict[str, TokenPrincipal] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise HTTPException(
                status_code=503,
                detail="Token registry is unavailable",
            )
        token_hash = entry.get("token_hash", "")
        if not token_hash:
            raise HTTPException(
                status_code=503,
                detail="Token registry is unavailable",
            )
        registry[token_hash] = TokenPrincipal(
            token_hash=token_hash,
            tenant_id=entry.get("tenant_id", ""),
            user_id=entry.get("user_id", ""),
            scopes=entry.get("scopes", []),
        )
    return registry


def extract_request_token(request: Request) -> str | None:
    """从 HTTP 请求中提取 API token。

    优先从 Authorization: Bearer <token> 提取，其次从 X-API-Key 头。

    Args:
        request: FastAPI Request 对象。

    Returns:
        提取到的 token 字符串，如果未找到则返回 None。
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :]
    x_api_key = request.headers.get("x-api-key", "")
    if x_api_key:
        return x_api_key
    return None


def verify_api_token(
    raw_token: str, registry: dict[str, TokenPrincipal], settings: Settings
) -> AuthContext:
    """验证 API token 并返回 AuthContext。

    对 raw_token 进行 sha256 哈希后使用 secrets.compare_digest 恒定时间比较。

    Args:
        raw_token: 原始 token 字符串。
        registry: token_hash -> TokenPrincipal 的注册表。
        settings: 应用配置（未直接使用，保留用于扩展）。

    Returns:
        认证后的 AuthContext。

    Raises:
        HTTPException: 401 当 token 无效时。
    """
    token_digest = hash_token(raw_token)
    for token_hash, principal in registry.items():
        if secrets.compare_digest(token_digest, token_hash):
            return AuthContext(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                scopes=list(principal.scopes),
            )
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API token",
    )


def extract_websocket_token(websocket: WebSocket, allow_query: bool = True) -> str | None:
    """从 WebSocket 连接中提取 API token。

    优先从 Authorization Bearer 头提取，其次从 X-API-Key 头提取。
    如果 allow_query 为 True，还会尝试查询参数 access_token 或 api_key。

    Args:
        websocket: FastAPI WebSocket 对象。
        allow_query: 是否允许从查询参数提取 token。

    Returns:
        提取到的 token 字符串，如果未找到则返回 None。
    """
    # HTTP headers: Bearer 优先
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :]
    x_api_key = websocket.headers.get("x-api-key", "")
    if x_api_key:
        return x_api_key
    # Query params
    if allow_query:
        for param_name in ("access_token", "api_key", "token"):
            val = websocket.query_params.get(param_name)
            if val:
                return val
    return None


def _get_registry(settings: Settings) -> dict[str, TokenPrincipal]:
    """获取（缓存）token 注册表。

    Args:
        settings: 应用配置。

    Returns:
        token_hash -> TokenPrincipal 的映射字典。

    Raises:
        HTTPException: 503 当 JSON 解析失败时。
    """
    return parse_token_registry(settings.auth_api_tokens_json)


async def require_auth(request: Request, settings: Settings | None = None) -> AuthContext:
    """FastAPI 依赖：验证 HTTP 请求的 API token。

    当 auth_enabled=False 时返回开发模式 AuthContext。
    当 auth_enabled=True 时校验 token 注册表。

    Args:
        request: FastAPI Request 对象。
        settings: 应用配置。如果为 None 则从 get_settings() 获取。

    Returns:
        认证后的 AuthContext。

    Raises:
        HTTPException: 401 当 token 缺失或无效时。
        HTTPException: 503 当 token 注册表不可用时。
    """
    if settings is None:
        settings = get_settings()

    if not settings.auth_enabled:
        return AuthContext(tenant_id="dev", user_id="dev", scopes=["*"])

    raw_token = extract_request_token(request)
    if raw_token is None:
        raise HTTPException(
            status_code=401,
            detail="Missing API token. Provide Authorization: Bearer <token> or X-API-Key header.",
        )

    registry = _get_registry(settings)
    return verify_api_token(raw_token, registry, settings)


def authenticate_websocket(websocket: WebSocket, settings: Settings | None = None) -> AuthContext:
    """WebSocket 鉴权。

    同步执行，从 WebSocket 头或查询参数提取并验证 token。

    Args:
        websocket: FastAPI WebSocket 对象。
        settings: 应用配置。如果为 None 则从 get_settings() 获取。

    Returns:
        认证后的 AuthContext。

    Raises:
        HTTPException: 401 当 token 缺失或无效时。
        HTTPException: 503 当 token 注册表不可用时。
    """
    if settings is None:
        settings = get_settings()

    if not settings.auth_enabled:
        return AuthContext(tenant_id="dev", user_id="dev", scopes=["*"])

    raw_token = extract_websocket_token(websocket, allow_query=settings.auth_allow_ws_query_token)
    if raw_token is None:
        raise HTTPException(
            status_code=401,
            detail="Missing API token for WebSocket connection.",
        )

    registry = _get_registry(settings)
    return verify_api_token(raw_token, registry, settings)
