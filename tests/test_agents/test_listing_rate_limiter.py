"""
刊登推送速率限制器测试。

Description:
    测试 RateLimiter 的令牌桶算法实现。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import time

import pytest

from src.agents.listing_rate_limiter import RateLimiter


class TestRateLimiting:
    """速率限制测试。"""

    @pytest.mark.asyncio
    async def test_rate_limiting(self) -> None:
        """测试速率限制：连续请求之间有间隔。"""
        limiter = RateLimiter(rpm=600)  # 10 次/秒，间隔 0.1 秒

        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # 第二次请求应该等待至少约 0.1 秒
        assert elapsed >= 0.05  # 允许一定误差

    @pytest.mark.asyncio
    async def test_no_limit_when_rpm_zero(self) -> None:
        """测试 rpm=0 时不做任何限制。"""
        limiter = RateLimiter(rpm=0)

        start = time.monotonic()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # 无限制时，10 次请求应该非常快
        assert elapsed < 0.1
