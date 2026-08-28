"""LLM 响应 JSON 提取工具。

Description:
    统一处理 LLM 输出中的 JSON 提取与解析：
    - 纯 JSON 文本
    - ```json ... ``` 围栏代码块
    - 前后夹杂说明文字的 JSON 对象
解析失败时记录 warning 并返回 None，由调用方决定兜底逻辑。
@author ganjianfei
@version 1.0.0
2026-08-25
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ```json ... ``` 或 ``` ... ``` 围栏代码块
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    """从 LLM 响应文本中提取第一个 JSON 对象。

    Args:
        text: LLM 响应文本。

    Returns:
        解析出的字典；无法提取或解析失败时返回 None。
    """
    if not text:
        return None

    # 优先尝试 ```json 围栏代码块内容
    for match in _FENCE_RE.finditer(text):
        try:
            parsed = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    # 从每个 "{" 位置尝试解析（兼容前后混杂说明文字、多个 JSON 片段）
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            parsed, _ = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)
            continue
        if isinstance(parsed, dict):
            return parsed
        idx = text.find("{", idx + 1)

    logger.warning(
        "LLM 响应 JSON 提取失败（返回 None），响应片段: %.200s",
        text.strip(),
    )
    return None


def extract_json_list(text: str) -> list[Any] | None:
    """从 LLM 响应文本中提取 JSON 数组。

    Args:
        text: LLM 响应文本。

    Returns:
        解析出的列表；无法提取或解析失败时返回 None。
    """
    if not text:
        return None

    # 优先尝试 ```json 围栏代码块内容
    for match in _FENCE_RE.finditer(text):
        try:
            parsed = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed

    # 从每个 "[" 位置尝试解析（兼容前后混杂说明文字）
    decoder = json.JSONDecoder()
    idx = text.find("[")
    while idx != -1:
        try:
            parsed, _ = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            idx = text.find("[", idx + 1)
            continue
        if isinstance(parsed, list):
            return parsed
        idx = text.find("[", idx + 1)

    logger.warning(
        "LLM 响应 JSON 数组提取失败（返回 None），响应片段: %.200s",
        text.strip(),
    )
    return None
