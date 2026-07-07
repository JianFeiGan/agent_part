"""
图片生成Agent模块。

Description:
    负责调用图像生成API产出商品图片。
    主要功能：
    - 调用通义万象API生成图片
    - 管理图片规格和质量
    - 处理批量生成请求
@author ganjianfei
@version 1.0.0
2026-03-23
"""

import base64
import logging
import uuid
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.clients import get_image_client
from src.clients.dashscope_image_client import DashScopeImageClient
from src.clients.provider_result import ProviderUnavailableError
from src.db.asset_repository import AssetRepository
from src.models.assets import AssetStatus, GeneratedImage, ImageFormat
from src.models.creative import ImageType
from src.storage.base import StorageBackend
from src.storage.factory import get_storage_backend

logger = logging.getLogger(__name__)


class ImageGenerationInput:
    """图片生成输入参数。"""

    prompt: str
    negative_prompt: str | None
    width: int
    height: int
    style: str
    num_images: int


# 1x1 透明 PNG 的 base64 编码（最小合法 PNG）
_EMPTY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+"
    "hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
)


class ImageGeneratorAgent(BaseAgent[AgentState]):
    """图片生成Agent。

    调用图像生成服务生成商品图片。

    Example:
        >>> agent = ImageGeneratorAgent()
        >>> result = await agent.execute(state)
        >>> images = result.data.get("generated_images")
    """

    def __init__(
        self,
        storage_backend: StorageBackend | None = None,
        session_factory: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """初始化图片生成Agent。

        Args:
            storage_backend: 可选的存储后端，默认从 factory 获取。
            session_factory: 可选的 AsyncSession 工厂，用于 DB 写入。
            **kwargs: 传递给 BaseAgent 的参数。
        """
        super().__init__(role=AgentRole.IMAGE_GENERATOR, **kwargs)
        self._storage_backend = storage_backend
        self._session_factory = session_factory
        self._image_client: DashScopeImageClient | None = get_image_client(
            settings=self.settings
        )
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # 图片优化提示
        optimize_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个AI图片提示词优化专家。"
                    "请优化输入的提示词，使其更适合AI图片生成。\n\n"
                    "优化原则：\n"
                    "1. 添加专业摄影术语\n"
                    "2. 明确光线和构图\n"
                    "3. 添加质量提升词\n"
                    "4. 控制在合理长度",
                ),
                (
                    "human",
                    "原始提示词：{prompt}\n"
                    "图片类型：{image_type}\n"
                    "风格要求：{style}\n\n"
                    "请优化提示词。",
                ),
            ]
        )
        self.register_prompt("optimize", optimize_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行图片生成。

        Args:
            state: 当前状态。

        Returns:
            包含生成图片的结果。
        """
        try:
            prompts = state.generation_prompts
            if not prompts:
                return AgentResult(
                    success=False,
                    error="缺少图片提示词",
                )

            generated_images: list[GeneratedImage] = []

            # 批量生成图片
            for prompt_data in prompts:
                images = await self._generate_images(
                    prompt_data,
                    state,
                )
                generated_images.extend(images)

            # 更新状态
            state.generated_images = generated_images
            state.mark_step_completed("image_generation")

            return AgentResult(
                success=True,
                data={
                    "generated_images": [img.model_dump() for img in generated_images],
                    "total_count": len(generated_images),
                },
                next_agent=AgentRole.QUALITY_REVIEWER,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"图片生成失败: {e}",
            )

    async def _generate_images(
        self,
        prompt_data: dict[str, Any],
        _state: AgentState,
    ) -> list[GeneratedImage]:
        """生成图片。

        Args:
            prompt_data: 提示词数据。
            _state: 当前状态。

        Returns:
            生成的图片列表。
        """
        prompt_text = prompt_data.get("prompt", "")
        negative_prompt = prompt_data.get("negative_prompt")
        style_keywords = prompt_data.get("style_keywords", [])
        aspect_ratio = prompt_data.get("aspect_ratio", "1:1")

        # 解析图片类型
        type_str = prompt_data.get("image_type", "main")
        try:
            image_type = ImageType(type_str)
        except ValueError:
            image_type = ImageType.MAIN

        # 解析宽高比
        width, height = self._parse_aspect_ratio(aspect_ratio)

        # 优化提示词
        optimized_prompt = await self._optimize_prompt(
            prompt_text, image_type.value, style_keywords
        )

        # 调用图片生成API
        images = await self._call_image_api(
            prompt=optimized_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            image_type=image_type.value,
            state=_state,
        )

        return images

    def _parse_aspect_ratio(self, ratio: str) -> tuple[int, int]:
        """解析宽高比。

        Args:
            ratio: 宽高比字符串。

        Returns:
            (宽度, 高度) 元组。
        """
        ratio_map: dict[str, tuple[int, int]] = {
            "1:1": (1024, 1024),
            "4:3": (1024, 768),
            "3:4": (768, 1024),
            "16:9": (1920, 1080),
            "9:16": (1080, 1920),
            "3:2": (1536, 1024),
            "2:3": (1024, 1536),
        }
        return ratio_map.get(ratio, (1024, 1024))

    async def _optimize_prompt(
        self,
        prompt: str,
        image_type: str,
        style_keywords: list[str],
    ) -> str:
        """优化提示词。

        Args:
            prompt: 原始提示词。
            image_type: 图片类型。
            style_keywords: 风格关键词。

        Returns:
            优化后的提示词。
        """
        prompt_template = self.get_prompt("optimize")
        if prompt_template is None:
            return self._default_optimize(prompt, style_keywords)

        try:
            optimized = await self.invoke_llm(
                prompt_template,
                {
                    "prompt": prompt,
                    "image_type": image_type,
                    "style": str(style_keywords),
                },
            )
            return optimized
        except Exception:
            return self._default_optimize(prompt, style_keywords)

    def _default_optimize(self, prompt: str, style_keywords: list[str]) -> str:
        """默认提示词优化。

        Args:
            prompt: 原始提示词。
            style_keywords: 风格关键词。

        Returns:
            优化后的提示词。
        """
        quality_words = [
            "professional photography",
            "high quality",
            "detailed",
            "4k",
            "sharp focus",
        ]
        style_str = ", ".join(style_keywords) if style_keywords else ""
        quality_str = ", ".join(quality_words)

        parts = [prompt]
        if style_str:
            parts.append(style_str)
        parts.append(quality_str)

        return ", ".join(parts)

    def _resolve_tenant_id(self, state: AgentState) -> str:
        """从 state 中解析 tenant_id。

        TODO: GenerationRequest 当前没有 tenant_id 字段。
        后续需要添加 tenant_id 到 GenerationRequest 或 AgentState。

        Args:
            state: 当前 AgentState。

        Returns:
            tenant_id 字符串。
        """
        # 尝试从 generation_request 获取（当前没有该字段）
        if state.generation_request is not None:
            req_tenant = getattr(state.generation_request, "tenant_id", None)
            if req_tenant:
                return req_tenant
        # 尝试从 product_info 获取
        if state.product_info is not None:
            prod_tenant = getattr(state.product_info, "tenant_id", None)
            if prod_tenant:
                return prod_tenant
        # 尝试从 state 顶层获取
        state_tenant = getattr(state, "tenant_id", None)
        if state_tenant:
            return state_tenant
        logger.warning("No tenant_id found in state; falling back to 'system'.")
        return "system"

    async def _write_asset_to_storage(
        self,
        data: bytes,
        tenant_id: str,
        image_id: str,
        mime_type: str,
    ) -> str:
        """将二进制数据写入存储后端并返回 URL。

        Args:
            data: 文件二进制数据。
            tenant_id: 租户 ID。
            image_id: 图片 ID。
            mime_type: MIME 类型。

        Returns:
            可访问 URL。
        """
        backend = self._storage_backend or get_storage_backend()
        key = f"images/{tenant_id}/{image_id}.png"
        url = await backend.save(data, key, content_type=mime_type)
        return url

    async def _create_asset_po(
        self,
        session: AsyncSession,
        tenant_id: str,
        url: str,
        storage_key: str,
        data: bytes,
        image_id: str,
        prompt: str,
        width: int,
        height: int,
        mime_type: str,
        provider: str = "mock",
        is_mock: bool = True,
    ) -> None:
        """在数据库中创建 GeneratedAssetPO 记录。

        Args:
            session: 异步数据库会话。
            tenant_id: 租户 ID。
            url: 可访问 URL。
            storage_key: 存储键名。
            data: 文件二进制数据。
            image_id: 图片 ID。
            prompt: 生成提示词。
            width: 宽度。
            height: 高度。
            mime_type: MIME 类型。
            provider: 生成提供方（真实为模型名，降级为 "mock"）。
            is_mock: 是否为 Mock 占位（真实为 False）。
        """
        from src.storage.local import LocalStorageBackend

        sha256 = LocalStorageBackend.compute_sha256(data)
        repo = AssetRepository(session)
        await repo.create_asset(
            tenant_id=tenant_id,
            asset_type="image",
            provider=provider,
            url=url,
            storage_key=storage_key,
            storage_backend="local",
            mime_type=mime_type,
            file_size=len(data),
            width=width,
            height=height,
            sha256=sha256,
            status="completed",
            is_mock=is_mock,
            extra_data={"prompt": prompt, "image_id": image_id},
        )

    async def _call_image_api(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int,
        height: int,
        image_type: str,
        state: AgentState | None = None,
        session: AsyncSession | None = None,
    ) -> list[GeneratedImage]:
        """调用图片生成API。

        Args:
            prompt: 提示词。
            negative_prompt: 负向提示词。
            width: 宽度。
            height: 高度。
            image_type: 图片类型。
            state: 当前 AgentState（用于获取 tenant_id）。
            session: 可选的 AsyncSession（用于写 DB）。

        Returns:
            生成的图片列表。
        """
        # 生成图片ID
        image_id = f"img_{uuid.uuid4().hex[:8]}"

        # 解析 tenant_id
        tenant_id = "system"
        if state is not None:
            tenant_id = self._resolve_tenant_id(state)

        # 真实路径：调用 DashScope 通义万象
        if self._image_client is not None:
            try:
                result = await self._image_client.generate(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    width=width,
                    height=height,
                    n=1,
                    seed=None,
                )
                image_bytes = result.images[0].data
                storage_key = f"images/{tenant_id}/{image_id}.png"
                url = await self._write_asset_to_storage(
                    image_bytes,
                    tenant_id,
                    image_id,
                    "image/png",
                )
                model_name = self.settings.image_model
                if session is not None:
                    await self._create_asset_po(
                        session=session,
                        tenant_id=tenant_id,
                        url=url,
                        storage_key=storage_key,
                        data=image_bytes,
                        image_id=image_id,
                        prompt=prompt,
                        width=width,
                        height=height,
                        mime_type="image/png",
                        provider=model_name,
                        is_mock=False,
                    )
                image = GeneratedImage(
                    image_id=image_id,
                    image_type=image_type,
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    url=url,
                    local_path=None,
                    format=ImageFormat.PNG,
                    width=width,
                    height=height,
                    file_size=len(image_bytes),
                    status=AssetStatus.COMPLETED,
                    model=model_name,
                    metadata={
                        "provider": model_name,
                        "is_mock": False,
                        "remote_url": result.images[0].url,
                        "seed": result.images[0].seed,
                    },
                )
                return [image]
            except ProviderUnavailableError as exc:
                logger.error("provider=dashscope 真实图片生成失败，回退 mock: %s", exc)
        else:
            logger.warning(
                "provider=dashscope 未配置 API Key，回退 mock 占位行为 (tenant=%s)",
                tenant_id,
            )

        # 降级 / Mock 占位路径（与无 key 的 CI / 本地行为逐字节一致）
        placeholder_bytes = base64.b64decode(_EMPTY_PNG_BASE64)
        storage_key = f"images/{tenant_id}/{image_id}.png"
        url = await self._write_asset_to_storage(
            placeholder_bytes,
            tenant_id,
            image_id,
            "image/png",
        )

        # 写入数据库（如果有 session）
        if session is not None:
            await self._create_asset_po(
                session=session,
                tenant_id=tenant_id,
                url=url,
                storage_key=storage_key,
                data=placeholder_bytes,
                image_id=image_id,
                prompt=prompt,
                width=width,
                height=height,
                mime_type="image/png",
                provider="mock",
                is_mock=True,
            )

        image = GeneratedImage(
            image_id=image_id,
            image_type=image_type,
            prompt=prompt,
            negative_prompt=negative_prompt,
            url=url,
            local_path=None,
            format=ImageFormat.PNG,
            width=width,
            height=height,
            file_size=len(placeholder_bytes),
            status=AssetStatus.COMPLETED,
            model=self.settings.image_model,
            metadata={
                "provider": "mock",
                "is_mock": True,
                "note": "Placeholder asset generated by mock provider; not a real media URL.",
            },
        )

        return [image]


# 定义LangChain工具
@tool
async def generate_product_image(
    prompt: str,
    style: str = "realistic",
    aspect_ratio: str = "1:1",
    num_images: int = 1,
) -> dict:
    """生成商品图片工具。

    Args:
        prompt: 图片生成提示词。
        style: 风格，默认realistic。
        aspect_ratio: 宽高比，默认1:1。
        num_images: 生成数量，默认1。

    Returns:
        生成结果字典。
    """
    # 实际实现应调用图像生成API
    return {
        "success": True,
        "images": [
            {
                "url": f"mock://images/{uuid.uuid4().hex[:8]}.png",
                "width": 1024,
                "height": 1024,
                "metadata": {
                    "provider": "mock",
                    "is_mock": True,
                    "note": "Placeholder asset generated by mock provider; not a real media URL.",
                },
            }
        ],
    }
