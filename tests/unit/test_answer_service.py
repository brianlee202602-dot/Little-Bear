from __future__ import annotations

from app.modules.answer import AnswerService
from app.modules.context.schemas import ContextChunk, QueryContext
from app.modules.models import ChatCompletionResult, ChatMessage, ModelClientError


class _ChatClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, temperature, max_tokens) -> ChatCompletionResult:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.fail:
            raise ModelClientError("LLM_PROVIDER_UNAVAILABLE", "provider unavailable")
        return ChatCompletionResult(
            content="员工年假需要提前申请。[source:chunk_1]",
            token_usage={"prompt_tokens": 12, "completion_tokens": 6},
        )


def test_answer_service_generates_answer_from_query_context() -> None:
    chat_client = _ChatClient()

    result = AnswerService(
        chat_client=chat_client,
        temperature=0.2,
        max_tokens=256,
    ).generate(query_context=_query_context())

    assert result.answer == "员工年假需要提前申请。[source:chunk_1]"
    assert result.degraded is False
    assert result.token_usage == {"prompt_tokens": 12, "completion_tokens": 6}
    assert chat_client.calls[0]["temperature"] == 0.2
    assert chat_client.calls[0]["max_tokens"] == 256
    messages = chat_client.calls[0]["messages"]
    assert isinstance(messages[0], ChatMessage)
    assert "只能基于用户可访问的资料回答" in messages[0].content
    assert "[source:chunk_1]" in messages[1].content
    assert "员工年假需要提前申请" in messages[1].content


def test_answer_service_degrades_without_context_or_llm_client() -> None:
    empty_result = AnswerService(chat_client=_ChatClient()).generate(query_context=None)
    unavailable_result = AnswerService().generate(query_context=_query_context())

    assert empty_result.degraded is True
    assert empty_result.degrade_reason == "llm_context_empty"
    assert unavailable_result.degraded is True
    assert unavailable_result.degrade_reason == "llm_runtime_config_unavailable"


def test_answer_service_degrades_when_llm_provider_fails() -> None:
    result = AnswerService(chat_client=_ChatClient(fail=True)).generate(
        query_context=_query_context()
    )

    assert result.answer == ""
    assert result.degraded is True
    assert result.degrade_reason == "LLM_PROVIDER_UNAVAILABLE"


def _query_context() -> QueryContext:
    return QueryContext(
        query_text="员工年假怎么申请？",
        chunks=(
            ContextChunk(
                chunk_id="chunk_1",
                document_id="doc_1",
                document_version_id="doc_v_1",
                title="员工手册",
                content="员工年假需要提前申请。",
                heading_path="制度/请假",
                page_start=1,
                page_end=2,
                score=0.9,
                rank=1,
            ),
        ),
        estimated_tokens=10,
        truncated=False,
    )
