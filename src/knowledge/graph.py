"""知识图谱数据结构（占位实现）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeGraph:
    """知识图谱实例。

    Attributes:
        id: 图谱 ID。
        name: 图谱名称。
        tenant_id: 租户 ID。
    """

    id: str
    name: str
    tenant_id: str
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
