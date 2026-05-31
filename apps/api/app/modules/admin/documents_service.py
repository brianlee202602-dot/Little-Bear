"""Document administration service facade."""

from __future__ import annotations

from typing import Any

from app.modules.admin.document_chunks_reader import AdminDocumentChunksReader
from app.modules.admin.document_preview_service import AdminDocumentPreviewService
from app.modules.admin.document_versions_reader import AdminDocumentVersionsReader
from app.modules.admin.document_writer import AdminDocumentWriter
from app.modules.admin.documents_reader import AdminDocumentsReader


class AdminDocumentsService:
    def __init__(self, core_service: Any) -> None:
        self._core_service = core_service

    def list_documents(self, *args: Any, **kwargs: Any) -> Any:
        return self._reader().list_documents(*args, **kwargs)

    def get_document(self, *args: Any, **kwargs: Any) -> Any:
        return self._reader().get_document(*args, **kwargs)

    def list_document_versions(self, *args: Any, **kwargs: Any) -> Any:
        return self._versions().list_document_versions(*args, **kwargs)

    def list_document_chunks(self, *args: Any, **kwargs: Any) -> Any:
        return self._chunks().list_document_chunks(*args, **kwargs)

    def get_document_preview(self, *args: Any, **kwargs: Any) -> Any:
        return self._preview().get_document_preview(*args, **kwargs)

    def list_document_index_versions(self, *args: Any, **kwargs: Any) -> Any:
        return self._versions().list_document_index_versions(*args, **kwargs)

    def patch_document(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().patch_document(*args, **kwargs)

    def delete_document(self, *args: Any, **kwargs: Any) -> Any:
        return self._writer().delete_document(*args, **kwargs)

    def _reader(self) -> AdminDocumentsReader:
        return AdminDocumentsReader(self._core_service)

    def _versions(self) -> AdminDocumentVersionsReader:
        return AdminDocumentVersionsReader(self._core_service)

    def _chunks(self) -> AdminDocumentChunksReader:
        return AdminDocumentChunksReader(self._core_service)

    def _preview(self) -> AdminDocumentPreviewService:
        return AdminDocumentPreviewService(self._core_service)

    def _writer(self) -> AdminDocumentWriter:
        return AdminDocumentWriter(self._core_service)
