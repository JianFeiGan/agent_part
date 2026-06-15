"""
AuthContext 定义。

Description:
    提供租户感知的 AuthContext 模型和 TokenPrincipal，用于在请求生命周期中传递认证信息。
@author ganjianfei
@version 1.0.0
2026-06-15
"""

from pydantic import BaseModel, Field


class TokenPrincipal:
    """Token 主体信息，记录 token 哈希与关联的租户/用户/权限。"""

    def __init__(self, token_hash: str, tenant_id: str, user_id: str, scopes: list[str]) -> None:
        """初始化 TokenPrincipal。

        Args:
            token_hash: token 的 sha256 hex。
            tenant_id: 租户标识。
            user_id: 用户标识。
            scopes: 权限范围列表。
        """
        self.token_hash = token_hash
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.scopes = scopes


class AuthContext(BaseModel):
    """认证上下文，携带租户、用户和权限范围信息。

    Attributes:
        tenant_id: 租户标识。
        user_id: 用户标识。
        scopes: 权限范围列表。
    """

    tenant_id: str = Field(description="租户标识")
    user_id: str = Field(description="用户标识")
    scopes: list[str] = Field(default_factory=list, description="权限范围列表")

    def has_scope(self, scope: str) -> bool:
        """检查是否拥有指定 scope。

        Args:
            scope: 待检查的权限范围。

        Returns:
            如果拥有该 scope 或拥有通配符 "*" 则返回 True。
        """
        if "*" in self.scopes:
            return True
        return scope in self.scopes
