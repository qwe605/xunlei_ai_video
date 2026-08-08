from fastapi import Request

from app.config import Settings, get_settings
from app.services.analysis_jobs import AnalysisService
from app.services.feedback import FeedbackService
from app.services.library import LibraryService
from app.services.questions import QuestionService
from app.services.search import SearchService


def get_app_settings() -> Settings:
    return get_settings()


def get_analysis_service(request: Request) -> AnalysisService:
    # Service 生命周期由 FastAPI lifespan 管理，所有请求复用同一模型和任务执行器。
    return request.app.state.analysis_service


def get_library_service(request: Request) -> LibraryService:
    return request.app.state.library_service


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search_service


def get_question_service(request: Request) -> QuestionService:
    return request.app.state.question_service


def get_feedback_service(request: Request) -> FeedbackService:
    return request.app.state.feedback_service
"""FastAPI 依赖注入入口，Controller 不自行构造全局服务。"""
