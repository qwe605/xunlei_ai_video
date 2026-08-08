import os
import re
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from app.services.content_analysis import TranscriptSegment, TranscriptWord
from app.services.text_normalization import to_simplified_chinese


# Windows 本地环境中 hf_xet 大文件分片可能长期无进度；默认使用可续传的普通 HTTP 下载。
# 部署环境确认 Xet 稳定后，仍可在启动前显式设置 HF_HUB_DISABLE_XET=0。
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

ASR_ENGINE = os.getenv("XUNLEI_ASR_ENGINE", "funasr").lower()
ASR_MODEL = os.getenv("XUNLEI_ASR_MODEL", "paraformer-zh")
ASR_DEVICE = os.getenv("XUNLEI_ASR_DEVICE", "cpu")
ASR_COMPUTE_TYPE = os.getenv(
    "XUNLEI_ASR_COMPUTE_TYPE",
    "float16" if ASR_DEVICE.startswith("cuda") else "int8",
)
ASR_HOTWORDS = os.getenv(
    "XUNLEI_ASR_HOTWORDS",
    "迅雷 云盘 磁力链接 人工智能 大模型 API GitHub ParseVideo",
)
PRECISE_ASR_MODEL = os.getenv("XUNLEI_PRECISE_ASR_MODEL", "large-v3")
PRECISE_ASR_DEVICE = os.getenv("XUNLEI_PRECISE_ASR_DEVICE", ASR_DEVICE)
PRECISE_ASR_COMPUTE_TYPE = os.getenv(
    "XUNLEI_PRECISE_ASR_COMPUTE_TYPE",
    "int8_float16" if PRECISE_ASR_DEVICE.startswith("cuda") else "int8",
)
PRECISE_MODEL_PATH = Path(
    os.getenv(
        "XUNLEI_PRECISE_MODEL_PATH",
        str(Path(__file__).resolve().parents[2] / "models" / "faster-whisper-large-v3"),
    )
)
PRECISE_MODEL_MIN_BYTES = 3_000_000_000
PRECISE_MODEL_REQUIRED_FILES = (
    "config.json",
    "model.bin",
    "preprocessor_config.json",
    "tokenizer.json",
    "vocabulary.json",
)


def precise_model_ready() -> bool:
    """只有本地权重完整时才开放精准模式，用户任务不负责临时下载模型。"""
    if not all((PRECISE_MODEL_PATH / name).is_file() for name in PRECISE_MODEL_REQUIRED_FILES):
        return False
    return (PRECISE_MODEL_PATH / "model.bin").stat().st_size >= PRECISE_MODEL_MIN_BYTES


@dataclass(frozen=True)
class TranscriptionInfo:
    language: str
    language_probability: float
    model_label: str


def _clean_text(value: str) -> str:
    # SenseVoice 等模型会附带情感和音频事件标签，字幕界面不直接展示这些控制标记。
    without_tags = re.sub(r"<\|[^|]+\|>", "", value)
    return to_simplified_chinese(without_tags).strip()


def _funasr_timestamp_words(text: str, raw_timestamps: Any) -> tuple[TranscriptWord, ...]:
    """只在时间戳数量可与可读 token 对应时保留，避免猜测错误边界。"""
    if not isinstance(raw_timestamps, list):
        return ()
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_+-]+", text)
    pairs = [
        item
        for item in raw_timestamps
        if isinstance(item, (list, tuple))
        and len(item) >= 2
        and float(item[1]) > float(item[0])
    ]
    if len(tokens) != len(pairs):
        return ()
    return tuple(
        TranscriptWord(float(pair[0]) / 1000, float(pair[1]) / 1000, token)
        for token, pair in zip(tokens, pairs, strict=True)
    )


