from fastapi import APIRouter

from app.controllers import (
    analysis_controller,
    feedback_controller,
    health_controller,
    library_controller,
    question_controller,
    search_controller,
    system_controller,
)


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_controller.router)
api_router.include_router(library_controller.router)
api_router.include_router(analysis_controller.router)
api_router.include_router(system_controller.router)
api_router.include_router(search_controller.router)
api_router.include_router(question_controller.router)
api_router.include_router(feedback_controller.router)
"""集中注册 v1 路由，应用入口只需挂载一个 Router。"""
