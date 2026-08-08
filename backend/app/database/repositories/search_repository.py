from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.video_library import VideoRecord


@dataclass(frozen=True)
class SearchCorpusVideo:
    """后端检索使用的只读视频语料；Repository 负责 ORM 查询，Service 只做排序编排。"""

    record: VideoRecord


class SearchRepository:
    """搜索数据访问层；复杂召回统一放在这里，Controller 和 Service 不散落 SQL。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_searchable_videos(self, owner_id: str) -> list[SearchCorpusVideo]:
        statement = (
            select(VideoRecord)
            .where(VideoRecord.owner_id == owner_id)
            .options(
                selectinload(VideoRecord.tags),
                selectinload(VideoRecord.chapters),
                selectinload(VideoRecord.transcript_segments),
            )
            .order_by(VideoRecord.created_at.desc())
        )
        return [SearchCorpusVideo(record=record) for record in self._session.scalars(statement)]
