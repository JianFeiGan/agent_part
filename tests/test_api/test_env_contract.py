"""环境变量契约测试。

Description:
    断言仓库根 `.env.example`（环境变量契约）与 `src.config.settings.Settings`
    （配置模型）保持双向一致：契约里每个键都必须被配置模型真实读取，
    部署必填字段必须在契约里有声明，契约内不得出现重复键或废弃同义键。
    键名拼错时 pydantic-settings 会静默忽略并回退默认值，本文件把该类
    缺陷变成测试期失败并指明具体键名。另覆盖厂商密钥的双来源约定：
    model_providers 配置表优先，环境变量兜底。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.provider_factory import ProviderFactory
from src.config.settings import Settings, get_settings

_CONTRACT_PATH = Path(__file__).resolve().parents[2] / ".env.example"

# 不进配置模型的契约键豁免清单。每个豁免必须写明理由，且键名从契约
# 删除时同步移除；豁免集合必须与「契约键 - Settings 字段」精确相等，
# 新增未建模键一律显式豁免，不允许默默跳过。
# 注：LANGCHAIN_* 追踪键除被 langsmith 直接读取外也建模为
# langchain_tracing_v2 等字段，按普通契约键校验，不在此豁免。
ENV_EXEMPTIONS: dict[str, str] = {
    "DASHSCOPE_API_BASE": (
        "DashScope 原生协议基址的部署说明位：当前实现端点硬编码于 "
        "src/clients/dashscope_image_client.py，Settings 未建模该键，"
        "dashscope SDK 亦未安装。已知契约漂移，保留待裁决（从契约移除 "
        "或补 Settings 字段），豁免保证不被静默跳过。"
    ),
}

# 部署必填范畴：不配置/配错会导致拒绝服务、鉴权旁路或依赖不可达的字段。
# 新增此类字段时必须同步 .env.example 与本清单。
DEPLOYMENT_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "credentials_encryption_key",
        "auth_api_tokens_json",
        "auth_enabled",
        "auth_allow_ws_query_token",
        "cors_allow_origins",
        "allow_mock_assets",
        "db_auto_create",
        "postgres_host",
        "postgres_port",
        "postgres_user",
        "postgres_password",
        "postgres_db",
        "redis_url",
    }
)

# 历史废弃/同义键黑名单：出现在契约中即失败（见 16e9551 契约清理）。
DEPRECATED_KEYS: dict[str, str] = {
    "DATABASE_URL": "整串连接配置已废弃，改用 POSTGRES_HOST/PORT/USER/PASSWORD/DB 分项拼装",
    "VECTOR_DIMENSION": "已更名为 EMBEDDING_DIMENSION",
    "RAG_QUERY_REWRITING_ENABLED": "RAG_ 多余前缀会被静默忽略，正确键为 QUERY_REWRITING_ENABLED",
    "RAG_QUERY_REWRITING_MODE": "RAG_ 多余前缀会被静默忽略，正确键为 QUERY_REWRITING_MODE",
    "RAG_QUERY_REWRITING_MAX_VARIANTS": (
        "RAG_ 多余前缀会被静默忽略，正确键为 QUERY_REWRITING_MAX_VARIANTS"
    ),
    "RAG_HYDE_ENABLED": "RAG_ 多余前缀会被静默忽略，正确键为 HYDE_ENABLED",
    "RAG_RERANKER_ENABLED": "RAG_ 多余前缀会被静默忽略，正确键为 RERANKER_ENABLED",
    "RAG_RERANKER_MODEL": "RAG_ 多余前缀会被静默忽略，正确键为 RERANKER_MODEL",
    "RAG_RERANKER_TOP_K": "RAG_ 多余前缀会被静默忽略，正确键为 RERANKER_TOP_K",
    "RAG_RERANKER_DEVICE": "RAG_ 多余前缀会被静默忽略，正确键为 RERANKER_DEVICE",
    "RAG_HYBRID_RETRIEVAL_ENABLED": (
        "RAG_ 多余前缀会被静默忽略，正确键为 HYBRID_RETRIEVAL_ENABLED"
    ),
    "RAG_HYBRID_MODEL": "RAG_ 多余前缀会被静默忽略，正确键为 HYBRID_MODEL",
    "RAG_HYBRID_DENSE_WEIGHT": "RAG_ 多余前缀会被静默忽略，正确键为 HYBRID_DENSE_WEIGHT",
    "RAG_HYBRID_SPARSE_WEIGHT": "RAG_ 多余前缀会被静默忽略，正确键为 HYBRID_SPARSE_WEIGHT",
    "RAG_HYBRID_COLBERT_WEIGHT": "RAG_ 多余前缀会被静默忽略，正确键为 HYBRID_COLBERT_WEIGHT",
    "RAG_HYBRID_RRF_K": "RAG_ 多余前缀会被静默忽略，正确键为 HYBRID_RRF_K",
}

# 厂商密钥双来源约定的环境变量兜底面（配置表优先，环境变量兜底）。
VENDOR_ENV_KEYS: frozenset[str] = frozenset(
    {
        "QWEN_API_KEY",
        "DASHSCOPE_API_KEY",
        "SENSENOVA_API_KEY",
        "KLING_ACCESS_KEY",
        "KLING_SECRET_KEY",
    }
)


def _load_contract_keys() -> list[str]:
    """解析契约文件中的环境变量键名。

    按 dotenv 绑定规则取每行首个 `=` 左侧，跳过注释与空行，
    保持出现顺序（含重复，供重复键断言使用）。

    Returns:
        契约声明的键名列表。
    """
    keys: list[str] = []
    for raw_line in _CONTRACT_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.append(key)
    return keys


def _settings_field_names() -> set[str]:
    """返回配置模型的字段名集合。

    Returns:
        `Settings` 全部字段名。
    """
    return set(Settings.model_fields)


def _unmapped_contract_keys(keys: list[str], fields: set[str]) -> set[str]:
    """返回契约中解析不到配置模型字段的键。

    绑定规则与 pydantic-settings 一致：无 env_prefix/alias 时按字段名
    大小写不敏感对应。

    Args:
        keys: 契约键名列表。
        fields: 配置模型字段名集合。

    Returns:
        无法解析到字段的契约键集合。
    """
    lowered = {field.lower() for field in fields}
    return {key for key in keys if key.lower() not in lowered}


def _force_vendor_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """显式设置全部厂商密钥环境变量并刷新配置缓存。

    Args:
        monkeypatch: pytest 的 monkeypatch 夹具。
        overrides: 需要覆盖的键值；未给出的键一律置空，
            避免本机 `.env` 中的实配泄入用例。
    """
    for name in VENDOR_ENV_KEYS:
        monkeypatch.setenv(name, overrides.get(name, ""))
    get_settings.cache_clear()


class TestContractKeysMapToSettings:
    """契约键与配置模型字段的对应关系。"""

    def test_contract_keys_resolve_to_settings_fields(self) -> None:
        """契约声明的每个键都能解析到配置模型上的真实字段（豁免项除外）。

        反例：把契约里任一键名写错时，本用例失败并指明是哪个键——
        否则拼错的键会被 pydantic-settings 静默忽略，配置改了也不生效。
        """
        keys = _load_contract_keys()
        fields = _settings_field_names()
        unmapped = sorted(_unmapped_contract_keys(keys, fields) - set(ENV_EXEMPTIONS))
        details = "\n".join(f"  - {key}" for key in unmapped)
        assert not unmapped, (
            f"以下契约键解析不到 Settings 字段（拼错会被静默忽略、回退默认值）:\n{details}"
        )

    def test_exemption_list_is_exact_and_justified(self) -> None:
        """豁免清单与未建模键精确相等，且每条豁免写明理由。

        未建模键必须显式豁免，豁免过期必须移除，禁止默默跳过。
        """
        keys = _load_contract_keys()
        fields = _settings_field_names()
        unmapped = _unmapped_contract_keys(keys, fields)
        assert unmapped == set(ENV_EXEMPTIONS), (
            f"豁免清单与未建模契约键不一致。未豁免的多余键: "
            f"{sorted(unmapped - set(ENV_EXEMPTIONS))}; "
            f"陈旧豁免（键已建模或已从契约删除）: "
            f"{sorted(set(ENV_EXEMPTIONS) - unmapped)}"
        )
        blank = [key for key, reason in ENV_EXEMPTIONS.items() if not reason.strip()]
        assert not blank, f"豁免必须写明理由，以下键理由为空: {blank}"


class TestContractCoverage:
    """契约对部署必填字段的覆盖与键卫生。"""

    def test_deployment_required_fields_are_declared_in_contract(self) -> None:
        """部署必填范畴的字段都在契约里有声明，防契约漏项。"""
        contract_upper = {key.upper() for key in _load_contract_keys()}
        fields = _settings_field_names()
        missing = sorted(
            field.upper() for field in DEPLOYMENT_REQUIRED_FIELDS if field not in fields
        )
        assert not missing, f"部署必填清单里的字段不在 Settings 上: {missing}"
        absent = sorted(
            field.upper()
            for field in DEPLOYMENT_REQUIRED_FIELDS
            if field.upper() not in contract_upper
        )
        details = "\n".join(f"  - {key}" for key in absent)
        assert not absent, f"以下部署必填键未在 {_CONTRACT_PATH.name} 中声明:\n{details}"

    def test_contract_has_no_duplicate_keys(self) -> None:
        """契约内无重复键（含仅大小写不同的重复）。"""
        keys = _load_contract_keys()
        exact_dupes = sorted({key for key in keys if keys.count(key) > 1})
        seen: set[str] = set()
        case_dupes: list[str] = []
        for key in keys:
            if key.upper() in seen:
                case_dupes.append(key)
            else:
                seen.add(key.upper())
        assert not exact_dupes, f"契约内出现重复键: {exact_dupes}"
        assert not case_dupes, f"契约内出现仅大小写不同的同义键: {sorted(set(case_dupes))}"

    def test_contract_has_no_deprecated_keys(self) -> None:
        """契约内无同义废弃键。"""
        keys = _load_contract_keys()
        deprecated = sorted({key for key in keys if key.upper() in DEPRECATED_KEYS})
        details = "\n".join(f"  - {key}: {DEPRECATED_KEYS[key.upper()]}" for key in deprecated)
        assert not deprecated, f"契约内出现废弃/同义键:\n{details}"

    def test_deprecated_denylist_entries_are_not_settings_fields(self) -> None:
        """废弃键黑名单不得误封真实字段。"""
        fields = {field.upper() for field in _settings_field_names()}
        wrongly_banned = sorted(set(DEPRECATED_KEYS) & fields)
        assert not wrongly_banned, f"黑名单键已是 Settings 字段，应从黑名单移除: {wrongly_banned}"


class TestVendorKeyDualSource:
    """厂商密钥双来源约定：配置表优先，环境变量兜底。"""

    def test_vendor_env_keys_are_declared_in_contract(self) -> None:
        """环境变量兜底面的厂商密钥都在契约里有声明。"""
        contract_upper = {key.upper() for key in _load_contract_keys()}
        absent = sorted(VENDOR_ENV_KEYS - contract_upper)
        details = "\n".join(f"  - {key}" for key in absent)
        assert not absent, f"以下厂商密钥未在契约中声明:\n{details}"

    async def test_vendor_key_prefers_provider_table_over_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """model_providers 表有配置时，密钥取自配置表，环境变量不生效。"""
        from src.db.model_provider_repository import ModelProviderRepository

        _force_vendor_env(monkeypatch, DASHSCOPE_API_KEY="env-secret")
        db_config = SimpleNamespace(
            protocol="openai_compatible",
            base_url="https://db-provider.example/v1",
            api_key={"key": "db-secret"},
            default_model="db-model",
            model_config_extra={},
            name="custom",
        )
        monkeypatch.setattr(
            ModelProviderRepository, "get_default", AsyncMock(return_value=db_config)
        )
        provider = await ProviderFactory.get_llm_provider(
            session=cast(AsyncSession, MagicMock()), tenant_id="tenant-1"
        )
        assert provider is not None
        chat_model = provider.create_chat_model()
        assert chat_model.openai_api_key.get_secret_value() == "db-secret"
        assert chat_model.model_name == "db-model"

    async def test_vendor_key_falls_back_to_env_without_provider_table(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """表内无厂商配置时，LLM Provider 兜底读取环境变量密钥。"""
        _force_vendor_env(monkeypatch, DASHSCOPE_API_KEY="env-secret")
        provider = await ProviderFactory.get_llm_provider(session=None)
        assert provider is not None
        chat_model = provider.create_chat_model()
        assert chat_model.openai_api_key.get_secret_value() == "env-secret"

    async def test_vendor_key_absent_in_both_sources_yields_no_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """两个来源都无密钥时不产出 Provider，不静默降级。"""
        _force_vendor_env(monkeypatch)
        provider = await ProviderFactory.get_llm_provider(session=None)
        assert provider is None
