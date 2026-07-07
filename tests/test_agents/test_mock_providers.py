"""
Mock provider 测试模块。

验证图片和视频 mock provider 输出符合预期：
- URL 使用 /static/ 协议（通过 StorageBackend）
- metadata 包含 provider/is_mock/note
- 视频 progress 设置为 100
- 存储文件确实存在
- GeneratedAssetPO 记录可创建（is_mock=True）
@author ganjianfei
@version 1.0.0
2026-06-19
"""

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.image_generator import ImageGeneratorAgent, generate_product_image
from src.agents.video_generator import VideoGeneratorAgent
from src.clients.provider_result import (
    ImageGenerationResult,
    SingleImageResult,
    VideoGenerationResult,
)
from src.graph.state import AgentState
from src.models.assets import AssetStatus
from src.models.storyboard import Scene, SceneType, ShotType, Storyboard
from src.storage.local import LocalStorageBackend


def _make_storyboard() -> Storyboard:
    """构建测试用 Storyboard。"""
    scene = Scene(
        scene_id=1,
        scene_type=SceneType.PRODUCT_INTRO,
        duration=5.0,
        shot_type=ShotType.MEDIUM,
        description="产品正面展示",
        visual_prompt="Product hero shot",
    )
    return Storyboard(
        storyboard_id="sb_test",
        title="测试分镜",
        description="测试用分镜脚本",
        total_duration=5.0,
        resolution="1080p",
        visual_style="科技感",
        scenes=[scene],
    )


def _make_state(storyboard: Storyboard) -> AgentState:
    """构建测试用 AgentState。"""
    return AgentState(
        generation_prompts=[
            {
                "prompt": "A beautiful product photo",
                "image_type": "main",
                "style_keywords": ["studio lighting"],
                "aspect_ratio": "1:1",
            }
        ],
        storyboard=storyboard,
    )


class TestMockImageProvider:
    """图片 mock provider 测试。"""

    @pytest.fixture
    def storage_backend(self, tmp_path) -> LocalStorageBackend:
        """创建指向临时目录的本地存储后端。"""
        return LocalStorageBackend(base_path=str(tmp_path))

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """创建模拟异步会话。"""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_image_url_uses_static_prefix(self, storage_backend: LocalStorageBackend) -> None:
        """图片 URL 应使用 /static/ 前缀（通过 StorageBackend）。"""
        agent = ImageGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        images = result.data["generated_images"]
        assert len(images) > 0
        for img_data in images:
            url = img_data["url"]
            assert url is not None
            assert url.startswith("/static/"), f"Expected /static/..., got {url}"
            assert url.endswith(".png"), f"Expected .png extension, got {url}"

    @pytest.mark.asyncio
    async def test_mock_image_provider_writes_to_storage(
        self, storage_backend: LocalStorageBackend
    ) -> None:
        """上传后 storage 中应存在文件。"""
        agent = ImageGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        images = result.data["generated_images"]
        assert len(images) > 0
        for img_data in images:
            url = img_data["url"]
            # 从 URL 中提取 key：/static/images/system/img_xxx.png -> images/system/img_xxx.png
            key = url[len("/static/") :]
            exists = await storage_backend.exists(key)
            assert exists, f"File should exist at key: {key}"

    @pytest.mark.asyncio
    async def test_mock_image_provider_creates_asset_po(
        self, storage_backend: LocalStorageBackend, mock_session: AsyncMock
    ) -> None:
        """GeneratedAssetPO 行应存在，is_mock=True。"""
        agent = ImageGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        images = result.data["generated_images"]
        assert len(images) > 0
        for img_data in images:
            # 直接调用 _call_image_api 时传入 session
            img_list = await agent._call_image_api(
                prompt=img_data.get("prompt", "test"),
                negative_prompt=None,
                width=img_data.get("width", 1024),
                height=img_data.get("height", 1024),
                image_type=img_data.get("image_type", "main"),
                state=state,
                session=mock_session,
            )
            assert len(img_list) == 1
            generated = img_list[0]
            assert generated.metadata.get("is_mock") is True
            assert generated.metadata.get("provider") == "mock"
            # 验证 URL 格式
            assert generated.url.startswith("/static/")

    @pytest.mark.asyncio
    async def test_image_metadata_has_mock_markers(self) -> None:
        """图片 metadata 应包含 provider/is_mock/note。"""
        # 使用不带 storage_backend 的 agent（不写存储，仍用 /static/ URL）
        agent = ImageGeneratorAgent()
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        images = result.data["generated_images"]
        for img_data in images:
            metadata = img_data.get("metadata", {})
            assert metadata.get("provider") == "mock"
            assert metadata.get("is_mock") is True
            assert "Placeholder asset generated by mock provider" in metadata.get("note", "")

    @pytest.mark.asyncio
    async def test_generate_product_image_tool_mock_url(self) -> None:
        """工具函数也应返回 mock:// 格式的 URL。"""
        result = await generate_product_image.ainvoke(
            {"prompt": "test", "style": "realistic", "aspect_ratio": "1:1", "num_images": 1}
        )
        assert result["success"] is True
        for img in result["images"]:
            assert img["url"].startswith("mock://images/")
            assert "example.com" not in img["url"]

    @pytest.mark.asyncio
    async def test_fallback_tenant_is_system(self, storage_backend: LocalStorageBackend) -> None:
        """当 state 没有 tenant_id 时，应 fallback 到 'system'。"""
        agent = ImageGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        images = result.data["generated_images"]
        for img_data in images:
            url = img_data["url"]
            # 验证 key 包含 system 租户
            assert "/images/system/" in url, f"Expected /images/system/ in URL, got {url}"


