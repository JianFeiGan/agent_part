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

import base64
import logging
import uuid
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.clients import get_video_client
from src.clients.kling_video_client import KlingVideoClient
from src.clients.provider_result import ProviderUnavailableError
from src.db.asset_repository import AssetRepository
from src.models.assets import AssetStatus, GeneratedVideo, VideoFormat
from src.models.storyboard import Scene
from src.storage.base import StorageBackend
from src.storage.factory import get_storage_backend

logger = logging.getLogger(__name__)

# 最小可解析的 MP4 文件 base64（ftyp + moov atom，1x1 像素）
_EMPTY_MP4_BASE64 = (
    "AAAAGGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAAhtZGF0AAAA"
    "AQAAAAEAAAAAAAAAAAAAAAAAAA=="
)


class VideoGeneratorAgent(BaseAgent[AgentState]):
    """视频生成Agent。

    根据分镜脚本生成商品营销视频。

    Example:
        >>> agent = VideoGeneratorAgent()
        >>> result = await agent.execute(state)
        >>> video = result.data.get("generated_video")
    """

    def __init__(
        self,
        storage_backend: StorageBackend | None = None,
        session_factory: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """初始化视频生成Agent。

        Args:
            storage_backend: 可选的存储后端，默认从 factory 获取。
            session_factory: 可选的 AsyncSession 工厂，用于 DB 写入。
            **kwargs: 传递给 BaseAgent 的参数。
        """
        super().__init__(role=AgentRole.VIDEO_GENERATOR, **kwargs)
        self._storage_backend = storage_backend
        self._session_factory = session_factory
        self._video_client: KlingVideoClient | None = get_video_client(
            settings=self.settings
        )
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
                    "分镜脚本：{storyboard}\n\n请设计组合方案。",
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
            state=state,
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
            prompt = await self._optimize_scene_prompt(scene, visual_style)
            processed_scenes.append(
                {
                    "scene_id": scene.scene_id,
                    "prompt": prompt,
                    "duration": scene.duration,
                    "shot_type": scene.shot_type.value,
                }
            )

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

    def _resolve_tenant_id(self, state: AgentState) -> str:
        """从 state 中解析 tenant_id。

        TODO: GenerationRequest 当前没有 tenant_id 字段。
        后续需要添加 tenant_id 到 GenerationRequest 或 AgentState。

        Args:
            state: 当前 AgentState。

        Returns:
            tenant_id 字符串。
        """
        if state.generation_request is not None:
            req_tenant = getattr(state.generation_request, "tenant_id", None)
            if req_tenant:
                return req_tenant
        if state.product_info is not None:
            prod_tenant = getattr(state.product_info, "tenant_id", None)
            if prod_tenant:
                return prod_tenant
        state_tenant = getattr(state, "tenant_id", None)
        if state_tenant:
            return state_tenant
        logger.warning("No tenant_id found in state; falling back to 'system'.")
        return "system"

    async def _write_asset_to_storage(
        self,
        data: bytes,
        tenant_id: str,
        video_id: str,
        mime_type: str,
    ) -> tuple[str, str]:
        """将二进制数据写入存储后端并返回 URL 和 key。

        Args:
            data: 文件二进制数据。
            tenant_id: 租户 ID。
            video_id: 视频 ID。
            mime_type: MIME 类型。

        Returns:
            (url, storage_key) 元组。
        """
        backend = self._storage_backend or get_storage_backend()
        key = f"videos/{tenant_id}/{video_id}.mp4"
        url = await backend.save(data, key, content_type=mime_type)
        return url, key

    async def _create_asset_po(
        self,
        session: AsyncSession,
        tenant_id: str,
        url: str,
        storage_key: str,
        data: bytes,
        video_id: str,
        visual_prompt: str,
        width: int,
        height: int,
        duration: float,
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
            video_id: 视频 ID。
            visual_prompt: 视觉提示词。
            width: 宽度。
            height: 高度。
            duration: 时长。
            mime_type: MIME 类型。
            provider: 生成提供方（真实为模型名，降级为 "mock"）。
            is_mock: 是否为 Mock 占位（真实为 False）。
        """
        from src.storage.local import LocalStorageBackend

        sha256 = LocalStorageBackend.compute_sha256(data)
        repo = AssetRepository(session)
        await repo.create_asset(
            tenant_id=tenant_id,
            asset_type="video",
            provider=provider,
            url=url,
            storage_key=storage_key,
            storage_backend="local",
            mime_type=mime_type,
            file_size=len(data),
            width=width,
            height=height,
            duration=duration,
            sha256=sha256,
            status="completed",
            is_mock=is_mock,
            extra_data={"visual_prompt": visual_prompt, "video_id": video_id},
        )

    async def _call_video_api(
        self,
        video_id: str,
        storyboard: Any,
        scene_prompts: list[dict[str, Any]],
        width: int,
        height: int,
        state: AgentState | None = None,
        session: AsyncSession | None = None,
    ) -> GeneratedVideo:
        """调用视频生成API。

        Args:
            video_id: 视频ID。
            storyboard: 分镜脚本。
            scene_prompts: 场景提示词列表。
            width: 宽度。
            height: 高度。
            state: 当前 AgentState（用于获取 tenant_id）。
            session: 可选的 AsyncSession（用于写 DB）。

        Returns:
            生成的视频。
        """
        # 解析 tenant_id
        tenant_id = "system"
        if state is not None:
            tenant_id = self._resolve_tenant_id(state)

        # Kling 模型时长上限保护：超过则裁剪并打 info 日志
        duration = float(storyboard.total_duration)
        if duration > 10.0:
            logger.info(
                "provider=kling 视频时长 %.1fs 超过模型上限，裁剪为 10.0s", duration
            )
            duration = 10.0

        # 真实路径：调用 Kling 可灵 AI
        if self._video_client is not None:
            try:
                visual_prompt = self._build_video_prompt(scene_prompts)
                result = await self._video_client.generate(
                    prompt=visual_prompt,
                    image=None,
                    duration=duration,
                    mode="std",
                    cfg_scale=0.5,
                    aspect_ratio="16:9",
                )
                video_bytes = result.data
                storage_key = f"videos/{tenant_id}/{video_id}.mp4"
                url, _ = await self._write_asset_to_storage(
                    video_bytes,
                    tenant_id,
                    video_id,
                    "video/mp4",
                )
                model_name = self.settings.video_model
                if session is not None:
                    await self._create_asset_po(
                        session=session,
                        tenant_id=tenant_id,
                        url=url,
                        storage_key=storage_key,
                        data=video_bytes,
                        video_id=video_id,
                        visual_prompt=visual_prompt,
                        width=width,
                        height=height,
                        duration=duration,
                        mime_type="video/mp4",
                        provider=model_name,
                        is_mock=False,
                    )
                video = GeneratedVideo(
                    video_id=video_id,
                    title=storyboard.title,
                    storyboard_id=storyboard.storyboard_id,
                    visual_prompt=visual_prompt,
                    url=url,
                    local_path=None,
                    format=VideoFormat.MP4,
                    width=width,
                    height=height,
                    duration=duration,
                    fps=30,
                    file_size=len(video_bytes),
                    status=AssetStatus.COMPLETED,
                    progress=100.0,
                    model=model_name,
                    metadata={
                        "provider": model_name,
                        "is_mock": False,
                        "remote_url": result.url,
                        "task_id": result.task_id,
                    },
                )
                return video
            except ProviderUnavailableError as exc:
                logger.error("provider=kling 真实视频生成失败，回退 mock: %s", exc)
        else:
            logger.warning(
                "provider=kling 未配置 API Key，回退 mock 占位行为 (tenant=%s)",
                tenant_id,
            )

        # 降级 / Mock 占位路径（与无 key 的 CI / 本地行为逐字节一致）
        # 生成最小可解析的 1x1x1 占位 MP4（ftyp + moov atom）
        placeholder_bytes = base64.b64decode(_EMPTY_MP4_BASE64)
        url, storage_key = await self._write_asset_to_storage(
            placeholder_bytes,
            tenant_id,
            video_id,
            "video/mp4",
        )

        # 写入数据库（如果有 session）
        if session is not None:
            await self._create_asset_po(
                session=session,
                tenant_id=tenant_id,
                url=url,
                storage_key=storage_key,
                data=placeholder_bytes,
                video_id=video_id,
                visual_prompt=str(scene_prompts),
                width=width,
                height=height,
                duration=storyboard.total_duration,
                mime_type="video/mp4",
                provider="mock",
                is_mock=True,
            )

        # 创建视频对象
        video = GeneratedVideo(
            video_id=video_id,
            title=storyboard.title,
            storyboard_id=storyboard.storyboard_id,
            visual_prompt=str(scene_prompts),
            url=url,
            local_path=None,
            format=VideoFormat.MP4,
            width=width,
            height=height,
            duration=storyboard.total_duration,
            fps=30,
            file_size=len(placeholder_bytes),
            status=AssetStatus.COMPLETED,
            progress=100.0,
            model=self.settings.video_model,
            metadata={
                "provider": "mock",
                "is_mock": True,
                "note": "Placeholder asset generated by mock provider; not a real media URL.",
            },
        )

        return video

    def _build_video_prompt(self, scene_prompts: list[dict[str, Any]]) -> str:
        """将分镜提示词列表合并为单一视频生成提示词。

        Args:
            scene_prompts: 处理后的场景提示词列表（含 ``prompt`` 字段）。

        Returns:
            合并后的视频提示词字符串。
        """
        parts = [
            sp.get("prompt", "")
            for sp in scene_prompts
            if isinstance(sp, dict) and sp.get("prompt")
        ]
        if not parts:
            return "A high-quality product promotional video"
        return "\n".join(parts)


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
            "url": f"mock://videos/{uuid.uuid4().hex[:8]}.mp4",
            "duration": duration,
            "resolution": "1080p",
            "progress": 100.0,
            "metadata": {
                "provider": "mock",
                "is_mock": True,
                "note": "Placeholder asset generated by mock provider; not a real media URL.",
            },
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
        scenes.append(
            {
                "scene_id": i + 1,
                "duration": video_duration / num_scenes,
                "description": f"场景 {i + 1}",
                "shot_type": "medium",
            }
        )

    return {
        "success": True,
        "storyboard": {
            "title": f"{product_info.get('name', '产品')}视频",
            "total_duration": video_duration,
            "scenes": scenes,
        },
    }
