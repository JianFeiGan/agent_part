"""模型厂商预置数据 Seeder。

Description:
    应用启动时检查 model_providers 表是否为空，
    为每个租户 seed 预置的厂商配置（商汤、阿里云、可灵）。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ModelProviderPO

logger = logging.getLogger(__name__)

# 预置厂商配置模板（不含 tenant_id，seed 时按租户填充）
_PRESET_PROVIDERS: list[dict] = [
    # ===== LLM =====
    {
        "name": "sensenova",
        "display_name": "商汤科技",
        "provider_type": "llm",
        "base_url": "https://token.sensenova.cn/v1",
        "default_model": "deepseek-v4-flash",
        "supported_models": [
            "deepseek-v4-flash",
            "sensenova-6.7-flash-lite",
        ],
        "protocol": "openai_compatible",
        "is_default": True,
    },
    {
        "name": "dashscope",
        "display_name": "阿里云通义",
        "provider_type": "llm",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "supported_models": [
            "qwen-plus",
            "qwen-turbo",
            "qwen-max",
            "qwen3.5-flash",
        ],
        "protocol": "openai_compatible",
        "is_default": False,
    },
    # ===== 图片生成 =====
    {
        "name": "sensenova",
        "display_name": "商汤科技",
        "provider_type": "image",
        "base_url": "https://token.sensenova.cn/v1",
        "default_model": "sensenova-u1-fast",
        "supported_models": [
            "sensenova-u1-fast",
        ],
        "protocol": "openai_compatible",
        "is_default": False,
    },
    {
        "name": "dashscope",
        "display_name": "阿里云通义",
        "provider_type": "image",
        "base_url": "https://dashscope.aliyuncs.com/api/v1",
        "default_model": "wanx-v1",
        "supported_models": [
            "wanx-v1",
            "wanx-sketch-to-image-v1",
        ],
        "protocol": "custom_rest",
        "is_default": True,
    },
    # ===== 视频生成 =====
    {
        "name": "kling",
        "display_name": "可灵AI",
        "provider_type": "video",
        "base_url": "https://api.klingai.com",
        "default_model": "kling-v1",
        "supported_models": [
            "kling-v1",
            "kling-v1-5",
            "kling-v2",
        ],
        "protocol": "custom_rest",
        "is_default": True,
    },
]


async def seed_model_providers(session: AsyncSession, tenant_id: str) -> None:
    """为指定租户 seed 预置厂商配置。

    仅当该租户没有任何厂商配置时才执行 seed，避免重复写入。

    Args:
        session: 异步数据库会话。
        tenant_id: 租户 ID。
    """
    # 检查是否已有配置
    stmt = (
        select(ModelProviderPO)
        .where(ModelProviderPO.tenant_id == tenant_id)
        .limit(1)
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        return

    # Seed 预置配置
    for preset in _PRESET_PROVIDERS:
        po = ModelProviderPO(
            tenant_id=tenant_id,
            name=preset["name"],
            display_name=preset["display_name"],
            provider_type=preset["provider_type"],
            base_url=preset["base_url"],
            api_key={},  # 空 dict，用户需在前端配置
            extra_credentials={},
            default_model=preset["default_model"],
            supported_models=preset["supported_models"],
            model_config_extra={},
            protocol=preset["protocol"],
            is_active=True,
            is_default=preset["is_default"],
        )
        session.add(po)

    await session.flush()
    logger.info("已为租户 %s seed %d 条预置厂商配置", tenant_id, len(_PRESET_PROVIDERS))
