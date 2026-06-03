"""Query Rewrite LLM prompt。"""

from __future__ import annotations

from app.modules.models import ChatMessage
from app.modules.query_rewrite.schemas import QueryRewriteInput

SYSTEM_PROMPT = """你只负责把用户问题改写为检索 query。
不要回答问题。
不要生成事实。
不要扩展到用户没有提到的业务领域。
每个 query 必须适合在企业知识库中检索。
输出严格 JSON，不要输出 markdown。
格式：
{"queries":[{"query":"...","intent":"...","weight":1.0}]}"""


def rewrite_messages(input_data: QueryRewriteInput) -> tuple[ChatMessage, ...]:
    history_lines = []
    for message in input_data.conversation_messages:
        role = "用户" if message.role == "user" else "助手"
        history_lines.append(f"{role}: {message.content}")
    history = "\n".join(history_lines[-6:]) if history_lines else "无"
    user_prompt = "\n".join(
        [
            f"最多返回 {max(input_data.max_queries, 1)} 个 query。",
            "如果用户问题包含多个子问题，请拆成多个 query。",
            "保留原始问题的核心实体和业务对象。",
            "最近会话仅用于补全“这个/那个/预算呢”等指代，不要把助手回答当作事实。",
            "",
            f"最近会话：\n{history}",
            "",
            f"用户当前问题：{input_data.original_query}",
        ]
    )
    return (
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    )
