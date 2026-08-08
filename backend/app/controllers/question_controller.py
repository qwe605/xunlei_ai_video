from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_question_service
from app.schemas import VideoQuestionRequest, VideoQuestionResponse
from app.services.questions import QuestionService


router = APIRouter(prefix="/videos", tags=["问视频"])


@router.post("/{video_id}/questions", response_model=VideoQuestionResponse)
def answer_video_question(
    video_id: str,
    payload: VideoQuestionRequest,
    service: Annotated[QuestionService, Depends(get_question_service)],
) -> VideoQuestionResponse:
    try:
        return service.answer_video_question(video_id=video_id, payload=payload)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
