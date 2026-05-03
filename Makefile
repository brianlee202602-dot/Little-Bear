ENV_FILE ?= .env

COMPOSE ?= docker compose
PYTHON ?= python3
POSTGRES_DB ?= little_bear
POSTGRES_USER ?= little_bear
API_HOST ?= 0.0.0.0
API_PORT ?= 8000
LOG_LEVEL ?= INFO

define env_shell
set -a; [ ! -f "$(ENV_FILE)" ] || . "$(ENV_FILE)"; set +a;
endef

.PHONY: env up down restart ps logs logs-model health clean reset api worker model-gateway web admin db-upgrade db-downgrade db-current

env:
	@if [ ! -f $(ENV_FILE) ]; then cp .env.example $(ENV_FILE); fi

up: env
	$(COMPOSE) --env-file $(ENV_FILE) up -d

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

restart: down up

ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

logs:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f

logs-model:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f model-gateway

health:
	@printf "postgres: "; $(COMPOSE) --env-file $(ENV_FILE) exec -T postgres pg_isready -U $(POSTGRES_USER) -d $(POSTGRES_DB)
	@printf "redis: "; $(COMPOSE) --env-file $(ENV_FILE) exec -T redis redis-cli ping
	@printf "minio: "; curl -fsS http://localhost:9000/minio/health/live >/dev/null && echo ok
	@printf "qdrant: "; curl -fsS http://localhost:6333/readyz >/dev/null && echo ok
	@printf "model-gateway: "; curl -fsS http://localhost:8080/internal/v1/model-health >/dev/null && echo ok

clean:
	$(COMPOSE) --env-file $(ENV_FILE) down --remove-orphans

reset:
	$(COMPOSE) --env-file $(ENV_FILE) down --volumes --remove-orphans

api:
	$(env_shell) PYTHONPATH=apps/api LOG_LEVEL="$(LOG_LEVEL)" $(PYTHON) -m uvicorn app.main:app --host "$(API_HOST)" --port "$(API_PORT)" --reload

worker:
	$(env_shell) LOG_LEVEL="$(LOG_LEVEL)" $(PYTHON) apps/worker/app/main.py

model-gateway:
	PYTHONPATH=apps/model-gateway $(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

web:
	npm run dev:web

admin:
	npm run dev:admin

db-upgrade:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m alembic upgrade head

db-downgrade:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m alembic downgrade -1

db-current:
	$(env_shell) PYTHONPATH=apps/api $(PYTHON) -m alembic current
