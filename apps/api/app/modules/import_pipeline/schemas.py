"""Import Service 内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ImportActorContext:
    user_id: str
    scopes: tuple[str, ...]
    department_ids: tuple[str, ...] = ()
    knowledge_base_ids: tuple[str, ...] = ()
    can_import_all_knowledge_bases: bool = False


@dataclass(frozen=True)
class DocumentImportItem:
    title: str
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportJob:
    id: str
    kb_id: str | None
    status: str
    stage: str
    document_ids: tuple[str, ...] = ()
    error_summary: str | None = None
    job_type: str | None = None


@dataclass(frozen=True)
class ImportJobList:
    items: tuple[ImportJob, ...]
    total: int
