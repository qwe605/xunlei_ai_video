"""兼容旧启动命令；新入口位于 app.app。"""

from app.app import app, create_app

__all__ = ["app", "create_app"]
