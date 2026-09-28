"""
Type stub for optional third-party dependency.

Description:
    Minimal stub so mypy strict can type-check lazy imports.
    Not a runtime package — Python never imports this file.
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from typing import Protocol, overload

class _EncodedVector(Protocol):
    def tolist(self) -> list[float]: ...

class _EncodedBatch(Protocol):
    def __iter__(self) -> object: ...

class SentenceTransformer:
    def __init__(self, model_name_or_path: str, device: str | None = None) -> None: ...
    @overload
    def encode(
        self,
        sentences: str,
        *,
        batch_size: int = ...,
        normalize_embeddings: bool = ...,
        show_progress_bar: bool = ...,
    ) -> _EncodedVector: ...
    @overload
    def encode(
        self,
        sentences: list[str],
        *,
        batch_size: int = ...,
        normalize_embeddings: bool = ...,
        show_progress_bar: bool = ...,
    ) -> _EncodedBatch: ...
    def get_sentence_embedding_dimension(self) -> int: ...
