"""User-facing degraded answer policy for query workflows."""

from __future__ import annotations


def degraded_answer(
    *,
    query_text: str,
    degrade_reasons: tuple[str, ...],
    citation_count: int,
    candidate_count: int,
) -> str:
    reason_messages = degrade_reason_messages(degrade_reasons)
    query_summary = brief_query(query_text)
    if citation_count > 0:
        retrieval_summary = (
            f"系统找到了 {citation_count} 条当前账号可访问的引用资料，"
            "但没有生成可直接采信的业务答案。"
        )
        next_step = "你可以先查看下方引用资料，或换一种更具体的问题重新查询。"
    elif candidate_count > 0:
        retrieval_summary = (
            "系统找到了一些候选片段，但这些片段没有形成可用于回答的最终上下文。"
        )
        next_step = "请检查相关文档是否已完成索引、权限快照是否已刷新，或缩小问题范围后重试。"
    else:
        retrieval_summary = (
            "系统没有在当前账号可访问、已发布且已索引的知识库内容中找到匹配资料。"
        )
        next_step = "请确认知识库中已有可访问文档、文档已索引完成，或选择其他知识库后重试。"

    return "\n".join(
        [
            f"我没有得到可以直接回答“{query_summary}”的可靠答案。",
            f"本次处理结果：{retrieval_summary}",
            f"没有答案的原因：{'；'.join(reason_messages)}。",
            next_step,
        ]
    )


def degrade_reason_messages(reasons: tuple[str, ...]) -> tuple[str, ...]:
    messages: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        message = degrade_reason_message(reason)
        if message in seen:
            continue
        seen.add(message)
        messages.append(message)
    return tuple(messages) or ("系统进入降级流程，但没有提供更具体的原因",)


def degrade_reason_message(reason: str) -> str:
    if reason == "query_scope_empty":
        return "当前账号没有可用于问答检索的知识库"
    if reason == "llm_context_empty":
        return "没有可用于生成答案的上下文，通常是文档为空、未检索到内容或权限过滤后无可用片段"
    if reason == "llm_runtime_config_unavailable":
        return "回答生成服务未完成可用配置"
    if reason == "llm_stream_result_missing":
        return "流式回答结束时没有得到有效的模型输出"
    if reason == "citation_missing":
        return "模型生成的回答缺少可验证引用，系统已拦截原回答"
    if reason == "citation_auto_attached":
        return "模型生成的回答缺少引用标记，系统已自动附加本次已授权来源"
    if reason == "citation_invalid_format":
        return "模型生成的回答使用了不存在的引用占位符，系统已拦截原回答"
    if reason == "citation_unauthorized":
        return "模型生成的回答引用了本次查询未授权或未命中的资料，系统已拦截原回答"
    if reason in {
        "vector_retriever_unavailable",
        "vector_runtime_config_unavailable",
        "vector_runtime_config_incomplete",
    }:
        return "向量检索能力不可用，本次只能依赖关键词检索"
    if reason == "vector_collection_unavailable":
        return "当前知识库没有可用的向量集合"
    if reason == "query_embedding_failed":
        return "问题向量化失败，本次只能依赖关键词检索"
    if reason == "vector_search_failed":
        return "向量数据库检索失败，本次只能依赖关键词检索"
    if reason == "retrieval_relevance_too_low":
        return "召回片段与问题相关性过低，系统未将这些片段交给模型生成答案"
    if reason == "retrieval_quality_too_low":
        return "检索到的片段与问题相关性过低，系统未将这些片段交给模型生成答案"
    if reason in {
        "RERANK_PROVIDER_UNAVAILABLE",
        "RERANK_PROVIDER_HTTP_ERROR",
        "RERANK_PROVIDER_RESPONSE_INVALID",
        "QUERY_RERANK_INPUT_UNAVAILABLE",
        "rerank_input_mismatch",
    }:
        return "候选精排不可用，系统已使用检索排序继续处理"
    if reason in {
        "LLM_PROVIDER_HTTP_ERROR",
        "LLM_PROVIDER_UNAVAILABLE",
        "LLM_PROVIDER_RESPONSE_INVALID",
    }:
        return "回答生成模型不可用、超时或返回异常"
    return f"系统降级原因代码为 {reason}"


def brief_query(query_text: str, *, limit: int = 80) -> str:
    compact = " ".join(query_text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."
