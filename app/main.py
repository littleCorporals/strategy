from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.admin.routes import router as admin_router
from app.api.routes.market import router as market_router
from app.core.config import STATIC_DIR


def _allowed_origins() -> list[str]:
    configured = os.getenv("APP_ALLOWED_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tushare 交易决策台",
        description="通过 Tushare SDK 代理查询行情，用于本地筛选、复盘和交易计划。",
        version="0.2.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(market_router)
    app.include_router(admin_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(content={"detail": exc.detail}, status_code=exc.status_code)

    return app


app = create_app()
