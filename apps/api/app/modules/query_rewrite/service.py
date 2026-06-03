"""Query Rewrite 服务。"""

from __future__ import annotations

import json
import re
import time

from app.modules.models import ChatCompletionClient, ModelClientError
from app.modules.query_rewrite.fallback import fallback_rewrite
from app.modules.query_rewrite.prompt import rewrite_messages
from app.modules.query_rewrite.schemas import (
    QueryRewriteInput,
    QueryRewriteItem,
    QueryRewriteResult,
)
from app.modules.retrieval import RetrievalModelCall
from app.shared.json_utils import stable_json_hash

CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class QueryRewriteService:
    """把用户原始问题改写为一个或多个检索 query。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        chat_client: ChatCompletionClient | None = None,
        max_queries: int = 4,
        max_query_chars: int = 120,
        use_conversation: bool = True,
        recent_messages: int = 6,
        max_tokens: int = 512,
    ) -> None:
        self.enabled = enabled
        self.chat_client = chat_client
        # P1 只允许有限 query 扇出，避免复合问题把关键词/向量召回成本线性放大。
        self.max_queries = min(max(max_queries, 1), 5)
        self.max_query_chars = min(max(max_query_chars, 20), 300)
        self.use_conversation = use_conversation
        self.recent_messages = min(max(recent_messages, 0), 20)
        self.max_tokens = max(max_tokens, 64)

    def rewrite(self, input_data: QueryRewriteInput) -> QueryRewriteResult:
        normalized_input = QueryRewriteInput(
            original_query=input_data.original_query,
            conversation_messages=(
                input_data.conversation_messages[-self.recent_messages :]
                if self.use_conversation and self.recent_messages > 0
                else ()
            ),
            max_queries=min(max(input_data.max_queries, 1), self.max_queries),
            locale=input_data.locale,
        )
        fallback_items = self._fallback_items(normalized_input)
        if not self.enabled or self.chat_client is None:
            return QueryRewriteResult(
                original_query=normalized_input.original_query,
                rewritten_queries=fallback_items,
            )

        messages = rewrite_messages(normalized_input)
        started_at = time.monotonic()
        prompt_hash = stable_json_hash(
            {
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ]
            }
        )
        input_hash = stable_json_hash(
            {
                "query": normalized_input.original_query,
                "history_count": len(normalized_input.conversation_messages),
                "max_queries": normalized_input.max_queries,
            }
        )
        try:
            response = self.chat_client.complete(
                messages=messages,
                temperature=0.0,
                max_tokens=self.max_tokens,
            )
            parsed_items = self._items_from_model_response(response.content, normalized_input)
        except ModelClientError as exc:
            return QueryRewriteResult(
                original_query=normalized_input.original_query,
                rewritten_queries=fallback_items,
                degraded=True,
                degrade_reason=exc.error_code,
                model_call=self._failed_model_call(
                    started_at=started_at,
                    prompt_hash=prompt_hash,
                    input_hash=input_hash,
                    error_code=exc.error_code,
                ),
            )
        except ValueError:
            return QueryRewriteResult(
                original_query=normalized_input.original_query,
                rewritten_queries=fallback_items,
                degraded=True,
                degrade_reason="QUERY_REWRITE_RESPONSE_INVALID",
                model_call=self._failed_model_call(
                    started_at=started_at,
                    prompt_hash=prompt_hash,
                    input_hash=input_hash,
                    error_code="QUERY_REWRITE_RESPONSE_INVALID",
                ),
            )

        items = self._merge_items(fallback_items[:1], parsed_items, normalized_input)
        return QueryRewriteResult(
            original_query=normalized_input.original_query,
            rewritten_queries=items,
            model_call=RetrievalModelCall(
                model_type="query_rewrite",
                model_name=self._model_name(),
                model_version=None,
                model_route_hash=self._model_route_hash(),
                status="success",
                degraded=False,
                latency_ms=_elapsed_ms(started_at),
                token_usage=response.token_usage,
                prompt_hash=prompt_hash,
                input_hash=input_hash,
                output_hash=stable_json_hash({"queries": [item.query for item in items]}),
            ),
        )

    def _fallback_items(self, input_data: QueryRewriteInput) -> tuple[QueryRewriteItem, ...]:
        items = fallback_rewrite(input_data)
        if items:
            return self._merge_items((), items, input_data)
        return (
            QueryRewriteItem(
                query=self._truncate_query(input_data.original_query),
                intent="original",
                weight=1.0,
            ),
        )

    def _items_from_model_response(
        self,
        content: str,
        input_data: QueryRewriteInput,
    ) -> tuple[QueryRewriteItem, ...]:
        payload = json.loads(_strip_code_fence(content))
        if not isinstance(payload, dict):
            raise ValueError("rewrite response must be object")
        raw_queries = payload.get("queries")
        if not isinstance(raw_queries, list):
            raise ValueError("rewrite response must contain queries")
        items: list[QueryRewriteItem] = []
        for raw_item in raw_queries:
            if not isinstance(raw_item, dict):
                continue
            query = raw_item.get("query")
            if not isinstance(query, str) or not query.strip():
                continue
            intent = raw_item.get("intent")
            weight = raw_item.get("weight")
            items.append(
                QueryRewriteItem(
                    query=self._truncate_query(query),
                    intent=intent if isinstance(intent, str) and intent.strip() else "model",
                    weight=float(weight) if isinstance(weight, int | float) else 0.9,
                )
            )
        if not items:
            raise ValueError("rewrite response produced no queries")
        return self._merge_items((), tuple(items), input_data)

    def _merge_items(
        self,
        first_items: tuple[QueryRewriteItem, ...],
        other_items: tuple[QueryRewriteItem, ...],
        input_data: QueryRewriteInput,
    ) -> tuple[QueryRewriteItem, ...]:
        seen: set[str] = set()
        merged: list[QueryRewriteItem] = []
        for item in (*first_items, *other_items):
            query = self._truncate_query(item.query)
            if not query or query in seen:
                continue
            seen.add(query)
            merged.append(
                QueryRewriteItem(
                    query=query,
                    intent=item.intent,
                    weight=max(min(float(item.weight), 1.0), 0.1),
                )
            )
            if len(merged) >= min(max(input_data.max_queries, 1), self.max_queries):
                break
        return tuple(merged)

    def _truncate_query(self, query: str) -> str:
        compact = " ".join(query.split()).strip()
        if len(compact) <= self.max_query_chars:
            return compact
        return compact[: self.max_query_chars].rstrip()

    def _failed_model_call(
        self,
        *,
        started_at: float,
        prompt_hash: str,
        input_hash: str,
        error_code: str,
    ) -> RetrievalModelCall:
        return RetrievalModelCall(
            model_type="query_rewrite",
            model_name=self._model_name(),
            model_version=None,
            model_route_hash=self._model_route_hash(),
            status="failed",
            degraded=True,
            latency_ms=_elapsed_ms(started_at),
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            error_code=error_code,
        )

    def _model_name(self) -> str:
        value = getattr(self.chat_client, "model", None)
        return value if isinstance(value, str) and value else "unknown"

    def _model_route_hash(self) -> str:
        return stable_json_hash(
            {
                "base_url": getattr(self.chat_client, "base_url", None),
                "path": getattr(self.chat_client, "path", None),
                "model": self._model_name(),
                "purpose": "query_rewrite",
            }
        )


def _strip_code_fence(content: str) -> str:
    return CODE_FENCE_PATTERN.sub("", content.strip()).strip()


def _elapsed_ms(started_at: float) -> int:
    return max(int((time.monotonic() - started_at) * 1000), 0)
