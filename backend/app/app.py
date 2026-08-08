from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.controllers import api_router
from app.database.session import init_database
from app.services.analysis_jobs import AnalysisService
from app.services.feedback import FeedbackService
from app.services.library import LibraryService
from app.services.questions import QuestionService
from app.services.search import SearchService


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # 先建表再构造 Service，确保后台预热线程启动时数据库已经可用。
    init_database()
    service = AnalysisService()
    application.state.analysis_service = service
    application.state.library_service = LibraryService()
    application.state.search_service = SearchService()
    application.state.question_service = QuestionService()
    application.state.feedback_service = FeedbackService()
    try:
        yield
    finally:
        # 不强制终止正在清理临时文件的线程，关闭后由进程完成剩余回收。
        service.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()
