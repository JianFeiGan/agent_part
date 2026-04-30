"""
合规检查 Agent。

Description:
    对素材和文案执行合规检查，包括图片规范、文案规范、禁词检测。
    当前阶段使用规则检查，后续可接入 AI 辅助审核。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from src.agents.listing_compliance_rules import get_compliance_rules
from src.graph.listing_state import ListingState
from src.models.listing import (
    ComplianceIssue,
    ComplianceReport,
    ComplianceStatus,
    Platform,
)

logger = logging.getLogger(__name__)


class ComplianceCheckerAgent:
    """合规检查 Agent。

    在素材和文案生成完成后，对每个平台执行合规检查。
    检查项包括：
    - 图片合规：尺寸、背景、数量
    - 文案合规：标题长度、必填字段、搜索词限制
    - 禁词检测：广告法禁词、平台敏感词

    Attributes:
        _settings: 可选配置对象。
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化。

        Args:
            settings: 可选配置。
        """
        self._settings = settings

    def execute_sync(self, state: ListingState) -> dict:
        """同步执行合规检查。

        Args:
            state: 工作流状态。

        Returns:
            包含 compliance_reports 的字典。
        """
        product = state.product
        if not product:
            return {"compliance_reports": {}}

        compliance_reports: dict[Platform, ComplianceReport] = {}

        for platform in state.target_platforms:
            report = self._check_platform(
                state=state,
                platform=platform,
                task_id=0,
            )
            compliance_reports[platform] = report
            logger.info(
                f"合规检查: platform={platform.value}, "
                f"overall={report.overall}, "
                f"issues={len(report.image_issues) + len(report.text_issues)}"
            )

        return {"compliance_reports": compliance_reports}

    def _check_platform(
        self,
        state: ListingState,
        platform: Platform,
        task_id: int,
    ) -> ComplianceReport:
        """对单个平台执行合规检查。

        Args:
            state: 工作流状态。
            platform: 目标平台。
            task_id: 关联任务ID。

        Returns:
            合规检查报告。
        """
        report = ComplianceReport(
            listing_task_id=task_id,
            platform=platform,
        )

        rules = get_compliance_rules(platform.value)

        # 检查文案合规
        self._check_copywriting(state, report, rules)
        # 检查禁词
        self._check_forbidden_words(state, report, rules)

        return report

    def _check_copywriting(
        self,
        state: ListingState,
        report: ComplianceReport,
        rules: Any,
    ) -> None:
        """检查文案合规。

        Args:
            state: 工作流状态。
            report: 合规报告。
            rules: 平台规则集。
        """
        pkg = state.copywriting_packages.get(report.platform)
        if not pkg:
            return

        for rule in rules.text_rules:
            if rule.max_length and rule.check_field:
                value = getattr(pkg, rule.check_field, None)
                if value is not None:
                    if isinstance(value, str) and len(value) > rule.max_length:
                        report.mark_fail(
                            ComplianceIssue(
                                severity=ComplianceStatus.FAIL,
                                rule=rule.rule_id,
                                field=rule.check_field,
                                message=f"{rule.name}: 长度 {len(value)} 超过限制 {rule.max_length}",
                                suggestion=f"将{rule.check_field}缩短至 {rule.max_length} 字符以内",
                            ),
                            field="text",
                        )
                    elif isinstance(value, list) and rule.check_field == "search_terms":
                        total_bytes = len(" ".join(value).encode("utf-8"))
                        if total_bytes > rule.max_length:
                            report.mark_fail(
                                ComplianceIssue(
                                    severity=ComplianceStatus.FAIL,
                                    rule=rule.rule_id,
                                    field=rule.check_field,
                                    message=f"{rule.name}: 总字节 {total_bytes} 超过限制 {rule.max_length}",
                                    suggestion="减少搜索关键词数量",
                                ),
                                field="text",
                            )

            if rule.required and rule.check_field:
                value = getattr(pkg, rule.check_field, None)
                if not value or (isinstance(value, list) and len(value) == 0):
                    report.mark_fail(
                        ComplianceIssue(
                            severity=ComplianceStatus.FAIL,
                            rule=rule.rule_id,
                            field=rule.check_field,
                            message=f"{rule.name}: 该字段为必填项",
                            suggestion=f"请提供{rule.name}",
                        ),
                        field="text",
                    )

    def _check_forbidden_words(
        self,
        state: ListingState,
        report: ComplianceReport,
        rules: Any,
    ) -> None:
        """检查禁词。

        Args:
            state: 工作流状态。
            report: 合规报告。
            rules: 平台规则集。
        """
        pkg = state.copywriting_packages.get(report.platform)
        if not pkg:
            return

        # 检查标题和描述中的禁词
        text_to_check = " ".join(
            [
                pkg.title,
                pkg.description,
                " ".join(pkg.bullet_points),
                " ".join(pkg.search_terms),
            ]
        ).lower()

        for word in rules.forbidden_words:
            if word.lower() in text_to_check:
                report.forbidden_words.append(word)
                report.overall = ComplianceStatus.WARNING
                report.text_issues.append(
                    ComplianceIssue(
                        severity=ComplianceStatus.WARNING,
                        rule="FORBIDDEN-001",
                        field="copywriting",
                        message=f"检测到敏感词: {word}",
                        suggestion="替换为合规表达",
                    ),
                )

    async def execute(self, state: ListingState) -> dict:
        """异步执行（工作流节点接口）。

        Args:
            state: 工作流状态。

        Returns:
            包含 compliance_reports 的字典。
        """
        return self.execute_sync(state)
