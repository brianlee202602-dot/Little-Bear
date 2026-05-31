"""Knowledge-base administration service facade."""

from __future__ import annotations

from typing import Any

from app.modules.admin.knowledge_base_reader import AdminKnowledgeBaseReader
from app.modules.admin.knowledge_base_writer import AdminKnowledgeBaseWriter


class AdminKnowledgeBasesService:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_knowledge_bases(self, *args: Any, **kwargs: Any) -> Any:
        return self._reader().list_knowledge_bases(*args, **kwargs)

    def list_knowledge_base_options(self, *args: Any, **kwargs: Any) -> Any:
        return self._reader().list_knowledge_base_options(*args, **kwargs)

    def get_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._reader().get_knowledge_base(*args, **kwargs)

    def create_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().create_knowledge_base(*args, **kwargs)

    def patch_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().patch_knowledge_base(*args, **kwargs)

    def delete_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().delete_knowledge_base(*args, **kwargs)

    def _reader(self) -> AdminKnowledgeBaseReader:
        return AdminKnowledgeBaseReader(self._core_service)

    def _writer(self) -> AdminKnowledgeBaseWriter:
        return AdminKnowledgeBaseWriter(self._core_service)
