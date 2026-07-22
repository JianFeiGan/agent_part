"""Provider 抽象协议定义。

Description:
    为 LLM、图片生成、视频生成各定义 Protocol 接口。
    现有客户端只需满足方法签名即可被视为实现了协议，无需显式继承。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.clients.provider_result import ImageGenerationResult, VideoGenerationResult


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """LLM 提供商协议。

    职责：根据配置创建一个 LangChain BaseChatModel 实例。
    Agent 不直接调用此协议生成文本，而是通过 BaseChatModel 标准接口。
    """

    def is_available(self) -> bool:
        """是否已配置必要的 API Key / 凭证。

        Returns:
            已配置返回 True，否则 False。
        """
        ...

    def create_chat_model(self) -> "BaseChatModel":
        """创建 LangChain BaseChatModel 实例。

        Returns:
            可用于 LangChain chain 的 ChatModel 实例。
        """
        ...


@runtime_checkable
class ImageProviderProtocol(Protocol):
    """图片生成提供商协议。"""

    def is_available(self) -> bool:
        """是否已配置必要的 API Key / 凭证。

        Returns:
            已配置返回 True，否则 False。
        """
        ...

    async def generate(
        self,
        prompt: str,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        n: int = 1,
        seed: int | None = None,
    ) -> ImageGenerationResult:
        """生成图片。

        Args:
            prompt: 正向提示词。
            negative_prompt: 负向提示词。
            width: 宽度（像素）。
            height: 高度（像素）。
            n: 生成数量。
            seed: 随机种子。

        Returns:
            图片生成结果。

        Raises:
            ProviderUnavailableError: 调用失败时抛出。
        """
        ...


@runtime_checkable
class VideoProviderProtocol(Protocol):
    """视频生成提供商协议。"""

    def is_available(self) -> bool:
        """是否已配置必要的 API Key / 凭证。

        Returns:
            已配置返回 True，否则 False。
        """
        ...

    async def generate(
        self,
        prompt: str,
        image: bytes | None = None,
        duration: float = 5.0,
        mode: str = "std",
        cfg_scale: float = 0.5,
        aspect_ratio: str = "16:9",
    ) -> VideoGenerationResult:
        """生成视频。

        Args:
            prompt: 视频提示词。
            image: 可选首帧图片字节。
            duration: 时长（秒）。
            mode: 生成模式。
            cfg_scale: 自由度参数。
            aspect_ratio: 宽高比。

        Returns:
            视频生成结果。

        Raises:
            ProviderUnavailableError: 调用失败时抛出。
        """
        ...
