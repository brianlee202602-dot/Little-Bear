from __future__ import annotations

# ruff: noqa: E402, I001

import logging
import os
import signal
import sys
import time
from pathlib import Path

API_PATH = Path(__file__).resolve().parents[2] / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from app.db.session import session_scope  # noqa: E402
from app.modules.import_pipeline.errors import ImportServiceError  # noqa: E402
from app.modules.import_pipeline.runtime import build_import_service  # noqa: E402


LOGGER = logging.getLogger("little_bear.worker")


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    configure_logging()
    stop = False

    def handle_stop(signum: int, _frame: object) -> None:
        nonlocal stop
        LOGGER.info("received stop signal", extra={"signal": signum})
        stop = True

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    worker_id = os.getenv("WORKER_ID") or f"worker-{os.getpid()}"
    poll_interval_seconds = float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2"))
    lock_seconds = int(os.getenv("WORKER_LOCK_SECONDS", "60"))
    stage_interval_seconds = float(os.getenv("WORKER_STAGE_INTERVAL_SECONDS", "0"))

    LOGGER.info("worker started", extra={"worker_id": worker_id})
    while not stop:
        try:
            with session_scope() as session:
                service = build_import_service(session)
                job = service.claim_next_job(
                    session,
                    worker_id=worker_id,
                    lock_seconds=lock_seconds,
                )
            if job is None:
                time.sleep(poll_interval_seconds)
                continue

            while not stop and job.status == "running":
                try:
                    with session_scope() as session:
                        service = build_import_service(session)
                        service.heartbeat_claimed_job(
                            session,
                            job_id=job.id,
                            worker_id=worker_id,
                            lock_seconds=lock_seconds,
                        )
                        advanced = service.advance_claimed_job(
                            session,
                            job_id=job.id,
                            worker_id=worker_id,
                        )
                except ImportServiceError as exc:
                    with session_scope() as session:
                        service = build_import_service(session)
                        job = service.mark_claimed_job_failed(
                            session,
                            job_id=job.id,
                            worker_id=worker_id,
                            error_code=exc.error_code,
                            error_message=exc.message,
                            retryable=exc.retryable,
                        )
                    LOGGER.warning(
                        "import job marked failed",
                        extra={
                            "worker_id": worker_id,
                            "job_id": job.id,
                            "status": job.status,
                            "stage": job.stage,
                            "error_code": exc.error_code,
                            "retryable": exc.retryable,
                        },
                    )
                    break
                LOGGER.info(
                    "import job advanced",
                    extra={
                        "worker_id": worker_id,
                        "job_id": advanced.id,
                        "status": advanced.status,
                        "stage": advanced.stage,
                    },
                )
                job = advanced
                if job.status == "running" and stage_interval_seconds > 0:
                    time.sleep(stage_interval_seconds)
        except ImportServiceError as exc:
            LOGGER.warning(
                "import job step failed",
                extra={
                    "worker_id": worker_id,
                    "error_code": exc.error_code,
                    "retryable": exc.retryable,
                },
            )
            time.sleep(poll_interval_seconds)
        except Exception:
            LOGGER.exception("worker loop crashed", extra={"worker_id": worker_id})
            time.sleep(poll_interval_seconds)
    LOGGER.info("worker stopped", extra={"worker_id": worker_id})


if __name__ == "__main__":
    main()
