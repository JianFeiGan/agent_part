"""
任务管理器。

Description:
    管理异步任务的创建、执行、状态查询和取消。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

import asyncio
import contextlib
import logging
from typing import Any
from uuid import uuid4

from src.api.schema.task import TaskStatus, TaskType
from src.api.service.asset_persister import AssetPersister
from src.api.service.redis_client import RedisClient, get_redis
from src.db.postgres import get_db_session
from src.graph.state import AgentState, GenerationRequest, create_initial_state
from src.graph.workflow import ProductVisualWorkflow
from src.models.product import Product

logger = logging.getLogger(__name__)

# 工作流步骤配置
WORKFLOW_STEPS = [
    "orchestration",
    "requirement_analysis",
    "creative_planning",
    "visual_design",
    "image_generation",
    "video_generation",
    "quality_review",
]

# 步骤进度映射
STEP_PROGRESS = {
    "init": 0,
    "orchestration": 10,
    "requirement_analysis": 20,
    "creative_planning": 35,
    "visual_design": 50,
    "image_generation": 65,
    "video_generation": 80,
    "quality_review": 95,
    "completed": 100,
}


class TaskManager:
    """任务管理器。

    负责任务的创建、执行、状态查询和取消。

    Attributes:
        _running_tasks: 正在运行的任务字典，键为任务 ID，值为 asyncio.Task。

    Example:
        >>> manager = TaskManager()
        >>> task_id = await manager.create_task(product_id, request_data, redis)
        >>> status = await manager.get_task_status(task_id, redis)
    """

    def __init__(self) -> None:
        """初始化任务管理器。"""
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._ws_subscribers: dict[str, list[Any]] = {}

    async def create_task(
        self,
        product_id: str,
        request_data: dict[str, Any],
        redis: RedisClient,
        *,
        tenant_id: str,
    ) -> str:
        """创建任务。

        Args:
            product_id: 商品 ID。
            request_data: 任务配置数据（含 provider_id 字段）。
            redis: Redis 客户端。
            tenant_id: 租户 ID。

        Returns:
            任务 ID。

        Raises:
            ValueError: 商品不存在。
        """
        # 生成任务 ID
        task_id = f"task_{uuid4().hex[:12]}"

        # 创建生成请求
        generation_request = GenerationRequest(
            task_id=task_id,
            task_type=request_data.get("task_type", TaskType.IMAGE_AND_VIDEO.value),
            image_types=request_data.get("image_types", ["main", "scene"]),
            image_count_per_type=request_data.get("image_count_per_type", 1),
            video_duration=request_data.get("video_duration", 30.0),
            video_style=request_data.get("video_style", "professional"),
            style_preference=request_data.get("style_preference"),
            color_preference=request_data.get("color_preference"),
            quality_level=request_data.get("quality_level", "standard"),
        )

        # 提取任务级 provider_id
        provider_ids = {
            "llm_provider_id": request_data.get("llm_provider_id"),
            "image_provider_id": request_data.get("image_provider_id"),
            "video_provider_id": request_data.get("video_provider_id"),
        }

        # 在 Redis 中创建任务记录
        await redis.create_task(task_id, product_id, generation_request, tenant_id=tenant_id)

        # 获取商品信息
        product = await redis.get_product(product_id, tenant_id=tenant_id)
        if not product:
            raise ValueError(f"商品不存在: {product_id}")

        # 启动后台任务执行工作流
        task = asyncio.create_task(
            self._execute_workflow(
                task_id, product, generation_request, tenant_id=tenant_id, **provider_ids
            )
        )
        self._running_tasks[task_id] = task

        return task_id

    async def _execute_workflow(
        self,
        task_id: str,
        product: Product,
        request: GenerationRequest,
        *,
        tenant_id: str,
        llm_provider_id: int | None = None,
        image_provider_id: int | None = None,
        video_provider_id: int | None = None,
    ) -> None:
        """执行工作流（后台任务）。

        Args:
            task_id: 任务 ID。
            product: 商品信息。
            request: 生成请求。
            tenant_id: 租户 ID。
            llm_provider_id: 任务级指定的 LLM 厂商 ID。
            image_provider_id: 任务级指定的图片厂商 ID。
            video_provider_id: 任务级指定的视频厂商 ID。
        """
        redis = await get_redis()

        try:
            # 更新状态为运行中
            await redis.update_task_progress(
                task_id, TaskStatus.RUNNING.value, 0, "init", tenant_id=tenant_id
            )

            # 创建工作流并执行
            workflow = ProductVisualWorkflow()

            # 使用回调更新进度
            async def progress_callback(state: AgentState) -> None:
                """进度更新回调函数。

                Args:
                    state: 当前 Agent 状态。
                """
                progress = STEP_PROGRESS.get(state.current_step, 0)
                await redis.update_task_progress(
                    task_id,
                    TaskStatus.RUNNING.value,
                    progress,
                    state.current_step,
                    tenant_id=tenant_id,
                )
                await redis.save_task_state(task_id, state, tenant_id=tenant_id)

                # 推送进度更新事件
                await self._broadcast_event(task_id, {
                    "type": "progress_update",
                    "progress": progress,
                    "current_step": state.current_step,
                })

                # 推送 agent 状态变化和日志更新事件
                if state.agent_logs:
                    for log in state.agent_logs:
                        await self._broadcast_event(task_id, {
                            "type": "agent_status_change",
                            "agent_name": log.step,
                            "status": log.status,
                        })
                    # 推送最新的完整日志
                    latest_log = state.agent_logs[-1]
                    if latest_log.status in ("completed", "failed"):
                        await self._broadcast_event(task_id, {
                            "type": "agent_log_update",
                            "agent_log": latest_log.model_dump(),
                        })

            # 执行工作流（使用 stream 模式，逐步获取节点输出）
            initial_state = create_initial_state(
                product,
                request,
                llm_provider_id=llm_provider_id,
                image_provider_id=image_provider_id,
                video_provider_id=video_provider_id,
            )
            config = {"configurable": {"thread_id": task_id}}

            async for event in workflow.app.astream(initial_state, config=config):
                # event 是每个节点的输出 dict，key 为节点名
                # 获取最新状态并触发回调
                latest_state = await workflow.app.aget_state(config)
                if latest_state and latest_state.values:
                    state_values = latest_state.values
                    if isinstance(state_values, dict):
                        state = AgentState(**state_values)
                    else:
                        state = state_values
                    await progress_callback(state)

            # 获取最终结果
            final_state = await workflow.app.aget_state(config)
            if final_state and final_state.values:
                state_values = final_state.values
                if isinstance(state_values, dict):
                    result = AgentState(**state_values)
                else:
                    result = state_values
            else:
                result = AgentState(product_info=product, generation_request=request)

            # 保存最终状态
            await redis.save_task_state(task_id, result, tenant_id=tenant_id)

            # 将生成产物落库到 generated_assets，供刊登工作流复用
            if not result.has_error() and result.product_info:
                product_id = result.product_info.product_id or ""
                if product_id and result.generated_images:
                    try:
                        async with get_db_session() as session:
                            persister = AssetPersister(session=session)
                            persisted = await persister.persist_images(
                                tenant_id=tenant_id,
                                product_id=product_id,
                                task_id=task_id,
                                images=result.generated_images,
                            )
                            logger.info(
                                f"任务 {task_id} 产物落库: {persisted} 张图片"
                            )
                    except Exception as e:
                        logger.error(f"任务 {task_id} 产物落库失败: {e}")

            # 更新任务状态为完成
            if result.has_error():
                await redis.update_task_progress(
                    task_id,
                    TaskStatus.FAILED.value,
                    0,
                    result.current_step,
                    tenant_id=tenant_id,
                )
            else:
                await redis.update_task_progress(
                    task_id,
                    TaskStatus.COMPLETED.value,
                    100,
                    "completed",
                    tenant_id=tenant_id,
                )

        except asyncio.CancelledError:
            # 任务被取消
            await redis.update_task_progress(
                task_id,
                TaskStatus.FAILED.value,
                0,
                "cancelled",
                tenant_id=tenant_id,
            )
            raise

        except Exception as e:
            # 更新任务状态为失败
            await redis.update_task_progress(
                task_id,
                TaskStatus.FAILED.value,
                0,
                "error",
                tenant_id=tenant_id,
            )
            # 记录错误
            state = await redis.get_task_state(task_id, tenant_id=tenant_id)
            if state:
                state.error = str(e)
                await redis.save_task_state(task_id, state, tenant_id=tenant_id)

        finally:
            # 清理运行中的任务引用
            self._running_tasks.pop(task_id, None)

    async def get_task_status(
        self, task_id: str, redis: RedisClient, *, tenant_id: str
    ) -> dict[str, Any]:
        """获取任务状态。

        Args:
            task_id: 任务 ID。
            redis: Redis 客户端。
            tenant_id: 租户 ID。

        Returns:
            任务状态信息。

        Raises:
            ValueError: 任务不存在。
        """
        metadata = await redis.get_task_metadata(task_id, tenant_id=tenant_id)
        if not metadata:
            raise ValueError(f"任务不存在: {task_id}")

        return {
            "task_id": task_id,
            "status": metadata.get("status", TaskStatus.PENDING.value),
            "progress": metadata.get("progress", 0.0),
            "current_step": metadata.get("current_step", "init"),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
        }

    async def get_task_detail(
        self, task_id: str, redis: RedisClient, *, tenant_id: str
    ) -> dict[str, Any]:
        """获取任务详情。

        Args:
            task_id: 任务 ID。
            redis: Redis 客户端。
            tenant_id: 租户 ID。

        Returns:
            任务详细信息。

        Raises:
            ValueError: 任务不存在。
        """
        metadata = await redis.get_task_metadata(task_id, tenant_id=tenant_id)
        if not metadata:
            raise ValueError(f"任务不存在: {task_id}")

        state = await redis.get_task_state(task_id, tenant_id=tenant_id)
        request_data = metadata.get("request", {})

        # 提取 agent_logs
        agent_logs = []
        if state and hasattr(state, "agent_logs"):
            agent_logs = [log.model_dump() for log in state.agent_logs]

        # 提取 error_message
        error_message = state.error if state else None

        # 提取 completed_steps
        completed_steps = state.completed_steps if state else []

        # 提取生成的图片
        images = []
        if state and hasattr(state, "generated_images") and state.generated_images:
            images = [img.model_dump() for img in state.generated_images]

        # 提取生成的视频
        video = None
        if state and state.generated_video:
            video = state.generated_video.model_dump()

        # 提取质量报告
        quality_reports = []
        if state and hasattr(state, "quality_reports") and state.quality_reports:
            quality_reports = [r.model_dump() for r in state.quality_reports]

        return {
            "task_id": task_id,
            "product_id": metadata.get("product_id"),
            "task_type": request_data.get("task_type", "image_and_video"),
            "status": metadata.get("status"),
            "progress": metadata.get("progress", 0),
            "current_step": metadata.get("current_step"),
            "completed_steps": completed_steps,
            "agent_logs": agent_logs,
            "images": images,
            "video": video,
            "quality_reports": quality_reports,
            "error_message": error_message,
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "state": state.model_dump() if state else None,
        }

    async def cancel_task(
        self, task_id: str, redis: RedisClient, *, tenant_id: str
    ) -> bool:
        """取消任务。

        Args:
            task_id: 任务 ID。
            redis: Redis 客户端。
            tenant_id: 租户 ID。

        Returns:
            是否取消成功。
        """
        # 检查任务是否存在
        metadata = await redis.get_task_metadata(task_id, tenant_id=tenant_id)
        if not metadata:
            return False

        # 检查是否正在运行
        if task_id in self._running_tasks:
            task = self._running_tasks[task_id]
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # 更新状态为取消（使用 failed 状态）
        await redis.update_task_progress(
            task_id, TaskStatus.FAILED.value, 0, "cancelled", tenant_id=tenant_id
        )

        return True

    async def list_tasks(
        self,
        redis: RedisClient,
        page: int = 1,
        page_size: int = 10,
        status: str | None = None,
        *,
        tenant_id: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """获取任务列表。

        Args:
            redis: Redis 客户端。
            page: 页码。
            page_size: 每页数量。
            status: 状态过滤。
            tenant_id: 租户 ID。

        Returns:
            任务列表和总数。
        """
        return await redis.list_tasks(
            tenant_id=tenant_id, page=page, page_size=page_size, status=status
        )

    def get_running_task_count(self) -> int:
        """获取正在运行的任务数量。

        Returns:
            正在运行的任务数量。
        """
        return len(self._running_tasks)

    def is_task_running(self, task_id: str) -> bool:
        """检查任务是否正在运行。

        Args:
            task_id: 任务 ID。

        Returns:
            是否正在运行。
        """
        return task_id in self._running_tasks

    def subscribe_ws(self, task_id: str, websocket: Any) -> None:
        """订阅任务 WebSocket 事件。

        Args:
            task_id: 任务 ID。
            websocket: WebSocket 连接对象。
        """
        if task_id not in self._ws_subscribers:
            self._ws_subscribers[task_id] = []
        self._ws_subscribers[task_id].append(websocket)

    def unsubscribe_ws(self, task_id: str, websocket: Any) -> None:
        """取消订阅任务 WebSocket 事件。

        Args:
            task_id: 任务 ID。
            websocket: WebSocket 连接对象。
        """
        if task_id in self._ws_subscribers:
            self._ws_subscribers[task_id] = [
                ws for ws in self._ws_subscribers[task_id] if ws is not websocket
            ]
            if not self._ws_subscribers[task_id]:
                del self._ws_subscribers[task_id]

    async def _broadcast_event(self, task_id: str, event: dict[str, Any]) -> None:
        """广播 WebSocket 事件给所有订阅者。

        Args:
            task_id: 任务 ID。
            event: 事件数据。
        """
        subscribers = self._ws_subscribers.get(task_id, [])
        for ws in subscribers[:]:  # 复制列表避免迭代中修改
            try:
                await ws.send_json(event)
            except Exception:
                # 连接已断开，移除订阅
                self.unsubscribe_ws(task_id, ws)


# 全局单例
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """获取任务管理器实例（单例）。

    Returns:
        任务管理器实例。
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
