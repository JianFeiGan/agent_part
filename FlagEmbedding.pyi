"""
Type stub for optional third-party dependency.

Description:
    Minimal stub so mypy strict can type-check lazy imports.
    Not a runtime package — Python never imports this file.
@author ganjianfei
@version 1.0.0
2026-09-28
"""

class BGEM3FlagModel:
    def __init__(
        self,
        model_name_or_path: str,
        use_fp16: bool = ...,
        device: str | None = ...,
    ) -> None: ...
    def encode(self, *args: object, **kwargs: object) -> object: ...

class FlagReranker:
    def __init__(
        self,
        model_name_or_path: str,
        use_fp16: bool = ...,
        device: str | None = ...,
    ) -> None: ...
    def compute_score(self, *args: object, **kwargs: object) -> object: ...
