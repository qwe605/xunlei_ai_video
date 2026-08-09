from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class UserRecord(TimestampMixin, Base):
    """服务端用户实体；密码只保存带盐的 scrypt 派生值。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(40), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)

    sessions: Mapped[list["AuthSessionRecord"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class AuthSessionRecord(TimestampMixin, Base):
    """不透明登录会话；数据库仅保存令牌哈希，原始令牌只进入 HttpOnly Cookie。"""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    user: Mapped[UserRecord] = relationship(back_populates="sessions")
