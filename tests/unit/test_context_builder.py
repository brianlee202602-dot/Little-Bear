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


def test_context_builder_truncates_by_token_budget_for_cjk_text() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": "chunk_1",
                            "document_id": "doc_1",
                            "document_version_id": "doc_v_1",
                            "title": "协议说明",
                            "text_preview": "甲乙丙丁戊己庚辛",
                            "heading_path": None,
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    )
                ]
            )
        ]
    )

    context = ContextBuilder(max_context_tokens=6).build(
        session,
        query_text="协议说明",
        allowed_candidates=(
            _allowed_candidate(chunk_id="chunk_1", title="协议说明", score=0.9, rank=1),
        ),
    )

    assert context.chunks[0].content == "甲乙丙丁戊己"
    assert context.estimated_tokens == 6
    assert context.truncated is True


def test_context_builder_reads_full_chunk_text_from_object_reader() -> None:
    reader = _ChunkTextReader({"chunks/doc_1/chunk_1.txt": "完整 chunk 正文"})
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
                            "text_object_key": "chunks/doc_1/chunk_1.txt",
                            "text_preview": "预览正文",
                            "heading_path": None,
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    )
                ]
            )
        ]
    )

    context = ContextBuilder(chunk_text_reader=reader).build(
        session,
        query_text="员工如何请假",
        allowed_candidates=(
            _allowed_candidate(chunk_id="chunk_1", title="员工手册", score=0.9, rank=1),
        ),
    )

    assert context.chunks[0].content == "完整 chunk 正文"
    assert reader.object_keys == ["chunks/doc_1/chunk_1.txt"]
    assert "c.text_object_key" in session.executed[0][0]


def test_context_builder_falls_back_to_preview_when_full_text_unavailable() -> None:
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
                            "text_object_key": "chunks/doc_1/chunk_1.txt",
                            "text_preview": "预览正文",
                            "heading_path": None,
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    )
                ]
            )
        ]
    )

    context = ContextBuilder(chunk_text_reader=_ChunkTextReader({})).build(
        session,
        query_text="员工如何请假",
        allowed_candidates=(
            _allowed_candidate(chunk_id="chunk_1", title="员工手册", score=0.9, rank=1),
        ),
    )

    assert context.chunks[0].content == "预览正文"


def test_context_builder_limits_chunks_per_section() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": f"chunk_{index}",
                            "document_id": "doc_shared",
                            "document_version_id": "doc_v_shared",
                            "title": "员工手册",
                            "text_preview": f"同一小节内容 {index}",
                            "heading_path": "制度/请假",
                            "page_start": index,
                            "page_end": index,
                            "source_offsets": {"section_id": "leave_policy"},
                        }
                    )
                    for index in range(1, 5)
                ]
            )
        ]
    )

    context = ContextBuilder(
        max_chunks=4,
        max_chunks_per_document=4,
        max_chunks_per_section=2,
        mmr_enabled=False,
    ).build(
        session,
        query_text="请假制度",
        allowed_candidates=tuple(
            _allowed_candidate(
                chunk_id=f"chunk_{index}",
                title="员工手册",
                score=1.0 - index * 0.1,
                rank=index,
                document_id="doc_shared",
                document_version_id="doc_v_shared",
            )
            for index in range(1, 5)
        ),
    )

    assert [chunk.chunk_id for chunk in context.chunks] == ["chunk_1", "chunk_2"]


def test_context_builder_preserves_multi_query_coverage_and_char_budget() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": "can_1",
                            "document_id": "doc_can",
                            "document_version_id": "doc_v_can",
                            "title": "CAN 协议",
                            "text_preview": "CAN 协议定义内容很长很长很长",
                            "heading_path": "CAN",
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "can_2",
                            "document_id": "doc_can",
                            "document_version_id": "doc_v_can",
                            "title": "CAN 协议",
                            "text_preview": "CAN 其他内容",
                            "heading_path": "CAN",
                            "page_start": 2,
                            "page_end": 2,
                            "source_offsets": None,
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "rag_1",
                            "document_id": "doc_rag",
                            "document_version_id": "doc_v_rag",
                            "title": "RAG",
                            "text_preview": "RAG 是检索增强生成",
                            "heading_path": "RAG",
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                ]
            )
        ]
    )

    context = ContextBuilder(max_chunks=2, max_chars=20).build(
        session,
        query_text="什么是 CAN，什么是 RAG",
        allowed_candidates=(
            _allowed_candidate(
                chunk_id="can_1",
                title="CAN 协议",
                score=0.99,
                rank=1,
                document_id="doc_can",
                document_version_id="doc_v_can",
                matched_query="什么是 CAN",
                matched_query_index=1,
            ),
            _allowed_candidate(
                chunk_id="can_2",
                title="CAN 协议",
                score=0.9,
                rank=2,
                document_id="doc_can",
                document_version_id="doc_v_can",
                matched_query="什么是 CAN",
                matched_query_index=1,
            ),
            _allowed_candidate(
                chunk_id="rag_1",
                title="RAG",
                score=0.6,
                rank=3,
                document_id="doc_rag",
                document_version_id="doc_v_rag",
                matched_query="什么是 RAG",
                matched_query_index=2,
            ),
        ),
    )

    assert [chunk.chunk_id for chunk in context.chunks] == ["can_1", "rag_1"]
    assert [chunk.matched_query for chunk in context.chunks] == ["什么是 CAN", "什么是 RAG"]
    assert len(context.chunks[0].content) <= 10
    assert context.truncated is True


