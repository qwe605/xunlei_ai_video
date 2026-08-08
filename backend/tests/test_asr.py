import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from app.integrations.asr import (
    PRECISE_MODEL_PATH,
    create_transcriber,
    effective_content_duration,
    parse_funasr_result,
    FasterWhisperTranscriber,
)
from app.services.content_analysis import TranscriptSegment
from app.services.text_normalization import simplify_data, to_simplified_chinese


class ChineseAsrTests(unittest.TestCase):
    def test_parses_funasr_sentence_timestamps(self) -> None:
        segments = parse_funasr_result(
            [
                {
                    "sentence_info": [
                        {
                            "start": 1200,
                            "end": 3400,
                            "text": "這段影片介紹 ParseVideo 軟體資訊。",
                            "score": 0.91,
                        }
                    ]
                }
            ],
            duration_seconds=10,
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual((segments[0].start, segments[0].end), (1.2, 3.4))
        self.assertEqual(segments[0].text, "这段视频介绍 ParseVideo 软件信息。")

    def test_parses_funasr_character_timestamps_when_shape_matches(self) -> None:
        segments = parse_funasr_result(
            [
                {
                    "sentence_info": [
                        {
                            "start": 0,
                            "end": 4000,
                            "text": "第一，二",
                            "timestamp": [[0, 900], [1000, 1800], [3000, 3900]],
                        }
                    ]
                }
            ],
            duration_seconds=5,
        )

        self.assertEqual([word.text for word in segments[0].words], ["第", "一", "二"])
        self.assertEqual(segments[0].words[2].start, 3.0)

    @patch("app.integrations.asr.precise_model_ready", return_value=True)
    @patch("app.integrations.asr.FasterWhisperTranscriber")
    def test_precise_mode_selects_configured_large_model(
        self,
        transcriber,
        _model_ready,
    ) -> None:
        create_transcriber("precise")

        self.assertEqual(
            transcriber.call_args.kwargs["model_name"],
            str(PRECISE_MODEL_PATH),
        )
        self.assertEqual(transcriber.call_args.kwargs["display_name"], "large-v3")

    @patch("app.integrations.asr.precise_model_ready", return_value=False)
    def test_precise_mode_rejects_missing_local_model(self, _model_ready) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "精准模型未安装完整"):
            create_transcriber("precise")

    def test_precise_transcriber_uses_stable_timestamps_without_regrouping(self) -> None:
        captured: dict[str, object] = {}

        class FakeModel:
            def transcribe(self, source, **options):
                captured["source"] = source
                captured.update(options)
                options["progress_callback"](2.0, 4.0)
                word = SimpleNamespace(start=1.25, end=1.82, word="测试", probability=0.93)
                segment = SimpleNamespace(
                    start=1.25,
                    end=1.82,
                    text="测试。",
                    words=[word],
                    avg_logprob=-0.1,
                    no_speech_prob=0.01,
                    compression_ratio=1.0,
                )
                return SimpleNamespace(segments=[segment])

        stable_module = ModuleType("stable_whisper")
        stable_module.load_faster_whisper = lambda *_args, **_kwargs: FakeModel()
        progress: list[float] = []
        with patch.dict("sys.modules", {"stable_whisper": stable_module}), patch(
            "app.integrations.asr.decode_audio_waveform",
            return_value=np.zeros(64_000, dtype=np.float32),
        ):
            transcriber = FasterWhisperTranscriber(model_name="mock-large-v3")
            transcriber.set_progress_callback(progress.append)
            segments, info = transcriber.transcribe(Path("sample.mp4"), 4.0)

        self.assertTrue(captured["suppress_silence"])
        self.assertTrue(captured["suppress_word_ts"])
        self.assertFalse(captured["vad"])
        self.assertFalse(captured["regroup"])
        self.assertIsInstance(captured["source"], np.ndarray)
        self.assertEqual((segments[0].start, segments[0].end), (1.25, 1.82))
        self.assertEqual(segments[0].words[0].text, "测试")
        self.assertIn(0.5, progress)
        self.assertIn("stable-ts", info.model_label)

    def test_simplifies_nested_model_output(self) -> None:
        result = simplify_data(
            {
                "summary": "這個影片介紹雲端資料庫。",
                "tags": ["軟體", "網路"],
            }
        )

        self.assertEqual(result["summary"], "这个视频介绍云端数据库。")
        self.assertEqual(result["tags"], ["软件", "网络"])

    def test_converts_mainland_product_terms(self) -> None:
        self.assertEqual(
            to_simplified_chinese("請登入帳號並開啟影片資訊"),
            "请登录账号并开启视频信息",
        )
        self.assertEqual(
            to_simplified_chinese("這是影片,可以播放嗎?"),
            "这是视频，可以播放吗？",
        )

    def test_ignores_abnormally_long_silent_tail_for_chapters(self) -> None:
        duration = effective_content_duration(
            [
                TranscriptSegment(0, 20, "第一段"),
                TranscriptSegment(20, 72, "最后一段人声"),
            ],
            media_duration_seconds=3_784,
        )

        self.assertEqual(duration, 77)


if __name__ == "__main__":
    unittest.main()
