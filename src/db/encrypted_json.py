"""
Encrypted JSONB TypeDecorator.

Description:
    使用 cryptography Fernet 对 JSONB 列进行透明加密/解密。
    加密后的 JSONB 格式为 {"_encrypted": true, "v": 1, "ciphertext": "..."}。
    支持兼容旧明文数据（无 _encrypted 时原样返回）。
@author ganjianfei
@version 1.0.0
2026-06-16
"""

import json
import logging
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import JSON, Dialect
from sqlalchemy.types import TypeDecorator

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class EncryptedJSONB(TypeDecorator):
    """加密 JSONB TypeDecorator。

    透明加密写入、解密读取。使用 SQLAlchemy TypeDecorator，
    底层存储为普通 JSONB，应用层加解密。

    加密格式: {"_encrypted": true, "v": 1, "ciphertext": "<Fernet token>"}
    旧明文数据（无 _encrypted）直接原样返回，不抛异常。

    Example:
        >>> credentials = Column(EncryptedJSONB, default=dict)
    """

    impl = JSON
    cache_ok = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @staticmethod
    def _get_key() -> bytes:
        """获取加密密钥，fail closed。

        Returns:
            Fernet 兼容的 32 字节 URL-safe base64 密钥。

        Raises:
            ValueError: 如果 credentials_encryption_key 未配置。
        """
        raw = get_settings().credentials_encryption_key
        if not raw:
            raise ValueError(
                "credentials_encryption_key is not configured. "
                "Set CREDENTIALS_ENCRYPTION_KEY in environment."
            )
        return raw.encode() if isinstance(raw, str) else raw

    def process_bind_param(
        self, value: dict | None, dialect: Dialect  # noqa: ARG002
    ) -> dict | None:
        """写入数据库前加密。

        Args:
            value: 原始字典。
            dialect: SQLAlchemy dialect。

        Returns:
            加密后的字典（含 _encrypted 标记），或 None。
        """
        if value is None:
            return None
        try:
            key = self._get_key()
            fernet = Fernet(key)
            plaintext = json.dumps(value, ensure_ascii=False).encode("utf-8")
            token = fernet.encrypt(plaintext).decode("utf-8")
            return {"_encrypted": True, "v": 1, "ciphertext": token}
        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to encrypt credentials")
            raise ValueError("Failed to encrypt credentials") from None

    def process_result_value(
        self, value: dict | None, dialect: Dialect  # noqa: ARG002
    ) -> dict | None:
        """从数据库读取后解密。

        兼容旧明文数据：无 _encrypted 标记时原样返回。

        Args:
            value: 数据库中的值。
            dialect: SQLAlchemy dialect。

        Returns:
            解密后的原始字典，或 None。
        """
        if value is None:
            return None
        if not isinstance(value, dict):
            return value
        if not value.get("_encrypted"):
            # 旧明文数据，原样返回
            return value
        try:
            key = self._get_key()
            fernet = Fernet(key)
            token = value["ciphertext"].encode("utf-8")
            plaintext = fernet.decrypt(token)
            return json.loads(plaintext)
        except Exception:
            logger.exception("Failed to decrypt credentials")
            raise ValueError("Failed to decrypt credentials") from None
