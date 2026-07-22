"""视觉生成产物落库服务。

Description:
    将视觉生成工作流产出的 GeneratedImage / GeneratedVideo
    持久化到 PostgreSQL 的 generated_assets 表，供刊登工作流
    后续通过 product_id 拉取使用。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

import logging
from typing import Any

from src.db.asset_repository import AssetRepository
from src.models.assets import GeneratedImage

logger = logging.getLogger(__name__)


class AssetPersister:
    """视觉产物落库服务。

    将 GeneratedImage 列表写入 generated_assets 表，
    关联 product_id 和 task_id，供刊登流程复用。

    Attributes:
        _repo: AssetRepository 实例。
    """

    def __init__(self, *, repo: AssetRepository | Any = None, session: Any = None) -> None:
        """初始化。

        Args:
            repo: 可选的 AssetRepository 实例（测试注入）。
            session: 可选的数据库会话，未提供 repo 时用于创建。
        """
        if repo is not None:
            self._repo = repo
        elif session is not None:
            self._repo = AssetRepository(session)
        else:
            raise ValueError("必须提供 repo 或 session")

    async def persist_images(
        self,
        *,
        tenant_id: str,
        product_id: str,
        task_id: str,
        images: list[GeneratedImage],
    ) -> int:
        """将生成的图片列表落库。

        Args:
            tenant_id: 租户 ID。
            product_id: 关联商品 ID。
            task_id: 生成任务 ID。
            images: 生成的图片列表。

        Returns:
            成功落库的图片数量。
        """
        count = 0
        for img in images:
            if not img.is_ready():
                logger.warning(f"跳过未就绪图片: {img.image_id}")
                continue

            is_mock = img.model == "mock"
            url = img.url or f"/output/{img.local_path}"
            storage_key = img.local_path or img.url or img.image_id

            await self._repo.create_asset(
                tenant_id=tenant_id,
                product_id=product_id,
                task_id=task_id,
                asset_type="image",
                provider=img.model or "wanx",
                url=url,
                storage_key=storage_key,
                storage_backend="local",
                mime_type=f"image/{img.format.value}",
                width=img.width,
                height=img.height,
                file_size=img.file_size,
                status="completed",
                is_mock=is_mock,
                extra_data={
                    "image_type": img.image_type,
                    "image_id": img.image_id,
                    "prompt": (img.prompt or "")[:500],
                },
            )
            count += 1
            logger.info(f"图片落库: image_id={img.image_id}, product_id={product_id}")

        return count
