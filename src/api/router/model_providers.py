"""模型厂商管理 API 路由。

Description:
    提供模型厂商配置的 CRUD REST 接口，包括：
    - 列表查询（按 provider_type 过滤）
    - 创建 / 更新 / 删除
    - 设置默认厂商
    - 测试连接
    所有端点需要认证，按 tenant_id 隔离数据。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

import logging
import time

from fastapi import APIRouter, Depends, status

from src.api.deps import AuthDep
from src.api.schema.common import ApiResponse
from src.api.schema.model_provider import (
    ModelProviderCreateRequest,
    ModelProviderResponse,
    ModelProviderTestRequest,
    ModelProviderTestResponse,
    ModelProviderUpdateRequest,
)
from src.auth.api_key import require_auth
from src.auth.context import AuthContext
from src.clients.provider_result import get_api_key_value
from src.db.model_provider_repository import ModelProviderRepository
from src.db.postgres import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


def _mask_api_key(api_key_field: dict | str | None) -> str:
    """脱敏 API Key，仅保留前 4 位和后 4 位。

    Args:
        api_key_field: EncryptedJSONB 解密后的 dict 或原始字符串。

    Returns:
        脱敏后的 API Key 字符串。
    """
    plain = get_api_key_value(api_key_field)
    if not plain or len(plain) <= 8:
        return "****" if plain else ""
    return f"{plain[:4]}****{plain[-4:]}"


def _po_to_response(po: object) -> ModelProviderResponse:
    """将 ORM 对象转换为脱敏响应。

    Args:
        po: ModelProviderPO 实例。

    Returns:
        脱敏后的响应模型。
    """
    return ModelProviderResponse(
        id=po.id,
        name=po.name,
        display_name=po.display_name,
        provider_type=po.provider_type,
        base_url=po.base_url,
        api_key_masked=_mask_api_key(po.api_key),
        default_model=po.default_model,
        supported_models=po.supported_models or [],
        protocol=po.protocol,
        is_active=po.is_active,
        is_default=po.is_default,
        created_at=po.created_at,
        updated_at=po.updated_at,
    )


@router.get(
    "",
    response_model=ApiResponse[list[ModelProviderResponse]],
    summary="模型厂商列表",
)
async def list_model_providers(
    provider_type: str | None = None,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[list[ModelProviderResponse]]:
    """获取模型厂商列表（仅当前租户）。

    Args:
        provider_type: 可选的厂商类型过滤（llm/image/video）。
        auth: 认证上下文。

    Returns:
        厂商配置列表（API Key 脱敏）。
    """
    async with get_db() as session:
        repo = ModelProviderRepository(session)
        providers = await repo.list_by_type(auth.tenant_id, provider_type)
        return ApiResponse(
            code=200,
            message="成功",
            data=[_po_to_response(p) for p in providers],
        )


@router.get(
    "/{provider_id}",
    response_model=ApiResponse[ModelProviderResponse],
    summary="模型厂商详情",
)
async def get_model_provider(
    provider_id: int,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ModelProviderResponse]:
    """获取单个模型厂商详情（脱敏，仅当前租户）。

    Args:
        provider_id: 厂商 ID。
        auth: 认证上下文。

    Returns:
        厂商配置详情（API Key 脱敏）。
    """
    async with get_db() as session:
        repo = ModelProviderRepository(session)
        po = await repo.get_for_tenant(provider_id, auth.tenant_id)
        if not po:
            return ApiResponse(code=404, message="厂商配置不存在", data=None)
        return ApiResponse(
            code=200,
            message="成功",
            data=_po_to_response(po),
        )


@router.post(
    "",
    response_model=ApiResponse[ModelProviderResponse],
    status_code=status.HTTP_201_CREATED,
    summary="创建模型厂商",
)
async def create_model_provider(
    request: ModelProviderCreateRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ModelProviderResponse]:
    """创建新的模型厂商配置。

    Args:
        request: 厂商创建请求。
        auth: 认证上下文。

    Returns:
        新创建的厂商配置（API Key 脱敏）。
    """
    async with get_db() as session:
        # 如果设为默认，先取消同类型其他默认
        if request.is_default:
            repo = ModelProviderRepository(session)
            await repo.set_default(auth.tenant_id, 0, request.provider_type)
            # set_default(provider_id=0) 仅清除，不设置新默认

        from src.db.models import ModelProviderPO

        po = ModelProviderPO(
            tenant_id=auth.tenant_id,
            name=request.name,
            display_name=request.display_name,
            provider_type=request.provider_type,
            base_url=request.base_url,
            api_key={"key": request.api_key} if request.api_key else {"key": ""},
            extra_credentials=request.extra_credentials,
            default_model=request.default_model,
            supported_models=request.supported_models,
            model_config_extra=request.model_config_extra,
            protocol=request.protocol,
            is_active=request.is_active,
            is_default=request.is_default,
        )
        session.add(po)
        await session.flush()
        await session.refresh(po)
        return ApiResponse(
            code=200,
            message="创建成功",
            data=_po_to_response(po),
        )


@router.put(
    "/{provider_id}",
    response_model=ApiResponse[ModelProviderResponse],
    summary="更新模型厂商",
)
async def update_model_provider(
    provider_id: int,
    request: ModelProviderUpdateRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ModelProviderResponse]:
    """更新模型厂商配置（仅当前租户）。

    Args:
        provider_id: 厂商 ID。
        request: 更新请求。
        auth: 认证上下文。

    Returns:
        更新后的厂商配置（API Key 脱敏）。
    """
    async with get_db() as session:
        repo = ModelProviderRepository(session)
        po = await repo.get_for_tenant(provider_id, auth.tenant_id)
        if not po:
            return ApiResponse(code=404, message="厂商配置不存在", data=None)

        # 逐字段更新
        if request.display_name is not None:
            po.display_name = request.display_name
        if request.base_url is not None:
            po.base_url = request.base_url
        if request.api_key is not None:
            po.api_key = {"key": request.api_key}
        if request.extra_credentials is not None:
            po.extra_credentials = request.extra_credentials
        if request.default_model is not None:
            po.default_model = request.default_model
        if request.supported_models is not None:
            po.supported_models = request.supported_models
        if request.model_config_extra is not None:
            po.model_config_extra = request.model_config_extra
        if request.protocol is not None:
            po.protocol = request.protocol
        if request.is_active is not None:
            po.is_active = request.is_active

        await session.flush()
        await session.refresh(po)
        return ApiResponse(
            code=200,
            message="更新成功",
            data=_po_to_response(po),
        )


@router.delete(
    "/{provider_id}",
    response_model=ApiResponse[None],
    summary="删除模型厂商",
)
async def delete_model_provider(
    provider_id: int,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[None]:
    """删除模型厂商配置（仅当前租户）。

    Args:
        provider_id: 厂商 ID。
        auth: 认证上下文。

    Returns:
        操作结果。
    """
    async with get_db() as session:
        repo = ModelProviderRepository(session)
        po = await repo.get_for_tenant(provider_id, auth.tenant_id)
        if not po:
            return ApiResponse(code=404, message="厂商配置不存在", data=None)

        await session.delete(po)
        await session.flush()
        return ApiResponse(code=200, message="删除成功", data=None)


@router.put(
    "/{provider_id}/default",
    response_model=ApiResponse[ModelProviderResponse],
    summary="设为默认厂商",
)
async def set_default_model_provider(
    provider_id: int,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ModelProviderResponse]:
    """将指定厂商设为该类型的默认厂商。

    同类型其他厂商自动取消默认。

    Args:
        provider_id: 厂商 ID。
        auth: 认证上下文。

    Returns:
        更新后的厂商配置（API Key 脱敏）。
    """
    async with get_db() as session:
        repo = ModelProviderRepository(session)
        # 先获取厂商以确定 provider_type
        po = await repo.get_for_tenant(provider_id, auth.tenant_id)
        if not po:
            return ApiResponse(code=404, message="厂商配置不存在", data=None)

        updated = await repo.set_default(auth.tenant_id, provider_id, po.provider_type)
        if not updated:
            return ApiResponse(code=400, message="设置默认失败", data=None)

        return ApiResponse(
            code=200,
            message="设置默认成功",
            data=_po_to_response(updated),
        )


@router.post(
    "/{provider_id}/test",
    response_model=ApiResponse[ModelProviderTestResponse],
    summary="测试厂商连接",
)
async def test_model_provider(
    provider_id: int,
    request: ModelProviderTestRequest | None = None,
    auth: AuthContext = Depends(require_auth),
) -> ApiResponse[ModelProviderTestResponse]:
    """测试模型厂商连接是否可用。

    根据厂商类型执行不同的测试：
    - LLM: 发送简单 chat 请求
    - Image: 检查 API Key 有效性
    - Video: 检查 API Key 有效性

    Args:
        provider_id: 厂商 ID。
        request: 测试请求（可选）。
        auth: 认证上下文。

    Returns:
        测试结果。
    """
    async with get_db() as session:
        repo = ModelProviderRepository(session)
        po = await repo.get_for_tenant(provider_id, auth.tenant_id)
        if not po:
            return ApiResponse(code=404, message="厂商配置不存在", data=None)

        api_key = get_api_key_value(po.api_key)
        if not api_key:
            return ApiResponse(
                code=200,
                message="成功",
                data=ModelProviderTestResponse(
                    success=False,
                    message="API Key 未配置",
                ),
            )

        test_model = (request.model if request else None) or po.default_model

        try:
            start = time.monotonic()

            if po.provider_type == "llm":
                # LLM: 通过 OpenAI 兼容接口发送简单 chat 请求
                from src.clients.openai_compatible_llm import OpenAICompatibleLLMProvider

                provider = OpenAICompatibleLLMProvider(
                    base_url=po.base_url,
                    api_key=api_key,
                    model=test_model,
                )
                chat_model = provider.create_chat_model()
                await chat_model.ainvoke("Hi")
            elif po.provider_type == "image":
                # Image: 检查 API Key 有效性（尝试生成最小图片）
                from src.clients.provider_factory import _create_image_from_config

                image_provider = _create_image_from_config(po)
                if not image_provider.is_available():
                    raise ValueError("Provider 不可用")
            elif po.provider_type == "video":
                # Video: 检查 API Key 有效性
                from src.clients.provider_factory import _create_video_from_config

                video_provider = _create_video_from_config(po)
                if not video_provider.is_available():
                    raise ValueError("Provider 不可用")
            else:
                raise ValueError(f"不支持的厂商类型: {po.provider_type}")

            latency = (time.monotonic() - start) * 1000
            return ApiResponse(
                code=200,
                message="成功",
                data=ModelProviderTestResponse(
                    success=True,
                    message="连接测试成功",
                    latency_ms=round(latency, 2),
                ),
            )
        except Exception as exc:
            logger.warning("厂商连接测试失败: provider_id=%d, error=%s", provider_id, exc)
            return ApiResponse(
                code=200,
                message="成功",
                data=ModelProviderTestResponse(
                    success=False,
                    message=f"连接测试失败: {exc}",
                ),
            )
