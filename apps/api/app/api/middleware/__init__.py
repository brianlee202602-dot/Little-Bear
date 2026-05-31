"""API 层中间件。"""

from app.api.middleware.setup_guard import SetupGuardMiddleware

__all__ = ["SetupGuardMiddleware"]
