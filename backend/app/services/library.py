from pathlib import Path

from app.config import Settings, get_settings
from app.database.repositories import VideoRepository
from app.database.session import session_scope
from app.schemas import ProgressUpdateResponse, SubtitleRead, VideoAssetRead, VideoDetail, VideoListItem


class LibraryService:
    """片库业务层；负责把 Repository 的持久化能力包装成稳定 API 语义。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def list_videos(self, owner_id: str = "demo-local") -> list[VideoListItem]:
        with session_scope() as session:
            return VideoRepository(session).list_by_owner(owner_id)

    def get_video(self, video_id: str, owner_id: str = "demo-local") -> VideoDetail | None:
        with session_scope() as session:
            return VideoRepository(session).get_detail(video_id, owner_id)

    def update_progress(
        self,
        *,
        video_id: str,
        user_id: str,
        position_seconds: float,
        duration_seconds: float,
    ) -> ProgressUpdateResponse:
        with session_scope() as session:
            repository = VideoRepository(session)
            # 当前本地 Demo 仍用 owner_id=user_id；后续接入服务端鉴权时由依赖注入统一替换。
            if repository.get_detail(video_id, user_id) is None:
                raise LookupError("视频不存在或无权访问")
            return repository.update_progress(
                video_id=video_id,
                user_id=user_id,
                position_seconds=position_seconds,
                duration_seconds=duration_seconds,
            )

    def get_source_asset_path(
        self,
        *,
        video_id: str,
        owner_id: str = "demo-local",
    ) -> tuple[Path, VideoAssetRead] | None:
        with session_scope() as session:
            asset = VideoRepository(session).get_source_asset(video_id, owner_id)
        if asset is None:
            return None
        path = self._resolve_media_path(asset.storage_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("视频源文件不存在，请重新导入")
        return path, asset

    def get_active_subtitle(
        self,
        *,
        video_id: str,
        owner_id: str = "demo-local",
    ) -> SubtitleRead | None:
        with session_scope() as session:
            subtitle = VideoRepository(session).get_active_subtitle(video_id, owner_id)
            return SubtitleRead.model_validate(subtitle) if subtitle else None

    def _resolve_media_path(self, storage_path: str) -> Path:
        root = self._settings.media_root.resolve()
        path = (root / storage_path).resolve()
        # 数据库字段也是输入边界，必须确认最终路径仍在媒体根目录内。
        if root != path and root not in path.parents:
            raise PermissionError("媒体路径越界")
        return path
