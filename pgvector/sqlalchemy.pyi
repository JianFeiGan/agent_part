"""
Type stub for optional third-party dependency.

Description:
    Minimal stub so mypy strict can type-check lazy imports.
    Not a runtime package — Python never imports this file.
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from typing import Any
from sqlalchemy.types import TypeEngine

class Vector(TypeEngine[Any]):
    def __init__(self, dim: int | None = None) -> None: ...
