"""知识库管道支撑模块覆盖率补齐测试。

Description:
    覆盖文档处理（DocumentProcessor 解析/分块）、RAG 使用日志
    （RAGLogger 记录/统计/命中率）与 Query 改写的模式开关、
    回退与 LLM 构造分支。数据库会话与 LLM 全部以桩替换。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.rag.document_processor import DocumentProcessor, ParsedDocument
from src.rag.logger import RAGLogger, get_rag_logger
from src.rag.query_rewriter import QueryRewriter, get_query_rewriter

# ==================== DocumentProcessor ====================


class TestDocumentProcessorParse:
    """文档解析测试类。"""

    @pytest.fixture
    def processor(self) -> DocumentProcessor:
        """创建文档处理器。

        Returns:
            文档处理器实例。
        """
        return DocumentProcessor()

    def test_parse_markdown_extracts_heading_title(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """Markdown 首个一级标题作为文档标题。"""
        path = tmp_path / "guide.md"
        path.write_text("# 品牌手册\n\n正文内容。", encoding="utf-8")

        doc = processor.parse(path, doc_type="brand_guide", category="digital")

        assert doc.title == "品牌手册"
        assert doc.content.startswith("# 品牌手册")
        assert doc.source == "guide.md"
        assert doc.doc_type == "brand_guide"
        assert doc.category == "digital"
        assert doc.metadata["file_suffix"] == ".md"

    def test_parse_markdown_without_heading_uses_stem(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """Markdown 无一级标题时以文件名主干为标题。"""
        path = tmp_path / "notes.md"
        path.write_text("二级标题不是标题\n\n正文。", encoding="utf-8")

        doc = processor.parse(path)

        assert doc.title == "notes"

    def test_parse_text_short_first_line_becomes_title(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """纯文本首行短于 100 字符时作为标题。"""
        path = tmp_path / "intro.txt"
        path.write_text("产品简介\n\n正文内容。", encoding="utf-8")

        doc = processor.parse(path)

        assert doc.title == "产品简介"

    def test_parse_text_long_first_line_falls_back_to_stem(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """纯文本首行过长时不作为标题。"""
        path = tmp_path / "long.txt"
        path.write_text(f"{'字' * 150}\n\n正文。", encoding="utf-8")

        doc = processor.parse(path)

        assert doc.title == "long"

    def test_parse_json_content_field(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        """JSON 含 content 字段时直接取该字段为正文。"""
        path = tmp_path / "meta.json"
        path.write_text(
            json.dumps({"title": "商品知识", "content": "正文内容"}, ensure_ascii=False),
            encoding="utf-8",
        )

        doc = processor.parse(path)

        assert doc.title == "商品知识"
        assert doc.content == "正文内容"

    def test_parse_json_name_and_description(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """JSON 无 content 时退而取 description 字段。"""
        path = tmp_path / "desc.json"
        path.write_text(
            json.dumps({"name": "类目描述", "description": "描述正文"}, ensure_ascii=False),
            encoding="utf-8",
        )

        doc = processor.parse(path)

        assert doc.title == "类目描述"
        assert doc.content == "描述正文"

    def test_parse_json_without_main_fields_dumps(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """JSON 无正文字段时整体序列化为文本。"""
        path = tmp_path / "raw.json"
        path.write_text(json.dumps({"a": 1}), encoding="utf-8")

        doc = processor.parse(path)

        assert doc.title == "raw"
        assert json.loads(doc.content) == {"a": 1}

    def test_parse_json_non_string_content_falls_back_to_dump(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """JSON 正文字段非字符串时忽略该字段，整体序列化。"""
        path = tmp_path / "num.json"
        path.write_text(json.dumps({"content": 123}), encoding="utf-8")

        doc = processor.parse(path)

        assert json.loads(doc.content) == {"content": 123}

    def test_parse_json_top_level_list_does_not_crash(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """JSON 顶层数组不再抛 AttributeError，标题回退文件名。"""
        path = tmp_path / "arr.json"
        path.write_text(json.dumps([{"a": 1}, {"b": 2}], ensure_ascii=False), encoding="utf-8")

        doc = processor.parse(path)

        assert doc.title == "arr"
        assert "a" in doc.content and "b" in doc.content

    def test_parse_json_top_level_scalar_does_not_crash(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """JSON 顶层数字/字符串不再抛 AttributeError，标题回退文件名。"""
        path = tmp_path / "num.json"
        path.write_text("42", encoding="utf-8")

        doc = processor.parse(path)

        assert doc.title == "num"
        assert doc.content == "42"

    def test_parse_unsupported_suffix_raises(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """不支持的文件格式抛 ValueError。"""
        path = tmp_path / "table.csv"
        path.write_text("a,b", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported file format"):
            processor.parse(path)

    def test_parse_missing_file_raises(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        """文件不存在时抛 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            processor.parse(tmp_path / "missing.md")

    def test_parse_merges_extra_metadata(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        """外部元数据与文件元数据合并返回。"""
        path = tmp_path / "doc.md"
        path.write_text("内容", encoding="utf-8")

        doc = processor.parse(path, metadata={"lang": "zh"})

        assert doc.metadata["lang"] == "zh"
        assert doc.metadata["file_size"] > 0
        assert doc.metadata["file_suffix"] == ".md"

    def test_parse_pdf_without_dependency_raises(
        self, processor: DocumentProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """pypdf 不可用时解析 PDF 抛 ImportError。"""
        path = tmp_path / "doc.pdf"
        path.write_bytes(b"%PDF-1.4")
        monkeypatch.setitem(sys.modules, "pypdf", None)

        with pytest.raises(ImportError, match="pypdf"):
            processor.parse(path)

    def test_parse_docx_without_dependency_raises(
        self, processor: DocumentProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """python-docx 不可用时解析 DOCX 抛 ImportError。"""
        path = tmp_path / "doc.docx"
        path.write_bytes(b"PK")
        monkeypatch.setitem(sys.modules, "docx", None)

        with pytest.raises(ImportError, match="python-docx"):
            processor.parse(path)

    def test_parse_pdf_uses_reader_content_and_metadata_title(
        self, processor: DocumentProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """PDF 逐页抽取文本并优先采用元数据标题。"""
        path = tmp_path / "doc.pdf"
        path.write_bytes(b"%PDF-1.4")
        reader = SimpleNamespace(
            pages=[
                SimpleNamespace(extract_text=lambda: "第一页\n"),
                SimpleNamespace(extract_text=lambda: None),
                SimpleNamespace(extract_text=lambda: "第二页"),
            ],
            metadata=SimpleNamespace(title="元数据标题"),
        )
        monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _p: reader))

        doc = processor.parse(path)

        assert doc.title == "元数据标题"
        # None 页按空串参与拼接，不抛异常
        assert doc.content == "第一页\n\n\n\n\n第二页"

    def test_parse_pdf_without_metadata_title_uses_stem(
        self, processor: DocumentProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """PDF 无元数据标题时以文件名主干为标题。"""
        path = tmp_path / "plain.pdf"
        path.write_bytes(b"%PDF-1.4")
        reader = SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda: "正文")],
            metadata=None,
        )
        monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _p: reader))

        doc = processor.parse(path)

        assert doc.title == "plain"
        assert doc.content == "正文"

    def test_parse_docx_uses_first_paragraph_title(
        self, processor: DocumentProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """DOCX 首个短段落作为标题，正文合并非空段落。"""
        path = tmp_path / "doc.docx"
        path.write_bytes(b"PK")
        doc_obj = SimpleNamespace(
            paragraphs=[
                SimpleNamespace(text="段落标题"),
                SimpleNamespace(text="   "),
                SimpleNamespace(text="正文段落"),
            ]
        )
        monkeypatch.setitem(sys.modules, "docx", SimpleNamespace(Document=lambda _p: doc_obj))

        doc = processor.parse(path)

        assert doc.title == "段落标题"
        assert doc.content == "段落标题\n\n正文段落"

    def test_parse_docx_long_first_paragraph_keeps_stem(
        self, processor: DocumentProcessor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """DOCX 首段过长或无段落时不作为标题。"""
        path = tmp_path / "long.docx"
        path.write_bytes(b"PK")
        doc_obj = SimpleNamespace(paragraphs=[SimpleNamespace(text="字" * 150)])
        monkeypatch.setitem(sys.modules, "docx", SimpleNamespace(Document=lambda _p: doc_obj))

        parsed = processor.parse(path)

        assert parsed.title == "long"
        assert parsed.content == "字" * 150


class TestDocumentProcessorIngest:
    """直接解析与分块测试类。"""

    @pytest.fixture
    def processor(self) -> DocumentProcessor:
        """创建文档处理器。

        Returns:
            文档处理器实例。
        """
        return DocumentProcessor()

    def test_parse_content_direct(self, processor: DocumentProcessor) -> None:
        """直接传入文本时按给定标题/类型构建文档。"""
        doc = processor.parse_content(
            content="正文",
            title="标题",
            doc_type="category_knowledge",
            category="digital",
            metadata={"lang": "zh"},
        )

        assert doc == ParsedDocument(
            title="标题",
            content="正文",
            metadata={"lang": "zh"},
            source="direct_input",
            doc_type="category_knowledge",
            category="digital",
        )

    def test_process_carries_document_metadata(self, processor: DocumentProcessor) -> None:
        """分块结果继承标题/类型/类目/来源元数据。"""
        doc = processor.parse_content(
            content="第一段落。\n\n第二段落。\n\n第三段落。",
            title="标题",
            doc_type="brand_guide",
            category="digital",
            metadata={"lang": "zh"},
        )

        chunks = processor.process(doc)

        assert chunks
        for chunk in chunks:
            assert chunk["metadata"]["title"] == "标题"
            assert chunk["metadata"]["doc_type"] == "brand_guide"
            assert chunk["metadata"]["category"] == "digital"
            assert chunk["metadata"]["source"] == "direct_input"
            assert chunk["metadata"]["lang"] == "zh"
            assert chunk["content"].strip()

    def test_process_empty_content_yields_no_chunks(self, processor: DocumentProcessor) -> None:
        """空文档不产出分块。"""
        doc = processor.parse_content(content="   ", title="空")

        assert processor.process(doc) == []

    def test_process_splits_long_text_into_chunks(self, processor: DocumentProcessor) -> None:
        """长文本被切分为多个分块。"""
        content = "。".join([f"第{i}句内容" for i in range(80)]) + "。"
        doc = processor.parse_content(content=content, title="长文")

        chunks = processor.process(doc)

        assert len(chunks) > 1


# ==================== RAGLogger ====================


class TestRAGLogger:
    """RAG 使用日志测试类。"""

    @pytest.fixture
    def logger(self) -> RAGLogger:
        """创建 RAG 日志记录器。

        Returns:
            RAGLogger 实例。
        """
        return RAGLogger()

    @pytest.mark.asyncio
    async def test_log_retrieval_persists_and_returns_record(self, logger: RAGLogger) -> None:
        """记录检索日志后入库并返回日志对象。"""
        session = AsyncMock()
        session.add = MagicMock()

        log = await logger.log_retrieval(
            session,
            tenant_id="tenant-1",
            task_id="task-1",
            agent_name="CreativePlanner",
            query="品牌调性",
            chunk_ids=[1, 2],
            scores=[0.9, 0.8],
            output="输出",
        )

        session.add.assert_called_once_with(log)
        session.flush.assert_awaited_once()
        assert log.tenant_id == "tenant-1"
        assert log.task_id == "task-1"
        assert log.agent_name == "CreativePlanner"
        assert log.retrieved_chunk_ids == [1, 2]
        assert log.similarity_scores == [0.9, 0.8]
        assert log.generated_output == "输出"

    @pytest.mark.asyncio
    async def test_get_logs_by_task_returns_records(self, logger: RAGLogger) -> None:
        """按任务 ID 查询返回日志列表。"""
        expected = [MagicMock(), MagicMock()]
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: expected))
        )

        logs = await logger.get_logs_by_task(session, "tenant-1", "task-1")

        assert logs == expected

    @pytest.mark.asyncio
    async def test_get_logs_by_agent_returns_records(self, logger: RAGLogger) -> None:
        """按 Agent 查询返回日志列表。"""
        expected = [MagicMock()]
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: expected))
        )

        logs = await logger.get_logs_by_agent(session, "tenant-1", "CreativePlanner", limit=5)

        assert logs == expected

    @pytest.mark.asyncio
    async def test_get_usage_stats_shapes_output(self, logger: RAGLogger) -> None:
        """使用统计返回总数、按 Agent 分布与平均相似度。"""
        agent_row = MagicMock(agent_name="CreativePlanner", count=3)
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                SimpleNamespace(scalar=lambda: 5),
                [agent_row],
                SimpleNamespace(scalar=lambda: 0.75),
            ]
        )
        start = datetime(2026, 1, 1)
        end = datetime(2026, 2, 1)

        stats = await logger.get_usage_stats(session, "tenant-1", start_date=start, end_date=end)

        assert stats["total_retrievals"] == 5
        assert stats["by_agent"] == [{"agent": "CreativePlanner", "count": 3}]
        assert stats["avg_similarity"] == 0.75
        assert stats["period"]["start"] == start.isoformat()
        assert stats["period"]["end"] == end.isoformat()

    @pytest.mark.asyncio
    async def test_get_usage_stats_defaults_when_empty(self, logger: RAGLogger) -> None:
        """无数据时统计为 0，周期两端为 None。"""
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                SimpleNamespace(scalar=lambda: None),
                [],
                SimpleNamespace(scalar=lambda: None),
            ]
        )

        stats = await logger.get_usage_stats(session, "tenant-1")

        assert stats["total_retrievals"] == 0
        assert stats["by_agent"] == []
        assert stats["avg_similarity"] == 0.0
        assert stats["period"] == {"start": None, "end": None}

    @pytest.mark.asyncio
    async def test_get_chunk_hit_rate_empty(self, logger: RAGLogger) -> None:
        """无检索记录时命中率为 0。"""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=iter([]))

        stats = await logger.get_chunk_hit_rate(session, "tenant-1")

        assert stats == {"total_retrievals": 0, "unique_chunks_hit": 0, "top_chunks": []}

    @pytest.mark.asyncio
    async def test_get_chunk_hit_rate_counts_hits(self, logger: RAGLogger) -> None:
        """命中率按 chunk 聚合并降序返回热门 chunk。"""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=iter([([1, 2],), ([2, 3],)]))

        stats = await logger.get_chunk_hit_rate(session, "tenant-1")

        assert stats["total_retrievals"] == 4
        assert stats["unique_chunks_hit"] == 3
        assert stats["top_chunks"][0] == {"chunk_id": 2, "hits": 2}
        assert {item["chunk_id"] for item in stats["top_chunks"]} == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_get_chunk_hit_rate_skips_null_rows(self, logger: RAGLogger) -> None:
        """检索记录里 chunk ID 为空的行被忽略。"""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=iter([(None,), ([7],)]))

        stats = await logger.get_chunk_hit_rate(session, "tenant-1")

        assert stats["total_retrievals"] == 1
        assert stats["top_chunks"] == [{"chunk_id": 7, "hits": 1}]

    def test_get_rag_logger_is_singleton(self) -> None:
        """全局日志记录器复用同一实例。"""
        assert get_rag_logger() is get_rag_logger()


