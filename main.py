"""
FastAPI 应用入口。

Description:
    商品视觉生成系统的 API 服务入口，提供 RESTful API 和 WebSocket 接口。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.router import api_router
from src.api.service.redis_client import close_redis, get_redis
from src.config.settings import get_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动时初始化 Redis 连接，关闭时清理资源。
    """
    # 启动时
    logger.info("正在启动应用...")
    try:
        redis = await get_redis()
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.warning(f"Redis 连接失败: {e}，将使用内存存储")

    yield

    # 关闭时
    logger.info("正在关闭应用...")
    await close_redis()
    logger.info("应用已关闭")


# 创建 FastAPI 应用
settings = get_settings()
app = FastAPI(
    title="商品视觉生成器 API",
    description="基于 LangChain/LangGraph 的多 Agent 商品视觉生成系统",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理。

    Args:
        request: 请求对象。
        exc: 异常对象。

    Returns:
        错误响应。
    """
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.debug else None,
        },
    )


# 注册路由
app.include_router(api_router)


# 根路径
@app.get("/")
async def root() -> dict:
    """根路径。

    Returns:
        欢迎信息。
    """
    return {
        "message": "欢迎使用商品视觉生成器 API",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )