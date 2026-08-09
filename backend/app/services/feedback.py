from app.database.repositories import FeedbackRepository, VideoRepository
from app.database.session import session_scope
from app.schemas import FeedbackCreate, FeedbackRead, FeedbackSummary


class FeedbackService:
    """AI 反馈业务层；当前只可靠保存，后续再接入重排、纠错任务和指标面板。"""

    def create_feedback(self, payload: FeedbackCreate) -> FeedbackRead:
        with session_scope() as session:
            if payload.video_id:
                video_owner = VideoRepository(session).get_owner_id(payload.video_id)
                if video_owner is not None and video_owner != payload.user_id:
                    raise LookupError("视频不存在或无权反馈")
            return FeedbackRepository(session).create(payload)

    def summary(self, user_id: str = "demo-local") -> FeedbackSummary:
        with session_scope() as session:
            return FeedbackRepository(session).summary(user_id)
