ENV_FILE ?= .env
COMPOSE ?= docker compose
PYTHON ?= python3
API_HOST ?= 0.0.0.0
API_PORT ?= 8000
LOG_LEVEL ?= INFO

define env_shell
set -a; [ ! -f "./.env" ] || . "./.env"; set +a;
endef

.PHONY: env up down restart ps logs clean reset db-upgrade db-current api web admin test test-integration-qdrant

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

web:
	npm run dev:web

admin:
	npm run dev:admin

test:
	$(env_shell)

test-integration-qdrant:
	$(env_shell) LITTLE_BEAR_RUN_QDRANT_INTEGRATION=1 PYTHONPATH=apps/api $(PYTHON) -m pytest -q tests/integration/test_qdrant_indexing_flow.py
