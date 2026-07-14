"""
刊登推送重试策略。

Description:
    定义可重试和不可重试的推送错误类型，
    基于 tenacity 实现指数退避重试装饰器。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class RetryablePushError(Exception):
    """可重试的推送错误。

    适用于网络超时、5xx 服务端错误、429 限流等临时性故障。
    """

    pass


class PermanentPushError(Exception):
    """不可重试的推送错误。

    适用于认证失败、数据格式错误、权限不足等永久性故障。
    """

    pass


def create_push_retry_decorator(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> retry:  # type: ignore[misc]
    """创建推送重试装饰器。

    仅对 RetryablePushError 进行重试，PermanentPushError 直接抛出。
    使用指数退避策略，延迟从 base_delay 开始，最大不超过 max_delay。

    Args:
        max_retries: 最大重试次数。
        base_delay: 基础延迟（秒），指数退避的起始值。
        max_delay: 最大延迟（秒），退避上限。

    Returns:
        tenacity retry 装饰器。
    """
    return retry(
        retry=retry_if_exception_type(RetryablePushError),
        stop=stop_after_attempt(max_retries + 1),
        wait=wait_exponential(multiplier=base_delay, max=max_delay),
        reraise=True,
    )
