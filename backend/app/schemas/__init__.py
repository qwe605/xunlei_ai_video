from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class JobStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnalysisMode(StrEnum):
    fast = "fast"
    precise = "precise"


class ChapterResult(ApiModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=80)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    summary: str = Field(min_length=1, max_length=500)
    source: str = "subtitle"
    confidence: float = Field(ge=0, le=1)
    spoiler_level: str = "none"


class AnalysisResult(ApiModel):
    language: str = Field(min_length=1, max_length=40)
    confidence: float = Field(ge=0, le=1)
    short_description: str = Field(min_length=1, max_length=220)
    summary: str = Field(min_length=1, max_length=1200)
    tags: list[str] = Field(min_length=1, max_length=8)
    subtitles_vtt: str = Field(min_length=20)
    asr_model: str = Field(min_length=1, max_length=120)
    subtitle_correction_count: int = Field(default=0, ge=0, le=100)
    chapters: list[ChapterResult] = Field(min_length=1, max_length=24)


class AnalysisJob(ApiModel):
    id: str
    video_id: str
    status: JobStatus
    stage: str
    progress: int = Field(ge=0, le=100)
    detail: str
    result: AnalysisResult | None = None
    error_code: str | None = None


class HealthResponse(ApiModel):
    status: str
    model: str
    device: str
    version: str
    precise_model: str
    precise_model_ready: bool


class MagnetOpenRequest(ApiModel):
    magnet: Annotated[str, Field(min_length=50, max_length=4096)]


class MagnetOpenResponse(ApiModel):
    status: str
    detail: str


class VideoAssetRead(ApiModel):
    id: str
    asset_type: str
    storage_path: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    checksum: str | None = None


class SubtitleRead(ApiModel):
    id: str
    origin: str
    language: str
    asr_model: str | None = None
    vtt_text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    is_active: bool


class VideoTagRead(ApiModel):
    id: str
    name: str = Field(min_length=1, max_length=40)


class UserProgressRead(ApiModel):
    last_position_seconds: float = Field(ge=0)
    completed_percent: float = Field(ge=0, le=1)


class TranscriptSegmentRead(ApiModel):
    id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    segment_index: int = Field(ge=0)


class VideoListItem(ApiModel):
    id: str
    title: str
    original_filename: str
    media_type: str
    duration_seconds: float
    resolution: str
    codec: str
    language: str
    saved_at: str
    index_status: str
    index_level: str
    confidence: float = Field(ge=0, le=1)
    short_description: str
    summary: str
    subtitle_origin: str
    asr_model: str | None = None
    import_source: str
    spoiler_protected: bool
    organize_hint: str | None = None
    tags: list[str] = Field(default_factory=list)
    progress: UserProgressRead | None = None


class VideoDetail(VideoListItem):
    assets: list[VideoAssetRead] = Field(default_factory=list)
    subtitles: list[SubtitleRead] = Field(default_factory=list)
    chapters: list[ChapterResult] = Field(default_factory=list)
    transcript_segments: list[TranscriptSegmentRead] = Field(default_factory=list)


class ProgressUpdate(ApiModel):
    user_id: str = Field(default="demo-local", min_length=1, max_length=120)
    position_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0, le=86_400)


class ProgressUpdateResponse(ApiModel):
    video_id: str
    progress: UserProgressRead
