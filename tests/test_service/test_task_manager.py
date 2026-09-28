"""TaskManager 行为测试。

覆盖任务创建、状态/详情查询、取消、终态写入、异常与取消路径、
僵尸 RUNNING 任务回收。所有外部依赖（Redis / DB / 工作流）均以替身隔离。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.schema.task import TaskStatus
from src.api.service.redis_client import RedisClient
from src.api.service.task_manager import TaskManager, get_task_manager
from src.graph.state import AgentLog, AgentState, GenerationRequest
from src.models.assets import AssetStatus, GeneratedImage, GeneratedVideo, ImageFormat
from src.models.product import Product, ProductCategory

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _product(product_id: str = "prod_001") -> Product:
    """构造可用的商品。"""
    return Product(
        product_id=product_id,
        name="测试商品名称",
        category=ProductCategory.DIGITAL,
        description="这是一个用于测试的商品描述信息",
    )


def _request(task_id: str = "task_abc") -> GenerationRequest:
    """构造生成请求。"""
    return GenerationRequest(task_id=task_id, task_type="image_and_video")


def _image(**kwargs: Any) -> GeneratedImage:
    """构造已完成图片。"""
    defaults: dict[str, Any] = {
        "image_id": "img_001",
        "image_type": "main",
        "prompt": "test prompt",
        "url": "https://example.com/img.png",
        "format": ImageFormat.PNG,
        "width": 1024,
        "height": 1024,
        "status": AssetStatus.COMPLETED,
        "model": "wanx-v1",
    }
    defaults.update(kwargs)
    return GeneratedImage(**defaults)


def _video(**kwargs: Any) -> GeneratedVideo:
    """构造已完成视频。"""
    defaults: dict[str, Any] = {
        "video_id": "vid_001",
        "visual_prompt": "video prompt",
        "url": "https://example.com/v.mp4",
        "duration": 5.0,
        "status": AssetStatus.COMPLETED,
        "model": "kling-v1",
    }
    defaults.update(kwargs)
    return GeneratedVideo(**defaults)


def _redis(metadata: dict[str, Any] | None = None) -> AsyncMock:
    """构造 RedisClient 替身。"""
    redis = AsyncMock()
    redis.get_task_metadata = AsyncMock(return_value=metadata)
    redis.get_task_state = AsyncMock(return_value=None)
    redis.save_task_state = AsyncMock()
    redis.update_task_progress = AsyncMock()
    redis.create_task = AsyncMock()
    redis.publish_task_event = AsyncMock()
    redis.get_product = AsyncMock(return_value=_product())
    redis.list_tasks = AsyncMock(return_value=([], 0))
    redis.delete_task = AsyncMock(return_value=True)
    return redis


class _FakeWorkflowApp:
    """按 values 流模式产出状态序列的工作流替身。"""

    def __init__(self, states: list[Any]) -> None:
        self._states = states
        self.received: list[Any] = []
        self.config: dict[str, Any] | None = None

    async def astream(self, initial: Any, *, config: Any = None, stream_mode: str = "") -> Any:
        self.received.append(initial)
        self.config = config
        for state in self._states:
            yield state


class _SessionCtx:
    """可 async with 的数据库会话替身。"""

    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *exc: Any) -> None:
        return None


class _PubSubBus:
    """进程内 Redis pub/sub 传输替身（publish / pubsub 接口对齐 redis.Redis）。"""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[str]]] = {}

    async def publish(self, channel: str, message: str) -> int:
        queues = self._subscribers.get(channel, [])
        for queue in queues:
            queue.put_nowait(message)
        return len(queues)

    def pubsub(self, **_kwargs: Any) -> _PubSubHandle:
        return _PubSubHandle(self)


class _PubSubHandle:
    """订阅端替身，接口对齐 WebSocket 端点使用的 pubsub 读写方法。"""

    def __init__(self, bus: _PubSubBus) -> None:
        self._bus = bus
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._channel: str | None = None

    async def subscribe(self, *channels: str) -> None:
        for channel in channels:
            self._channel = channel
            self._bus._subscribers.setdefault(channel, []).append(self._queue)

    async def get_message(
        self,
        ignore_subscribe_messages: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        try:
            data = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None
        return {"type": "message", "channel": self._channel, "data": data}

    async def close(self) -> None:
        if self._channel is None:
            return
        queues = self._bus._subscribers.get(self._channel, [])
        if self._queue in queues:
            queues.remove(self._queue)


def _patch_workflow(monkeypatch: pytest.MonkeyPatch, states: list[Any]) -> _FakeWorkflowApp:
    """注入假 ProductVisualWorkflow。"""
    app = _FakeWorkflowApp(states)
    wf = MagicMock()
    wf.app = app
    monkeypatch.setattr(
        "src.api.service.task_manager.ProductVisualWorkflow",
        lambda **_kw: wf,
    )
    return app


def _patch_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    redis: AsyncMock,
    persister: AsyncMock | None = None,
) -> AsyncMock:
    """注入 redis / get_db_session / AssetPersister 替身。"""
    monkeypatch.setattr("src.api.service.task_manager.get_redis", AsyncMock(return_value=redis))
    session = AsyncMock()
    monkeypatch.setattr(
        "src.api.service.task_manager.get_db_session",
        lambda: _SessionCtx(session),
    )
    if persister is not None:
        monkeypatch.setattr("src.api.service.task_manager.AssetPersister", lambda **_kw: persister)
    return session


class TestCreateTask:
    """create_task 行为。"""

    async def test_missing_product_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """商品不存在时抛 ValueError，且不启动工作流。"""
        redis = _redis()
        redis.get_product = AsyncMock(return_value=None)
        _patch_env(monkeypatch, redis=redis)

        manager = TaskManager()
        with pytest.raises(ValueError, match="商品不存在"):
            await manager.create_task("prod_x", {}, redis, tenant_id="tenant-1")

        assert manager.get_running_task_count() == 0

    async def test_create_task_starts_background_work(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """创建成功时记录 running task 并写入 Redis。"""
        redis = _redis()
        _patch_env(monkeypatch, redis=redis)
        app = _patch_workflow(monkeypatch, [])

        manager = TaskManager()
        task_id = await manager.create_task(
            "prod_001",
            {
                "task_type": "image_only",
                "image_types": ["main"],
                "image_count_per_type": 2,
                "video_duration": 12.5,
                "llm_provider_id": 3,
                "image_provider_id": 4,
                "video_provider_id": 5,
            },
            redis,
            tenant_id="tenant-1",
        )

        assert task_id.startswith("task_")
        redis.create_task.assert_awaited_once()
        # 等后台任务跑完，避免泄漏
        task = manager._running_tasks.get(task_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        assert app.received, "工作流未收到初始状态"
        initial = app.received[0]
        assert initial.llm_provider_id == 3
        assert initial.image_provider_id == 4
        assert initial.video_provider_id == 5
        assert initial.tenant_id == "tenant-1"


class TestExecuteWorkflow:
    """_execute_workflow 终态与持久化行为。"""

    async def test_success_completes_and_persists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无错结果落库并置 COMPLETED。"""
        redis = _redis()
        persister = AsyncMock()
        persister.persist_images = AsyncMock(return_value=1)
        persister.persist_videos = AsyncMock(return_value=1)
        _patch_env(monkeypatch, redis=redis, persister=persister)

        final = AgentState(
            product_info=_product(),
            generation_request=_request(),
            generated_images=[_image()],
            generated_video=_video(),
        )
        _patch_workflow(monkeypatch, [final.model_dump()])

        manager = TaskManager()
        await manager._execute_workflow(
            task_id="task_abc",
            product=_product(),
            request=_request(),
            tenant_id="tenant-1",
        )

        persister.persist_images.assert_awaited_once()
        persister.persist_videos.assert_awaited_once()
        redis.update_task_progress.assert_any_await(
            "task_abc", TaskStatus.COMPLETED.value, 100, "completed", tenant_id="tenant-1"
        )

    async def test_error_result_marks_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """结果带 error 时终态为 FAILED，进度沿用 metadata。"""
        redis = _redis(metadata={"progress": 65.0})
        _patch_env(monkeypatch, redis=redis)

        final = AgentState(
            product_info=_product(),
            generation_request=_request(),
            error="生成失败",
            current_step="image_generation",
        )
        _patch_workflow(monkeypatch, [final.model_dump()])

        manager = TaskManager()
        await manager._execute_workflow(
            task_id="task_abc",
            product=_product(),
            request=_request(),
            tenant_id="tenant-1",
        )

        redis.update_task_progress.assert_any_await(
            "task_abc", TaskStatus.FAILED.value, 65.0, "image_generation", tenant_id="tenant-1"
        )

    async def test_finalize_progress_invalid_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """metadata 中 progress 非法时按 0 处理。"""
        redis = _redis(metadata={"progress": "not-a-number"})
        _patch_env(monkeypatch, redis=redis)

        final = AgentState(
            product_info=_product(),
            generation_request=_request(),
            error="x",
        )
        _patch_workflow(monkeypatch, [final.model_dump()])

        manager = TaskManager()
        await manager._execute_workflow(
            task_id="task_abc",
            product=_product(),
            request=_request(),
            tenant_id="tenant-1",
        )

        redis.update_task_progress.assert_any_await(
            "task_abc", TaskStatus.FAILED.value, 0.0, "init", tenant_id="tenant-1"
        )

    async def test_exception_marks_failed_and_records_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """工作流抛异常时写 FAILED 并把错误记入 state。"""
        redis = _redis()
        state = AgentState(product_info=_product(), generation_request=_request())
        redis.get_task_state = AsyncMock(return_value=state)
        _patch_env(monkeypatch, redis=redis)

        app = _FakeWorkflowApp([])

        async def _boom(*_a: Any, **_k: Any) -> Any:
            raise RuntimeError("workflow exploded")
            yield  # pragma: no cover

        app.astream = _boom  # type: ignore[method-assign]
        wf = MagicMock()
        wf.app = app
        monkeypatch.setattr("src.api.service.task_manager.ProductVisualWorkflow", lambda **_kw: wf)

        manager = TaskManager()
        await manager._execute_workflow(
            task_id="task_abc",
            product=_product(),
            request=_request(),
            tenant_id="tenant-1",
        )

        redis.update_task_progress.assert_any_await(
            "task_abc", TaskStatus.FAILED.value, 0.0, "error", tenant_id="tenant-1"
        )
        assert state.error == "workflow exploded"
        redis.save_task_state.assert_awaited()

    async def test_cancelled_marks_cancelled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """工作流被取消时终态 CANCELLED 且取消信号继续传播。"""
        redis = _redis()
        _patch_env(monkeypatch, redis=redis)

        app = _FakeWorkflowApp([])

        async def _cancel(*_a: Any, **_k: Any) -> Any:
            raise asyncio.CancelledError()
            yield  # pragma: no cover

        app.astream = _cancel  # type: ignore[method-assign]
        wf = MagicMock()
        wf.app = app
        monkeypatch.setattr("src.api.service.task_manager.ProductVisualWorkflow", lambda **_kw: wf)

        manager = TaskManager()
        with pytest.raises(asyncio.CancelledError):
            await manager._execute_workflow(
                task_id="task_abc",
                product=_product(),
                request=_request(),
                tenant_id="tenant-1",
            )

        redis.update_task_progress.assert_any_await(
            "task_abc", TaskStatus.CANCELLED.value, 0.0, "cancelled", tenant_id="tenant-1"
        )

    async def test_persist_failure_does_not_fail_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """产物落库失败只记日志，任务仍 COMPLETED。"""
        redis = _redis()
        persister = AsyncMock()
        persister.persist_images = AsyncMock(side_effect=RuntimeError("db down"))
        _patch_env(monkeypatch, redis=redis, persister=persister)

        final = AgentState(
            product_info=_product(),
            generation_request=_request(),
            generated_images=[_image()],
        )
        _patch_workflow(monkeypatch, [final.model_dump()])

        manager = TaskManager()
        await manager._execute_workflow(
            task_id="task_abc",
            product=_product(),
            request=_request(),
            tenant_id="tenant-1",
        )

        redis.update_task_progress.assert_any_await(
            "task_abc", TaskStatus.COMPLETED.value, 100, "completed", tenant_id="tenant-1"
        )

    async def test_progress_callback_publishes_agent_logs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """agent_logs 非空时事件真正发布到 Redis pub/sub，携带任务与租户。"""
        redis = _redis()
        _patch_env(monkeypatch, redis=redis)

        log = AgentLog(
            agent_name="VisualDesigner",
            step="visual_design",
            status="completed",
            start_time="2026-01-01T00:00:00",
        )
        state = AgentState(
            product_info=_product(),
            generation_request=_request(),
            current_step="visual_design",
            agent_logs=[log],
        )
        _patch_workflow(monkeypatch, [state.model_dump()])

        manager = TaskManager()
        await manager._execute_workflow(
            task_id="task_abc",
            product=_product(),
            request=_request(),
            tenant_id="tenant-1",
        )

        calls = redis.publish_task_event.await_args_list
        assert calls, "任务事件未发布到 Redis"
        kinds = {call.args[1]["type"] for call in calls}
        assert "progress_update" in kinds
        assert "agent_status_change" in kinds
        assert "agent_log_update" in kinds
        for call in calls:
            assert call.args[0] == "task_abc"
            assert call.kwargs["tenant_id"] == "tenant-1"


