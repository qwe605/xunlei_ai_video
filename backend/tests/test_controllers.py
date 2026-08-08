import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.controllers import api_router
from app.schemas import (
    AnalysisJob,
    JobStatus,
    ProgressUpdateResponse,
    UserProgressRead,
    SubtitleRead,
    VideoAssetRead,
    VideoDeleteResponse,
    VideoDetail,
    VideoListItem,
)


class FakeAnalysisService:
    def __init__(self) -> None:
        self.create_arguments: dict[str, object] = {}

    async def create_from_upload(self, **arguments: object) -> AnalysisJob:
        self.create_arguments = arguments
        return AnalysisJob(
            id="job-api",
            video_id="video-api",
            status=JobStatus.queued,
            stage="等待模型",
            progress=5,
            detail="已进入队列",
        )

    def get(self, job_id: str) -> AnalysisJob | None:
        if job_id != "job-api":
            return None
        return AnalysisJob(
            id=job_id,
            video_id="video-api",
            status=JobStatus.processing,
            stage="识别语音",
            progress=25,
            detail="正在识别",
        )


class FakeLibraryService:
    def __init__(self) -> None:
        self._tempdir = TemporaryDirectory()
        self.media_path = Path(self._tempdir.name) / "video-api.mp4"
        self.poster_path = Path(self._tempdir.name) / "poster.jpg"
        self.media_path.write_bytes(b"fake-media")
        self.poster_path.write_bytes(b"fake-poster")

    def close(self) -> None:
        self._tempdir.cleanup()

    def list_videos(self, owner_id: str = "demo-local") -> list[VideoListItem]:
        return [
            VideoListItem(
                id="video-api",
                title="接口样例",
                original_filename="api.mp4",
                media_type="other",
                duration_seconds=120,
                resolution="1280 × 720",
                codec="本地 MP4",
                language="中文（简体）",
                saved_at="2026-08-08T00:00:00+00:00",
                index_status="ready",
                index_level="L2",
                confidence=0.95,
                short_description="接口测试视频",
                summary="用于测试片库接口。",
                subtitle_origin="ai-generated",
                asr_model="faster-whisper:large-v3",
                import_source="local",
                spoiler_protected=False,
                organize_hint="AI 已整理",
                has_poster=True,
                tags=["测试"],
                progress=None,
            )
        ]

    def get_video(self, video_id: str, owner_id: str = "demo-local") -> VideoDetail | None:
        if video_id != "video-api":
            return None
        return VideoDetail.model_validate(self.list_videos(owner_id)[0].model_dump())

    def update_progress(self, **arguments: object) -> ProgressUpdateResponse:
        if arguments["video_id"] != "video-api":
            raise LookupError("视频不存在或无权访问")
        return ProgressUpdateResponse(
            video_id="video-api",
            progress=UserProgressRead(last_position_seconds=42, completed_percent=0.35),
        )

    def get_asset_path(self, **arguments: object) -> tuple[Path, VideoAssetRead] | None:
        if arguments["video_id"] != "video-api":
            return None
        if arguments["asset_type"] == "poster":
            return (
                self.poster_path,
                VideoAssetRead(
                    id="poster-api",
                    asset_type="poster",
                    storage_path="video-api/poster.jpg",
                    mime_type="image/jpeg",
                    size_bytes=self.poster_path.stat().st_size,
                ),
            )
        return (
            self.media_path,
            VideoAssetRead(
                id="asset-api",
                asset_type="source",
                storage_path="video-api/source.mp4",
                mime_type="video/mp4",
                size_bytes=self.media_path.stat().st_size,
            ),
        )

    def get_active_subtitle(self, **arguments: object) -> SubtitleRead | None:
        if arguments["video_id"] != "video-api":
            return None
        return SubtitleRead(
            id="subtitle-api",
            origin="ai-generated",
            language="中文（简体）",
            asr_model="faster-whisper:large-v3",
            vtt_text="WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n字幕测试",
            confidence=0.96,
            is_active=True,
        )

    def delete_video(self, **arguments: object) -> VideoDeleteResponse:
        if arguments["video_id"] != "video-api":
            raise LookupError("视频不存在或无权访问")
        return VideoDeleteResponse(video_id="video-api", deleted_assets=2)


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        application = FastAPI()
        application.include_router(api_router)
        self.service = FakeAnalysisService()
        self.library_service = FakeLibraryService()
        application.state.analysis_service = self.service
        application.state.library_service = self.library_service
        self.client = TestClient(application)

    def tearDown(self) -> None:
        self.library_service.close()

    def test_health_and_missing_job_use_http_semantics(self) -> None:
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["version"], "2.0.0")
        self.assertIn("preciseModelReady", health.json())

        missing = self.client.get("/api/v1/analyses/missing")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["detail"], "分析任务不存在或已过期")

    def test_create_analysis_validates_form_and_returns_accepted(self) -> None:
        response = self.client.post(
            "/api/v1/analyses",
            data={"video_id": "video-api", "duration_seconds": "12"},
            files={"video": ("demo.mp4", b"media", "video/mp4")},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["id"], "job-api")
        self.assertEqual(self.service.create_arguments["analysis_mode"], "fast")

    def test_create_analysis_forwards_precise_mode(self) -> None:
        response = self.client.post(
            "/api/v1/analyses",
            data={
                "video_id": "video-api",
                "duration_seconds": "12",
                "analysis_mode": "precise",
            },
            files={"video": ("demo.mp4", b"media", "video/mp4")},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.service.create_arguments["analysis_mode"], "precise")

        invalid = self.client.post(
            "/api/v1/analyses",
            data={
                "video_id": "video-api",
                "duration_seconds": "12",
                "analysis_mode": "unknown",
            },
            files={"video": ("demo.mp4", b"media", "video/mp4")},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_magnet_controller_maps_invalid_input_to_422(self) -> None:
        response = self.client.post(
            "/api/v1/system/magnet",
            json={"magnet": "https://example.com/not-a-magnet-link-but-long-enough"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "磁力链接格式不正确")

    def test_video_library_endpoints_return_persisted_records_and_progress(self) -> None:
        listing = self.client.get("/api/v1/videos")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()[0]["id"], "video-api")
        self.assertEqual(listing.json()[0]["tags"], ["测试"])

        detail = self.client.get("/api/v1/videos/video-api")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["title"], "接口样例")

        missing = self.client.get("/api/v1/videos/missing")
        self.assertEqual(missing.status_code, 404)

        progress = self.client.patch(
            "/api/v1/videos/video-api/progress",
            json={
                "userId": "demo-local",
                "positionSeconds": 42,
                "durationSeconds": 120,
            },
        )
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(progress.json()["progress"]["lastPositionSeconds"], 42)

        media = self.client.get("/api/v1/videos/video-api/media")
        self.assertEqual(media.status_code, 200)
        self.assertEqual(media.headers["content-type"], "video/mp4")

        poster = self.client.get("/api/v1/videos/video-api/assets/poster")
        self.assertEqual(poster.status_code, 200)
        self.assertEqual(poster.headers["content-type"], "image/jpeg")

        subtitle = self.client.get("/api/v1/videos/video-api/subtitles/active")
        self.assertEqual(subtitle.status_code, 200)
        self.assertIn("WEBVTT", subtitle.text)

        deleted = self.client.delete("/api/v1/videos/video-api")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["deletedAssets"], 2)


if __name__ == "__main__":
    unittest.main()