def test_context_builder_splits_multi_query_budget_across_selected_chunks() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": chunk_id,
                            "document_id": document_id,
                            "document_version_id": f"{document_id}_v",
                            "title": title,
                            "text_preview": content,
                            "heading_path": title,
                            "page_start": index,
                            "page_end": index,
                            "source_offsets": None,
                        }
                    )
                    for index, chunk_id, document_id, title, content in (
                        (1, "can_1", "doc_can", "CAN", "CAN" * 20),
                        (2, "rag_1", "doc_rag", "RAG", "RAG" * 20),
                        (3, "can_2", "doc_can", "CAN", "协议" * 20),
                        (4, "rag_2", "doc_rag", "RAG", "检索" * 20),
                    )
                ]
            )
        ]
    )

    context = ContextBuilder(
        max_chunks=4,
        max_chars=20,
        max_chunks_per_document=4,
        max_chunks_per_section=4,
        mmr_enabled=False,
    ).build(
        session,
        query_text="什么是 CAN，什么是 RAG",
        allowed_candidates=(
            _allowed_candidate(
                chunk_id="can_1",
                title="CAN",
                score=0.99,
                rank=1,
                document_id="doc_can",
                document_version_id="doc_can_v",
                matched_query="什么是 CAN",
                matched_query_index=1,
            ),
            _allowed_candidate(
                chunk_id="rag_1",
                title="RAG",
                score=0.98,
                rank=2,
                document_id="doc_rag",
                document_version_id="doc_rag_v",
                matched_query="什么是 RAG",
                matched_query_index=2,
            ),
            _allowed_candidate(
                chunk_id="can_2",
                title="CAN",
                score=0.97,
                rank=3,
                document_id="doc_can",
                document_version_id="doc_can_v",
                matched_query="什么是 CAN",
                matched_query_index=1,
            ),
            _allowed_candidate(
                chunk_id="rag_2",
                title="RAG",
                score=0.96,
                rank=4,
                document_id="doc_rag",
                document_version_id="doc_rag_v",
                matched_query="什么是 RAG",
                matched_query_index=2,
            ),
        ),
    )

    assert [chunk.chunk_id for chunk in context.chunks] == [
        "can_1",
        "rag_1",
        "can_2",
        "rag_2",
    ]
    assert [len(chunk.content) for chunk in context.chunks] == [5, 5, 5, 5]
    assert context.truncated is True


def test_context_builder_mmr_fills_after_multi_query_seed_without_key_error() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": "can_1",
                            "document_id": "doc_can",
                            "document_version_id": "doc_v_can",
                            "title": "CAN 协议",
                            "text_preview": "CAN 协议是控制器局域网通信协议",
                            "heading_path": "CAN",
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "rag_1",
                            "document_id": "doc_rag",
                            "document_version_id": "doc_v_rag",
                            "title": "RAG",
                            "text_preview": "RAG 是检索增强生成",
                            "heading_path": "RAG",
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "rag_2",
                            "document_id": "doc_rag",
                            "document_version_id": "doc_v_rag",
                            "title": "RAG",
                            "text_preview": "RAG 通过检索资料补充大模型上下文",
                            "heading_path": "RAG",
                            "page_start": 2,
                            "page_end": 2,
                            "source_offsets": None,
                        }
                    ),
                ]
            )
        ]
    )

    context = ContextBuilder(max_chunks=3, max_chars=200).build(
        session,
        query_text="什么是 CAN，什么是 RAG",
        allowed_candidates=(
            _allowed_candidate(
                chunk_id="can_1",
                title="CAN 协议",
                score=0.99,
                rank=1,
                document_id="doc_can",
                document_version_id="doc_v_can",
                matched_query="什么是 CAN",
                matched_query_index=1,
            ),
            _allowed_candidate(
                chunk_id="rag_1",
                title="RAG",
                score=0.9,
                rank=2,
                document_id="doc_rag",
                document_version_id="doc_v_rag",
                matched_query="什么是 RAG",
                matched_query_index=2,
            ),
            _allowed_candidate(
                chunk_id="rag_2",
                title="RAG",
                score=0.8,
                rank=3,
                document_id="doc_rag",
                document_version_id="doc_v_rag",
                matched_query="什么是 RAG",
                matched_query_index=2,
            ),
        ),
    )

    assert [chunk.chunk_id for chunk in context.chunks] == ["can_1", "rag_1", "rag_2"]


