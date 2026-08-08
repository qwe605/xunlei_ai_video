from typing import Annotated

from fastapi import APIRouter, Body, HTTPException

from app.integrations.system_links import MagnetOpenError, open_magnet_in_system
from app.schemas import MagnetOpenRequest, MagnetOpenResponse


router = APIRouter(prefix="/system", tags=["系统集成"])


@router.post("/magnet", response_model=MagnetOpenResponse)
def open_magnet(
    payload: Annotated[MagnetOpenRequest, Body()],
) -> MagnetOpenResponse:
    try:
        open_magnet_in_system(payload.magnet)
    except MagnetOpenError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return MagnetOpenResponse(status="opened", detail="已交给迅雷客户端处理")
"""操作系统能力接口，目前只暴露经过格式校验的磁力协议调用。"""
