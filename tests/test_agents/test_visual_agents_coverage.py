"""
视觉生成 Agent 群行为级覆盖率测试。

Description:
    覆盖创意策划、视觉设计、质量审核三个核心 Agent 及其 RAG 增强变体：
    - LLM JSON 解析（合法 / 围栏 / 夹带说明文字 / 完全非法）与解析失败降级
    - 资产装配缺字段、规格异常、状态异常时的问题标注
    - 输入校验与异常包装为失败结果
    - RAG 检索成功 / 失败 / 无检索器时的降级路径
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.creative_planner import CreativePlannerAgent
from src.agents.quality_reviewer import QualityReviewerAgent
from src.agents.rag_creative_planner import RAGEnhancedCreativePlanner
from src.agents.rag_image_generator import RAGEnhancedImageGenerator
from src.agents.rag_quality_reviewer import RAGEnhancedQualityReviewer
from src.agents.rag_requirement_analyzer import RAGEnhancedRequirementAnalyzer
from src.agents.visual_designer import VisualDesignerAgent
from src.db.vector_store import SearchResult
from src.graph.state import AgentState, GenerationRequest
from src.models.assets import AssetStatus, GeneratedImage, GeneratedVideo
from src.models.creative import (
    ColorInfo,
    ColorPalette,
    ColorRole,
    CreativePlan,
    VisualStyle,
)
from src.models.product import Product, ProductCategory
from src.rag.retriever import KnowledgeRetriever, RetrievalResult

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _product(**kwargs: Any) -> Product:
    """构造商品。"""
    defaults: dict[str, Any] = {
        "product_id": "prod_001",
        "name": "智能手表",
        "category": ProductCategory.DIGITAL,
        "description": "这是一款用于测试的智能手表商品描述",
    }
    defaults.update(kwargs)
    return Product(**defaults)


def _state(**kwargs: Any) -> AgentState:
    """构造工作流状态。"""
    defaults: dict[str, Any] = {
        "product_info": _product(),
        "generation_request": GenerationRequest(task_id="t1"),
    }
    defaults.update(kwargs)
    return AgentState(**defaults)


def _settings(**kwargs: Any) -> SimpleNamespace:
    """构造 Agent 用到的 Settings 子集。"""
    defaults: dict[str, Any] = {
        "rag_enabled": True,
        "llm_provider": "qwen",
        "llm_retry_attempts": 0,
        "llm_retry_initial_backoff": 0.01,
        "image_rag_auto_ingest": False,
        "image_rag_quality_threshold": 0.7,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _creative_plan() -> CreativePlan:
    """构造创意方案。"""
    palette = ColorPalette(
        name="测试配色",
        description="测试配色方案",
        colors=[ColorInfo(hex="#0066CC", name="主色", role=ColorRole.PRIMARY)],
        mood="测试",
    )
    return CreativePlan(
        name="测试创意",
        description="测试创意描述",
        visual_style=VisualStyle.MODERN,
        color_palette=palette,
    )


def _image(**kwargs: Any) -> GeneratedImage:
    """构造图片资产。"""
    defaults: dict[str, Any] = {
        "image_id": "img_001",
        "image_type": "main",
        "prompt": "product photography of smart watch",
        "width": 1024,
        "height": 1024,
        "status": AssetStatus.COMPLETED,
        "url": "https://example.com/img.png",
    }
    defaults.update(kwargs)
    return GeneratedImage(**defaults)


def _video(**kwargs: Any) -> GeneratedVideo:
    """构造视频资产。"""
    defaults: dict[str, Any] = {
        "video_id": "vid_001",
        "visual_prompt": "product hero video",
        "duration": 30.0,
        "fps": 30,
        "status": AssetStatus.COMPLETED,
    }
    defaults.update(kwargs)
    return GeneratedVideo(**defaults)


def _agent_llm(agent: Any, response: str) -> Any:
    """注入假 LLM 与文本响应。"""
    agent._llm = MagicMock()  # noqa: SLF001
    agent.invoke_llm = AsyncMock(return_value=response)
    return agent


def _knowledge_retriever() -> KnowledgeRetriever:
    """构造不触发外部依赖的 KnowledgeRetriever。"""
    return KnowledgeRetriever(embedding_service=MagicMock(), vector_store=MagicMock())


def _search_result(chunk_id: int, doc_type: str, content: str = "知识内容") -> SearchResult:
    """构造检索命中。"""
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=1,
        content=content,
        similarity=0.9,
        metadata={},
        doc_title="文档",
        doc_type=doc_type,
    )


def _session() -> MagicMock:
    """构造数据库会话桩。"""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


# --------------------------------------------------------------------------- #
# CreativePlannerAgent
# --------------------------------------------------------------------------- #

VALID_PLAN_JSON = (
    '{"theme_name": "科技未来", "theme_description": "描述",'
    ' "visual_style": "tech", "style_keywords": ["科技"],'
    ' "key_elements": ["产品"], "target_emotion": "信赖",'
    ' "color_suggestion": "luxury"}'
)


class TestCreativePlanner:
    """CreativePlannerAgent.execute 行为。"""

    async def test_missing_product_fails(self) -> None:
        """缺商品信息时返回失败结果。"""
        agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())

        result = await agent.execute(_state(product_info=None))

        assert result.success is False
        assert "缺少商品信息" in result.error

    async def test_llm_json_parsed_into_plan(self) -> None:
        """LLM 返回合法 JSON 时采纳主题、风格与配色。"""
        agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())
        _agent_llm(agent, VALID_PLAN_JSON)

        state = _state()
        result = await agent.execute(state)

        assert result.success is True
        assert result.data["creative_plan"]["name"] == "科技未来"
        assert result.data["creative_plan"]["visual_style"] == "tech"
        assert result.data["color_palette"]["name"] == "奢华金"
        assert state.creative_plan is not None
        assert "creative_planning" in state.completed_steps

    async def test_fenced_json_with_prose_parsed(self) -> None:
        """围栏 JSON 与夹带说明文字均可解析。"""
        agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())
        _agent_llm(agent, "好的，方案如下：\n```json\n" + VALID_PLAN_JSON + "\n```\n请查收。")

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["creative_plan"]["name"] == "科技未来"

    async def test_unknown_style_falls_back_to_modern(self) -> None:
        """未知视觉风格回退 MODERN，未知配色回退科技蓝。"""
        agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())
        _agent_llm(
            agent,
            '{"theme_name": "T", "visual_style": "not_a_style", "color_suggestion": "nope"}',
        )

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["creative_plan"]["visual_style"] == "modern"
        assert result.data["color_palette"]["name"] == "科技蓝"

    async def test_invalid_json_falls_back_to_default_plan(self) -> None:
        """完全非法输出降级为默认创意方案。"""
        agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())
        _agent_llm(agent, "这不是 JSON")

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["creative_plan"]["name"] == "智能手表产品展示"
        assert result.data["creative_plan"]["visual_style"] == "modern"

    async def test_default_plan_palette_by_category(self) -> None:
        """类目驱动的默认配色分支可观测。"""
        cases = [
            (ProductCategory.CLOTHING, "极简白"),
            (ProductCategory.FOOD, "自然绿"),
            (ProductCategory.DIGITAL, "科技蓝"),
        ]
        for category, expected_palette in cases:
            agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())
            agent.get_prompt = MagicMock(return_value=None)  # type: ignore[method-assign]
            result = await agent.execute(_state(product_info=_product(category=category)))
            assert result.data["color_palette"]["name"] == expected_palette

    async def test_default_plan_luxury_name(self) -> None:
        """商品名含 luxury 时默认走奢华金配色。"""
        agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(return_value=None)  # type: ignore[method-assign]

        result = await agent.execute(_state(product_info=_product(name="Luxury 手表")))

        assert result.data["color_palette"]["name"] == "奢华金"

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = CreativePlannerAgent(llm=MagicMock(), settings=_settings())
        agent._generate_creative_plan = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        result = await agent.execute(_state())

        assert result.success is False
        assert "创意策划失败" in result.error


# --------------------------------------------------------------------------- #
# VisualDesignerAgent
# --------------------------------------------------------------------------- #

VALID_PROMPTS_JSON = (
    '[{"image_type": "main", "prompt": "hero shot",'
    ' "negative_prompt": "blur", "style_keywords": ["clean"],'
    ' "aspect_ratio": "1:1"},'
    ' {"image_type": "scene", "prompt": "lifestyle",'
    ' "style_keywords": "warm, soft", "aspect_ratio": "4:3"}]'
)

VALID_STORYBOARD_JSON = (
    '{"title": "产品视频", "description": "整体描述", "scenes": ['
    '{"scene_type": "product_intro", "duration": 4, "shot_type": "wide",'
    ' "description": "开场", "visual_prompt": "open"},'
    '{"scene_type": "bad_type", "duration": 3, "shot_type": "bad_shot",'
    ' "description": "卖点", "visual_prompt": "feature"}]}'
)


class TestVisualDesigner:
    """VisualDesignerAgent.execute 行为。"""

    def _agent(self, response: str | None = None) -> VisualDesignerAgent:
        """构造已注入 LLM 的视觉设计 Agent。"""
        agent = VisualDesignerAgent(llm=MagicMock(), settings=_settings())
        if response is not None:
            _agent_llm(agent, response)
        return agent

    async def test_missing_product_fails(self) -> None:
        """缺商品信息时返回失败结果。"""
        agent = self._agent()

        result = await agent.execute(_state(product_info=None))

        assert result.success is False
        assert "缺少商品信息" in result.error

    async def test_missing_creative_plan_fails(self) -> None:
        """缺创意方案时返回失败结果。"""
        agent = self._agent()

        result = await agent.execute(_state(creative_plan=None))

        assert result.success is False
        assert "缺少创意方案" in result.error

    async def test_image_only_skips_storyboard(self) -> None:
        """image_only 任务只产出图片提示词。"""
        agent = self._agent(VALID_PROMPTS_JSON)

        state = _state(
            generation_request=GenerationRequest(task_id="t1", task_type="image_only"),
            creative_plan=_creative_plan(),
        )
        result = await agent.execute(state)

        assert result.success is True
        assert "image_prompts" in result.data
        assert "storyboard" not in result.data
        assert state.generation_prompts

    async def test_video_only_skips_image_prompts(self) -> None:
        """video_only 任务只产出分镜脚本。"""
        agent = self._agent(VALID_STORYBOARD_JSON)

        state = _state(
            generation_request=GenerationRequest(task_id="t1", task_type="video_only"),
            creative_plan=_creative_plan(),
        )
        result = await agent.execute(state)

        assert result.success is True
        assert "storyboard" in result.data
        assert "image_prompts" not in result.data
        assert state.storyboard is not None

    async def test_image_and_video_produces_both(self) -> None:
        """image_and_video 同时产出提示词与分镜。"""
        agent = self._agent(VALID_PROMPTS_JSON)
        agent.invoke_llm = AsyncMock(side_effect=[VALID_PROMPTS_JSON, VALID_STORYBOARD_JSON])

        state = _state(creative_plan=_creative_plan())
        result = await agent.execute(state)

        assert result.success is True
        assert "image_prompts" in result.data
        assert "storyboard" in result.data
        assert "visual_design" in state.completed_steps

    async def test_image_prompt_list_parsed(self) -> None:
        """LLM 返回提示词数组时按条装配 ImagePrompt。"""
        agent = self._agent(VALID_PROMPTS_JSON)

        state = _state(
            generation_request=GenerationRequest(task_id="t1", task_type="image_only"),
            creative_plan=_creative_plan(),
        )
        result = await agent.execute(state)

        prompts = result.data["image_prompts"]
        assert len(prompts) == 2
        assert prompts[0]["image_type"] == "main"
        assert prompts[0]["prompt"] == "hero shot"
        assert prompts[1]["style_keywords"] == ["warm", "soft"]

    async def test_image_prompt_invalid_type_and_non_dict_items(self) -> None:
        """非法图片类型回退 main，非字典条目被跳过。"""
        agent = self._agent(
            '[{"image_type": "weird", "prompt": "p", "style_keywords": "a, b"}, "junk", 42]'
        )

        state = _state(
            generation_request=GenerationRequest(task_id="t1", task_type="image_only"),
            creative_plan=_creative_plan(),
        )
        result = await agent.execute(state)

        prompts = result.data["image_prompts"]
        assert len(prompts) == 1
        assert prompts[0]["image_type"] == "main"
        assert prompts[0]["style_keywords"] == ["a", "b"]

    async def test_image_prompt_invalid_json_falls_back_to_defaults(self) -> None:
        """提示词解析失败时按请求的图片类型生成默认提示词。"""
        agent = self._agent("完全不是 JSON")

        state = _state(
            generation_request=GenerationRequest(
                task_id="t1",
                task_type="image_only",
                image_types=["main", "scene", "selling_point", "detail"],
            ),
            creative_plan=_creative_plan(),
        )
        result = await agent.execute(state)

        prompts = result.data["image_prompts"]
        assert len(prompts) == 4
        types = [p["image_type"] for p in prompts]
        assert types == ["main", "scene", "selling_point", "detail"]
        assert "clean white background" in prompts[0]["prompt"]
        assert "Lifestyle photography" in prompts[1]["prompt"]
        assert "feature highlight" in prompts[2]["prompt"]
        assert "Product photography" in prompts[3]["prompt"]

    async def test_image_prompt_unknown_type_string_defaults_to_main(self) -> None:
        """默认提示词对未知类型字符串回退 main。"""
        agent = self._agent("not json")

        state = _state(
            generation_request=GenerationRequest(
                task_id="t1", task_type="image_only", image_types=["unknown_type"]
            ),
            creative_plan=_creative_plan(),
        )
        result = await agent.execute(state)

        assert result.data["image_prompts"][0]["image_type"] == "main"

    async def test_selling_points_dict_shapes_passed_to_llm(self) -> None:
        """卖点字典的 title / description / 兜底形态都会进入 LLM 输入。"""
        agent = self._agent("not json")

        state = _state(
            generation_request=GenerationRequest(task_id="t1", task_type="image_only"),
            creative_plan=_creative_plan(),
            selling_points=[
                {"title": "续航长"},
                {"description": "防水"},
                {"note": "轻便"},
            ],
        )
        result = await agent.execute(state)

        assert result.success is True
        input_vars = agent.invoke_llm.call_args.args[1]
        assert "续航长" in input_vars["selling_points"]
        assert "防水" in input_vars["selling_points"]
        assert "轻便" in input_vars["selling_points"]

    async def test_storyboard_llm_parsed_with_enum_fallbacks(self) -> None:
        """分镜 JSON 中的非法枚举回退默认值，scene_id 顺序编号。"""
        agent = self._agent(VALID_STORYBOARD_JSON)

        state = _state(
            generation_request=GenerationRequest(task_id="t1", task_type="video_only"),
            creative_plan=_creative_plan(),
            selling_points=[{"title": "续航"}],
        )
        result = await agent.execute(state)

        storyboard = result.data["storyboard"]
        assert storyboard["title"] == "产品视频"
        assert len(storyboard["scenes"]) == 2
        assert storyboard["scenes"][0]["scene_id"] == 1
        assert storyboard["scenes"][0]["scene_type"] == "product_intro"
        assert storyboard["scenes"][1]["scene_type"] == "product_intro"
        assert storyboard["scenes"][1]["shot_type"] == "medium"
        assert storyboard["total_duration"] == 30.0

    async def test_storyboard_invalid_json_falls_back_to_default(self) -> None:
        """分镜解析失败时生成五段默认分镜。"""
        agent = self._agent("不是 JSON")

        state = _state(
            generation_request=GenerationRequest(
                task_id="t1", task_type="video_only", video_duration=10.0
            ),
            creative_plan=_creative_plan(),
        )
        result = await agent.execute(state)

        storyboard = result.data["storyboard"]
        assert storyboard["title"] == "智能手表产品介绍"
        assert len(storyboard["scenes"]) == 5
        assert storyboard["total_duration"] == 10.0
        assert storyboard["scenes"][0]["duration"] == 2.0

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = self._agent()
        agent._generate_image_prompts = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        state = _state(creative_plan=_creative_plan())
        result = await agent.execute(state)

        assert result.success is False
        assert "视觉设计失败" in result.error


# --------------------------------------------------------------------------- #
# QualityReviewerAgent
# --------------------------------------------------------------------------- #

GOOD_SCORE_JSON = (
    '{"overall_score": 0.95, "clarity_score": 0.9,'
    ' "composition_score": 0.9, "color_score": 0.9, "relevance_score": 0.9}'
)
LOW_SCORE_JSON = '{"overall_score": 0.5}'


class TestQualityReviewer:
    """QualityReviewerAgent.execute 行为。"""

    def _agent(self, response: str | None = None) -> QualityReviewerAgent:
        """构造已注入 LLM 的质量审核 Agent。"""
        agent = QualityReviewerAgent(llm=MagicMock(), settings=_settings())
        if response is not None:
            _agent_llm(agent, response)
        return agent

    async def test_missing_product_fails(self) -> None:
        """缺商品信息时返回失败结果。"""
        agent = self._agent()

        result = await agent.execute(_state(product_info=None))

        assert result.success is False
        assert "缺少商品信息" in result.error

    async def test_image_spec_issues_and_pass_flag(self) -> None:
        """低分辨率与异常状态会被标注，导致审核不通过。"""
        agent = self._agent(GOOD_SCORE_JSON)

        state = _state(
            generated_images=[
                _image(width=500, height=500, status=AssetStatus.FAILED),
            ]
        )
        result = await agent.execute(state)

        assert result.success is True
        report = result.data["quality_reports"][0]
        issue_types = [i["issue_type"] for i in report["issues"]]
        assert "resolution" in issue_types
        assert "status" in issue_types
        assert report["passed"] is False
        assert result.data["issues_count"] == 2
        assert result.data["overall_score"] == 0.95

    async def test_image_passes_when_high_quality(self) -> None:
        """高分辨率、状态正常、评分达标时审核通过。"""
        agent = self._agent(GOOD_SCORE_JSON)

        state = _state(generated_images=[_image()])
        result = await agent.execute(state)

        report = result.data["quality_reports"][0]
        assert report["passed"] is True
        assert report["issues"] == []
        assert result.data["final_results"]["assets_passed"] == 1
        assert "智能手表" in result.data["final_results"]["product_name"]

    async def test_llm_failure_is_fail_closed(self) -> None:
        """LLM 调用失败按 fail-closed 记 0 分并标注 high 级问题。"""
        agent = self._agent()
        agent.invoke_llm = AsyncMock(side_effect=RuntimeError("llm down"))

        state = _state(generated_images=[_image()])
        result = await agent.execute(state)

        report = result.data["quality_reports"][0]
        assert report["score"]["overall_score"] == 0.0
        assert report["passed"] is False
        issue_types = [i["issue_type"] for i in report["issues"]]
        assert "scoring_unavailable" in issue_types

    async def test_unparseable_score_fails_closed(self) -> None:
        """评分响应无法解析时同样 fail-closed。"""
        agent = self._agent("完全不是 JSON")

        state = _state(generated_images=[_image()])
        result = await agent.execute(state)

        report = result.data["quality_reports"][0]
        assert report["score"]["overall_score"] == 0.0
        assert any(i["issue_type"] == "scoring_unavailable" for i in report["issues"])

    async def test_video_llm_failure_is_fail_closed(self) -> None:
        """视频评分 LLM 失败同样 fail-closed。"""
        agent = self._agent()
        agent.invoke_llm = AsyncMock(side_effect=RuntimeError("llm down"))

        state = _state(generated_video=_video())
        result = await agent.execute(state)

        report = result.data["quality_reports"][0]
        assert report["score"]["overall_score"] == 0.0
        assert any(i["issue_type"] == "scoring_unavailable" for i in report["issues"])

    async def test_video_spec_issues(self) -> None:
        """视频时长、帧率、状态异常会被标注。"""
        agent = self._agent(GOOD_SCORE_JSON)

        state = _state(
            generated_video=_video(duration=3.0, fps=12, status=AssetStatus.PENDING),
        )
        result = await agent.execute(state)

        report = result.data["quality_reports"][0]
        issue_types = [i["issue_type"] for i in report["issues"]]
        assert issue_types == ["duration", "fps", "status"]
        assert report["asset_type"] == "video"
        assert report["passed"] is False
        assert result.data["final_results"]["video_generated"] is True

    async def test_video_llm_json_applied(self) -> None:
        """视频评分采纳 LLM 返回的分值。"""
        agent = self._agent(
            '{"overall_score": 0.85, "clarity_score": 0.8,'
            ' "composition_score": 0.8, "color_score": 0.8, "relevance_score": 0.8}'
        )

        state = _state(generated_video=_video())
        result = await agent.execute(state)

        report = result.data["quality_reports"][0]
        assert report["score"]["overall_score"] == 0.85
        assert report["passed"] is True

    async def test_no_assets_overall_score_zero(self) -> None:
        """无任何资产时总体评分 0 且建议重新生成。"""
        agent = self._agent()

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["overall_score"] == 0.0
        assert result.data["quality_reports"] == []
        assert "重新生成" in result.data["final_results"]["recommendation"]

    async def test_recommendation_tiers(self) -> None:
        """总体评分分档给出不同改进建议。"""
        cases = [
            (0.95, "优秀"),
            (0.85, "良好"),
            (0.75, "一般"),
            (0.5, "不达标"),
        ]
        for score, keyword in cases:
            agent = self._agent(f'{{"overall_score": {score}}}')
            result = await agent.execute(_state(generated_images=[_image()]))
            assert keyword in result.data["final_results"]["recommendation"]

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = self._agent()
        agent._review_image = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        result = await agent.execute(_state(generated_images=[_image()]))

        assert result.success is False
        assert "质量审核失败" in result.error


# --------------------------------------------------------------------------- #
# RAGEnhancedCreativePlanner
# --------------------------------------------------------------------------- #


class TestRAGCreativePlanner:
    """RAGEnhancedCreativePlanner.execute 行为。"""

    def _agent(self, **kwargs: Any) -> RAGEnhancedCreativePlanner:
        """构造 RAG 创意策划 Agent。"""
        return RAGEnhancedCreativePlanner(settings=_settings(), **kwargs)

    async def test_missing_product_fails(self) -> None:
        """缺商品信息时返回失败结果。"""
        agent = self._agent()

        result = await agent.execute(_state(product_info=None))

        assert result.success is False
        assert "缺少商品信息" in result.error

    async def test_without_retriever_still_succeeds(self) -> None:
        """无检索器时按无知识路径产出方案。"""
        agent = self._agent()
        _agent_llm(agent, VALID_PLAN_JSON)

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["rag_enhanced"] is False
        assert result.data["rag_sources"] == []
        assert result.data["creative_plan"]["name"] == "科技未来"

    async def test_non_knowledge_retriever_ignored(self) -> None:
        """非 KnowledgeRetriever 实例不触发检索。"""
        agent = self._agent(retriever=MagicMock(), session=_session())
        _agent_llm(agent, VALID_PLAN_JSON)

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["rag_enhanced"] is False

    async def test_knowledge_bucketed_by_doc_type(self) -> None:
        """检索命中按 doc_type 分桶并记入 rag_sources。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_for_creative_planning = AsyncMock(  # type: ignore[method-assign]
            return_value=RetrievalResult(
                query="创意",
                results=[
                    _search_result(1, "brand_guide", "B" * 500),
                    _search_result(2, "category_knowledge", "S" * 500),
                    _search_result(3, "case_study", "C" * 400),
                ],
                context="",
                sources=[],
            )
        )
        agent = self._agent(retriever=retriever, session=_session())
        _agent_llm(agent, VALID_PLAN_JSON)

        state = _state()
        result = await agent.execute(state)

        assert result.success is True
        assert result.data["rag_enhanced"] is True
        assert len(result.data["rag_sources"]) == 3
        assert state.rag_sources
        input_vars = agent.invoke_llm.call_args.args[1]
        assert "B" * 400 in input_vars["brand_guidelines"]
        assert "S" * 400 in input_vars["category_styles"]
        assert "C" * 300 in input_vars["case_inspirations"]

    async def test_retrieve_failure_degrades(self) -> None:
        """检索抛异常时按无知识降级且仍产出方案。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_for_creative_planning = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("retriever down")
        )
        agent = self._agent(retriever=retriever, session=_session())
        _agent_llm(agent, VALID_PLAN_JSON)

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["rag_enhanced"] is False

    async def test_invalid_json_falls_back_to_default(self) -> None:
        """非法输出降级为默认方案。"""
        agent = self._agent()
        _agent_llm(agent, "不是 JSON")

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["creative_plan"]["name"] == "智能手表产品展示"

    async def test_unknown_style_falls_back_to_modern(self) -> None:
        """未知视觉风格回退 MODERN。"""
        agent = self._agent()
        _agent_llm(agent, '{"theme_name": "T", "visual_style": "not_a_style"}')

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["creative_plan"]["visual_style"] == "modern"

    async def test_default_plan_category_branches(self) -> None:
        """无提示模板时按类目生成默认方案。"""
        agent = self._agent()
        agent.get_prompt = MagicMock(return_value=None)  # type: ignore[method-assign]

        result = await agent.execute(_state(product_info=_product(category=ProductCategory.FOOD)))

        assert result.success is True
        assert result.data["color_palette"]["name"] == "自然绿"

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = self._agent()
        agent._generate_creative_plan_with_rag = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        result = await agent.execute(_state())

        assert result.success is False
        assert "创意策划失败" in result.error


# --------------------------------------------------------------------------- #
# RAGEnhancedQualityReviewer
# --------------------------------------------------------------------------- #


class TestRAGQualityReviewer:
    """RAGEnhancedQualityReviewer.execute 行为。"""

    def _agent(self, **kwargs: Any) -> RAGEnhancedQualityReviewer:
        """构造 RAG 质量审核 Agent。"""
        return RAGEnhancedQualityReviewer(settings=_settings(), **kwargs)

    async def test_missing_product_fails(self) -> None:
        """缺商品信息时返回失败结果。"""
        agent = self._agent()

        result = await agent.execute(_state(product_info=None))

        assert result.success is False
        assert "缺少商品信息" in result.error

    async def test_without_rag_reviews_image_normally(self) -> None:
        """无检索器时仍完成审核，合规规则数为 0。"""
        agent = self._agent()
        _agent_llm(agent, GOOD_SCORE_JSON)

        state = _state(generated_images=[_image()])
        result = await agent.execute(state)

        assert result.success is True
        assert result.data["compliance_rules_applied"] == 0
        assert result.data["quality_reports"][0]["passed"] is True

    async def test_compliance_rules_flag_prohibited_words(self) -> None:
        """知识库规则中的禁止词命中内容时标注 high 级合规问题。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_compliance_rules = AsyncMock(  # type: ignore[method-assign]
            return_value=RetrievalResult(
                query="compliance_rules",
                results=[_search_result(1, "compliance_rule", '禁止词列表："最好"、"第一"')],
                context="",
                sources=[],
            )
        )
        agent = self._agent(retriever=retriever, session=_session())
        _agent_llm(agent, GOOD_SCORE_JSON)

        state = _state(generated_images=[_image(prompt="这是最好的产品，全网第一")])
        result = await agent.execute(state)

        assert result.success is True
        assert result.data["compliance_rules_applied"] == 1
        issues = result.data["quality_reports"][0]["issues"]
        prohibited = [i for i in issues if i["issue_type"] == "prohibited_content"]
        assert len(prohibited) == 2
        assert all(i["severity"] == "high" for i in prohibited)
        assert result.data["quality_reports"][0]["passed"] is False
        assert "严重问题" in result.data["final_results"]["recommendation"]

    async def test_retrieve_rules_failure_degrades(self) -> None:
        """合规规则检索失败时按无规则降级。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_compliance_rules = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("down")
        )
        agent = self._agent(retriever=retriever, session=_session())
        _agent_llm(agent, GOOD_SCORE_JSON)

        result = await agent.execute(_state(generated_images=[_image()]))

        assert result.success is True
        assert result.data["compliance_rules_applied"] == 0

    async def test_non_knowledge_retriever_skips_rules(self) -> None:
        """非 KnowledgeRetriever 不加载合规规则。"""
        agent = self._agent(retriever=MagicMock(), session=_session())
        _agent_llm(agent, GOOD_SCORE_JSON)

        result = await agent.execute(_state(generated_images=[_image()]))

        assert result.success is True
        assert result.data["compliance_rules_applied"] == 0

    async def test_video_review_with_rag_rules(self) -> None:
        """视频路径同样执行合规检查与规格检查。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_compliance_rules = AsyncMock(  # type: ignore[method-assign]
            return_value=RetrievalResult(
                query="compliance_rules",
                results=[_search_result(1, "compliance_rule", '违禁词："绝对"')],
                context="",
                sources=[],
            )
        )
        agent = self._agent(retriever=retriever, session=_session())
        _agent_llm(agent, GOOD_SCORE_JSON)

        state = _state(generated_video=_video(duration=2.0, fps=10, visual_prompt="绝对好用"))
        result = await agent.execute(state)

        report = result.data["quality_reports"][0]
        issue_types = [i["issue_type"] for i in report["issues"]]
        assert "prohibited_content" in issue_types
        assert "duration" in issue_types
        assert "fps" in issue_types
        assert report["passed"] is False

    async def test_video_llm_failure_is_fail_closed(self) -> None:
        """视频评分 LLM 失败时 fail-closed。"""
        agent = self._agent()
        agent.invoke_llm = AsyncMock(side_effect=RuntimeError("llm down"))

        result = await agent.execute(_state(generated_video=_video()))

        report = result.data["quality_reports"][0]
        assert report["score"]["overall_score"] == 0.0
        assert any(i["issue_type"] == "scoring_unavailable" for i in report["issues"])

    async def test_unparseable_score_fails_closed(self) -> None:
        """评分无法解析时 fail-closed。"""
        agent = self._agent()
        _agent_llm(agent, "不是 JSON")

        result = await agent.execute(_state(generated_images=[_image()]))

        report = result.data["quality_reports"][0]
        assert report["score"]["overall_score"] == 0.0
        assert any(i["issue_type"] == "scoring_unavailable" for i in report["issues"])

    async def test_recommendation_without_high_issues(self) -> None:
        """无 high 级问题时按分档给建议。"""
        agent = self._agent()
        _agent_llm(agent, LOW_SCORE_JSON)

        result = await agent.execute(_state(generated_images=[_image()]))

        assert "不达标" in result.data["final_results"]["recommendation"]
        assert result.data["final_results"]["rag_compliance_rules_used"] == 0

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = self._agent()
        agent._review_image_with_rag = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        result = await agent.execute(_state(generated_images=[_image()]))

        assert result.success is False
        assert "质量审核失败" in result.error


