from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_feedback_service
from app.schemas import FeedbackCreate, FeedbackRead, FeedbackSubmission, FeedbackSummary, UserRead
from app.services.feedback import FeedbackService


router = APIRouter(prefix="/feedback", tags=["反馈"])


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: FeedbackSubmission,
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
    user: Annotated[UserRead, Depends(get_current_user)],
) -> FeedbackRead:
    try:
        return service.create_feedback(FeedbackCreate(user_id=user.id, **payload.model_dump()))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/summary", response_model=FeedbackSummary)
def feedback_summary(
    service: Annotated[FeedbackService, Depends(get_feedback_service)],
    user: Annotated[UserRead, Depends(get_current_user)],
) -> FeedbackSummary:
    return service.summary(user.id)
