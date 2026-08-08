from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_app_settings
from app.schemas import HealthResponse
from app.integrations.asr import PRECISE_ASR_MODEL, precise_model_ready
from app.services.analysis_jobs import MODEL_DEVICE, MODEL_NAME


router = APIRouter(tags=["系统"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_app_settings)]) -> HealthResponse:
    api_asr_ready = bool(
        settings.public_base_url
        and (settings.volc_asr_api_key or (settings.volc_asr_app_id and settings.volc_asr_access_token))
    )
    return HealthResponse(
        status="ok",
        model=MODEL_NAME,
        device=MODEL_DEVICE,
        version=settings.app_version,
        precise_model=f"faster-whisper:{PRECISE_ASR_MODEL}",
        precise_model_ready=precise_model_ready(),
        api_asr_ready=api_asr_ready,
    )
"""健康检查接口，用于 Nginx、部署平台和前端启动探测。"""
