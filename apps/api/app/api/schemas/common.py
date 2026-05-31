"""Common API schemas shared across route domains."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PaginationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int
    page_size: int
    total: int


class CitationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    doc_id: str
    document_version_id: str
    title: str
    page_start: int
    page_end: int
    score: float
