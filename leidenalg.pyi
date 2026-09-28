"""
Type stub for optional third-party dependency.

Description:
    Minimal stub so mypy strict can type-check lazy imports.
    Not a runtime package — Python never imports this file.
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from typing import Iterator

class ModularityVertexPartition:
    def __init__(self, *args: object, **kwargs: object) -> None: ...

class Partition:
    def __iter__(self) -> Iterator[list[int]]: ...

def find_partition(graph: object, partition_type: object, *args: object, **kwargs: object) -> Partition: ...
