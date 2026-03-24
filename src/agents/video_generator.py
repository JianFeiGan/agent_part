"""
视频生成Agent模块。

Description:
    负责生成商品营销视频。
    主要功能：
    - 分镜脚本解析
    - 场景素材生成
    - 视频合成输出
    - 调用可灵AI API
@author ganjianfei
@version 1.0.0
2026-03-23
"""

import uuid
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.models.assets import AssetStatus, GeneratedVideo, VideoFormat
from src.models.storyboard import Scene


class VideoGeneratorAgent(BaseAgent[AgentState]):
    """视频生成Agent。

    根据分镜脚本生成商品营销视频。

    Example:
        >>> agent = VideoGeneratorAgent()
        >>> result = await agent.execute(state)
        >>> video = result.data.get("generated_video")
    """

    def __init__(self, **kwargs: Any) -> None:
        """初始化视频生成Agent。"""
        super().__init__(role=AgentRole.VIDEO_GENERATOR, **kwargs)
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # 场景提示词优化
        scene_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个AI视频提示词专家。"
                    "请将分镜描述转换为适合AI视频生成的提示词。\n\n"
                    "要点：\n"
                    "1. 描述动态效果\n"
                    "2. 明确镜头运动\n"
                    "3. 指定场景氛围\n"
                    "4. 控制在合理长度",
                ),
                (
                    "human",
                    "场景描述：{description}\n"
                    "镜头类型：{shot_type}\n"
                    "场景类型：{scene_type}\n"
                    "风格：{style}\n\n"
                    "请生成视频提示词。",
                ),
            ]
        )
        self.register_prompt("scene", scene_prompt)

        # 视频组合提示
        composition_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个视频剪辑专家。"
                    "请根据分镜脚本设计视频组合方案。\n\n"
                    "输出：\n"
                    "- 转场效果建议\n"
                    "- 音频配合建议\n"
                    "- 节奏控制建议",
                ),
                (
                    "human",
                    "分镜脚本：{storyboard}\n\n"
                    "请设计组合方案。",
                ),
            ]
        )
        self.register_prompt("composition", composition_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行视频生成。

        Args:
            state: 当前状态。

        Returns:
            包含生成视频的结果。
        """
        try:
            storyboard = state.storyboard
            if storyboard is None:
                return AgentResult(
                    success=False,
                    error="缺少分镜脚本",
                )

            # 生成视频
            video = await self._generate_video(storyboard, state)

            # 更新状态
            state.generated_video = video
            state.mark_step_completed("video_generation")

            return AgentResult(
                success=True,
                data={
                    "generated_video": video.model_dump(),
                },
                next_agent=AgentRole.QUALITY_REVIEWER,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"视频生成失败: {e}",
            )

    async def _generate_video(
        self,
        storyboard: Any,
        state: AgentState,
    ) -> GeneratedVideo:
        """生成视频。

        Args:
            storyboard: 分镜脚本。
            state: 当前状态。

        Returns:
            生成的视频。
        """
        # 生成视频ID
        video_id = f"vid_{uuid.uuid4().hex[:8]}"

        # 获取分辨率
        resolution = storyboard.resolution
        width, height = self._parse_resolution(resolution)

        # 处理场景
        scene_prompts = await self._process_scenes(
            storyboard.scenes,
            storyboard.visual_style,
        )

        # 调用视频生成API
        video = await self._call_video_api(
            video_id=video_id,
            storyboard=storyboard,
            scene_prompts=scene_prompts,
            width=width,
            height=height,
        )

        return video

    def _parse_resolution(self, resolution: str) -> tuple[int, int]:
        """解析分辨率。

        Args:
            resolution: 分辨率字符串。

        Returns:
            (宽度, 高度) 元组。
        """
        resolution_map: dict[str, tuple[int, int]] = {
            "4k": (3840, 2160),
            "2k": (2560, 1440),
            "1080p": (1920, 1080),
            "720p": (1280, 720),
            "480p": (854, 480),
        }
        return resolution_map.get(resolution.lower(), (1920, 1080))

    async def _process_scenes(
        self,
        scenes: list[Scene],
        visual_style: str,
    ) -> list[dict[str, Any]]:
        """处理场景列表。

        Args:
            scenes: 场景列表。
            visual_style: 视觉风格。

        Returns:
            处理后的场景提示词列表。
        """
        processed_scenes = []

        for scene in scenes:
            # 优化场景提示词
            prompt = await self._optimize_scene_prompt(
                scene, visual_style
            )
            processed_scenes.append({
                "scene_id": scene.scene_id,
                "prompt": prompt,
                "duration": scene.duration,
                "shot_type": scene.shot_type.value,
            })

        return processed_scenes

    async def _optimize_scene_prompt(
        self,
        scene: Scene,
        visual_style: str,
    ) -> str:
        """优化场景提示词。

        Args:
            scene: 场景对象。
            visual_style: 视觉风格。

        Returns:
            优化后的提示词。
        """
        prompt_template = self.get_prompt("scene")
        if prompt_template is None:
            return scene.visual_prompt

        try:
            optimized = await self.invoke_llm(
                prompt_template,
                {
                    "description": scene.description,
                    "shot_type": scene.shot_type.value,
                    "scene_type": scene.scene_type.value,
                    "style": visual_style,
                },
            )
            return optimized
        except Exception:
            return scene.visual_prompt

    async def _call_video_api(
        self,
        video_id: str,
        storyboard: Any,
        scene_prompts: list[dict[str, Any]],
        width: int,
        height: int,
    ) -> GeneratedVideo:
        """调用视频生成API。

        Args:
            video_id: 视频ID。
            storyboard: 分镜脚本。
            scene_prompts: 场景提示词列表。
            width: 宽度。
            height: 高度。

        Returns:
            生成的视频。
        """
        # 创建视频对象
        video = GeneratedVideo(
            video_id=video_id,
            title=storyboard.title,
            storyboard_id=storyboard.storyboard_id,
            visual_prompt=str(scene_prompts),
            url=None,
            local_path=None,
            format=VideoFormat.MP4,
            width=width,
            height=height,
            duration=storyboard.total_duration,
            fps=30,
            status=AssetStatus.GENERATING,
            model="kling-v1",
        )

        # TODO: 实际调用可灵AI API
        # 模拟生成完成
        video.status = AssetStatus.COMPLETED
        video.url = f"https://example.com/videos/{video_id}.mp4"

        return video


# 定义LangChain工具
@tool
async def generate_product_video(
    storyboard: dict,
    style: str = "professional",
    duration: float = 30.0,
) -> dict:
    """生成商品视频工具。

    Args:
        storyboard: 分镜脚本字典。
        style: 风格，默认professional。
        duration: 时长，默认30秒。

    Returns:
        生成结果字典。
    """
    return {
        "success": True,
        "video": {
            "url": f"https://example.com/videos/{uuid.uuid4().hex[:8]}.mp4",
            "duration": duration,
            "resolution": "1080p",
        },
    }


@tool
async def generate_storyboard(
    product_info: dict,
    video_duration: float,
    video_style: str,
    key_selling_points: list[str],
) -> dict:
    """生成视频分镜脚本工具。

    自动划分场景、设计镜头语言。

    Args:
        product_info: 商品信息字典。
        video_duration: 视频时长。
        video_style: 视频风格。
        key_selling_points: 关键卖点列表。

    Returns:
        分镜脚本字典。
    """
    # 计算场景数量
    num_scenes = max(3, int(video_duration / 5))

    scenes = []
    for i in range(num_scenes):
        scenes.append({
            "scene_id": i + 1,
            "duration": video_duration / num_scenes,
            "description": f"场景 {i + 1}",
            "shot_type": "medium",
        })

    return {
        "success": True,
        "storyboard": {
            "title": f"{product_info.get('name', '产品')}视频",
            "total_duration": video_duration,
            "scenes": scenes,
        },
    }
