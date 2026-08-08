import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.controllers import api_router
from app.schemas import AnalysisJob, JobStatus


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


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        application = FastAPI()
        application.include_router(api_router)
        self.service = FakeAnalysisService()
        application.state.analysis_service = self.service
        self.client = TestClient(application)

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


if __name__ == "__main__":
    unittest.main()
