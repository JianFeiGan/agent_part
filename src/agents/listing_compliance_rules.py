"""
平台合规检查规则。

Description:
    定义各平台特有的合规规则，包括图片规范、文案规范、禁词列表等。
    Phase 2 使用规则检查，后续可扩展 AI 辅助审核。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from dataclasses import dataclass, field

# 通用禁词列表（广告法禁止词汇 + 平台敏感词）
FORBIDDEN_WORDS: list[str] = [
    # 广告法禁止词汇
    "最佳",
    "最好",
    "最优",
    "最强",
    "最低",
    "最低价",
    "最便宜",
    "第一",
    "唯一",
    "首个",
    "全网第一",
    "全国第一",
    "绝对",
    "100%",
    "百分百",
    "完全",
    "彻底",
    "国家级",
    "世界级",
    "顶级",
    "极品",
    "极值",
    "万能",
    "无敌",
    "史上最",
    "永久",
    # 平台敏感词
    "free shipping",
    "free delivery",
    "包邮",
    "免邮",
    "guarantee",
    "warranty",
    "保修",
    "质保",
    "best seller",
    "hot sale",
    "爆款",
]


@dataclass
class ImageRule:
    """图片合规规则。"""

    rule_id: str
    name: str
    description: str
    check_field: str  # 检查的字段


@dataclass
class TextRule:
    """文案合规规则。"""

    rule_id: str
    name: str
    description: str
    max_length: int | None = None
    required: bool = False
    check_field: str = ""


@dataclass(frozen=True)
class ComplianceRules:
    """平台合规规则集。"""

    image_rules: list[ImageRule] = field(default_factory=list)
    text_rules: list[TextRule] = field(default_factory=list)
    forbidden_words: list[str] = field(default_factory=lambda: FORBIDDEN_WORDS.copy())


def get_compliance_rules(platform: str) -> ComplianceRules:
    """获取平台的合规规则集。

    Args:
        platform: 平台名称（amazon/ebay/shopify）。

    Returns:
        平台合规规则集。
    """
    amazon = ComplianceRules(
        image_rules=[
            ImageRule("IMG-001", "主图白底", "主图必须为纯白色背景", "main_image"),
            ImageRule("IMG-002", "图片尺寸", "主图尺寸不小于 1500x1500", "main_image"),
            ImageRule("IMG-003", "图片数量", "图片总数不超过 9 张", "variant_images"),
        ],
        text_rules=[
            TextRule(
                "TXT-001", "标题长度", "标题不超过 200 字符", max_length=200, check_field="title"
            ),
            TextRule(
                "TXT-002",
                "五点描述",
                "必须提供五点描述",
                required=True,
                check_field="bullet_points",
            ),
            TextRule(
                "TXT-003",
                "搜索词",
                "搜索词总字节数不超过 249",
                max_length=249,
                check_field="search_terms",
            ),
        ],
    )
    ebay = ComplianceRules(
        image_rules=[
            ImageRule("IMG-001", "主图白底", "主图必须为纯白色背景", "main_image"),
            ImageRule("IMG-002", "图片尺寸", "主图尺寸不小于 1600x1600", "main_image"),
            ImageRule("IMG-003", "图片数量", "图片总数不超过 12 张", "variant_images"),
        ],
        text_rules=[
            TextRule(
                "TXT-001", "标题长度", "标题不超过 80 字符", max_length=80, check_field="title"
            ),
        ],
    )
    shopify = ComplianceRules(
        image_rules=[
            ImageRule("IMG-001", "图片尺寸", "推荐尺寸 2048x2048", "main_image"),
        ],
        text_rules=[],
    )

    rules_map: dict[str, ComplianceRules] = {
        "amazon": amazon,
        "ebay": ebay,
        "shopify": shopify,
    }
    return rules_map.get(platform, ComplianceRules())