class TestBroadcastEvent:
    """任务事件广播的降级与连通性。"""

    async def test_publish_failure_warns_and_does_not_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Redis 不可用时记 warning 并继续，任务仍写入终态。"""
        redis = _redis()
        redis.publish_task_event = AsyncMock(side_effect=RuntimeError("redis down"))
        _patch_env(monkeypatch, redis=redis)

        final = AgentState(
            product_info=_product(),
            generation_request=_request(),
        )
        _patch_workflow(monkeypatch, [final.model_dump()])

        manager = TaskManager()
        with caplog.at_level(logging.WARNING, logger="src.api.service.task_manager"):
            await manager._execute_workflow(
                task_id="task_abc",
                product=_product(),
                request=_request(),
                tenant_id="tenant-1",
            )

        redis.publish_task_event.assert_awaited()
        assert any("事件广播失败" in record.getMessage() for record in caplog.records)
        redis.update_task_progress.assert_any_await(
            "task_abc", TaskStatus.COMPLETED.value, 100, "completed", tenant_id="tenant-1"
        )

    async def test_published_event_reaches_subscriber(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """广播出的事件能被同频道订阅端收到（多进程部署依赖的频道桥）。"""
        bus = _PubSubBus()
        publisher = RedisClient()
        publisher._client = bus
        subscriber = RedisClient()
        subscriber._client = bus
        monkeypatch.setattr(
            "src.api.service.task_manager.get_redis",
            AsyncMock(return_value=publisher),
        )

        pubsub = await subscriber.subscribe_task_events("task_1", tenant_id="tenant-1")

        manager = TaskManager()
        await manager._broadcast_event(
            "task_1",
            {"type": "progress_update", "progress": 42},
            tenant_id="tenant-1",
        )

        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        await pubsub.close()

        assert message is not None
        assert message["type"] == "message"
        assert json.loads(message["data"]) == {"type": "progress_update", "progress": 42}


class TestQueries:
    """状态 / 详情查询。"""

    async def test_get_task_status_missing_raises(self) -> None:
        """任务不存在时抛 ValueError。"""
        redis = _redis()
        manager = TaskManager()
        with pytest.raises(ValueError, match="任务不存在"):
            await manager.get_task_status("nope", redis, tenant_id="tenant-1")

    async def test_get_task_status_defaults(self) -> None:
        """缺省字段回落到默认值。"""
        redis = _redis(metadata={"status": "running"})
        manager = TaskManager()
        data = await manager.get_task_status("t1", redis, tenant_id="tenant-1")

        assert data["task_id"] == "t1"
        assert data["status"] == "running"
        assert data["progress"] == 0.0
        assert data["current_step"] == "init"

    async def test_get_task_detail_missing_raises(self) -> None:
        """详情查询任务不存在时抛 ValueError。"""
        redis = _redis()
        manager = TaskManager()
        with pytest.raises(ValueError, match="任务不存在"):
            await manager.get_task_detail("nope", redis, tenant_id="tenant-1")

    async def test_get_task_detail_aggregates_state(self) -> None:
        """详情聚合 agent_logs / 图片 / 视频 / 质量报告 / mock 标记。"""
        state = AgentState(
            product_info=_product(),
            generation_request=_request(),
            error="boom",
            completed_steps=["visual_design"],
            agent_logs=[
                AgentLog(
                    agent_name="A",
                    step="visual_design",
                    status="failed",
                    start_time="2026-01-01T00:00:00",
                )
            ],
            generated_images=[
                _image(metadata={"is_mock": True}),
                _image(image_id="img_002", metadata={}),
            ],
            generated_video=_video(metadata={"is_mock": True}),
        )
        redis = _redis(
            metadata={
                "product_id": "prod_001",
                "request": {"task_type": "image_only"},
                "status": "failed",
                "progress": 42,
                "current_step": "quality_review",
            }
        )
        redis.get_task_state = AsyncMock(return_value=state)

        manager = TaskManager()
        detail = await manager.get_task_detail("t1", redis, tenant_id="tenant-1")

        assert detail["product_id"] == "prod_001"
        assert detail["task_type"] == "image_only"
        assert detail["error_message"] == "boom"
        assert detail["completed_steps"] == ["visual_design"]
        assert len(detail["agent_logs"]) == 1
        assert len(detail["images"]) == 2
        assert detail["video"] is not None
        assert detail["has_mock_assets"] is True
        assert detail["state"] is not None

    async def test_get_task_detail_without_state(self) -> None:
        """无 state 时详情仍可返回，产物为空。"""
        redis = _redis(metadata={"status": "pending", "product_id": "p1"})
        manager = TaskManager()
        detail = await manager.get_task_detail("t1", redis, tenant_id="tenant-1")

        assert detail["images"] == []
        assert detail["video"] is None
        assert detail["error_message"] is None
        assert detail["has_mock_assets"] is False
        assert detail["state"] is None


class TestCancelTask:
    """cancel_task 行为。"""

    async def test_cancel_missing_returns_false(self) -> None:
        """任务不存在返回 False。"""
        redis = _redis()
        manager = TaskManager()
        assert await manager.cancel_task("nope", redis, tenant_id="tenant-1") is False

    async def test_cancel_running_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """取消运行中的 asyncio.Task 并写终态。"""
        redis = _redis(metadata={"progress": 30.0})
        manager = TaskManager()

        started = asyncio.Event()

        async def _hang() -> None:
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(_hang())
        await started.wait()
        manager._running_tasks["t1"] = task

        assert await manager.cancel_task("t1", redis, tenant_id="tenant-1") is True
        redis.update_task_progress.assert_awaited_with(
            "t1", TaskStatus.CANCELLED.value, 30.0, "cancelled", tenant_id="tenant-1"
        )
        assert task.cancelled()

    async def test_cancel_finished_task_without_running_ref(self) -> None:
        """不在运行表中的任务也能写取消终态。"""
        redis = _redis(metadata={"progress": 0.0})
        manager = TaskManager()

        assert await manager.cancel_task("t1", redis, tenant_id="tenant-1") is True


class TestRunningRegistry:
    """运行中任务登记表。"""

    def test_running_count_and_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_running_task_count / is_task_running 反映登记表。"""
        manager = TaskManager()
        manager._running_tasks["t1"] = MagicMock()

        assert manager.get_running_task_count() == 1
        assert manager.is_task_running("t1") is True
        assert manager.is_task_running("t2") is False

    async def test_list_tasks_delegates(self) -> None:
        """list_tasks 透传到 Redis 并带租户。"""
        redis = _redis()
        redis.list_tasks = AsyncMock(return_value=([{"task_id": "t1"}], 1))
        manager = TaskManager()

        items, total = await manager.list_tasks(
            redis, page=2, page_size=5, status="running", tenant_id="tenant-1"
        )

        assert items == [{"task_id": "t1"}]
        assert total == 1
        redis.list_tasks.assert_awaited_once_with(
            tenant_id="tenant-1", page=2, page_size=5, status="running"
        )


