from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class VideoRecord(TimestampMixin, Base):
    """视频主记录；后续云盘同步、本地导入和内置样例都会落到同一张表。"""

    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(260), nullable=False)
    media_type: Mapped[str] = mapped_column(String(30), default="other", nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    resolution: Mapped[str] = mapped_column(String(40), default="待识别", nullable=False)
    codec: Mapped[str] = mapped_column(String(80), default="待识别", nullable=False)
    language: Mapped[str] = mapped_column(String(40), default="待 AI 识别", nullable=False)
    saved_at: Mapped[str] = mapped_column(String(40), nullable=False)
    index_status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    index_level: Mapped[str] = mapped_column(String(10), default="L0", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle_origin: Mapped[str] = mapped_column(String(30), default="processing", nullable=False)
    asr_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    import_source: Mapped[str] = mapped_column(String(30), default="local", nullable=False)
    spoiler_protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    organize_hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    assets: Mapped[list["VideoAssetRecord"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="VideoAssetRecord.created_at",
    )
    subtitles: Mapped[list["SubtitleRecord"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="SubtitleRecord.created_at",
    )
    chapters: Mapped[list["ChapterRecord"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="ChapterRecord.sort_order",
    )
    tags: Mapped[list["VideoTagRecord"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="VideoTagRecord.name",
    )
    progress_entries: Mapped[list["UserProgressRecord"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )
    transcript_segments: Mapped[list["TranscriptSegmentRecord"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="TranscriptSegmentRecord.segment_index",
    )


class VideoAssetRecord(TimestampMixin, Base):
    """媒体、封面、后续转码产物的资产索引；文件本体只存路径，不塞进数据库。"""

    __tablename__ = "video_assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(80), nullable=True)

    video: Mapped[VideoRecord] = relationship(back_populates="assets")


class SubtitleRecord(TimestampMixin, Base):
    """字幕版本表；AI 字幕、用户修订字幕、原始外挂字幕都可并存。"""

    __tablename__ = "subtitles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    origin: Mapped[str] = mapped_column(String(30), nullable=False)
    language: Mapped[str] = mapped_column(String(40), nullable=False)
    asr_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vtt_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    video: Mapped[VideoRecord] = relationship(back_populates="subtitles")


class ChapterRecord(TimestampMixin, Base):
    """可跳转智能章节；章节文本和时间都必须可被用户核验。"""

    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="subtitle", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    spoiler_level: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    video: Mapped[VideoRecord] = relationship(back_populates="chapters")


class VideoTagRecord(TimestampMixin, Base):
    """标签单独建表，便于后续搜索和用户纠错。"""

    __tablename__ = "video_tags"
    __table_args__ = (UniqueConstraint("video_id", "name", name="uq_video_tag_name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)

    video: Mapped[VideoRecord] = relationship(back_populates="tags")


class UserProgressRecord(TimestampMixin, Base):
    """观看进度按用户保存，为后续多用户隔离提前留出边界。"""

    __tablename__ = "user_progress"
    __table_args__ = (UniqueConstraint("user_id", "video_id", name="uq_user_video_progress"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    last_position_seconds: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    completed_percent: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    video: Mapped[VideoRecord] = relationship(back_populates="progress_entries")


class TranscriptSegmentRecord(TimestampMixin, Base):
    """字幕检索分片；P2 搜索和 P3 问视频 RAG 会直接复用这些证据。"""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint("subtitle_id", "segment_index", name="uq_subtitle_segment_index"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    subtitle_id: Mapped[str] = mapped_column(ForeignKey("subtitles.id", ondelete="CASCADE"), index=True)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)

    video: Mapped[VideoRecord] = relationship(back_populates="transcript_segments")
