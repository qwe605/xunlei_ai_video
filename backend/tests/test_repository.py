import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.repositories import AnalysisJobRepository, VideoRepository
from app.schemas import AnalysisJob, AnalysisResult, ChapterResult, JobStatus


class AnalysisJobRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_creates_reads_and_updates_job_with_orm(self) -> None:
        with self.session_factory.begin() as session:
            repository = AnalysisJobRepository(session)
            created = repository.create(
                AnalysisJob(
                    id="job-1",
                    video_id="video-1",
                    status=JobStatus.queued,
                    stage="等待模型",
                    progress=5,
                    detail="已进入队列",
                )
            )
            self.assertEqual(created.video_id, "video-1")

        with self.session_factory.begin() as session:
            repository = AnalysisJobRepository(session)
            updated = repository.update(
                "job-1",
                {"status": JobStatus.processing, "progress": 25, "stage": "识别语音"},
            )
            self.assertEqual(updated.status, JobStatus.processing)
            self.assertEqual(repository.get("job-1").progress, 25)  # type: ignore[union-attr]

    def test_marks_interrupted_jobs_as_retryable_failures(self) -> None:
        with self.session_factory.begin() as session:
            repository = AnalysisJobRepository(session)
            repository.create(
                AnalysisJob(
                    id="job-interrupted",
                    video_id="video-2",
                    status=JobStatus.processing,
                    stage="识别语音",
                    progress=25,
                    detail="正在识别",
                )
            )
            self.assertEqual(repository.fail_interrupted(), 1)
            recovered = repository.get("job-interrupted")
            self.assertEqual(recovered.status, JobStatus.failed)  # type: ignore[union-attr]
            self.assertEqual(recovered.error_code, "SERVICE_RESTARTED")  # type: ignore[union-attr]

    def test_video_repository_persists_analysis_result_and_progress(self) -> None:
        with self.session_factory.begin() as session:
            repository = VideoRepository(session)
            created = repository.create_placeholder(
                video_id="video-persist",
                owner_id="demo-local",
                title="持久化样例",
                original_filename="persist.mp4",
                duration_seconds=60,
                resolution="1280 × 720",
                codec="本地 MP4",
            )
            self.assertEqual(created.index_status, "pending")

            detail = repository.apply_analysis_result(
                video_id="video-persist",
                owner_id="demo-local",
                result=AnalysisResult(
                    language="中文（简体）",
                    confidence=0.96,
                    short_description="已经完成字幕和章节整理。",
                    summary="这是一段用于验证持久化的视频。",
                    tags=["持久化", "字幕"],
                    subtitles_vtt=(
                        "WEBVTT\n\n"
                        "1\n00:00:00.000 --> 00:00:02.000\n第一句字幕\n\n"
                        "2\n00:00:02.000 --> 00:00:05.000\n第二句字幕\n"
                    ),
                    asr_model="faster-whisper:large-v3",
                    chapters=[
                        ChapterResult(
                            id="chapter-1",
                            title="开场",
                            start_seconds=0,
                            end_seconds=30,
                            summary="介绍视频主题。",
                            source="subtitle",
                            confidence=0.9,
                            spoiler_level="none",
                        )
                    ],
                ),
            )
            self.assertIsNotNone(detail)
            self.assertEqual(detail.index_status, "ready")  # type: ignore[union-attr]
            self.assertEqual(len(detail.subtitles), 1)  # type: ignore[union-attr]
            self.assertEqual(len(detail.chapters), 1)  # type: ignore[union-attr]
            self.assertEqual(len(detail.transcript_segments), 2)  # type: ignore[union-attr]

            progress = repository.update_progress(
                video_id="video-persist",
                user_id="demo-local",
                position_seconds=15,
                duration_seconds=60,
            )
            self.assertEqual(progress.progress.last_position_seconds, 15)
            self.assertAlmostEqual(progress.progress.completed_percent, 0.25)

        with self.session_factory.begin() as session:
            repository = VideoRepository(session)
            videos = repository.list_by_owner("demo-local")
            self.assertEqual(len(videos), 1)
            self.assertEqual(videos[0].progress.completed_percent, 0.25)  # type: ignore[union-attr]

    def test_video_repository_deletes_video_and_returns_asset_paths(self) -> None:
        with self.session_factory.begin() as session:
            repository = VideoRepository(session)
            repository.create_placeholder(
                video_id="video-delete",
                owner_id="demo-local",
                title="待删除样例",
                original_filename="delete.mp4",
                duration_seconds=30,
                asset_path="video-delete/source.mp4",
                asset_mime_type="video/mp4",
                asset_size_bytes=10,
                poster_path="video-delete/poster.jpg",
                poster_mime_type="image/jpeg",
                poster_size_bytes=8,
            )
            paths = repository.delete_video("video-delete", "demo-local")
            self.assertEqual(paths, ["video-delete/source.mp4", "video-delete/poster.jpg"])
            self.assertEqual(repository.list_by_owner("demo-local"), [])


if __name__ == "__main__":
    unittest.main()
