"""Folder-related document counters for admin services."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


class AdminFolderDocumentCounterMixin:
    """Compatibility mixin exposing historical AdminService folder counters."""

    def _count_folder_documents(
        self,
        session: Session,
        *,
        enterprise_id: str,
        folder_id: str,
    ) -> int:
        row = session.execute(
            text(
                """
                SELECT count(*) AS document_count
                FROM documents
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND folder_id = CAST(:folder_id AS uuid)
                  AND deleted_at IS NULL
                  AND lifecycle_status != 'deleted'
                """
            ),
            {"enterprise_id": enterprise_id, "folder_id": folder_id},
        ).one()
        return int(row._mapping["document_count"])
