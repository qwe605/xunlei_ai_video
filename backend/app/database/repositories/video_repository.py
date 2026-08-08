import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.video_library import (
    ChapterRecord,
    SubtitleRecord,
    TranscriptSegmentRecord,
    UserProgressRecord,
    VideoAssetRecord,
    VideoRecord,
    VideoTagRecord,
)
from app.schemas import (
    AnalysisResult,
    ChapterResult,
    VideoAssetRead,
    ProgressUpdateResponse,
    UserProgressRead,
    VideoDetail,
    VideoListItem,
)


def _new_id() -> str:
    return uuid.uuid4().hex


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _relative_storage_path(path: Path) -> str:
    # 资产路径统一存 POSIX 风格相对路径，避免 Windows 绝对路径进入 API 和数据库。
    return path.as_posix().lstrip("/")


def _parse_vtt_segments(vtt_text: str) -> list[tuple[float, float, str]]:
    """解析后端生成的 WebVTT，作为后续搜索和问视频的可核验证据分片。"""

    def parse_timestamp(value: str) -> float:
        hours, minutes, rest = value.split(":")
        seconds, millis = rest.split(".")
        return (
            int(hours) * 3600
            + int(minutes) * 60
            + int(seconds)
            + int(millis[:3].ljust(3, "0")) / 1000
        )

    segments: list[tuple[float, float, str]] = []
    lines = [line.strip() for line in vtt_text.splitlines()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if "-->" not in line:
            index += 1
            continue
        raw_start, raw_end = [part.strip() for part in line.split("-->", 1)]
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index]:
            text_lines.append(lines[index])
            index += 1
        text = " ".join(text_lines).strip()
        if text:
            segments.append((parse_timestamp(raw_start), parse_timestamp(raw_end), text))
        index += 1
    return segments


