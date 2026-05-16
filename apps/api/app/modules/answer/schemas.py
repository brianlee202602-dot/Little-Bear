"""答案生成模块内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerGenerationResult:
    answer: str
    degraded: bool
    degrade_reason: str | None
    token_usage: dict[str, int] | None = None
    model_call_attempted: bool = False
    model_type: str = "llm"
    model_name: str | None = None
    model_version: str | None = None
    model_route_hash: str | None = None
    latency_ms: int | None = None
    prompt_hash: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    error_message: str | None = None
