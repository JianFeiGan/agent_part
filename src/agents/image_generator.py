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

import uuid
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.models.assets import AssetStatus, GeneratedImage, ImageFormat
from src.models.creative import ImageType


class ImageGenerationInput:
    """图片生成输入参数。"""

    prompt: str
    negative_prompt: str | None
    width: int
    height: int
    style: str
    num_images: int


class ImageGeneratorAgent(BaseAgent[AgentState]):
    """图片生成Agent。

    调用图像生成服务生成商品图片。

    Example:
        >>> agent = ImageGeneratorAgent()
        >>> result = await agent.execute(state)
        >>> images = result.data.get("generated_images")
    """

    def __init__(self, **kwargs: Any) -> None:
        """初始化图片生成Agent。"""
        super().__init__(role=AgentRole.IMAGE_GENERATOR, **kwargs)
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
        state: AgentState,
    ) -> list[GeneratedImage]:
        """生成图片。

        Args:
            prompt_data: 提示词数据。
            state: 当前状态。

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

    async def _call_image_api(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int,
        height: int,
        image_type: str,
    ) -> list[GeneratedImage]:
        """调用图片生成API。

        Args:
            prompt: 提示词。
            negative_prompt: 负向提示词。
            width: 宽度。
            height: 高度。
            image_type: 图片类型。

        Returns:
            生成的图片列表。
        """
        # 生成图片ID
        image_id = f"img_{uuid.uuid4().hex[:8]}"

        # TODO: 实际调用通义万象API
        # 这里返回模拟结果
        image = GeneratedImage(
            image_id=image_id,
            image_type=image_type,
            prompt=prompt,
            negative_prompt=negative_prompt,
            url=None,  # API返回的URL
            local_path=None,
            format=ImageFormat.PNG,
            width=width,
            height=height,
            status=AssetStatus.PENDING,
            model="wanx-v1",
        )

        # 模拟生成完成
        image.status = AssetStatus.COMPLETED
        image.url = f"https://example.com/images/{image_id}.png"

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
                "url": f"https://example.com/images/{uuid.uuid4().hex[:8]}.png",
                "width": 1024,
                "height": 1024,
            }
        ],
    }
