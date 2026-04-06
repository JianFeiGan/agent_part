"""
语义分块器。

Description:
    实现文档的智能语义分块，支持固定窗口和语义边界分块。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """文档分块。

    Attributes:
        content: 分块内容。
        index: 分块索引。
        metadata: 分块元数据。
        start_char: 起始字符位置。
        end_char: 结束字符位置。
    """

    content: str
    index: int
    metadata: dict[str, Any]
    start_char: int = 0
    end_char: int = 0


class SemanticChunker:
    """语义分块器。

    将文档分割为适合向量检索的分块。

    Example:
        >>> chunker = SemanticChunker()
        >>> chunks = chunker.split("长文档内容...")
        >>> for chunk in chunks:
        ...     print(chunk.content)
    """

    # 中文句子结束符
    SENTENCE_ENDINGS_ZH = ["。", "！", "？", "；", "\n"]
    # 英文句子结束符
    SENTENCE_ENDINGS_EN = [".", "!", "?", ";", "\n"]

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        """初始化分块器。

        Args:
            chunk_size: 分块大小 (字符数)，默认使用配置值。
            chunk_overlap: 分块重叠大小 (字符数)，默认使用配置值。
        """
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def split(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """将文本分割为分块。

        使用滑动窗口方式，在句子边界处分块。

        Args:
            text: 输入文本。
            metadata: 每个分块继承的元数据。

        Returns:
            分块列表。
        """
        if not text.strip():
            return []

        metadata = metadata or {}
        chunks = []

        # 预处理：标准化换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        start = 0
        index = 0

        while start < len(text):
            # 计算分块结束位置
            end = min(start + self.chunk_size, len(text))

            # 如果不是文本末尾，尝试在句子边界处断开
            if end < len(text):
                boundary_pos = self._find_sentence_boundary(text, end)
                if boundary_pos > start:
                    end = boundary_pos

            # 提取分块内容
            chunk_content = text[start:end].strip()

            if chunk_content:
                chunks.append(
                    Chunk(
                        content=chunk_content,
                        index=index,
                        metadata=metadata.copy(),
                        start_char=start,
                        end_char=end,
                    )
                )
                index += 1

            # 移动到下一个分块起始位置（考虑重叠）
            next_start = end - self.chunk_overlap
            if next_start <= start:
                next_start = end  # 避免无限循环

            start = next_start

        logger.info(
            f"Split text into {len(chunks)} chunks (size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        return chunks

    def split_by_semantic(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """按语义边界分割文本。

        先按段落分割，再按句子分割，最后按固定大小分割。

        Args:
            text: 输入文本。
            metadata: 每个分块继承的元数据。

        Returns:
            分块列表。
        """
        if not text.strip():
            return []

        metadata = metadata or {}
        chunks = []

        # 按段落分割
        paragraphs = re.split(r"\n\s*\n", text)

        current_chunk = ""
        current_start = 0
        index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果段落本身超过 chunk_size，需要进一步分割
            if len(para) > self.chunk_size:
                # 先保存当前累积的内容
                if current_chunk:
                    chunks.append(
                        Chunk(
                            content=current_chunk.strip(),
                            index=index,
                            metadata=metadata.copy(),
                            start_char=current_start,
                            end_char=current_start + len(current_chunk),
                        )
                    )
                    index += 1
                    current_chunk = ""

                # 分割大段落
                para_chunks = self.split(para, metadata)
                for pc in para_chunks:
                    pc.index = index
                    chunks.append(pc)
                    index += 1

            # 如果加入这个段落会超过限制，先保存当前内容
            elif len(current_chunk) + len(para) + 2 > self.chunk_size:
                if current_chunk:
                    chunks.append(
                        Chunk(
                            content=current_chunk.strip(),
                            index=index,
                            metadata=metadata.copy(),
                            start_char=current_start,
                            end_char=current_start + len(current_chunk),
                        )
                    )
                    index += 1

                current_chunk = para
                current_start = text.find(para, current_start)

            else:
                # 加入当前段落
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                    current_start = text.find(para)

        # 保存最后的内容
        if current_chunk:
            chunks.append(
                Chunk(
                    content=current_chunk.strip(),
                    index=index,
                    metadata=metadata.copy(),
                    start_char=current_start,
                    end_char=current_start + len(current_chunk),
                )
            )

        logger.info(f"Semantic split produced {len(chunks)} chunks")
        return chunks

    def _find_sentence_boundary(self, text: str, position: int) -> int:
        """在指定位置附近查找句子边界。

        Args:
            text: 文本内容。
            position: 目标位置。

        Returns:
            句子边界位置，如果未找到则返回 position。
        """
        # 向后查找最近的句子结束符
        search_range = min(200, len(text) - position)  # 最多向后查找200字符

        for i in range(position, min(position + search_range, len(text))):
            if text[i] in self.SENTENCE_ENDINGS_ZH + self.SENTENCE_ENDINGS_EN:
                return i + 1

        # 向前查找最近的句子结束符
        for i in range(position, max(0, position - search_range), -1):
            if text[i] in self.SENTENCE_ENDINGS_ZH + self.SENTENCE_ENDINGS_EN:
                return i + 1

        return position
