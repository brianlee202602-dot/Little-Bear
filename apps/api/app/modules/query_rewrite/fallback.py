"""规则式 Query Rewrite fallback。"""

from __future__ import annotations

import re

from app.modules.query_rewrite.schemas import (
    QueryRewriteInput,
    QueryRewriteItem,
    RewriteConversationMessage,
)

FILLER_PATTERNS = (
    r"^我想(?:要)?",
    r"^我希望",
    r"^帮我",
    r"^请问",
    r"^麻烦",
    r"^想问一下",
    r"^问一下",
)
QUESTION_SUFFIX_PATTERN = re.compile(r"[？?。.\s]+$")
COMPOSITE_SPLIT_PATTERN = re.compile(
    r"(?:，|,|；|;|、|分别是|分别|以及|还有|另外|并且|同时|和|与)"
)
SELF_CONTAINED_QUESTION_PATTERN = re.compile(
    r"^(?:什么是|什么叫|何为|如何|怎么|怎样|为什么|是否|能否|可以|请问)"
)
SHORT_REFERENCE_PATTERN = re.compile(
    r"^(?:那|那么|这个|那个|它|他们|预算|流程|材料|审批|限制|条件|费用).{0,18}$"
)


def fallback_rewrite(input_data: QueryRewriteInput) -> tuple[QueryRewriteItem, ...]:
    original = _compact(input_data.original_query)
    contextual = _contextualize_short_query(
        original,
        conversation_messages=input_data.conversation_messages,
    )
    candidates = [contextual]
    candidates.extend(_split_composite_query(contextual))
    return _normalize_items(candidates, max_queries=input_data.max_queries)


def _contextualize_short_query(
    query: str,
    *,
    conversation_messages: tuple[RewriteConversationMessage, ...],
) -> str:
    if not query or len(query) > 24 or not SHORT_REFERENCE_PATTERN.search(query):
        return query
    antecedent = _last_user_query(conversation_messages)
    if not antecedent:
        return query
    topic = _topic_summary(antecedent)
    if not topic or topic in query:
        return query
    return _compact(f"{topic} {query}")


def _last_user_query(messages: tuple[RewriteConversationMessage, ...]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        content = _compact(message.content)
        if content:
            return content
    return ""


def _topic_summary(value: str, *, limit: int = 48) -> str:
    compact = _strip_fillers(value)
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip()


def _split_composite_query(query: str) -> list[str]:
    parts = [_strip_fillers(part) for part in COMPOSITE_SPLIT_PATTERN.split(query)]
    meaningful = [part for part in parts if len(part) >= 3]
    if len(meaningful) <= 1:
        return []
    prefix = _shared_prefix(query, meaningful)
    rewritten: list[str] = []
    for part in meaningful:
        if (
            prefix
            and prefix not in part
            and len(part) <= 24
            and not SELF_CONTAINED_QUESTION_PATTERN.search(part)
        ):
            rewritten.append(_compact(f"{prefix} {part}"))
        else:
            rewritten.append(part)
    return rewritten


def _shared_prefix(query: str, parts: list[str]) -> str:
    first = parts[0]
    if len(first) <= 18:
        return first
    for marker in ("项目", "流程", "制度", "申请", "管理", "采购"):
        index = first.find(marker)
        if index >= 1:
            return first[: index + len(marker)]
    if "，" in query:
        return query.split("，", maxsplit=1)[0][:24]
    return ""


def _normalize_items(values: list[str], *, max_queries: int) -> tuple[QueryRewriteItem, ...]:
    seen: set[str] = set()
    items: list[QueryRewriteItem] = []
    for index, value in enumerate(values):
        query = _strip_fillers(value)
        if not query or query in seen:
            continue
        seen.add(query)
        items.append(
            QueryRewriteItem(
                query=query,
                intent="original" if index == 0 else "sub_query",
                weight=1.0 if index == 0 else 0.85,
            )
        )
        if len(items) >= max(max_queries, 1):
            break
    return tuple(items)


def _strip_fillers(value: str) -> str:
    result = _compact(value)
    for pattern in FILLER_PATTERNS:
        result = re.sub(pattern, "", result).strip()
    return QUESTION_SUFFIX_PATTERN.sub("", result).strip()


def _compact(value: str) -> str:
    return " ".join(value.split()).strip()
