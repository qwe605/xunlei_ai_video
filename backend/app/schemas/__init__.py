from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


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