# --------------------------------------------------------------------------- #
# RAGEnhancedImageGenerator
# --------------------------------------------------------------------------- #


class TestRAGImageGenerator:
    """RAGEnhancedImageGenerator.execute 行为。"""

    def _base(self, result: Any = None) -> Any:
        """构造基础图片生成 Agent 桩。"""
        base = MagicMock()
        base.execute = AsyncMock(
            return_value=result
            if result is not None
            else SimpleNamespace(success=True, data={"images": []}, error=None)
        )
        return base

    async def test_without_rag_delegates_to_base_agent(self) -> None:
        """无检索器时直接委托基础 Agent。"""
        base = self._base()
        agent = RAGEnhancedImageGenerator(
            base_agent=base, settings=_settings(image_rag_auto_ingest=False)
        )

        state = _state(generation_prompts=[{"prompt": "original"}])
        result = await agent.execute(state)

        assert result.success is True
        assert base.execute.await_count == 1
        assert state.generation_prompts[0]["prompt"] == "original"
        assert "rag_sources" not in result.data

    async def test_rag_enhances_prompts(self) -> None:
        """检索到上下文时注入规范并保留 original_prompt。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_for_image_generation = AsyncMock(  # type: ignore[method-assign]
            return_value=RetrievalResult(
                query="图片生成",
                results=[_search_result(1, "brand_guide")],
                context="品牌规范：使用冷色调",
                sources=[{"chunk_id": 1, "doc_id": 1, "similarity": 0.9}],
            )
        )
        base = self._base()
        agent = RAGEnhancedImageGenerator(
            base_agent=base,
            retriever=retriever,
            session=_session(),
            settings=_settings(image_rag_auto_ingest=False),
        )

        state = _state(
            generation_prompts=[{"prompt": "original shot", "image_type": "main"}],
            generation_request=GenerationRequest(
                task_id="t1", style_preference="极简", tenant_id="tenant-a"
            ),
        )
        result = await agent.execute(state)

        assert result.success is True
        enhanced = state.generation_prompts[0]
        assert enhanced["original_prompt"] == "original shot"
        assert "品牌规范：使用冷色调" in enhanced["prompt"]
        assert "风格偏好：极简" in enhanced["prompt"]
        assert result.data["image_rag_enhanced"] is True
        assert result.data["rag_context_length"] > 0
        retrieve_kwargs = retriever.retrieve_for_image_generation.call_args.kwargs
        assert retrieve_kwargs["tenant_id"] == "tenant-a"
        assert retrieve_kwargs["style_preference"] == "极简"

    async def test_non_retrieval_result_skips_enhancement(self) -> None:
        """检索返回非 RetrievalResult 时不改写提示词。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_for_image_generation = AsyncMock(  # type: ignore[method-assign]
            return_value={"unexpected": True}
        )
        base = self._base()
        agent = RAGEnhancedImageGenerator(
            base_agent=base,
            retriever=retriever,
            session=_session(),
            settings=_settings(image_rag_auto_ingest=False),
        )

        state = _state(generation_prompts=[{"prompt": "original"}])
        result = await agent.execute(state)

        assert result.success is True
        assert state.generation_prompts[0]["prompt"] == "original"
        assert "image_rag_enhanced" not in result.data

    async def test_auto_ingest_on_success(self) -> None:
        """生成成功且开启自动入库时逐图入库。"""
        base = self._base()
        agent = RAGEnhancedImageGenerator(
            base_agent=base,
            session=_session(),
            settings=_settings(image_rag_auto_ingest=True),
        )
        agent.ingest_generation_result = AsyncMock(return_value=1)  # type: ignore[method-assign]

        state = _state(
            generated_images=[
                _image(image_id="img_1", prompt="p1", url="https://a/1.png"),
                _image(image_id="img_2", prompt="p2", url=None),
            ],
            generation_prompts=[{"prompt": "p1", "original_prompt": "raw1"}],
        )
        await agent.execute(state)

        assert agent.ingest_generation_result.await_count == 1
        call_kwargs = agent.ingest_generation_result.call_args.kwargs
        assert call_kwargs["prompt"] == "raw1"
        assert call_kwargs["enhanced_prompt"] == "p1"
        assert call_kwargs["image_url"] == "https://a/1.png"

    async def test_auto_ingest_per_image_failure_continues(self) -> None:
        """单图入库失败不影响其余图片。"""
        base = self._base()
        agent = RAGEnhancedImageGenerator(
            base_agent=base,
            session=_session(),
            settings=_settings(image_rag_auto_ingest=True),
        )
        agent.ingest_generation_result = AsyncMock(  # type: ignore[method-assign]
            side_effect=[RuntimeError("boom"), 2]
        )

        state = _state(
            generated_images=[
                _image(image_id="img_1", prompt="p1", url="https://a/1.png"),
                _image(image_id="img_2", prompt="p2", url="https://a/2.png"),
            ]
        )
        result = await agent.execute(state)

        assert result.success is True
        assert agent.ingest_generation_result.await_count == 2

    async def test_base_failure_skips_ingest(self) -> None:
        """基础 Agent 失败时不入库。"""
        base = self._base(SimpleNamespace(success=False, data={}, error="gen failed"))
        agent = RAGEnhancedImageGenerator(
            base_agent=base,
            session=_session(),
            settings=_settings(image_rag_auto_ingest=True),
        )
        agent.ingest_generation_result = AsyncMock(return_value=1)  # type: ignore[method-assign]

        await agent.execute(_state(generated_images=[_image()]))

        assert agent.ingest_generation_result.await_count == 0

    async def test_ingest_skips_low_quality(self) -> None:
        """低于质量阈值的结果不入库。"""
        agent = RAGEnhancedImageGenerator(
            base_agent=self._base(),
            settings=_settings(image_rag_quality_threshold=0.7),
        )
        session = _session()

        doc_id = await agent.ingest_generation_result(
            session,
            prompt="p",
            enhanced_prompt="ep",
            image_url="https://a/1.png",
            category="digital",
            quality_score=0.3,
            tenant_id="t1",
        )

        assert doc_id is None
        assert session.add.call_count == 0

    async def test_ingest_high_quality_writes_case_study(self) -> None:
        """达到阈值的结果作为 case_study 入库并写入向量。"""
        agent = RAGEnhancedImageGenerator(
            base_agent=self._base(),
            settings=_settings(image_rag_quality_threshold=0.7),
        )
        session = _session()

        def _assign_id(obj: Any) -> None:
            obj.id = 42

        session.add = MagicMock(side_effect=_assign_id)

        mock_processor = MagicMock()
        mock_processor.parse_content.return_value = {"content": "c", "title": "t"}
        mock_processor.process.return_value = [{"content": "chunk"}]
        mock_embedding = MagicMock()
        mock_embedding.aembed_batch = AsyncMock(return_value=[[0.1, 0.2]])
        mock_store = MagicMock()
        mock_store.add_vectors = AsyncMock()

        with (
            patch(
                "src.rag.document_processor.DocumentProcessor",
                return_value=mock_processor,
            ),
            patch(
                "src.rag.embeddings.get_embedding_service",
                return_value=mock_embedding,
            ),
            patch("src.db.vector_store.VectorStore", return_value=mock_store),
        ):
            doc_id = await agent.ingest_generation_result(
                session,
                prompt="p",
                enhanced_prompt="ep",
                image_url="https://a/1.png",
                category="digital",
                brand="TechBrand",
                quality_score=0.9,
                tenant_id="t1",
            )

        assert doc_id == 42
        assert session.add.call_count == 1
        assert mock_store.add_vectors.await_count == 1

    async def test_ingest_failure_returns_none(self) -> None:
        """入库过程异常时返回 None 而不抛出。"""
        agent = RAGEnhancedImageGenerator(
            base_agent=self._base(),
            settings=_settings(image_rag_quality_threshold=0.7),
        )
        session = _session()
        session.add = MagicMock(side_effect=RuntimeError("db down"))

        with (
            patch("src.rag.document_processor.DocumentProcessor"),
            patch("src.rag.embeddings.get_embedding_service"),
            patch("src.db.vector_store.VectorStore"),
        ):
            doc_id = await agent.ingest_generation_result(
                session,
                prompt="p",
                enhanced_prompt="ep",
                image_url="https://a/1.png",
                category="digital",
                quality_score=None,
                tenant_id="t1",
            )

        assert doc_id is None

    async def test_tenant_id_resolution_fallbacks(self) -> None:
        """tenant_id 依次取请求、商品、状态，最后 system。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_for_image_generation = AsyncMock(  # type: ignore[method-assign]
            return_value=RetrievalResult(query="q", results=[], context="", sources=[])
        )
        agent = RAGEnhancedImageGenerator(
            base_agent=self._base(),
            retriever=retriever,
            session=_session(),
            settings=_settings(image_rag_auto_ingest=False),
        )

        # 请求带 tenant_id
        await agent.execute(
            _state(generation_request=GenerationRequest(task_id="t1", tenant_id="req-tenant"))
        )
        assert retriever.retrieve_for_image_generation.call_args.kwargs["tenant_id"] == "req-tenant"

        # 仅商品带 tenant_id（Product 模型无该字段，用 setattr 绕过校验模拟）
        product = _product()
        object.__setattr__(product, "tenant_id", "prod-tenant")
        await agent.execute(
            _state(
                product_info=product,
                generation_request=GenerationRequest(task_id="t1", tenant_id=""),
            )
        )
        assert (
            retriever.retrieve_for_image_generation.call_args.kwargs["tenant_id"] == "prod-tenant"
        )

        # 请求与商品都无 tenant_id 时落到状态级
        state = _state(
            generation_request=GenerationRequest(task_id="t1", tenant_id=""),
        )
        object.__setattr__(state, "tenant_id", "state-tenant")
        await agent.execute(state)
        assert (
            retriever.retrieve_for_image_generation.call_args.kwargs["tenant_id"] == "state-tenant"
        )

        # 全都缺失时落到 system
        await agent.execute(
            _state(generation_request=GenerationRequest(task_id="t1", tenant_id=""))
        )
        assert retriever.retrieve_for_image_generation.call_args.kwargs["tenant_id"] == "system"

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        base = MagicMock()
        base.execute = AsyncMock(side_effect=RuntimeError("boom"))
        agent = RAGEnhancedImageGenerator(
            base_agent=base, settings=_settings(image_rag_auto_ingest=False)
        )

        result = await agent.execute(_state())

        assert result.success is False
        assert "RAG 增强图片生成失败" in result.error


# --------------------------------------------------------------------------- #
# RAGEnhancedRequirementAnalyzer（补剩余分支）
# --------------------------------------------------------------------------- #

VALID_REPORT_JSON = (
    '{"product_summary": "摘要", "key_features": ["f1"],'
    ' "selling_points": [{"title": "t", "description": "d"}],'
    ' "target_audience": ["a"], "style_recommendations": [], "keywords": ["k"]}'
)


class TestRAGRequirementAnalyzer:
    """RAGEnhancedRequirementAnalyzer 检索与降级行为。"""

    def _agent(self, **kwargs: Any) -> RAGEnhancedRequirementAnalyzer:
        """构造 RAG 需求分析 Agent。"""
        return RAGEnhancedRequirementAnalyzer(settings=_settings(), **kwargs)

    async def test_knowledge_context_included(self) -> None:
        """检索命中时知识上下文进入 LLM 输入并写入状态。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_for_product_analysis = AsyncMock(  # type: ignore[method-assign]
            return_value=RetrievalResult(
                query="分析商品: 智能手表",
                results=[_search_result(1, "category_knowledge")],
                context="类目知识要点",
                sources=[{"chunk_id": 1, "doc_id": 1, "similarity": 0.9}],
            )
        )
        agent = self._agent(retriever=retriever, session=_session())
        _agent_llm(agent, VALID_REPORT_JSON)

        state = _state()
        result = await agent.execute(state)

        assert result.success is True
        assert result.data["rag_context_used"] is True
        assert state.rag_context == "类目知识要点"
        input_vars = agent.invoke_llm.call_args.args[1]
        assert input_vars["knowledge_context"] == "类目知识要点"

    async def test_retrieve_failure_degrades(self) -> None:
        """检索失败时按无知识继续分析。"""
        retriever = _knowledge_retriever()
        retriever.retrieve_for_product_analysis = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("down")
        )
        agent = self._agent(retriever=retriever, session=_session())
        _agent_llm(agent, VALID_REPORT_JSON)

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["rag_context_used"] is False

    async def test_non_knowledge_retriever_skips_retrieval(self) -> None:
        """非 KnowledgeRetriever 跳过检索。"""
        agent = self._agent(retriever=MagicMock(), session=_session())
        _agent_llm(agent, VALID_REPORT_JSON)

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["rag_context_used"] is False
        assert result.data["rag_sources"] == []

    async def test_invalid_json_falls_back_to_default_report(self) -> None:
        """非法输出降级为默认报告。"""
        agent = self._agent()
        _agent_llm(agent, "不是 JSON")

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["requirement_report"]["product_summary"] == "智能手表"
        assert result.data["requirement_report"]["key_features"] == [
            "高品质",
            "实用性强",
            "性价比高",
        ]

    async def test_no_prompt_defaults(self) -> None:
        """无提示模板时产出默认报告。"""
        agent = self._agent()
        agent.get_prompt = MagicMock(return_value=None)  # type: ignore[method-assign]

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["requirement_report"]["product_summary"] == "智能手表"

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = self._agent()
        agent._analyze_product_with_rag = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        result = await agent.execute(_state())

        assert result.success is False
        assert "需求分析失败" in result.error
