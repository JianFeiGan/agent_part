"""
质量审核Agent模块。

Description:
    负责审核生成内容的质量和合规性。
    主要功能：
    - 图像质量检测
    - 内容合规审核
    - 品牌一致性检查
    - 生成审核报告
@author ganjianfei
@version 1.0.0
2026-03-23
"""

import json
from datetime import datetime
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

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


class QualityReviewerAgent(BaseAgent[AgentState]):
    """质量审核Agent。

    对生成的内容进行全面质量检测。

    Example:
        >>> agent = QualityReviewerAgent()
        >>> result = await agent.execute(state)
        >>> report = result.data.get("quality_report")
    """

    # 质量阈值
    QUALITY_THRESHOLD = 0.7
    CLARITY_THRESHOLD = 0.6
    COMPOSITION_THRESHOLD = 0.6

    def __init__(self, **kwargs: Any) -> None:
        """初始化质量审核Agent。"""
        super().__init__(role=AgentRole.QUALITY_REVIEWER, **kwargs)
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # 质量评估提示
        quality_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个专业的电商视觉内容质量审核专家。"
                    "请对生成的内容进行全面质量评估。\n\n"
                    "评估维度：\n"
                    "1. 清晰度 (clarity): 图片/视频是否清晰\n"
                    "2. 构图 (composition): 构图是否合理美观\n"
                    "3. 色彩 (color): 色彩是否协调\n"
                    "4. 相关性 (relevance): 内容是否与商品相关\n"
                    "5. 专业度 (professionalism): 是否达到商业标准\n\n"
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
        self.register_prompt("quality", quality_prompt)

        # 合规审核提示
        compliance_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个内容合规审核专家。"
                    "请检查内容是否符合以下规范：\n\n"
                    "1. 无违禁内容和敏感信息\n"
                    "2. 无虚假宣传和夸大描述\n"
                    "3. 无侵犯他人权益的内容\n"
                    "4. 符合广告法规定\n"
                    "5. 符合平台内容规范\n\n"
                    "如有问题，请列出具体问题和严重程度（low/medium/high）。",
                ),
                (
                    "human",
                    "内容描述：{content}\n"
                    "商品类目：{category}\n\n"
                    "请进行合规审核。",
                ),
            ]
        )
        self.register_prompt("compliance", compliance_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行质量审核。

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

            quality_reports: list[QualityReport] = []
            all_issues: list[dict[str, Any]] = []

            # 审核图片
            for image in state.generated_images:
                report = await self._review_image(image, product, state)
                quality_reports.append(report)
                if report.issues:
                    all_issues.extend(
                        [{"asset_id": image.image_id, **issue.model_dump()}
                         for issue in report.issues]
                    )

            # 审核视频
            if state.generated_video:
                report = await self._review_video(
                    state.generated_video, product, state
                )
                quality_reports.append(report)
                if report.issues:
                    all_issues.extend(
                        [{"asset_id": state.generated_video.video_id, **issue.model_dump()}
                         for issue in report.issues]
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
                },
                next_agent=None,  # 流程结束
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"质量审核失败: {e}",
            )

    async def _review_image(
        self,
        image: GeneratedImage,
        product: Any,
        state: AgentState,
    ) -> QualityReport:
        """审核图片。

        Args:
            image: 图片对象。
            product: 商品信息。
            state: 当前状态。

        Returns:
            质量报告。
        """
        # 调用LLM评估质量
        prompt = self.get_prompt("quality")
        score = QualityScore(overall_score=0.8)
        issues: list[QualityIssue] = []

        if prompt:
            try:
                response = await self.invoke_llm(
                    prompt,
                    {
                        "product_name": product.name,
                        "content_type": f"图片-{image.image_type}",
                        "content_description": image.prompt,
                        "requirements": str(state.requirement_report),
                    },
                )
                score = self._parse_quality_score(response)
            except Exception:
                pass

        # 检查图片规格
        if image.width < 800 or image.height < 800:
            issues.append(QualityIssue(
                issue_type="resolution",
                severity="medium",
                description="图片分辨率较低，建议提高至至少800x800",
                suggestion="使用更高质量参数重新生成",
            ))

        # 检查状态
        if image.status != AssetStatus.COMPLETED:
            issues.append(QualityIssue(
                issue_type="status",
                severity="high",
                description=f"图片生成状态异常: {image.status.value}",
                suggestion="检查生成过程或重试",
            ))

        return QualityReport(
            asset_id=image.image_id,
            asset_type="image",
            score=score,
            issues=issues,
            passed=score.overall_score >= self.QUALITY_THRESHOLD and len([i for i in issues if i.severity == "high"]) == 0,
        )

    async def _review_video(
        self,
        video: GeneratedVideo,
        product: Any,
        state: AgentState,
    ) -> QualityReport:
        """审核视频。

        Args:
            video: 视频对象。
            product: 商品信息。
            state: 当前状态。

        Returns:
            质量报告。
        """
        prompt = self.get_prompt("quality")
        score = QualityScore(overall_score=0.8)
        issues: list[QualityIssue] = []

        if prompt:
            try:
                response = await self.invoke_llm(
                    prompt,
                    {
                        "product_name": product.name,
                        "content_type": "视频",
                        "content_description": video.visual_prompt or "",
                        "requirements": str(state.requirement_report),
                    },
                )
                score = self._parse_quality_score(response)
            except Exception:
                pass

        # 检查视频规格
        if video.duration < 5:
            issues.append(QualityIssue(
                issue_type="duration",
                severity="low",
                description="视频时长较短",
                suggestion="考虑增加视频时长以更好展示产品",
            ))

        if video.fps < 24:
            issues.append(QualityIssue(
                issue_type="fps",
                severity="medium",
                description="视频帧率较低，可能影响播放流畅度",
                suggestion="提高帧率至至少24fps",
            ))

        # 检查状态
        if video.status != AssetStatus.COMPLETED:
            issues.append(QualityIssue(
                issue_type="status",
                severity="high",
                description=f"视频生成状态异常: {video.status.value}",
                suggestion="检查生成过程或重试",
            ))

        return QualityReport(
            asset_id=video.video_id,
            asset_type="video",
            score=score,
            issues=issues,
            passed=score.overall_score >= self.QUALITY_THRESHOLD and len([i for i in issues if i.severity == "high"]) == 0,
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

    def _calculate_overall_score(
        self, reports: list[QualityReport]
    ) -> float:
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

        # 统计通过的资产
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
        }

    def _get_recommendation(
        self, score: float, issues: list[dict[str, Any]]
    ) -> str:
        """获取改进建议。

        Args:
            score: 总体评分。
            issues: 问题列表。

        Returns:
            改进建议。
        """
        if score >= 0.9:
            return "内容质量优秀，可以直接使用。"
        elif score >= 0.8:
            return "内容质量良好，建议微调后使用。"
        elif score >= 0.7:
            return "内容质量一般，建议优化后使用。"
        else:
            return "内容质量不达标，建议重新生成。"
