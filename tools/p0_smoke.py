#!/usr/bin/env python3
"""P0 查询闭环 smoke test。

该脚本面向已经初始化且已有 active 知识库/索引的环境，覆盖：
登录 -> 当前用户 -> 知识库浏览 -> 文档/来源浏览 -> 非流式查询 -> SSE 查询。

默认不创建业务数据，避免在共享环境里写入不可预期的文档。验收环境可以通过
--require-citations 强制要求查询返回 citation。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    username: str
    password: str
    enterprise_code: str | None
    kb_id: str | None
    query: str
    top_k: int
    require_citations: bool
    timeout_seconds: float


class SmokeError(Exception):
    pass


def main(argv: Sequence[str] | None = None) -> int:
    config = _parse_args(argv)
    try:
        _run_smoke(config)
    except SmokeError as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _run_smoke(config: SmokeConfig) -> None:
    print(f"api={config.base_url}")
    setup_state = _request_json(
        "GET",
        f"{config.base_url}/internal/v1/setup-state",
        timeout_seconds=config.timeout_seconds,
    )
    setup_data = _object(setup_state.get("data"), "setup-state.data")
    if setup_data.get("setup_required") is True:
        raise SmokeError("setup is still required")
    print("setup-state=ok")

    ready_response = _request_json(
        "GET",
        f"{config.base_url}/health/ready",
        timeout_seconds=config.timeout_seconds,
    )
    if ready_response.get("status") != "ready":
        raise SmokeError(f"health is not ready: {json.dumps(ready_response, ensure_ascii=False)}")
    print("health-ready=ok")

    login_payload: dict[str, Any] = {
        "username": config.username,
        "password": config.password,
    }
    if config.enterprise_code:
        login_payload["enterprise_code"] = config.enterprise_code
    token_response = _request_json(
        "POST",
        f"{config.base_url}/internal/v1/sessions",
        payload=login_payload,
        timeout_seconds=config.timeout_seconds,
    )
    access_token = _required_str(token_response, "access_token")
    print("login=ok")

    try:
        _run_authenticated_smoke(config, access_token)
    finally:
        _logout_current_session(config, access_token)


def _run_authenticated_smoke(config: SmokeConfig, access_token: str) -> None:
    user_response = _request_json(
        "GET",
        f"{config.base_url}/internal/v1/users/me",
        bearer_token=access_token,
        timeout_seconds=config.timeout_seconds,
    )
    user = _object(user_response.get("data"), "users.me.data")
    print(f"user={user.get('username', 'unknown')}")

    kb_response = _request_json(
        "GET",
        f"{config.base_url}/internal/v1/knowledge-bases?page=1&page_size=100",
        bearer_token=access_token,
        timeout_seconds=config.timeout_seconds,
    )
    knowledge_bases = _list(kb_response.get("data"), "knowledge-bases.data")
    selected_kb_id = config.kb_id or _first_id(knowledge_bases, "knowledge base")
    print(f"knowledge-bases={len(knowledge_bases)} selected={selected_kb_id}")

    documents_response = _request_json(
        "GET",
        (
            f"{config.base_url}/internal/v1/knowledge-bases/"
            f"{selected_kb_id}/documents?page=1&page_size=20"
        ),
        bearer_token=access_token,
        timeout_seconds=config.timeout_seconds,
    )
    documents = _list(documents_response.get("data"), "documents.data")
    print(f"documents={len(documents)}")
    if documents:
        document_id = _required_str(_object(documents[0], "documents[0]"), "id")
        chunks_response = _request_json(
            "GET",
            f"{config.base_url}/internal/v1/documents/{document_id}/chunks",
            bearer_token=access_token,
            timeout_seconds=config.timeout_seconds,
        )
        chunks = _list(chunks_response.get("data"), "chunks.data")
        print(f"chunks={len(chunks)} first_document={document_id}")

    query_payload = {
        "kb_ids": [selected_kb_id],
        "query": config.query,
        "mode": "answer",
        "filters": {},
        "top_k": config.top_k,
        "include_sources": True,
    }
    query_response = _request_json(
        "POST",
        f"{config.base_url}/internal/v1/queries",
        payload=query_payload,
        bearer_token=access_token,
        timeout_seconds=config.timeout_seconds,
    )
    citations = _list(query_response.get("citations"), "queries.citations")
    if config.require_citations and not citations:
        raise SmokeError("non-streaming query returned no citations")
    print(
        "query=ok "
        f"degraded={query_response.get('degraded')} citations={len(citations)} "
        f"trace_id={query_response.get('trace_id')}"
    )

    stream_text = _request_text(
        "POST",
        f"{config.base_url}/internal/v1/query-streams",
        payload=query_payload,
        bearer_token=access_token,
        timeout_seconds=config.timeout_seconds,
    )
    events = _parse_sse_events(stream_text)
    event_names = [event["event"] for event in events]
    for required_event in ("metadata", "done"):
        if required_event not in event_names:
            raise SmokeError(f"stream response missing {required_event} event")
    stream_citations = [event for event in events if event["event"] == "citation"]
    if config.require_citations and not stream_citations:
        raise SmokeError("streaming query returned no citation events")
    print(f"stream=ok events={','.join(event_names)}")
    print("smoke=passed")


def _logout_current_session(config: SmokeConfig, access_token: str) -> None:
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


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    bearer_token: str | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    text = _request_text(
        method,
        url,
        payload=payload,
        bearer_token=bearer_token,
        timeout_seconds=timeout_seconds,
    )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"response is not JSON for {url}") from exc
    if not isinstance(parsed, dict):
        raise SmokeError(f"response is not an object for {url}")
    return parsed


def _request_text(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    bearer_token: str | None = None,
    timeout_seconds: float,
) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    headers = {"accept": "application/json"}
    if body is not None:
        headers["content-type"] = "application/json"
    if bearer_token:
        headers["authorization"] = f"Bearer {bearer_token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"{method} {url} returned HTTP {exc.code}: {details}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise SmokeError(f"{method} {url} failed: {exc.__class__.__name__}") from exc


def _parse_sse_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in text.split("\n\n"):
        if not frame.strip():
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").lstrip())
        payload: Any = {}
        if data_lines:
            try:
                payload = json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
                payload = {"raw": "\n".join(data_lines)}
        events.append({"event": event_name, "data": payload})
    return events


def _parse_args(argv: Sequence[str] | None) -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Run Little Bear P0 smoke test.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("LITTLE_BEAR_API_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--username",
        default=os.getenv("LITTLE_BEAR_SMOKE_USERNAME"),
    )
    parser.add_argument(
        "--password",
        default=os.getenv("LITTLE_BEAR_SMOKE_PASSWORD"),
    )
    parser.add_argument(
        "--enterprise-code",
        default=os.getenv("LITTLE_BEAR_SMOKE_ENTERPRISE_CODE"),
    )
    parser.add_argument("--kb-id", default=os.getenv("LITTLE_BEAR_SMOKE_KB_ID"))
    parser.add_argument(
        "--query",
        default=os.getenv("LITTLE_BEAR_SMOKE_QUERY", "员工手册"),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=int(os.getenv("LITTLE_BEAR_SMOKE_TOP_K", "8")),
    )
    parser.add_argument(
        "--require-citations",
        action="store_true",
        default=os.getenv("LITTLE_BEAR_SMOKE_REQUIRE_CITATIONS") == "1",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("LITTLE_BEAR_SMOKE_TIMEOUT_SECONDS", "30")),
    )
    args = parser.parse_args(argv)
    if not args.username:
        parser.error("--username or LITTLE_BEAR_SMOKE_USERNAME is required")
    if not args.password:
        parser.error("--password or LITTLE_BEAR_SMOKE_PASSWORD is required")
    return SmokeConfig(
        base_url=str(args.base_url).rstrip("/"),
        username=str(args.username),
        password=str(args.password),
        enterprise_code=args.enterprise_code,
        kb_id=args.kb_id,
        query=str(args.query),
        top_k=max(int(args.top_k), 1),
        require_citations=bool(args.require_citations),
        timeout_seconds=max(float(args.timeout_seconds), 1.0),
    )


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SmokeError(f"{name} is not an object")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise SmokeError(f"{name} is not a list")
    return value


def _required_str(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise SmokeError(f"missing string field: {key}")
    return item


def _first_id(items: list[Any], name: str) -> str:
    if not items:
        raise SmokeError(f"no accessible {name}; create/import one or pass --kb-id")
    return _required_str(_object(items[0], f"{name}[0]"), "id")


if __name__ == "__main__":
    raise SystemExit(main())
