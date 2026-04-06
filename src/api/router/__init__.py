"""
API 路由模块。

Description:
    注册和管理所有 API 路由端点。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from fastapi import APIRouter

from src.api.router.evaluation import router as evaluation_router
from src.api.router.health import router as health_router
from src.api.router.knowledge import router as knowledge_router
from src.api.router.products import router as products_router
from src.api.router.tasks import router as tasks_router

# API v1 路由
api_router = APIRouter(prefix="/api/v1")

# 注册子路由
api_router.include_router(health_router, tags=["健康检查"])
api_router.include_router(products_router, prefix="/products", tags=["商品管理"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["任务管理"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识库管理"])
api_router.include_router(evaluation_router, prefix="/evaluation", tags=["RAG评估"])

__all__ = [
    "api_router",
    "health_router",
    "products_router",
    "tasks_router",
    "knowledge_router",
    "evaluation_router",
]
