"""
API 模块。

FastAPI 路由、Schema 和服务层。

Description:
    提供 B 端系统的 RESTful API 接口，包括商品管理、任务管理、资源管理等功能。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from src.api.router import health, products, tasks
from src.api.schema import asset, common, product, task

__all__ = [
    "products",
    "tasks",
    "health",
    "common",
    "product",
    "task",
    "asset",
]
