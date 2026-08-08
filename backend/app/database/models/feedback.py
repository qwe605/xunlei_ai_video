from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AiFeedbackRecord(TimestampMixin, Base):
    """AI 结果反馈表；先沉淀用户纠错信号，后续再驱动重排和修正任务。"""

    __tablename__ = "ai_feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    video_id: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    target_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
