import unittest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.repositories import (
    AnalysisJobRepository,
    FeedbackRepository,
    SearchRepository,
    VideoRepository,
)
from app.schemas import (
    AnalysisJob,
    AnalysisResult,
    ChapterResult,
    FeedbackCreate,
    JobStatus,
    SearchRequest,
    VideoCorrectionUpdate,
)
from app.schemas import VideoQuestionRequest
from app.integrations.minimax import MinimaxSummaryError
from app.services.questions import QuestionService
from app.services.search import SearchService


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

    def test_analysis_jobs_are_readable_by_owner_only(self) -> None:
        with self.session_factory.begin() as session:
            repository = AnalysisJobRepository(session)
            repository.create(
                AnalysisJob(
                    id="job-private",
                    video_id="video-private",
                    status=JobStatus.queued,
                    stage="等待整理",
                    progress=3,
                    detail="等待执行",
                ),
                owner_id="owner-a",
            )
            self.assertIsNotNone(repository.get("job-private", "owner-a"))
            self.assertIsNone(repository.get("job-private", "owner-b"))

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

    def test_video_repository_corrects_information_for_owner_only(self) -> None:
        with self.session_factory.begin() as session:
            repository = VideoRepository(session)
            repository.create_placeholder(
                video_id="video-correction",
                owner_id="owner-a",
                title="旧标题",
                original_filename="correction.mp4",
                duration_seconds=30,
            )
            updated = repository.update_information(
                "video-correction",
                "owner-a",
                VideoCorrectionUpdate(
                    title="新标题",
                    short_description="用户校正后的一句话简介。",
                    summary="用户确认后的完整内容摘要。",
                    tags=["校正", "中文", "校正"],
                ),
            )

            self.assertIsNotNone(updated)
            self.assertEqual(updated.title, "新标题")  # type: ignore[union-attr]
            self.assertEqual(updated.tags, ["校正", "中文"])  # type: ignore[union-attr]
            self.assertIsNone(
                repository.update_information(
                    "video-correction",
                    "owner-b",
                    VideoCorrectionUpdate(
                        title="越权修改",
                        short_description="不应保存的简介。",
                        summary="不应保存的摘要。",
                        tags=["越权"],
                    ),
                )
            )

    def test_feedback_repository_creates_feedback_and_summary(self) -> None:
        with self.session_factory.begin() as session:
            repository = FeedbackRepository(session)
            created = repository.create(
                FeedbackCreate(
                    user_id="demo-local",
                    video_id="video-api",
                    target_type="video_answer",
                    target_id="answer-1",
                    feedback_type="helpful",
                    content="回答有帮助",
                )
            )
            self.assertEqual(created.status, "received")
            summary = repository.summary("demo-local")

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.helpful, 1)

    def test_search_repository_returns_orm_corpus_for_owner(self) -> None:
        with self.session_factory.begin() as session:
            repository = VideoRepository(session)
            repository.create_placeholder(
                video_id="video-search",
                owner_id="demo-local",
                title="永夜生存实录",
                original_filename="survival.mp4",
                duration_seconds=90,
            )
            repository.apply_analysis_result(
                video_id="video-search",
                owner_id="demo-local",
                result=AnalysisResult(
                    language="中文（简体）",
                    confidence=0.94,
                    short_description="讲解避难所建设和夜间巡逻。",
                    summary="主角在永夜环境中规划避难所，并安排巡逻路线。",
                    tags=["永夜", "避难所"],
                    subtitles_vtt=(
                        "WEBVTT\n\n"
                        "1\n00:00:10.000 --> 00:00:13.000\n我们先加固避难所入口\n\n"
                        "2\n00:00:40.000 --> 00:00:44.000\n夜间巡逻要避开主路\n"
                    ),
                    asr_model="faster-whisper:large-v3",
                    chapters=[
                        ChapterResult(
                            id="chapter-search",
                            title="避难所规划",
                            start_seconds=8,
                            end_seconds=35,
                            summary="说明入口加固和物资摆放。",
                            source="subtitle",
                            confidence=0.92,
                            spoiler_level="none",
                        )
                    ],
                ),
            )
            corpus = SearchRepository(session).list_searchable_videos("demo-local")

        self.assertEqual(len(corpus), 1)
        self.assertEqual(corpus[0].record.title, "永夜生存实录")
        self.assertEqual(len(corpus[0].record.transcript_segments), 2)


class SearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.patch_scope = mock.patch("app.services.search.session_scope", self._session_scope)
        self.patch_scope.start()

    def tearDown(self) -> None:
        self.patch_scope.stop()
        self.engine.dispose()

    def _session_scope(self):
        return self.session_factory.begin()

    def test_search_service_returns_cited_subtitle_match(self) -> None:
        with self.session_factory.begin() as session:
            repository = VideoRepository(session)
            repository.create_placeholder(
                video_id="video-rag-search",
                owner_id="demo-local",
                title="中文教程",
                original_filename="course.mp4",
                duration_seconds=80,
            )
            repository.apply_analysis_result(
                video_id="video-rag-search",
                owner_id="demo-local",
                result=AnalysisResult(
                    language="中文（简体）",
                    confidence=0.95,
                    short_description="讲解 Python 保留字。",
                    summary="课程解释保留字为什么不能作为变量名。",
                    tags=["Python", "保留字"],
                    subtitles_vtt=(
                        "WEBVTT\n\n"
                        "1\n00:00:12.000 --> 00:00:16.000\n这些保留字不能作为变量名\n"
                    ),
                    asr_model="faster-whisper:large-v3",
                    chapters=[
                        ChapterResult(
                            id="chapter-python",
                            title="保留字说明",
                            start_seconds=10,
                            end_seconds=30,
                            summary="解释保留字和变量名限制。",
                            source="subtitle",
                            confidence=0.9,
                            spoiler_level="none",
                        )
                    ],
                ),
            )

        response = SearchService().search(
            SearchRequest(query="找关于 Python 保留字的视频", mode="hybrid")
        )

        self.assertEqual(response.total, 1)
        self.assertEqual(response.results[0].video_id, "video-rag-search")
        self.assertGreaterEqual(len(response.results[0].citations), 1)
        self.assertEqual(response.results[0].citations[0].source_type, "chapter")


class QuestionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.patch_scope = mock.patch("app.services.questions.session_scope", self._session_scope)
        self.patch_answer = mock.patch(
            "app.services.questions.request_video_answer",
            side_effect=MinimaxSummaryError("测试环境不调用模型"),
        )
        self.patch_scope.start()
        self.patch_answer.start()

    def tearDown(self) -> None:
        self.patch_answer.stop()
        self.patch_scope.stop()
        self.engine.dispose()

    def _session_scope(self):
        return self.session_factory.begin()

    def _seed_video(self) -> None:
        with self.session_factory.begin() as session:
            repository = VideoRepository(session)
            repository.create_placeholder(
                video_id="video-question",
                owner_id="demo-local",
                title="登录问题复盘",
                original_filename="login.mp4",
                duration_seconds=100,
            )
            repository.apply_analysis_result(
                video_id="video-question",
                owner_id="demo-local",
                result=AnalysisResult(
                    language="中文（简体）",
                    confidence=0.93,
                    short_description="讲解 Cookie 登录失效排查。",
                    summary="视频说明 Cookie 过期会导致登录失效，并建议重新获取会话。",
                    tags=["登录", "Cookie"],
                    subtitles_vtt=(
                        "WEBVTT\n\n"
                        "1\n00:00:20.000 --> 00:00:24.000\nCookie 过期会导致登录失效\n"
                    ),
                    asr_model="faster-whisper:large-v3",
                    chapters=[
                        ChapterResult(
                            id="chapter-login",
                            title="登录失效原因",
                            start_seconds=18,
                            end_seconds=40,
                            summary="说明 Cookie 过期会导致登录失败。",
                            source="subtitle",
                            confidence=0.91,
                            spoiler_level="none",
                        )
                    ],
                ),
            )

    def test_question_service_answers_with_retrieved_citation_fallback(self) -> None:
        self._seed_video()

        response = QuestionService().answer_video_question(
            video_id="video-question",
            payload=VideoQuestionRequest(question="有没有讲 Cookie 登录失效？"),
        )

        self.assertEqual(response.status, "answered")
        self.assertIn("Cookie", response.answer)
        self.assertGreaterEqual(len(response.citations), 1)

    def test_question_service_refuses_without_evidence(self) -> None:
        self._seed_video()

        response = QuestionService().answer_video_question(
            video_id="video-question",
            payload=VideoQuestionRequest(question="有没有推荐北京餐厅？"),
        )

        self.assertEqual(response.status, "no_evidence")
        self.assertEqual(response.citations, [])


if __name__ == "__main__":
    unittest.main()
