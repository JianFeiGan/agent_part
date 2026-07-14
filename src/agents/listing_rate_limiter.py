"""
刊登推送速率限制器。

Description:
    基于令牌桶算法实现 API 请求速率限制，
    控制每分钟请求数（RPM），防止触发平台限流。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import asyncio
import time


class RateLimiter:
    """基于令牌桶算法的速率限制器。

    通过 asyncio.Lock 和 time.monotonic() 控制请求间隔，
    确保不超过每分钟请求限制（RPM）。

    Attributes:
        _rpm: 每分钟允许的最大请求数。
        _interval: 两次请求之间的最小间隔（秒）。
        _lock: 异步锁，保证并发安全。
        _last_request_time: 上次请求的时间戳。
    """

    def __init__(self, rpm: int = 60) -> None:
        """初始化速率限制器。

        Args:
            rpm: 每分钟允许的最大请求数，0 表示无限制。
        """
        self._rpm = rpm
        self._interval: float = 60.0 / rpm if rpm > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    async def acquire(self) -> None:
        """获取一个请求许可。

        如果距离上次请求时间不足间隔，则等待剩余时间。
        当 rpm 为 0 时，不做任何限制。
        """
        if self._rpm <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            wait_time = self._interval - elapsed

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            self._last_request_time = time.monotonic()
