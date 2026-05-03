from __future__ import annotations

import logging
import os
import signal
import time


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

    LOGGER.info("worker started")
    while not stop:
        # 任务领取和阶段推进逻辑后续由 Import Service 实现。
        time.sleep(2)
    LOGGER.info("worker stopped")


if __name__ == "__main__":
    main()