class TestMockVideoProvider:
    """视频 mock provider 测试。"""

    @pytest.fixture
    def storage_backend(self, tmp_path) -> LocalStorageBackend:
        """创建指向临时目录的本地存储后端。"""
        return LocalStorageBackend(base_path=str(tmp_path))

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """创建模拟异步会话。"""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_video_url_uses_static_prefix(self, storage_backend: LocalStorageBackend) -> None:
        """视频 URL 应使用 /static/ 前缀（通过 StorageBackend）。"""
        agent = VideoGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        video_data = result.data["generated_video"]
        url = video_data["url"]
        assert url is not None
        assert url.startswith("/static/"), f"Expected /static/..., got {url}"
        assert url.endswith(".mp4"), f"Expected .mp4 extension, got {url}"

    @pytest.mark.asyncio
    async def test_mock_video_provider_writes_to_storage(
        self, storage_backend: LocalStorageBackend
    ) -> None:
        """上传后 storage 中应存在文件。"""
        agent = VideoGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        video_data = result.data["generated_video"]
        url = video_data["url"]
        # 从 URL 中提取 key
        key = url[len("/static/") :]
        exists = await storage_backend.exists(key)
        assert exists, f"File should exist at key: {key}"

    @pytest.mark.asyncio
    async def test_video_metadata_has_mock_markers(self) -> None:
        """视频 metadata 应包含 provider/is_mock/note。"""
        agent = VideoGeneratorAgent()
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        video_data = result.data["generated_video"]
        metadata = video_data.get("metadata", {})
        assert metadata.get("provider") == "mock"
        assert metadata.get("is_mock") is True
        assert "Placeholder asset generated by mock provider" in metadata.get("note", "")

    @pytest.mark.asyncio
    async def test_video_progress_is_100(self) -> None:
        """视频 mock provider 进度应设置为 100。"""
        agent = VideoGeneratorAgent()
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        video_data = result.data["generated_video"]
        assert video_data["progress"] == 100.0, (
            f"Expected progress 100, got {video_data['progress']}"
        )

    @pytest.mark.asyncio
    async def test_video_status_is_completed(self) -> None:
        """视频 mock provider 状态应为 completed。"""
        agent = VideoGeneratorAgent()
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        video_data = result.data["generated_video"]
        assert video_data["status"] == AssetStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_mock_video_creates_asset_po(
        self, storage_backend: LocalStorageBackend, mock_session: AsyncMock
    ) -> None:
        """视频 GeneratedAssetPO 行应存在，is_mock=True。"""
        agent = VideoGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        video_data = result.data["generated_video"]
        # 直接调用 _call_video_api 传入 session
        video = await agent._call_video_api(
            video_id=video_data.get("video_id", "vid_test"),
            storyboard=storyboard,
            scene_prompts=[{"prompt": "test"}],
            width=video_data.get("width", 1920),
            height=video_data.get("height", 1080),
            state=state,
            session=mock_session,
        )
        assert video.metadata.get("is_mock") is True
        assert video.metadata.get("provider") == "mock"
        assert video.url.startswith("/static/")

    @pytest.mark.asyncio
    async def test_video_fallback_tenant_is_system(
        self, storage_backend: LocalStorageBackend
    ) -> None:
        """当 state 没有 tenant_id 时，应 fallback 到 'system'。"""
        agent = VideoGeneratorAgent(storage_backend=storage_backend)
        storyboard = _make_storyboard()
        state = _make_state(storyboard)

        result = await agent.execute(state)

        assert result.success is True
        video_data = result.data["generated_video"]
        url = video_data["url"]
        assert "/videos/system/" in url, f"Expected /videos/system/ in URL, got {url}"