def parse_funasr_result(payload: Any, duration_seconds: float) -> list[TranscriptSegment]:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise ValueError("FunASR 未返回有效转写结果")

    result = payload[0]
    sentences = result.get("sentence_info") or []
    segments: list[TranscriptSegment] = []
    for sentence in sentences:
        if not isinstance(sentence, dict):
            continue
        text = _clean_text(str(sentence.get("text", "")))
        if not text:
            continue
        start = max(0.0, float(sentence.get("start", 0)) / 1000)
        end = min(duration_seconds, float(sentence.get("end", 0)) / 1000)
        if end <= start:
            continue
        score = float(sentence.get("score", 0.92))
        probability = score if 0 <= score <= 1 else 0.92
        segments.append(
            TranscriptSegment(
                start=start,
                end=end,
                text=text,
                avg_logprob=0.0,
                no_speech_prob=0.0,
                compression_ratio=1.0,
                min_word_probability=probability,
                low_confidence_word_ratio=1.0 if probability < 0.6 else 0.0,
                words=_funasr_timestamp_words(text, sentence.get("timestamp")),
            )
        )

    if segments:
        return segments

    # 个别模型只返回整段文本和字符级时间戳；保留真实起止范围，避免伪造句级时间。
    text = _clean_text(str(result.get("text", "")))
    timestamps = result.get("timestamp") or []
    if not text:
        return []
    start = float(timestamps[0][0]) / 1000 if timestamps else 0.0
    end = float(timestamps[-1][1]) / 1000 if timestamps else duration_seconds
    return [TranscriptSegment(start=max(0, start), end=min(duration_seconds, end), text=text)]


def effective_content_duration(
    segments: list[TranscriptSegment],
    media_duration_seconds: float,
) -> float:
    """摘要与章节只覆盖最后一句人声附近，避免异常静态尾段诱发模型补写内容。"""
    if not segments:
        return media_duration_seconds
    return min(media_duration_seconds, max(segment.end for segment in segments) + 5)


def extract_audio_wav(source_path: Path) -> Path:
    """用项目已有的 PyAV 解码，避免 FunASR 在 Windows 上依赖外部 ffmpeg 命令。"""
    import av

    handle = tempfile.NamedTemporaryFile(prefix="xunlei-asr-", suffix=".wav", delete=False)
    handle.close()
    output_path = Path(handle.name)
    try:
        with (
            av.open(str(source_path), metadata_errors="ignore") as container,
            wave.open(str(output_path), "wb") as output,
        ):
            audio = container.streams.audio[0]
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16_000)
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16_000)
            for frame in container.decode(audio):
                for converted in resampler.resample(frame):
                    samples = converted.to_ndarray().reshape(-1).astype(np.int16)
                    output.writeframes(samples.tobytes())
        return output_path
    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def decode_audio_waveform(source_path: Path) -> np.ndarray:
    """通过 PyAV 解码 16 kHz 单声道波形，避免 stable-ts 依赖系统 ffmpeg 命令。"""
    audio_path = extract_audio_wav(source_path)
    try:
        with wave.open(str(audio_path), "rb") as source:
            frames = source.readframes(source.getnframes())
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        audio_path.unlink(missing_ok=True)


class FunAsrTranscriber:
    def __init__(self) -> None:
        from funasr import AutoModel

        self._progress_callback: Callable[[float], None] | None = None
        self.model = AutoModel(
            model=ASR_MODEL,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30_000},
            punc_model="ct-punc",
            device=ASR_DEVICE,
            disable_update=True,
        )

    def set_progress_callback(
        self,
        callback: Callable[[float], None] | None,
    ) -> None:
        """注册当前任务进度；FunASR 不提供流式回调，因此只上报解码和转写边界。"""
        self._progress_callback = callback

    def transcribe(
        self,
        source_path: Path,
        duration_seconds: float,
    ) -> tuple[list[TranscriptSegment], TranscriptionInfo]:
        audio_path = extract_audio_wav(source_path)
        try:
            if self._progress_callback:
                self._progress_callback(0.08)
            payload = self.model.generate(
                input=str(audio_path),
                batch_size_s=300,
                batch_size_threshold_s=60,
                hotword=ASR_HOTWORDS,
                use_itn=True,
                sentence_timestamp=True,
            )
            if self._progress_callback:
                self._progress_callback(0.78)
            return (
                parse_funasr_result(payload, duration_seconds),
                TranscriptionInfo(
                    language="中文（简体）",
                    language_probability=0.96,
                    model_label=f"FunASR {ASR_MODEL} · {ASR_DEVICE}",
                ),
            )
        finally:
            audio_path.unlink(missing_ok=True)


