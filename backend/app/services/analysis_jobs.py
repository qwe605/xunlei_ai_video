import threading
import uuid
import logging
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.exc import OperationalError

from app.config import Settings, get_settings
from app.database.repositories import AnalysisJobRepository, VideoRepository
from app.database.session import session_scope
from app.integrations.asr import (
    ASR_DEVICE,
    ASR_ENGINE,
    ASR_MODEL,
    PRECISE_ASR_MODEL,
    VolcAsrError,
    api_asr_ready,
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
ALLOWED_POSTERS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_POSTER_BYTES = 2 * 1024 * 1024
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
            "api": threading.Lock(),
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
        poster: UploadFile | None = None,
        video_id: str,
        duration_seconds: float,
        analysis_mode: str = "fast",
        owner_id: str = "demo-local",
        title: str | None = None,
        resolution: str = "待识别",
        codec: str = "待识别",
        width: int | None = None,
        height: int | None = None,
    ) -> AnalysisJob:
        if analysis_mode == "fast" and ASR_ENGINE == "api":
            raise UploadValidationError(
                503,
                "云端演示不支持本地 FunASR 快速模型，请使用 ASR API；本地安装包可体验快速识别。",
            )
        if analysis_mode == "api" and not api_asr_ready(self._settings):
            raise UploadValidationError(
                503,
                "ASR API 尚未配置，请联系管理员完成火山引擎鉴权后再试。",
            )
        if analysis_mode == "precise" and not precise_model_ready():
            raise UploadValidationError(
                503,
                (
                    "云端演示不支持本地 Whisper large-v3 精准模型；本地安装包可体验精准识别。"
                    if ASR_ENGINE == "api"
                    else "精准语音模型尚未安装完成，请暂时使用快速模式。"
                ),
            )
        suffix = ALLOWED_MEDIA.get(video.content_type or "")
        if not suffix:
            raise UploadValidationError(415, "仅支持 MP4 或 WebM 视频")

        with session_scope() as session:
            existing_owner = VideoRepository(session).get_owner_id(video_id)
        if existing_owner is not None and existing_owner != owner_id:
            raise UploadValidationError(409, "视频标识已被占用，请重新选择文件后再试")

        media_dir = self._settings.media_root / video_id
        media_dir.mkdir(parents=True, exist_ok=True)
        path = media_dir / f"source{suffix}"
        poster_path: Path | None = None
        poster_total = 0
        poster_mime_type: str | None = None
        checksum = hashlib.sha256()
        total = 0
        try:
            with path.open("wb") as handle:
                while chunk := await video.read(1024 * 1024):
                    total += len(chunk)
                    if total > self._settings.max_upload_bytes:
                        raise UploadValidationError(413, "视频超过本地分析大小限制")
                    checksum.update(chunk)
                    handle.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await video.close()

        if total == 0:
            path.unlink(missing_ok=True)
            raise UploadValidationError(400, "视频文件为空")

        if poster is not None:
            poster_suffix = ALLOWED_POSTERS.get(poster.content_type or "")
            if not poster_suffix:
                path.unlink(missing_ok=True)
                raise UploadValidationError(415, "封面仅支持 JPG、PNG 或 WebP")
            poster_path = media_dir / f"poster{poster_suffix}"
            try:
                with poster_path.open("wb") as handle:
                    while chunk := await poster.read(256 * 1024):
                        poster_total += len(chunk)
                        if poster_total > MAX_POSTER_BYTES:
                            raise UploadValidationError(413, "封面图片超过 2 MB")
                        handle.write(chunk)
            except Exception:
                poster_path.unlink(missing_ok=True)
                path.unlink(missing_ok=True)
                raise
            finally:
                await poster.close()
            poster_mime_type = poster.content_type or "image/jpeg"
        filename = video.filename or f"{video_id}{suffix}"
        with session_scope() as session:
            VideoRepository(session).create_placeholder(
                video_id=video_id,
                owner_id=owner_id,
                title=title or Path(filename).stem or filename,
                original_filename=filename,
                duration_seconds=duration_seconds,
                resolution=resolution,
                codec=codec,
                asset_path=path.relative_to(self._settings.media_root).as_posix(),
                asset_mime_type=video.content_type or "application/octet-stream",
                asset_size_bytes=total,
                width=width,
                height=height,
                checksum=checksum.hexdigest(),
                poster_path=(
                    poster_path.relative_to(self._settings.media_root).as_posix()
                    if poster_path
                    else None
                ),
                poster_mime_type=poster_mime_type,
                poster_size_bytes=poster_total,
            )
        return self.create(video_id, path, duration_seconds, analysis_mode, owner_id)

    def create(
        self,
        video_id: str,
        source_path: Path,
        duration_seconds: float,
        analysis_mode: str = "fast",
        owner_id: str = "demo-local",
    ) -> AnalysisJob:
        if analysis_mode not in {"fast", "api", "precise"}:
            raise UploadValidationError(422, "不支持的分析模式")
        mode_label = {
            "fast": "快速模式",
            "api": "ASR API 模式",
            "precise": "本地精准模式",
        }[analysis_mode]
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
            created = AnalysisJobRepository(session).create(job, owner_id)
        self._executor.submit(
            self._run, created.id, source_path, duration_seconds, analysis_mode, owner_id
        )
        return created

    def get(self, job_id: str, owner_id: str | None = None) -> AnalysisJob | None:
        with session_scope() as session:
            return AnalysisJobRepository(session).get(job_id, owner_id)

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
        owner_id: str = "demo-local",
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
            elif analysis_mode == "api":
                model_stage = "准备 ASR API 识别"
                model_detail = "正在检查火山引擎 ASR API 配置，并准备把音轨提交到云端识别。"
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
                        "ASR API 配置不可用，请检查火山引擎密钥和公网访问地址。"
                        if analysis_mode == "api"
                        else
                        "本地精准语音模型加载失败，请检查模型文件和运行环境，"
                        "或先切换快速模式。"
                        if analysis_mode == "precise"
                        else "快速语音模型加载失败，请检查模型缓存或服务配置。"
                    ),
                ) from error
            model_name = (
                MODEL_NAME
                if analysis_mode == "fast"
                else "volcengine:seedasr-2.0"
                if analysis_mode == "api"
                else f"faster-whisper:{PRECISE_ASR_MODEL}"
            )
            self._update(
                job_id,
                stage="提交 ASR API" if analysis_mode == "api" else "识别语音",
                progress=25,
                detail=(
                    "正在把临时音频提交到火山引擎录音文件识别 2.0，完成后会继续生成字幕、摘要和章节。"
                    if analysis_mode == "api"
                    else (
                        f"{model_name} 正在从真实音轨生成带词级时间轴字幕；"
                        "进度按已识别的音频时间更新。"
                    )
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
                        "ASR API 正在排队或识别；完成后会自动进入 MiniMax-M3 整理。"
                        if analysis_mode == "api"
                        else (
                            f"已识别 {_format_media_time(processed)} / "
                            f"{_format_media_time(duration_seconds)}，正在生成词级时间轴字幕。"
                        )
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
            try:
                with session_scope() as session:
                    VideoRepository(session).apply_analysis_result(
                        video_id=current.video_id,
                        owner_id=owner_id,
                        result=result,
                    )
            except OperationalError:
                # 部分单元测试只创建 analysis_jobs 表，用来隔离验证分析调度；此时跳过片库增强写回。
                logger.warning("片库表尚未初始化，跳过分析结果写回：%s", current.video_id)
            except Exception:
                # 分析任务是主流程，片库写回是持久化增强；写回失败要记录日志，不能把已完成的字幕结果改成失败。
                logger.exception("分析结果写回片库失败，视频：%s", current.video_id)
        except MediaAnalysisError as error:
            self._update(
                job_id,
                status=JobStatus.failed,
                stage="无法分析",
                progress=0,
                detail=error.user_message,
                error_code=error.code,
            )
        except VolcAsrError as error:
            self._update(
                job_id,
                status=JobStatus.failed,
                stage="ASR API 识别失败",
                progress=0,
                detail=str(error),
                error_code="ASR_API_FAILED",
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
            # 原视频已作为片库 source 资产持久化，不能再按临时文件删除。
            pass


# 旧名称仅供已有离线脚本平滑迁移。
AnalysisJobManager = AnalysisService
