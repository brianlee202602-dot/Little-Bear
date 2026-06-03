#!/usr/bin/env python3
"""Run query regression cases against an initialized Little Bear environment."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from p0_smoke import (
    SmokeError,
    _first_id,
    _list,
    _parse_sse_events,
    _request_json,
    _request_text,
    _required_str,
)


@dataclass(frozen=True)
class RegressionConfig:
    base_url: str
    username: str
    password: str
    enterprise_code: str | None
    default_kb_id: str | None
    dataset_path: str
    record_path: str | None
    timeout_seconds: float


@dataclass(frozen=True)
class QueryCase:
    case_id: str
    query: str
    kb_ids: list[str]
    mode: str
    top_k: int
    include_sources: bool
    expect_answer: bool
    min_citations: int
    max_citations: int | None
    allow_degraded: bool
    expected_degrade_reasons: list[str]
    expected_answer_terms: list[str]
    forbidden_answer_terms: list[str]
    expected_citation_title_terms: list[str]
    expected_doc_ids: list[str]
    expected_source_ids: list[str]
    run_stream: bool


class RegressionError(Exception):
    pass


def main(argv: Sequence[str] | None = None) -> int:
    config = _parse_args(argv)
    started_perf = time.perf_counter()
    started_at = _utc_now()
    results: list[dict[str, Any]] = []
    status = "passed"
    error: str | None = None
    try:
        results = _run_regression(config)
    except (RegressionError, SmokeError) as exc:
        status = "failed"
        error = str(exc)
        print(f"query regression failed: {exc}", file=sys.stderr)
    finally:
        _write_record(
            config,
            status=status,
            error=error,
            started_at=started_at,
            duration_ms=round((time.perf_counter() - started_perf) * 1000, 2),
            results=results,
        )
    return 0 if status == "passed" else 1


def _run_regression(config: RegressionConfig) -> list[dict[str, Any]]:
    cases = _load_cases(config.dataset_path)
    if not cases:
        raise RegressionError(f"dataset has no query cases: {config.dataset_path}")

    token_response = _login(config)
    access_token = _required_str(token_response, "access_token")
    print(f"login=ok cases={len(cases)}")
    try:
        knowledge_bases = _load_knowledge_bases(config, access_token)
        default_kb_ids = _resolve_default_kb_ids(config, knowledge_bases)
        results: list[dict[str, Any]] = []
        failures = 0
        for raw_case in cases:
            query_case = _case_from_mapping(raw_case, default_kb_ids, knowledge_bases)
            result = _run_case(config, access_token, query_case)
            results.append(result)
            if result["status"] != "passed":
                failures += 1
            print(
                "case="
                f"{query_case.case_id} status={result['status']} "
                f"citations={result.get('citation_count', 0)} "
                f"degraded={result.get('degraded')} "
                f"degrade_reason={result.get('degrade_reason')}"
            )
        if failures:
            raise RegressionError(f"{failures}/{len(results)} query regression cases failed")
        return results
    finally:
        _logout(config, access_token)


def _run_case(
    config: RegressionConfig,
    access_token: str,
    query_case: QueryCase,
) -> dict[str, Any]:
    started_perf = time.perf_counter()
    payload = {
        "kb_ids": query_case.kb_ids,
        "query": query_case.query,
        "mode": query_case.mode,
        "filters": {},
        "top_k": query_case.top_k,
        "include_sources": query_case.include_sources,
    }
    result: dict[str, Any] = {
        "case_id": query_case.case_id,
        "status": "passed",
        "kb_ids": query_case.kb_ids,
        "query": query_case.query,
    }
    try:
        response = _request_json(
            "POST",
            f"{config.base_url}/internal/v1/queries",
            payload=payload,
            bearer_token=access_token,
            timeout_seconds=config.timeout_seconds,
        )
        citations = _list(response.get("citations"), f"{query_case.case_id}.citations")
        _validate_query_response(query_case, response, citations)
        result.update(
            {
                "debug_id": response.get("debug_id"),
                "degraded": response.get("degraded"),
                "degrade_reason": response.get("degrade_reason"),
                "confidence": response.get("confidence"),
                "answer_preview": str(response.get("answer") or "")[:500],
                "citation_count": len(citations),
                "citation_doc_ids": [_safe_str(citation, "doc_id") for citation in citations],
                "citation_source_ids": [
                    _safe_str(citation, "source_id") for citation in citations
                ],
                "citation_titles": [_safe_str(citation, "title") for citation in citations],
            }
        )
        if query_case.run_stream:
            result["stream"] = _run_stream_case(config, access_token, payload, query_case)
    except (RegressionError, SmokeError) as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
    result["duration_ms"] = round((time.perf_counter() - started_perf) * 1000, 2)
    return result


def _run_stream_case(
    config: RegressionConfig,
    access_token: str,
    payload: dict[str, Any],
    query_case: QueryCase,
) -> dict[str, Any]:
    stream_text = _request_text(
        "POST",
        f"{config.base_url}/internal/v1/query-streams",
        payload=payload,
        bearer_token=access_token,
        timeout_seconds=config.timeout_seconds,
    )
    events = _parse_sse_events(stream_text)
    event_names = [event["event"] for event in events]
    missing_events = [event for event in ("metadata", "done") if event not in event_names]
    if missing_events:
        raise RegressionError(
            f"{query_case.case_id}: stream missing events {','.join(missing_events)}"
        )
    citation_events = [event for event in events if event["event"] == "citation"]
    if query_case.min_citations > 0 and len(citation_events) < query_case.min_citations:
        raise RegressionError(
            f"{query_case.case_id}: stream citation events {len(citation_events)} "
            f"< expected {query_case.min_citations}"
        )
    if query_case.max_citations is not None and len(citation_events) > query_case.max_citations:
        raise RegressionError(
            f"{query_case.case_id}: stream citation events {len(citation_events)} "
            f"> expected {query_case.max_citations}"
        )
    done_events = [event for event in events if event["event"] == "done"]
    done_payload = done_events[-1]["data"] if done_events else {}
    if isinstance(done_payload, dict):
        done_citations = _list(
            done_payload.get("citations", citation_events),
            f"{query_case.case_id}.stream.done.citations",
        )
        _validate_query_response(query_case, done_payload, done_citations)
    return {
        "event_names": event_names,
        "citation_event_count": len(citation_events),
        "done_degraded": done_payload.get("degraded") if isinstance(done_payload, dict) else None,
        "done_degrade_reason": (
            done_payload.get("degrade_reason") if isinstance(done_payload, dict) else None
        ),
    }


def _validate_query_response(
    query_case: QueryCase,
    response: dict[str, Any],
    citations: list[Any],
) -> None:
    if not query_case.allow_degraded and response.get("degraded") is True:
        raise RegressionError(
            f"{query_case.case_id}: query degraded: {response.get('degrade_reason')}"
        )
    if not query_case.expect_answer and response.get("degraded") is not True:
        raise RegressionError(f"{query_case.case_id}: expected degraded no-answer response")

    missing_degrade_reasons = [
        reason
        for reason in query_case.expected_degrade_reasons
        if reason not in _degrade_reasons(response.get("degrade_reason"))
    ]
    if missing_degrade_reasons:
        raise RegressionError(
            f"{query_case.case_id}: degrade_reason missing {missing_degrade_reasons}"
        )

    if len(citations) < query_case.min_citations:
        raise RegressionError(
            f"{query_case.case_id}: citations {len(citations)} "
            f"< expected {query_case.min_citations}"
        )
    if query_case.max_citations is not None and len(citations) > query_case.max_citations:
        raise RegressionError(
            f"{query_case.case_id}: citations {len(citations)} "
            f"> expected {query_case.max_citations}"
        )

    answer = str(response.get("answer") or "")
    missing_answer_terms = [
        term for term in query_case.expected_answer_terms if term not in answer
    ]
    if missing_answer_terms:
        raise RegressionError(
            f"{query_case.case_id}: answer missing terms {missing_answer_terms}"
        )
    forbidden_answer_terms = [
        term for term in query_case.forbidden_answer_terms if term in answer
    ]
    if forbidden_answer_terms:
        raise RegressionError(
            f"{query_case.case_id}: answer unexpectedly contains terms "
            f"{forbidden_answer_terms}"
        )

    citation_doc_ids = {_safe_str(citation, "doc_id") for citation in citations}
    if query_case.expected_doc_ids and citation_doc_ids.isdisjoint(query_case.expected_doc_ids):
        raise RegressionError(
            f"{query_case.case_id}: citations did not include expected docs "
            f"{query_case.expected_doc_ids}"
        )

    citation_source_ids = {_safe_str(citation, "source_id") for citation in citations}
    if query_case.expected_source_ids and citation_source_ids.isdisjoint(
        query_case.expected_source_ids
    ):
        raise RegressionError(
            f"{query_case.case_id}: citations did not include expected sources "
            f"{query_case.expected_source_ids}"
        )

    citation_titles = [_safe_str(citation, "title") for citation in citations]
    for term in query_case.expected_citation_title_terms:
        if not any(term in title for title in citation_titles):
            raise RegressionError(
                f"{query_case.case_id}: citation titles missing term {term}"
            )


def _login(config: RegressionConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "username": config.username,
        "password": config.password,
    }
    if config.enterprise_code:
        payload["enterprise_code"] = config.enterprise_code
    return _request_json(
        "POST",
        f"{config.base_url}/internal/v1/sessions",
        payload=payload,
        timeout_seconds=config.timeout_seconds,
    )


def _logout(config: RegressionConfig, access_token: str) -> None:
    try:
        _request_text(
            "DELETE",
            f"{config.base_url}/internal/v1/sessions/current",
            bearer_token=access_token,
            timeout_seconds=config.timeout_seconds,
        )
    except SmokeError as exc:
        print(f"logout=skipped reason={exc}", file=sys.stderr)
    else:
        print("logout=ok")


def _load_knowledge_bases(config: RegressionConfig, access_token: str) -> list[Any]:
    kb_response = _request_json(
        "GET",
        f"{config.base_url}/internal/v1/knowledge-bases?page=1&page_size=100",
        bearer_token=access_token,
        timeout_seconds=config.timeout_seconds,
    )
    return _list(kb_response.get("data"), "knowledge-bases.data")


def _resolve_default_kb_ids(config: RegressionConfig, knowledge_bases: list[Any]) -> list[str]:
    if config.default_kb_id:
        return [config.default_kb_id]
    return [_first_id(knowledge_bases, "knowledge base")]


def _load_cases(path: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    dataset_path = Path(path)
    for line_no, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise RegressionError(f"{path}:{line_no} is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise RegressionError(f"{path}:{line_no} must be a JSON object")
        parsed.setdefault("case_id", f"line_{line_no}")
        cases.append(parsed)
    return cases


def _case_from_mapping(
    data: dict[str, Any],
    default_kb_ids: list[str],
    knowledge_bases: list[Any],
) -> QueryCase:
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise RegressionError(f"{data.get('case_id')}: query is required")
    kb_ids = _case_kb_ids(data, default_kb_ids, knowledge_bases)
    min_citations = max(_int_value(data.get("min_citations"), 0), 0)
    expected_answer_terms = _merge_string_lists(
        _string_list(data.get("expected_answer_terms"), default=[]),
        _string_list(data.get("required_keywords"), default=[]),
    )
    forbidden_answer_terms = _merge_string_lists(
        _string_list(data.get("forbidden_answer_terms"), default=[]),
        _string_list(data.get("forbidden_keywords"), default=[]),
    )
    expected_degrade_reasons = _string_list(data.get("expected_degrade_reasons"), default=[])
    expected_degrade_reason = data.get("expected_degrade_reason")
    if isinstance(expected_degrade_reason, str) and expected_degrade_reason.strip():
        expected_degrade_reasons = _merge_string_lists(
            expected_degrade_reasons,
            [expected_degrade_reason.strip()],
        )
    return QueryCase(
        case_id=str(data.get("case_id")),
        query=query.strip(),
        kb_ids=kb_ids,
        mode=_enum_value(data.get("mode"), {"answer", "search"}, "answer"),
        top_k=max(_int_value(data.get("top_k"), 8), 1),
        include_sources=_bool_value(data.get("include_sources"), True),
        expect_answer=_bool_value(data.get("expect_answer"), True),
        min_citations=min_citations,
        max_citations=_optional_int_value(data.get("max_citations")),
        allow_degraded=_bool_value(data.get("allow_degraded"), False),
        expected_degrade_reasons=expected_degrade_reasons,
        expected_answer_terms=expected_answer_terms,
        forbidden_answer_terms=forbidden_answer_terms,
        expected_citation_title_terms=_string_list(
            data.get("expected_citation_title_terms"),
            default=[],
        ),
        expected_doc_ids=_string_list(data.get("expected_doc_ids"), default=[]),
        expected_source_ids=_string_list(data.get("expected_source_ids"), default=[]),
        run_stream=_bool_value(data.get("run_stream"), False),
    )


def _case_kb_ids(
    data: dict[str, Any],
    default_kb_ids: list[str],
    knowledge_bases: list[Any],
) -> list[str]:
    explicit_ids = data.get("kb_ids")
    if explicit_ids is not None:
        # 显式空数组是有效输入：表示交给后端自动解析全部可访问知识库。
        return _explicit_string_list(explicit_ids, field_name="kb_ids")

    name_terms = _string_list(data.get("kb_name_terms"), default=[])
    if not name_terms:
        return list(default_kb_ids)

    matched: list[str] = []
    for knowledge_base in knowledge_bases:
        if not isinstance(knowledge_base, dict):
            continue
        kb_id = knowledge_base.get("id")
        name = knowledge_base.get("name")
        if not isinstance(kb_id, str) or not isinstance(name, str):
            continue
        if any(term in name for term in name_terms):
            matched.append(kb_id)
    if not matched:
        raise RegressionError(
            f"{data.get('case_id')}: no accessible knowledge base matched "
            f"kb_name_terms={name_terms}"
        )
    return matched


def _parse_args(argv: Sequence[str] | None) -> RegressionConfig:
    parser = argparse.ArgumentParser(description="Run Little Bear query regression cases.")
    parser.add_argument("--base-url", default=os.getenv("LITTLE_BEAR_API_URL", "http://localhost:8000"))
    parser.add_argument(
        "--username",
        default=os.getenv("LITTLE_BEAR_REGRESSION_USERNAME")
        or os.getenv("LITTLE_BEAR_SMOKE_USERNAME"),
    )
    parser.add_argument(
        "--password",
        default=os.getenv("LITTLE_BEAR_REGRESSION_PASSWORD")
        or os.getenv("LITTLE_BEAR_SMOKE_PASSWORD"),
    )
    parser.add_argument(
        "--enterprise-code",
        default=os.getenv("LITTLE_BEAR_REGRESSION_ENTERPRISE_CODE")
        or os.getenv("LITTLE_BEAR_SMOKE_ENTERPRISE_CODE"),
    )
    parser.add_argument(
        "--kb-id",
        default=os.getenv("LITTLE_BEAR_REGRESSION_KB_ID")
        or os.getenv("LITTLE_BEAR_SMOKE_KB_ID"),
    )
    parser.add_argument(
        "--dataset",
        default=os.getenv(
            "LITTLE_BEAR_QUERY_REGRESSION_DATASET",
            "docs/examples/query-regression.p0.jsonl",
        ),
    )
    parser.add_argument(
        "--record-path",
        default=os.getenv("LITTLE_BEAR_QUERY_REGRESSION_RECORD_PATH"),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("LITTLE_BEAR_REGRESSION_TIMEOUT_SECONDS", "30")),
    )
    args = parser.parse_args(argv)
    if not args.username:
        parser.error("--username or LITTLE_BEAR_REGRESSION_USERNAME is required")
    if not args.password:
        parser.error("--password or LITTLE_BEAR_REGRESSION_PASSWORD is required")
    return RegressionConfig(
        base_url=str(args.base_url).rstrip("/"),
        username=str(args.username),
        password=str(args.password),
        enterprise_code=args.enterprise_code,
        default_kb_id=args.kb_id,
        dataset_path=str(args.dataset),
        record_path=args.record_path,
        timeout_seconds=max(float(args.timeout_seconds), 1.0),
    )


def _write_record(
    config: RegressionConfig,
    *,
    status: str,
    error: str | None,
    started_at: str,
    duration_ms: float,
    results: list[dict[str, Any]],
) -> None:
    if not config.record_path:
        return
    path = Path(config.record_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "kind": "query_regression",
        "status": status,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "duration_ms": duration_ms,
        "config": {
            "base_url": config.base_url,
            "username": config.username,
            "enterprise_code": config.enterprise_code,
            "default_kb_id": config.default_kb_id,
            "dataset_path": config.dataset_path,
            "timeout_seconds": config.timeout_seconds,
        },
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result.get("status") == "passed"),
            "failed": sum(1 for result in results if result.get("status") != "passed"),
        },
        "results": results,
        "error": error,
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"record={path}")


def _string_list(value: Any, *, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if not isinstance(value, list):
        raise RegressionError("expected a list of strings")
    result = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return result or list(default)


def _explicit_string_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise RegressionError(f"{field_name} must be a list of strings")
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _int_value(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise RegressionError("expected integer, got boolean")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RegressionError(f"expected integer, got {value!r}") from exc


def _optional_int_value(value: Any) -> int | None:
    if value is None:
        return None
    return max(_int_value(value, 0), 0)


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise RegressionError(f"expected boolean, got {value!r}")


def _enum_value(value: Any, allowed: set[str], default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str) and value in allowed:
        return value
    raise RegressionError(f"expected one of {sorted(allowed)}, got {value!r}")


def _safe_str(value: Any, key: str) -> str:
    if isinstance(value, dict):
        item = value.get(key)
        return item if isinstance(item, str) else ""
    return ""


def _merge_string_lists(first: list[str], second: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*first, *second]:
        if item in seen:
            continue
        merged.append(item)
        seen.add(item)
    return merged


def _degrade_reasons(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {item.strip() for item in value.split(";") if item.strip()}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
