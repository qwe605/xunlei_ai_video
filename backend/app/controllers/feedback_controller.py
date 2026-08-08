from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import get_feedback_service
from app.schemas import FeedbackCreate, FeedbackRead, FeedbackSummary
from app.services.feedback import FeedbackService


router = APIRouter(prefix="/feedback", tags=["反馈"])


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: FeedbackCreate,
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
) -> FeedbackRead:
    return service.create_feedback(payload)


@router.get("/summary", response_model=FeedbackSummary)
def feedback_summary(
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
    user_id: str = "demo-local",
) -> FeedbackSummary:
    return service.summary(user_id)
