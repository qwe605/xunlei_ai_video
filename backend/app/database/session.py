from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.base import Base
from app.database.migrations import migrate_existing_database


settings = get_settings()
if settings.database_url.startswith("sqlite:///"):
    # SQLite 不会自动创建父目录，启动前先保证数据目录存在。
    Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(
        parents=True, exist_ok=True
    )

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_database() -> None:
    # 导入实体后 SQLAlchemy 才能把全部表注册到 metadata。
    import app.database.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_existing_database(engine)


def get_db() -> Generator[Session, None, None]:
    """供 FastAPI Depends 使用的请求级数据库会话。"""
    with SessionLocal() as session:
        yield session


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """供后台线程使用；成功提交，任何异常都回滚并继续抛出。"""
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
"""集中创建 Engine、Session，并定义提交和回滚边界。"""
