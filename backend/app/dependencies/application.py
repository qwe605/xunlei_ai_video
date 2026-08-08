from fastapi import Request

from app.config import Settings, get_settings
from app.services.analysis_jobs import AnalysisService


def get_app_settings() -> Settings:
    return get_settings()


def get_analysis_service(request: Request) -> AnalysisService:
    # Service 生命周期由 FastAPI lifespan 管理，所有请求复用同一模型和任务执行器。
    return request.app.state.analysis_service
"""FastAPI 依赖注入入口，Controller 不自行构造全局服务。"""
