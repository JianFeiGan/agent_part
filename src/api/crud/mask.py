"""
敏感值脱敏。

Description:
    收敛此前两种并存的脱敏实现：model_providers.py 的"前4后4"与
    adapter_config.py 的整体 "***"。字段知识（哪个字段需要脱敏）留在
    Pydantic schema 层，这里只提供策略函数。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from collections.abc import Mapping


def mask_secret(value: str | None, *, keep: int = 4, token: str = "****") -> str:
    """保留首尾各 keep 位、中间打码。

    Args:
        value: 原始字符串；None 或空串返回空串。
        keep: 首尾各保留的字符数。
        token: 打码占位符。

    Returns:
        脱敏后的字符串。长度不超过 2*keep 时整体打码，避免泄漏。
    """
    if not value:
        return ""
    if len(value) <= keep * 2:
        return token
    return f"{value[:keep]}{token}{value[-keep:]}"


def mask_values(values: Mapping[str, object] | None, *, token: str = "***") -> dict[str, str]:
    """键保留、值整体打码。

    Args:
        values: 原始键值映射；None 返回空字典。
        token: 打码占位符。

    Returns:
        打码后的新字典（不修改原映射）。
    """
    if not values:
        return {}
    return dict.fromkeys(values, token)
