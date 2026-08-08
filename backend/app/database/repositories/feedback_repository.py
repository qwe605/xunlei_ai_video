import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.feedback import AiFeedbackRecord
from app.schemas import FeedbackCreate, FeedbackRead, FeedbackSummary


def _new_id() -> str:
    return uuid.uuid4().hex


class FeedbackRepository:
    """AI 反馈数据访问层；反馈写入和统计集中在 Repository，便于后续影响排序。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, payload: FeedbackCreate) -> FeedbackRead:
        record = AiFeedbackRecord(
            id=_new_id(),
            user_id=payload.user_id,
            video_id=payload.video_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            feedback_type=payload.feedback_type,
            content=payload.content,
            status="received",
        )
        self._session.add(record)
        self._session.flush()
        return FeedbackRead.model_validate(record)

    def summary(self, user_id: str) -> FeedbackSummary:
        statement = select(
            AiFeedbackRecord.feedback_type,
            func.count(AiFeedbackRecord.id),
        ).where(AiFeedbackRecord.user_id == user_id).group_by(AiFeedbackRecord.feedback_type)
        counts = {feedback_type: count for feedback_type, count in self._session.execute(statement)}
        return FeedbackSummary(
            user_id=user_id,
            total=sum(counts.values()),
            helpful=counts.get("helpful", 0),
            not_relevant=counts.get("not_relevant", 0),
            correction=counts.get("correction", 0),
        )
