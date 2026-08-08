import os
from dataclasses import dataclass
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    default_database = (BACKEND_ROOT / "data" / "xunlei.db").as_posix()
    return Settings(
        app_name="迅雷 AI 片库分析服务",
        app_version="2.0.0",
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{default_database}"),
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
    )


# 兼容离线工具；应用代码统一通过依赖注入读取 Settings。
_settings = get_settings()
MINIMAX_API_KEY = _settings.minimax_api_key
MINIMAX_MODEL = _settings.minimax_model
MINIMAX_BASE_URL = _settings.minimax_base_url
