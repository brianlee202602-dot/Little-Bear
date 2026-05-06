"""Config Service 的进程内缓存。

这是 P0 的轻量缓存实现：每个 API/Worker 进程各自持有一份 active_config 快照。
后续配置发布事件落地后，可以在收到通知时显式 invalidate。
"""

from __future__ import annotations

import threading
import time

from app.modules.config.schemas import ActiveConfigSnapshot


class ConfigCache:
    """active_config 快照的线程安全进程内缓存。"""

    def __init__(self, *, ttl_seconds: float = 5.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._snapshot: ActiveConfigSnapshot | None = None
        self._expires_at = 0.0

    def get(self) -> ActiveConfigSnapshot | None:
        with self._lock:
            if self._snapshot is None:
                return None
            if self._expires_at <= time.monotonic():
                # TTL 到期后丢弃旧快照，下一次读取会重新校验数据库中的 active_config。
                self._snapshot = None
                self._expires_at = 0.0
                return None
            return self._snapshot

    def set(self, snapshot: ActiveConfigSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot
            self._expires_at = time.monotonic() + max(self.ttl_seconds, 0.0)

    def invalidate(self) -> None:
        with self._lock:
            self._snapshot = None
            self._expires_at = 0.0