class FasterWhisperTranscriber:
    def __init__(
        self,
        *,
        model_name: str | None = None,
        display_name: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        import stable_whisper

        fallback_model = model_name or os.getenv("XUNLEI_WHISPER_FALLBACK_MODEL", "small")
        self.model_name = fallback_model
        self.display_name = display_name or fallback_model
        self.device = device or ASR_DEVICE
        self.compute_type = compute_type or ASR_COMPUTE_TYPE
        self._progress_callback: Callable[[float], None] | None = None
        # stable-ts 复用 faster-whisper 权重，并在转写后用真实音频静音区收紧词级时间轴。
        # 此处不启用 stable-ts 自动重组，中文显示分段仍由本项目按词轴和标点统一处理。
        self.model = stable_whisper.load_faster_whisper(
            fallback_model,
            device=self.device,
            compute_type=self.compute_type,
        )

    def set_progress_callback(
        self,
        callback: Callable[[float], None] | None,
    ) -> None:
        """注册当前任务的真实音频进度回调，任务结束后由调用方清除。"""
        self._progress_callback = callback

    def transcribe(
        self,
        source_path: Path,
        duration_seconds: float,
    ) -> tuple[list[TranscriptSegment], TranscriptionInfo]:
        def report_stable_progress(processed_seconds: float, total_seconds: float) -> None:
            if self._progress_callback:
                total = total_seconds if total_seconds > 0 else duration_seconds
                self._progress_callback(min(1.0, max(0.0, processed_seconds / total)))

        # 直接传 16 kHz 波形，避免 stable-ts 为静音分析再次调用系统 ffmpeg。
        # 同一波形同时用于 Whisper 转写和时间轴收紧，防止两次解码产生采样偏差。
        audio = decode_audio_waveform(source_path)
        result = self.model.transcribe(
            audio,
            language="zh",
            task="transcribe",
            initial_prompt=ASR_HOTWORDS,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=True,
            word_timestamps=True,
            # stable-ts 的波形静音抑制用于修正 Whisper 常见的词轴提前/滞后。
            # 使用本地波形量化，不加载额外的 Silero 模型，部署时不会再次下载权重。
            suppress_silence=True,
            suppress_word_ts=True,
            vad=False,
            q_levels=20,
            k_size=5,
            min_silence_dur=0.1,
            nonspeech_error=0.1,
            regroup=False,
            verbose=None,
            progress_callback=report_stable_progress,
        )
        segments: list[TranscriptSegment] = []
        for segment in result.segments:
            if self._progress_callback and duration_seconds > 0:
                self._progress_callback(
                    min(1.0, max(0.0, float(segment.end) / duration_seconds))
                )
            text = _clean_text(segment.text)
            if not text:
                continue
            probabilities = [
                float(word.probability)
                for word in (segment.words or [])
                if word.word.strip() and word.probability is not None
            ]
            low_confidence = [value for value in probabilities if value < 0.5]
            words = tuple(
                TranscriptWord(
                    start=float(word.start),
                    end=float(word.end),
                    text=_clean_text(word.word),
                    probability=(
                        float(word.probability) if word.probability is not None else 1.0
                    ),
                )
                for word in (segment.words or [])
                if word.word.strip() and word.start is not None and word.end is not None
            )
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=min(duration_seconds, float(segment.end)),
                    text=text,
                    avg_logprob=float(getattr(segment, "avg_logprob", 0.0) or 0.0),
                    no_speech_prob=float(getattr(segment, "no_speech_prob", 0.0) or 0.0),
                    compression_ratio=float(
                        getattr(segment, "compression_ratio", 1.0) or 1.0
                    ),
                    min_word_probability=min(probabilities) if probabilities else 1.0,
                    low_confidence_word_ratio=(
                        len(low_confidence) / len(probabilities) if probabilities else 0.0
                    ),
                    words=words,
                )
            )
        return (
            segments,
            TranscriptionInfo(
                language="中文（简体）",
                # 精准模式固定指定中文；stable-ts 结果不暴露 faster-whisper 的语言概率。
                language_probability=0.99,
                model_label=(
                    f"faster-whisper {self.display_name} + stable-ts · "
                    f"{self.device} {self.compute_type}"
                ),
            ),
        )


def create_transcriber(mode: str = "fast"):
    if mode == "precise":
        if not precise_model_ready():
            raise FileNotFoundError(
                f"精准模型未安装完整：{PRECISE_MODEL_PATH}"
            )
        return FasterWhisperTranscriber(
            model_name=str(PRECISE_MODEL_PATH),
            display_name=PRECISE_ASR_MODEL,
            device=PRECISE_ASR_DEVICE,
            compute_type=PRECISE_ASR_COMPUTE_TYPE,
        )
    if mode != "fast":
        raise ValueError(f"不支持的分析模式：{mode}")
    if ASR_ENGINE == "faster-whisper":
        return FasterWhisperTranscriber()
    if ASR_ENGINE != "funasr":
        raise ValueError(f"不支持的 ASR 引擎：{ASR_ENGINE}")
    return FunAsrTranscriber()
