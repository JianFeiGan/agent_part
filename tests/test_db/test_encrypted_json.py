"""
EncryptedJSONB TypeDecorator 测试。

Description:
    测试 EncryptedJSONB 的加密/解密行为，包括：
    - 正常加密解密往返
    - None 值处理
    - 空密钥 fail closed
    - 旧明文兼容
    - 损坏密文异常
@author ganjianfei
@version 1.0.0
2026-06-16
"""

import json
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from src.db.encrypted_json import EncryptedJSONB

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fernet_key() -> bytes:
    """生成测试用 Fernet 密钥。"""
    return Fernet.generate_key()


@pytest.fixture
def fernet_key_str(fernet_key: bytes) -> str:
    """测试用 Fernet 密钥（字符串）。"""
    return fernet_key.decode("utf-8")


@pytest.fixture
def type_decorator() -> EncryptedJSONB:
    """EncryptedJSONB 实例。"""
    return EncryptedJSONB()


# ---------------------------------------------------------------------------
# process_bind_param (加密写入)
# ---------------------------------------------------------------------------

class TestProcessBindParam:
    """写入加密测试。"""

    def test_encrypt_dict(self, type_decorator: EncryptedJSONB, fernet_key_str: str) -> None:
        """测试正常加密字典。"""
        with patch("src.db.encrypted_json.get_settings") as mock_settings:
            mock_settings.return_value.credentials_encryption_key = fernet_key_str

            plain = {"client_id": "abc", "client_secret": "xyz"}
            result = type_decorator.process_bind_param(plain, None)

            assert result is not None
            assert result["_encrypted"] is True
            assert result["v"] == 1
            assert "ciphertext" in result
            # 解密验证
            fernet = Fernet(fernet_key_str.encode())
            decrypted = json.loads(fernet.decrypt(result["ciphertext"].encode()))
            assert decrypted == plain

    def test_encrypt_none(self, type_decorator: EncryptedJSONB) -> None:
        """测试 None 值原样返回。"""
        result = type_decorator.process_bind_param(None, None)
        assert result is None

    def test_encrypt_empty_key_raises(self, type_decorator: EncryptedJSONB) -> None:
        """测试空密钥时抛出 ValueError。"""
        with patch("src.db.encrypted_json.get_settings") as mock_settings:
            mock_settings.return_value.credentials_encryption_key = ""

            with pytest.raises(ValueError, match="credentials_encryption_key"):
                type_decorator.process_bind_param({"key": "value"}, None)

    def test_encrypt_empty_dict(self, type_decorator: EncryptedJSONB, fernet_key_str: str) -> None:
        """测试加密空字典。"""
        with patch("src.db.encrypted_json.get_settings") as mock_settings:
            mock_settings.return_value.credentials_encryption_key = fernet_key_str

            result = type_decorator.process_bind_param({}, None)
            assert result is not None
            assert result["_encrypted"] is True
            fernet = Fernet(fernet_key_str.encode())
            decrypted = json.loads(fernet.decrypt(result["ciphertext"].encode()))
            assert decrypted == {}


# ---------------------------------------------------------------------------
# process_result_value (解密读取)
# ---------------------------------------------------------------------------

class TestProcessResultValue:
    """读取解密测试。"""

    def test_decrypt_encrypted_value(
        self, type_decorator: EncryptedJSONB, fernet_key_str: str
    ) -> None:
        """测试解密加密值。"""
        fernet = Fernet(fernet_key_str.encode())
        plain = {"client_id": "abc", "client_secret": "xyz"}
        token = fernet.encrypt(json.dumps(plain).encode()).decode()

        encrypted = {"_encrypted": True, "v": 1, "ciphertext": token}

        with patch("src.db.encrypted_json.get_settings") as mock_settings:
            mock_settings.return_value.credentials_encryption_key = fernet_key_str

            result = type_decorator.process_result_value(encrypted, None)
            assert result == plain

    def test_decrypt_none(self, type_decorator: EncryptedJSONB) -> None:
        """测试 None 值原样返回。"""
        result = type_decorator.process_result_value(None, None)
        assert result is None

    def test_legacy_plaintext(self, type_decorator: EncryptedJSONB) -> None:
        """测试旧明文数据原样返回（无 _encrypted 标记）。"""
        plain = {"client_id": "legacy_id", "client_secret": "legacy_secret"}
        result = type_decorator.process_result_value(plain, None)
        assert result == plain

    def test_legacy_plaintext_no_encrypted_flag(
        self, type_decorator: EncryptedJSONB
    ) -> None:
        """测试没有 _encrypted: True 标记时原样返回。"""
        value = {"_encrypted": False, "data": "something"}
        result = type_decorator.process_result_value(value, None)
        assert result == value

    def test_decrypt_corrupted_ciphertext_raises(
        self, type_decorator: EncryptedJSONB, fernet_key_str: str
    ) -> None:
        """测试损坏密文抛出 ValueError。"""
        encrypted = {"_encrypted": True, "v": 1, "ciphertext": "not-valid-fernet-token"}

        with patch("src.db.encrypted_json.get_settings") as mock_settings:
            mock_settings.return_value.credentials_encryption_key = fernet_key_str

            with pytest.raises(ValueError, match="Failed to decrypt"):
                type_decorator.process_result_value(encrypted, None)

    def test_decrypt_wrong_key_raises(
        self, type_decorator: EncryptedJSONB, fernet_key_str: str
    ) -> None:
        """测试用错误密钥解密时抛出 ValueError。"""
        fernet = Fernet(fernet_key_str.encode())
        plain = {"key": "value"}
        token = fernet.encrypt(json.dumps(plain).encode()).decode()
        encrypted = {"_encrypted": True, "v": 1, "ciphertext": token}

        different_key = Fernet.generate_key().decode()

        with patch("src.db.encrypted_json.get_settings") as mock_settings:
            mock_settings.return_value.credentials_encryption_key = different_key

            with pytest.raises(ValueError, match="Failed to decrypt"):
                type_decorator.process_result_value(encrypted, None)

    def test_roundtrip(
        self, type_decorator: EncryptedJSONB, fernet_key_str: str
    ) -> None:
        """测试加密-解密往返。"""
        with patch("src.db.encrypted_json.get_settings") as mock_settings:
            mock_settings.return_value.credentials_encryption_key = fernet_key_str

            plain = {
                "client_id": "my_client",
                "client_secret": "my_secret",
                "nested": {"key": "value"},
            }
            encrypted = type_decorator.process_bind_param(plain, None)
            decrypted = type_decorator.process_result_value(encrypted, None)
            assert decrypted == plain
