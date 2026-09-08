"""
鉴权策略函数。

Description:
    scope 校验与租户解析的唯一实现，替换此前散落在 5 个 router 文件中的
    逐字重复拷贝。语义与原实现逐字一致：any-of 命中即通过（含 "*" 通配），
    全不命中抛 403 "Forbidden"。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from fastapi import HTTPException

from src.auth.context import AuthContext


def require_scope(auth: AuthContext | None, *scopes: str) -> None:
    """检查 auth 是否拥有指定 scope 之一，否则抛 403。

    遍历 scopes，任一 scope 满足 ``auth.has_scope(scope)``（含 "*" 通配）即通过。
    若全部不满足，抛出 HTTPException(status_code=403, detail="Forbidden")。

    Args:
        auth: 认证上下文；None 时放行——HTTP 路径上 require_auth 永不返回
            None（AUTH_ENABLED=false 时返回 dev 通配上下文），None 只可能
            出现在绕过 HTTP 的直调（测试/脚本）。
        *scopes: 一个或多个 scope 名称。

    Raises:
        HTTPException: 403 当 scope 不足时。
    """
    if auth is None:
        return
    for scope in scopes:
        if auth.has_scope(scope):
            return
    raise HTTPException(status_code=403, detail="Forbidden")


def resolve_tenant(auth: AuthContext | None, *, default: str = "default") -> str:
    """从 auth 解析租户 ID，auth 为 None 时回退默认值。

    Args:
        auth: 认证上下文。
        default: auth 为 None 时的回退租户（默认 "default"，与 knowledge.py
            现状一致；AUTH_ENABLED=false 时 require_auth 返回 "dev"）。

    Returns:
        租户 ID。
    """
    if auth is None:
        return default
    return auth.tenant_id