def test_context_builder_mmr_uses_embedding_similarity_when_available() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": "chunk_a",
                            "document_id": "doc_a",
                            "document_version_id": "doc_v_a",
                            "title": "A",
                            "text_preview": "alpha unique",
                            "heading_path": None,
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "chunk_b",
                            "document_id": "doc_b",
                            "document_version_id": "doc_v_b",
                            "title": "B",
                            "text_preview": "beta different",
                            "heading_path": None,
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                    _Row(
                        {
                            "chunk_id": "chunk_c",
                            "document_id": "doc_c",
                            "document_version_id": "doc_v_c",
                            "title": "C",
                            "text_preview": "gamma different",
                            "heading_path": None,
                            "page_start": 1,
                            "page_end": 1,
                            "source_offsets": None,
                        }
                    ),
                ]
            )
        ]
    )

    context = ContextBuilder(max_chunks=2, mmr_enabled=True, mmr_lambda=0.5).build(
        session,
        query_text="多样性选择",
        allowed_candidates=(
            _allowed_candidate(
                chunk_id="chunk_a",
                title="A",
                score=0.99,
                rank=1,
                embedding=(1.0, 0.0),
            ),
            _allowed_candidate(
                chunk_id="chunk_b",
                title="B",
                score=0.98,
                rank=2,
                embedding=(0.99, 0.01),
            ),
            _allowed_candidate(
                chunk_id="chunk_c",
                title="C",
                score=0.97,
                rank=3,
                embedding=(0.0, 1.0),
            ),
        ),
    )

    assert [chunk.chunk_id for chunk in context.chunks] == ["chunk_a", "chunk_c"]


def test_context_builder_applies_document_limits_per_rewritten_query() -> None:
    session = _FakeSession(
        [
            _Result(
                all_rows=[
                    _Row(
                        {
                            "chunk_id": chunk_id,
                            "document_id": "doc_shared",
                            "document_version_id": "doc_v_shared",
                            "title": "联合知识",
                            "text_preview": content,
                            "heading_path": heading,
                            "page_start": index,
                            "page_end": index,
                            "source_offsets": None,
                        }
                    )
                    for index, chunk_id, heading, content in (
                        (1, "can_1", "CAN", "CAN 协议定义"),
                        (2, "can_2", "CAN", "CAN 通信机制"),
                        (3, "rag_1", "RAG", "RAG 定义"),
                        (4, "rag_2", "RAG", "RAG 检索增强"),
                    )
                ]
            )
        ]
    )

    context = ContextBuilder(
        max_chunks=4,
        max_chunks_per_document=2,
        max_chunks_per_section=2,
        mmr_enabled=False,
    ).build(
        session,
        query_text="什么是 CAN，什么是 RAG",
        allowed_candidates=(
            _allowed_candidate(
                chunk_id="can_1",
                title="联合知识",
                score=0.99,
                rank=1,
                document_id="doc_shared",
                document_version_id="doc_v_shared",
                matched_query="什么是 CAN",
                matched_query_index=1,
            ),
            _allowed_candidate(
                chunk_id="can_2",
                title="联合知识",
                score=0.98,
                rank=2,
                document_id="doc_shared",
                document_version_id="doc_v_shared",
                matched_query="什么是 CAN",
                matched_query_index=1,
            ),
            _allowed_candidate(
                chunk_id="rag_1",
                title="联合知识",
                score=0.97,
                rank=3,
                document_id="doc_shared",
                document_version_id="doc_v_shared",
                matched_query="什么是 RAG",
                matched_query_index=2,
            ),
            _allowed_candidate(
                chunk_id="rag_2",
                title="联合知识",
                score=0.96,
                rank=4,
                document_id="doc_shared",
                document_version_id="doc_v_shared",
                matched_query="什么是 RAG",
                matched_query_index=2,
            ),
        ),
    )

    assert [chunk.chunk_id for chunk in context.chunks] == [
        "can_1",
        "rag_1",
        "can_2",
        "rag_2",
    ]


class _ChunkTextReader:
    def __init__(self, texts: dict[str, str]) -> None:
        self.texts = texts
        self.object_keys: list[str] = []

    def read_text(self, *, object_key: str) -> str | None:
        self.object_keys.append(object_key)
        return self.texts.get(object_key)


def _allowed_candidate(
    *,
    chunk_id: str,
    title: str,
    score: float,
    rank: int,
    document_id: str | None = None,
    document_version_id: str | None = None,
    matched_query: str | None = None,
    matched_query_index: int = 0,
    embedding: tuple[float, ...] | None = None,
) -> QueryAllowedCandidate:
    candidate = RetrievalCandidate(
        source="keyword",
        enterprise_id="ent_1",
        kb_id="kb_1",
        document_id=document_id or f"doc_for_{chunk_id}",
        document_version_id=document_version_id or f"doc_v_for_{chunk_id}",
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
        matched_query=matched_query,
        matched_query_index=matched_query_index,
        embedding=embedding,
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