# --------------------------------------------------------------------------- #
# 真实 provider 注入测试（验证真实路径接线正确，离线用假客户端）
# --------------------------------------------------------------------------- #
class _FakeImageClient:
    """模拟已配置的 DashScopeImageClient，返回真实字节。"""

    def __init__(self, data: bytes = b"REALIMG") -> None:
        self._data = data

    def is_available(self) -> bool:
        return True

    async def generate(self, prompt: str, **kwargs: object) -> ImageGenerationResult:  # noqa: ARG002
        return ImageGenerationResult(
            images=[SingleImageResult(data=self._data, url="https://remote/img.png", seed=7)]
        )


class _FakeVideoClient:
    """模拟已配置的 KlingVideoClient，返回真实字节。"""

    def __init__(self, data: bytes = b"REALVID") -> None:
        self._data = data

    def is_available(self) -> bool:
        return True

    async def generate(self, prompt: str, **kwargs: object) -> VideoGenerationResult:  # noqa: ARG002
        return VideoGenerationResult(
            data=self._data, url="https://remote/v.mp4", duration=5.0, task_id="task-1"
        )


class TestRealProviderPath:
    """验证有 key 时走真实 provider，落库字节为真实内容、metadata 标记非 mock。"""

    @pytest.fixture
    def storage_backend(self, tmp_path) -> LocalStorageBackend:
        """创建指向临时目录的本地存储后端。"""
        return LocalStorageBackend(base_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_image_real_path_writes_real_bytes(
        self, storage_backend: LocalStorageBackend
    ) -> None:
        agent = ImageGeneratorAgent(storage_backend=storage_backend)
        agent._image_client = _FakeImageClient(data=b"REALIMG")
        state = _make_state(_make_storyboard())

        result = await agent.execute(state)

        assert result.success is True
        img = result.data["generated_images"][0]
        assert img["metadata"]["is_mock"] is False
        assert img["metadata"]["provider"] == "wanx-v1"
        key = img["url"][len("/static/"):]
        raw = Path(storage_backend._base_path) / key
        assert raw.read_bytes() == b"REALIMG"

    @pytest.mark.asyncio
    async def test_video_real_path_writes_real_bytes(
        self, storage_backend: LocalStorageBackend
    ) -> None:
        agent = VideoGeneratorAgent(storage_backend=storage_backend)
        agent._video_client = _FakeVideoClient(data=b"REALVID")
        state = _make_state(_make_storyboard())

        result = await agent.execute(state)

        assert result.success is True
        video = result.data["generated_video"]
        assert video["metadata"]["is_mock"] is False
        assert video["metadata"]["provider"] == "kling-v1"
        key = video["url"][len("/static/"):]
        raw = Path(storage_backend._base_path) / key
        assert raw.read_bytes() == b"REALVID"


class TestProviderUnconfiguredWarning:
    """验证无 key 时降级为 Mock 并打 warning 日志。"""

    @pytest.fixture
    def storage_backend(self, tmp_path) -> LocalStorageBackend:
        """创建指向临时目录的本地存储后端。"""
        return LocalStorageBackend(base_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_image_unconfigured_warns_and_mocks(
        self, storage_backend: LocalStorageBackend, caplog
    ) -> None:
        with patch("src.agents.image_generator.get_image_client", return_value=None):
            agent = ImageGeneratorAgent(storage_backend=storage_backend)
        state = _make_state(_make_storyboard())
        with caplog.at_level(logging.WARNING):
            result = await agent.execute(state)

        assert result.success is True
        img = result.data["generated_images"][0]
        assert img["metadata"]["is_mock"] is True
        assert img["metadata"]["provider"] == "mock"
        assert any("回退 mock" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_video_unconfigured_warns_and_mocks(
        self, storage_backend: LocalStorageBackend, caplog
    ) -> None:
        with patch("src.agents.video_generator.get_video_client", return_value=None):
            agent = VideoGeneratorAgent(storage_backend=storage_backend)
        state = _make_state(_make_storyboard())
        with caplog.at_level(logging.WARNING):
            result = await agent.execute(state)

        assert result.success is True
        video = result.data["generated_video"]
        assert video["metadata"]["is_mock"] is True
        assert video["metadata"]["provider"] == "mock"
        assert any("回退 mock" in r.message for r in caplog.records)
