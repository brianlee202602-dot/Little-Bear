"""索引向量写入端口。"""

from __future__ import annotations

from typing import Protocol

from app.modules.indexing.schemas import DraftVectorPoint, VectorPayloadUpdate


class VectorIndexWriter(Protocol):
    """索引侧向量写入端口。"""

    def upsert_draft_points(self, points: tuple[DraftVectorPoint, ...]) -> None:
        ...

    def activate_points(
        self,
        *,
        collection_name: str,
        vector_ids: tuple[str, ...],
        permission_version: int,
    ) -> None:
        ...

    def update_payloads(self, updates: tuple[VectorPayloadUpdate, ...]) -> None:
        ...

    def delete_points(self, *, collection_name: str, vector_ids: tuple[str, ...]) -> None:
        ...


class NoopVectorIndexWriter:
    """本地最小链路默认不触碰外部 VectorStore。"""

    def upsert_draft_points(self, points: tuple[DraftVectorPoint, ...]) -> None:
        return None

    def activate_points(
        self,
        *,
        collection_name: str,
        vector_ids: tuple[str, ...],
        permission_version: int,
    ) -> None:
        return None

    def update_payloads(self, updates: tuple[VectorPayloadUpdate, ...]) -> None:
        return None

    def delete_points(self, *, collection_name: str, vector_ids: tuple[str, ...]) -> None:
        return None


__all__ = ["NoopVectorIndexWriter", "VectorIndexWriter"]