# ==================== QueryRewriter ====================


def _rewriter_settings(**overrides: Any) -> MagicMock:
    """构造 QueryRewriter 用的配置桩。

    Args:
        **overrides: 需要覆盖的配置字段。

    Returns:
        配置桩对象。
    """
    settings = MagicMock()
    settings.query_rewriting_enabled = True
    settings.query_rewriting_mode = "single"
    settings.query_rewriting_max_variants = 2
    settings.hyde_enabled = True
    settings.llm_provider = "qwen"
    settings.effective_qwen_api_key = "test-key"
    settings.qwen_api_base = "https://example.test/v1"
    settings.qwen_llm_model = "qwen-plus"
    settings.llm_model = "qwen-plus"
    settings.effective_dashscope_api_key = "test-key"
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _install_llm(rewriter: QueryRewriter, responses: list[str | Exception]) -> None:
    """把改写器的 LLM 替换为按序返回预置响应的可调用桩。

    Args:
        rewriter: 改写器实例。
        responses: 预置响应文本或待抛出的异常。
    """
    queue = list(responses)

    def _call(prompt_value: Any) -> Any:
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(content=item)

    rewriter._llm = _call


class TestQueryRewriterModes:
    """Query 改写模式开关与回退测试类。"""

    @pytest.mark.asyncio
    async def test_multi_query_mode_includes_original_and_truncates(
        self,
    ) -> None:
        """multi_query 模式保留原始查询并限制变体数量。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(
                    query_rewriting_mode="multi_query", query_rewriting_max_variants=2
                ),
            )
            rewriter = QueryRewriter()
        _install_llm(rewriter, ["变体一\n变体二\n变体三\n\n变体四"])

        result = await rewriter.rewrite("原始查询")

        assert result.mode == "multi_query"
        assert result.queries == ["原始查询", "变体一", "变体二"]
        assert result.rewritten_queries[0].is_original is True

    @pytest.mark.asyncio
    async def test_hyde_mode_generates_hypothetical_doc(self) -> None:
        """hyde 模式生成假设文档查询。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(query_rewriting_mode="hyde", hyde_enabled=True),
            )
            rewriter = QueryRewriter()
        _install_llm(rewriter, ["假设性回答文档"])

        result = await rewriter.rewrite("问题")

        assert result.mode == "hyde"
        assert result.queries == ["假设性回答文档"]

    @pytest.mark.asyncio
    async def test_hyde_disabled_falls_back_to_single(self) -> None:
        """hyde_enabled 关闭时回退为 single 改写。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(query_rewriting_mode="hyde", hyde_enabled=False),
            )
            rewriter = QueryRewriter()
        _install_llm(rewriter, ["改写结果"])

        result = await rewriter.rewrite("原始查询")

        assert result.mode == "single"
        assert result.queries == ["改写结果"]

    @pytest.mark.asyncio
    async def test_rewrite_error_falls_back_to_original(self) -> None:
        """改写抛异常时回退到原始查询并标记 is_original。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(query_rewriting_mode="multi_query"),
            )
            rewriter = QueryRewriter()
        _install_llm(rewriter, [RuntimeError("llm down")])

        result = await rewriter.rewrite("原始查询")

        assert result.mode == "multi_query"
        assert result.queries == ["原始查询"]
        assert result.rewritten_queries[0].is_original is True

    @pytest.mark.asyncio
    async def test_rewrite_disabled_returns_original(self) -> None:
        """开关关闭时不改写，模式标记为 none。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(query_rewriting_enabled=False),
            )
            rewriter = QueryRewriter()

        result = await rewriter.rewrite("原始查询")

        assert result.mode == "none"
        assert result.queries == ["原始查询"]


class TestQueryRewriterLLM:
    """Query 改写 LLM 构造测试类。"""

    def test_llm_property_builds_qwen_model(self) -> None:
        """llm_provider=qwen 且有 Key 时懒加载出可调用模型。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(llm_provider="qwen", effective_qwen_api_key="key"),
            )
            rewriter = QueryRewriter()

        model = rewriter.llm

        assert type(model).__name__ == "ChatOpenAI"

    def test_llm_property_qwen_without_key_raises(self) -> None:
        """llm_provider=qwen 但缺 API Key 时抛 ValueError。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(llm_provider="qwen", effective_qwen_api_key=""),
            )
            rewriter = QueryRewriter()

        with pytest.raises(ValueError, match="QWEN_API_KEY"):
            _ = rewriter.llm

    def test_llm_property_dashscope_without_key_raises(self) -> None:
        """默认 DashScope 路径缺 API Key 时抛 ValueError。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(
                    llm_provider="dashscope", effective_dashscope_api_key=""
                ),
            )
            rewriter = QueryRewriter()

        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            _ = rewriter.llm

    def test_llm_property_is_cached(self) -> None:
        """llm 属性懒加载且缓存同一实例。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(llm_provider="qwen", effective_qwen_api_key="key"),
            )
            rewriter = QueryRewriter()

        assert rewriter.llm is rewriter.llm

    @pytest.mark.asyncio
    async def test_rewrite_falls_back_when_llm_unbuildable(self) -> None:
        """LLM 无法构造（缺 Key）时改写回退到原始查询。"""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "src.rag.query_rewriter.get_settings",
                lambda: _rewriter_settings(
                    query_rewriting_mode="single", effective_qwen_api_key=""
                ),
            )
            rewriter = QueryRewriter()

        result = await rewriter.rewrite("原始查询")

        assert result.mode == "single"
        assert result.queries == ["原始查询"]
        assert result.rewritten_queries[0].is_original is True

    def test_get_query_rewriter_is_singleton(self) -> None:
        """全局改写器复用同一实例。"""
        assert get_query_rewriter() is get_query_rewriter()
