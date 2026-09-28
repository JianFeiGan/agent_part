"""
Type stub for optional third-party dependency.

Description:
    Minimal stub so mypy strict can type-check lazy imports.
    Not a runtime package — Python never imports this file.
@author ganjianfei
@version 1.0.0
2026-09-28
"""

class Graph:
    def __init__(self, n: int = ..., directed: bool = ...) -> None: ...
    def add_edge(self, source: int, target: int) -> None: ...
    def connected_components(self) -> list[list[int]]: ...
