from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.database.models import (
    AiFeedbackRecord,
    AnalysisJobRecord,
    AuthSessionRecord,
    UserProgressRecord,
    UserRecord,
    VideoRecord,
)


class AuthRepository:
    """用户、会话和旧数据归属迁移的数据访问入口。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def count_users(self) -> int:
        return int(self._session.scalar(select(func.count(UserRecord.id))) or 0)

    def get_user_by_email(self, email: str) -> UserRecord | None:
        return self._session.scalar(select(UserRecord).where(UserRecord.email == email))

    def create_user(self, record: UserRecord) -> UserRecord:
        self._session.add(record)
        self._session.flush()
        return record

    def create_session(self, record: AuthSessionRecord) -> None:
        self._session.add(record)
        self._session.flush()

    def get_session_user(self, token_hash: str) -> UserRecord | None:
        statement = (
            select(AuthSessionRecord)
            .options(joinedload(AuthSessionRecord.user))
            .where(AuthSessionRecord.token_hash == token_hash)
        )
        record = self._session.scalar(statement)
        if record is None:
            return None
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            self._session.delete(record)
            self._session.flush()
            return None
        return record.user

    def delete_session(self, token_hash: str) -> None:
        record = self._session.scalar(
            select(AuthSessionRecord).where(AuthSessionRecord.token_hash == token_hash)
        )
        if record is not None:
            self._session.delete(record)
            self._session.flush()

    def adopt_legacy_owner(self, user_id: str) -> None:
        """首个服务端账号接管升级前 demo-local 的私有数据。"""

        for model, field in (
            (VideoRecord, VideoRecord.owner_id),
            (AnalysisJobRecord, AnalysisJobRecord.owner_id),
            (UserProgressRecord, UserProgressRecord.user_id),
            (AiFeedbackRecord, AiFeedbackRecord.user_id),
        ):
            self._session.execute(
                update(model).where(field == "demo-local").values({field.key: user_id})
            )
        self._session.flush()
