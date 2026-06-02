"""查询 API 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import query_conversations, query_execute, query_stream

router = APIRouter()
router.include_router(query_conversations.router)
router.include_router(query_execute.router)
router.include_router(query_stream.router)
