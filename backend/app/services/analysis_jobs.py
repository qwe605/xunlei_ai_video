import tempfile
import threading
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.config import Settings, get_settings
from app.database.repositories import AnalysisJobRepository
from app.database.session import session_scope
from app.integrations.asr import (
    ASR_DEVICE,
    ASR_ENGINE,
    ASR_MODEL,
    PRECISE_ASR_MODEL,
    create_transcriber,
    effective_content_duration,
    precise_model_ready,
)
from app.integrations.minimax import MinimaxSummaryError, build_minimax_result
from app.schemas import AnalysisJob, JobStatus
from app.services.content_analysis import prepare_segments_for_review
from app.services.subtitle_review import select_suspicious_segments


MODEL_NAME = f"{ASR_ENGINE}:{ASR_MODEL}"
MODEL_DEVICE = ASR_DEVICE
ALLOWED_MEDIA = {"video/mp4": ".mp4", "video/webm": ".webm"}
logger = logging.getLogger(__name__)


def _format_media_time(seconds: float) -> str:
    total = max(0, round(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


class MediaAnalysisError(Exception):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message


class UploadValidationError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def validate_audio_track(source_path: Path) -> None:
    import av

    try:
        with av.open(str(source_path), mode="r", metadata_errors="ignore") as container:
            if not container.streams.audio:
                raise MediaAnalysisError(
                    "NO_AUDIO_TRACK",
                    "该视频没有可识别的音轨，无法生成字幕、摘要和章节。",
                )
    except MediaAnalysisError:
        raise
    except (av.error.InvalidDataError, av.error.EOFError) as error:
        raise MediaAnalysisError(
            "MEDIA_DECODE_FAILED",
            "视频音轨无法解码，请转换为标准 MP4(H.264/AAC) 或 WebM 后重试。",
        ) from error


class AnalysisService:
    """编排上传、ASR 与摘要任务；任务状态通过 Repository 持久化。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # 单并发避免普通笔记本同时加载多个模型任务导致内存和 CPU 被占满。
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xunlei-asr")
        self._models: dict[str, Any] = {}
        # 两种模式独立加锁，避免快速模型预热阻塞用户主动提交的精准任务。
        self._model_locks = {
            "fast": threading.Lock(),
            "precise": threading.Lock(),
        }
        self._recover_interrupted_jobs()
        if self._settings.preload_asr:
            threading.Thread(
                target=self._get_model,
                args=("fast",),
                name="xunlei-asr-preload",
                daemon=True,
            ).start()

    async def create_from_upload(
        self,
        *,
        video: UploadFile,
        video_id: str,
        duration_seconds: float,
        analysis_mode: str = "fast",
    ) -> AnalysisJob:
        if analysis_mode == "precise" and not precise_model_ready():
            raise UploadValidationError(
                503,
                "精准语音模型尚未安装完成，请暂时使用快速模式。",
            )
        suffix = ALLOWED_MEDIA.get(video.content_type or "")
        if not suffix:
            raise UploadValidationError(415, "仅支持 MP4 或 WebM 视频")

        handle = tempfile.NamedTemporaryFile(
            prefix="xunlei-ai-", suffix=suffix, delete=False
        )
        path = Path(handle.name)
        total = 0
        try:
            while chunk := await video.read(1024 * 1024):
                total += len(chunk)
                if total > self._settings.max_upload_bytes:
                    raise UploadValidationError(413, "视频超过本地分析大小限制")
                handle.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            handle.close()
            await video.close()

        if total == 0:
            path.unlink(missing_ok=True)
            raise UploadValidationError(400, "视频文件为空")
        return self.create(video_id, path, duration_seconds, analysis_mode)

    def create(
        self,
        video_id: str,
        source_path: Path,
        duration_seconds: float,
        analysis_mode: str = "fast",
    ) -> AnalysisJob:
        if analysis_mode not in {"fast", "precise"}:
            raise UploadValidationError(422, "不支持的分析模式")
        mode_label = "快速模式" if analysis_mode == "fast" else "精准模式"
        job = AnalysisJob(
            id=uuid.uuid4().hex,
            video_id=video_id,
            status=JobStatus.queued,
            stage="等待整理队列",
            progress=3,
            detail=(
                f"任务已进入 AI 分析队列，当前选择{mode_label}；"
                "前一个视频完成后会自动开始。"
            ),
        )
        with session_scope() as session:
            created = AnalysisJobRepository(session).create(job)
        self._executor.submit(
            self._run, created.id, source_path, duration_seconds, analysis_mode
        )
        return created

    def get(self, job_id: str) -> AnalysisJob | None:
        with session_scope() as session:
            return AnalysisJobRepository(session).get(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _update(self, job_id: str, **values: object) -> AnalysisJob:
        with session_scope() as session:
            return AnalysisJobRepository(session).update(job_id, values)

    def _recover_interrupted_jobs(self) -> None:
        # 后台线程无法跨进程恢复，启动时把遗留任务改成可理解、可重试的失败状态。
        with session_scope() as session:
            AnalysisJobRepository(session).fail_interrupted()

    def _get_model(self, analysis_mode: str) -> Any:
        with self._model_locks[analysis_mode]:
            if analysis_mode not in self._models:
                self._models[analysis_mode] = create_transcriber(analysis_mode)
            return self._models[analysis_mode]

    def _run(
        self,
        job_id: str,
        source_path: Path,
        duration_seconds: float,
        analysis_mode: str,
    ) -> None:
        try:
            self._update(
                job_id,
                status=JobStatus.processing,
                stage="检查音轨",
                progress=8,
                detail="正在确认视频包含可解码的音轨。",
            )
            validate_audio_track(source_path)
            model_cached = analysis_mode in getattr(self, "_models", {})
            if analysis_mode == "fast":
                model_stage = "准备快速识别" if model_cached else "首次加载快速语音模型"
                model_detail = (
                    "快速模型已在后台预热完成，正在准备读取音轨。"
                    if model_cached
                    else "首次运行需要把 FunASR 中文模型载入内存；之后同一服务进程会复用模型。"
                )
            else:
                model_stage = "准备精准识别" if model_cached else "加载本地精准语音模型"
                model_detail = (
                    "精准模型已在内存中，正在准备读取音轨。"
                    if model_cached
                    else "正在加载已安装并校验的 Whisper large-v3，本次任务不会临时下载模型。"
                )
            self._update(
                job_id,
                stage=model_stage,
                progress=12,
                detail=model_detail,
            )
            try:
                model = self._get_model(analysis_mode)
            except RuntimeError:
                # CUDA/cuDNN 等运行库错误由下方专用分支转换成可操作提示。
                raise
            except Exception as error:
                logger.exception("ASR 模型下载或加载失败，模式：%s", analysis_mode)
                raise MediaAnalysisError(
                    "ASR_MODEL_LOAD_FAILED",
                    (
                        "本地精准语音模型加载失败，请检查模型文件和运行环境，"
                        "或先切换快速模式。"
                        if analysis_mode == "precise"
                        else "快速语音模型加载失败，请检查模型缓存或服务配置。"
                    ),
                ) from error
            model_name = (
                MODEL_NAME
                if analysis_mode == "fast"
                else f"faster-whisper:{PRECISE_ASR_MODEL}"
            )
            self._update(
                job_id,
                stage="识别语音",
                progress=25,
                detail=(
                    f"{model_name} 正在从真实音轨生成带词级时间轴字幕；"
                    "进度按已识别的音频时间更新。"
                ),
            )
            last_progress = 24

            def report_transcription_progress(ratio: float) -> None:
                nonlocal last_progress
                progress = min(79, 25 + int(max(0.0, min(1.0, ratio)) * 54))
                # 限制数据库写入频率，同时保证页面持续看到真实进展。
                if progress <= last_progress:
                    return
                last_progress = progress
                processed = min(duration_seconds, duration_seconds * ratio)
                self._update(
                    job_id,
                    progress=progress,
                    detail=(
                        f"已识别 {_format_media_time(processed)} / "
                        f"{_format_media_time(duration_seconds)}，正在生成词级时间轴字幕。"
                    ),
                )

            set_progress_callback = getattr(model, "set_progress_callback", None)
            if callable(set_progress_callback):
                set_progress_callback(report_transcription_progress)
            try:
                segments, info = model.transcribe(source_path, duration_seconds)
            finally:
                if callable(set_progress_callback):
                    set_progress_callback(None)
            self._update(job_id, progress=80)

            review_segments = prepare_segments_for_review(segments)
            review_all_chinese = info.language.startswith("中文")
            suspicious_indexes = select_suspicious_segments(
                review_segments,
                limit=64,
                review_all=review_all_chinese,
            )
            content_duration_seconds = effective_content_duration(segments, duration_seconds)
            self._update(
                job_id,
                stage="MiniMax-M3 快速整理",
                progress=88,
                detail=(
                    f"正在一次生成摘要、章节，并保守核对 "
                    f"{len(suspicious_indexes)} 段低置信字幕。"
                ),
            )
            current = self.get(job_id)
            if current is None:
                raise LookupError("分析任务持久化记录丢失")
            result = build_minimax_result(
                video_id=current.video_id,
                duration_seconds=content_duration_seconds,
                segments=review_segments,
                language=info.language,
                language_probability=float(info.language_probability),
                asr_model=info.model_label,
                suspicious_indexes=set(suspicious_indexes),
            )
            self._update(
                job_id,
                status=JobStatus.completed,
                stage="整理完成",
                progress=100,
                detail=(
                    f"已生成 {len(review_segments)} 段字幕、校订 "
                    f"{result.subtitle_correction_count} 段，"
                    f"并生成 {len(result.chapters)} 个章节。"
                ),
                result=result,
            )
        except MediaAnalysisError as error:
            self._update(
                job_id,
                status=JobStatus.failed,
                stage="无法分析",
                progress=0,
                detail=error.user_message,
                error_code=error.code,
            )
        except ValueError as error:
            no_speech = "没有识别到语音" in str(error)
            self._update(
                job_id,
                status=JobStatus.failed,
                stage="无法分析",
                progress=0,
                detail=(
                    "没有检测到清晰人声，无法生成可靠字幕。"
                    if no_speech
                    else "AI 结果未通过结构校验，请重试或更换视频。"
                ),
                error_code="NO_SPEECH" if no_speech else "INVALID_RESULT",
            )
        except MinimaxSummaryError as error:
            self._update(
                job_id,
                status=JobStatus.failed,
                stage="MiniMax 整理失败",
                progress=82,
                detail=str(error),
                error_code="MINIMAX_FAILED",
            )
        except RuntimeError as error:
            runtime_message = str(error).lower()
            precise_runtime_missing = analysis_mode == "precise" and any(
                name in runtime_message for name in ("cublas", "cudnn", "cuda")
            )
            self._update(
                job_id,
                status=JobStatus.failed,
                stage="精准模型不可用" if precise_runtime_missing else "整理失败",
                progress=0,
                detail=(
                    "当前服务器缺少 Whisper GPU 运行库，请切换快速模式，或为服务器安装 CUDA 12 cuBLAS 与 cuDNN 9。"
                    if precise_runtime_missing
                    else "AI 分析运行异常，请重试或切换快速模式。"
                ),
                error_code=(
                    "PRECISE_RUNTIME_UNAVAILABLE"
                    if precise_runtime_missing
                    else "ANALYSIS_RUNTIME_FAILED"
                ),
            )
        except Exception:
            logger.exception("AI 分析任务出现未分类异常，任务：%s", job_id)
            # 不把模型栈、缓存路径或用户文件信息暴露给前端。
            self._update(
                job_id,
                status=JobStatus.failed,
                stage="整理失败",
                progress=0,
                detail="AI 分析异常，请重试或切换快速模式。",
                error_code="ANALYSIS_FAILED",
            )
        finally:
            source_path.unlink(missing_ok=True)


# 旧名称仅供已有离线脚本平滑迁移。
AnalysisJobManager = AnalysisService
