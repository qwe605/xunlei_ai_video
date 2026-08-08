from fastapi import APIRouter

from app.controllers import analysis_controller, health_controller, system_controller


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_controller.router)
api_router.include_router(analysis_controller.router)
api_router.include_router(system_controller.router)
"""集中注册 v1 路由，应用入口只需挂载一个 Router。"""
