"""
RAG增强的质量审核Agent模块。

Description:
    基于知识库检索的质量审核Agent，通过RAG增强合规检查能力。
    主要功能：
    - 知识库驱动的合规规则检查
    - 品牌一致性验证
    - 行业标准审核
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import json
from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.models.assets import (
    AssetCollection,
    AssetStatus,
    GeneratedImage,
    GeneratedVideo,
    QualityIssue,
    QualityReport,
    QualityScore,
)


class RAGEnhancedQualityReviewer(BaseAgent[AgentState]):
    """RAG增强的质量审核Agent。

    通过知识库检索增强审核能力：
    - 合规规则：检查是否违反平台/法规规定
    - 品牌规范：验证内容是否符合品牌调性
    - 行业标准：对照行业标准评估质量

    Example:
        >>> from src.rag.retriever import KnowledgeRetriever
        >>> retriever = KnowledgeRetriever()
        >>> agent = RAGEnhancedQualityReviewer(retriever=retriever)
        >>> result = await agent.execute(state, session)
    """

    # 质量阈值
    QUALITY_THRESHOLD = 0.7
    CLARITY_THRESHOLD = 0.6
    COMPOSITION_THRESHOLD = 0.6

    def __init__(self, session: AsyncSession | None = None, **kwargs: Any) -> None:
        """初始化RAG增强质量审核Agent。

        Args:
            session: 数据库会话，用于知识检索。
            **kwargs: 传递给父类的参数。
        """
        super().__init__(role=AgentRole.QUALITY_REVIEWER, **kwargs)
        self._session = session
        self._compliance_rules: list[dict[str, Any]] = []
        self._setup_prompts()

    def set_session(self, session: AsyncSession) -> None:
        """设置数据库会话。

        Args:
            session: 数据库会话。
        """
        self._session = session

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # RAG增强的质量评估提示
        quality_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个专业的电商视觉内容质量审核专家。"
                    "请结合以下合规规则，对生成的内容进行全面质量评估。\n\n"
                    "【合规审核规则】\n{compliance_rules}\n\n"
                    "评估维度：\n"
                    "1. 清晰度 (clarity): 图片/视频是否清晰\n"
                    "2. 构图 (composition): 构图是否合理美观\n"
                    "3. 色彩 (color): 色彩是否协调\n"
                    "4. 相关性 (relevance): 内容是否与商品相关\n"
                    "5. 专业度 (professionalism): 是否达到商业标准\n"
                    "6. 合规性 (compliance): 是否符合平台和法规要求\n\n"
                    "输出JSON格式，包含各维度评分(0-1)和总体评价。",
                ),
                (
                    "human",
                    "商品名称：{product_name}\n"
                    "内容类型：{content_type}\n"
                    "内容描述：{content_description}\n"
                    "原始需求：{requirements}\n\n"
                    "请评估内容质量。",
                ),
            ]
        )
        self.register_prompt("rag_quality", quality_prompt)

        # 合规审核提示
        compliance_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个内容合规审核专家。"
                    "请结合以下规则检查内容合规性。\n\n"
                    "【平台禁止词列表】\n{prohibited_words}\n\n"
                    "【行业监管要求】\n{industry_regulations}\n\n"
                    "检查项目：\n"
                    "1. 是否包含违禁内容和敏感信息\n"
                    "2. 是否存在虚假宣传和夸大描述\n"
                    "3. 是否侵犯他人权益\n"
                    "4. 是否符合广告法规定\n"
                    "5. 是否符合平台内容规范\n\n"
                    "如有问题，请列出具体问题和严重程度（low/medium/high）。",
                ),
                (
                    "human",
                    "内容描述：{content}\n商品类目：{category}\n\n请进行合规审核。",
                ),
            ]
        )
        self.register_prompt("rag_compliance", compliance_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行RAG增强的质量审核。

        Args:
            state: 当前状态。

        Returns:
            包含质量报告的结果。
        """
        try:
            product = state.product_info
            if product is None:
                return AgentResult(
                    success=False,
                    error="缺少商品信息",
                )

            # 加载合规规则
            await self._load_compliance_rules(state)

            quality_reports: list[QualityReport] = []
            all_issues: list[dict[str, Any]] = []

            # 审核图片
            for image in state.generated_images:
                report = await self._review_image_with_rag(image, product, state)
                quality_reports.append(report)
                if report.issues:
                    all_issues.extend(
                        [
                            {"asset_id": image.image_id, **issue.model_dump()}
                            for issue in report.issues
                        ]
                    )

            # 审核视频
            if state.generated_video:
                report = await self._review_video_with_rag(state.generated_video, product, state)
                quality_reports.append(report)
                if report.issues:
                    all_issues.extend(
                        [
                            {"asset_id": state.generated_video.video_id, **issue.model_dump()}
                            for issue in report.issues
                        ]
                    )

            # 计算总体评分
            overall_score = self._calculate_overall_score(quality_reports)

            # 创建资源集合
            asset_collection = AssetCollection(
                collection_id=f"col_{product.product_id or 'default'}",
                task_id=state.generation_request.task_id if state.generation_request else "default",
                product_name=product.name,
                images=state.generated_images,
                videos=[state.generated_video] if state.generated_video else [],
                quality_reports=quality_reports,
            )

            # 更新状态
            state.quality_reports = quality_reports
            state.quality_score = overall_score
            state.issues = all_issues
            state.asset_collection = asset_collection
            state.mark_step_completed("quality_review")

            # 创建最终结果
            final_results = self._create_final_results(state, quality_reports, overall_score)
            state.final_results = final_results

            return AgentResult(
                success=True,
                data={
                    "quality_reports": [r.model_dump() for r in quality_reports],
                    "overall_score": overall_score,
                    "issues_count": len(all_issues),
                    "asset_collection": asset_collection.model_dump(),
                    "final_results": final_results,
                    "compliance_rules_applied": len(self._compliance_rules),
                },
                next_agent=None,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"质量审核失败: {e}",
            )

    async def _load_compliance_rules(self, state: AgentState) -> None:
        """从知识库加载合规规则。

        Args:
            state: 当前状态。
        """
        if not self.has_rag() or not self._session:
            self._compliance_rules = []
            return

        from src.rag.retriever import KnowledgeRetriever

        if not isinstance(self._retriever, KnowledgeRetriever):
            self._compliance_rules = []
            return

        # 检索合规规则
        results = await self._retriever.retrieve(
            self._session,
            query="禁止词列表 广告法规定 平台内容规范 敏感内容",
            doc_type="compliance_rule",
            top_k=5,
        )

        self._compliance_rules = [
            {
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "content": r.content,
            }
            for r in results.results
        ]

        # 记录到RAG来源
        state.rag_sources = [
            {
                "query": "compliance_rules",
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "similarity": r.similarity,
            }
            for r in results.results
        ]

    async def _review_image_with_rag(
        self,
        image: GeneratedImage,
        product: Any,
        state: AgentState,
    ) -> QualityReport:
        """使用RAG规则审核图片。

        Args:
            image: 图片对象。
            product: 商品信息。
            state: 当前状态。

        Returns:
            质量报告。
        """
        compliance_rules_text = self._format_compliance_rules()
        prompt = self.get_prompt("rag_quality")
        score = QualityScore(overall_score=0.8)
        issues: list[QualityIssue] = []

        if prompt:
            try:
                response = await self.invoke_llm(
                    prompt,
                    {
                        "compliance_rules": compliance_rules_text or "暂无特定合规规则",
                        "product_name": product.name,
                        "content_type": f"图片-{image.image_type}",
                        "content_description": image.prompt,
                        "requirements": str(state.requirement_report),
                    },
                )
                score = self._parse_quality_score(response)
            except Exception:
                pass

        # 合规性检查
        compliance_issues = await self._check_compliance(
            image.prompt or "",
            product.category.value if hasattr(product.category, "value") else str(product.category),
        )
        issues.extend(compliance_issues)

        # 规格检查
        if image.width < 800 or image.height < 800:
            issues.append(
                QualityIssue(
                    issue_type="resolution",
                    severity="medium",
                    description="图片分辨率较低，建议提高至至少800x800",
                    suggestion="使用更高质量参数重新生成",
                )
            )

        if image.status != AssetStatus.COMPLETED:
            issues.append(
                QualityIssue(
                    issue_type="status",
                    severity="high",
                    description=f"图片生成状态异常: {image.status.value}",
                    suggestion="检查生成过程或重试",
                )
            )

        return QualityReport(
            asset_id=image.image_id,
            asset_type="image",
            score=score,
            issues=issues,
            passed=score.overall_score >= self.QUALITY_THRESHOLD
            and len([i for i in issues if i.severity == "high"]) == 0,
        )

    async def _review_video_with_rag(
        self,
        video: GeneratedVideo,
        product: Any,
        state: AgentState,
    ) -> QualityReport:
        """使用RAG规则审核视频。

        Args:
            video: 视频对象。
            product: 商品信息。
            state: 当前状态。

        Returns:
            质量报告。
        """
        compliance_rules_text = self._format_compliance_rules()
        prompt = self.get_prompt("rag_quality")
        score = QualityScore(overall_score=0.8)
        issues: list[QualityIssue] = []

        if prompt:
            try:
                response = await self.invoke_llm(
                    prompt,
                    {
                        "compliance_rules": compliance_rules_text or "暂无特定合规规则",
                        "product_name": product.name,
                        "content_type": "视频",
                        "content_description": video.visual_prompt or "",
                        "requirements": str(state.requirement_report),
                    },
                )
                score = self._parse_quality_score(response)
            except Exception:
                pass

        # 合规性检查
        compliance_issues = await self._check_compliance(
            video.visual_prompt or "",
            product.category.value if hasattr(product.category, "value") else str(product.category),
        )
        issues.extend(compliance_issues)

        # 规格检查
        if video.duration < 5:
            issues.append(
                QualityIssue(
                    issue_type="duration",
                    severity="low",
                    description="视频时长较短",
                    suggestion="考虑增加视频时长以更好展示产品",
                )
            )

        if video.fps < 24:
            issues.append(
                QualityIssue(
                    issue_type="fps",
                    severity="medium",
                    description="视频帧率较低，可能影响播放流畅度",
                    suggestion="提高帧率至至少24fps",
                )
            )

        if video.status != AssetStatus.COMPLETED:
            issues.append(
                QualityIssue(
                    issue_type="status",
                    severity="high",
                    description=f"视频生成状态异常: {video.status.value}",
                    suggestion="检查生成过程或重试",
                )
            )

        return QualityReport(
            asset_id=video.video_id,
            asset_type="video",
            score=score,
            issues=issues,
            passed=score.overall_score >= self.QUALITY_THRESHOLD
            and len([i for i in issues if i.severity == "high"]) == 0,
        )

    async def _check_compliance(self, content: str, category: str) -> list[QualityIssue]:
        """检查内容合规性。

        Args:
            content: 待检查内容。
            category: 商品类目。

        Returns:
            合规问题列表。
        """
        issues: list[QualityIssue] = []

        # 基于知识库规则的检查
        for rule in self._compliance_rules:
            rule_content = rule.get("content", "").lower()

            # 检查是否包含禁止词
            if "禁止词" in rule_content or "违禁词" in rule_content:
                # 简单的关键词匹配（实际应用中可以使用更复杂的NLP方法）
                prohibited_keywords = self._extract_prohibited_words(rule_content)
                for keyword in prohibited_keywords:
                    if keyword in content.lower():
                        issues.append(
                            QualityIssue(
                                issue_type="prohibited_content",
                                severity="high",
                                description=f"内容包含禁止词: {keyword}",
                                suggestion="请移除或替换该词汇",
                            )
                        )

        return issues

    def _extract_prohibited_words(self, rule_content: str) -> list[str]:
        """从规则内容中提取禁止词。

        Args:
            rule_content: 规则内容。

        Returns:
            禁止词列表。
        """
        # 简化实现：提取引号内的词汇
        import re

        words = re.findall(r'["\']([^"\']+)["\']', rule_content)
        return [w for w in words if len(w) >= 2]

    def _format_compliance_rules(self) -> str:
        """格式化合规规则为文本。

        Returns:
            格式化的合规规则文本。
        """
        if not self._compliance_rules:
            return ""

        return "\n".join(
            [f"- {rule.get('content', '')[:200]}" for rule in self._compliance_rules[:3]]
        )

    def _parse_quality_score(self, response: str) -> QualityScore:
        """解析质量评分。

        Args:
            response: LLM响应。

        Returns:
            质量评分对象。
        """
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])
                return QualityScore(
                    overall_score=float(data.get("overall_score", 0.8)),
                    clarity_score=float(data.get("clarity_score", 0.8)),
                    composition_score=float(data.get("composition_score", 0.8)),
                    color_score=float(data.get("color_score", 0.8)),
                    relevance_score=float(data.get("relevance_score", 0.8)),
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return QualityScore(overall_score=0.8)

    def _calculate_overall_score(self, reports: list[QualityReport]) -> float:
        """计算总体评分。

        Args:
            reports: 质量报告列表。

        Returns:
            总体评分。
        """
        if not reports:
            return 0.0

        scores = [report.score.overall_score for report in reports]
        return sum(scores) / len(scores)

    def _create_final_results(
        self,
        state: AgentState,
        reports: list[QualityReport],
        overall_score: float,
    ) -> dict[str, Any]:
        """创建最终结果。

        Args:
            state: 当前状态。
            reports: 质量报告列表。
            overall_score: 总体评分。

        Returns:
            最终结果字典。
        """
        product = state.product_info
        passed_count = sum(1 for r in reports if r.passed)
        total_count = len(reports)

        return {
            "product_name": product.name if product else "未知商品",
            "images_generated": len(state.generated_images),
            "video_generated": state.generated_video is not None,
            "overall_quality_score": overall_score,
            "assets_passed": passed_count,
            "assets_total": total_count,
            "issues_found": len(state.issues),
            "recommendation": self._get_recommendation(overall_score, state.issues),
            "completed_at": datetime.now().isoformat(),
            "rag_compliance_rules_used": len(self._compliance_rules),
        }

    def _get_recommendation(self, score: float, issues: list[dict[str, Any]]) -> str:
        """获取改进建议。

        Args:
            score: 总体评分。
            issues: 问题列表。

        Returns:
            改进建议。
        """
        high_severity_count = len([i for i in issues if i.get("severity") == "high"])

        if high_severity_count > 0:
            return f"发现{high_severity_count}个严重问题，必须修复后才能使用。"
        elif score >= 0.9:
            return "内容质量优秀，可以直接使用。"
        elif score >= 0.8:
            return "内容质量良好，建议微调后使用。"
        elif score >= 0.7:
            return "内容质量一般，建议优化后使用。"
        else:
            return "内容质量不达标，建议重新生成。"
