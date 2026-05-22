from __future__ import annotations

from app.modules.answer import AnswerService
from app.modules.context.schemas import ContextChunk, QueryContext
from app.modules.models import (
    ChatCompletionChunk,
    ChatCompletionResult,
    ChatMessage,
    ModelClientError,
)


class _ChatClient:
    def __init__(self, *, fail: bool = False, stream: bool = False) -> None:
        self.fail = fail
        self.stream = stream
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

    def stream_complete(self, *, messages, temperature, max_tokens):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
        )
        if self.fail:
            raise ModelClientError("LLM_PROVIDER_UNAVAILABLE", "provider unavailable")
        yield ChatCompletionChunk(content_delta="员工年假")
        yield ChatCompletionChunk(content_delta="需要提前申请。")
        yield ChatCompletionChunk(
            content_delta="[source:chunk_1]",
            token_usage={"prompt_tokens": 12, "completion_tokens": 6},
        )


class _ThinkingChatClient:
    def complete(self, *, messages, temperature, max_tokens) -> ChatCompletionResult:
        return ChatCompletionResult(
            content="<think>先分析内部资料。</think>\n员工年假需要提前申请。[source:chunk_1]",
            token_usage={"prompt_tokens": 12, "completion_tokens": 12},
        )

    def stream_complete(self, *, messages, temperature, max_tokens):
        yield ChatCompletionChunk(content_delta="<thi")
        yield ChatCompletionChunk(content_delta="nk>先分析")
        yield ChatCompletionChunk(content_delta="内部资料。</think>\n员工")
        yield ChatCompletionChunk(content_delta="年假需要提前申请。")
        yield ChatCompletionChunk(content_delta="[source:chunk_1]")


class _ThinkingOnlyChatClient:
    def complete(self, *, messages, temperature, max_tokens) -> ChatCompletionResult:
        return ChatCompletionResult(
            content="<think>只有内部推理，没有最终答案。</think>",
            token_usage={"prompt_tokens": 12, "completion_tokens": 8},
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
    assert "不要输出 [source:无相关资料]" in messages[0].content
    assert "本次允许引用的 source id：chunk_1" in messages[1].content
    assert "[source:chunk_1]" in messages[1].content
    assert "员工年假需要提前申请" in messages[1].content


def test_answer_service_strips_thinking_blocks_from_answer() -> None:
    result = AnswerService(chat_client=_ThinkingChatClient()).generate(
        query_context=_query_context()
    )

    assert result.answer == "员工年假需要提前申请。[source:chunk_1]"
    assert "<think>" not in result.answer
    assert "先分析" not in result.answer


def test_answer_service_degrades_when_filtered_answer_is_empty() -> None:
    result = AnswerService(chat_client=_ThinkingOnlyChatClient()).generate(
        query_context=_query_context()
    )

    assert result.answer == ""
    assert result.degraded is True
    assert result.degrade_reason == "LLM_PROVIDER_RESPONSE_INVALID"
    assert result.token_usage == {"prompt_tokens": 12, "completion_tokens": 8}


def test_answer_service_streams_answer_from_query_context() -> None:
    chat_client = _ChatClient(stream=True)
    runner = AnswerService(
        chat_client=chat_client,
        temperature=0.2,
        max_tokens=256,
    ).stream(query_context=_query_context())

    tokens = list(runner.stream_tokens())

    assert tokens == ["员工年假", "需要提前申请。"]
    assert runner.result is not None
    assert runner.result.answer == "员工年假需要提前申请。[source:chunk_1]"
    assert runner.result.degraded is False
    assert runner.result.token_usage == {"prompt_tokens": 12, "completion_tokens": 6}
    assert chat_client.calls[0]["stream"] is True


def test_answer_service_stream_filters_thinking_blocks() -> None:
    runner = AnswerService(chat_client=_ThinkingChatClient()).stream(
        query_context=_query_context()
    )

    tokens = list(runner.stream_tokens())

    assert "".join(tokens) == "员工年假需要提前申请。"
    assert runner.result is not None
    assert runner.result.answer == "员工年假需要提前申请。[source:chunk_1]"
    assert "<think>" not in runner.result.answer
    assert "先分析" not in runner.result.answer


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
