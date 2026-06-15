"""
Auth 模块。

提供 AuthContext、TokenPrincipal、Token 解析和 API 鉴权功能。
"""

from src.auth.api_key import (
    authenticate_websocket,
    extract_request_token,
    extract_websocket_token,
    hash_token,
    parse_token_registry,
    require_auth,
    verify_api_token,
)
from src.auth.context import AuthContext, TokenPrincipal

__all__ = [
    "AuthContext",
    "TokenPrincipal",
    "authenticate_websocket",
    "extract_request_token",
    "extract_websocket_token",
    "hash_token",
    "parse_token_registry",
    "require_auth",
    "verify_api_token",
]
