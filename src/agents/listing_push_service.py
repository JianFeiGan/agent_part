"""
统一刊登推送服务。

Description:
    提供多平台并行推送能力，使用 asyncio.Semaphore 控制并发，
    asyncio.gather 并行推送，支持失败重试。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import asyncio
import logging

from src.agents.listing_platform_adapter import AdapterRegistry, PushConfig, PushResult
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    ListingTask,
    Platform,
)

logger = logging.getLogger(__name__)

# 默认最大并发推送数
DEFAULT_MAX_CONCURRENT = 5


class ListingPushService:
    """统一刊登推送服务。

    负责将刊登内容并行推送到多个目标平台，
    使用 asyncio.Semaphore 控制并发数，asyncio.gather 实现并行推送。

    Attributes:
        _registry: 适配器注册表。
        _max_concurrent: 最大并发推送数。
    """

    def __init__(
        self,
        registry: AdapterRegistry | None = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        """初始化推送服务。

        Args:
            registry: 适配器注册表，默认使用全局单例。
            max_concurrent: 最大并发推送数。
        """
        self._registry = registry or AdapterRegistry()
        self._max_concurrent = max_concurrent

    async def push_to_platforms(
        self,
        product: ListingProduct,
        asset_packages: dict[Platform, AssetPackage],
        copywriting_packages: dict[Platform, CopywritingPackage],
        task: ListingTask,
        push_config: PushConfig | None = None,
    ) -> dict[str, PushResult]:
        """并行推送到多个平台。

        使用 asyncio.Semaphore 控制并发，asyncio.gather 并行推送。

        Args:
            product: 源商品。
            asset_packages: 各平台的素材包。
            copywriting_packages: 各平台的文案包。
            task: 刊登任务。
            push_config: 可选的推送配置。

        Returns:
            各平台推送结果 {platform_name: PushResult}。
        """
        semaphore = asyncio.Semaphore(self._max_concurrent)
        results: dict[str, PushResult] = {}

        async def _push_one(platform: Platform) -> tuple[str, PushResult]:
            """推送单个平台。"""
            async with semaphore:
                try:
                    adapter = self._registry.get(platform, push_config=push_config)
                    asset_pkg = asset_packages.get(platform)
                    copy_pkg = copywriting_packages.get(platform)

                    if not asset_pkg or not copy_pkg:
                        return platform.value, PushResult(
                            success=False,
                            platform=platform,
                            error=f"Missing asset or copywriting package for {platform.value}",
                            error_code="MISSING_DATA",
                        )

                    result = await adapter.push_listing(
                        product=product,
                        asset_package=asset_pkg,
                        copywriting=copy_pkg,
                        task=task,
                    )
                    return platform.value, result

                except KeyError:
                    return platform.value, PushResult(
                        success=False,
                        platform=platform,
                        error=f"Platform {platform.value} not registered",
                        error_code="NOT_REGISTERED",
                    )
                except Exception as e:
                    logger.exception(f"Push to {platform.value} failed: {e}")
                    return platform.value, PushResult(
                        success=False,
                        platform=platform,
                        error=str(e),
                        error_code="UNEXPECTED_ERROR",
                    )

        # 并行推送所有平台
        tasks = [_push_one(platform) for platform in task.target_platforms]
        completed = await asyncio.gather(*tasks, return_exceptions=False)

        for platform_name, result in completed:
            results[platform_name] = result
            if result.success:
                logger.info(f"Push to {platform_name} succeeded, listing_id={result.listing_id}")
            else:
                logger.error(f"Push to {platform_name} failed: {result.error}")

        return results

    async def retry_failed(
        self,
        product: ListingProduct,
        asset_packages: dict[Platform, AssetPackage],
        copywriting_packages: dict[Platform, CopywritingPackage],
        task: ListingTask,
        previous_results: dict[str, PushResult],
        push_config: PushConfig | None = None,
    ) -> dict[str, PushResult]:
        """重试非 PERMANENT 错误的平台。

        仅重试 error_code 不是 PERMANENT_ERROR 的失败推送。

        Args:
            product: 源商品。
            asset_packages: 各平台的素材包。
            copywriting_packages: 各平台的文案包。
            task: 刊登任务。
            previous_results: 上次推送结果。
            push_config: 可选的推送配置。

        Returns:
            更新后的推送结果（包含重试结果）。
        """
        # 筛选可重试的失败平台
        retry_platforms: list[Platform] = []
        for _platform_name, result in previous_results.items():
            if not result.success and result.error_code != "PERMANENT_ERROR":
                retry_platforms.append(result.platform)

        if not retry_platforms:
            return previous_results

        logger.info(f"Retrying push for platforms: {[p.value for p in retry_platforms]}")

        # 创建仅包含重试平台的任务
        retry_task = task.model_copy(update={"target_platforms": retry_platforms})

        retry_results = await self.push_to_platforms(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            task=retry_task,
            push_config=push_config,
        )

        # 合并结果
        merged = dict(previous_results)
        merged.update(retry_results)
        return merged
