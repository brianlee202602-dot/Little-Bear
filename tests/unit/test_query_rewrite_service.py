from __future__ import annotations

import pytest
from app.modules.models import ChatCompletionResult, ChatMessage, ModelClientError
from app.modules.query_rewrite import (
    QueryRewriteInput,
    QueryRewriteService,
    RewriteConversationMessage,
)


class _RewriteChatClient:
    model = "qwen-rewrite"
    base_url = "https://llm.example"
    path = "/v1/chat/completions"

    def __init__(self, *, content: str = "", fail: bool = False) -> None:
        self.content = content
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        *,
        messages: tuple[ChatMessage, ...],
        temperature: float,
        max_tokens: int,
    ) -> ChatCompletionResult:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.fail:
            raise ModelClientError("LLM_PROVIDER_UNAVAILABLE", "provider unavailable")
        return ChatCompletionResult(content=self.content)


def test_rule_fallback_splits_composite_query_and_keeps_original() -> None:
    result = QueryRewriteService(chat_client=None, max_queries=4).rewrite(
        QueryRewriteInput(
            original_query="我想做采购项目，前期要准备什么，审批流程和预算限制分别是什么？",
            max_queries=4,
        )
    )

    queries = [item.query for item in result.rewritten_queries]
    assert queries[0] == "做采购项目，前期要准备什么，审批流程和预算限制分别是什么"
    assert "做采购项目 前期要准备什么" in queries
    assert "做采购项目 审批流程" in queries
    assert result.degraded is False
    assert result.model_call is None


def test_rule_fallback_keeps_self_contained_sub_questions() -> None:
    result = QueryRewriteService(chat_client=None, max_queries=4).rewrite(
        QueryRewriteInput(
            original_query="什么是 Can 协议，什么是 RAG",
            max_queries=4,
        )
    )

    queries = [item.query for item in result.rewritten_queries]
    assert queries == [
        "什么是 Can 协议，什么是 RAG",
        "什么是 Can 协议",
        "什么是 RAG",
    ]


def test_query_rewrite_caps_max_queries_to_five() -> None:
    service = QueryRewriteService(chat_client=None, max_queries=20)

    result = service.rewrite(
        QueryRewriteInput(
            original_query="采购项目材料、审批流程、预算限制、验收要求、合同归档、付款节点分别是什么",
            max_queries=20,
        )
    )

    assert service.max_queries == 5
    assert len(result.rewritten_queries) <= 5


def test_rule_fallback_uses_recent_user_history_for_short_reference() -> None:
    result = QueryRewriteService(chat_client=None, max_queries=3).rewrite(
        QueryRewriteInput(
            original_query="预算呢？",
            conversation_messages=(
                RewriteConversationMessage(role="user", content="采购项目怎么启动？"),
                RewriteConversationMessage(role="assistant", content="需要先提交立项材料。"),
            ),
            max_queries=3,
        )
    )

    assert result.rewritten_queries[0].query == "采购项目怎么启动 预算呢"


def test_llm_rewrite_parses_json_and_logs_success_model_call() -> None:
    client = _RewriteChatClient(
        content='{"queries":[{"query":"采购项目审批流程","intent":"approval","weight":0.9}]}'
    )

    result = QueryRewriteService(chat_client=client, max_queries=3).rewrite(
        QueryRewriteInput(original_query="采购项目审批和预算分别是什么", max_queries=3)
    )

    queries = [item.query for item in result.rewritten_queries]
    assert queries[0] == "采购项目审批和预算分别是什么"
    assert "采购项目审批流程" in queries
    assert result.degraded is False
    assert result.model_call is not None
    assert result.model_call.status == "success"
    assert result.model_call.model_type == "query_rewrite"
    assert client.calls[0]["temperature"] == 0.0


@pytest.mark.parametrize(
    ("content", "error_code"),
    [
        ("不是 JSON", "QUERY_REWRITE_RESPONSE_INVALID"),
        ('{"queries":[]}', "QUERY_REWRITE_RESPONSE_INVALID"),
    ],
)
def test_llm_rewrite_invalid_output_falls_back_to_rules(
    content: str,
    error_code: str,
) -> None:
    result = QueryRewriteService(
        chat_client=_RewriteChatClient(content=content),
        max_queries=3,
    ).rewrite(QueryRewriteInput(original_query="采购项目审批和预算分别是什么", max_queries=3))

    assert result.degraded is True
    assert result.degrade_reason == error_code
    assert result.model_call is not None
    assert result.model_call.status == "failed"
    assert result.rewritten_queries[0].query == "采购项目审批和预算分别是什么"


def test_llm_rewrite_provider_failure_falls_back_to_rules() -> None:
    result = QueryRewriteService(
        chat_client=_RewriteChatClient(fail=True),
        max_queries=3,
    ).rewrite(QueryRewriteInput(original_query="采购项目审批和预算分别是什么", max_queries=3))

    assert result.degraded is True
    assert result.degrade_reason == "LLM_PROVIDER_UNAVAILABLE"
    assert result.model_call is not None
    assert result.model_call.status == "failed"
    assert result.rewritten_queries[0].query == "采购项目审批和预算分别是什么"
