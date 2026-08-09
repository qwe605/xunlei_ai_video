import hmac
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config import Settings
from app.dependencies import get_analysis_service, get_current_user
from app.dependencies import get_app_settings
from app.integrations.asr import asr_audio_access_token
from app.schemas import AnalysisJob, AnalysisMode, UserRead
from app.services.analysis_jobs import AnalysisService, UploadValidationError


router = APIRouter(prefix="/analyses", tags=["视频分析"])


@router.post("", response_model=AnalysisJob, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
    user: Annotated[UserRead, Depends(get_current_user)],
    video: UploadFile = File(),
    poster: UploadFile | None = File(default=None),
    video_id: str = Form(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$"),
    duration_seconds: float = Form(gt=0, le=86_400),
    analysis_mode: AnalysisMode = Form(default=AnalysisMode.fast),
    title: str | None = Form(default=None, max_length=160),
    resolution: str = Form(default="待识别", max_length=40),
    codec: str = Form(default="待识别", max_length=80),
    width: int | None = Form(default=None, ge=0, le=16_384),
    height: int | None = Form(default=None, ge=0, le=16_384),
) -> AnalysisJob:
    # Controller 不保存文件、不接触 ORM，上传生命周期由 Service 统一负责。
    try:
        return await service.create_from_upload(
            video=video,
            poster=poster,
            video_id=video_id,
            duration_seconds=duration_seconds,
            analysis_mode=analysis_mode.value,
            owner_id=user.id,
            title=title,
            resolution=resolution,
            codec=codec,
            width=width,
            height=height,
        )
    except UploadValidationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/{job_id}", response_model=AnalysisJob)
def get_analysis(
    job_id: str,
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
    user: Annotated[UserRead, Depends(get_current_user)],
) -> AnalysisJob:
    job = service.get(job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="分析任务不存在或已过期")
    return job


@router.get("/media/{video_id}/asr-audio")
def get_analysis_audio_for_asr(
    video_id: str,
    settings: Annotated[Settings, Depends(get_app_settings)],
    token: str = "",
) -> FileResponse:
    # 仅暴露后端为 ASR API 生成的临时 WAV，避免把任意本地路径变成公开下载入口。
    if not re.fullmatch(r"[A-Za-z0-9._-]+", video_id):
        raise HTTPException(status_code=404, detail="音频不存在")
    expected_token = asr_audio_access_token(video_id, settings)
    if not expected_token or not hmac.compare_digest(token, expected_token):
        raise HTTPException(status_code=404, detail="音频不存在")
    audio_path = settings.media_root / video_id / "asr-api.wav"
    try:
        audio_path.relative_to(settings.media_root)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="音频不存在") from error
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="音频不存在")
    return FileResponse(Path(audio_path), media_type="audio/wav", filename="asr-api.wav")
"""视频分析 HTTP 接口：校验请求、映射状态码并调用业务 Service。"""
