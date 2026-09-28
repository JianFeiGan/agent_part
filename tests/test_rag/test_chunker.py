"""语义分块器行为测试。

覆盖滑动窗口分块、句子边界断句、语义分段与超长段落的二次切分。
"""

from __future__ import annotations

from typing import Any

from src.rag.chunker import Chunk, SemanticChunker

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _chunker(size: int = 50, overlap: int = 5) -> SemanticChunker:
    """构造固定参数的分块器。"""
    return SemanticChunker(chunk_size=size, chunk_overlap=overlap)


class TestSplit:
    """固定窗口分块。"""

    def test_empty_text_returns_empty(self) -> None:
        """空白文本不产块。"""
        assert _chunker().split("   \n\t ") == []

    def test_short_text_single_chunk(self) -> None:
        """短文本产出单块。"""
        chunks = _chunker(size=100, overlap=0).split("这是一段短文本。")

        assert len(chunks) == 1
        assert chunks[0].content == "这是一段短文本。"
        assert chunks[0].index == 0

    def test_long_text_produces_multiple_chunks(self) -> None:
        """长文本按窗口切成多块。"""
        text = "第一句话结束。" * 30
        chunks = _chunker(size=50, overlap=5).split(text)

        assert len(chunks) > 1
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_metadata_copied_to_each_chunk(self) -> None:
        """元数据复制到每个块，互不共享引用。"""
        meta: dict[str, Any] = {"source": "guide"}
        chunks = _chunker(size=20, overlap=0).split("一二三四五六七八九十" * 5, meta)

        assert all(c.metadata == {"source": "guide"} for c in chunks)
        chunks[0].metadata["source"] = "mutated"
        assert chunks[1].metadata["source"] == "guide"

    def test_normalizes_crlf(self) -> None:
        """CRLF 统一为 LF。"""
        chunks = _chunker(size=100).split("a\r\nb\rc")

        assert "\r" not in chunks[0].content

    def test_overlap_avoids_infinite_loop(self) -> None:
        """重叠 >= 分块大小时仍能推进。"""
        chunks = SemanticChunker(chunk_size=10, chunk_overlap=20).split("x" * 50)

        assert len(chunks) >= 2

    def test_breaks_at_sentence_boundary(self) -> None:
        """优先在句子结束符处断开。"""
        text = "第一句话结束。" + "第二句话结束。" + "第三句话结束。"
        chunks = _chunker(size=12, overlap=0).split(text)

        # 每块应以句子结束符收尾（末块除外）
        for chunk in chunks[:-1]:
            assert chunk.content.endswith(("。", "！", "？", "；"))

    def test_positions_are_recorded(self) -> None:
        """记录起止字符位置。"""
        chunks = _chunker(size=20, overlap=0).split("一二三四五六七八九十" * 4)

        assert chunks[0].start_char == 0
        assert chunks[0].end_char > chunks[0].start_char


class TestSplitBySemantic:
    """语义分段。"""

    def test_empty_returns_empty(self) -> None:
        """空白文本不产块。"""
        assert _chunker().split_by_semantic("") == []

    def test_paragraphs_merged_within_limit(self) -> None:
        """短段落合并进同块。"""
        text = "段落一。\n\n段落二。\n\n段落三。"
        chunks = _chunker(size=100, overlap=0).split_by_semantic(text)

        assert len(chunks) == 1
        assert "段落一" in chunks[0].content
        assert "段落三" in chunks[0].content

    def test_oversized_paragraph_split_further(self) -> None:
        """超长段落二次切分为多块。"""
        long_para = "很长的句子。" * 40
        text = f"引言。\n\n{long_para}"
        chunks = _chunker(size=60, overlap=0).split_by_semantic(text)

        assert len(chunks) > 1

    def test_new_chunk_started_when_overflow(self) -> None:
        """加入段落会超限时另起新块。"""
        text = "AAAA\n\nBBBB\n\nCCCC"
        chunks = _chunker(size=8, overlap=0).split_by_semantic(text)

        assert len(chunks) >= 2

    def test_indices_are_sequential(self) -> None:
        """语义分块索引连续。"""
        text = "一。\n\n二。\n\n三。\n\n四。"
        chunks = _chunker(size=6, overlap=0).split_by_semantic(text)

        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_metadata_inherited(self) -> None:
        """语义分块继承元数据。"""
        chunks = _chunker(size=50).split_by_semantic("段落。", {"doc": "d1"})

        assert all(c.metadata == {"doc": "d1"} for c in chunks)

    def test_blank_paragraphs_skipped(self) -> None:
        """空段落被跳过。"""
        chunks = _chunker(size=50).split_by_semantic("正文。\n\n   \n\n更多正文。")

        assert len(chunks) == 1


class TestChunkDataclass:
    """Chunk 数据结构。"""

    def test_defaults(self) -> None:
        """默认位置为 0。"""
        chunk = Chunk(content="c", index=0, metadata={})
        assert chunk.start_char == 0
        assert chunk.end_char == 0
