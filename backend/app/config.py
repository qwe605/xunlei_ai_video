import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_local_environment() -> None:
    """加载本机配置，系统环境变量优先且密钥不进入源码。"""
    path = BACKEND_ROOT / ".env.local"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_local_environment()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    database_url: str
    max_upload_bytes: int
    minimax_api_key: str
    minimax_model: str
    minimax_base_url: str
    preload_asr: bool
    auth_cookie_secure: bool = False
    auth_session_days: int = 7
    media_root: Path = field(default_factory=lambda: BACKEND_ROOT / "data" / "media")
    public_base_url: str = ""
    volc_asr_api_key: str = ""
    volc_asr_app_id: str = ""
    volc_asr_access_token: str = ""
    volc_asr_resource_id: str = "volc.seedasr.auc"
    volc_asr_base_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel"
    volc_asr_poll_interval_seconds: float = 2.0
    volc_asr_timeout_seconds: float = 600.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_root = BACKEND_ROOT / "data"
    default_database = (data_root / "xunlei.db").as_posix()
    return Settings(
        app_name="迅雷 AI 片库分析服务",
        app_version="2.0.0",
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{default_database}"),
        media_root=Path(os.getenv("XUNLEI_MEDIA_ROOT", str(data_root / "media"))),
        max_upload_bytes=int(
            os.getenv("XUNLEI_MAX_UPLOAD_BYTES", str(300 * 1024 * 1024))
        ),
        minimax_api_key=os.getenv("MINIMAX_API_KEY", ""),
        minimax_model=os.getenv("MINIMAX_MODEL", "MiniMax-M3"),
        minimax_base_url=os.getenv(
            "MINIMAX_BASE_URL", "https://api.minimaxi.com"
        ).rstrip("/"),
        preload_asr=os.getenv("XUNLEI_PRELOAD_ASR", "true").lower()
        in {"1", "true", "yes"},
        auth_cookie_secure=os.getenv("XUNLEI_AUTH_COOKIE_SECURE", "false").lower()
        in {"1", "true", "yes"},
        auth_session_days=max(1, int(os.getenv("XUNLEI_AUTH_SESSION_DAYS", "7"))),
        public_base_url=os.getenv("XUNLEI_PUBLIC_BASE_URL", "").rstrip("/"),
        volc_asr_api_key=os.getenv("VOLC_ASR_API_KEY", ""),
        volc_asr_app_id=os.getenv("VOLC_ASR_APP_ID", ""),
        volc_asr_access_token=os.getenv("VOLC_ASR_ACCESS_TOKEN", ""),
        volc_asr_resource_id=os.getenv("VOLC_ASR_RESOURCE_ID", "volc.seedasr.auc"),
        volc_asr_base_url=os.getenv(
            "VOLC_ASR_BASE_URL",
            "https://openspeech.bytedance.com/api/v3/auc/bigmodel",
        ).rstrip("/"),
        volc_asr_poll_interval_seconds=float(
            os.getenv("VOLC_ASR_POLL_INTERVAL_SECONDS", "2")
        ),
        volc_asr_timeout_seconds=float(os.getenv("VOLC_ASR_TIMEOUT_SECONDS", "600")),
    )


# 兼容离线工具；应用代码统一通过依赖注入读取 Settings。
_settings = get_settings()
MINIMAX_API_KEY = _settings.minimax_api_key
MINIMAX_MODEL = _settings.minimax_model
MINIMAX_BASE_URL = _settings.minimax_base_url
