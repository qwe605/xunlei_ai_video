from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from app.dependencies import get_library_service
from app.schemas import (
    ProgressUpdate,
    ProgressUpdateResponse,
    VideoDeleteResponse,
    VideoDetail,
    VideoListItem,
)
from app.services.library import LibraryService


router = APIRouter(prefix="/videos", tags=["片库"])


@router.get("", response_model=list[VideoListItem])
def list_videos(
    service: Annotated[LibraryService, Depends(get_library_service)],
    owner_id: str = "demo-local",
) -> list[VideoListItem]:
    return service.list_videos(owner_id=owner_id)


@router.get("/{video_id}", response_model=VideoDetail)
def get_video(
    video_id: str,
    service: Annotated[LibraryService, Depends(get_library_service)],
    owner_id: str = "demo-local",
) -> VideoDetail:
    video = service.get_video(video_id=video_id, owner_id=owner_id)
    if video is None:
        raise HTTPException(status_code=404, detail="视频不存在或无权访问")
    return video


@router.patch("/{video_id}/progress", response_model=ProgressUpdateResponse)
def update_progress(
    video_id: str,
    payload: ProgressUpdate,
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> ProgressUpdateResponse:
    try:
        return service.update_progress(
            video_id=video_id,
            user_id=payload.user_id,
            position_seconds=payload.position_seconds,
            duration_seconds=payload.duration_seconds,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{video_id}/media")
def get_video_media(
    video_id: str,
    service: Annotated[LibraryService, Depends(get_library_service)],
    owner_id: str = "demo-local",
) -> FileResponse:
    try:
        resolved = service.get_asset_path(
            video_id=video_id,
            asset_type="source",
            owner_id=owner_id,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="无权访问该视频资产") from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if resolved is None:
        raise HTTPException(status_code=404, detail="视频不存在或无权访问")
    path, asset = resolved
    return FileResponse(path, media_type=asset.mime_type, filename=path.name)


@router.delete("/{video_id}", response_model=VideoDeleteResponse)
def delete_video(
    video_id: str,
    service: Annotated[LibraryService, Depends(get_library_service)],
    owner_id: str = "demo-local",
) -> VideoDeleteResponse:
    try:
        return service.delete_video(video_id=video_id, owner_id=owner_id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="无权删除该视频资产") from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{video_id}/assets/poster")
def get_video_poster(
    video_id: str,
    service: Annotated[LibraryService, Depends(get_library_service)],
    owner_id: str = "demo-local",
) -> FileResponse:
    try:
        resolved = service.get_asset_path(
            video_id=video_id,
            asset_type="poster",
            owner_id=owner_id,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="无权访问该视频资产") from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if resolved is None:
        raise HTTPException(status_code=404, detail="封面不存在或尚未生成")
    path, asset = resolved
    return FileResponse(path, media_type=asset.mime_type, filename=path.name)


@router.get("/{video_id}/subtitles/active")
def get_active_subtitle(
    video_id: str,
    service: Annotated[LibraryService, Depends(get_library_service)],
    owner_id: str = "demo-local",
) -> Response:
    subtitle = service.get_active_subtitle(video_id=video_id, owner_id=owner_id)
    if subtitle is None:
        raise HTTPException(status_code=404, detail="字幕不存在或尚未生成")
    return Response(content=subtitle.vtt_text, media_type="text/vtt; charset=utf-8")
