"""合规检查 Agent 测试。"""

from src.agents.listing_compliance_checker import ComplianceCheckerAgent
from src.agents.listing_compliance_rules import (
    FORBIDDEN_WORDS,
    ComplianceRules,
    get_compliance_rules,
)
from src.graph.listing_state import ListingState
from src.models.listing import (
    ComplianceReport,
    ComplianceStatus,
    CopywritingPackage,
    ListingProduct,
    Platform,
)


class TestComplianceRules:
    """测试合规规则配置。"""

    def test_forbidden_words_not_empty(self) -> None:
        """测试禁词列表不为空。"""
        assert len(FORBIDDEN_WORDS) > 0
        assert "最佳" in FORBIDDEN_WORDS

    def test_amazon_rules(self) -> None:
        """测试 Amazon 规则。"""
        rules = get_compliance_rules("amazon")
        assert len(rules.image_rules) == 3
        assert len(rules.text_rules) == 3

    def test_ebay_rules(self) -> None:
        """测试 eBay 规则。"""
        rules = get_compliance_rules("ebay")
        assert len(rules.image_rules) == 3
        assert len(rules.text_rules) == 1

    def test_shopify_rules(self) -> None:
        """测试 Shopify 规则。"""
        rules = get_compliance_rules("shopify")
        assert len(rules.image_rules) == 1
        assert len(rules.text_rules) == 0

    def test_unknown_platform(self) -> None:
        """测试未知平台返回空规则。"""
        rules = get_compliance_rules("unknown")
        assert isinstance(rules, ComplianceRules)


class TestComplianceReport:
    """测试合规报告模型。"""

    def test_initial_report(self) -> None:
        """测试初始报告为通过状态。"""
        report = ComplianceReport(listing_task_id=1, platform=Platform.AMAZON)
        assert report.overall == ComplianceStatus.PASS
        assert report.is_pass is True

    def test_mark_fail_text(self) -> None:
        """测试标记文本问题。"""
        report = ComplianceReport(listing_task_id=1, platform=Platform.AMAZON)
        from src.models.listing import ComplianceIssue

        issue = ComplianceIssue(
            severity=ComplianceStatus.FAIL,
            rule="TXT-001",
            field="title",
            message="标题过长",
        )
        report.mark_fail(issue, field="text")
        assert report.overall == ComplianceStatus.FAIL
        assert report.is_pass is False
        assert len(report.text_issues) == 1

    def test_mark_fail_image(self) -> None:
        """测试标记图片问题。"""
        report = ComplianceReport(listing_task_id=1, platform=Platform.AMAZON)
        from src.models.listing import ComplianceIssue

        issue = ComplianceIssue(
            severity=ComplianceStatus.FAIL,
            rule="IMG-001",
            field="main_image",
            message="非白底",
        )
        report.mark_fail(issue, field="image")
        assert len(report.image_issues) == 1


class TestComplianceCheckerAgent:
    """测试合规检查 Agent。"""

    def _make_state(
        self,
        title: str = "Test Product",
        description: str = "A test product",
        platforms: list[Platform] | None = None,
    ) -> ListingState:
        """创建测试状态。"""
        product = ListingProduct(sku="T-001", title=title, description=description)
        return ListingState(
            product=product,
            target_platforms=platforms or [Platform.AMAZON],
        )

    def test_clean_copywriting_passes(self) -> None:
        """测试干净文案通过检查。"""
        state = self._make_state(
            title="Wireless Bluetooth Headphones",
            description="Premium noise-cancelling headphones with 40-hour battery life.",
        )
        state.copywriting_packages[Platform.AMAZON] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Wireless Bluetooth Headphones",
            bullet_points=["40-hour battery life", "Noise cancelling"],
            description="Premium headphones",
            search_terms=["wireless", "bluetooth"],
        )
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        report = result["compliance_reports"][Platform.AMAZON]
        assert report.is_pass is True
        assert len(report.forbidden_words) == 0

    def test_title_too_long_fails(self) -> None:
        """测试超长标题不合规。"""
        long_title = "A" * 250
        state = self._make_state(title=long_title)
        state.copywriting_packages[Platform.AMAZON] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title=long_title,
            bullet_points=["Good product"],
            description="Test",
        )
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        report = result["compliance_reports"][Platform.AMAZON]
        assert report.is_pass is False
        assert any(issue.rule == "TXT-001" for issue in report.text_issues)

    def test_ebay_title_truncated(self) -> None:
        """测试 eBay 标题长度检查（80字符）。"""
        long_title = "A" * 100
        state = self._make_state(title=long_title, platforms=[Platform.EBAY])
        state.copywriting_packages[Platform.EBAY] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.EBAY,
            language="en",
            title=long_title,
        )
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        report = result["compliance_reports"][Platform.EBAY]
        assert report.is_pass is False

    def test_amazon_bullet_points_required(self) -> None:
        """测试 Amazon 五点描述必填。"""
        state = self._make_state()
        state.copywriting_packages[Platform.AMAZON] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Test",
            bullet_points=[],
        )
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        report = result["compliance_reports"][Platform.AMAZON]
        assert report.is_pass is False
        assert any(issue.rule == "TXT-002" for issue in report.text_issues)

    def test_forbidden_words_detected(self) -> None:
        """测试禁词检测。"""
        state = self._make_state(
            title="Best Wireless Headphones - 100% Quality",
            description="The best product ever",
        )
        state.copywriting_packages[Platform.AMAZON] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Best Wireless Headphones - 100% Quality",
            bullet_points=["The best quality"],
            description="100% perfect",
        )
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        report = result["compliance_reports"][Platform.AMAZON]
        assert len(report.forbidden_words) > 0
        assert report.overall == ComplianceStatus.WARNING

    def test_multi_platform_check(self) -> None:
        """测试多平台合规检查。"""
        state = self._make_state(
            platforms=[Platform.AMAZON, Platform.EBAY, Platform.SHOPIFY],
        )
        for platform in [Platform.AMAZON, Platform.EBAY, Platform.SHOPIFY]:
            state.copywriting_packages[platform] = CopywritingPackage(
                listing_task_id=1,
                platform=platform,
                language="en",
                title="Clean Product Title",
                bullet_points=["Good feature"],
                description="A clean product",
            )
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        assert len(result["compliance_reports"]) == 3
        for platform in [Platform.AMAZON, Platform.EBAY, Platform.SHOPIFY]:
            assert platform in result["compliance_reports"]

    def test_no_copywriting_package(self) -> None:
        """测试无文案包时不报错。"""
        state = self._make_state()
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        assert len(result["compliance_reports"]) == 1
        report = result["compliance_reports"][Platform.AMAZON]
        assert report.is_pass is True

    def test_amazon_search_terms_byte_limit(self) -> None:
        """测试 Amazon 搜索词字节限制。"""
        state = self._make_state()
        state.copywriting_packages[Platform.AMAZON] = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en",
            title="Test",
            bullet_points=["Feature"],
            search_terms=[
                "wireless",
                "bluetooth",
                "headphones",
                "noise-cancelling",
                "premium",
                "quality",
                "brand-new",
            ],
        )
        agent = ComplianceCheckerAgent()
        result = agent.execute_sync(state)
        report = result["compliance_reports"][Platform.AMAZON]
        total_bytes = len(
            " ".join(
                [
                    "wireless",
                    "bluetooth",
                    "headphones",
                    "noise-cancelling",
                    "premium",
                    "quality",
                    "brand-new",
                ]
            ).encode("utf-8")
        )
        if total_bytes > 249:
            assert report.is_pass is False
