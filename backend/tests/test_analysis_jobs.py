import asyncio
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import Settings
from app.services.analysis_jobs import AnalysisService, UploadValidationError


class AnalysisServiceSchedulingTests(unittest.TestCase):
    def test_model_preload_does_not_occupy_user_job_executor(self) -> None:
        """快速模型预热较慢时，用户提交的分析任务仍应能进入执行器。"""
        preload_started = threading.Event()
        release_preload = threading.Event()
        user_work_started = threading.Event()

        def blocking_preload(_service: AnalysisService, mode: str) -> object:
            self.assertEqual(mode, "fast")
            preload_started.set()
            release_preload.wait(timeout=2)
            return object()

        settings = Settings(
            app_name="测试服务",
            app_version="test",
            database_url="sqlite:///:memory:",
            max_upload_bytes=1024,
            minimax_api_key="",
            minimax_model="MiniMax-M3",
            minimax_base_url="https://example.com",
            preload_asr=True,
        )

        with (
            patch.object(AnalysisService, "_recover_interrupted_jobs"),
            patch.object(AnalysisService, "_get_model", blocking_preload),
        ):
            service = AnalysisService(settings)
            try:
                self.assertTrue(preload_started.wait(timeout=1))
                service._executor.submit(user_work_started.set)
                self.assertTrue(
                    user_work_started.wait(timeout=1),
                    "模型预热占用了用户分析任务执行器",
                )
            finally:
                release_preload.set()
                service.shutdown()

    def test_precise_model_download_failure_has_specific_message(self) -> None:
        """模型下载失败不能误报成用户视频格式错误。"""
        service = AnalysisService.__new__(AnalysisService)
        service._update = MagicMock()
        service._get_model = MagicMock(side_effect=OSError("download interrupted"))

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            source_path = Path(handle.name)

        with (
            patch("app.services.analysis_jobs.validate_audio_track"),
            patch("app.services.analysis_jobs.logger.exception"),
        ):
            service._run("job-test", source_path, 10, "precise")

        final_update = service._update.call_args_list[-1]
        self.assertEqual(final_update.kwargs["error_code"], "ASR_MODEL_LOAD_FAILED")
        self.assertIn("本地精准语音模型加载失败", final_update.kwargs["detail"])
        self.assertNotIn("转换视频格式", final_update.kwargs["detail"])

    def test_precise_transcription_reports_real_media_progress(self) -> None:
        """精准转写应按已处理的音频时间推进，不能长期停在模型加载阶段。"""
        class FakeModel:
            def __init__(self) -> None:
                self.callback = None

            def set_progress_callback(self, callback):
                self.callback = callback

            def transcribe(self, _path: Path, _duration: float):
                self.callback(0.5)
                info = MagicMock(language="英文", language_probability=1, model_label="test")
                return [MagicMock(end=10)], info

        service = AnalysisService.__new__(AnalysisService)
        service._update = MagicMock()
        service._get_model = MagicMock(return_value=FakeModel())
        service.get = MagicMock(return_value=MagicMock(video_id="video-test"))

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            source_path = Path(handle.name)

        with (
            patch("app.services.analysis_jobs.validate_audio_track"),
            patch("app.services.analysis_jobs.prepare_segments_for_review", return_value=[]),
            patch("app.services.analysis_jobs.select_suspicious_segments", return_value=[]),
            patch("app.services.analysis_jobs.effective_content_duration", return_value=20),
            patch("app.services.analysis_jobs.build_minimax_result") as build_result,
        ):
            build_result.return_value = MagicMock(
                subtitle_correction_count=0,
                chapters=[MagicMock()],
            )
            service._run("job-test", source_path, 20, "precise")

        progress_updates = [call.kwargs for call in service._update.call_args_list]
        midpoint = next(item for item in progress_updates if item.get("progress") == 52)
        self.assertIn("00:10 / 00:20", midpoint["detail"])

    def test_fast_transcription_leaves_model_stage_when_decode_starts(self) -> None:
        """快速模式即使 FunASR 本身不提供流式进度，也应尽早离开模型等待阶段。"""
        class FakeFastModel:
            def __init__(self) -> None:
                self.callback = None

            def set_progress_callback(self, callback):
                self.callback = callback

            def transcribe(self, _path: Path, _duration: float):
                self.callback(0.08)
                info = MagicMock(language="中文（简体）", language_probability=1, model_label="funasr")
                return [MagicMock(end=10)], info

        service = AnalysisService.__new__(AnalysisService)
        service._models = {"fast": object()}
        service._update = MagicMock()
        service._get_model = MagicMock(return_value=FakeFastModel())
        service.get = MagicMock(return_value=MagicMock(video_id="video-test"))

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            source_path = Path(handle.name)

        with (
            patch("app.services.analysis_jobs.validate_audio_track"),
            patch("app.services.analysis_jobs.prepare_segments_for_review", return_value=[]),
            patch("app.services.analysis_jobs.select_suspicious_segments", return_value=[]),
            patch("app.services.analysis_jobs.effective_content_duration", return_value=20),
            patch("app.services.analysis_jobs.build_minimax_result") as build_result,
        ):
            build_result.return_value = MagicMock(
                subtitle_correction_count=0,
                chapters=[MagicMock()],
            )
            service._run("job-test", source_path, 20, "fast")

        updates = [call.kwargs for call in service._update.call_args_list]
        self.assertIn("准备快速识别", [item.get("stage") for item in updates])
        self.assertTrue(any(item.get("stage") == "识别语音" for item in updates))
        self.assertTrue(any(item.get("progress") == 29 for item in updates))

    def test_missing_precise_model_is_rejected_before_upload_read(self) -> None:
        """精准模型未安装时，不应先读取并上传用户的大视频。"""
        service = AnalysisService.__new__(AnalysisService)
        video = MagicMock()

        with (
            patch("app.services.analysis_jobs.precise_model_ready", return_value=False),
            self.assertRaisesRegex(UploadValidationError, "尚未安装完成"),
        ):
            asyncio.run(
                service.create_from_upload(
                    video=video,
                    video_id="video-test",
                    duration_seconds=10,
                    analysis_mode="precise",
                )
            )

        video.read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
