"""
视觉设计Agent模块。

Description:
    负责具体的视觉设计工作。
    主要功能：
    - 构图设计
    - 图片提示词生成
    - 分镜脚本设计
@author ganjianfei
@version 1.0.0
2026-03-23
"""

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.models.creative import ImagePrompt, ImageType
from src.models.storyboard import (
    Scene,
    SceneType,
    ShotType,
    Storyboard,
    TransitionType,
)


class VisualDesignerAgent(BaseAgent[AgentState]):
    """视觉设计Agent。

    将创意方案转化为具体的视觉输出规格。

    Example:
        >>> agent = VisualDesignerAgent()
        >>> result = await agent.execute(state)
        >>> prompts = result.data.get("image_prompts")
    """

    def __init__(self, **kwargs: Any) -> None:
        """初始化视觉设计Agent。"""
        super().__init__(role=AgentRole.VISUAL_DESIGNER, **kwargs)
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # 图片提示词生成
        image_prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个专业的电商图片提示词专家。"
                    "请根据商品信息和创意方案，生成高质量的图片生成提示词。\n\n"
                    "提示词要素：\n"
                    "1. 主体描述：产品名称、特征\n"
                    "2. 场景设定：背景、环境\n"
                    "3. 光线效果：光线类型、方向\n"
                    "4. 构图方式：角度、位置\n"
                    "5. 风格关键词：视觉风格描述\n"
                    "6. 质量参数：清晰度、细节要求\n\n"
                    "输出JSON数组，每个元素包含：\n"
                    "- image_type: 图片类型（main/scene/selling_point/detail）\n"
                    "- prompt: 英文提示词\n"
                    "- negative_prompt: 负向提示词\n"
                    "- style_keywords: 风格关键词列表\n"
                    "- aspect_ratio: 宽高比",
                ),
                (
                    "human",
                    "商品名称：{product_name}\n"
                    "商品描述：{description}\n"
                    "核心卖点：{selling_points}\n"
                    "视觉风格：{visual_style}\n"
                    "配色方案：{color_palette}\n"
                    "需要生成的图片类型：{image_types}\n\n"
                    "请生成图片提示词。",
                ),
            ]
        )
        self.register_prompt("image_prompt", image_prompt_template)

        # 分镜脚本生成
        storyboard_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个专业的视频分镜设计师。"
                    "请根据商品信息和创意方案，设计视频分镜脚本。\n\n"
                    "分镜设计原则：\n"
                    "1. 开场吸引：前3秒抓住观众\n"
                    "2. 产品展示：清晰展示产品特点\n"
                    "3. 卖点呈现：逐个展示核心卖点\n"
                    "4. 情感共鸣：引发观众情感连接\n"
                    "5. 结尾号召：引导行动\n\n"
                    "输出JSON格式，包含：\n"
                    "- title: 分镜标题\n"
                    "- description: 整体描述\n"
                    "- scenes: 场景数组，每个包含scene_id, scene_type, duration, shot_type, description, visual_prompt",
                ),
                (
                    "human",
                    "商品名称：{product_name}\n"
                    "商品描述：{description}\n"
                    "核心卖点：{selling_points}\n"
                    "视频时长：{duration}秒\n"
                    "视觉风格：{visual_style}\n\n"
                    "请设计分镜脚本。",
                ),
            ]
        )
        self.register_prompt("storyboard", storyboard_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行视觉设计。

        Args:
            state: 当前状态。

        Returns:
            包含图片提示词和分镜脚本的结果。
        """
        try:
            product = state.product_info
            creative_plan = state.creative_plan

            if product is None:
                return AgentResult(
                    success=False,
                    error="缺少商品信息",
                )

            if creative_plan is None:
                return AgentResult(
                    success=False,
                    error="缺少创意方案",
                )

            # 判断需要生成的内容
            request = state.generation_request
            task_type = request.task_type if request else "image_and_video"

            result_data: dict[str, Any] = {}

            # 生成图片提示词
            if task_type in ["image_only", "image_and_video"]:
                image_prompts = await self._generate_image_prompts(
                    product, creative_plan, state
                )
                result_data["image_prompts"] = [
                    p.model_dump() for p in image_prompts
                ]
                state.generation_prompts = result_data["image_prompts"]

            # 生成分镜脚本
            if task_type in ["video_only", "image_and_video"]:
                storyboard = await self._generate_storyboard(
                    product, creative_plan, state
                )
                result_data["storyboard"] = storyboard.model_dump()
                state.storyboard = storyboard

            state.mark_step_completed("visual_design")

            # 根据任务类型确定下一个Agent
            if task_type == "image_only":
                next_agent = AgentRole.IMAGE_GENERATOR
            elif task_type == "video_only":
                next_agent = AgentRole.VIDEO_GENERATOR
            else:
                next_agent = AgentRole.IMAGE_GENERATOR  # 先执行图片生成

            return AgentResult(
                success=True,
                data=result_data,
                next_agent=next_agent,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"视觉设计失败: {e}",
            )

    async def _generate_image_prompts(
        self,
        product: Any,
        creative_plan: Any,
        state: AgentState,
    ) -> list[ImagePrompt]:
        """生成图片提示词。

        Args:
            product: 商品信息。
            creative_plan: 创意方案。
            state: 当前状态。

        Returns:
            图片提示词列表。
        """
        # 准备输入
        selling_points = (
            [sp.get("title", "") for sp in state.selling_points]
            if state.selling_points
            else []
        )
        image_types = (
            state.generation_request.image_types
            if state.generation_request
            else ["main"]
        )

        prompt = self.get_prompt("image_prompt")
        if prompt is None:
            return self._create_default_prompts(product, image_types)

        response = await self.invoke_llm(
            prompt,
            {
                "product_name": product.name,
                "description": product.description,
                "selling_points": str(selling_points),
                "visual_style": creative_plan.visual_style.value,
                "color_palette": creative_plan.color_palette.name,
                "image_types": str(image_types),
            },
        )

        return self._parse_image_prompts(response, image_types)

    def _parse_image_prompts(
        self, response: str, image_types: list[str]
    ) -> list[ImagePrompt]:
        """解析图片提示词响应。

        Args:
            response: LLM响应。
            image_types: 图片类型列表。

        Returns:
            图片提示词列表。
        """
        try:
            # 尝试解析JSON数组
            start = response.find("[")
            end = response.rfind("]") + 1
            if start != -1 and end > start:
                data_list = json.loads(response[start:end])
                prompts = []
                for data in data_list:
                    type_str = data.get("image_type", "main")
                    try:
                        image_type = ImageType(type_str)
                    except ValueError:
                        image_type = ImageType.MAIN

                    prompts.append(
                        ImagePrompt(
                            image_type=image_type,
                            prompt=data.get("prompt", ""),
                            negative_prompt=data.get("negative_prompt"),
                            style_keywords=data.get("style_keywords", []),
                            aspect_ratio=data.get("aspect_ratio", "1:1"),
                        )
                    )
                return prompts
        except json.JSONDecodeError:
            pass

        return self._create_default_prompts(None, image_types)

    def _create_default_prompts(
        self, product: Any, image_types: list[str]
    ) -> list[ImagePrompt]:
        """创建默认图片提示词。

        Args:
            product: 商品信息。
            image_types: 图片类型列表。

        Returns:
            默认图片提示词列表。
        """
        product_name = product.name if product else "Product"
        prompts = []

        for img_type in image_types:
            try:
                image_type = ImageType(img_type)
            except ValueError:
                image_type = ImageType.MAIN

            # 根据类型生成不同的提示词
            if image_type == ImageType.MAIN:
                prompt_text = (
                    f"Professional product photography of {product_name}, "
                    f"clean white background, studio lighting, "
                    f"high detail, 4k quality, commercial photography"
                )
            elif image_type == ImageType.SCENE:
                prompt_text = (
                    f"Lifestyle photography of {product_name} in use, "
                    f"modern interior setting, natural lighting, "
                    f"high quality, lifestyle shot"
                )
            elif image_type == ImageType.SELLING_POINT:
                prompt_text = (
                    f"Product feature highlight of {product_name}, "
                    f"detail shot showing key features, "
                    f"clean background, macro photography"
                )
            else:
                prompt_text = (
                    f"Product photography of {product_name}, "
                    f"professional quality, high detail"
                )

            prompts.append(
                ImagePrompt(
                    image_type=image_type,
                    prompt=prompt_text,
                    negative_prompt="blurry, low quality, watermark, text",
                    style_keywords=["professional", "clean", "high-quality"],
                    aspect_ratio="1:1",
                )
            )

        return prompts

    async def _generate_storyboard(
        self,
        product: Any,
        creative_plan: Any,
        state: AgentState,
    ) -> Storyboard:
        """生成分镜脚本。

        Args:
            product: 商品信息。
            creative_plan: 创意方案。
            state: 当前状态。

        Returns:
            分镜脚本。
        """
        duration = (
            state.generation_request.video_duration
            if state.generation_request
            else 30.0
        )
        selling_points = (
            [sp.get("title", "") for sp in state.selling_points]
            if state.selling_points
            else []
        )

        prompt = self.get_prompt("storyboard")
        if prompt is None:
            return self._create_default_storyboard(product, duration)

        response = await self.invoke_llm(
            prompt,
            {
                "product_name": product.name,
                "description": product.description,
                "selling_points": str(selling_points),
                "duration": duration,
                "visual_style": creative_plan.visual_style.value,
            },
        )

        return self._parse_storyboard(response, product, duration)

    def _parse_storyboard(
        self, response: str, product: Any, duration: float
    ) -> Storyboard:
        """解析分镜脚本响应。

        Args:
            response: LLM响应。
            product: 商品信息。
            duration: 视频时长。

        Returns:
            分镜脚本。
        """
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])

                scenes = []
                for i, scene_data in enumerate(data.get("scenes", [])):
                    scene_type_str = scene_data.get(
                        "scene_type", "product_intro"
                    )
                    try:
                        scene_type = SceneType(scene_type_str)
                    except ValueError:
                        scene_type = SceneType.PRODUCT_INTRO

                    shot_type_str = scene_data.get("shot_type", "medium")
                    try:
                        shot_type = ShotType(shot_type_str)
                    except ValueError:
                        shot_type = ShotType.MEDIUM

                    scenes.append(
                        Scene(
                            scene_id=i + 1,
                            scene_type=scene_type,
                            duration=float(scene_data.get("duration", 3.0)),
                            shot_type=shot_type,
                            description=scene_data.get("description", ""),
                            visual_prompt=scene_data.get("visual_prompt", ""),
                            transition_in=TransitionType.CUT,
                            transition_out=TransitionType.CUT,
                        )
                    )

                return Storyboard(
                    title=data.get("title", f"{product.name}产品视频"),
                    description=data.get("description", ""),
                    total_duration=duration,
                    scenes=scenes,
                    visual_style="modern",
                )
        except json.JSONDecodeError:
            pass

        return self._create_default_storyboard(product, duration)

    def _create_default_storyboard(
        self, product: Any, duration: float
    ) -> Storyboard:
        """创建默认分镜脚本。

        Args:
            product: 商品信息。
            duration: 视频时长。

        Returns:
            默认分镜脚本。
        """
        # 创建基础场景模板
        scene_duration = duration / 5

        scenes = [
            Scene(
                scene_id=1,
                scene_type=SceneType.PRODUCT_INTRO,
                duration=scene_duration,
                shot_type=ShotType.MEDIUM,
                description="产品开场展示",
                visual_prompt=f"Product hero shot of {product.name}, dramatic lighting",
                transition_in=TransitionType.FADE,
                transition_out=TransitionType.DISSOLVE,
            ),
            Scene(
                scene_id=2,
                scene_type=SceneType.FEATURE_HIGHLIGHT,
                duration=scene_duration,
                shot_type=ShotType.CLOSE_UP,
                description="功能特性展示",
                visual_prompt=f"Feature highlight of {product.name}, detail shot",
                transition_in=TransitionType.DISSOLVE,
                transition_out=TransitionType.CUT,
            ),
            Scene(
                scene_id=3,
                scene_type=SceneType.USAGE_SCENARIO,
                duration=scene_duration,
                shot_type=ShotType.WIDE,
                description="使用场景展示",
                visual_prompt=f"Lifestyle shot of {product.name} in use",
                transition_in=TransitionType.CUT,
                transition_out=TransitionType.DISSOLVE,
            ),
            Scene(
                scene_id=4,
                scene_type=SceneType.BRAND_MOMENT,
                duration=scene_duration,
                shot_type=ShotType.MEDIUM,
                description="品牌时刻",
                visual_prompt=f"Brand moment with {product.name}, premium feel",
                transition_in=TransitionType.DISSOLVE,
                transition_out=TransitionType.FADE,
            ),
            Scene(
                scene_id=5,
                scene_type=SceneType.CALL_TO_ACTION,
                duration=scene_duration,
                shot_type=ShotType.MEDIUM,
                description="行动号召",
                visual_prompt=f"Call to action shot, {product.name} with CTA",
                transition_in=TransitionType.FADE,
                transition_out=TransitionType.FADE,
            ),
        ]

        return Storyboard(
            title=f"{product.name}产品介绍",
            description="产品营销视频分镜",
            total_duration=duration,
            scenes=scenes,
            visual_style="modern",
        )
