"""答案生成模块内部数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerGenerationResult:
    answer: str
    degraded: bool
    degrade_reason: str | None
    token_usage: dict[str, int] | None = None
