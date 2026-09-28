"""
Type stub for optional third-party dependency.

Description:
    Minimal stub so mypy strict can type-check lazy imports.
    Not a runtime package — Python never imports this file.
@author ganjianfei
@version 1.0.0
2026-09-28
"""

class _Cuda:
    @staticmethod
    def is_available() -> bool: ...

cuda: _Cuda