class VideoRepository:
    """真实片库的数据访问层；Service 只编排业务，不散落 ORM 查询。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_owner(self, owner_id: str = "demo-local") -> list[VideoListItem]:
        statement = (
            select(VideoRecord)
            .where(VideoRecord.owner_id == owner_id)
            .options(
                selectinload(VideoRecord.assets),
                selectinload(VideoRecord.tags),
                selectinload(VideoRecord.progress_entries),
            )
            .order_by(VideoRecord.created_at.desc())
        )
        return [self._to_list_item(record, owner_id) for record in self._session.scalars(statement)]

    def get_detail(self, video_id: str, owner_id: str = "demo-local") -> VideoDetail | None:
        record = self._load_video(video_id, owner_id)
        return self._to_detail(record, owner_id) if record else None

    def create_placeholder(
        self,
        *,
        video_id: str,
        owner_id: str,
        title: str,
        original_filename: str,
        duration_seconds: float,
        resolution: str = "待识别",
        codec: str = "待识别",
        language: str = "待 AI 识别",
        media_type: str = "other",
        import_source: str = "local",
        asset_path: str | None = None,
        asset_mime_type: str | None = None,
        asset_size_bytes: int = 0,
        width: int | None = None,
        height: int | None = None,
        checksum: str | None = None,
        poster_path: str | None = None,
        poster_mime_type: str | None = None,
        poster_size_bytes: int = 0,
    ) -> VideoDetail:
        existing = self._load_video(video_id, owner_id)
        if existing is not None:
            return self._to_detail(existing, owner_id)

        now = datetime.now(timezone.utc).isoformat()
        record = VideoRecord(
            id=video_id,
            owner_id=owner_id,
            title=title,
            original_filename=original_filename,
            media_type=media_type,
            duration_seconds=duration_seconds,
            resolution=resolution,
            codec=codec,
            language=language,
            saved_at=now,
            index_status="pending",
            index_level="L0",
            confidence=1,
            short_description="视频已进入片库，等待 AI 整理。",
            summary="视频资产已持久化，AI 字幕、摘要和章节生成后会写回片库。",
            subtitle_origin="processing",
            import_source=import_source,
            spoiler_protected=False,
            organize_hint="等待 AI 整理队列",
        )
        self._session.add(record)
        if asset_path and asset_mime_type:
            record.assets.append(
                VideoAssetRecord(
                    id=_new_id(),
                    video_id=video_id,
                    asset_type="source",
                    storage_path=_relative_storage_path(Path(asset_path)),
                    mime_type=asset_mime_type,
                    size_bytes=asset_size_bytes,
                    width=width,
                    height=height,
                    checksum=checksum,
                )
            )
        if poster_path and poster_mime_type:
            record.assets.append(
                VideoAssetRecord(
                    id=_new_id(),
                    video_id=video_id,
                    asset_type="poster",
                    storage_path=_relative_storage_path(Path(poster_path)),
                    mime_type=poster_mime_type,
                    size_bytes=poster_size_bytes,
                    width=width,
                    height=height,
                    checksum=None,
                )
            )
        self._session.flush()
        return self._to_detail(record, owner_id)

    def get_asset(self, video_id: str, owner_id: str, asset_type: str) -> VideoAssetRead | None:
        record = self._load_video(video_id, owner_id)
        if record is None:
            return None
        asset = next((item for item in record.assets if item.asset_type == asset_type), None)
        return VideoAssetRead.model_validate(asset) if asset else None

    def get_active_subtitle(self, video_id: str, owner_id: str) -> SubtitleRecord | None:
        record = self._load_video(video_id, owner_id)
        if record is None:
            return None
        return next((item for item in record.subtitles if item.is_active), None)

    def delete_video(self, video_id: str, owner_id: str) -> list[str] | None:
        record = self._load_video(video_id, owner_id)
        if record is None:
            return None
        asset_paths = [asset.storage_path for asset in record.assets]
        self._session.delete(record)
        self._session.flush()
        return asset_paths

    def update_progress(
        self,
        *,
        video_id: str,
        user_id: str,
        position_seconds: float,
        duration_seconds: float,
    ) -> ProgressUpdateResponse:
        record = self._session.scalar(
            select(UserProgressRecord).where(
                UserProgressRecord.user_id == user_id,
                UserProgressRecord.video_id == video_id,
            )
        )
        completed_percent = min(1.0, max(0.0, position_seconds / max(duration_seconds, 1)))
        if record is None:
            record = UserProgressRecord(
                id=_new_id(),
                user_id=user_id,
                video_id=video_id,
                last_position_seconds=position_seconds,
                completed_percent=completed_percent,
            )
            self._session.add(record)
        else:
            record.last_position_seconds = position_seconds
            record.completed_percent = completed_percent
        self._session.flush()
        return ProgressUpdateResponse(
            video_id=video_id,
            progress=UserProgressRead(
                last_position_seconds=record.last_position_seconds,
                completed_percent=record.completed_percent,
            ),
        )

    def apply_analysis_result(
        self,
        *,
        video_id: str,
        owner_id: str,
        result: AnalysisResult,
    ) -> VideoDetail | None:
        record = self._load_video(video_id, owner_id)
        if record is None:
            return None

        record.language = result.language
        record.index_status = "ready"
        record.index_level = "L2"
        record.confidence = result.confidence
        record.short_description = result.short_description
        record.summary = result.summary
        record.subtitle_origin = "ai-generated"
        record.asr_model = result.asr_model
        record.organize_hint = f"AI 已生成字幕、摘要和 {len(result.chapters)} 个章节"

        record.tags[:] = [
            VideoTagRecord(id=_new_id(), video_id=video_id, name=tag)
            for tag in dict.fromkeys(result.tags)
        ]
        record.chapters[:] = [
            self._chapter_record(video_id, chapter, index)
            for index, chapter in enumerate(result.chapters)
        ]
        subtitle = SubtitleRecord(
            id=_new_id(),
            video_id=video_id,
            origin="ai-generated",
            language=result.language,
            asr_model=result.asr_model,
            vtt_text=result.subtitles_vtt,
            confidence=result.confidence,
            is_active=True,
        )
        record.subtitles[:] = [subtitle]
        record.transcript_segments[:] = [
            TranscriptSegmentRecord(
                id=_new_id(),
                video_id=video_id,
                subtitle_id=subtitle.id,
                segment_index=index,
                start_seconds=start,
                end_seconds=end,
                text=text,
                normalized_text=_normalize_text(text),
            )
            for index, (start, end, text) in enumerate(_parse_vtt_segments(result.subtitles_vtt))
        ]
        self._session.flush()
        return self._to_detail(record, owner_id)

    def _load_video(self, video_id: str, owner_id: str) -> VideoRecord | None:
        return self._session.scalar(
            select(VideoRecord)
            .where(VideoRecord.id == video_id, VideoRecord.owner_id == owner_id)
            .options(
                selectinload(VideoRecord.assets),
                selectinload(VideoRecord.subtitles),
                selectinload(VideoRecord.chapters),
                selectinload(VideoRecord.tags),
                selectinload(VideoRecord.progress_entries),
                selectinload(VideoRecord.transcript_segments),
            )
        )

    @staticmethod
    def _chapter_record(video_id: str, chapter: ChapterResult, index: int) -> ChapterRecord:
        return ChapterRecord(
            id=chapter.id,
            video_id=video_id,
            title=chapter.title,
            summary=chapter.summary,
            start_seconds=chapter.start_seconds,
            end_seconds=chapter.end_seconds,
            source=chapter.source,
            confidence=chapter.confidence,
            spoiler_level=chapter.spoiler_level,
            sort_order=index,
        )

    @staticmethod
    def _progress(record: VideoRecord, owner_id: str) -> UserProgressRead | None:
        progress = next(
            (item for item in record.progress_entries if item.user_id == owner_id),
            None,
        )
        if progress is None:
            return None
        return UserProgressRead(
            last_position_seconds=progress.last_position_seconds,
            completed_percent=progress.completed_percent,
        )

    @classmethod
    def _to_list_item(cls, record: VideoRecord, owner_id: str) -> VideoListItem:
        return VideoListItem(
            id=record.id,
            title=record.title,
            original_filename=record.original_filename,
            media_type=record.media_type,
            duration_seconds=record.duration_seconds,
            resolution=record.resolution,
            codec=record.codec,
            language=record.language,
            saved_at=record.saved_at,
            index_status=record.index_status,
            index_level=record.index_level,
            confidence=record.confidence,
            short_description=record.short_description,
            summary=record.summary,
            subtitle_origin=record.subtitle_origin,
            asr_model=record.asr_model,
            import_source=record.import_source,
            spoiler_protected=record.spoiler_protected,
            organize_hint=record.organize_hint,
            has_poster=any(asset.asset_type == "poster" for asset in record.assets),
            tags=[tag.name for tag in record.tags],
            progress=cls._progress(record, owner_id),
        )

    @classmethod
    def _to_detail(cls, record: VideoRecord, owner_id: str) -> VideoDetail:
        base = cls._to_list_item(record, owner_id).model_dump()
        return VideoDetail.model_validate(
            {
                **base,
                "assets": record.assets,
                "subtitles": record.subtitles,
                "chapters": record.chapters,
                "transcript_segments": record.transcript_segments,
            }
        )
