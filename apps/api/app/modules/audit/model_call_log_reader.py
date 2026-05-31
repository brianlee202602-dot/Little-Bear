"""模型调用日志读取。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.audit.errors import AuditServiceError
from app.modules.audit.schemas import ModelCallLog, ModelCallLogList
from app.shared.json_utils import as_dict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

MODEL_CALL_LOG_FILTER_FIELDS = {
    "request_id": "request_id",
    "trace_id": "trace_id",
    "caller": "caller",
    "model_type": "model_type",
    "status": "status",
    "error_code": "error_code",
}


class ModelCallLogReader:
    """读取模型网关调用日志。"""

    def list_model_call_logs(
        self,
        session: Session,
        *,
        enterprise_id: str,
        page: int,
        page_size: int,
        filters: dict[str, str | bool | None] | None = None,
    ) -> ModelCallLogList:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 200)
        conditions, params = _build_filter_conditions(filters or {})
        conditions.insert(0, "enterprise_id = CAST(:enterprise_id AS uuid)")
        params.update(
            {
                "enterprise_id": enterprise_id,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            }
        )
        where_sql = f"WHERE {' AND '.join(conditions)}"

        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT
                        id::text AS id,
                        caller,
                        model_type,
                        model_name,
                        model_version,
                        status,
                        latency_ms,
                        degraded,
                        error_code,
                        created_at
                    FROM model_call_logs
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            ).all()
            total_row = session.execute(
                text(f"SELECT count(*) AS total FROM model_call_logs {where_sql}"),
                params,
            ).one()
        except SQLAlchemyError as exc:
            raise AuditServiceError(
                "MODEL_CALL_LOG_UNAVAILABLE",
                "model call logs cannot be read",
                retryable=True,
                details={"error_type": exc.__class__.__name__},
            ) from exc

        return ModelCallLogList(
            items=[_model_call_log_from_mapping(dict(row._mapping)) for row in rows],
            total=int(total_row._mapping["total"]),
        )

    def get_model_call_log(
        self,
        session: Session,
        *,
        enterprise_id: str,
        model_call_log_id: str,
    ) -> ModelCallLog:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS id,
                        request_id,
                        trace_id,
                        caller,
                        model_type,
                        model_name,
                        model_version,
                        model_route_hash,
                        status,
                        latency_ms,
                        token_usage_json,
                        degraded,
                        config_version,
                        prompt_hash,
                        input_hash,
                        output_hash,
                        error_code,
                        created_at
                    FROM model_call_logs
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND id::text = :model_call_log_id
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id, "model_call_log_id": model_call_log_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise AuditServiceError(
                "MODEL_CALL_LOG_UNAVAILABLE",
                "model call log cannot be read",
                retryable=True,
                details={
                    "error_type": exc.__class__.__name__,
                    "model_call_log_id": model_call_log_id,
                },
            ) from exc

        if row is None:
            raise AuditServiceError(
                "MODEL_CALL_LOG_NOT_FOUND",
                "model call log does not exist",
                details={"model_call_log_id": model_call_log_id},
            )
        return _model_call_log_from_mapping(dict(row._mapping))


def _build_filter_conditions(
    filters: dict[str, str | bool | None],
) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    for field, column in MODEL_CALL_LOG_FILTER_FIELDS.items():
        value = filters.get(field)
        if not value:
            continue
        conditions.append(f"{column} = :{field}")
        params[field] = value
    degraded = filters.get("degraded")
    if isinstance(degraded, bool):
        conditions.append("degraded = :degraded")
        params["degraded"] = degraded
    model = filters.get("model")
    if isinstance(model, str) and model:
        conditions.append("(model_name ILIKE :model OR COALESCE(model_version, '') ILIKE :model)")
        params["model"] = f"%{model}%"
    return conditions, params


def _model_call_log_from_mapping(row: dict[str, Any]) -> ModelCallLog:
    token_usage = row.get("token_usage_json")
    return ModelCallLog(
        id=str(row["id"]),
        request_id=_optional_str(row.get("request_id")),
        trace_id=str(row.get("trace_id") or ""),
        caller=str(row["caller"]),
        model_type=str(row["model_type"]),
        model_name=str(row["model_name"]),
        model_version=_optional_str(row.get("model_version")),
        model_route_hash=str(row.get("model_route_hash") or ""),
        status=str(row["status"]),
        latency_ms=int(row["latency_ms"]),
        token_usage_json=as_dict(token_usage) if token_usage is not None else None,
        degraded=bool(row["degraded"]),
        config_version=_optional_int(row.get("config_version")),
        prompt_hash=_optional_str(row.get("prompt_hash")),
        input_hash=_optional_str(row.get("input_hash")),
        output_hash=_optional_str(row.get("output_hash")),
        error_code=_optional_str(row.get("error_code")),
        created_at=row.get("created_at") if isinstance(row.get("created_at"), datetime) else None,
    )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None

