from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user, get_search_service
from app.schemas import SearchRequest, SearchResponse, UserRead
from app.services.search import SearchService


router = APIRouter(prefix="/search", tags=["搜索"])


@router.post("", response_model=SearchResponse)
def search_videos(
    payload: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
    user: Annotated[UserRead, Depends(get_current_user)],
) -> SearchResponse:
    # 请求结构已由 Pydantic 在边界校验；这里仅负责 HTTP 语义和 Service 调用。
    return service.search(payload, user.id)
