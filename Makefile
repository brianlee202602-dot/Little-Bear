ENV_FILE ?= .env
COMPOSE ?= docker compose
PYTHON ?= python3
API_HOST ?= 0.0.0.0
API_PORT ?= 8000
LOG_LEVEL ?= INFO
WORKER_ID ?=
WORKER_POLL_INTERVAL_SECONDS ?= 2
WORKER_LOCK_SECONDS ?= 60
WORKER_STAGE_INTERVAL_SECONDS ?= 0
SMOKE_API_URL ?= http://localhost:8000
SMOKE_USERNAME ?=
SMOKE_PASSWORD ?=
SMOKE_ENTERPRISE_CODE ?=
SMOKE_KB_ID ?=
SMOKE_QUERY ?= 员工手册
SMOKE_TOP_K ?= 8
SMOKE_REQUIRE_CITATIONS ?= 0
SMOKE_TIMEOUT_SECONDS ?= 30

define env_shell
set -a; [ ! -f "$(ENV_FILE)" ] || . "$(ENV_FILE)"; set +a;
endef

.PHONY: env up down restart ps logs clean reset db-upgrade db-current api worker web admin test smoke-p0 test-integration-qdrant

env:
	@if [ ! -f "$(ENV_FILE)" ]; then cp .env.example "$(ENV_FILE)"; fi

up: env
	$(COMPOSE) --env-file "$(ENV_FILE)" up -d

down:
	$(COMPOSE) --env-file "$(ENV_FILE)" down

restart: down up

ps:
	$(COMPOSE) --env-file "$(ENV_FILE)" ps

logs:
	$(COMPOSE) --env-file "$(ENV_FILE)" logs -f

clean:
	$(COMPOSE) --env-file "$(ENV_FILE)" down --remove-orphans

reset:
	$(COMPOSE) --env-file "$(ENV_FILE)" down --volumes --remove-orphans

db-upgrade:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m alembic.config upgrade head

db-current:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m alembic.config current

api:
	$(env_shell) PYTHONPATH=apps/api LOG_LEVEL="$(LOG_LEVEL)" $(PYTHON) -m uvicorn app.main:app --host "$(API_HOST)" --port "$(API_PORT)" --reload

worker:
	$(env_shell) PYTHONPATH=apps/api LOG_LEVEL="$(LOG_LEVEL)" WORKER_ID="$(WORKER_ID)" WORKER_POLL_INTERVAL_SECONDS="$(WORKER_POLL_INTERVAL_SECONDS)" WORKER_LOCK_SECONDS="$(WORKER_LOCK_SECONDS)" WORKER_STAGE_INTERVAL_SECONDS="$(WORKER_STAGE_INTERVAL_SECONDS)" $(PYTHON) apps/worker/app/main.py

worker-%:
	$(MAKE) worker WORKER_ID="worker-$*"

web:
	npm run dev:web

admin:
	npm run dev:admin

test:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m ruff check apps/api tests tools
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m pytest -q tests/unit

smoke-p0:
	$(env_shell) test -n "$${LITTLE_BEAR_SMOKE_USERNAME:-$(SMOKE_USERNAME)}" || (echo "LITTLE_BEAR_SMOKE_USERNAME or SMOKE_USERNAME is required for smoke-p0" >&2; exit 2)
	$(env_shell) test -n "$${LITTLE_BEAR_SMOKE_PASSWORD:-$(SMOKE_PASSWORD)}" || (echo "LITTLE_BEAR_SMOKE_PASSWORD or SMOKE_PASSWORD is required for smoke-p0" >&2; exit 2)
	$(env_shell) \
		PYTHONPATH=apps/api \
		LITTLE_BEAR_API_URL="$${LITTLE_BEAR_API_URL:-$(SMOKE_API_URL)}" \
		LITTLE_BEAR_SMOKE_USERNAME="$${LITTLE_BEAR_SMOKE_USERNAME:-$(SMOKE_USERNAME)}" \
		LITTLE_BEAR_SMOKE_PASSWORD="$${LITTLE_BEAR_SMOKE_PASSWORD:-$(SMOKE_PASSWORD)}" \
		LITTLE_BEAR_SMOKE_ENTERPRISE_CODE="$${LITTLE_BEAR_SMOKE_ENTERPRISE_CODE:-$(SMOKE_ENTERPRISE_CODE)}" \
		LITTLE_BEAR_SMOKE_KB_ID="$${LITTLE_BEAR_SMOKE_KB_ID:-$(SMOKE_KB_ID)}" \
		LITTLE_BEAR_SMOKE_QUERY="$${LITTLE_BEAR_SMOKE_QUERY:-$(SMOKE_QUERY)}" \
		LITTLE_BEAR_SMOKE_TOP_K="$${LITTLE_BEAR_SMOKE_TOP_K:-$(SMOKE_TOP_K)}" \
		LITTLE_BEAR_SMOKE_REQUIRE_CITATIONS="$${LITTLE_BEAR_SMOKE_REQUIRE_CITATIONS:-$(SMOKE_REQUIRE_CITATIONS)}" \
		LITTLE_BEAR_SMOKE_TIMEOUT_SECONDS="$${LITTLE_BEAR_SMOKE_TIMEOUT_SECONDS:-$(SMOKE_TIMEOUT_SECONDS)}" \
		$(PYTHON) tools/p0_smoke.py

test-integration-qdrant:
	$(env_shell) LITTLE_BEAR_RUN_QDRANT_INTEGRATION=1 PYTHONPATH=apps/api $(PYTHON) -m pytest -q tests/integration/test_qdrant_indexing_flow.py
