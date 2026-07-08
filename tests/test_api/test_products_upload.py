"""
商品图片上传 API 测试。

Description:
    测试 upload_product_image 接口的上传成功、MIME 拒绝、大小限制、
    SHA256 去重和 scope 校验。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from src.api.router.products import upload_product_image
from src.auth.context import AuthContext
from src.config.settings import Settings
from src.db.asset_repository import AssetRepository
from src.db.listing_models import GeneratedAssetPO

# ==================== Helpers ====================


def _make_auth(tenant_id: str = "tenant_test", scopes: list[str] | None = None) -> AuthContext:
    """创建测试用 AuthContext。"""
    if scopes is None:
        scopes = ["products:write"]
    return AuthContext(tenant_id=tenant_id, user_id="user_1", scopes=scopes)


def _make_settings(max_upload_size_mb: int = 10) -> Settings:
    """创建测试用 Settings，覆盖 max_upload_size_mb。"""
    return Settings(max_upload_size_mb=max_upload_size_mb)


def _make_upload_file(
    content: bytes,
    filename: str = "test.png",
    content_type: str = "image/png",
) -> UploadFile:
    """创建测试用 UploadFile。"""
    return UploadFile(filename=filename, file=io.BytesIO(content), headers={"content-type": content_type})


def _make_asset_po(asset_id: int = 1, url: str = "/static/images/test.png") -> GeneratedAssetPO:
    """创建测试用 GeneratedAssetPO。"""
    return GeneratedAssetPO(
        id=asset_id,
        tenant_id="tenant_test",
        product_id="prod_001",
        asset_type="image",
        provider="user_upload",
        url=url,
        storage_key="images/test.png",
        storage_backend="local",
        mime_type="image/png",
        file_size=100,
        sha256="abc123",
        status="completed",
        is_mock=False,
    )


# ==================== Test Cases ====================


class TestUploadImageSuccess:
    """测试上传成功场景。"""

    @pytest.mark.asyncio
    async def test_upload_image_success(self) -> None:
        """成功上传图片，落盘并返回 URL。"""
        # 准备
        auth = _make_auth()
        settings = _make_settings()
        redis = MagicMock()
        redis.get_product = AsyncMock(return_value=MagicMock())

        content = b"fake-png-data-for-test"
        file = _make_upload_file(content=content, content_type="image/png")

        asset_mock = _make_asset_po(asset_id=42, url="/static/products/tenant_test/prod_001/abcd.png")

        # Mock 存储后端
        with patch(
            "src.api.router.products.get_storage_backend"
        ) as mock_get_backend:
            backend_mock = MagicMock()
            backend_mock.save = AsyncMock(
                return_value="/static/products/tenant_test/prod_001/abcd.png"
            )
            backend_mock.delete = AsyncMock(return_value=True)
            mock_get_backend.return_value = backend_mock

            # Mock DB session + AssetRepository
            with patch("src.api.router.products.get_db") as mock_get_db:
                mock_session = MagicMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_get_db.return_value = mock_session

                mock_repo = MagicMock(spec=AssetRepository)
                mock_repo.find_by_sha256 = AsyncMock(return_value=None)
                mock_repo.create_asset = AsyncMock(return_value=asset_mock)

                with patch(
                    "src.api.router.products.AssetRepository",
                    return_value=mock_repo,
                ):
                    result = await upload_product_image(
                        product_id="prod_001",
                        redis=redis,
                        auth=auth,
                        settings=settings,
                        file=file,
                    )

        # 验证
        assert result.code == 200
        assert result.data["url"] == "/static/products/tenant_test/prod_001/abcd.png"
        assert result.data["asset_id"] == 42
        assert result.data["size"] == len(content)
        assert result.data["content_type"] == "image/png"

        # 验证存储后端被调用
        backend_mock.save.assert_awaited_once()
        mock_repo.create_asset.assert_awaited_once()
        # 确认 create_asset 参数正确
        call_kwargs = mock_repo.create_asset.call_args.kwargs
        assert call_kwargs["tenant_id"] == "tenant_test"
        assert call_kwargs["product_id"] == "prod_001"
        assert call_kwargs["asset_type"] == "image"
        assert call_kwargs["provider"] == "user_upload"
        assert call_kwargs["mime_type"] == "image/png"
        assert call_kwargs["file_size"] == len(content)
        assert call_kwargs["status"] == "completed"
        assert call_kwargs["is_mock"] is False


class TestUploadRejectsInvalidMime:
    """测试 MIME 类型校验。"""

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_mime(self) -> None:
        """text/plain 类型应返回 400。"""
        auth = _make_auth()
        settings = _make_settings()
        redis = MagicMock()
        redis.get_product = AsyncMock(return_value=MagicMock())

        file = _make_upload_file(content=b"not-an-image", content_type="text/plain")

        with pytest.raises(HTTPException) as exc_info:
            await upload_product_image(
                product_id="prod_001",
                redis=redis,
                auth=auth,
                settings=settings,
                file=file,
            )

        assert exc_info.value.status_code == 400
        assert "text/plain" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_upload_rejects_no_content_type(self) -> None:
        """无 content_type（默认为 application/octet-stream）应返回 400。"""
        auth = _make_auth()
        settings = _make_settings()
        redis = MagicMock()
        redis.get_product = AsyncMock(return_value=MagicMock())

        file = _make_upload_file(content=b"data", content_type="application/octet-stream")

        with pytest.raises(HTTPException) as exc_info:
            await upload_product_image(
                product_id="prod_001",
                redis=redis,
                auth=auth,
                settings=settings,
                file=file,
            )

        assert exc_info.value.status_code == 400


class TestUploadRejectsTooLarge:
    """测试文件大小限制。"""

    @pytest.mark.asyncio
    async def test_upload_rejects_too_large(self) -> None:
        """超过 max_upload_size_mb 应返回 413。"""
        auth = _make_auth()
        settings = _make_settings(max_upload_size_mb=1)  # 1MB limit
        redis = MagicMock()
        redis.get_product = AsyncMock(return_value=MagicMock())

        # 创建 1MB + 1 byte 的内容
        content = b"x" * (1 * 1024 * 1024 + 1)
        file = _make_upload_file(content=content, content_type="image/png")

        with pytest.raises(HTTPException) as exc_info:
            await upload_product_image(
                product_id="prod_001",
                redis=redis,
                auth=auth,
                settings=settings,
                file=file,
            )

        assert exc_info.value.status_code == 413
        assert "1MB" in exc_info.value.detail


class TestUploadDedupesBySha256:
    """测试 SHA256 去重。"""

    @pytest.mark.asyncio
    async def test_upload_dedupes_by_sha256(self) -> None:
        """相同内容上传两次只创建一条 DB 记录，第二次复用已有资产。"""
        auth = _make_auth()
        settings = _make_settings()
        redis = MagicMock()
        redis.get_product = AsyncMock(return_value=MagicMock())

        content = b"same-image-content-for-dedup"
        file1 = _make_upload_file(content=content, content_type="image/png")
        file2 = _make_upload_file(content=content, content_type="image/png")

        existing_asset = _make_asset_po(asset_id=1, url="/static/products/test/existing.png")

        # 第一次上传：find_by_sha256 -> None，然后 create_asset
        # 第二次上传：find_by_sha256 -> 命中已有资产
        with patch("src.api.router.products.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_session

            # 第一次上传
            mock_repo1 = MagicMock(spec=AssetRepository)
            mock_repo1.find_by_sha256 = AsyncMock(return_value=None)
            mock_repo1.create_asset = AsyncMock(return_value=existing_asset)

            with patch(
                "src.api.router.products.get_storage_backend"
            ) as mock_get_backend:
                backend_mock = MagicMock()
                backend_mock.save = AsyncMock(return_value=existing_asset.url)
                mock_get_backend.return_value = backend_mock

                with patch(
                    "src.api.router.products.AssetRepository",
                    return_value=mock_repo1,
                ):
                    result1 = await upload_product_image(
                        product_id="prod_001",
                        redis=redis,
                        auth=auth,
                        settings=settings,
                        file=file1,
                    )

            # 第二次上传：命中去重
            mock_repo2 = MagicMock(spec=AssetRepository)
            mock_repo2.find_by_sha256 = AsyncMock(return_value=existing_asset)
            mock_repo2.create_asset = AsyncMock()

            with patch(
                "src.api.router.products.AssetRepository",
                return_value=mock_repo2,
            ):
                result2 = await upload_product_image(
                    product_id="prod_001",
                    redis=redis,
                    auth=auth,
                    settings=settings,
                    file=file2,
                )

        # 第一次上传：创建了记录
        assert result1.code == 200
        assert result1.data["asset_id"] == 1
        mock_repo1.create_asset.assert_awaited_once()

        # 第二次上传：复用已有资产，没有创建新记录
        assert result2.code == 200
        assert result2.data["asset_id"] == 1
        assert result2.data["url"] == existing_asset.url
        mock_repo2.create_asset.assert_not_awaited()


class TestUploadRequiresWriteScope:
    """测试 scope 校验。"""

    @pytest.mark.asyncio
    async def test_upload_requires_write_scope(self) -> None:
        """仅 read scope 应返回 403。"""
        auth = _make_auth(scopes=["products:read"])
        settings = _make_settings()
        redis = MagicMock()

        file = _make_upload_file(content=b"data", content_type="image/png")

        with pytest.raises(HTTPException) as exc_info:
            await upload_product_image(
                product_id="prod_001",
                redis=redis,
                auth=auth,
                settings=settings,
                file=file,
            )

        assert exc_info.value.status_code == 403


class TestUploadStorageRollback:
    """测试失败回滚。"""

    @pytest.mark.asyncio
    async def test_db_failure_cleans_storage(self) -> None:
        """DB 写入失败时，应尝试删除已落盘的 storage 文件。"""
        auth = _make_auth()
        settings = _make_settings()
        redis = MagicMock()
        redis.get_product = AsyncMock(return_value=MagicMock())

        content = b"test-content-for-rollback"
        file = _make_upload_file(content=content, content_type="image/png")

        with patch("src.api.router.products.get_db") as mock_get_db:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_db.return_value = mock_session

            mock_repo = MagicMock(spec=AssetRepository)
            mock_repo.find_by_sha256 = AsyncMock(return_value=None)
            mock_repo.create_asset = AsyncMock(side_effect=RuntimeError("DB write error"))

            with (
                patch(
                    "src.api.router.products.get_storage_backend"
                ) as mock_get_backend,
                patch(
                    "src.api.router.products.AssetRepository",
                    return_value=mock_repo,
                ),
            ):
                backend_mock = MagicMock()
                backend_mock.save = AsyncMock(
                    return_value="/static/products/test/rollback.png"
                )
                backend_mock.delete = AsyncMock(return_value=True)
                mock_get_backend.return_value = backend_mock

                with pytest.raises(HTTPException) as exc_info:
                    await upload_product_image(
                        product_id="prod_001",
                        redis=redis,
                        auth=auth,
                        settings=settings,
                        file=file,
                    )

        assert exc_info.value.status_code == 500
        assert "资产记录写入失败" in exc_info.value.detail
        # 验证 storage.delete 被调用以清理
        backend_mock.delete.assert_awaited_once()
