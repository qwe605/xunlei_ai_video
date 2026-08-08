import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.repositories import AnalysisJobRepository
from app.schemas import AnalysisJob, JobStatus


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


if __name__ == "__main__":
    unittest.main()
