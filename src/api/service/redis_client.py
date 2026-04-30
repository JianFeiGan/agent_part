"""
Redis 存储服务。

Description:
    提供 Redis 数据存储和缓存功能，用于任务状态持久化和商品数据存储。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

import json
from datetime import datetime
from typing import Any

import redis.asyncio as redis

from src.config.settings import get_settings
from src.graph.state import AgentState, GenerationRequest
from src.models.product import Product


class RedisClient:
    """Redis 客户端封装。

    提供商品和任务数据的存储、查询、更新、删除功能。

    Attributes:
        settings: 应用配置实例。
        _client: Redis 客户端实例。
        _prefix: Key 前缀。

    Example:
        >>> client = RedisClient()
        >>> await client.connect()
        >>> await client.save_product(product)
        >>> product = await client.get_product("prod_001")
    """

    def __init__(self) -> None:
        """初始化 Redis 客户端。"""
        self.settings = get_settings()
        self._client: redis.Redis | None = None
        self._prefix = self.settings.redis_prefix

    async def connect(self) -> None:
        """建立 Redis 连接。

        Raises:
            redis.ConnectionError: 连接失败时抛出。
        """
        self._client = redis.from_url(
            self.settings.redis_url, encoding="utf-8", decode_responses=True
        )

    async def disconnect(self) -> None:
        """关闭 Redis 连接。"""
        if self._client:
            await self._client.close()
            self._client = None

    def _key(self, *parts: str) -> str:
        """生成带前缀的 key。

        Args:
            *parts: Key 的各个部分。

        Returns:
            完整的 Redis Key。
        """
        return f"{self._prefix}{':'.join(parts)}"

    async def _ensure_connected(self) -> redis.Redis:
        """确保 Redis 连接已建立。

        Returns:
            Redis 客户端实例。

        Raises:
            RuntimeError: 未连接时抛出。
        """
        if self._client is None:
            raise RuntimeError("Redis 客户端未连接，请先调用 connect()")
        return self._client

    # ==================== 商品相关操作 ====================

    async def save_product(self, product: Product) -> str:
        """保存商品数据。

        Args:
            product: 商品信息模型。

        Returns:
            商品 ID。

        Raises:
            RuntimeError: Redis 未连接。
            ValueError: 商品 ID 为空。
        """
        client = await self._ensure_connected()

        if not product.product_id:
            raise ValueError("商品 ID 不能为空")

        product_id = product.product_id
        product_key = self._key("product", product_id)
        list_key = self._key("product", "list")

        # 获取当前时间戳作为排序分数
        timestamp = datetime.now().timestamp()

        # 序列化商品数据
        product_data = product.model_dump(mode="json")

        # 使用事务保存数据
        async with client.pipeline() as pipe:
            # 保存商品 Hash
            pipe.hset(product_key, mapping={"data": json.dumps(product_data, ensure_ascii=False)})
            # 添加到排序列表（按创建时间排序）
            pipe.zadd(list_key, {product_id: timestamp})
            await pipe.execute()

        return product_id

    async def get_product(self, product_id: str) -> Product | None:
        """获取商品数据。

        Args:
            product_id: 商品 ID。

        Returns:
            商品信息模型，不存在则返回 None。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        product_key = self._key("product", product_id)

        data = await client.hget(product_key, "data")
        if not data:
            return None

        try:
            product_data = json.loads(data)
            return Product(**product_data)
        except (json.JSONDecodeError, TypeError):
            return None

    async def list_products(
        self, page: int = 1, page_size: int = 10, category: str | None = None
    ) -> tuple[list[Product], int]:
        """获取商品列表（分页）。

        Args:
            page: 页码，从 1 开始。
            page_size: 每页数量。
            category: 商品类目过滤（可选）。

        Returns:
            商品列表和总数。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        list_key = self._key("product", "list")

        # 获取总数
        total = await client.zcard(list_key)

        # 计算分页偏移
        start = (page - 1) * page_size
        end = start + page_size - 1

        # 按时间倒序获取商品 ID 列表
        product_ids = await client.zrevrange(list_key, start, end)

        # 批量获取商品数据
        products: list[Product] = []
        for product_id in product_ids:
            product = await self.get_product(product_id)
            if product:
                # 类目过滤
                if category and product.category.value != category:
                    continue
                products.append(product)

        return products, total

    async def update_product(self, product: Product) -> bool:
        """更新商品数据。

        Args:
            product: 商品信息模型。

        Returns:
            是否更新成功。

        Raises:
            RuntimeError: Redis 未连接。
            ValueError: 商品 ID 为空。
        """
        client = await self._ensure_connected()

        if not product.product_id:
            raise ValueError("商品 ID 不能为空")

        product_id = product.product_id
        product_key = self._key("product", product_id)

        # 检查商品是否存在
        exists = await client.exists(product_key)
        if not exists:
            return False

        # 更新商品数据
        product_data = product.model_dump(mode="json")
        await client.hset(
            product_key, mapping={"data": json.dumps(product_data, ensure_ascii=False)}
        )

        return True

    async def delete_product(self, product_id: str) -> bool:
        """删除商品。

        Args:
            product_id: 商品 ID。

        Returns:
            是否删除成功。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        product_key = self._key("product", product_id)
        list_key = self._key("product", "list")

        # 使用事务删除
        async with client.pipeline() as pipe:
            pipe.delete(product_key)
            pipe.zrem(list_key, product_id)
            results = await pipe.execute()

        return results[0] > 0

    # ==================== 任务相关操作 ====================

    async def create_task(self, task_id: str, product_id: str, request: GenerationRequest) -> None:
        """创建任务元数据。

        Args:
            task_id: 任务 ID。
            product_id: 关联的商品 ID。
            request: 生成请求配置。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        task_key = self._key("task", task_id)
        list_key = self._key("task", "list")

        timestamp = datetime.now().timestamp()
        metadata = {
            "task_id": task_id,
            "product_id": product_id,
            "status": "pending",
            "progress": 0.0,
            "current_step": "init",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "request": request.model_dump(mode="json"),
        }

        # 使用事务保存
        async with client.pipeline() as pipe:
            pipe.hset(task_key, mapping={"metadata": json.dumps(metadata, ensure_ascii=False)})
            pipe.zadd(list_key, {task_id: timestamp})
            await pipe.execute()

    async def get_task_metadata(self, task_id: str) -> dict[str, Any] | None:
        """获取任务元数据。

        Args:
            task_id: 任务 ID。

        Returns:
            任务元数据字典，不存在则返回 None。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        task_key = self._key("task", task_id)

        data = await client.hget(task_key, "metadata")
        if not data:
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    async def save_task_state(self, task_id: str, state: AgentState) -> None:
        """保存任务状态。

        Args:
            task_id: 任务 ID。
            state: Agent 状态模型。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        state_key = self._key("task", task_id, "state")
        task_key = self._key("task", task_id)

        # 序列化状态数据
        state_data = state.model_dump(mode="json")

        async with client.pipeline() as pipe:
            # 保存完整状态
            pipe.set(state_key, json.dumps(state_data, ensure_ascii=False))
            # 更新任务元数据的更新时间
            metadata = await self.get_task_metadata(task_id)
            if metadata:
                metadata["updated_at"] = datetime.now().isoformat()
                pipe.hset(task_key, "metadata", json.dumps(metadata, ensure_ascii=False))
            await pipe.execute()

    async def get_task_state(self, task_id: str) -> AgentState | None:
        """获取任务状态。

        Args:
            task_id: 任务 ID。

        Returns:
            Agent 状态模型，不存在则返回 None。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        state_key = self._key("task", task_id, "state")

        data = await client.get(state_key)
        if not data:
            return None

        try:
            state_data = json.loads(data)
            return AgentState(**state_data)
        except (json.JSONDecodeError, TypeError):
            return None

    async def update_task_progress(
        self, task_id: str, status: str, progress: float, current_step: str
    ) -> None:
        """更新任务进度。

        Args:
            task_id: 任务 ID。
            status: 任务状态。
            progress: 进度值 (0-100)。
            current_step: 当前步骤。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        task_key = self._key("task", task_id)

        metadata = await self.get_task_metadata(task_id)
        if not metadata:
            return

        metadata["status"] = status
        metadata["progress"] = progress
        metadata["current_step"] = current_step
        metadata["updated_at"] = datetime.now().isoformat()

        await client.hset(task_key, "metadata", json.dumps(metadata, ensure_ascii=False))

    async def list_tasks(
        self, page: int = 1, page_size: int = 10, status: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """获取任务列表。

        Args:
            page: 页码，从 1 开始。
            page_size: 每页数量。
            status: 任务状态过滤（可选）。

        Returns:
            任务元数据列表和总数。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        list_key = self._key("task", "list")

        # 获取总数
        total = await client.zcard(list_key)

        # 计算分页偏移
        start = (page - 1) * page_size
        end = start + page_size - 1

        # 按时间倒序获取任务 ID 列表
        task_ids = await client.zrevrange(list_key, start, end)

        # 批量获取任务元数据
        tasks: list[dict[str, Any]] = []
        for task_id in task_ids:
            metadata = await self.get_task_metadata(task_id)
            if metadata:
                # 状态过滤
                if status and metadata.get("status") != status:
                    continue

                # 获取任务状态以提取错误信息
                task_state = await self.get_task_state(task_id)
                if task_state and task_state.error:
                    metadata["error_message"] = task_state.error

                tasks.append(metadata)

        return tasks, total

    async def delete_task(self, task_id: str) -> bool:
        """删除任务。

        Args:
            task_id: 任务 ID。

        Returns:
            是否删除成功。

        Raises:
            RuntimeError: Redis 未连接。
        """
        client = await self._ensure_connected()
        task_key = self._key("task", task_id)
        state_key = self._key("task", task_id, "state")
        list_key = self._key("task", "list")

        # 使用事务删除
        async with client.pipeline() as pipe:
            pipe.delete(task_key, state_key)
            pipe.zrem(list_key, task_id)
            results = await pipe.execute()

        return results[0] > 0


# 全局单例
_redis_client: RedisClient | None = None


async def get_redis() -> RedisClient:
    """获取 Redis 客户端实例（单例）。

    如果客户端未初始化，会自动建立连接。

    Returns:
        Redis 客户端实例。
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接。

    用于应用关闭时清理资源。
    """
    global _redis_client
    if _redis_client is not None:
        await _redis_client.disconnect()
        _redis_client = None
