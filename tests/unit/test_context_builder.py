from __future__ import annotations

from app.modules.context.service import ContextBuilder
from app.modules.query.schemas import QueryAllowedCandidate, QueryCitation
from app.modules.retrieval import RetrievalCandidate


class _Row:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping


class _Result:
    def __init__(self, *, all_rows: list[_Row] | None = None) -> None:
        self._all_rows = all_rows or []

    def all(self) -> list[_Row]:
        return self._all_rows


class _FakeSession:
    def __init__(self, results: list[_Result]) -> None:
        self.results = results
        self.executed: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        if self.results:
            return self.results.pop(0)
        return _Result()


def test_context_builder_builds_context_from_allowed_candidates() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": "chunk_1",
                            "document_id": "doc_1",
                            "document_version_id": "doc_v_1",
                            "title": "员工手册",
                            "text_preview": "第一段内容",
                            "heading_path": "制度/请假",
                            "page_start": 1,
                            "page_end": 2,
                            "source_offsets": {"item_index": 0, "chunk_ordinal": 1},
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "chunk_2",
                            "document_id": "doc_2",
                            "document_version_id": "doc_v_2",
                            "title": "报销制度",
                            "text_preview": "第二段内容",
                            "heading_path": None,
                            "page_start": 3,
                            "page_end": 3,
                            "source_offsets": '{"item_index": 0, "chunk_ordinal": 2}',
                        }
                    ),
                ]
            )
        ]
    )

    context = ContextBuilder().build(
        session,
        query_text="员工如何请假",
        allowed_candidates=(
            _allowed_candidate(chunk_id="chunk_1", title="员工手册", score=0.9, rank=1),
            _allowed_candidate(chunk_id="chunk_2", title="报销制度", score=0.7, rank=2),
        ),
    )

    assert context.query_text == "员工如何请假"
    assert [chunk.chunk_id for chunk in context.chunks] == ["chunk_1", "chunk_2"]
    assert context.chunks[0].heading_path == "制度/请假"
    assert context.chunks[1].source_offsets == {"item_index": 0, "chunk_ordinal": 2}
    assert context.estimated_tokens > 0
    assert context.truncated is False


def test_context_builder_truncates_total_context_chars() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": "chunk_1",
                            "document_id": "doc_1",
                            "document_version_id": "doc_v_1",
                            "title": "员工手册",
                            "text_preview": "abcdef",
                            "heading_path": None,
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "chunk_2",
                            "document_id": "doc_2",
                            "document_version_id": "doc_v_2",
                            "title": "报销制度",
                            "text_preview": "ghijkl",
                            "heading_path": None,
                            "page_start": 2,
                            "page_end": 2,
                            "source_offsets": None,
                        }
                    ),
                ]
            )
        ]
    )

    context = ContextBuilder(max_chars=10).build(
        session,
        query_text="员工如何请假",
        allowed_candidates=(
            _allowed_candidate(chunk_id="chunk_1", title="员工手册", score=0.9, rank=1),
            _allowed_candidate(chunk_id="chunk_2", title="报销制度", score=0.7, rank=2),
        ),
    )

    assert [chunk.content for chunk in context.chunks] == ["abcdef", "ghij"]
    assert context.truncated is True


def _allowed_candidate(
    *,
    chunk_id: str,
    title: str,
    score: float,
    rank: int,
) -> QueryAllowedCandidate:
    candidate = RetrievalCandidate(
        source="keyword",
        enterprise_id="ent_1",
        kb_id="kb_1",
        document_id=f"doc_for_{chunk_id}",
        document_version_id=f"doc_v_for_{chunk_id}",
        chunk_id=chunk_id,
        title=title,
        owner_department_id="dept_1",
        visibility="department",
        document_lifecycle_status="active",
        document_index_status="indexed",
        chunk_status="active",
        visibility_state="active",
        index_version_id="index_1",
        indexed_permission_version=42,
        page_start=1,
        page_end=1,
        rank=rank,
        score=score,
    )
    citation = QueryCitation(
        source_id=chunk_id,
        doc_id=candidate.document_id,
        document_version_id=candidate.document_version_id,
        title=title,
        page_start=1,
        page_end=1,
        score=score,
    )
    return QueryAllowedCandidate(candidate=candidate, citation=citation)
