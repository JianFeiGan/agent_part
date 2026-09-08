"""
租户范围 CRUD 门面包。

Description:
    公共接口出口。调用方只应 import 本模块：

        from src.api.crud import ResourceSpec, Scopes, TenantCRUD

    内部构件（_internals）与各子模块不作为公共接口。
@author ganjianfei
@version 1.0.0
2026-09-08
"""

from src.api.crud.access import require_scope, resolve_tenant
from src.api.crud.facade import TenantCRUD
from src.api.crud.mask import mask_secret, mask_values
from src.api.crud.paging import PageParams, PageParamsDep, PageResult, page_params_dep
from src.api.crud.spec import ResourceSpec, Scopes, TenantMatch

__all__ = [
    "PageParams",
    "PageParamsDep",
    "PageResult",
    "ResourceSpec",
    "Scopes",
    "TenantCRUD",
    "TenantMatch",
    "mask_secret",
    "mask_values",
    "page_params_dep",
    "require_scope",
    "resolve_tenant",
]
