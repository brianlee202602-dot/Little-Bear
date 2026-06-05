ENV_FILE ?= .env
COMPOSE ?= docker compose
PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
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
SMOKE_RECORD_PATH ?=
QUERY_REGRESSION_DATASET ?= docs/examples/query-regression.p0.jsonl
QUERY_REGRESSION_RECORD_PATH ?= artifacts/query-regression-latest.json
RAG_REGRESSION_DATASET ?= docs/examples/query-regression.rag-enhancement.jsonl
RAG_REGRESSION_RECORD_PATH ?= artifacts/query-regression-rag-latest.json
REGRESSION_KB_ID ?= $(SMOKE_KB_ID)
REGRESSION_TIMEOUT_SECONDS ?= 30
BACKUP_DIR ?= artifacts/backups
BACKUP_TIMESTAMP ?= $(shell date +%Y%m%d-%H%M%S)
PG_BACKUP_FILE ?= $(BACKUP_DIR)/postgres-$(BACKUP_TIMESTAMP).dump

define env_shell
set -a; [ ! -f "./$(ENV_FILE)" ] || . "./$(ENV_FILE)"; set +a;
endef

.PHONY: env up down restart ps logs clean reset db-upgrade db-current setup-secrets setup-secrets-verify setup-qdrant-secret setup-qdrant-secret-verify secrets-list pg-backup api worker web admin test smoke-p0 smoke-p0-record query-regression-p0 query-regression-rag release-smoke-p0 test-integration-qdrant

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

setup-secrets: env
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets put secret://rag/minio/access-key --value-env SECRET_INIT_MINIO_ACCESS_KEY
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets put secret://rag/minio/secret-key --value-env SECRET_INIT_MINIO_SECRET_KEY
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets put secret://rag/auth/jwt-signing-key --value-env SECRET_INIT_JWT_SIGNING_KEY

setup-secrets-verify:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets verify secret://rag/minio/access-key
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets verify secret://rag/minio/secret-key
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets verify secret://rag/auth/jwt-signing-key

setup-qdrant-secret: env
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets put secret://rag/qdrant/api-key --value-env SECRET_INIT_QDRANT_API_KEY

setup-qdrant-secret-verify:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets verify secret://rag/qdrant/api-key

secrets-list:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m app.cli.secrets list

pg-backup:
	@mkdir -p "$(BACKUP_DIR)"
	$(COMPOSE) --env-file "$(ENV_FILE)" exec -T postgres sh -lc 'pg_dump -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -Fc' > "$(PG_BACKUP_FILE)"
	@echo "PostgreSQL backup written to $(PG_BACKUP_FILE)"

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
		LITTLE_BEAR_SMOKE_RECORD_PATH="$${LITTLE_BEAR_SMOKE_RECORD_PATH:-$(SMOKE_RECORD_PATH)}" \
		$(PYTHON) tools/p0_smoke.py

smoke-p0-record:
	$(MAKE) smoke-p0 SMOKE_RECORD_PATH=artifacts/p0-smoke-latest.json

query-regression-p0:
	$(env_shell) test -n "$${LITTLE_BEAR_REGRESSION_USERNAME:-$${LITTLE_BEAR_SMOKE_USERNAME:-$(SMOKE_USERNAME)}}" || (echo "LITTLE_BEAR_REGRESSION_USERNAME, LITTLE_BEAR_SMOKE_USERNAME or SMOKE_USERNAME is required for query-regression-p0" >&2; exit 2)
	$(env_shell) test -n "$${LITTLE_BEAR_REGRESSION_PASSWORD:-$${LITTLE_BEAR_SMOKE_PASSWORD:-$(SMOKE_PASSWORD)}}" || (echo "LITTLE_BEAR_REGRESSION_PASSWORD, LITTLE_BEAR_SMOKE_PASSWORD or SMOKE_PASSWORD is required for query-regression-p0" >&2; exit 2)
	$(env_shell) \
		PYTHONPATH=tools:apps/api \
		LITTLE_BEAR_API_URL="$${LITTLE_BEAR_API_URL:-$(SMOKE_API_URL)}" \
		LITTLE_BEAR_REGRESSION_USERNAME="$${LITTLE_BEAR_REGRESSION_USERNAME:-$${LITTLE_BEAR_SMOKE_USERNAME:-$(SMOKE_USERNAME)}}" \
		LITTLE_BEAR_REGRESSION_PASSWORD="$${LITTLE_BEAR_REGRESSION_PASSWORD:-$${LITTLE_BEAR_SMOKE_PASSWORD:-$(SMOKE_PASSWORD)}}" \
		LITTLE_BEAR_REGRESSION_ENTERPRISE_CODE="$${LITTLE_BEAR_REGRESSION_ENTERPRISE_CODE:-$${LITTLE_BEAR_SMOKE_ENTERPRISE_CODE:-$(SMOKE_ENTERPRISE_CODE)}}" \
		LITTLE_BEAR_REGRESSION_KB_ID="$${LITTLE_BEAR_REGRESSION_KB_ID:-$(REGRESSION_KB_ID)}" \
		LITTLE_BEAR_QUERY_REGRESSION_DATASET="$${LITTLE_BEAR_QUERY_REGRESSION_DATASET:-$(QUERY_REGRESSION_DATASET)}" \
		LITTLE_BEAR_QUERY_REGRESSION_RECORD_PATH="$${LITTLE_BEAR_QUERY_REGRESSION_RECORD_PATH:-$(QUERY_REGRESSION_RECORD_PATH)}" \
		LITTLE_BEAR_REGRESSION_TIMEOUT_SECONDS="$${LITTLE_BEAR_REGRESSION_TIMEOUT_SECONDS:-$(REGRESSION_TIMEOUT_SECONDS)}" \
		$(PYTHON) tools/query_regression.py

query-regression-rag:
	$(MAKE) query-regression-p0 \
		QUERY_REGRESSION_DATASET="$(RAG_REGRESSION_DATASET)" \
		QUERY_REGRESSION_RECORD_PATH="$(RAG_REGRESSION_RECORD_PATH)"

release-smoke-p0: smoke-p0-record query-regression-p0

test-integration-qdrant:
	$(env_shell) LITTLE_BEAR_RUN_QDRANT_INTEGRATION=1 PYTHONPATH=apps/api $(PYTHON) -m pytest -q tests/integration/test_qdrant_indexing_flow.py
