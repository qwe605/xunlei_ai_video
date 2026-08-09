import unittest
from contextlib import contextmanager
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.controllers import auth_controller, library_controller
from app.database.base import Base
from app.database.models import UserRecord
from app.database.repositories import VideoRepository
from app.schemas import FeedbackCreate
from app.services.auth import AuthService
from app.services.feedback import FeedbackService
from app.services.library import LibraryService


class AuthenticationIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.auth_scope = mock.patch(
            "app.services.auth.session_scope", self._session_scope
        )
        self.library_scope = mock.patch(
            "app.services.library.session_scope", self._session_scope
        )
        self.feedback_scope = mock.patch(
            "app.services.feedback.session_scope", self._session_scope
        )
        self.auth_scope.start()
        self.library_scope.start()
        self.feedback_scope.start()

        application = FastAPI()
        application.include_router(auth_controller.router, prefix="/api/v1")
        application.include_router(library_controller.router, prefix="/api/v1")
        application.state.auth_service = AuthService()
        application.state.library_service = LibraryService()
        self.client = TestClient(application)

    def tearDown(self) -> None:
        self.client.close()
        self.feedback_scope.stop()
        self.library_scope.stop()
        self.auth_scope.stop()
        self.engine.dispose()

    @contextmanager
    def _session_scope(self):
        with self.session_factory.begin() as session:
            yield session

    def _register(self, name: str, email: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/register",
            json={"displayName": name, "email": email, "password": "StrongPass123"},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_register_login_logout_and_password_storage(self) -> None:
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        account = self._register("账号甲", "owner-a@example.com")
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["id"], account["id"])
        cookie = self.client.cookies.get("xunlei_session")
        self.assertTrue(cookie)

        with self.session_factory() as session:
            record = session.scalar(
                select(UserRecord).where(UserRecord.email == "owner-a@example.com")
            )
            self.assertIsNotNone(record)
            self.assertNotEqual(record.password_hash, "StrongPass123")  # type: ignore[union-attr]
            self.assertNotIn("StrongPass123", record.password_hash)  # type: ignore[union-attr]

        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={
                "displayName": "重复账号",
                "email": "owner-a@example.com",
                "password": "StrongPass123",
            },
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

        wrong_password = self.client.post(
            "/api/v1/auth/login",
            json={"email": "owner-a@example.com", "password": "WrongPass123"},
        )
        self.assertEqual(wrong_password.status_code, 401)
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": "owner-a@example.com", "password": "StrongPass123"},
        )
        self.assertEqual(login.status_code, 200)

    def test_private_library_isolated_between_accounts(self) -> None:
        self.assertEqual(self.client.get("/api/v1/videos").status_code, 401)
        owner_a = self._register("账号甲", "a@example.com")
        with self.session_factory.begin() as session:
            VideoRepository(session).create_placeholder(
                video_id="private-video-a",
                owner_id=owner_a["id"],
                title="甲的私有视频",
                original_filename="private-a.mp4",
                duration_seconds=60,
            )

        self.assertEqual(len(self.client.get("/api/v1/videos").json()), 1)
        self.assertEqual(
            self.client.get("/api/v1/videos/private-video-a").status_code,
            200,
        )

        self.client.post("/api/v1/auth/logout")
        owner_b = self._register("账号乙", "b@example.com")
        self.assertEqual(self.client.get("/api/v1/videos").json(), [])
        self.assertEqual(
            self.client.get("/api/v1/videos/private-video-a").status_code,
            404,
        )
        with self.assertRaises(LookupError):
            FeedbackService().create_feedback(
                FeedbackCreate(
                    user_id=owner_b["id"],
                    video_id="private-video-a",
                    target_type="video_metadata",
                    target_id="private-video-a",
                    feedback_type="correction",
                    content="尝试跨账号反馈",
                )
            )


if __name__ == "__main__":
    unittest.main()