class TestRecoverStaleRunningTasks:
    """重启后僵尸 RUNNING 任务回收。"""

    async def test_recovers_across_tenants(self) -> None:
        """按租户扫描 RUNNING 并置 FAILED。"""
        redis = _redis()
        redis.list_tasks = AsyncMock(
            side_effect=[
                ([{"task_id": "t1", "progress": 40}], 1),
                ([{"task_id": "t2", "progress": None}], 1),
            ]
        )
        manager = TaskManager()

        recovered = await manager.recover_stale_running_tasks(redis, ["tenant-1", "tenant-2"])

        assert recovered == 2
        redis.update_task_progress.assert_any_await(
            "t1", TaskStatus.FAILED.value, 40.0, "interrupted", tenant_id="tenant-1"
        )
        redis.update_task_progress.assert_any_await(
            "t2", TaskStatus.FAILED.value, 0.0, "interrupted", tenant_id="tenant-2"
        )

    async def test_skips_locally_running_tasks(self) -> None:
        """进程内仍在跑的任务不回收。"""
        redis = _redis()
        redis.list_tasks = AsyncMock(return_value=([{"task_id": "t1", "progress": 1}], 1))
        manager = TaskManager()
        manager._running_tasks["t1"] = MagicMock()

        assert await manager.recover_stale_running_tasks(redis, ["tenant-1"]) == 0
        redis.update_task_progress.assert_not_awaited()

    async def test_scan_error_is_tolerated(self) -> None:
        """某租户扫描失败不影响其它租户。"""
        redis = _redis()

        async def _list(*_a: Any, **kwargs: Any) -> Any:
            if kwargs.get("tenant_id") == "bad":
                raise RuntimeError("redis error")
            return ([{"task_id": "ok", "progress": 1}], 1)

        redis.list_tasks = AsyncMock(side_effect=_list)
        manager = TaskManager()

        assert await manager.recover_stale_running_tasks(redis, ["bad", "good"]) == 1


class TestSingleton:
    """get_task_manager 单例。"""

    def test_returns_same_instance(self) -> None:
        """重复调用返回同一实例。"""
        first = get_task_manager()
        assert get_task_manager() is first
